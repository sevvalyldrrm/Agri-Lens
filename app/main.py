"""
Agri-Lens FastAPI application — main entry point.

Endpoints:
  POST /analyze                        -> Full multimodal field analysis
  POST /analyze/quick                  -> Form-based analysis (mobile-friendly)
  POST /analyze/demo                   -> Demo with pre-built scenario (no upload needed)
  POST /analyze/plant-disease          -> Leaf image + sensor cross-query
  POST /analyze/plant-disease/upload   -> Form-based image upload
  GET  /demo/plant-disease/{scenario}  -> Pre-built plant-disease scenario
  GET  /demo/live                      -> SSE live stream demo
  GET  /demo/live-ui                   -> Browser demo UI
  GET  /health                         -> Health check
  GET  /devices/status                 -> Current IoT device states
"""

import logging
import os
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse

from app.config import get_settings
from app.models import (
    AnalysisRequest, DiagnosisResult, IoTSensorData,
    PlantDiseaseRequest, PlantDiseaseResult,
)
from app.gemini_service import GeminiService
from app.iot_handler import get_device_state
from app.demo_scenarios import (
    build_drought_stress_request,
    build_live_stream_request,
    build_plant_disease_request,
    PLANT_DISEASE_SCENARIO_KEYS,
)

# ---------------------------------------------------------------------------
#  Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Application lifespan
# ---------------------------------------------------------------------------
gemini_service: GeminiService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global gemini_service
    logger.info("🌱 Agri-Lens starting up...")
    gemini_service = GeminiService()
    logger.info("✅ GeminiService ready.")
    yield
    logger.info("🛑 Agri-Lens shutting down.")


# ---------------------------------------------------------------------------
#  FastAPI app
# ---------------------------------------------------------------------------
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "An AI agronomist in every farmer's pocket. "
        "Analyses field video, audio, and IoT sensor data using the Gemini API."
    ),
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
#  Helper
# ---------------------------------------------------------------------------

def _require_service() -> GeminiService:
    if not gemini_service:
        raise HTTPException(status_code=503, detail="GeminiService not ready yet.")
    return gemini_service


# ---------------------------------------------------------------------------
#  System endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
async def health_check():
    """Application health check."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "gemini_model": settings.gemini_model,
    }


@app.get("/devices/status", tags=["iot"])
async def get_devices_status():
    """Returns the current state of all simulated IoT devices."""
    return {"device_state": get_device_state()}


# ---------------------------------------------------------------------------
#  Field analysis endpoints
# ---------------------------------------------------------------------------

@app.post("/analyze", response_model=DiagnosisResult, tags=["analysis"])
async def analyze_field(request: AnalysisRequest):
    """
    Full multimodal field analysis.

    - **video_path**: Server-side path to the field video file (optional)
    - **audio_base64**: Farmer's voice question, base64-encoded (optional)
    - **sensor_data**: Real-time IoT sensor readings
    - **historical_logs**: Up to 1 year of historical records (Long Context)
    - **question**: Farmer's question in natural language
    """
    service = _require_service()
    try:
        return await service.analyze_field(request)
    except Exception as e:
        logger.exception(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/analyze/quick", response_model=DiagnosisResult, tags=["analysis"])
async def quick_analyze(
    field_id: str = Form(...),
    question: str = Form(...),
    soil_moisture: float = Form(45.0),
    temperature: float = Form(28.0),
    humidity: float = Form(70.0),
    ph_level: float = Form(6.5),
    nitrogen: float = Form(30.0),
    phosphorus: float = Form(20.0),
    potassium: float = Form(25.0),
    light_intensity: float = Form(50000.0),
    video: UploadFile | None = File(None),
):
    """
    Quick analysis via form data — ideal for mobile app integration.
    Video upload is optional.
    """
    service = _require_service()

    video_path = None
    if video:
        suffix = "." + video.filename.split(".")[-1] if video.filename else ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await video.read())
            video_path = tmp.name

    sensor_data = IoTSensorData(
        field_id=field_id,
        soil_moisture=soil_moisture,
        temperature=temperature,
        humidity=humidity,
        ph_level=ph_level,
        nitrogen=nitrogen,
        phosphorus=phosphorus,
        potassium=potassium,
        light_intensity=light_intensity,
        timestamp=datetime.now().isoformat(),
    )

    request = AnalysisRequest(
        field_id=field_id,
        question=question,
        sensor_data=sensor_data,
        video_path=video_path,
    )

    try:
        return await service.analyze_field(request)
    finally:
        if video_path and os.path.exists(video_path):
            os.unlink(video_path)


@app.post("/analyze/demo", response_model=DiagnosisResult, tags=["analysis"])
async def demo_analyze():
    """
    Demo endpoint — tests the full pipeline with a pre-built drought stress scenario.
    Requires a valid API key and network access.
    """
    service = _require_service()
    try:
        return await service.analyze_field(build_drought_stress_request())
    except Exception as e:
        logger.exception(f"Demo analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
#  Plant disease endpoints
# ---------------------------------------------------------------------------

@app.post("/analyze/plant-disease", response_model=PlantDiseaseResult, tags=["plant-disease"])
async def analyze_plant_disease(request: PlantDiseaseRequest):
    """
    Leaf image + IoT sensor cross-query analysis (PlantVillage-style).

    Priority logic:
    - Disease visible BUT moisture < 25% → irrigation priority
    - Leaf yellowing BUT nitrogen < 20 mg/kg → nutrient deficiency priority
    - Disease clearly visible AND moisture sufficient → disease treatment priority
    """
    service = _require_service()
    try:
        return await service.analyze_plant_disease(request)
    except Exception as e:
        logger.exception(f"Plant disease analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/plant-disease/upload", response_model=PlantDiseaseResult, tags=["plant-disease"])
async def analyze_plant_disease_upload(
    field_id: str = Form(...),
    question: str = Form("What is wrong with these leaves and what should I do?"),
    soil_moisture: float = Form(...),
    temperature: float = Form(...),
    humidity: float = Form(65.0),
    ph_level: float = Form(6.5),
    nitrogen: float = Form(28.0),
    phosphorus: float = Form(20.0),
    potassium: float = Form(25.0),
    light_intensity: float = Form(55000.0),
    use_sensor_logs: bool = Form(True),
    image: UploadFile = File(...),
):
    """
    Form-based image upload endpoint — ideal for mobile app integration.
    The image is uploaded directly; sensor values come from form fields.
    """
    service = _require_service()

    suffix = "." + image.filename.split(".")[-1] if image.filename else ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await image.read())
        tmp_path = tmp.name

    sensor_data = IoTSensorData(
        field_id=field_id,
        soil_moisture=soil_moisture,
        temperature=temperature,
        humidity=humidity,
        ph_level=ph_level,
        nitrogen=nitrogen,
        phosphorus=phosphorus,
        potassium=potassium,
        light_intensity=light_intensity,
        timestamp=datetime.now().isoformat(),
    )

    request = PlantDiseaseRequest(
        field_id=field_id,
        question=question,
        image_path=tmp_path,
        sensor_data=sensor_data,
        sensor_log_path="data/sensor_logs.json" if use_sensor_logs else None,
    )

    try:
        return await service.analyze_plant_disease(request)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.get("/demo/plant-disease/{scenario}", response_model=PlantDiseaseResult, tags=["plant-disease"])
async def demo_plant_disease(scenario: str):
    """
    3 pre-built demo scenarios for jury presentation.

    **scenario** values:
    - `late-blight`         : Tomato Late Blight + drought stress
    - `nutrient-deficiency` : Early Blight + nitrogen deficiency
    - `healthy`             : Healthy plant + normal sensors
    """
    service = _require_service()

    if scenario not in PLANT_DISEASE_SCENARIO_KEYS:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario not found. Valid values: {PLANT_DISEASE_SCENARIO_KEYS}",
        )

    try:
        return await service.analyze_plant_disease(build_plant_disease_request(scenario))
    except Exception as e:
        logger.exception(f"Demo plant disease error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
#  Live streaming demo endpoints
# ---------------------------------------------------------------------------

@app.get("/demo/live", tags=["demo"])
async def demo_live_stream():
    """
    Real-time SSE stream of the full analysis pipeline.

    Connect with:  curl -N http://localhost:8000/demo/live
    Or open:       http://localhost:8000/demo/live-ui
    """
    service = _require_service()
    import json

    async def event_generator():
        try:
            async for event_json in service.analyze_field_stream(build_live_stream_request()):
                yield f"data: {event_json}\n\n"
        except Exception as e:
            error = json.dumps({"event": "error", "message": str(e)})
            yield f"data: {error}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/demo/live-ui", response_class=HTMLResponse, tags=["demo"])
async def demo_live_ui():
    """
    Self-contained HTML demo page for jury presentation.
    No frontend framework needed — open in any browser.
    """
    template_path = Path(__file__).parent / "templates" / "live_demo.html"
    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))
