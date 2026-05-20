from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IoTSensorData(BaseModel):
    """Real-time readings from field sensors."""
    field_id: str = Field(..., description="Field identifier")
    soil_moisture: float = Field(..., ge=0, le=100, description="Soil moisture (%)")
    temperature: float = Field(..., description="Air temperature (°C)")
    humidity: float = Field(..., ge=0, le=100, description="Air humidity (%)")
    ph_level: float = Field(..., ge=0, le=14, description="Soil pH value")
    nitrogen: float = Field(..., ge=0, description="Nitrogen level (mg/kg)")
    phosphorus: float = Field(..., ge=0, description="Phosphorus level (mg/kg)")
    potassium: float = Field(..., ge=0, description="Potassium level (mg/kg)")
    light_intensity: float = Field(..., ge=0, description="Light intensity (lux)")
    timestamp: str = Field(..., description="Measurement timestamp")


class HistoricalLog(BaseModel):
    """Historical sensor log entry."""
    date: str
    soil_moisture: float
    temperature: float
    ph_level: float
    event: Optional[str] = None  # e.g. "disease detected", "irrigation", "fertilization"


class AnalysisRequest(BaseModel):
    """Analysis request from the farmer."""
    field_id: str = Field(..., description="Field ID")
    question: str = Field(..., description="Farmer's question in natural language")
    sensor_data: IoTSensorData = Field(..., description="Real-time sensor readings")
    historical_logs: list[HistoricalLog] = Field(
        default=[], description="Historical sensor records (Long Context)"
    )
    # video and audio delivered as file path or base64
    video_path: Optional[str] = None
    audio_base64: Optional[str] = None


class IoTAction(BaseModel):
    """An IoT action triggered by Gemini via Function Calling."""
    action_name: str
    parameters: dict
    reason: str


class DiagnosisResult(BaseModel):
    """Final diagnosis and action report."""
    field_id: str
    diagnosis: str = Field(..., description="Diagnosis result")
    severity: SeverityLevel
    root_cause: str = Field(..., description="Root cause analysis")
    recommendations: list[str] = Field(..., description="List of recommendations")
    actions_taken: list[IoTAction] = Field(
        default=[], description="IoT actions triggered by Gemini"
    )
    report_for_farmer: str = Field(..., description="Plain-language report for the farmer")
    confidence_score: float = Field(..., ge=0, le=1, description="Confidence score")
