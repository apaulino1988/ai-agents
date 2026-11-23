"""Multi-tenant spec (specs/multi-tenant.md) — AC-001..AC-009."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import db
from app import main as main_module
from app.main import app
from app.services import booking, channels, knowledge, tenants

MONDAY = "2026-11-23"  # open day in the default (dental) profile

SALON_PROFILE = {
    "name": "Luz Salon",
    "tagline": "Hair & beauty",
    "description": "A neighborhood salon.",
    "location": "12 Main St",
    "phone": "+15557770000",
    "email": "hola@luzsalon.test",
    "hours": {
        "monday": ["10:00", "18:00"],
        "tuesday": ["10:00", "18:00"],
        "wednesday": None,
        "thursday": ["10:00", "18:00"],
        "friday": ["10:00", "18:00"],
        "saturday": ["09:00", "14:00"],
        "sunday": None,
    },
    "services": [
        {
            "id": "haircut",
            "name": "Haircut",
            "duration_minutes": 30,
            "price_usd": 45,
            "description": "Cut and style.",
        }
    ],
    "policies": ["Walk-ins welcome before noon."],
}


@pytest.fixture
def salon(temp_db):
    """A second business seeded alongside the default tenant."""
    return tenants.create_business(
        slug="luz-salon",
        name="Luz Salon",
        profile=SALON_PROFILE,
        timezone="America/New_York",
        twilio_number="+15557770000",
        whatsapp_sender="+15557770001",
    )


# ── AC-001: businesses table and tenant identity ───────────────────────────────


def test_AC_001_create_business_returns_full_identity(salon):
    assert salon["id"] > 1
    assert salon["slug"] == "luz-salon"
    assert salon["name"] == "Luz Salon"
    assert salon["profile"]["services"][0]["id"] == "haircut"
    assert salon["timezone"] == "America/New_York"
    assert salon["twilio_number"] == "+15557770000"
    assert salon["whatsapp_sender"] == "+15557770001"
    assert salon["status"] == "active"


def test_AC_001_lookup_by_slug_and_number(salon):
    assert tenants.get_by_slug("luz-salon")["id"] == salon["id"]
    assert tenants.get_by_number("+15557770000")["id"] == salon["id"]
    # WhatsApp sender matches too, with or without the whatsapp: prefix
    assert tenants.get_by_number("whatsapp:+15557770001")["id"] == salon["id"]
    assert tenants.get_by_slug("nope") is None
    assert tenants.get_by_number("+15550009999") is None


def test_AC_001_duplicate_slug_or_number_rejected(salon):
    with pytest.raises(tenants.TenantError):
        tenants.create_business(slug="luz-salon", name="Dup", profile=SALON_PROFILE)
    with pytest.raises(tenants.TenantError):
        tenants.create_business(
            slug="other", name="Dup", profile=SALON_PROFILE,
            twilio_number="+15557770000",
        )


# ── AC-002: business_id on all tenant-owned tables ─────────────────────────────


def test_AC_002_tenant_tables_carry_business_id(temp_db):
    with db.connect() as conn:
        for table in (
            "appointments",
            "conversation_log",
            "agent_tasks",
            "channel_prefs",
            "outbox",
        ):
            cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]
            assert "business_id" in cols, f"{table} missing business_id"


def test_AC_002_bookings_are_scoped_by_business(salon):
    booking.book_appointment("cleaning", MONDAY, "10:00", "Alice", "+15550001111")
    booking.book_appointment(
        "haircut", MONDAY, "10:00", "Alice", "+15550001111",
        business_id=salon["id"],
    )
    default_appts = booking.find_appointments("+15550001111")
    salon_appts = booking.find_appointments(
        "+15550001111", business_id=salon["id"]
    )
    assert len(default_appts) == 1 and default_appts[0]["service_id"] == "cleaning"
    assert len(salon_appts) == 1 and salon_appts[0]["service_id"] == "haircut"


# ── AC-003: existing databases migrate in place ────────────────────────────────

LEGACY_SCHEMA = """
CREATE TABLE appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id TEXT NOT NULL,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    customer_name TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'booked',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE conversation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE agent_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent TEXT NOT NULL,
    to_agent TEXT NOT NULL,
    task_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    due_at TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE channel_prefs (
    phone TEXT PRIMARY KEY,
    preferred_channel TEXT NOT NULL DEFAULT 'sms',
    last_contact_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    to_phone TEXT NOT NULL,
    customer_name TEXT,
    body TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'sms-outbox',
    appointment_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def test_AC_003_legacy_db_migrates_to_default_tenant(temp_db):
    raw = sqlite3.connect(temp_db)
    raw.executescript(LEGACY_SCHEMA)
    raw.execute(
        "INSERT INTO appointments (service_id, date, time, duration_minutes,"
        " customer_name, customer_phone) VALUES ('cleaning', ?, '10:00', 60,"
        " 'Legacy Customer', '+15550002222')",
        (MONDAY,),
    )
    raw.execute(
        "INSERT INTO channel_prefs (phone, preferred_channel)"
        " VALUES ('+15550002222', 'whatsapp')"
    )
    raw.commit()
    raw.close()

    default = tenants.get_default()  # connect() migrates + seeds
    assert default["id"] == 1
    assert default["profile"]["services"]  # seeded from data/business.json

    appts = booking.find_appointments("+15550002222")
    assert len(appts) == 1 and appts[0]["business_id"] == 1
    assert channels.preferred_channel("+15550002222") == "whatsapp"


def test_AC_003_migration_is_idempotent(temp_db):
    for _ in range(3):
        with db.connect() as conn:
            count = conn.execute("SELECT COUNT(*) AS n FROM businesses").fetchone()["n"]
    assert count == 1


# ── AC-004: webhook routes by receiving number ─────────────────────────────────


def _mock_agent(monkeypatch, seen):
    def fake_run_turn(history, msg):
        seen.append(msg)
        return "Claro!", []

    monkeypatch.setattr(main_module.agent, "run_turn", fake_run_turn)


def test_AC_004_inbound_to_number_routes_to_that_business(salon, monkeypatch):
    seen: list = []
    _mock_agent(monkeypatch, seen)
    client = TestClient(app)
    res = client.post(
        "/webhooks/sms",
        data={
            "From": "whatsapp:+15551112222",
            "To": "whatsapp:+15557770001",
            "Body": "Hola",
        },
    )
    assert res.status_code == 200
    # Preference recorded under the salon, not the default business
    assert channels.preferred_channel("+15551112222", business_id=salon["id"]) == "whatsapp"
    with db.connect() as conn:
        row = conn.execute(
            "SELECT preferred_channel FROM channel_prefs WHERE business_id = 1"
            " AND phone = '+15551112222'"
        ).fetchone()
    assert row is None


def test_AC_004_unknown_to_number_gets_polite_decline(temp_db, monkeypatch):
    seen: list = []
    _mock_agent(monkeypatch, seen)
    client = TestClient(app)
    res = client.post(
        "/webhooks/sms",
        data={"From": "+15551112222", "To": "+19990001234", "Body": "Hi"},
    )
    assert res.status_code == 200
    assert "<Message>" in res.text  # polite TwiML reply, not an error
    assert seen == []  # agent never invoked
    with db.connect() as conn:
        logs = conn.execute("SELECT COUNT(*) AS n FROM conversation_log").fetchone()["n"]
        prefs = conn.execute("SELECT COUNT(*) AS n FROM channel_prefs").fetchone()["n"]
    assert logs == 0 and prefs == 0  # nothing persisted for any tenant


def test_AC_004_missing_to_defaults_to_tenant_one(temp_db, monkeypatch):
    seen: list = []
    _mock_agent(monkeypatch, seen)
    client = TestClient(app)
    res = client.post(
        "/webhooks/sms", data={"From": "+15551112222", "Body": "Hi"}
    )
    assert res.status_code == 200
    assert channels.preferred_channel("+15551112222") == "sms"  # business 1
    assert len(seen) == 1


# ── AC-005: web chat resolves tenant from slug ─────────────────────────────────


def test_AC_005_chat_slug_selects_business(salon, monkeypatch):
    captured: list = []

    def fake_run_turn(history, msg):
        from app.tenant import current_business_id

        captured.append(current_business_id.get())
        return "Hello!", []

    monkeypatch.setattr(main_module.agent, "run_turn", fake_run_turn)
    client = TestClient(app)

    res = client.post("/chat", json={"message": "hi", "business": "luz-salon"})
    assert res.status_code == 200
    res = client.post("/chat", json={"message": "hi"})  # no slug → default
    assert res.status_code == 200
    res = client.post("/chat", json={"message": "hi", "business": "unknown-slug"})
    assert res.status_code == 200

    assert captured == [salon["id"], 1, 1]


# ── AC-006: services operate per tenant ────────────────────────────────────────


def test_AC_006_knowledge_is_per_tenant_from_db(salon):
    assert knowledge.get_profile()["name"] != "Luz Salon"
    assert knowledge.get_profile(business_id=salon["id"])["name"] == "Luz Salon"
    assert knowledge.get_service("haircut") is None  # not a default-tenant service
    svc = knowledge.get_service("haircut", business_id=salon["id"])
    assert svc and svc["duration_minutes"] == 30
    assert knowledge.hours_for_day("monday", business_id=salon["id"]) == (
        "10:00",
        "18:00",
    )
    text = knowledge.profile_as_prompt_text(business_id=salon["id"])
    assert "Luz Salon" in text and "Haircut" in text


def test_AC_006_availability_uses_tenant_hours(salon):
    # Salon opens at 10:00 on Mondays; default (dental) opens at 09:00
    salon_slots = booking.check_availability(
        MONDAY, "haircut", business_id=salon["id"]
    )
    assert salon_slots[0] == "10:00"
    default_slots = booking.check_availability(MONDAY, "cleaning")
    assert default_slots[0] == "09:00"
    # Tenant services don't leak: 'cleaning' is unknown to the salon
    with pytest.raises(booking.BookingError):
        booking.check_availability(MONDAY, "cleaning", business_id=salon["id"])


def test_AC_006_admin_profile_update_changes_answers(salon, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "sekret")
    client = TestClient(app)
    new_profile = dict(SALON_PROFILE, name="Luz Salon & Spa")
    res = client.put(
        f"/admin/businesses/{salon['slug']}",
        json={"profile": new_profile},
        headers={"Authorization": "Bearer sekret"},
    )
    assert res.status_code == 200
    assert knowledge.get_profile(business_id=salon["id"])["name"] == "Luz Salon & Spa"


# ── AC-007: cross-tenant isolation ─────────────────────────────────────────────


def test_AC_007_same_phone_isolated_across_tenants(salon):
    phone = "+15553334444"
    booking.book_appointment("cleaning", MONDAY, "11:00", "Ana", phone)
    booking.book_appointment(
        "haircut", MONDAY, "11:00", "Ana", phone, business_id=salon["id"]
    )
    channels.record_preference(phone, "sms")  # default tenant
    channels.record_preference(phone, "whatsapp", business_id=salon["id"])

    assert [a["service_id"] for a in booking.find_appointments(phone)] == ["cleaning"]
    assert [
        a["service_id"]
        for a in booking.find_appointments(phone, business_id=salon["id"])
    ] == ["haircut"]
    assert channels.preferred_channel(phone) == "sms"
    assert channels.preferred_channel(phone, business_id=salon["id"]) == "whatsapp"


def test_AC_007_outbox_and_reminders_are_tenant_scoped(salon):
    phone = "+15553334444"
    appt = booking.book_appointment(
        "haircut", MONDAY, "11:00", "Ana", phone, business_id=salon["id"]
    )
    record = channels.send(phone, "Reminder", business_id=salon["id"],
                           appointment_id=appt["id"])
    assert record["business_id"] == salon["id"]
    assert record["channel"] == "sms-outbox"  # no creds in unit tests


# ── AC-008: minimal admin API ──────────────────────────────────────────────────


def test_AC_008_admin_api_disabled_without_token(temp_db):
    client = TestClient(app)
    res = client.post(
        "/admin/businesses",
        json={"slug": "x", "name": "X", "profile": SALON_PROFILE},
        headers={"Authorization": "Bearer anything"},
    )
    assert res.status_code == 404


def test_AC_008_admin_api_requires_valid_token(temp_db, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "sekret")
    client = TestClient(app)
    payload = {"slug": "x", "name": "X", "profile": SALON_PROFILE}
    assert client.post("/admin/businesses", json=payload).status_code == 401
    res = client.post(
        "/admin/businesses",
        json=payload,
        headers={"Authorization": "Bearer wrong"},
    )
    assert res.status_code == 401


def test_AC_008_admin_create_and_update_business(temp_db, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "sekret")
    client = TestClient(app)
    headers = {"Authorization": "Bearer sekret"}
    res = client.post(
        "/admin/businesses",
        json={
            "slug": "barber",
            "name": "Main St Barber",
            "profile": SALON_PROFILE,
            "timezone": "America/Chicago",
            "twilio_number": "+15558880000",
        },
        headers=headers,
    )
    assert res.status_code == 201
    created = res.json()
    assert created["slug"] == "barber" and created["id"] > 1

    res = client.put(
        "/admin/businesses/barber",
        json={"name": "Main Street Barber", "status": "suspended"},
        headers=headers,
    )
    assert res.status_code == 200
    updated = tenants.get_by_slug("barber")
    assert updated["name"] == "Main Street Barber"
    assert updated["status"] == "suspended"

    assert client.put(
        "/admin/businesses/ghost", json={"name": "X"}, headers=headers
    ).status_code == 404


def test_AC_008_suspended_business_declines_politely(salon, monkeypatch):
    seen: list = []
    _mock_agent(monkeypatch, seen)
    monkeypatch.setenv("ADMIN_TOKEN", "sekret")
    client = TestClient(app)
    client.put(
        f"/admin/businesses/{salon['slug']}",
        json={"status": "suspended"},
        headers={"Authorization": "Bearer sekret"},
    )
    res = client.post(
        "/webhooks/sms",
        data={"From": "+15551112222", "To": "+15557770000", "Body": "Hi"},
    )
    assert res.status_code == 200
    assert "<Message>" in res.text
    assert seen == []  # agent not invoked for suspended tenants


# ── AC-009: PostgreSQL-portable schema ─────────────────────────────────────────


def test_AC_009_businesses_schema_is_portable(temp_db):
    with db.connect() as conn:
        cols = {
            r["name"]: r["type"].upper()
            for r in conn.execute("PRAGMA table_info(businesses)")
        }
    assert set(cols) >= {
        "id", "slug", "name", "profile", "timezone",
        "twilio_number", "whatsapp_sender", "calendar_id", "status", "created_at",
    }
    assert all(t in ("INTEGER", "TEXT") for t in cols.values()), cols
    # profile is JSON stored as TEXT
    with db.connect() as conn:
        raw = conn.execute("SELECT profile FROM businesses WHERE id = 1").fetchone()
    assert isinstance(json.loads(raw["profile"]), dict)
