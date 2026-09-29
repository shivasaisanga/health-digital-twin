"""
train_model.py
----------------
Generates a realistic synthetic health dataset and trains three
Random Forest classifiers (diabetes, hypertension, heart disease risk)
plus saves a StandardScaler. Also trains a small regression model
for the overall Health Score.

Run this once before starting the Flask app:
    python models/train_model.py

Outputs (saved into models/):
    diabetes_model.joblib
    hypertension_model.joblib
    heart_model.joblib
    scaler.joblib
    feature_names.joblib
    health_data.csv   (the synthetic dataset, for reference / retraining)
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score
import joblib
import os

np.random.seed(42)
N = 6000

MODEL_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------
# 1. Generate synthetic but medically-plausible data
# ---------------------------------------------------------------------
age = np.random.randint(18, 80, N)
gender = np.random.choice(["male", "female"], N)

height_cm = np.random.normal(165, 10, N).clip(140, 200)
weight_kg = np.random.normal(70, 15, N).clip(40, 150)
bmi = weight_kg / ((height_cm / 100) ** 2)

# Blood pressure correlates loosely with age + bmi
systolic_bp = (100 + (age * 0.4) + (bmi * 0.6) + np.random.normal(0, 8, N)).clip(90, 200)
diastolic_bp = (60 + (age * 0.15) + (bmi * 0.3) + np.random.normal(0, 6, N)).clip(55, 130)

# Glucose correlates with age + bmi
glucose = (80 + (age * 0.3) + (bmi * 0.9) + np.random.normal(0, 12, N)).clip(60, 250)

sleep_hours = np.random.normal(6.8, 1.3, N).clip(3, 10)
activity_min_per_week = np.random.exponential(120, N).clip(0, 600)
smoking = np.random.choice([0, 1], N, p=[0.8, 0.2])
alcohol = np.random.choice([0, 1], N, p=[0.7, 0.3])
family_history = np.random.choice([0, 1], N, p=[0.65, 0.35])
water_intake_l = np.random.normal(1.8, 0.6, N).clip(0.3, 4)
diet_quality = np.random.randint(1, 11, N)  # 1 (poor) - 10 (excellent)
stress_level = np.random.randint(1, 11, N)  # 1 (low) - 10 (high)

df = pd.DataFrame({
    "age": age,
    "gender": gender,
    "bmi": bmi.round(1),
    "systolic_bp": systolic_bp.round(0),
    "diastolic_bp": diastolic_bp.round(0),
    "glucose": glucose.round(0),
    "sleep_hours": sleep_hours.round(1),
    "activity_min_per_week": activity_min_per_week.round(0),
    "smoking": smoking,
    "alcohol": alcohol,
    "family_history": family_history,
    "water_intake_l": water_intake_l.round(1),
    "diet_quality": diet_quality,
    "stress_level": stress_level,
})

# ---------------------------------------------------------------------
# 2. Generate risk labels using a logistic-style rule + noise
#    (this mimics real epidemiological risk relationships)
# ---------------------------------------------------------------------
def sigmoid(x):
    return 1 / (1 + np.exp(-x))

# Diabetes risk driven mainly by glucose, bmi, age, family history, activity
diabetes_score = (
    0.05 * (df.glucose - 100) +
    0.08 * (df.bmi - 25) +
    0.03 * (df.age - 40) +
    1.2 * df.family_history -
    0.01 * df.activity_min_per_week +
    0.1 * df.stress_level +
    np.random.normal(0, 1.0, N)
)
df["diabetes_risk"] = (sigmoid(diabetes_score / 5) > 0.5).astype(int)

# Hypertension risk driven mainly by BP, age, bmi, smoking, stress
hyper_score = (
    0.06 * (df.systolic_bp - 120) +
    0.08 * (df.diastolic_bp - 80) +
    0.04 * (df.age - 40) +
    0.05 * (df.bmi - 25) +
    0.8 * df.smoking +
    0.15 * df.stress_level +
    np.random.normal(0, 1.0, N)
)
df["hypertension_risk"] = (sigmoid(hyper_score / 5) > 0.5).astype(int)

# Heart disease risk driven by combination of BP, glucose, bmi, age, smoking, family hist, sleep
heart_score = (
    0.04 * (df.systolic_bp - 120) +
    0.03 * (df.glucose - 100) +
    0.05 * (df.bmi - 25) +
    0.05 * (df.age - 40) +
    1.0 * df.smoking +
    1.0 * df.family_history -
    0.2 * (df.sleep_hours - 7) -
    0.008 * df.activity_min_per_week +
    0.1 * df.stress_level +
    np.random.normal(0, 1.2, N)
)
df["heart_risk"] = (sigmoid(heart_score / 6) > 0.5).astype(int)

# ---------------------------------------------------------------------
# 3. Feature encoding
# ---------------------------------------------------------------------
df["gender_male"] = (df["gender"] == "male").astype(int)

FEATURES = [
    "age", "gender_male", "bmi", "systolic_bp", "diastolic_bp", "glucose",
    "sleep_hours", "activity_min_per_week", "smoking", "alcohol",
    "family_history", "water_intake_l", "diet_quality", "stress_level"
]

X = df[FEATURES]
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# ---------------------------------------------------------------------
# 4. Train one RandomForestClassifier per disease
# ---------------------------------------------------------------------
def train_and_save(target_col, out_name):
    y = df[target_col]
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y
    )
    clf = RandomForestClassifier(
        n_estimators=200, max_depth=8, random_state=42, class_weight="balanced"
    )
    clf.fit(X_train, y_train)
    preds = clf.predict(X_test)
    proba = clf.predict_proba(X_test)[:, 1]
    acc = accuracy_score(y_test, preds)
    auc = roc_auc_score(y_test, proba)
    print(f"[{target_col}] accuracy={acc:.3f}  auc={auc:.3f}")
    joblib.dump(clf, os.path.join(MODEL_DIR, out_name))
    return clf

diabetes_model = train_and_save("diabetes_risk", "diabetes_model.joblib")
hypertension_model = train_and_save("hypertension_risk", "hypertension_model.joblib")
heart_model = train_and_save("heart_risk", "heart_model.joblib")

joblib.dump(scaler, os.path.join(MODEL_DIR, "scaler.joblib"))
joblib.dump(FEATURES, os.path.join(MODEL_DIR, "feature_names.joblib"))

df.to_csv(os.path.join(MODEL_DIR, "health_data.csv"), index=False)

print("\nAll models trained and saved to:", MODEL_DIR)
print("Files:", os.listdir(MODEL_DIR))
