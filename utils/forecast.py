"""
forecast.py
------------
Risk Trend Forecasting — fits a simple linear regression (least-squares,
via numpy.polyfit) on the user's historical health score / disease risk
values and projects where they're headed in 30/60/90 days if the current
trend continues.

This is intentionally a lightweight statistical technique (not another
classifier) so it's easy to explain: "we're not predicting a new outcome,
we're extrapolating the existing trend line."
"""

import numpy as np
from datetime import datetime, timedelta


def _parse_dt(s):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(s, fmt)
        except (ValueError, TypeError):
            continue
    return None


def forecast_metric(history: list, field: str, horizons_days=(30, 60, 90)):
    """
    history: list of dicts with 'recorded_at' and the given field, ordered ascending.
    Returns None if fewer than 3 data points (not enough to trust a trend).
    """
    points = []
    for rec in history:
        dt = _parse_dt(rec.get("recorded_at"))
        if dt is not None and rec.get(field) is not None:
            points.append((dt, float(rec[field])))

    if len(points) < 3:
        return None

    t0 = points[0][0]
    xs = np.array([(dt - t0).days for dt, _ in points], dtype=float)
    ys = np.array([val for _, val in points], dtype=float)

    # If all entries were logged on the same day (common during a live demo/testing),
    # day-based x-values would all be 0 with no variance to fit a trend line against.
    # Fall back to using the entry sequence (1st, 2nd, 3rd...) as the x-axis instead,
    # and treat each step as one "day" for the purposes of the projection.
    using_sequence_fallback = xs.max() == xs.min()
    if using_sequence_fallback:
        xs = np.arange(len(points), dtype=float)
        if xs.max() == xs.min():
            return None

    slope, intercept = np.polyfit(xs, ys, 1)

    last_x = xs[-1]
    projections = {}
    for h in horizons_days:
        projected_x = last_x + h
        projected_y = slope * projected_x + intercept
        projections[h] = round(float(np.clip(projected_y, 0, 100)), 1)

    return {
        "slope_per_day": round(float(slope), 4),
        "trend": "improving" if slope > 0.01 else ("declining" if slope < -0.01 else "stable"),
        "current_value": round(ys[-1], 1),
        "projections": projections,
        "sequence_fallback": using_sequence_fallback,
    }


def forecast_all(history: list):
    if not history or len(history) < 3:
        return None
    return {
        "health_score": forecast_metric(history, "health_score"),
        "diabetes_risk": forecast_metric(history, "diabetes_risk"),
        "hypertension_risk": forecast_metric(history, "hypertension_risk"),
        "heart_risk": forecast_metric(history, "heart_risk"),
    }
