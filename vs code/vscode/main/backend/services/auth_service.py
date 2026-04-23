"""
auth_service.py — Authentication helpers.

Password hashing, OTP issuance/verification, email sending.
Extracted from app.py lines 165-242.
"""

import re
import time
import hashlib
import secrets
import sqlite3

from backend.services.db import AUTH_DB_PATH

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
OTP_TTL_SECS = 600
RESEND_COOLDOWN = 60

# In-memory last-OTP store (dev convenience)
last_otp: dict = {}


# ---------------------------------------------------------------------------
# Password Hashing
# ---------------------------------------------------------------------------

def hash_password(pw: str) -> str:
    try:
        from argon2 import PasswordHasher
        return PasswordHasher().hash(pw)
    except ImportError:
        salt = secrets.token_hex(16)
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 260_000)
        return f"pbkdf2${salt}${dk.hex()}"


def verify_password(stored: str, pw: str) -> bool:
    if stored.startswith("$argon2"):
        from argon2 import PasswordHasher
        from argon2.exceptions import VerifyMismatchError
        try:
            PasswordHasher().verify(stored, pw)
            return True
        except VerifyMismatchError:
            return False
    if stored.startswith("pbkdf2$"):
        _, salt, dk_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 260_000)
        return secrets.compare_digest(dk.hex(), dk_hex)
    return False


# ---------------------------------------------------------------------------
# OTP Management
# ---------------------------------------------------------------------------

def issue_otp(email: str, purpose: str) -> str:
    code = str(secrets.randbelow(900_000) + 100_000)
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    with sqlite3.connect(AUTH_DB_PATH) as con:
        con.execute(
            "INSERT INTO otp_tokens(email,purpose,code_hash,expires_at) VALUES(?,?,?,?)",
            (email, purpose, code_hash, time.time() + OTP_TTL_SECS),
        )
        con.commit()
    return code


def verify_otp(email: str, purpose: str, code: str) -> bool:
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    with sqlite3.connect(AUTH_DB_PATH) as con:
        row = con.execute(
            "SELECT id FROM otp_tokens "
            "WHERE email=? AND purpose=? AND code_hash=? AND used=0 AND expires_at>?",
            (email, purpose, code_hash, time.time()),
        ).fetchone()
        if not row:
            return False
        con.execute("UPDATE otp_tokens SET used=1 WHERE id=?", (row[0],))
        con.commit()
    return True


def get_resend_wait(email: str, purpose: str) -> float:
    with sqlite3.connect(AUTH_DB_PATH) as con:
        row = con.execute(
            "SELECT MAX(expires_at) FROM otp_tokens WHERE email=? AND purpose=?",
            (email, purpose),
        ).fetchone()
    if not row or not row[0]:
        return 0
    issued_at = row[0] - OTP_TTL_SECS
    return max(RESEND_COOLDOWN - (time.time() - issued_at), 0)


def send_otp_email(to_email: str, code: str, purpose: str):
    label = "Verification" if purpose == "signup" else "Password Reset"
    print(f"\n  📧  {label} code for {to_email}: {code}\n", flush=True)
    last_otp["code"] = code
    last_otp["email"] = to_email
    last_otp["purpose"] = purpose
    last_otp["ts"] = time.time()
