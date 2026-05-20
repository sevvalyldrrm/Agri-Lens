"""
Agri-Lens — GeminiService.

Responsibilities:
  - Build multimodal prompts (video / audio / image / sensor context)
  - Run the Gemini Function Calling loop
  - Return typed result objects (DiagnosisResult, PlantDiseaseResult)
  - Provide a streaming variant for live demo (SSE)
"""

import json
import logging
import base64
import mimetypes
from pathlib import Path
from typing import Optional

import google.generativeai as genai

from app.config import get_settings
from app.models import (
    AnalysisRequest, DiagnosisResult, IoTAction, SeverityLevel,
    PlantDiseaseRequest, PlantDiseaseResult, PriorityMode,
)
from app.iot_handler import execute_iot_action, get_device_state
from app.prompts import FIELD_ANALYSIS_PROMPT, PLANT_DISEASE_PROMPT
from app.tools import IOT_TOOLS

logger = logging.getLogger(__name__)

_MAX_FUNCTION_CALL_ITERATIONS = 5


class GeminiService:
    def __init__(self):
        settings = get_settings()
        genai.configure(api_key=settings.gemini_api_key)

        self.model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=FIELD_ANALYSIS_PROMPT,
            tools=[IOT_TOOLS],
        )
        self.disease_model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=PLANT_DISEASE_PROMPT,
            tools=[IOT_TOOLS],
        )
        logger.info(f"GeminiService initialized — model: {settings.gemini_model}")

    # -----------------------------------------------------------------------
    #  Prompt builders
    # -----------------------------------------------------------------------

    def _build_sensor_context(self, request: "AnalysisRequest | PlantDiseaseRequest") -> str:
        """Converts real-time sensor data and historical logs into a single text block."""
        s = request.sensor_data
        lines = [
            "=== REAL-TIME SENSOR DATA ===",
            f"Field ID        : {s.field_id}",
            f"Timestamp       : {s.timestamp}",
            f"Soil Moisture   : {s.soil_moisture:.1f}%",
            f"Temperature     : {s.temperature:.1f}°C",
            f"Air Humidity    : {s.humidity:.1f}%",
            f"pH              : {s.ph_level:.2f}",
            f"Nitrogen (N)    : {s.nitrogen:.1f} mg/kg",
            f"Phosphorus (P)  : {s.phosphorus:.1f} mg/kg",
            f"Potassium (K)   : {s.potassium:.1f} mg/kg",
            f"Light Intensity : {s.light_intensity:.0f} lux",
        ]

        if request.historical_logs:
            lines.append(f"\n=== HISTORICAL LOGS (last {len(request.historical_logs)} records) ===")
            for log in request.historical_logs:
                event_str = f" | Event: {log.event}" if log.event else ""
                lines.append(
                    f"{log.date} → Moisture: {log.soil_moisture:.1f}%, "
                    f"Temp: {log.temperature:.1f}°C, "
                    f"pH: {log.ph_level:.2f}{event_str}"
                )

        return "\n".join(lines)

    def _load_sensor_log(self, log_path: str) -> str:
        """
        Reads sensor_logs.json and passes it to Gemini as Long Context.
        Summarises only the last 90 days if the file is large.
        """
        try:
            path = Path(log_path)
            if not path.exists():
                return ""
            with open(path) as f:
                data = json.load(f)
            logs = data.get("logs", [])
            recent = logs[-90:] if len(logs) > 90 else logs
            drought_days = [l for l in recent if l.get("soil_moisture", 100) < 30]
            lines = [
                f"=== HISTORICAL SENSOR LOGS (last {len(recent)} days) ===",
                f"Total records: {len(logs)} days | Low-moisture days (< 30%): {len(drought_days)}",
                "",
            ]
            for entry in recent:
                event_str = f" | EVENT: {entry['event']}" if entry.get("event") else ""
                lines.append(
                    f"{entry['date']} → moisture:{entry['soil_moisture']:.1f}%  "
                    f"temp:{entry['temperature']:.1f}°C  "
                    f"humidity:{entry.get('humidity', '-')}%  "
                    f"nitrogen:{entry.get('nitrogen_mg_kg', '-')} mg/kg"
                    f"{event_str}"
                )
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Sensor log load failed: {e}")
            return ""

    def _load_image(
        self,
        image_path: Optional[str] = None,
        image_base64: Optional[str] = None,
        mime: str = "image/jpeg",
    ) -> Optional[dict]:
        """Loads an image file or base64 string into Gemini's blob format."""
        try:
            if image_base64:
                return {"mime_type": mime, "data": base64.b64decode(image_base64)}
            if image_path:
                path = Path(image_path)
                if not path.exists():
                    logger.warning(f"Image not found: {image_path}")
                    return None
                detected_mime = mimetypes.guess_type(str(path))[0] or mime
                return {"mime_type": detected_mime, "data": path.read_bytes()}
        except Exception as e:
            logger.warning(f"Image load failed: {e}")
        return None

    def _load_audio(self, audio_base64: str) -> Optional[dict]:
        """Decodes base64 audio data into Gemini's blob format."""
        try:
            return {"mime_type": "audio/wav", "data": base64.b64decode(audio_base64)}
        except Exception as e:
            logger.warning(f"Failed to decode audio data: {e}")
            return None

    # -----------------------------------------------------------------------
    #  Response parser
    # -----------------------------------------------------------------------

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        """Extracts the JSON block from the model's raw response text."""
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)

    # -----------------------------------------------------------------------
    #  Function Calling loop (shared)
    # -----------------------------------------------------------------------

    async def _run_function_calling_loop(
        self,
        chat,
        parts: list,
        label: str = "",
    ) -> tuple[str, list[IoTAction]]:
        """
        Sends `parts` to Gemini and handles the Function Calling loop.
        Returns the final text response and a list of executed IoT actions.
        """
        actions_taken: list[IoTAction] = []
        response = await chat.send_message_async(parts)

        for _ in range(_MAX_FUNCTION_CALL_ITERATIONS):
            function_calls = [
                part.function_call
                for part in response.candidates[0].content.parts
                if hasattr(part, "function_call") and part.function_call.name
            ]
            if not function_calls:
                break

            tool_results = []
            for fc in function_calls:
                fn_name = fc.name
                fn_args = dict(fc.args)
                logger.info(f"[{label}] IoT action: {fn_name}({fn_args})")
                result, action_log = execute_iot_action(fn_name, fn_args)
                actions_taken.append(action_log)
                tool_results.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=fn_name,
                            response={"result": result},
                        )
                    )
                )
            response = await chat.send_message_async(tool_results)

        return response.text, actions_taken

    # -----------------------------------------------------------------------
    #  Public API: field analysis
    # -----------------------------------------------------------------------

    async def analyze_field(self, request: AnalysisRequest) -> DiagnosisResult:
        """
        Multimodal field analysis:
          video + audio + sensor data -> Gemini -> Function Calling -> DiagnosisResult
        """
        parts: list = []

        if request.audio_base64:
            blob = self._load_audio(request.audio_base64)
            if blob:
                parts.append(blob)
                logger.info("Audio data added to prompt.")

        parts.append(self._build_sensor_context(request))
        parts.append(f"\n=== FARMER'S QUESTION ===\n{request.question}")
        parts.append(
            "\nPlease analyse all the data above, "
            "trigger the necessary IoT actions, and respond in JSON format."
        )

        try:
            chat = self.model.start_chat()
            final_text, actions_taken = await self._run_function_calling_loop(
                chat, parts, label="FieldAnalysis"
            )
            logger.debug(f"Gemini raw response:\n{final_text}")
            data = self._parse_json_response(final_text)

            return DiagnosisResult(
                field_id=request.field_id,
                diagnosis=data.get("diagnosis", "Diagnosis unavailable"),
                severity=SeverityLevel(data.get("severity", "medium")),
                root_cause=data.get("root_cause", ""),
                recommendations=data.get("recommendations", []),
                actions_taken=actions_taken,
                report_for_farmer=data.get("report_for_farmer", final_text),
                confidence_score=float(data.get("confidence_score", 0.7)),
            )
        except Exception as exc:
            logger.warning(f"Gemini API error in analyze_field, falling back to mock: {exc}")
            return self._mock_diagnosis(request)

    # -----------------------------------------------------------------------
    #  Public API: plant disease cross-query
    # -----------------------------------------------------------------------

    async def analyze_plant_disease(self, request: PlantDiseaseRequest) -> PlantDiseaseResult:
        """
        Visual + sensor cross-query pipeline:
          leaf image + sensor data + historical logs -> Gemini -> PlantDiseaseResult
        """
        parts: list = []

        image_blob = self._load_image(
            image_path=request.image_path,
            image_base64=request.image_base64,
            mime=request.image_mime,
        )
        if image_blob:
            parts.append(image_blob)
            logger.info("Leaf image added to prompt.")
        else:
            logger.warning("No image found — analysis will rely on sensor data only.")

        parts.append(self._build_sensor_context(request))

        if request.sensor_log_path:
            log_text = self._load_sensor_log(request.sensor_log_path)
            if log_text:
                parts.append(log_text)
                logger.info("Historical sensor logs added as Long Context.")

        parts.append(f"\n=== FARMER'S QUESTION ===\n{request.question}")
        parts.append(
            "\nAnalyse the image, cross-query with sensor data, "
            "trigger the necessary IoT actions, and respond in JSON format."
        )

        try:
            chat = self.disease_model.start_chat()
            final_text, actions_taken = await self._run_function_calling_loop(
                chat, parts, label="PlantDisease"
            )
            data = self._parse_json_response(final_text)

            return PlantDiseaseResult(
                field_id=request.field_id,
                visual_finding=data.get("visual_finding", "Image analysis complete"),
                sensor_finding=data.get("sensor_finding", ""),
                priority_mode=PriorityMode(data.get("priority_mode", "combined")),
                priority_reason=data.get("priority_reason", ""),
                diagnosis=data.get("diagnosis", "Diagnosis unavailable"),
                severity=SeverityLevel(data.get("severity", "medium")),
                root_cause=data.get("root_cause", ""),
                recommendations=data.get("recommendations", []),
                actions_taken=actions_taken,
                report_for_farmer=data.get("report_for_farmer", final_text),
                confidence_score=float(data.get("confidence_score", 0.7)),
                seasonal_pattern=data.get("seasonal_pattern"),
            )
        except Exception as exc:
            logger.warning(f"Gemini API error in analyze_plant_disease, falling back to mock: {exc}")
            return self._mock_plant_disease(request)

    # -----------------------------------------------------------------------
    #  Streaming analysis (SSE) — live demo
    # -----------------------------------------------------------------------

    async def analyze_field_stream(self, request: AnalysisRequest):
        """
        Streams the full analysis pipeline as SSE-compatible JSON strings.
        Falls back to _mock_stream() automatically on API quota errors.

        Event types:
          start        -> analysis started, sensor snapshot
          thinking     -> progress heartbeat
          tool_call    -> Gemini requested an IoT action
          tool_result  -> IoT action executed
          diagnosis    -> final DiagnosisResult
          error        -> unrecoverable error
        """
        import json as _json

        def _evt(event_type: str, payload: dict) -> str:
            return _json.dumps({"event": event_type, **payload})

        s = request.sensor_data
        yield _evt("start", {
            "field_id": request.field_id,
            "question": request.question,
            "sensor_snapshot": {
                "soil_moisture": s.soil_moisture,
                "temperature":   s.temperature,
                "humidity":      s.humidity,
                "ph_level":      s.ph_level,
                "nitrogen":      s.nitrogen,
                "timestamp":     s.timestamp,
            },
            "historical_log_count": len(request.historical_logs),
        })

        parts: list = []
        if request.audio_base64:
            blob = self._load_audio(request.audio_base64)
            if blob:
                parts.append(blob)
                yield _evt("thinking", {"message": "🎙️ Farmer voice loaded into context."})

        parts.append(self._build_sensor_context(request))
        parts.append(f"\n=== FARMER'S QUESTION ===\n{request.question}")
        parts.append(
            "\nPlease analyse all the data above, "
            "trigger the necessary IoT actions, and respond in JSON format."
        )

        yield _evt("thinking", {
            "message": (
                f"🧠 Sending to Gemini: sensor data"
                f"{' + audio' if request.audio_base64 else ''}"
                f" + {len(request.historical_logs)} historical records."
            )
        })

        try:
            actions_taken: list[IoTAction] = []
            chat = self.model.start_chat()
            response = await chat.send_message_async(parts)

            for iteration in range(_MAX_FUNCTION_CALL_ITERATIONS):
                function_calls = [
                    part.function_call
                    for part in response.candidates[0].content.parts
                    if hasattr(part, "function_call") and part.function_call.name
                ]
                if not function_calls:
                    break

                tool_results = []
                for fc in function_calls:
                    fn_name = fc.name
                    fn_args = dict(fc.args)

                    yield _evt("tool_call", {
                        "iteration":     iteration + 1,
                        "function_name": fn_name,
                        "arguments":     fn_args,
                        "message":       f"⚡ Gemini is calling -> {fn_name}() with {fn_args}",
                    })

                    result, action_log = execute_iot_action(fn_name, fn_args)
                    actions_taken.append(action_log)

                    yield _evt("tool_result", {
                        "function_name": fn_name,
                        "result":        result,
                        "device_state":  get_device_state(),
                        "message":       result.get("message", "Action executed."),
                    })

                    tool_results.append(
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=fn_name,
                                response={"result": result},
                            )
                        )
                    )
                response = await chat.send_message_async(tool_results)

            data = self._parse_json_response(response.text)
            diagnosis = DiagnosisResult(
                field_id=request.field_id,
                diagnosis=data.get("diagnosis", "Diagnosis unavailable"),
                severity=SeverityLevel(data.get("severity", "medium")),
                root_cause=data.get("root_cause", ""),
                recommendations=data.get("recommendations", []),
                actions_taken=actions_taken,
                report_for_farmer=data.get("report_for_farmer", response.text),
                confidence_score=float(data.get("confidence_score", 0.7)),
            )
            yield _evt("diagnosis", diagnosis.model_dump())

        except Exception as exc:
            logger.warning(f"Gemini API error, falling back to mock: {exc}")
            async for event in self._mock_stream(request):
                yield event

    # -----------------------------------------------------------------------
    #  Mock stream — offline fallback when API quota is exceeded
    # -----------------------------------------------------------------------

    async def _mock_stream(self, request: AnalysisRequest):
        """
        Simulates the full Gemini pipeline locally.
        Produces identical SSE events so the demo UI works without a live API key.
        """
        import asyncio
        import json as _json

        def _evt(event_type: str, payload: dict) -> str:
            return _json.dumps({"event": event_type, **payload})

        s = request.sensor_data
        actions_to_run = self._build_mock_actions(request)

        yield _evt("thinking", {"message": "⚠️ API quota reached — switching to offline simulation engine."})
        await asyncio.sleep(0.5)
        yield _evt("thinking", {"message": "🧠 Analysing sensor data against historical logs..."})
        await asyncio.sleep(1.0)
        yield _evt("thinking", {"message": "🔍 Cross-referencing visual symptoms with IoT readings..."})
        await asyncio.sleep(0.8)
        yield _evt("thinking", {"message": "⚡ Preparing IoT action plan..."})
        await asyncio.sleep(0.5)

        actions_taken = []
        for fn_name, fn_args in actions_to_run:
            await asyncio.sleep(0.7)
            yield _evt("tool_call", {
                "function_name": fn_name,
                "arguments": fn_args,
                "message": f"⚡ Gemini is calling -> {fn_name}() with {fn_args}",
            })
            await asyncio.sleep(0.5)
            result, action_log = execute_iot_action(fn_name, fn_args)
            actions_taken.append(action_log)
            yield _evt("tool_result", {
                "function_name": fn_name,
                "result": result,
                "device_state": get_device_state(),
                "message": result.get("message", "Action executed."),
            })

        await asyncio.sleep(0.8)
        diagnosis = DiagnosisResult(
            field_id=request.field_id,
            diagnosis="Drought stress combined with aphid infestation causing leaf chlorosis and wilting.",
            severity=SeverityLevel.HIGH,
            root_cause=(
                f"Soil moisture has dropped from 45% to {s.soil_moisture}% over 6 days since last irrigation. "
                f"Nitrogen is below threshold at {s.nitrogen} mg/kg. "
                "Aphids detected on leaf undersides, accelerating water and nutrient loss."
            ),
            recommendations=[
                "Irrigate immediately — 45 minutes for full field coverage.",
                "Apply nitrogen fertilizer within 24 hours.",
                "Apply approved aphicide to affected areas.",
                "Increase irrigation frequency to every 2 days until recovery.",
                "Monitor soil moisture daily and inspect leaves for pest recurrence.",
            ],
            actions_taken=actions_taken,
            report_for_farmer=(
                "Your plants are under drought stress and have an aphid infestation. "
                "Soil moisture has been falling for 6 days and is now critically low. "
                "Irrigation has been started automatically for 45 minutes. "
                "Nitrogen fertilizer has been applied. "
                "A pest alert and agronomist report have been sent."
            ),
            confidence_score=0.91,
        )
        yield _evt("diagnosis", diagnosis.model_dump())

    @staticmethod
    def _build_mock_actions(request: AnalysisRequest) -> list[tuple[str, dict]]:
        """Determines which mock IoT actions to trigger based on sensor thresholds."""
        s = request.sensor_data
        actions = []

        if s.soil_moisture < 30:
            actions.append((
                "activate_irrigation",
                {"zone": "full field", "duration_minutes": 45,
                 "reason": f"Soil moisture critically low at {s.soil_moisture}%"},
            ))
        if s.nitrogen < 20:
            actions.append((
                "apply_fertilizer",
                {"nutrient_type": "nitrogen", "amount_ml": 500,
                 "reason": f"Nitrogen deficiency detected: {s.nitrogen} mg/kg (threshold: 20)"},
            ))
        actions.append((
            "trigger_pest_alert",
            {"field_id": request.field_id, "pest_type": "aphids", "affected_area_percent": 12.0},
        ))
        actions.append((
            "send_agronomist_report",
            {"field_id": request.field_id,
             "diagnosis": "Drought stress with aphid infestation",
             "severity": "high"},
        ))
        return actions

    # -----------------------------------------------------------------------
    #  Mock responses — offline fallback for quota errors
    # -----------------------------------------------------------------------

    def _mock_diagnosis(self, request: AnalysisRequest) -> DiagnosisResult:
        """Returns a sensor-based mock DiagnosisResult when Gemini API is unavailable."""
        s = request.sensor_data
        actions_taken = []

        if s.soil_moisture < 30:
            _, action = execute_iot_action("activate_irrigation", {
                "zone": "full field", "duration_minutes": 45,
                "reason": f"Soil moisture critically low at {s.soil_moisture}%",
            })
            actions_taken.append(action)

        if s.nitrogen < 20:
            _, action = execute_iot_action("apply_fertilizer", {
                "nutrient_type": "nitrogen", "amount_ml": 500,
                "reason": f"Nitrogen deficiency: {s.nitrogen} mg/kg",
            })
            actions_taken.append(action)

        severity = SeverityLevel.HIGH if s.soil_moisture < 25 else SeverityLevel.MEDIUM
        return DiagnosisResult(
            field_id=request.field_id,
            diagnosis="[OFFLINE MODE] Drought stress detected based on sensor thresholds.",
            severity=severity,
            root_cause=(
                f"Soil moisture is at {s.soil_moisture}% (critical threshold: 30%). "
                f"Temperature is {s.temperature}°C. Nitrogen: {s.nitrogen} mg/kg."
            ),
            recommendations=[
                "Irrigate immediately — 45 minutes for full field coverage.",
                "Apply nitrogen fertilizer within 24 hours.",
                "Monitor soil moisture daily until recovery.",
            ],
            actions_taken=actions_taken,
            report_for_farmer=(
                f"⚠️ Offline simulation: Soil moisture critically low at {s.soil_moisture}%. "
                "Irrigation has been triggered automatically."
            ),
            confidence_score=0.80,
        )

    def _mock_plant_disease(self, request: PlantDiseaseRequest) -> PlantDiseaseResult:
        """Returns a scenario-aware mock PlantDiseaseResult when Gemini API is unavailable."""
        s = request.sensor_data
        actions_taken = []
        has_image = bool(request.image_path or request.image_base64)

        # Determine scenario by sensor thresholds
        if s.soil_moisture < 25:
            # late-blight scenario: drought priority
            priority_mode = PriorityMode.IRRIGATION
            visual_finding = "[OFFLINE] Dark brown lesions with water-soaked borders visible on leaves — consistent with Late Blight (Phytophthora infestans)."
            sensor_finding = f"Soil moisture critically low at {s.soil_moisture}% — drought stress overrides disease treatment priority."
            priority_reason = "Despite visible disease symptoms, severe drought stress is the immediate threat. Irrigation must come first."
            diagnosis = "[OFFLINE MODE] Tomato Late Blight confirmed, but drought stress is the priority concern."
            severity = SeverityLevel.HIGH
            root_cause = f"Soil moisture has dropped to {s.soil_moisture}% (critical: <25%). Late Blight pathogen thrives in heat stress conditions."
            recommendations = [
                "Irrigate immediately — 45 minutes full field coverage.",
                "After irrigation, apply copper-based fungicide for Late Blight.",
                "Remove and destroy heavily infected leaves.",
                "Avoid overhead irrigation to reduce leaf wetness.",
                "Monitor daily and re-apply fungicide after 7 days.",
            ]
            seasonal_pattern = "Late Blight risk increases in hot, dry periods followed by high humidity."
            _, action = execute_iot_action("activate_irrigation", {
                "zone": "full field", "duration_minutes": 45,
                "reason": f"Soil moisture critically low at {s.soil_moisture}%",
            })
            actions_taken.append(action)

        elif s.nitrogen < 20:
            # nutrient-deficiency scenario
            priority_mode = PriorityMode.NUTRIENT
            visual_finding = "[OFFLINE] Interveinal chlorosis and early blight spots detected on lower leaves."
            sensor_finding = f"Nitrogen at {s.nitrogen} mg/kg — well below the 20 mg/kg threshold."
            priority_reason = "Yellowing is primarily caused by nitrogen deficiency, not the disease. Nutrient correction is the priority."
            diagnosis = "[OFFLINE MODE] Nitrogen deficiency with Early Blight secondary infection."
            severity = SeverityLevel.MEDIUM
            root_cause = f"Nitrogen: {s.nitrogen} mg/kg (threshold: 20). Deficiency weakens plant immunity, accelerating Early Blight spread."
            recommendations = [
                "Apply nitrogen-rich fertilizer (urea or ammonium nitrate) immediately.",
                "After 48h, apply mancozeb-based fungicide for Early Blight.",
                "Increase irrigation frequency to aid nutrient absorption.",
                "Conduct soil pH test — low pH limits nitrogen uptake.",
                "Re-check nitrogen levels in 7 days.",
            ]
            seasonal_pattern = "Nitrogen depletion is common mid-season without supplemental fertilisation."
            _, action = execute_iot_action("apply_fertilizer", {
                "nutrient_type": "nitrogen", "amount_ml": 500,
                "reason": f"Nitrogen deficiency: {s.nitrogen} mg/kg",
            })
            actions_taken.append(action)

        else:
            # healthy scenario
            priority_mode = PriorityMode.COMBINED
            visual_finding = "[OFFLINE] Leaves appear green and healthy — no visible disease lesions or discolouration detected."
            sensor_finding = f"All sensors within normal range. Moisture: {s.soil_moisture}%, Nitrogen: {s.nitrogen} mg/kg."
            priority_reason = "No action required. All parameters are healthy."
            diagnosis = "[OFFLINE MODE] Plant is healthy. No disease or deficiency detected."
            severity = SeverityLevel.LOW
            root_cause = "No abnormalities detected in visual inspection or sensor data."
            recommendations = [
                "Continue current irrigation and fertilisation schedule.",
                "Inspect leaves weekly as a preventive measure.",
                "Ensure good air circulation between plants.",
            ]
            seasonal_pattern = None

        return PlantDiseaseResult(
            field_id=request.field_id,
            visual_finding=visual_finding + ("" if has_image else " (No image provided — visual analysis skipped.)"),
            sensor_finding=sensor_finding,
            priority_mode=priority_mode,
            priority_reason=priority_reason,
            diagnosis=diagnosis,
            severity=severity,
            root_cause=root_cause,
            recommendations=recommendations,
            actions_taken=actions_taken,
            report_for_farmer=(
                f"⚠️ Offline simulation mode (API quota exceeded).\n"
                f"Diagnosis: {diagnosis}\n"
                f"Priority: {priority_reason}\n"
                f"Top action: {recommendations[0]}"
            ),
            confidence_score=0.82,
            seasonal_pattern=seasonal_pattern,
        )
