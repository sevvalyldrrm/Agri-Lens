"""
IoT Handler — manages field devices.
In production this connects to physical devices via MQTT/HTTP.
This version runs in simulation mode.
"""

import logging
from datetime import datetime
from app.models import IoTAction

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Simulated IoT device states
# ---------------------------------------------------------------------------
_device_state: dict = {
    "irrigation":      {"active": False, "zone": None, "duration_min": 0},
    "fertilizer_pump": {"active": False, "nutrient": None, "amount_ml": 0},
    "ventilation_fan": {"active": False, "speed_percent": 0},
    "alert_system":    {"triggered": False, "message": ""},
    "report_sent":     False,
}


# ---------------------------------------------------------------------------
#  IoT action functions
# ---------------------------------------------------------------------------

def activate_irrigation(zone: str, duration_minutes: int, reason: str) -> dict:
    """
    Starts the irrigation system.
    :param zone: Irrigation zone (e.g. "A1", "B2", "full field")
    :param duration_minutes: Irrigation duration in minutes
    :param reason: Reason for triggering irrigation
    """
    _device_state["irrigation"] = {
        "active": True,
        "zone": zone,
        "duration_min": duration_minutes,
        "started_at": datetime.now().isoformat(),
    }
    msg = (
        f"✅ Irrigation activated — "
        f"Zone: {zone}, Duration: {duration_minutes} min, Reason: {reason}"
    )
    logger.info(msg)
    return {"status": "success", "message": msg, "device_state": _device_state["irrigation"]}


def stop_irrigation(zone: str) -> dict:
    """Stops the active irrigation system."""
    _device_state["irrigation"]["active"] = False
    msg = f"⏹️ Irrigation stopped — Zone: {zone}"
    logger.info(msg)
    return {"status": "success", "message": msg}


def apply_fertilizer(nutrient_type: str, amount_ml: int, reason: str) -> dict:
    """
    Activates the fertilizer pump.
    :param nutrient_type: Nutrient type ('nitrogen', 'phosphorus', 'potassium', 'mixed')
    :param amount_ml: Application amount in ml
    :param reason: Reason for fertilization
    """
    _device_state["fertilizer_pump"] = {
        "active": True,
        "nutrient": nutrient_type,
        "amount_ml": amount_ml,
        "started_at": datetime.now().isoformat(),
    }
    nutrient_labels = {
        "nitrogen":   "Nitrogen (N)",
        "phosphorus": "Phosphorus (P)",
        "potassium":  "Potassium (K)",
        "mixed":      "Mixed fertilizer",
    }
    label = nutrient_labels.get(nutrient_type, nutrient_type)
    msg = (
        f"✅ Fertilizer pump activated — "
        f"Nutrient: {label}, Amount: {amount_ml} ml, Reason: {reason}"
    )
    logger.info(msg)
    return {"status": "success", "message": msg, "device_state": _device_state["fertilizer_pump"]}


def activate_ventilation(speed_percent: int, reason: str) -> dict:
    """
    Starts the ventilation fan.
    :param speed_percent: Fan speed (0-100%)
    :param reason: Reason for ventilation
    """
    _device_state["ventilation_fan"] = {
        "active": True,
        "speed_percent": speed_percent,
        "started_at": datetime.now().isoformat(),
    }
    msg = f"✅ Ventilation fan activated — Speed: {speed_percent}%, Reason: {reason}"
    logger.info(msg)
    return {"status": "success", "message": msg}


def send_agronomist_report(
    field_id: str,
    diagnosis: str,
    severity: str,
    farmer_contact: str = "farmer",
) -> dict:
    """
    Sends a diagnosis report to the agronomist and farmer.
    :param field_id: Field ID
    :param diagnosis: Diagnosis summary
    :param severity: Severity level
    :param farmer_contact: Farmer name or contact info
    """
    _device_state["report_sent"] = True
    msg = (
        f"📧 Report sent — "
        f"Field: {field_id}, Diagnosis: {diagnosis}, "
        f"Severity: {severity}, Recipient: {farmer_contact}"
    )
    logger.info(msg)
    return {
        "status": "success",
        "message": msg,
        "sent_at": datetime.now().isoformat(),
    }


def trigger_pest_alert(field_id: str, pest_type: str, affected_area_percent: float) -> dict:
    """
    Triggers the pest / disease alert system.
    :param field_id: Field ID
    :param pest_type: Pest or disease type
    :param affected_area_percent: Percentage of affected area
    """
    message = (
        f"⚠️ PEST ALERT — Field {field_id}: "
        f"{pest_type} detected, affected area: {affected_area_percent:.1f}%"
    )
    _device_state["alert_system"] = {"triggered": True, "message": message}
    logger.warning(message)
    return {"status": "success", "message": message, "alert_level": "HIGH"}


# ---------------------------------------------------------------------------
#  Function dispatcher — executes function_calls returned by Gemini
# ---------------------------------------------------------------------------

AVAILABLE_FUNCTIONS: dict = {
    "activate_irrigation":   activate_irrigation,
    "stop_irrigation":       stop_irrigation,
    "apply_fertilizer":      apply_fertilizer,
    "activate_ventilation":  activate_ventilation,
    "send_agronomist_report": send_agronomist_report,
    "trigger_pest_alert":    trigger_pest_alert,
}


def execute_iot_action(function_name: str, function_args: dict) -> tuple[dict, IoTAction]:
    """
    Executes the IoT function requested by Gemini.
    Returns the raw result and an IoTAction log entry.
    """
    func = AVAILABLE_FUNCTIONS.get(function_name)
    if not func:
        error_msg = f"Unknown IoT function: {function_name}"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}, IoTAction(
            action_name=function_name,
            parameters=function_args,
            reason="ERROR: Function not found",
        )

    result = func(**function_args)

    action_log = IoTAction(
        action_name=function_name,
        parameters=function_args,
        reason=function_args.get("reason", "Triggered by Gemini"),
    )
    return result, action_log


def get_device_state() -> dict:
    """Returns the current device state (for debug / monitoring)."""
    return _device_state.copy()
