"""Outbound message channels (SMS and WhatsApp via Twilio).

Delivers via the Twilio Messages API when credentials are configured;
otherwise messages are recorded to the outbox only, so local development
needs no Twilio account. Every message is recorded in the outbox either way —
`channel` says what happened: `sms-twilio` / `whatsapp-twilio` (delivered),
`sms-outbox` / `whatsapp-outbox` (recorded only), or `sms-twilio
(fallback: ...)` when a WhatsApp send was rejected and retried as SMS.

Customers' channel preference (last inbound channel, SMS default) lives in
`channel_prefs`; `send_preferred` routes by it.
"""

import base64
import hashlib
import hmac
import os

import httpx

from app import db
from app.services import outbox

TWILIO_API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


class ChannelError(Exception):
    """Delivery failed; message is safe to surface to the calling agent."""


def twilio_config() -> dict | None:
    """Platform Twilio account (shared across tenants); From numbers are
    per-tenant — see sms_from / whatsapp_from."""
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if sid and token:
        return {"sid": sid, "token": token}
    return None


def normalize_phone(address: str) -> str:
    """Bare E.164: strips Twilio's `whatsapp:` address prefix if present."""
    return address.removeprefix("whatsapp:").strip()


def _business_row(business_id: int, db_path: str | None = None) -> dict | None:
    from app.services import tenants  # lazy: avoid cycle at import time

    return tenants.get_business(business_id, db_path)


def sms_from(business_id: int = 1, db_path: str | None = None) -> str | None:
    """The tenant's outbound SMS number. For the default tenant only, the
    original TWILIO_FROM_NUMBER env var is the fallback — other tenants never
    send from a number they don't own (isolation; outbox record-only without)."""
    business = _business_row(business_id, db_path) or {}
    number = business.get("twilio_number")
    if not number and business_id == 1:
        number = os.environ.get("TWILIO_FROM_NUMBER")
    return number


def whatsapp_from(business_id: int = 1, db_path: str | None = None) -> str | None:
    """The tenant's WhatsApp sender, normalized to the `whatsapp:+E164` form.
    Default tenant falls back to TWILIO_WHATSAPP_FROM; others use their row only."""
    business = _business_row(business_id, db_path) or {}
    raw = business.get("whatsapp_sender")
    if not raw and business_id == 1:
        raw = os.environ.get("TWILIO_WHATSAPP_FROM")
    if not raw:
        return None
    return raw if raw.startswith("whatsapp:") else f"whatsapp:{raw}"


def _post(cfg: dict, from_addr: str, to_addr: str, body: str) -> httpx.Response:
    return httpx.post(
        TWILIO_API.format(sid=cfg["sid"]),
        auth=(cfg["sid"], cfg["token"]),
        data={"From": from_addr, "To": to_addr, "Body": body},
        timeout=30,
    )


def _deliver_sms(
    cfg: dict,
    from_number: str,
    to_phone: str,
    body: str,
    fallback_reason: str | None = None,
) -> str:
    response = _post(cfg, from_number, to_phone, body)
    if response.status_code >= 400:
        prefix = f"after {fallback_reason}, " if fallback_reason else ""
        raise ChannelError(
            f"Twilio send failed ({prefix}sms {response.status_code}): {response.text[:200]}"
        )
    return f"sms-twilio (fallback: {fallback_reason})" if fallback_reason else "sms-twilio"


def _deliver(
    cfg: dict,
    from_number: str,
    wa_from: str | None,
    to_phone: str,
    body: str,
    channel: str,
) -> str:
    """Deliver via Twilio; returns the outbox channel label. Raises ChannelError."""
    if channel != "whatsapp":
        return _deliver_sms(cfg, from_number, to_phone, body)
    if not wa_from:
        return _deliver_sms(
            cfg, from_number, to_phone, body, fallback_reason="no whatsapp sender"
        )
    response = _post(cfg, wa_from, f"whatsapp:{to_phone}", body)
    if response.status_code < 400:
        return "whatsapp-twilio"
    # 24h window / template rule / not a WhatsApp user: fall back to SMS so
    # the message still arrives (spec AC-004).
    return _deliver_sms(
        cfg, from_number, to_phone, body,
        fallback_reason=f"whatsapp {response.status_code}",
    )


def send(
    to_phone: str,
    body: str,
    customer_name: str | None = None,
    appointment_id: int | None = None,
    db_path: str | None = None,
    channel: str = "sms",
    business_id: int = 1,
) -> dict:
    """Send on `channel` ("sms" | "whatsapp"), record-only without Twilio creds
    or when the tenant has no sending number of its own.

    Returns the outbox row; its `channel` field records what actually happened.
    """
    to_phone = normalize_phone(to_phone)
    cfg = twilio_config()
    from_number = sms_from(business_id, db_path)
    if cfg and from_number:
        recorded = _deliver(
            cfg, from_number, whatsapp_from(business_id, db_path),
            to_phone, body, channel,
        )
    else:
        recorded = f"{channel}-outbox"
    return outbox.record(
        to_phone=to_phone,
        body=body,
        customer_name=customer_name,
        appointment_id=appointment_id,
        channel=recorded,
        db_path=db_path,
        business_id=business_id,
    )


def send_preferred(to_phone: str, body: str, business_id: int = 1, **kwargs) -> dict:
    """Send on the customer's preferred channel (last inbound; SMS default)."""
    phone = normalize_phone(to_phone)
    return send(
        phone,
        body,
        channel=preferred_channel(phone, business_id=business_id),
        business_id=business_id,
        **kwargs,
    )


def record_preference(
    phone: str, channel: str, db_path: str | None = None, business_id: int = 1
) -> None:
    """Upsert the customer's channel preference from an inbound message."""
    with db.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO channel_prefs (business_id, phone, preferred_channel)"
            " VALUES (?, ?, ?)"
            " ON CONFLICT(business_id, phone) DO UPDATE"
            " SET preferred_channel = excluded.preferred_channel,"
            " last_contact_at = datetime('now')",
            (business_id, normalize_phone(phone), channel),
        )
        conn.commit()


def preferred_channel(
    phone: str, db_path: str | None = None, business_id: int = 1
) -> str:
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT preferred_channel FROM channel_prefs"
            " WHERE phone = ? AND business_id = ?",
            (normalize_phone(phone), business_id),
        ).fetchone()
    return row["preferred_channel"] if row else "sms"


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
