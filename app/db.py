"""SQLite persistence for appointments and conversation logs."""

import os
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "secretary.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id TEXT NOT NULL,
    date TEXT NOT NULL,            -- YYYY-MM-DD
    time TEXT NOT NULL,            -- HH:MM
    duration_minutes INTEGER NOT NULL,
    customer_name TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'booked',   -- booked | cancelled
    confirmed_at TEXT,                       -- set when customer confirms
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conversation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,            -- user | assistant | tool
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent TEXT NOT NULL,
    to_agent TEXT NOT NULL,
    task_type TEXT NOT NULL,
    payload TEXT NOT NULL,         -- JSON
    due_at TEXT,                   -- ISO datetime; NULL = due immediately
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | done | failed
    result TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    to_phone TEXT NOT NULL,
    customer_name TEXT,
    body TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'sms-outbox',
    appointment_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def db_path() -> str:
    return os.environ.get("SECRETARY_DB_PATH", str(DEFAULT_DB))


def connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive migrations for databases created before a column existed."""
    try:
        conn.execute("ALTER TABLE appointments ADD COLUMN confirmed_at TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists
