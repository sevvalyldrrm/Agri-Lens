"""
Agri-Lens FastAPI application — main entry point.

Endpoints:
  POST /analyze/text                   -> Metin tabanlı analiz (mobil)
  POST /analyze/audio                  -> Ses analizi (mobil)
  POST /analyze/plant-disease/upload   -> Görüntü yükleme ile bitki hastalığı analizi
  GET  /demo/plant-disease/{scenario}  -> Pre-built demo senaryosu
  GET  /demo/live                      -> SSE canlı akış demo
  GET  /demo/live-ui                   -> Tarayıcı demo UI
  GET  /health                         -> Sağlık kontrolü
  GET  /devices/status                 -> IoT cihaz durumu
"""

import base64
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models import (
    AnalysisRequest, DiagnosisResult, IoTSensorData,
    PlantDiseaseRequest, PlantDiseaseResult,
)
from app.gemini_service import GeminiService
from app.iot_handler import get_device_state
from app.demo_scenarios import (
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

# Serve demo images statically at /assets/demo_images/
# Path: monorepo/backend/assets/demo_images/
app.mount(
    "/assets",
    StaticFiles(directory=Path(__file__).parent.parent / "assets"),
    name="assets",
)

# CORS – allow agri-lens-mobile (file:// + any local dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
#  Analysis endpoints
# ---------------------------------------------------------------------------


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


@app.post("/analyze/text", response_model=DiagnosisResult, tags=["analysis"])
async def analyze_text(
    field_id: str = Form("field-A"),
    question: str = Form(...),
    soil_moisture: float = Form(45.0),
    temperature: float = Form(28.0),
    humidity: float = Form(70.0),
    ph_level: float = Form(6.5),
    nitrogen: float = Form(30.0),
    phosphorus: float = Form(20.0),
    potassium: float = Form(25.0),
    light_intensity: float = Form(50000.0),
):
    """
    Text-only analysis — farmer types a question, no image needed.
    """
    service = _require_service()
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
    )
    try:
        return await service.analyze_field(request)
    except Exception as e:
        logger.exception(f"Text analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/analyze/audio", response_model=DiagnosisResult, tags=["analysis"])
async def analyze_audio(
    field_id: str = Form("field-A"),
    soil_moisture: float = Form(45.0),
    temperature: float = Form(28.0),
    humidity: float = Form(70.0),
    ph_level: float = Form(6.5),
    nitrogen: float = Form(30.0),
    phosphorus: float = Form(20.0),
    potassium: float = Form(25.0),
    light_intensity: float = Form(50000.0),
    audio: UploadFile = File(...),
):
    """
    Voice analysis — farmer records a voice question, Gemini transcribes and answers.
    """
    service = _require_service()

    audio_bytes = await audio.read()
    audio_base64 = base64.b64encode(audio_bytes).decode()

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
        question="[Voice message — see audio attachment]",
        sensor_data=sensor_data,
        audio_base64=audio_base64,
    )
    try:
        return await service.analyze_field(request)
    except Exception as e:
        logger.exception(f"Audio analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Audio analysis failed: {str(e)}")


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
async def demo_live_stream(question: str | None = None):
    """
    Real-time SSE stream of the full analysis pipeline.

    Connect with:  curl -N http://localhost:8000/demo/live
    Or open:       http://localhost:8000/demo/live-ui

    Optional query param:
      ?question=Why are my leaves yellow?
    """
    service = _require_service()
    import json

    base_request = build_live_stream_request()
    if question:
        base_request.question = question

    async def event_generator():
        try:
            async for event_json in service.analyze_field_stream(base_request):
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
