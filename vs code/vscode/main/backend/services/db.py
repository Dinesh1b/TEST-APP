"""
db.py — Database initialization and CRUD helpers.

Manages two SQLite databases:
  - qaudit.db  : run history
  - auth.db    : user accounts and OTP tokens
"""

import os
import time
import sqlite3

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(os.path.dirname(_HERE), "data")
os.makedirs(_DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(_DATA_DIR, "qaudit.db")
AUTH_DB_PATH = os.path.join(_DATA_DIR, "auth.db")


# ---------------------------------------------------------------------------
# Main DB — Run History
# ---------------------------------------------------------------------------

def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id     TEXT,
                step       TEXT,
                status     TEXT,
                progress   INTEGER DEFAULT 0,
                started_at REAL,
                ended_at   REAL
            )
        """)
        con.commit()


def db_insert_step(run_id, step, status, progress):
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "INSERT INTO runs(run_id,step,status,progress,started_at) VALUES(?,?,?,?,?)",
            (run_id, step, status, progress, time.time()),
        )
        con.commit()


def db_finish_run(run_id, status):
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "UPDATE runs SET ended_at=?, status=? WHERE run_id=? AND ended_at IS NULL",
            (time.time(), status, run_id),
        )
        con.commit()


def get_history():
    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute(
            "SELECT run_id, step, status, progress, started_at, ended_at "
            "FROM runs ORDER BY id DESC LIMIT 100"
        ).fetchall()
    return [
        {"run_id": r[0], "step": r[1], "status": r[2],
         "progress": r[3], "started_at": r[4], "ended_at": r[5]}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Auth DB — Users & OTP Tokens
# ---------------------------------------------------------------------------

def init_auth_db():
    with sqlite3.connect(AUTH_DB_PATH) as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT UNIQUE NOT NULL,
                first_name    TEXT,
                last_name     TEXT,
                password_hash TEXT,
                is_verified   INTEGER DEFAULT 0,
                created_at    REAL,
                last_login    REAL
            );
            CREATE TABLE IF NOT EXISTS otp_tokens (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                email      TEXT NOT NULL,
                purpose    TEXT NOT NULL,
                code_hash  TEXT NOT NULL,
                expires_at REAL NOT NULL,
                used       INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_otp_email ON otp_tokens(email, purpose);
        """)
        con.commit()
