"""
health_score.py
-----------------
Computes the overall Health Score (0-100) and the four sub-scores
(Metabolic, Cardiovascular, Sleep, Activity) that power the radar chart.

These are transparent, rule-based formulas (not black-box ML) so they are
easy to explain in a viva/report, and they update instantly for the
What-If Simulation without needing to retrain anything.
"""


def _clip(value, low=0, high=100):
    return max(low, min(high, value))


def metabolic_score(bmi, glucose):
    # Ideal BMI ~22, ideal fasting glucose ~90
    bmi_penalty = abs(bmi - 22) * 2.5
    glucose_penalty = max(0, glucose - 90) * 0.6
    score = 100 - bmi_penalty - glucose_penalty
    return round(_clip(score), 1)


def cardio_score(systolic_bp, diastolic_bp):
    # Ideal BP ~ 115/75
    sys_penalty = max(0, systolic_bp - 115) * 0.6
    dia_penalty = max(0, diastolic_bp - 75) * 0.7
    score = 100 - sys_penalty - dia_penalty
    return round(_clip(score), 1)


def sleep_score(sleep_hours):
    # Ideal sleep 7-8.5 hours
    if 7 <= sleep_hours <= 8.5:
        score = 100
    else:
        deviation = min(abs(sleep_hours - 7), abs(sleep_hours - 8.5))
        score = 100 - deviation * 12
    return round(_clip(score), 1)


def activity_score(activity_min_per_week):
    # WHO recommendation: 150 min/week moderate activity = full score
    score = (activity_min_per_week / 150) * 100
    return round(_clip(score), 1)


def stress_penalty(stress_level):
    # stress_level 1-10 -> penalty applied to overall score
    return (stress_level - 5) * 1.5


def lifestyle_penalty(smoking, alcohol, diet_quality, water_intake_l):
    penalty = 0
    penalty += 8 if smoking else 0
    penalty += 4 if alcohol else 0
    penalty += (10 - diet_quality) * 1.2
    penalty += max(0, (2.0 - water_intake_l)) * 3
    return penalty


def compute_scores(data: dict) -> dict:
    """
    data must contain: bmi, systolic_bp, diastolic_bp, glucose, sleep_hours,
    activity_min_per_week, smoking, alcohol, diet_quality, water_intake_l,
    stress_level
    """
    m = metabolic_score(data["bmi"], data["glucose"])
    c = cardio_score(data["systolic_bp"], data["diastolic_bp"])
    s = sleep_score(data["sleep_hours"])
    a = activity_score(data["activity_min_per_week"])

    base = (m * 0.30) + (c * 0.30) + (s * 0.20) + (a * 0.20)
    penalty = stress_penalty(data["stress_level"]) + lifestyle_penalty(
        data["smoking"], data["alcohol"], data["diet_quality"], data["water_intake_l"]
    )
    overall = _clip(base - penalty)

    return {
        "health_score": round(overall, 1),
        "metabolic_score": m,
        "cardio_score": c,
        "sleep_score": s,
        "activity_score": a,
    }
