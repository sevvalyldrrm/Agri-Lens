"""
Agri-Lens FastAPI application — main entry point.

Endpoints:
  POST /analyze         → Full multimodal field analysis (video + audio + sensors)
  POST /analyze/quick   → Form-based analysis (mobile-friendly)
  POST /analyze/demo    → Demo with pre-built scenario (no upload needed)
  GET  /health          → Health check
  GET  /devices/status  → Current IoT device states
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse

from app.config import get_settings
from app.models import AnalysisRequest, DiagnosisResult, IoTSensorData, HistoricalLog
from app.gemini_service import GeminiService
from app.iot_handler import get_device_state

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
#  Endpoints
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
    if not gemini_service:
        raise HTTPException(status_code=503, detail="GeminiService not ready yet.")
    try:
        result = await gemini_service.analyze_field(request)
        return result
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
    if not gemini_service:
        raise HTTPException(status_code=503, detail="GeminiService not ready yet.")

    from datetime import datetime
    import tempfile, os

    # Save video to a temp file if provided
    video_path = None
    if video:
        suffix = "." + video.filename.split(".")[-1] if video.filename else ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await video.read()
            tmp.write(content)
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
        result = await gemini_service.analyze_field(request)
        return result
    finally:
        # Clean up temp video file
        if video_path and os.path.exists(video_path):
            os.unlink(video_path)


@app.post("/analyze/demo", response_model=DiagnosisResult, tags=["analysis"])
async def demo_analyze():
    """
    Demo endpoint — tests the full pipeline with a pre-built drought stress scenario.
    Requires a valid API key and network access.
    """
    if not gemini_service:
        raise HTTPException(status_code=503, detail="GeminiService not ready yet.")

    from datetime import datetime, timedelta

    # Scenario: drought stress — soil moisture critically low
    sensor_data = IoTSensorData(
        field_id="FIELD-001",
        soil_moisture=18.5,       # ← critically low (threshold: 30%)
        temperature=34.2,
        humidity=45.0,
        ph_level=6.8,
        nitrogen=22.0,
        phosphorus=18.5,
        potassium=24.0,
        light_intensity=75000.0,
        timestamp=datetime.now().isoformat(),
    )

    # Last 7 days of logs (Long Context demo)
    historical_logs = [
        HistoricalLog(
            date=(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d"),
            soil_moisture=45.0 - i * 3.5,
            temperature=28.0 + i * 0.8,
            ph_level=6.8,
            event="irrigation" if i == 6 else None,
        )
        for i in range(7)
    ]

    request = AnalysisRequest(
        field_id="FIELD-001",
        question="Why are the leaves turning yellow and starting to droop? What should I do?",
        sensor_data=sensor_data,
        historical_logs=historical_logs,
    )

    try:
        result = await gemini_service.analyze_field(request)
        return result
    except Exception as e:
        logger.exception(f"Demo analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
#  Live streaming demo — SSE endpoint (jüri için)
# ---------------------------------------------------------------------------

@app.get("/demo/live", tags=["demo"])
async def demo_live_stream():
    """
    Real-time SSE stream of the full analysis pipeline.
    Shows every step: sensor ingestion → Gemini thinking →
    function calls → IoT actions → final diagnosis.

    Connect with:  curl -N http://localhost:8000/demo/live
    Or open:       http://localhost:8000/demo/live-ui
    """
    if not gemini_service:
        raise HTTPException(status_code=503, detail="GeminiService not ready yet.")

    from datetime import datetime, timedelta
    import json

    # ── Demo scenario: drought stress + pest detection ───────────────────────
    sensor_data = IoTSensorData(
        field_id="FIELD-001",
        soil_moisture=18.5,       # critically low  (threshold: 30%)
        temperature=34.2,
        humidity=47.0,
        ph_level=6.8,
        nitrogen=17.5,            # below threshold (threshold: 20 mg/kg)
        phosphorus=18.5,
        potassium=24.0,
        light_intensity=75000.0,
        timestamp=datetime.now().isoformat(),
    )

    historical_logs = [
        HistoricalLog(
            date=(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d"),
            soil_moisture=45.0 - i * 3.5,
            temperature=28.0 + i * 0.8,
            ph_level=6.8,
            event="irrigation" if i == 6 else None,
        )
        for i in range(7)
    ]

    request = AnalysisRequest(
        field_id="FIELD-001",
        question=(
            "The leaves are turning yellow and I can see small insects "
            "on the undersides. What is happening and what should I do?"
        ),
        sensor_data=sensor_data,
        historical_logs=historical_logs,
    )

    async def event_generator():
        try:
            async for event_json in gemini_service.analyze_field_stream(request):
                yield f"data: {event_json}\n\n"
        except Exception as e:
            error = json.dumps({"event": "error", "message": str(e)})
            yield f"data: {error}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",    # nginx proxy desteği için
        },
    )


@app.get("/demo/live-ui", response_class=HTMLResponse, tags=["demo"])
async def demo_live_ui():
    """
    Self-contained HTML demo page for jury presentation.
    No frontend framework needed — open in any browser.
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Agri-Lens — Live Demo</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Segoe UI', system-ui, sans-serif;
      background: #0a0f0a;
      color: #e2f0e2;
      min-height: 100vh;
      padding: 2rem;
    }

    header {
      text-align: center;
      margin-bottom: 2rem;
    }
    header h1 { font-size: 2.4rem; color: #4ade80; letter-spacing: 2px; }
    header p  { color: #86efac; margin-top: .4rem; font-size: 1rem; }

    /* ── Sensor bar ── */
    #sensors {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: .8rem;
      margin-bottom: 2rem;
    }
    .sensor-card {
      background: #111b11;
      border: 1px solid #1f3b1f;
      border-radius: 10px;
      padding: 1rem;
      text-align: center;
    }
    .sensor-card .label { font-size: .72rem; color: #6b8f6b; text-transform: uppercase; }
    .sensor-card .value { font-size: 1.6rem; font-weight: 700; color: #4ade80; margin-top: .3rem; }
    .sensor-card.alert .value { color: #f87171; }

    /* ── Event log ── */
    #log {
      background: #0d150d;
      border: 1px solid #1f3b1f;
      border-radius: 12px;
      padding: 1.2rem;
      height: 380px;
      overflow-y: auto;
      font-family: 'Courier New', monospace;
      font-size: .85rem;
      margin-bottom: 2rem;
    }
    .log-entry { padding: .35rem 0; border-bottom: 1px solid #1a2e1a; line-height: 1.5; }
    .log-entry:last-child { border-bottom: none; }

    .tag {
      display: inline-block;
      padding: .1rem .45rem;
      border-radius: 4px;
      font-size: .7rem;
      font-weight: 700;
      margin-right: .5rem;
      text-transform: uppercase;
    }
    .tag-start      { background:#1e3a5f; color:#93c5fd; }
    .tag-thinking   { background:#2d2d0a; color:#fde68a; }
    .tag-tool_call  { background:#3b1f0a; color:#fb923c; }
    .tag-tool_result{ background:#0a2e1a; color:#4ade80; }
    .tag-diagnosis  { background:#2d1050; color:#c084fc; }
    .tag-error      { background:#450a0a; color:#fca5a5; }

    /* ── Diagnosis card ── */
    #result {
      display: none;
      background: #0d1f1a;
      border: 1px solid #166534;
      border-radius: 14px;
      padding: 1.5rem;
    }
    #result h2 { color: #4ade80; margin-bottom: 1rem; font-size: 1.3rem; }
    .result-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1rem;
    }
    .result-block { background: #111b11; border-radius: 8px; padding: 1rem; }
    .result-block h3 { color: #86efac; font-size: .8rem; text-transform: uppercase; margin-bottom: .5rem; }
    .result-block p  { font-size: .92rem; line-height: 1.6; }
    .severity-badge {
      display: inline-block; padding: .25rem .8rem;
      border-radius: 20px; font-weight: 700; font-size: .85rem;
    }
    .sev-low      { background:#14532d; color:#86efac; }
    .sev-medium   { background:#713f12; color:#fde68a; }
    .sev-high     { background:#7c2d12; color:#fb923c; }
    .sev-critical { background:#450a0a; color:#fca5a5; }

    .rec-list { list-style: none; }
    .rec-list li::before { content: "→ "; color: #4ade80; }
    .rec-list li { padding: .2rem 0; font-size: .9rem; }

    .action-chip {
      display: inline-block;
      background: #1a3a1a; border: 1px solid #166534;
      border-radius: 6px; padding: .3rem .7rem;
      font-size: .78rem; margin: .2rem .2rem 0 0;
      color: #4ade80;
    }

    /* ── Button ── */
    #startBtn {
      display: block; margin: 0 auto 2rem;
      background: #16a34a; color: #fff;
      border: none; border-radius: 10px;
      padding: .85rem 2.5rem; font-size: 1.05rem;
      cursor: pointer; transition: background .2s;
    }
    #startBtn:hover   { background: #15803d; }
    #startBtn:disabled{ background: #374137; color:#6b8f6b; cursor:default; }

    .confidence-bar-wrap { margin-top: .5rem; }
    .confidence-bar-bg {
      background: #1f3b1f; border-radius: 99px; height: 10px; overflow: hidden;
    }
    .confidence-bar-fill {
      background: linear-gradient(90deg,#16a34a,#4ade80);
      height: 100%; border-radius: 99px;
      transition: width 1s ease;
    }
    .confidence-label { font-size:.8rem; color:#86efac; margin-top:.3rem; }
  </style>
</head>
<body>

<header>
  <h1>🌱 Agri-Lens</h1>
  <p>AI Agronomist — Real-time Field Analysis Demo</p>
</header>

<!-- Sensor snapshot -->
<div id="sensors">
  <div class="sensor-card alert" id="sc-moisture">
    <div class="label">Soil Moisture</div>
    <div class="value">18.5%</div>
  </div>
  <div class="sensor-card" id="sc-temp">
    <div class="label">Temperature</div>
    <div class="value">34.2°C</div>
  </div>
  <div class="sensor-card" id="sc-humidity">
    <div class="label">Air Humidity</div>
    <div class="value">47.0%</div>
  </div>
  <div class="sensor-card" id="sc-ph">
    <div class="label">pH</div>
    <div class="value">6.8</div>
  </div>
  <div class="sensor-card alert" id="sc-nitrogen">
    <div class="label">Nitrogen</div>
    <div class="value">17.5 mg/kg</div>
  </div>
  <div class="sensor-card" id="sc-hist">
    <div class="label">History</div>
    <div class="value">7 days</div>
  </div>
</div>

<button id="startBtn" onclick="startDemo()">▶ Run Live Analysis</button>

<!-- Event log -->
<div id="log"><span style="color:#3d5c3d">// Events will appear here...</span></div>

<!-- Diagnosis result -->
<div id="result">
  <h2>🔬 Diagnosis Result</h2>
  <div class="result-grid">
    <div class="result-block">
      <h3>Diagnosis</h3>
      <p id="r-diagnosis"></p>
      <br/>
      <span id="r-severity" class="severity-badge"></span>
    </div>
    <div class="result-block">
      <h3>Root Cause</h3>
      <p id="r-rootcause"></p>
    </div>
    <div class="result-block">
      <h3>Recommendations</h3>
      <ul class="rec-list" id="r-recs"></ul>
    </div>
    <div class="result-block">
      <h3>IoT Actions Triggered</h3>
      <div id="r-actions"></div>
      <br/>
      <h3>Confidence Score</h3>
      <div class="confidence-bar-wrap">
        <div class="confidence-bar-bg">
          <div class="confidence-bar-fill" id="r-conf-bar" style="width:0%"></div>
        </div>
        <div class="confidence-label" id="r-conf-label">—</div>
      </div>
    </div>
  </div>
  <div class="result-block" style="margin-top:1rem">
    <h3>Report for Farmer</h3>
    <p id="r-report"></p>
  </div>
</div>

<script>
function startDemo() {
  const btn = document.getElementById('startBtn');
  const log = document.getElementById('log');
  const result = document.getElementById('result');

  btn.disabled = true;
  btn.textContent = '⏳ Analysing...';
  log.innerHTML = '';
  result.style.display = 'none';

  const es = new EventSource('/demo/live');

  es.onmessage = (e) => {
    const data = JSON.parse(e.data);
    appendLog(data);

    if (data.event === 'diagnosis') {
      renderDiagnosis(data);
      es.close();
      btn.disabled = false;
      btn.textContent = '▶ Run Again';
    }
    if (data.event === 'error') {
      es.close();
      btn.disabled = false;
      btn.textContent = '▶ Retry';
    }
  };

  es.onerror = () => {
    appendLog({ event: 'error', message: 'Connection lost.' });
    es.close();
    btn.disabled = false;
    btn.textContent = '▶ Retry';
  };
}

function appendLog(data) {
  const log = document.getElementById('log');
  const div = document.createElement('div');
  div.className = 'log-entry';

  const tag = document.createElement('span');
  tag.className = `tag tag-${data.event}`;
  tag.textContent = data.event;

  let text = '';
  if (data.message)       text = data.message;
  else if (data.question) text = `Field: ${data.field_id} — "${data.question}"`;
  else                    text = JSON.stringify(data).slice(0, 120) + '…';

  div.appendChild(tag);
  div.appendChild(document.createTextNode(text));
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function renderDiagnosis(d) {
  const result = document.getElementById('result');

  document.getElementById('r-diagnosis').textContent  = d.diagnosis;
  document.getElementById('r-rootcause').textContent  = d.root_cause;
  document.getElementById('r-report').textContent     = d.report_for_farmer;

  const sevEl = document.getElementById('r-severity');
  sevEl.textContent = d.severity.toUpperCase();
  sevEl.className = `severity-badge sev-${d.severity}`;

  const recList = document.getElementById('r-recs');
  recList.innerHTML = '';
  (d.recommendations || []).forEach(r => {
    const li = document.createElement('li');
    li.textContent = r;
    recList.appendChild(li);
  });

  const actDiv = document.getElementById('r-actions');
  actDiv.innerHTML = '';
  (d.actions_taken || []).forEach(a => {
    const chip = document.createElement('span');
    chip.className = 'action-chip';
    chip.textContent = a.action_name + '()';
    actDiv.appendChild(chip);
  });

  const pct = Math.round((d.confidence_score || 0) * 100);
  document.getElementById('r-conf-bar').style.width   = pct + '%';
  document.getElementById('r-conf-label').textContent = pct + '% confidence';

  result.style.display = 'block';
  result.scrollIntoView({ behavior: 'smooth' });
}
</script>
</body>
</html>"""
    return HTMLResponse(content=html)
