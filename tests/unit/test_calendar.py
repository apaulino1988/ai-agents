"""calendar-sync spec tests (specs/calendar-sync.md).

Test names carry the AC they verify (test_AC_NNN_*) for spec traceability.
"""

from datetime import datetime

from app.services import booking, calendar

MONDAY = "2026-11-23"  # business open 09:00-17:00

GOOGLE_ENV = {
    "GOOGLE_SERVICE_ACCOUNT_FILE": "data/google-sa.json",
    "GOOGLE_CALENDAR_ID": "owner@example.com",
}


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict:
        return self._payload


def set_google_env(monkeypatch, enabled=True):
    for key, value in GOOGLE_ENV.items():
        if enabled:
            monkeypatch.setenv(key, value)
        else:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BUSINESS_TIMEZONE", "UTC")


def fake_token(monkeypatch):
    monkeypatch.setattr(calendar, "_access_token", lambda: "tok-123")


# ── AC-001: without creds, everything behaves exactly as today ────────────────


def test_AC_001_disabled_without_creds(temp_db, monkeypatch):
    set_google_env(monkeypatch, enabled=False)
    assert calendar.enabled() is False

    def boom(*a, **k):  # any calendar HTTP call is a failure
        raise AssertionError("calendar API must not be called when disabled")

    monkeypatch.setattr(calendar.httpx, "post", boom)
    monkeypatch.setattr(calendar.httpx, "delete", boom, raising=False)

    appt = booking.book_appointment("cleaning", MONDAY, "10:00", "Alice", "555-0001")
    assert appt["calendar_event_id"] is None
    assert "10:00" not in booking.check_availability(MONDAY, "cleaning")
    booking.cancel_appointment(appt["id"])


# ── AC-002: booking pushes a correct event and stores its id ──────────────────


def test_AC_002_create_event_payload(temp_db, monkeypatch):
    set_google_env(monkeypatch)
    fake_token(monkeypatch)
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers
        seen["json"] = json
        return FakeResponse(200, {"id": "evt-42"})

    monkeypatch.setattr(calendar.httpx, "post", fake_post)
    appt = {
        "id": 1,
        "service_id": "cleaning",
        "date": MONDAY,
        "time": "10:00",
        "duration_minutes": 60,
        "customer_name": "Alice",
        "customer_phone": "555-0001",
    }
    event_id = calendar.create_event(appt)
    assert event_id == "evt-42"
    assert "owner%40example.com" in seen["url"] or "owner@example.com" in seen["url"]
    assert seen["headers"]["Authorization"] == "Bearer tok-123"
    body = seen["json"]
    assert "Alice" in body["summary"] and "Cleaning" in body["summary"]
    assert body["start"]["dateTime"].startswith("2026-11-23T10:00")
    assert body["end"]["dateTime"].startswith("2026-11-23T11:00")


def test_AC_002_booking_stores_event_id(temp_db, monkeypatch):
    set_google_env(monkeypatch)
    monkeypatch.setattr(calendar, "create_event", lambda appt: "evt-99")
    monkeypatch.setattr(calendar, "busy_intervals", lambda date: [])
    appt = booking.book_appointment("cleaning", MONDAY, "10:00", "Alice", "555-0001")
    assert appt["calendar_event_id"] == "evt-99"


# ── AC-003: cancel deletes the event ──────────────────────────────────────────


def test_AC_003_cancel_deletes_event(temp_db, monkeypatch):
    set_google_env(monkeypatch)
    monkeypatch.setattr(calendar, "create_event", lambda appt: "evt-7")
    monkeypatch.setattr(calendar, "busy_intervals", lambda date: [])
    deleted = []
    monkeypatch.setattr(calendar, "delete_event", deleted.append)

    appt = booking.book_appointment("cleaning", MONDAY, "10:00", "Alice", "555-0001")
    booking.cancel_appointment(appt["id"])
    assert deleted == ["evt-7"]


def test_AC_003_cancel_without_event_skips_delete(temp_db, monkeypatch):
    set_google_env(monkeypatch, enabled=False)
    called = []
    monkeypatch.setattr(calendar, "delete_event", called.append)
    appt = booking.book_appointment("cleaning", MONDAY, "10:00", "Alice", "555-0001")
    booking.cancel_appointment(appt["id"])
    assert called == []


# ── AC-004: calendar busy times block availability ────────────────────────────


def test_AC_004_busy_interval_blocks_slots(temp_db, monkeypatch):
    set_google_env(monkeypatch)
    busy = [(datetime(1900, 1, 1, 10, 0), datetime(1900, 1, 1, 11, 0))]
    monkeypatch.setattr(calendar, "busy_intervals", lambda date: busy)

    slots = booking.check_availability(MONDAY, "cleaning")
    # 60-min service: any start overlapping 10:00-11:00 is excluded
    assert "10:00" not in slots
    assert "10:30" not in slots
    assert "09:30" not in slots
    assert "09:00" in slots
    assert "11:00" in slots


def test_AC_004_freebusy_parsing(temp_db, monkeypatch):
    set_google_env(monkeypatch)
    fake_token(monkeypatch)

    def fake_post(url, headers=None, json=None, timeout=None):
        assert url.endswith("/freeBusy")
        cal = json["items"][0]["id"]
        return FakeResponse(
            200,
            {
                "calendars": {
                    cal: {
                        "busy": [
                            {
                                "start": "2026-11-23T14:00:00Z",
                                "end": "2026-11-23T15:30:00Z",
                            }
                        ]
                    }
                }
            },
        )

    monkeypatch.setattr(calendar.httpx, "post", fake_post)
    intervals = calendar.busy_intervals(MONDAY)
    assert intervals == [(datetime(1900, 1, 1, 14, 0), datetime(1900, 1, 1, 15, 30))]


# ── AC-005: calendar failures never block the customer ────────────────────────


def test_AC_005_create_event_failure_returns_none(temp_db, monkeypatch):
    set_google_env(monkeypatch)
    fake_token(monkeypatch)
    monkeypatch.setattr(
        calendar.httpx, "post", lambda *a, **k: FakeResponse(503, text="down")
    )
    appt = {
        "id": 1,
        "service_id": "cleaning",
        "date": MONDAY,
        "time": "10:00",
        "duration_minutes": 60,
        "customer_name": "Alice",
        "customer_phone": "555-0001",
    }
    assert calendar.create_event(appt) is None  # logged, not raised


def test_AC_005_booking_succeeds_when_calendar_down(temp_db, monkeypatch):
    set_google_env(monkeypatch)
    fake_token(monkeypatch)

    def fake_post(url, headers=None, json=None, timeout=None):
        raise calendar.httpx.ConnectError("network down")

    monkeypatch.setattr(calendar.httpx, "post", fake_post)
    appt = booking.book_appointment("cleaning", MONDAY, "10:00", "Alice", "555-0001")
    assert appt["status"] == "booked"
    assert appt["calendar_event_id"] is None


def test_AC_005_busy_check_fails_open(temp_db, monkeypatch):
    set_google_env(monkeypatch)
    fake_token(monkeypatch)
    monkeypatch.setattr(
        calendar.httpx, "post", lambda *a, **k: FakeResponse(500, text="boom")
    )
    assert calendar.busy_intervals(MONDAY) == []
    # availability falls back to local data only
    slots = booking.check_availability(MONDAY, "cleaning")
    assert "09:00" in slots


# ── AC-007: service-account token exchange (no SDK) ───────────────────────────


def test_AC_007_token_exchange(temp_db, monkeypatch, tmp_path):
    sa = tmp_path / "sa.json"
    sa.write_text(
        '{"client_email": "svc@proj.iam.gserviceaccount.com",'
        ' "private_key": "fake-pem", "token_uri": "https://oauth2.googleapis.com/token"}'
    )
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(sa))
    monkeypatch.setenv("GOOGLE_CALENDAR_ID", "owner@example.com")
    calendar._token_cache.clear()

    monkeypatch.setattr(calendar.jwt, "encode", lambda claims, key, algorithm: "signed-jwt")
    seen = {}

    def fake_post(url, data=None, timeout=None, **kw):
        seen["url"] = url
        seen["data"] = data
        return FakeResponse(200, {"access_token": "tok-xyz", "expires_in": 3600})

    monkeypatch.setattr(calendar.httpx, "post", fake_post)
    token = calendar._access_token()
    assert token == "tok-xyz"
    assert seen["url"] == "https://oauth2.googleapis.com/token"
    assert seen["data"]["assertion"] == "signed-jwt"
    # cached: a second call must not hit the network again
    monkeypatch.setattr(calendar.httpx, "post", lambda *a, **k: 1 / 0)
    assert calendar._access_token() == "tok-xyz"
