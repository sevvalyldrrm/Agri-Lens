# 🌿 Agri-Lens — Monorepo

> AI-powered agronomist in every farmer's pocket.

```
agri-lens/
├── backend/          # FastAPI + Gemini AI — Python
│   ├── app/
│   │   ├── main.py           ← API entry point
│   │   ├── gemini_service.py ← Gemini multimodal AI
│   │   ├── models.py         ← Pydantic data models
│   │   ├── iot_handler.py    ← IoT device simulation
│   │   ├── demo_scenarios.py ← Pre-built demo data
│   │   ├── prompts.py        ← AI prompt templates
│   │   ├── tools.py          ← Gemini function tools
│   │   ├── config.py         ← App settings
│   │   └── templates/        ← HTML demo pages
│   ├── assets/
│   │   └── demo_images/      ← Demo crop images
│   └── requirements.txt
└── mobile/           # Vanilla JS Mobile UI
    ├── index.html            ← Phone frame shell + nav
    ├── css/
    │   ├── base.css          ← Variables, reset, frame, nav
    │   └── components.css    ← Shared UI primitives
    └── js/
        ├── api.js            ← All backend fetch calls
        ├── router.js         ← Screen navigation manager
        └── screens/
            ├── home.js       ← Field Health Status
            ├── vision.js     ← Camera / Image Analysis
            ├── report.js     ← Diagnosis Details
            ├── actions.js    ← Action Center
            └── analytics.js  ← Growth Analytics
```

## 🚀 Quick Start

### 1 — Backend (port 8000)
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env      # add your GEMINI_API_KEY
uvicorn app.main:app --reload
```

### 2 — Mobile UI (port 3000)
```bash
cd mobile
python -m http.server 3000
# open http://localhost:3000
```

## 🔌 API ↔ Mobile Connection

| Mobile Screen | Backend Endpoint |
|---------------|-----------------|
| Home          | `GET /devices/status` |
| Vision        | `POST /analyze/plant-disease/upload` |
| Report        | `GET /demo/plant-disease/{scenario}` |
| Actions       | `GET /demo/plant-disease/late-blight` |
| Analytics     | `GET /demo/plant-disease/{scenario}` + `GET /devices/status` |

## 📡 All Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET  | `/health` | Health check |
| GET  | `/devices/status` | Live IoT sensor state |
| POST | `/analyze` | Full multimodal analysis |
| POST | `/analyze/quick` | Form-based quick analysis |
| POST | `/analyze/plant-disease/upload` | Image + sensors → AI diagnosis |
| GET  | `/demo/plant-disease/{scenario}` | Pre-built scenarios: `late-blight`, `nutrient-deficiency`, `healthy` |
| GET  | `/demo/live` | SSE real-time stream |
| GET  | `/demo/live-ui` | Browser stream demo UI |
| GET  | `/docs` | Swagger UI |
