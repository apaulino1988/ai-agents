"""whatsapp-channel spec tests (specs/whatsapp-channel.md).

Test names carry the AC they verify (test_AC_NNN_*) for spec traceability.
"""

import pytest

from app.services import channels, outbox

TWILIO_ENV = {
    "TWILIO_ACCOUNT_SID": "ACtest123",
    "TWILIO_AUTH_TOKEN": "secret-token",
    "TWILIO_FROM_NUMBER": "+15550000000",
    "TWILIO_WHATSAPP_FROM": "whatsapp:+15550000000",
}


class FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


def set_twilio_env(monkeypatch, **overrides):
    env = {**TWILIO_ENV, **overrides}
    for key in TWILIO_ENV:
        if env.get(key) is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, env[key])


# ── AC-002: whatsapp sends use whatsapp:-prefixed addresses, same API ──────────


def test_AC_002_whatsapp_send_uses_prefixed_addresses(temp_db, monkeypatch):
    set_twilio_env(monkeypatch)
    calls = []

    def fake_post(url, auth=None, data=None, timeout=None):
        calls.append({"url": url, "data": data})
        return FakeResponse(201)

    monkeypatch.setattr(channels.httpx, "post", fake_post)
    record = channels.send("+15551112222", "Hola!", channel="whatsapp")
    assert record["channel"] == "whatsapp-twilio"
    assert calls[0]["url"] == (
        "https://api.twilio.com/2010-04-01/Accounts/ACtest123/Messages.json"
    )
    assert calls[0]["data"]["From"] == "whatsapp:+15550000000"
    assert calls[0]["data"]["To"] == "whatsapp:+15551112222"


def test_AC_002_default_channel_is_still_sms(temp_db, monkeypatch):
    set_twilio_env(monkeypatch)
    calls = []
    monkeypatch.setattr(
        channels.httpx,
        "post",
        lambda url, auth=None, data=None, timeout=None: (
            calls.append(data),
            FakeResponse(201),
        )[1],
    )
    record = channels.send("+15551112222", "Hello!")
    assert record["channel"] == "sms-twilio"
    assert calls[0]["To"] == "+15551112222"  # no whatsapp: prefix


# ── AC-005: no creds → record-only outbox ──────────────────────────────────────


def test_AC_005_whatsapp_without_creds_records_outbox_only(temp_db, monkeypatch):
    for key in TWILIO_ENV:
        monkeypatch.delenv(key, raising=False)
    record = channels.send("+15551112222", "Hola!", channel="whatsapp")
    assert record["channel"] == "whatsapp-outbox"
    assert len(outbox.list_messages()) == 1


def test_AC_005_whatsapp_without_sender_number_falls_back_to_sms(
    temp_db, monkeypatch
):
    # Twilio creds set, but no WhatsApp sender configured → deliver via SMS.
    set_twilio_env(monkeypatch, TWILIO_WHATSAPP_FROM=None)
    calls = []

    def fake_post(url, auth=None, data=None, timeout=None):
        calls.append(data)
        return FakeResponse(201)

    monkeypatch.setattr(channels.httpx, "post", fake_post)
    record = channels.send("+15551112222", "Hola!", channel="whatsapp")
    assert record["channel"].startswith("sms-twilio")
    assert calls[0]["To"] == "+15551112222"


# ── AC-004: whatsapp 4xx → automatic SMS fallback ─────────────────────────────


def test_AC_004_whatsapp_rejection_falls_back_to_sms(temp_db, monkeypatch):
    set_twilio_env(monkeypatch)
    calls = []

    def fake_post(url, auth=None, data=None, timeout=None):
        calls.append(data)
        if data["To"].startswith("whatsapp:"):
            return FakeResponse(400, "63016 outside window")
        return FakeResponse(201)

    monkeypatch.setattr(channels.httpx, "post", fake_post)
    record = channels.send("+15551112222", "Reminder", channel="whatsapp")
    assert len(calls) == 2
    assert calls[1]["To"] == "+15551112222"
    assert record["channel"].startswith("sms-twilio")
    assert "fallback" in record["channel"]  # AC-006: fallback reason recorded


def test_AC_004_both_channels_failing_raises(temp_db, monkeypatch):
    set_twilio_env(monkeypatch)
    monkeypatch.setattr(
        channels.httpx,
        "post",
        lambda url, auth=None, data=None, timeout=None: FakeResponse(400, "nope"),
    )
    with pytest.raises(channels.ChannelError):
        channels.send("+15551112222", "Reminder", channel="whatsapp")
    assert outbox.list_messages() == []


# ── AC-003: channel preference by phone, last-used wins, sms default ──────────


def test_AC_003_preference_defaults_to_sms(temp_db):
    assert channels.preferred_channel("+15551112222") == "sms"


def test_AC_003_preference_follows_last_inbound_channel(temp_db):
    channels.record_preference("+15551112222", "whatsapp")
    assert channels.preferred_channel("+15551112222") == "whatsapp"
    channels.record_preference("+15551112222", "sms")  # customer switches back
    assert channels.preferred_channel("+15551112222") == "sms"


def test_AC_003_send_preferred_routes_by_preference(temp_db, monkeypatch):
    set_twilio_env(monkeypatch)
    calls = []

    def fake_post(url, auth=None, data=None, timeout=None):
        calls.append(data)
        return FakeResponse(201)

    monkeypatch.setattr(channels.httpx, "post", fake_post)
    channels.record_preference("+15551112222", "whatsapp")
    record = channels.send_preferred("+15551112222", "Reminder")
    assert record["channel"] == "whatsapp-twilio"
    assert calls[0]["To"] == "whatsapp:+15551112222"
    # Unknown phone → SMS (TC-003)
    record = channels.send_preferred("+15559998888", "Reminder")
    assert record["channel"] == "sms-twilio"


# ── AC-001 / AC-007: inbound WhatsApp through the existing webhook ────────────


def test_AC_001_whatsapp_webhook_replies_twiml_and_normalizes_phone(
    temp_db, monkeypatch
):
    from fastapi.testclient import TestClient

    from app import main

    seen = {}

    def fake_run_turn(history, message):
        seen["message"] = message
        return "¡Confirmado!", history

    monkeypatch.setattr(main.agent, "run_turn", fake_run_turn)
    client = TestClient(main.app)
    resp = client.post(
        "/webhooks/sms",
        data={"From": "whatsapp:+15551112222", "Body": "CONFIRM"},
    )
    assert resp.status_code == 200
    assert "¡Confirmado!" in resp.text
    assert resp.headers["content-type"].startswith("application/xml")
    # Channel context names WhatsApp; phone is normalized (no whatsapp: prefix)
    assert "WhatsApp" in seen["message"]
    assert "+15551112222" in seen["message"]
    assert "whatsapp:+15551112222" not in seen["message"]


def test_AC_003_whatsapp_webhook_records_preference(temp_db, monkeypatch):
    from fastapi.testclient import TestClient

    from app import main

    monkeypatch.setattr(main.agent, "run_turn", lambda h, m: ("Hi!", h))
    client = TestClient(main.app)
    client.post(
        "/webhooks/sms",
        data={"From": "whatsapp:+15551112222", "Body": "hola"},
    )
    assert channels.preferred_channel("+15551112222") == "whatsapp"
    # An SMS from the same customer flips the preference back
    client.post("/webhooks/sms", data={"From": "+15551112222", "Body": "hi"})
    assert channels.preferred_channel("+15551112222") == "sms"
