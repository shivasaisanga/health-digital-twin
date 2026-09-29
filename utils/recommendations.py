"""
recommendations.py
--------------------
Generates personalized, rule-based recommendations from the user's
current metrics. Kept simple and transparent (no black box) so it is
easy to justify in the project report.
"""


def generate_recommendations(data: dict, risks: dict) -> list:
    tips = []

    if data["bmi"] >= 25:
        tips.append("Your BMI is above the healthy range — a gradual weight loss "
                     "of 5-10% of body weight can meaningfully lower diabetes and heart risk.")
    elif data["bmi"] < 18.5:
        tips.append("Your BMI is below the healthy range — consider a nutrient-dense "
                     "diet plan to reach a healthier weight.")

    if data["systolic_bp"] >= 130 or data["diastolic_bp"] >= 85:
        tips.append("Your blood pressure is elevated — reduce sodium intake, "
                     "manage stress, and monitor BP regularly.")

    if data["glucose"] >= 100:
        tips.append("Your blood glucose is above the normal fasting range — "
                     "reduce refined sugar/carbs and consider a fasting glucose retest.")

    if data["sleep_hours"] < 7:
        tips.append("You are getting less sleep than recommended — aim for 7-8.5 hours "
                     "nightly to support metabolic and cardiovascular health.")
    elif data["sleep_hours"] > 9:
        tips.append("You are sleeping more than typical — excessive sleep can sometimes "
                     "signal other health issues worth discussing with a doctor.")

    if data["activity_min_per_week"] < 150:
        tips.append("You are below the WHO-recommended 150 minutes of weekly activity — "
                     "try adding 20-30 minutes of brisk walking most days.")

    if data["smoking"]:
        tips.append("Smoking significantly increases cardiovascular and cancer risk — "
                     "consider a structured quit-smoking program.")

    if data["alcohol"]:
        tips.append("Reducing alcohol intake can improve liver function, sleep quality, "
                     "and blood pressure.")

    if data["water_intake_l"] < 2.0:
        tips.append("Your water intake is on the lower side — aim for about 2-3 liters "
                     "per day depending on activity level.")

    if data["diet_quality"] <= 5:
        tips.append("Your self-rated diet quality is low — increase whole foods, "
                     "vegetables, and fiber while reducing processed foods.")

    if data["stress_level"] >= 7:
        tips.append("Your stress level is high — mindfulness, regular exercise, and "
                     "adequate sleep can help lower chronic stress markers.")

    if data["family_history"] and (risks["diabetes_risk"] > 40 or risks["heart_risk"] > 40):
        tips.append("Given your family history and current risk profile, "
                     "regular clinical checkups are strongly advised.")

    if not tips:
        tips.append("Your health profile currently looks well-balanced — keep up the "
                     "consistent habits and continue periodic monitoring.")

    return tips
