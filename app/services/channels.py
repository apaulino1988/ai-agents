"""Outbound message channels.

Delivers via Twilio SMS when credentials are configured; otherwise messages
are recorded to the outbox only, so local development needs no Twilio account.
Every message is recorded in the outbox either way — `channel` says whether it
was actually delivered (`sms-twilio`) or recorded only (`sms-outbox`).
"""

import base64
import hashlib
import hmac
import os

import httpx

from app.services import outbox

TWILIO_API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


class ChannelError(Exception):
    """Delivery failed; message is safe to surface to the calling agent."""


def twilio_config() -> dict | None:
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")
    if sid and token and from_number:
        return {"sid": sid, "token": token, "from": from_number}
    return None


def send(
    to_phone: str,
    body: str,
    customer_name: str | None = None,
    appointment_id: int | None = None,
    db_path: str | None = None,
) -> dict:
    """Send an SMS (or record-only without Twilio creds). Returns the outbox row."""
    cfg = twilio_config()
    channel = "sms-outbox"
    if cfg:
        response = httpx.post(
            TWILIO_API.format(sid=cfg["sid"]),
            auth=(cfg["sid"], cfg["token"]),
            data={"From": cfg["from"], "To": to_phone, "Body": body},
            timeout=30,
        )
        if response.status_code >= 400:
            raise ChannelError(
                f"Twilio send failed ({response.status_code}): {response.text[:200]}"
            )
        channel = "sms-twilio"
    return outbox.record(
        to_phone=to_phone,
        body=body,
        customer_name=customer_name,
        appointment_id=appointment_id,
        channel=channel,
        db_path=db_path,
    )


def validation_enabled() -> bool:
    return (
        os.environ.get("TWILIO_VALIDATE", "").lower() == "true"
        and bool(os.environ.get("TWILIO_AUTH_TOKEN"))
    )


def validate_signature(
    url: str, params: dict, signature: str, auth_token: str | None = None
) -> bool:
    """Twilio webhook signature check: base64(HMAC-SHA1(token, url + sorted k+v))."""
    token = auth_token or os.environ.get("TWILIO_AUTH_TOKEN", "")
    payload = url + "".join(f"{k}{v}" for k, v in sorted(params.items()))
    digest = hmac.new(token.encode(), payload.encode("utf-8"), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, signature)
