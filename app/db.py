"""SQLite persistence for tenants, appointments and conversation logs.

Multi-tenant: every tenant-owned table carries `business_id`; the `businesses`
table is the tenant registry. Existing single-tenant databases migrate in
place — a default business (id=1) is seeded from `data/business.json` plus the
original env-var channel/calendar settings, and pre-existing rows backfill to
it via the column DEFAULT. New DDL sticks to INTEGER/TEXT so the schema stays
PostgreSQL-portable (spec AC-009).
"""

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "secretary.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS businesses (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    profile TEXT NOT NULL,         -- JSON, same shape as data/business.json
    timezone TEXT NOT NULL DEFAULT 'UTC',
    twilio_number TEXT,            -- E.164; inbound SMS routing key
    whatsapp_sender TEXT,          -- E.164, stored bare (no whatsapp: prefix)
    calendar_id TEXT,              -- NULL = calendar sync off for this tenant
    status TEXT NOT NULL DEFAULT 'active',   -- active | suspended
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL DEFAULT 1,
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
    business_id INTEGER NOT NULL DEFAULT 1,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,            -- user | assistant | tool
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL DEFAULT 1,
    from_agent TEXT NOT NULL,
    to_agent TEXT NOT NULL,
    task_type TEXT NOT NULL,
    payload TEXT NOT NULL,         -- JSON
    due_at TEXT,                   -- ISO datetime; NULL = due immediately
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | done | failed
    result TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS channel_prefs (
    business_id INTEGER NOT NULL DEFAULT 1,
    phone TEXT NOT NULL,                 -- E.164, never whatsapp:-prefixed
    preferred_channel TEXT NOT NULL DEFAULT 'sms',  -- sms | whatsapp
    last_contact_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (business_id, phone)
);

CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL DEFAULT 1,
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


@contextmanager
def connect(path: str | None = None) -> Iterator[sqlite3.Connection]:
    """Context manager: yields a ready (migrated, seeded) connection and
    closes it on exit. Callers commit explicitly."""
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    try:
        yield conn
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive migrations for databases created before a column existed."""
    for statement in (
        "ALTER TABLE appointments ADD COLUMN confirmed_at TEXT",
        "ALTER TABLE appointments ADD COLUMN calendar_event_id TEXT",
        "ALTER TABLE appointments ADD COLUMN business_id INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE conversation_log ADD COLUMN business_id INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE agent_tasks ADD COLUMN business_id INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE outbox ADD COLUMN business_id INTEGER NOT NULL DEFAULT 1",
    ):
        try:
            conn.execute(statement)
        except sqlite3.OperationalError:
            pass  # column already exists
    _migrate_channel_prefs(conn)
    _seed_default_business(conn)
    conn.commit()


def _migrate_channel_prefs(conn: sqlite3.Connection) -> None:
    """Rebuild channel_prefs with the (business_id, phone) composite key."""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(channel_prefs)")]
    if "business_id" in cols:
        return
    conn.executescript(
        """
        ALTER TABLE channel_prefs RENAME TO channel_prefs_legacy;
        CREATE TABLE channel_prefs (
            business_id INTEGER NOT NULL DEFAULT 1,
            phone TEXT NOT NULL,
            preferred_channel TEXT NOT NULL DEFAULT 'sms',
            last_contact_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (business_id, phone)
        );
        INSERT INTO channel_prefs (business_id, phone, preferred_channel, last_contact_at)
            SELECT 1, phone, preferred_channel, last_contact_at
            FROM channel_prefs_legacy;
        DROP TABLE channel_prefs_legacy;
        """
    )


def _seed_default_business(conn: sqlite3.Connection) -> None:
    """Create the default tenant (id=1) once, from the original single-tenant
    config: data/business.json plus the env-var channel/calendar settings."""
    if conn.execute("SELECT 1 FROM businesses WHERE id = 1").fetchone():
        return
    profile = _default_profile()
    whatsapp = os.environ.get("TWILIO_WHATSAPP_FROM", "").removeprefix("whatsapp:")
    conn.execute(
        "INSERT INTO businesses"
        " (id, slug, name, profile, timezone, twilio_number, whatsapp_sender, calendar_id)"
        " VALUES (1, 'default', ?, ?, ?, ?, ?, ?)",
        (
            profile.get("name", "Default Business"),
            json.dumps(profile),
            os.environ.get("BUSINESS_TIMEZONE", "UTC"),
            os.environ.get("TWILIO_FROM_NUMBER"),
            whatsapp or None,
            os.environ.get("GOOGLE_CALENDAR_ID"),
        ),
    )


def _default_profile() -> dict:
    from app.services.knowledge import business_file  # lazy: avoids import cycle

    path = business_file()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {
        "name": "Default Business",
        "tagline": "",
        "description": "",
        "location": "",
        "phone": "",
        "email": "",
        "hours": {},
        "services": [],
        "policies": [],
    }
