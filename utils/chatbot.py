"""
chatbot.py
-----------
"Conversational Twin" — a lightweight, rule-based (intent-matching)
chatbot that lets users ask natural-language questions about their own
Digital Twin and get answers grounded in their actual latest health
record, XAI factors, and habit-impact rankings.

This intentionally avoids a heavy NLP/LLM dependency (no internet call,
no extra install) so it works fully offline and is easy to explain in a
viva: keyword/intent matching + templated responses using real user data,
not free-form generation.
"""

import re
from utils.xai import explain_all
from utils.habit_impact import rank_habit_impacts
from utils.recommendations import generate_recommendations

INTENT_PATTERNS = {
    "greeting": r"\b(hi|hello|hey|good morning|good evening)\b",
    "health_score": r"\b(health score|overall score|my score)\b",
    "risk_why": r"\b(why).*(risk|diabetes|hypertension|heart|high)\b",
    "diabetes_risk": r"\bdiabet",
    "hypertension_risk": r"\b(hypertension|blood pressure|bp)\b",
    "heart_risk": r"\b(heart|cardiac|cardiovascular)\b",
    "improve": r"\b(improve|better|reduce risk|lower risk|what should i do|help me)\b",
    "sleep": r"\bsleep\b",
    "diet": r"\b(diet|food|eat|nutrition)\b",
    "top_change": r"\b(top|best|single|most effective|biggest) (change|habit|thing)\b",
    "thanks": r"\b(thanks|thank you|thx)\b",
}


def _match_intent(message: str):
    msg = message.lower()
    for intent, pattern in INTENT_PATTERNS.items():
        if re.search(pattern, msg):
            return intent
    return "fallback"


def _risk_label(pct):
    if pct >= 60:
        return "high"
    if pct >= 30:
        return "moderate"
    return "low"


def get_response(message: str, user: dict, record: dict) -> str:
    if not record:
        return ("You haven't logged any health data yet. Go to 'Log Update' first, "
                "and I'll be able to answer questions about your Digital Twin.")

    intent = _match_intent(message)
    first_name = user["name"].split(" ")[0]

    data = {
        "age": user["age"], "gender": user["gender"], "bmi": record["bmi"],
        "systolic_bp": record["systolic_bp"], "diastolic_bp": record["diastolic_bp"],
        "glucose": record["glucose"], "sleep_hours": record["sleep_hours"],
        "activity_min_per_week": record["activity_min_per_week"], "smoking": record["smoking"],
        "alcohol": record["alcohol"], "family_history": record["family_history"],
        "water_intake_l": record["water_intake_l"], "diet_quality": record["diet_quality"],
        "stress_level": record["stress_level"],
    }

    if intent == "greeting":
        return f"Hi {first_name}! I'm your Digital Twin assistant. Ask me about your health score, risk factors, or what would help most."

    if intent == "thanks":
        return "You're welcome! Stay consistent with your habits and check back after your next update."

    if intent == "health_score":
        return (f"Your current Health Score is {record['health_score']}/100. "
                f"Sub-scores: Metabolic {record['metabolic_score']}, Cardiovascular {record['cardio_score']}, "
                f"Sleep {record['sleep_score']}, Activity {record['activity_score']}.")

    if intent in ("diabetes_risk", "hypertension_risk", "heart_risk", "risk_why"):
        disease_map = {"diabetes_risk": "diabetes", "hypertension_risk": "hypertension", "heart_risk": "heart"}
        disease_key = disease_map.get(intent)

        if not disease_key:
            # risk_why matched generically ("why is my risk high") -- check if a
            # specific disease was also named in the message before falling back
            # to whichever risk is currently highest for this user.
            msg_lower = message.lower()
            if re.search(r"\bdiabet", msg_lower):
                disease_key = "diabetes"
            elif re.search(r"\b(hypertension|blood pressure|\bbp\b)", msg_lower):
                disease_key = "hypertension"
            elif re.search(r"\b(heart|cardiac|cardiovascular)\b", msg_lower):
                disease_key = "heart"
            else:
                risks = {"diabetes": record["diabetes_risk"], "hypertension": record["hypertension_risk"],
                         "heart": record["heart_risk"]}
                disease_key = max(risks, key=risks.get)

        risk_col = {"diabetes": "diabetes_risk", "hypertension": "hypertension_risk", "heart": "heart_risk"}[disease_key]
        pct = record[risk_col]
        factors = explain_all(data, top_n=3)[disease_key]
        factor_names = ", ".join(f["friendly_name"] for f in factors if f["feature"] != "none")
        label = _risk_label(pct)

        response = f"Your predicted {disease_key} risk is {pct}% ({label})."
        if factor_names:
            response += f" The main contributing factors are: {factor_names}."
        return response

    if intent == "top_change" or intent == "improve":
        top = rank_habit_impacts(data, top_n=3)
        if not top:
            return "Your profile currently looks well-balanced — keep up your habits!"
        lines = [f"{i+1}. {h['change']} (−{h['risk_reduction_pct']} pts avg. risk, +{h['health_score_gain']} score)"
                 for i, h in enumerate(top)]
        return "Here are the highest-impact changes for you right now:\n" + "\n".join(lines)

    if intent == "sleep":
        return (f"You're averaging {record['sleep_hours']} hours of sleep, giving a Sleep sub-score of "
                f"{record['sleep_score']}/100. The ideal range is 7–8.5 hours per night.")

    if intent == "diet":
        risks = {"diabetes_risk": record["diabetes_risk"], "hypertension_risk": record["hypertension_risk"],
                 "heart_risk": record["heart_risk"]}
        tips = generate_recommendations(data, risks)
        diet_tips = [t for t in tips if any(w in t.lower() for w in ["diet", "sugar", "sodium", "water", "food"])]
        if diet_tips:
            return " ".join(diet_tips)
        return "Your diet-related metrics currently look reasonable — keep favoring whole foods and consistent hydration."

    # fallback
    return (f"I can answer questions about your health score, diabetes/hypertension/heart risk, "
            f"sleep, diet, or the single most effective change you can make — try asking "
            f"something like \"why is my heart risk high?\" or \"what's my biggest opportunity?\"")
