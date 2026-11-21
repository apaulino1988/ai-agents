import base64
import hashlib
import hmac

import pytest

from app.services import channels, outbox

TWILIO_ENV = {
    "TWILIO_ACCOUNT_SID": "ACtest123",
    "TWILIO_AUTH_TOKEN": "secret-token",
    "TWILIO_FROM_NUMBER": "+15550000000",
}


class FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


def test_send_without_twilio_records_outbox_only(temp_db, monkeypatch):
    for key in TWILIO_ENV:
        monkeypatch.delenv(key, raising=False)
    record = channels.send("+15551112222", "Hello!")
    assert record["channel"] == "sms-outbox"
    assert len(outbox.list_messages()) == 1


def test_send_with_twilio_calls_api(temp_db, monkeypatch):
    for key, value in TWILIO_ENV.items():
        monkeypatch.setenv(key, value)
    calls = {}

    def fake_post(url, auth=None, data=None, timeout=None):
        calls["url"] = url
        calls["auth"] = auth
        calls["data"] = data
        return FakeResponse(201)

    monkeypatch.setattr(channels.httpx, "post", fake_post)
    record = channels.send("+15551112222", "Hello!")
    assert record["channel"] == "sms-twilio"
    assert calls["url"] == "https://api.twilio.com/2010-04-01/Accounts/ACtest123/Messages.json"
    assert calls["auth"] == ("ACtest123", "secret-token")
    assert calls["data"] == {"From": "+15550000000", "To": "+15551112222", "Body": "Hello!"}


def test_send_twilio_error_raises(temp_db, monkeypatch):
    for key, value in TWILIO_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(
        channels.httpx, "post", lambda *a, **k: FakeResponse(401, "auth failed")
    )
    with pytest.raises(channels.ChannelError):
        channels.send("+15551112222", "Hello!")
    assert outbox.list_messages() == []  # failed delivery is not recorded as sent


def test_validate_signature_roundtrip():
    token = "secret-token"
    url = "https://example.com/webhooks/sms"
    params = {"From": "+15551112222", "Body": "CONFIRM"}
    payload = url + "".join(f"{k}{v}" for k, v in sorted(params.items()))
    good = base64.b64encode(
        hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()
    ).decode()

    assert channels.validate_signature(url, params, good, auth_token=token)
    assert not channels.validate_signature(url, params, "tampered", auth_token=token)
    assert not channels.validate_signature(
        url, {**params, "Body": "CANCEL"}, good, auth_token=token
    )
