"""
email_otp.py
-------------
Generates and sends One-Time Passwords (OTP) via email for:
  - registration verification
  - passwordless OTP login

Uses Python's built-in smtplib (no extra dependency). To enable real
email sending, set these values below (or as environment variables):

    SMTP_EMAIL    - your Gmail address (e.g. yourproject@gmail.com)
    SMTP_PASSWORD - a Gmail "App Password" (NOT your normal password;
                    generate one at https://myaccount.google.com/apppasswords
                    after enabling 2-Step Verification on the Gmail account)

If SMTP is not configured or sending fails (e.g. no internet, wrong
credentials), the app falls back to DEMO MODE: the OTP is shown directly
on screen with a flash message instead of emailed, so the project can
still be demoed/evaluated without email setup.
"""

import os
import random
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta

SMTP_EMAIL = os.environ.get("SMTP_EMAIL", "")        # set your Gmail address here
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")  # set your Gmail App Password here
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

OTP_VALIDITY_MINUTES = 10


def generate_otp():
    return str(random.randint(100000, 999999))


def get_expiry():
    return (datetime.now() + timedelta(minutes=OTP_VALIDITY_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")


def send_otp_email(to_email, otp_code, purpose="register"):
    """
    Returns True if a real email was sent, False if it fell back to demo mode.
    Caller should flash the OTP on screen when this returns False.
    """
    subject = "Your Health Digital Twin Verification Code"
    if purpose == "login":
        subject = "Your Health Digital Twin Login OTP"
    elif purpose == "reset":
        subject = "Your Health Digital Twin Password Reset Code"

    body = (
        f"Your OTP code is: {otp_code}\n\n"
        f"This code is valid for {OTP_VALIDITY_MINUTES} minutes.\n"
        f"If you did not request this, you can safely ignore this email."
    )

    return send_email(to_email, subject, body)


def send_email(to_email, subject, body):
    """
    General-purpose email sender (used for OTPs and SOS risk alerts).
    Returns True if sent, False if SMTP isn't configured or sending failed.
    """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        return False

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_EMAIL
        msg["To"] = to_email

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"[email_otp] Failed to send email: {e}")
        return False
