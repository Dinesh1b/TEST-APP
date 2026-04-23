"""
auth.py — Authentication API routes.

Handles signup, login, logout, OTP verification, password set/reset.
"""

import time
import sqlite3

from flask import Blueprint, request, jsonify, session

from backend.services.auth_service import (
    EMAIL_RE,
    hash_password,
    verify_password,
    issue_otp,
    verify_otp,
    get_resend_wait,
    send_otp_email,
    last_otp,
)
from backend.services.db import AUTH_DB_PATH

auth_bp = Blueprint("auth", __name__)


def _json_ok(**kwargs):
    return jsonify({"ok": True, **kwargs})


def _json_err(msg: str, status: int = 400):
    return jsonify({"ok": False, "error": msg}), status


# ──────────────────────────────────────────────────────────────────────────
# DEV ROUTE — DELETE before deploying to production
# ──────────────────────────────────────────────────────────────────────────
@auth_bp.route("/dev/otp")
def dev_otp():
    if not last_otp:
        return jsonify({"ok": False})
    return jsonify({"ok": True, **last_otp})


# ──────────────────────────────────────────────────────────────────────────
# AUTH API ROUTES
# ──────────────────────────────────────────────────────────────────────────

@auth_bp.route("/auth/signup", methods=["POST"])
def api_signup():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()

    if not email or not EMAIL_RE.match(email):
        return _json_err("Invalid email address.")
    if not first_name or not last_name:
        return _json_err("First and last name are required.")

    with sqlite3.connect(AUTH_DB_PATH) as con:
        existing = con.execute(
            "SELECT id, is_verified FROM users WHERE email=?", (email,)
        ).fetchone()

    if existing:
        _, verified = existing
        if verified:
            return _json_err("An account with this email already exists.")

    with sqlite3.connect(AUTH_DB_PATH) as con:
        if not existing:
            con.execute(
                "INSERT INTO users(email,first_name,last_name,created_at) VALUES(?,?,?,?)",
                (email, first_name, last_name, time.time()),
            )
            con.commit()

    wait = get_resend_wait(email, "signup")
    if wait > 0:
        return _json_err(f"Please wait {int(wait)+1}s before requesting another code.")

    code = issue_otp(email, "signup")
    send_otp_email(email, code, "signup")
    return _json_ok(message="Verification code sent.")


@auth_bp.route("/auth/verify", methods=["POST"])
def api_verify():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    code = (data.get("code") or "").strip()

    if not email or not code:
        return _json_err("Email and code are required.")
    if not verify_otp(email, "signup", code):
        return _json_err("Invalid or expired verification code.")

    with sqlite3.connect(AUTH_DB_PATH) as con:
        con.execute("UPDATE users SET is_verified=1 WHERE email=?", (email,))
        con.commit()
    return _json_ok()


@auth_bp.route("/auth/resend", methods=["POST"])
def api_resend():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return _json_err("Email is required.")

    wait = get_resend_wait(email, "signup")
    if wait > 0:
        return _json_err(f"Please wait {int(wait)+1}s before resending.")

    code = issue_otp(email, "signup")
    send_otp_email(email, code, "signup")
    return _json_ok(message="Code resent.")


@auth_bp.route("/auth/set-password", methods=["POST"])
def api_set_password():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email:
        return _json_err("Email is required.")
    if len(password) < 8:
        return _json_err("Password must be at least 8 characters.")

    with sqlite3.connect(AUTH_DB_PATH) as con:
        row = con.execute(
            "SELECT id, is_verified FROM users WHERE email=?", (email,)
        ).fetchone()
    if not row:
        return _json_err("Account not found.")
    if not row[1]:
        return _json_err("Email not verified. Please complete verification first.")

    pw_hash = hash_password(password)
    with sqlite3.connect(AUTH_DB_PATH) as con:
        con.execute(
            "UPDATE users SET password_hash=? WHERE email=?", (pw_hash, email)
        )
        con.commit()

    session["user_id"] = row[0]
    session["email"] = email
    return _json_ok(message="Account created successfully.")


@auth_bp.route("/auth/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return _json_err("Email and password are required.")

    with sqlite3.connect(AUTH_DB_PATH) as con:
        row = con.execute(
            "SELECT id, password_hash, is_verified FROM users WHERE email=?", (email,)
        ).fetchone()

    if not row:
        return _json_err("Invalid email or password.")

    uid, pw_hash, verified = row

    if not verified:
        return _json_err("Please verify your email before signing in.")
    if not pw_hash:
        return _json_err("Account setup incomplete. Please set a password.")
    if not verify_password(pw_hash, password):
        return _json_err("Invalid email or password.")

    with sqlite3.connect(AUTH_DB_PATH) as con:
        con.execute("UPDATE users SET last_login=? WHERE id=?", (time.time(), uid))
        con.commit()

    session["user_id"] = uid
    session["email"] = email
    return _json_ok()


@auth_bp.route("/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return _json_ok(redirect="/login")


@auth_bp.route("/auth/forgot-password", methods=["POST"])
def api_forgot_password():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()

    if not email or not EMAIL_RE.match(email):
        return _json_err("Invalid email address.")

    with sqlite3.connect(AUTH_DB_PATH) as con:
        row = con.execute(
            "SELECT id FROM users WHERE email=? AND is_verified=1", (email,)
        ).fetchone()

    if row:
        wait = get_resend_wait(email, "reset")
        if wait <= 0:
            code = issue_otp(email, "reset")
            send_otp_email(email, code, "reset")

    return _json_ok(message="If that address is registered you will receive a reset code.")


@auth_bp.route("/auth/reset-password", methods=["POST"])
def api_reset_password():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    code = (data.get("code") or "").strip()
    password = data.get("password") or ""

    if not email or not code:
        return _json_err("Email and code are required.")
    if len(password) < 8:
        return _json_err("Password must be at least 8 characters.")
    if not verify_otp(email, "reset", code):
        return _json_err("Invalid or expired reset code.")

    pw_hash = hash_password(password)
    with sqlite3.connect(AUTH_DB_PATH) as con:
        con.execute(
            "UPDATE users SET password_hash=? WHERE email=?", (pw_hash, email)
        )
        con.commit()
    return _json_ok(message="Password updated successfully.")
