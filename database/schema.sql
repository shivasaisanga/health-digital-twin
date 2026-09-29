-- MySQL schema for AI Personalized Health Digital Twin
-- Create the database first:  CREATE DATABASE health_twin;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    age INT,
    gender VARCHAR(20),
    role VARCHAR(20) NOT NULL DEFAULT 'patient',   -- 'patient' | 'doctor' | 'admin'
    is_verified TINYINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS health_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    bmi FLOAT,
    systolic_bp FLOAT,
    diastolic_bp FLOAT,
    glucose FLOAT,
    sleep_hours FLOAT,
    activity_min_per_week FLOAT,
    smoking TINYINT,
    alcohol TINYINT,
    family_history TINYINT,
    water_intake_l FLOAT,
    diet_quality INT,
    stress_level INT,
    health_score FLOAT,
    metabolic_score FLOAT,
    cardio_score FLOAT,
    sleep_score FLOAT,
    activity_score FLOAT,
    diabetes_risk FLOAT,
    hypertension_risk FLOAT,
    heart_risk FLOAT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS otp_codes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(150) NOT NULL,
    otp_code VARCHAR(10) NOT NULL,
    purpose VARCHAR(30) NOT NULL DEFAULT 'register',
    expires_at DATETIME NOT NULL,
    used TINYINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS chat_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    message TEXT,
    response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS login_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    method VARCHAR(20) NOT NULL DEFAULT 'password',
    logged_in_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS health_goals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    target_health_score FLOAT NOT NULL,
    baseline_health_score FLOAT NOT NULL,
    target_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS appointments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    doctor_id INT NOT NULL,
    requested_time VARCHAR(100) NOT NULL,
    notes TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_health_records_user ON health_records(user_id, recorded_at);
CREATE INDEX idx_otp_email ON otp_codes(email, purpose);
