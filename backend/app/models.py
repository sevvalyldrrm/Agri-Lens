from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class PriorityMode(str, Enum):
    """Priority decision made by Gemini during cross-query analysis."""
    DISEASE    = "disease"       # Visual findings are dominant
    IRRIGATION = "irrigation"    # Sensor data (drought) is dominant
    NUTRIENT   = "nutrient"      # Nutrient deficiency is dominant
    COMBINED   = "combined"      # Both factors require simultaneous action


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
    # audio delivered as base64
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


class PlantDiseaseRequest(BaseModel):
    """
    Leaf image + IoT sensor cross-query request (PlantVillage-style).
    Either image_base64 OR image_path must be provided.
    """
    field_id: str = Field(..., description="Field identifier")
    question: str = Field(
        default="What is wrong with these leaves and what should I do?",
        description="Farmer's question in natural language",
    )
    image_base64: Optional[str] = Field(None, description="Base64-encoded leaf image")
    image_path: Optional[str]   = Field(None, description="Server-side image file path")
    image_mime: str             = Field(default="image/jpeg", description="Image MIME type")
    sensor_data: IoTSensorData  = Field(..., description="Real-time sensor readings")
    historical_logs: list[HistoricalLog] = Field(
        default=[], description="Historical sensor records"
    )
    sensor_log_path: Optional[str] = Field(
        None, description="Path to data/sensor_logs.json — used for Long Context"
    )


class PlantDiseaseResult(BaseModel):
    """Result of the visual + sensor cross-query analysis."""
    field_id: str
    visual_finding: str       = Field(..., description="Finding detected from the image")
    sensor_finding: str       = Field(..., description="Main issue detected from sensor data")
    priority_mode: PriorityMode
    priority_reason: str      = Field(..., description="Explanation of why this priority was chosen")
    diagnosis: str
    severity: SeverityLevel
    root_cause: str
    recommendations: list[str]
    actions_taken: list[IoTAction] = []
    report_for_farmer: str
    confidence_score: float   = Field(..., ge=0, le=1)
    seasonal_pattern: Optional[str] = Field(
        None, description="Seasonal pattern detected from historical logs"
    )
