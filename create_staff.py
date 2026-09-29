"""
create_staff.py
-----------------
Run this once to create a doctor or admin account directly (bypasses
email OTP verification, since these are trusted staff accounts you
create yourself).

Usage:
    python create_staff.py
"""

from werkzeug.security import generate_password_hash
from database import db

db.init_db()


def main():
    print("=== Create a Doctor or Admin account ===")
    role = input("Role (doctor/admin): ").strip().lower()
    if role not in ("doctor", "admin"):
        print("Role must be 'doctor' or 'admin'.")
        return

    name = input("Full name: ").strip()
    email = input("Email: ").strip().lower()
    password = input("Password: ").strip()
    age = input("Age (optional, press Enter to skip): ").strip()
    gender = input("Gender (optional, press Enter to skip): ").strip()

    if db.get_user_by_email(email):
        print(f"An account with email {email} already exists.")
        return

    password_hash = generate_password_hash(password)
    user_id = db.create_user(
        name, email, password_hash,
        age=int(age) if age else None,
        gender=gender if gender else None,
        role=role,
        is_verified=1,  # pre-verified, no OTP needed for staff accounts
    )

    print(f"\n{role.title()} account created successfully (id={user_id}).")
    print(f"Log in at /login with:\n  Email: {email}\n  Password: (the one you entered)")


if __name__ == "__main__":
    main()
