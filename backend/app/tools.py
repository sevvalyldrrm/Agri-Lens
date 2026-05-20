"""
Agri-Lens — Gemini Function Calling tool declarations.

All IoT tool schemas are defined here so they can be updated
independently from the service or handler logic.
"""

from google.generativeai.types import FunctionDeclaration, Tool

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
