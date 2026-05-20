"""
Agri-Lens — Pre-built demo scenarios.

Each builder function returns a fully constructed request object
ready to be passed to GeminiService.
"""

from datetime import datetime, timedelta

from app.models import (
    AnalysisRequest, PlantDiseaseRequest,
    IoTSensorData, HistoricalLog,
)

# ---------------------------------------------------------------------------
#  Live stream demo
# ---------------------------------------------------------------------------


def build_live_stream_request() -> AnalysisRequest:
    """
    Scenario: drought stress + pest detection.
    Used by GET /demo/live (SSE streaming endpoint).
    """
    sensor_data = IoTSensorData(
        field_id="FIELD-001",
        soil_moisture=18.5,
        temperature=34.2,
        humidity=47.0,
        ph_level=6.8,
        nitrogen=17.5,
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

    return AnalysisRequest(
        field_id="FIELD-001",
        question=(
            "The leaves are turning yellow and I can see small insects "
            "on the undersides. What is happening and what should I do?"
        ),
        sensor_data=sensor_data,
        historical_logs=historical_logs,
    )


# ---------------------------------------------------------------------------
#  Plant disease demos
# ---------------------------------------------------------------------------

# Sensor overrides for each plant-disease scenario
_PLANT_DISEASE_SCENARIOS: dict[str, dict] = {
    "late-blight": {
        "description": "Tomato Late Blight + Drought Stress",
        "image": "assets/demo_images/late_blight.jpg",
        "question": "What is wrong with these leaves and what should I do?",
        "sensor": dict(
            field_id="FIELD-001", soil_moisture=20.0, temperature=35.0,
            humidity=48.0, ph_level=6.8, nitrogen=24.0, phosphorus=19.0,
            potassium=23.0, light_intensity=78000.0,
        ),
    },
    "nutrient-deficiency": {
        "description": "Early Blight + Nitrogen Deficiency",
        "image": "assets/demo_images/early_blight.jpg",
        "question": "Why are the leaves turning yellow — is it a disease or something else?",
        "sensor": dict(
            field_id="FIELD-002", soil_moisture=42.0, temperature=27.0,
            humidity=60.0, ph_level=6.5, nitrogen=14.0, phosphorus=18.0,
            potassium=22.0, light_intensity=52000.0,
        ),
    },
    "healthy": {
        "description": "Healthy Plant + Normal Sensors",
        "image": "assets/demo_images/healthy.jpg",
        "question": "My plants look healthy — is everything okay?",
        "sensor": dict(
            field_id="FIELD-003", soil_moisture=55.0, temperature=24.0,
            humidity=65.0, ph_level=6.7, nitrogen=32.0, phosphorus=22.0,
            potassium=28.0, light_intensity=48000.0,
        ),
    },
}

PLANT_DISEASE_SCENARIO_KEYS = list(_PLANT_DISEASE_SCENARIOS.keys())


def build_plant_disease_request(scenario: str) -> PlantDiseaseRequest:
    """
    Returns a PlantDiseaseRequest for the given named scenario.
    Raises KeyError if the scenario name is unknown.
    """
    import os

    s = _PLANT_DISEASE_SCENARIOS[scenario]  # raises KeyError for invalid names
    sensor_data = IoTSensorData(
        **s["sensor"],
        timestamp=datetime.now().isoformat(),
    )

    image_path = s["image"] if os.path.exists(s["image"]) else None

    return PlantDiseaseRequest(
        field_id=sensor_data.field_id,
        question=s["question"],
        image_path=image_path,
        sensor_data=sensor_data,
        sensor_log_path="data/sensor_logs.json",
    )
