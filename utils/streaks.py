"""
streaks.py
-----------
Calculates a "weekly check-in streak" — the number of consecutive weeks
in which the user logged at least one health update, counting backwards
from their most recent entry. Used purely for gamification/engagement on
the dashboard.
"""

from datetime import datetime


def _parse_dt(s):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(s, fmt)
        except (ValueError, TypeError):
            continue
    return None


def calculate_streak(history: list) -> int:
    """
    history: list of dicts with 'recorded_at', ordered ascending (oldest first).
    Returns the number of consecutive weeks (most recent backwards) with
    at least one log entry.
    """
    if not history:
        return 0

    dates = sorted(set(_parse_dt(r["recorded_at"]).date() for r in history if _parse_dt(r["recorded_at"])))
    if not dates:
        return 0

    # Group into ISO week numbers (year, week)
    weeks = sorted(set(d.isocalendar()[:2] for d in dates), reverse=True)

    streak = 1
    for i in range(1, len(weeks)):
        prev_year, prev_week = weeks[i - 1]
        year, week = weeks[i]
        # consecutive if exactly one ISO week apart
        if prev_week - week == 1 and prev_year == year:
            streak += 1
        elif prev_week == 1 and week >= 52 and prev_year - year == 1:
            streak += 1  # year boundary wrap
        else:
            break

    return streak
