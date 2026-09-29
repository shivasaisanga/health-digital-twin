"""
app.py
-------
AI Personalized Health Digital Twin with Predictive Risk Intelligence
Main Flask application.

Run:
    python models/train_model.py     # once, to train the ML models
    python app.py                    # start the server
Then open http://127.0.0.1:5000

Roles: 'patient' (default), 'doctor', 'admin'.
Use create_staff.py to create doctor/admin accounts (see README).
"""

import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from database import db
from utils.health_score import compute_scores
from utils.predictor import predict_risks
from utils.xai import explain_all
from utils.recommendations import generate_recommendations
from utils.habit_impact import rank_habit_impacts
from utils.pdf_report import build_report
from utils.email_otp import generate_otp, get_expiry, send_otp_email, send_email, OTP_VALIDITY_MINUTES
from utils.chatbot import get_response as chatbot_response
from utils.forecast import forecast_all
from utils.streaks import calculate_streak
import csv
import io
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "change-this-secret-key-in-production"

db.init_db()

DOCTOR_ACCESS_CODE = os.environ.get("DOCTOR_ACCESS_CODE", "DOCTOR2026")


# ---------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------
def current_user():
    if "user_id" not in session:
        return None
    return db.get_user_by_id(session["user_id"])


def login_required(view_fn):
    @wraps(view_fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_fn(*args, **kwargs)
    return wrapper


def role_required(role):
    def decorator(view_fn):
        @wraps(view_fn)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            user = current_user()
            if not user or user["role"] != role:
                flash("You don't have access to that page.", "error")
                return redirect(url_for("dashboard"))
            return view_fn(*args, **kwargs)
        return wrapper
    return decorator


@app.context_processor
def inject_user():
    return {"logged_in_user": current_user() if "user_id" in session else None}


# ---------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        age = int(request.form["age"])
        gender = request.form["gender"]
        requested_role = request.form.get("role", "patient")
        access_code = request.form.get("access_code", "").strip()

        if db.get_user_by_email(email):
            flash("An account with this email already exists.", "error")
            return redirect(url_for("register"))

        role = "patient"
        if requested_role == "doctor":
            if access_code != DOCTOR_ACCESS_CODE:
                flash("Invalid doctor access code.", "error")
                return redirect(url_for("register"))
            role = "doctor"

        password_hash = generate_password_hash(password)
        db.create_user(name, email, password_hash, age, gender, role=role, is_verified=0)

        # Generate & send OTP for email verification
        otp_code = generate_otp()
        db.create_otp(email, otp_code, "register", get_expiry())
        sent = send_otp_email(email, otp_code, purpose="register")

        session["pending_email"] = email
        if sent:
            flash("Account created! Check your email for a 6-digit verification code.", "success")
        else:
            flash(f"DEMO MODE (email not configured): your OTP is {otp_code}", "success")

        return redirect(url_for("verify_otp"))

    return render_template("register.html")


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    email = session.get("pending_email")
    if not email:
        return redirect(url_for("register"))

    if request.method == "POST":
        entered = request.form.get("otp", "").strip()
        otp_row = db.get_valid_otp(email, entered, "register")

        if not otp_row:
            flash("Invalid OTP. Please try again.", "error")
            return redirect(url_for("verify_otp"))

        from datetime import datetime
        if datetime.strptime(otp_row["expires_at"], "%Y-%m-%d %H:%M:%S") < datetime.now():
            flash("This OTP has expired. Please request a new one.", "error")
            return redirect(url_for("verify_otp"))

        db.mark_otp_used(otp_row["id"])
        db.mark_user_verified(email)

        user = db.get_user_by_email(email)
        session.pop("pending_email", None)
        session["user_id"] = user["id"]
        flash("Email verified successfully! Welcome to your Digital Twin.", "success")

        if user["role"] == "doctor":
            return redirect(url_for("doctor_dashboard"))
        return redirect(url_for("intake"))

    return render_template("verify_otp.html", email=email, validity=OTP_VALIDITY_MINUTES)


@app.route("/resend-otp")
def resend_otp():
    email = session.get("pending_email")
    if not email:
        return redirect(url_for("register"))

    otp_code = generate_otp()
    db.create_otp(email, otp_code, "register", get_expiry())
    sent = send_otp_email(email, otp_code, purpose="register")

    if sent:
        flash("A new OTP has been sent to your email.", "success")
    else:
        flash(f"DEMO MODE (email not configured): your new OTP is {otp_code}", "success")

    return redirect(url_for("verify_otp"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = db.get_user_by_email(email)

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))

        if not user["is_verified"]:
            session["pending_email"] = email
            flash("Please verify your email before logging in.", "error")
            return redirect(url_for("verify_otp"))

        session["user_id"] = user["id"]
        db.log_login(user["id"], method="password")
        if user["role"] == "doctor":
            return redirect(url_for("doctor_dashboard"))
        if user["role"] == "admin":
            return redirect(url_for("admin_users"))
        return redirect(url_for("dashboard"))

    return render_template("login.html")


# ---------------------------------------------------------------------
# Passwordless OTP Login
# ---------------------------------------------------------------------
@app.route("/login-otp/request", methods=["GET", "POST"])
def login_otp_request():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        user = db.get_user_by_email(email)
        if not user:
            flash("No account found with that email.", "error")
            return redirect(url_for("login_otp_request"))
        if not user["is_verified"]:
            flash("This account isn't verified yet. Please verify your email first.", "error")
            session["pending_email"] = email
            return redirect(url_for("verify_otp"))

        otp_code = generate_otp()
        db.create_otp(email, otp_code, "login", get_expiry())
        sent = send_otp_email(email, otp_code, purpose="login")

        session["login_otp_email"] = email
        if sent:
            flash("A login OTP has been sent to your email.", "success")
        else:
            flash(f"DEMO MODE (email not configured): your login OTP is {otp_code}", "success")

        return redirect(url_for("login_otp_verify"))

    return render_template("login_otp_request.html")


@app.route("/login-otp/verify", methods=["GET", "POST"])
def login_otp_verify():
    email = session.get("login_otp_email")
    if not email:
        return redirect(url_for("login_otp_request"))

    if request.method == "POST":
        entered = request.form.get("otp", "").strip()
        otp_row = db.get_valid_otp(email, entered, "login")

        if not otp_row:
            flash("Invalid OTP. Please try again.", "error")
            return redirect(url_for("login_otp_verify"))

        from datetime import datetime
        if datetime.strptime(otp_row["expires_at"], "%Y-%m-%d %H:%M:%S") < datetime.now():
            flash("This OTP has expired. Please request a new one.", "error")
            return redirect(url_for("login_otp_request"))

        db.mark_otp_used(otp_row["id"])
        user = db.get_user_by_email(email)
        session.pop("login_otp_email", None)
        session["user_id"] = user["id"]
        db.log_login(user["id"], method="otp")
        flash("Logged in successfully via OTP!", "success")

        if user["role"] == "doctor":
            return redirect(url_for("doctor_dashboard"))
        if user["role"] == "admin":
            return redirect(url_for("admin_users"))
        return redirect(url_for("dashboard"))

    return render_template("login_otp_verify.html", email=email, validity=OTP_VALIDITY_MINUTES)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------
# Health data intake
# ---------------------------------------------------------------------
@app.route("/intake", methods=["GET", "POST"])
@login_required
def intake():
    user = current_user()

    if request.method == "POST":
        form = request.form
        data = {
            "age": user["age"],
            "gender": user["gender"],
            "bmi": float(form["bmi"]),
            "systolic_bp": float(form["systolic_bp"]),
            "diastolic_bp": float(form["diastolic_bp"]),
            "glucose": float(form["glucose"]),
            "sleep_hours": float(form["sleep_hours"]),
            "activity_min_per_week": float(form["activity_min_per_week"]),
            "smoking": 1 if form.get("smoking") == "on" else 0,
            "alcohol": 1 if form.get("alcohol") == "on" else 0,
            "family_history": 1 if form.get("family_history") == "on" else 0,
            "water_intake_l": float(form["water_intake_l"]),
            "diet_quality": int(form["diet_quality"]),
            "stress_level": int(form["stress_level"]),
        }

        scores = compute_scores(data)
        risks = predict_risks(data)
        db.add_health_record(user["id"], data, scores, risks)

        # SOS / Critical Risk Alert — notify the user if any risk crosses 80%
        critical = {k: v for k, v in risks.items() if v >= 80}
        if critical:
            labels = {"diabetes_risk": "Diabetes", "hypertension_risk": "Hypertension", "heart_risk": "Heart Disease"}
            lines = "\n".join(f"- {labels[k]}: {v}%" for k, v in critical.items())
            body = (
                f"Hi {user['name']},\n\n"
                f"Your latest health check-in shows a critically high predicted risk:\n\n{lines}\n\n"
                f"Please consider consulting a healthcare professional soon.\n\n"
                f"— AI Health Digital Twin"
            )
            send_email(user["email"], "⚠ Critical Health Risk Alert", body)
            crit_names = ", ".join(labels[k] for k in critical)
            flash(f"⚠ SOS Alert: your {crit_names} risk is critically high. Please consult a doctor soon.", "error")

        return redirect(url_for("dashboard"))

    return render_template("intake.html", user=user)


# ---------------------------------------------------------------------
# Dashboard (patient)
# ---------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    record = db.get_latest_record(user["id"])

    if not record:
        return redirect(url_for("intake"))

    data = _record_to_input(user, record)
    xai = explain_all(data, top_n=3)
    tips = generate_recommendations(data, {
        "diabetes_risk": record["diabetes_risk"],
        "hypertension_risk": record["hypertension_risk"],
        "heart_risk": record["heart_risk"],
    })
    top_changes = rank_habit_impacts(data, top_n=5)
    history = db.get_history(user["id"])
    streak = calculate_streak(history)
    goal = db.get_latest_goal(user["id"])

    return render_template(
        "dashboard.html",
        user=user, record=record, xai=xai, tips=tips,
        top_changes=top_changes, history=history, streak=streak, goal=goal
    )


def _record_to_input(user, record):
    return {
        "age": user["age"],
        "gender": user["gender"],
        "bmi": record["bmi"],
        "systolic_bp": record["systolic_bp"],
        "diastolic_bp": record["diastolic_bp"],
        "glucose": record["glucose"],
        "sleep_hours": record["sleep_hours"],
        "activity_min_per_week": record["activity_min_per_week"],
        "smoking": record["smoking"],
        "alcohol": record["alcohol"],
        "family_history": record["family_history"],
        "water_intake_l": record["water_intake_l"],
        "diet_quality": record["diet_quality"],
        "stress_level": record["stress_level"],
    }


# ---------------------------------------------------------------------
# What-If Simulation (AJAX endpoint used by dashboard.html / JS)
# ---------------------------------------------------------------------
@app.route("/api/whatif", methods=["POST"])
@login_required
def api_whatif():
    user = current_user()
    record = db.get_latest_record(user["id"])
    if not record:
        return jsonify({"error": "No baseline health record found."}), 400

    base_data = _record_to_input(user, record)
    overrides = request.get_json(force=True) or {}

    simulated = dict(base_data)
    for key in ["bmi", "systolic_bp", "diastolic_bp", "glucose", "sleep_hours",
                "activity_min_per_week", "water_intake_l"]:
        if key in overrides:
            simulated[key] = float(overrides[key])
    for key in ["diet_quality", "stress_level"]:
        if key in overrides:
            simulated[key] = int(overrides[key])
    for key in ["smoking", "alcohol", "family_history"]:
        if key in overrides:
            simulated[key] = int(overrides[key])

    scores = compute_scores(simulated)
    risks = predict_risks(simulated)

    return jsonify({"scores": scores, "risks": risks})


# ---------------------------------------------------------------------
# Conversational Twin — Chatbot API
# ---------------------------------------------------------------------
@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    user = current_user()
    record = db.get_latest_record(user["id"])
    payload = request.get_json(force=True) or {}
    message = payload.get("message", "").strip()

    if not message:
        return jsonify({"reply": "Ask me something about your health score, risk, or habits!"})

    reply = chatbot_response(message, user, record)
    db.log_chat(user["id"], message, reply)

    return jsonify({"reply": reply})


# ---------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------
@app.route("/timeline")
@login_required
def timeline():
    user = current_user()
    history = db.get_history(user["id"], limit=100)
    forecast = forecast_all(history)
    return render_template("timeline.html", user=user, history=history, forecast=forecast)


# ---------------------------------------------------------------------
# Admin — view registered users (role-protected)
# ---------------------------------------------------------------------
@app.route("/admin/users")
@role_required("admin")
def admin_users():
    users = db.get_all_users()
    return render_template("admin_users.html", users=users)


# ---------------------------------------------------------------------
# Doctor Dashboard — view all patients and drill into their twin
# ---------------------------------------------------------------------
@app.route("/doctor/dashboard")
@role_required("doctor")
def doctor_dashboard():
    patients = db.get_users_by_role("patient")
    patient_summaries = []
    for p in patients:
        record = db.get_latest_record(p["id"])
        patient_summaries.append({"patient": p, "record": record})
    return render_template("doctor_dashboard.html", patient_summaries=patient_summaries)


@app.route("/doctor/patient/<int:patient_id>")
@role_required("doctor")
def doctor_view_patient(patient_id):
    patient = db.get_user_by_id(patient_id)
    if not patient or patient["role"] != "patient":
        flash("Patient not found.", "error")
        return redirect(url_for("doctor_dashboard"))

    record = db.get_latest_record(patient_id)
    if not record:
        flash(f"{patient['name']} has not logged any health data yet.", "error")
        return redirect(url_for("doctor_dashboard"))

    data = _record_to_input(patient, record)
    xai = explain_all(data, top_n=3)
    tips = generate_recommendations(data, {
        "diabetes_risk": record["diabetes_risk"],
        "hypertension_risk": record["hypertension_risk"],
        "heart_risk": record["heart_risk"],
    })
    top_changes = rank_habit_impacts(data, top_n=5)
    history = db.get_history(patient_id)

    return render_template(
        "doctor_patient_view.html",
        patient=patient, record=record, xai=xai, tips=tips,
        top_changes=top_changes, history=history
    )


# ---------------------------------------------------------------------
# Doctor-Share Mode — PDF report
# ---------------------------------------------------------------------
@app.route("/report/download")
@login_required
def download_report():
    user = current_user()
    record = db.get_latest_record(user["id"])
    if not record:
        flash("No health data available yet.", "error")
        return redirect(url_for("intake"))

    data = _record_to_input(user, record)
    xai = explain_all(data, top_n=3)
    tips = generate_recommendations(data, {
        "diabetes_risk": record["diabetes_risk"],
        "hypertension_risk": record["hypertension_risk"],
        "heart_risk": record["heart_risk"],
    })
    top_changes = rank_habit_impacts(data, top_n=5)

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"health_report_user{user['id']}.pdf")

    build_report(path, user, record, xai, tips, top_changes)

    return send_file(path, as_attachment=True, download_name="Health_Digital_Twin_Report.pdf")


# ---------------------------------------------------------------------
# Forgot / Reset Password via OTP
# ---------------------------------------------------------------------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        user = db.get_user_by_email(email)
        if not user:
            flash("No account found with that email.", "error")
            return redirect(url_for("forgot_password"))

        otp_code = generate_otp()
        db.create_otp(email, otp_code, "reset", get_expiry())
        sent = send_otp_email(email, otp_code, purpose="reset")

        session["reset_email"] = email
        if sent:
            flash("A password reset code has been sent to your email.", "success")
        else:
            flash(f"DEMO MODE (email not configured): your reset OTP is {otp_code}", "success")

        return redirect(url_for("reset_password"))

    return render_template("forgot_password.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    email = session.get("reset_email")
    if not email:
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        entered = request.form.get("otp", "").strip()
        new_password = request.form.get("password", "")
        otp_row = db.get_valid_otp(email, entered, "reset")

        if not otp_row:
            flash("Invalid OTP. Please try again.", "error")
            return redirect(url_for("reset_password"))

        if datetime.strptime(otp_row["expires_at"], "%Y-%m-%d %H:%M:%S") < datetime.now():
            flash("This OTP has expired. Please request a new one.", "error")
            return redirect(url_for("forgot_password"))

        if len(new_password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect(url_for("reset_password"))

        db.mark_otp_used(otp_row["id"])
        db.update_password(email, generate_password_hash(new_password))
        session.pop("reset_email", None)
        flash("Password reset successfully! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", email=email, validity=OTP_VALIDITY_MINUTES)


# ---------------------------------------------------------------------
# Export health data as CSV
# ---------------------------------------------------------------------
@app.route("/export/csv")
@login_required
def export_csv():
    user = current_user()
    history = db.get_history(user["id"], limit=1000)

    output = io.StringIO()
    if history:
        writer = csv.DictWriter(output, fieldnames=list(history[0].keys()))
        writer.writeheader()
        writer.writerows(history)
    else:
        output.write("No health records found.\n")

    mem = io.BytesIO(output.getvalue().encode("utf-8"))
    return send_file(mem, as_attachment=True, download_name="health_history.csv", mimetype="text/csv")


# ---------------------------------------------------------------------
# Security / Login activity log
# ---------------------------------------------------------------------
@app.route("/account/security")
@login_required
def account_security():
    user = current_user()
    logins = db.get_recent_logins(user["id"], limit=5)
    return render_template("security.html", user=user, logins=logins)


# ---------------------------------------------------------------------
# Health Goals & Progress Tracking
# ---------------------------------------------------------------------
@app.route("/goals", methods=["GET", "POST"])
@login_required
def goals():
    user = current_user()
    record = db.get_latest_record(user["id"])

    if request.method == "POST":
        if not record:
            flash("Log a health update first before setting a goal.", "error")
            return redirect(url_for("intake"))

        target_score = float(request.form["target_health_score"])
        target_date = request.form["target_date"]
        db.create_goal(user["id"], target_score, record["health_score"], target_date)
        flash("Goal set successfully!", "success")
        return redirect(url_for("goals"))

    goal = db.get_latest_goal(user["id"])
    progress_pct = None
    if goal and record:
        span = goal["target_health_score"] - goal["baseline_health_score"]
        if span != 0:
            progress_pct = round(((record["health_score"] - goal["baseline_health_score"]) / span) * 100, 1)
            progress_pct = max(0, min(100, progress_pct))
        else:
            progress_pct = 100

    return render_template("goals.html", user=user, record=record, goal=goal, progress_pct=progress_pct)


# ---------------------------------------------------------------------
# Privacy / Consent — download data, delete account
# ---------------------------------------------------------------------
@app.route("/privacy")
@login_required
def privacy():
    return render_template("privacy.html")


@app.route("/account/delete", methods=["POST"])
@login_required
def delete_account():
    user = current_user()
    db.delete_user(user["id"])
    session.clear()
    flash("Your account and all associated data have been deleted.", "success")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------
# Appointment Booking
# ---------------------------------------------------------------------
@app.route("/appointments", methods=["GET", "POST"])
@login_required
def appointments():
    user = current_user()
    if user["role"] != "patient":
        flash("Only patients can book appointments.", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        doctor_id = int(request.form["doctor_id"])
        requested_time = request.form["requested_time"]
        notes = request.form.get("notes", "")
        db.create_appointment(user["id"], doctor_id, requested_time, notes)
        flash("Appointment request sent!", "success")
        return redirect(url_for("appointments"))

    doctors = db.get_users_by_role("doctor")
    my_appointments = db.get_appointments_for_patient(user["id"])
    return render_template("appointments.html", doctors=doctors, appointments=my_appointments)


@app.route("/doctor/appointments", methods=["GET", "POST"])
@role_required("doctor")
def doctor_appointments():
    user = current_user()

    if request.method == "POST":
        appt_id = int(request.form["appointment_id"])
        status = request.form["status"]
        db.update_appointment_status(appt_id, status)
        flash("Appointment updated.", "success")
        return redirect(url_for("doctor_appointments"))

    my_appointments = db.get_appointments_for_doctor(user["id"])
    return render_template("doctor_appointments.html", appointments=my_appointments)


# ---------------------------------------------------------------------
# About the Developer
# ---------------------------------------------------------------------
@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(debug=True)
