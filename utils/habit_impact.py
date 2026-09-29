"""
habit_impact.py
-----------------
The Habit-Impact Ranking Engine — the project's signature innovation.

For a given user, it simulates several realistic lifestyle changes ONE AT A
TIME (counterfactual analysis), re-runs the trained ML models on each
modified profile, and ranks the changes by how much they reduce overall
average disease risk. This tells the user exactly which single habit change
would help them the most, instead of a generic tip list.

It reuses the already-trained models via predictor.predict_risks — no
retraining needed, so it's cheap enough to run on every dashboard request.
"""

import copy
from utils.predictor import predict_risks
from utils.health_score import compute_scores

# Each candidate change: (label, function that mutates a copy of the data dict)
CANDIDATE_CHANGES = [
    ("Lose 5 kg (reduce BMI)", lambda d: _adjust_bmi(d, -2.0)),
    ("Lose 10 kg (reduce BMI)", lambda d: _adjust_bmi(d, -4.0)),
    ("Increase sleep to 8 hours/night", lambda d: _set(d, "sleep_hours", 8.0)),
    ("Add 60 min/week of exercise", lambda d: _add(d, "activity_min_per_week", 60)),
    ("Add 150 min/week of exercise", lambda d: _add(d, "activity_min_per_week", 150)),
    ("Quit smoking", lambda d: _set(d, "smoking", 0)),
    ("Reduce alcohol consumption", lambda d: _set(d, "alcohol", 0)),
    ("Improve diet quality by 3 points", lambda d: _clamp_add(d, "diet_quality", 3, 1, 10)),
    ("Reduce stress level by 3 points", lambda d: _clamp_add(d, "stress_level", -3, 1, 10)),
    ("Increase water intake to 2.5L/day", lambda d: _set(d, "water_intake_l", 2.5)),
    ("Lower blood glucose by 15 mg/dL", lambda d: _add(d, "glucose", -15)),
    ("Lower systolic BP by 10 mmHg", lambda d: _add(d, "systolic_bp", -10)),
]


def _set(d, key, value):
    d[key] = value
    return d


def _add(d, key, delta):
    d[key] = max(0, d[key] + delta)
    return d


def _clamp_add(d, key, delta, low, high):
    d[key] = max(low, min(high, d[key] + delta))
    return d


def _adjust_bmi(d, delta):
    # approximate: also nudges glucose/BP slightly since weight loss affects both
    d["bmi"] = max(15, d["bmi"] + delta)
    d["glucose"] = max(60, d["glucose"] + delta * 2.5)
    d["systolic_bp"] = max(90, d["systolic_bp"] + delta * 1.5)
    return d


def _avg_risk(risks: dict) -> float:
    return (risks["diabetes_risk"] + risks["hypertension_risk"] + risks["heart_risk"]) / 3


def rank_habit_impacts(user_data: dict, top_n=5):
    """
    user_data: raw profile dict (age, gender, bmi, systolic_bp, diastolic_bp,
               glucose, sleep_hours, activity_min_per_week, smoking, alcohol,
               family_history, water_intake_l, diet_quality, stress_level)
    Returns a ranked list of changes with risk reduction and new health score.
    """
    baseline_risks = predict_risks(user_data)
    baseline_avg = _avg_risk(baseline_risks)
    baseline_score = compute_scores(user_data)["health_score"]

    results = []
    for label, mutate_fn in CANDIDATE_CHANGES:
        candidate = copy.deepcopy(user_data)
        candidate = mutate_fn(candidate)

        new_risks = predict_risks(candidate)
        new_avg = _avg_risk(new_risks)
        new_score = compute_scores(candidate)["health_score"]

        results.append({
            "change": label,
            "risk_reduction_pct": round(baseline_avg - new_avg, 2),
            "new_avg_risk": round(new_avg, 1),
            "baseline_avg_risk": round(baseline_avg, 1),
            "health_score_gain": round(new_score - baseline_score, 1),
            "new_health_score": new_score,
        })

    results.sort(key=lambda x: x["risk_reduction_pct"], reverse=True)
    return results[:top_n]
