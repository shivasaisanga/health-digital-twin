"""
db.py
------
Lightweight database layer using Python's built-in sqlite3 module.
This keeps the project dependency-free and runnable out of the box.

To switch to MySQL for production/deployment, see database/schema.sql
and README.md for the pymysql-based version of this file.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "health_twin.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        age INTEGER,
        gender TEXT,
        role TEXT NOT NULL DEFAULT 'patient',
        is_verified INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS health_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        bmi REAL,
        systolic_bp REAL,
        diastolic_bp REAL,
        glucose REAL,
        sleep_hours REAL,
        activity_min_per_week REAL,
        smoking INTEGER,
        alcohol INTEGER,
        family_history INTEGER,
        water_intake_l REAL,
        diet_quality INTEGER,
        stress_level INTEGER,
        health_score REAL,
        metabolic_score REAL,
        cardio_score REAL,
        sleep_score REAL,
        activity_score REAL,
        diabetes_risk REAL,
        hypertension_risk REAL,
        heart_risk REAL,
        recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS otp_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        otp_code TEXT NOT NULL,
        purpose TEXT NOT NULL DEFAULT 'register',
        expires_at TEXT NOT NULL,
        used INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS chat_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message TEXT,
        response TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS login_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        method TEXT NOT NULL DEFAULT 'password',
        logged_in_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS health_goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        target_health_score REAL NOT NULL,
        baseline_health_score REAL NOT NULL,
        target_date TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        requested_time TEXT NOT NULL,
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    conn.commit()

    # Lightweight migration for older DBs created before role/is_verified existed
    cur.execute("PRAGMA table_info(users)")
    cols = [r["name"] for r in cur.fetchall()]
    if "role" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'patient'")
    if "is_verified" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER NOT NULL DEFAULT 0")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------
def create_user(name, email, password_hash, age, gender, role="patient", is_verified=0):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (name, email, password_hash, age, gender, role, is_verified) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, email, password_hash, age, gender, role, is_verified),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def get_user_by_email(email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def mark_user_verified(email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_verified = 1 WHERE email = ?", (email,))
    conn.commit()
    conn.close()


def update_password(email, password_hash):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET password_hash = ? WHERE email = ?", (password_hash, email))
    conn.commit()
    conn.close()


def get_all_users():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, age, gender, role, is_verified, created_at "
                "FROM users ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_users_by_role(role):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, age, gender, created_at FROM users "
                "WHERE role = ? ORDER BY created_at DESC", (role,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------
# OTP helpers
# ---------------------------------------------------------------------
def create_otp(email, otp_code, purpose, expires_at):
    conn = get_connection()
    cur = conn.cursor()
    # invalidate older unused OTPs for this email/purpose
    cur.execute("UPDATE otp_codes SET used = 1 WHERE email = ? AND purpose = ? AND used = 0",
                (email, purpose))
    cur.execute(
        "INSERT INTO otp_codes (email, otp_code, purpose, expires_at) VALUES (?, ?, ?, ?)",
        (email, otp_code, purpose, expires_at),
    )
    conn.commit()
    conn.close()


def get_valid_otp(email, otp_code, purpose):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM otp_codes WHERE email = ? AND otp_code = ? AND purpose = ? "
        "AND used = 0 ORDER BY created_at DESC LIMIT 1",
        (email, otp_code, purpose),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def mark_otp_used(otp_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE otp_codes SET used = 1 WHERE id = ?", (otp_id,))
    conn.commit()
    conn.close()


def get_latest_otp_for_email(email, purpose):
    """Used only for the offline/demo fallback display when SMTP isn't configured."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM otp_codes WHERE email = ? AND purpose = ? AND used = 0 "
        "ORDER BY created_at DESC LIMIT 1",
        (email, purpose),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------
# Health record helpers
# ---------------------------------------------------------------------
def add_health_record(user_id, data, scores, risks):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO health_records (
            user_id, bmi, systolic_bp, diastolic_bp, glucose, sleep_hours,
            activity_min_per_week, smoking, alcohol, family_history,
            water_intake_l, diet_quality, stress_level,
            health_score, metabolic_score, cardio_score, sleep_score, activity_score,
            diabetes_risk, hypertension_risk, heart_risk
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, data["bmi"], data["systolic_bp"], data["diastolic_bp"], data["glucose"],
        data["sleep_hours"], data["activity_min_per_week"], data["smoking"], data["alcohol"],
        data["family_history"], data["water_intake_l"], data["diet_quality"], data["stress_level"],
        scores["health_score"], scores["metabolic_score"], scores["cardio_score"],
        scores["sleep_score"], scores["activity_score"],
        risks["diabetes_risk"], risks["hypertension_risk"], risks["heart_risk"]
    ))
    conn.commit()
    record_id = cur.lastrowid
    conn.close()
    return record_id


def get_latest_record(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM health_records WHERE user_id = ? ORDER BY recorded_at DESC LIMIT 1",
        (user_id,)
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_history(user_id, limit=30):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM health_records WHERE user_id = ? ORDER BY recorded_at ASC LIMIT ?",
        (user_id, limit)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------
# Chat log helpers (for the Conversational Twin chatbot)
# ---------------------------------------------------------------------
def log_chat(user_id, message, response):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO chat_logs (user_id, message, response) VALUES (?, ?, ?)",
        (user_id, message, response),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------
# Login activity log
# ---------------------------------------------------------------------
def log_login(user_id, method="password"):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO login_logs (user_id, method) VALUES (?, ?)",
        (user_id, method),
    )
    conn.commit()
    conn.close()


def get_recent_logins(user_id, limit=5):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM login_logs WHERE user_id = ? ORDER BY logged_in_at DESC LIMIT ?",
        (user_id, limit)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------
# Health goals
# ---------------------------------------------------------------------
def create_goal(user_id, target_health_score, baseline_health_score, target_date):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO health_goals (user_id, target_health_score, baseline_health_score, target_date) "
        "VALUES (?, ?, ?, ?)",
        (user_id, target_health_score, baseline_health_score, target_date),
    )
    conn.commit()
    conn.close()


def get_latest_goal(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM health_goals WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------
def create_appointment(patient_id, doctor_id, requested_time, notes):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO appointments (patient_id, doctor_id, requested_time, notes) VALUES (?, ?, ?, ?)",
        (patient_id, doctor_id, requested_time, notes),
    )
    conn.commit()
    appt_id = cur.lastrowid
    conn.close()
    return appt_id


def get_appointments_for_patient(patient_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.*, u.name AS doctor_name FROM appointments a
        JOIN users u ON u.id = a.doctor_id
        WHERE a.patient_id = ? ORDER BY a.created_at DESC
    """, (patient_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_appointments_for_doctor(doctor_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.*, u.name AS patient_name FROM appointments a
        JOIN users u ON u.id = a.patient_id
        WHERE a.doctor_id = ? ORDER BY a.created_at DESC
    """, (doctor_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_appointment_status(appointment_id, status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE appointments SET status = ? WHERE id = ?", (status, appointment_id))
    conn.commit()
    conn.close()
