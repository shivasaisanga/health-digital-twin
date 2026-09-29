"""
xai.py
-------
Explainable AI module. Uses the RandomForest's built-in feature_importances_
combined with how far the user's own values deviate from healthy reference
ranges, to produce a ranked, human-readable list of "why" behind a
prediction. This avoids adding a heavy SHAP dependency while still giving
genuine per-user explanations (importance x deviation), not just a fixed
global ranking.
"""

from utils.predictor import get_models, FEATURES

REFERENCE_RANGES = {
    "bmi": (18.5, 24.9),
    "systolic_bp": (90, 120),
    "diastolic_bp": (60, 80),
    "glucose": (70, 99),
    "sleep_hours": (7, 8.5),
    "activity_min_per_week": (150, 600),
    "water_intake_l": (2.0, 4.0),
    "diet_quality": (7, 10),
    "stress_level": (1, 4),
}

FRIENDLY_NAMES = {
    "age": "Age",
    "gender_male": "Gender",
    "bmi": "BMI",
    "systolic_bp": "Systolic Blood Pressure",
    "diastolic_bp": "Diastolic Blood Pressure",
    "glucose": "Blood Glucose",
    "sleep_hours": "Sleep Duration",
    "activity_min_per_week": "Weekly Physical Activity",
    "smoking": "Smoking",
    "alcohol": "Alcohol Consumption",
    "family_history": "Family Medical History",
    "water_intake_l": "Water Intake",
    "diet_quality": "Diet Quality",
    "stress_level": "Stress Level",
}


def _deviation_score(feature, value):
    """Returns 0 if within healthy range, otherwise a normalized deviation (0-1+)."""
    if feature in REFERENCE_RANGES:
        low, high = REFERENCE_RANGES[feature]
        if low <= value <= high:
            return 0.0
        span = max(high - low, 1e-6)
        if value < low:
            return (low - value) / span
        return (value - high) / span
    if feature in ("smoking", "alcohol", "family_history"):
        return 1.0 if value else 0.0
    return 0.0


def explain(disease: str, data: dict, top_n=4):
    """
    disease: 'diabetes' | 'hypertension' | 'heart'
    data: the raw user input dict (unscaled)
    Returns a ranked list of dicts: {feature, friendly_name, contribution, direction}
    """
    models = get_models()
    model = models[disease]
    importances = model.feature_importances_

    row = {
        "age": data["age"],
        "gender_male": 1 if data.get("gender", "male").lower() == "male" else 0,
        "bmi": data["bmi"],
        "systolic_bp": data["systolic_bp"],
        "diastolic_bp": data["diastolic_bp"],
        "glucose": data["glucose"],
        "sleep_hours": data["sleep_hours"],
        "activity_min_per_week": data["activity_min_per_week"],
        "smoking": data["smoking"],
        "alcohol": data["alcohol"],
        "family_history": data["family_history"],
        "water_intake_l": data["water_intake_l"],
        "diet_quality": data["diet_quality"],
        "stress_level": data["stress_level"],
    }

    scored = []
    for i, feat in enumerate(FEATURES):
        deviation = _deviation_score(feat, row[feat])
        contribution = importances[i] * (0.15 + deviation)  # base weight + deviation boost
        if deviation > 0 or feat in ("family_history", "smoking", "alcohol"):
            scored.append({
                "feature": feat,
                "friendly_name": FRIENDLY_NAMES.get(feat, feat),
                "contribution": round(float(contribution) * 100, 2),
                "value": row[feat],
            })

    scored.sort(key=lambda x: x["contribution"], reverse=True)
    return scored[:top_n] if scored else [{
        "feature": "none", "friendly_name": "All factors within healthy range",
        "contribution": 0, "value": None
    }]


def explain_all(data: dict, top_n=4):
    return {
        "diabetes": explain("diabetes", data, top_n),
        "hypertension": explain("hypertension", data, top_n),
        "heart": explain("heart", data, top_n),
    }
