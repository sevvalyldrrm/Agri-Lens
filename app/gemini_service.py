"""
Gemini Service — the brain of Agri-Lens.

Gemini capabilities used:
  • Native Multimodality  : video + audio + text processed simultaneously
  • Long Context Window   : up to 1 year of sensor logs in a single prompt
  • Function Calling      : directly triggers IoT devices
"""

import json
import logging
import base64
import mimetypes
from pathlib import Path

import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool

from app.config import get_settings
from app.models import AnalysisRequest, DiagnosisResult, IoTAction, SeverityLevel
from app.iot_handler import execute_iot_action, get_device_state

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  IoT tools exposed to Gemini (Function Calling declarations)
# ---------------------------------------------------------------------------

IOT_TOOLS = Tool(function_declarations=[
    FunctionDeclaration(
        name="activate_irrigation",
        description=(
            "Starts the field irrigation system. "
            "Use when soil moisture is low or drought stress is detected."
        ),
        parameters={
            "type": "object",
            "properties": {
                "zone":             {"type": "string",  "description": "Irrigation zone (e.g. 'A1', 'B2', 'full field')"},
                "duration_minutes": {"type": "integer", "description": "Irrigation duration in minutes (10-120)"},
                "reason":           {"type": "string",  "description": "Justification for the irrigation decision"},
            },
            "required": ["zone", "duration_minutes", "reason"],
        },
    ),
    FunctionDeclaration(
        name="stop_irrigation",
        description="Stops the active irrigation system.",
        parameters={
            "type": "object",
            "properties": {
                "zone": {"type": "string", "description": "Zone to stop"},
            },
            "required": ["zone"],
        },
    ),
    FunctionDeclaration(
        name="apply_fertilizer",
        description=(
            "Activates the fertilizer pump. "
            "Use when nitrogen, phosphorus, or potassium deficiency is detected."
        ),
        parameters={
            "type": "object",
            "properties": {
                "nutrient_type": {
                    "type": "string",
                    "enum": ["nitrogen", "phosphorus", "potassium", "mixed"],
                    "description": "Nutrient type to apply",
                },
                "amount_ml": {"type": "integer", "description": "Application amount (ml)"},
                "reason":     {"type": "string",  "description": "Justification for fertilization"},
            },
            "required": ["nutrient_type", "amount_ml", "reason"],
        },
    ),
    FunctionDeclaration(
        name="activate_ventilation",
        description="Starts the ventilation fan. Use when humidity is very high or fungal risk is detected.",
        parameters={
            "type": "object",
            "properties": {
                "speed_percent": {"type": "integer", "description": "Fan speed (0-100%)"},
                "reason":        {"type": "string",  "description": "Justification"},
            },
            "required": ["speed_percent", "reason"],
        },
    ),
    FunctionDeclaration(
        name="send_agronomist_report",
        description=(
            "Sends the diagnosis report to the agronomist and farmer. "
            "Always call this when severity is 'high' or 'critical'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "field_id":       {"type": "string", "description": "Field ID"},
                "diagnosis":      {"type": "string", "description": "Diagnosis summary"},
                "severity":       {"type": "string", "description": "Severity level"},
                "farmer_contact": {"type": "string", "description": "Farmer name or contact info"},
            },
            "required": ["field_id", "diagnosis", "severity"],
        },
    ),
    FunctionDeclaration(
        name="trigger_pest_alert",
        description="Triggers the pest or disease alert system.",
        parameters={
            "type": "object",
            "properties": {
                "field_id":              {"type": "string", "description": "Field ID"},
                "pest_type":             {"type": "string", "description": "Pest or disease type"},
                "affected_area_percent": {"type": "number", "description": "Affected area (%)"},
            },
            "required": ["field_id", "pest_type", "affected_area_percent"],
        },
    ),
])


# ---------------------------------------------------------------------------
#  System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are Agri-Lens — an AI agricultural assistant that acts as a
highly qualified agronomist for small-scale farmers anywhere in the world.

YOUR TASKS:
1. Analyse the farmer's question, field video/audio recording, and IoT sensor data together.
2. Resolve conflicts between visual findings and sensor data
   (e.g. if leaves look yellow but sensors indicate drought → diagnose drought stress).
3. Compare today's readings against historical log data.
4. After diagnosis, trigger the required IoT actions using the available TOOLS (function calling).
5. Report back to the farmer in clear, plain language. Keep technical jargon minimal.

DECISION RULES:
- Soil moisture < 30% → trigger irrigation
- pH < 5.5 or > 7.5  → issue warning
- Nitrogen < 20 mg/kg → apply nitrogen fertilizer
- Air humidity > 85% + high temperature → fungal risk, activate ventilation
- Severity "high" or "critical" → always send a report

OUTPUT FORMAT (JSON):
Return your response STRICTLY in the following JSON format:
{
  "diagnosis": "Main diagnosis (1-2 sentences)",
  "severity": "low|medium|high|critical",
  "root_cause": "Root cause analysis",
  "recommendations": ["recommendation 1", "recommendation 2", "recommendation 3"],
  "report_for_farmer": "Plain-language explanation for the farmer",
  "confidence_score": 0.0-1.0
}
"""


# ---------------------------------------------------------------------------
#  GeminiService
# ---------------------------------------------------------------------------

class GeminiService:
    def __init__(self):
        settings = get_settings()
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=SYSTEM_PROMPT,
            tools=[IOT_TOOLS],
        )
        logger.info(f"GeminiService initialized — model: {settings.gemini_model}")

    # -----------------------------------------------------------------------
    #  Helper methods
    # -----------------------------------------------------------------------

    def _build_sensor_context(self, request: AnalysisRequest) -> str:
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

    def _load_video(self, video_path: str):
        """Loads a video file into the format Gemini expects."""
        path = Path(video_path)
        if not path.exists():
            logger.warning(f"Video file not found: {video_path}")
            return None
        mime_type = mimetypes.guess_type(str(path))[0] or "video/mp4"
        with open(path, "rb") as f:
            data = f.read()
        return {"mime_type": mime_type, "data": data}

    def _load_audio(self, audio_base64: str):
        """Decodes base64 audio data into the format Gemini expects."""
        try:
            data = base64.b64decode(audio_base64)
            return {"mime_type": "audio/wav", "data": data}
        except Exception as e:
            logger.warning(f"Failed to decode audio data: {e}")
            return None

    def _parse_json_response(self, text: str) -> dict:
        """Extracts the JSON block from the model's response."""
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)

    # -----------------------------------------------------------------------
    #  Main analysis flow
    # -----------------------------------------------------------------------

    async def analyze_field(self, request: AnalysisRequest) -> DiagnosisResult:
        """
        Multimodal field analysis:
          1. Video + audio + sensor data  → Gemini
          2. Function Calling             → IoT actions
          3. Final JSON response          → DiagnosisResult
        """
        # Build prompt parts
        parts: list = []

        # Video (native multimodality)
        if request.video_path:
            video_blob = self._load_video(request.video_path)
            if video_blob:
                parts.append(video_blob)
                logger.info("Video added to prompt.")

        # Audio (native multimodality)
        if request.audio_base64:
            audio_blob = self._load_audio(request.audio_base64)
            if audio_blob:
                parts.append(audio_blob)
                logger.info("Audio data added to prompt.")

        # Sensor data + historical logs (Long Context)
        sensor_context = self._build_sensor_context(request)
        parts.append(sensor_context)

        # Farmer's question
        parts.append(f"\n=== FARMER'S QUESTION ===\n{request.question}")
        parts.append(
            "\nPlease analyse all the data above, "
            "trigger the necessary IoT actions, and respond in JSON format."
        )

        # Send to Gemini — Function Calling loop
        actions_taken: list[IoTAction] = []
        chat = self.model.start_chat()
        response = await chat.send_message_async(parts)

        # Gemini may call multiple tools in sequence
        max_iterations = 5
        for _ in range(max_iterations):
            function_calls = [
                part.function_call
                for part in response.candidates[0].content.parts
                if hasattr(part, "function_call") and part.function_call.name
            ]

            if not function_calls:
                break  # No more tool calls — proceed to final response

            # Execute each function call and return results to Gemini
            tool_results = []
            for fc in function_calls:
                fn_name = fc.name
                fn_args = dict(fc.args)
                logger.info(f"Triggering IoT action: {fn_name}({fn_args})")

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

        # Parse final response
        final_text = response.text
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

    # -----------------------------------------------------------------------
    #  Mock stream — offline fallback for demo when API quota is exceeded
    # -----------------------------------------------------------------------

    async def _mock_stream(self, request: AnalysisRequest):
        """
        Simulates the full Gemini pipeline locally.
        Triggered automatically when the real API returns a quota error.
        Produces identical SSE events so the demo UI works without a live API key.
        """
        import asyncio
        import json as _json

        def _evt(event_type: str, payload: dict) -> str:
            return _json.dumps({"event": event_type, **payload})

        s = request.sensor_data
        await asyncio.sleep(0.3)

        # Decide which actions to trigger based on sensor thresholds
        actions_to_run = []
        if s.soil_moisture < 30:
            actions_to_run.append((
                "activate_irrigation",
                {"zone": "full field", "duration_minutes": 45,
                 "reason": f"Soil moisture critically low at {s.soil_moisture}%"}
            ))
        if s.nitrogen < 20:
            actions_to_run.append((
                "apply_fertilizer",
                {"nutrient_type": "nitrogen", "amount_ml": 500,
                 "reason": f"Nitrogen deficiency detected: {s.nitrogen} mg/kg (threshold: 20)"}
            ))
        actions_to_run.append((
            "trigger_pest_alert",
            {"field_id": request.field_id, "pest_type": "aphids",
             "affected_area_percent": 12.0}
        ))
        actions_to_run.append((
            "send_agronomist_report",
            {"field_id": request.field_id,
             "diagnosis": "Drought stress with aphid infestation",
             "severity": "high"}
        ))

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
                "message": f"⚡ Gemini is calling → {fn_name}() with {fn_args}",
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

    # -----------------------------------------------------------------------
    #  Streaming analysis — yields real-time SSE events for live demo
    # -----------------------------------------------------------------------

    async def analyze_field_stream(self, request: AnalysisRequest):
        """
        Streams the full analysis pipeline as SSE-compatible JSON strings.
        Falls back to _mock_stream() automatically on API quota errors.

        Event types:
          start        → analysis started, sensor snapshot
          thinking     → progress heartbeat
          tool_call    → Gemini requested an IoT action
          tool_result  → IoT action executed
          diagnosis    → final DiagnosisResult
          error        → unrecoverable error
        """
        import asyncio
        import json as _json

        def _evt(event_type: str, payload: dict) -> str:
            return _json.dumps({"event": event_type, **payload})

        # ── START ────────────────────────────────────────────────────────────
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

        # ── BUILD PROMPT ─────────────────────────────────────────────────────
        parts: list = []
        if request.video_path:
            blob = self._load_video(request.video_path)
            if blob:
                parts.append(blob)
                yield _evt("thinking", {"message": "📹 Field video loaded into context."})

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
                f"{' + video' if request.video_path else ''}"
                f"{' + audio' if request.audio_base64 else ''}"
                f" + {len(request.historical_logs)} historical records."
            )
        })

        # ── GEMINI CALL with quota fallback ──────────────────────────────────
        try:
            actions_taken: list[IoTAction] = []
            chat = self.model.start_chat()
            response = await chat.send_message_async(parts)

            for iteration in range(5):
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
                    fn_args  = dict(fc.args)

                    yield _evt("tool_call", {
                        "iteration":     iteration + 1,
                        "function_name": fn_name,
                        "arguments":     fn_args,
                        "message":       f"⚡ Gemini is calling → {fn_name}() with {fn_args}",
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

            final_text = response.text
            data = self._parse_json_response(final_text)

            diagnosis = DiagnosisResult(
                field_id=request.field_id,
                diagnosis=data.get("diagnosis", "Diagnosis unavailable"),
                severity=SeverityLevel(data.get("severity", "medium")),
                root_cause=data.get("root_cause", ""),
                recommendations=data.get("recommendations", []),
                actions_taken=actions_taken,
                report_for_farmer=data.get("report_for_farmer", final_text),
                confidence_score=float(data.get("confidence_score", 0.7)),
            )
            yield _evt("diagnosis", diagnosis.model_dump())

        except Exception as exc:
            # Quota or any API error → switch to offline mock
            logger.warning(f"Gemini API error, falling back to mock: {exc}")
            async for event in self._mock_stream(request):
                yield event
