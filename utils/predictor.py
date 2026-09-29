"""
predictor.py
-------------
Loads the trained models once at import time and exposes a single
`predict_risks(data)` function used across the app (dashboard, what-if
simulation, habit-impact ranking engine, PDF report).
"""

import os
import joblib
import numpy as np

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")

_diabetes_model = joblib.load(os.path.join(MODEL_DIR, "diabetes_model.joblib"))
_hypertension_model = joblib.load(os.path.join(MODEL_DIR, "hypertension_model.joblib"))
_heart_model = joblib.load(os.path.join(MODEL_DIR, "heart_model.joblib"))
_scaler = joblib.load(os.path.join(MODEL_DIR, "scaler.joblib"))
FEATURES = joblib.load(os.path.join(MODEL_DIR, "feature_names.joblib"))


def _to_feature_vector(data: dict) -> np.ndarray:
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
    import pandas as pd
    return pd.DataFrame([[row[f] for f in FEATURES]], columns=FEATURES)


def predict_risks(data: dict) -> dict:
    """Returns risk probabilities (0-1) for each disease."""
    X = _to_feature_vector(data)
    X_scaled = _scaler.transform(X)

    diabetes_p = float(_diabetes_model.predict_proba(X_scaled)[0][1])
    hyper_p = float(_hypertension_model.predict_proba(X_scaled)[0][1])
    heart_p = float(_heart_model.predict_proba(X_scaled)[0][1])

    return {
        "diabetes_risk": round(diabetes_p * 100, 1),
        "hypertension_risk": round(hyper_p * 100, 1),
        "heart_risk": round(heart_p * 100, 1),
    }


def get_models():
    return {
        "diabetes": _diabetes_model,
        "hypertension": _hypertension_model,
        "heart": _heart_model,
    }


def get_scaler():
    return _scaler
