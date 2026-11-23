"""Google Calendar provider (calendar-sync spec).

Push + busy-block behind a small provider interface: bookings create events
on the business calendar, and the calendar's busy times block availability.
Mirrors the Twilio pattern — without `GOOGLE_SERVICE_ACCOUNT_FILE` and
`GOOGLE_CALENDAR_ID`, everything is disabled and the app behaves as before.

Failure policy (spec AC-005): the calendar must never block a customer.
`create_event`/`delete_event` log failures and return; `busy_intervals`
fails open (empty list). Auth is a service-account JWT grant exchanged for
an access token over plain httpx — no Google SDK.
"""

import json
import logging
import os
import time
import urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import jwt

from app.tenant import current_business_id

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"
SCOPE = "https://www.googleapis.com/auth/calendar"
TOKEN_SLACK_SECONDS = 60  # refresh slightly before expiry

_token_cache: dict = {}


class CalendarError(Exception):
    """Internal calendar failure; callers log it, never surface to customers."""


def _business_row(business_id: int) -> dict | None:
    from app.services import tenants  # lazy: avoid cycle at import time

    return tenants.get_business(business_id)


def _resolve(business_id: int | None) -> int:
    """Explicit business_id wins; otherwise the request's tenant context.
    Keeps public call shapes single-tenant-compatible (callers may omit it)."""
    if business_id is not None:
        return business_id
    return current_business_id.get()


def config(business_id: int | None = None) -> dict | None:
    """Per-tenant calendar config. One platform service account is shared;
    the calendar id comes from the business row. For the default tenant only,
    the original GOOGLE_CALENDAR_ID env var still works as a fallback —
    other tenants never inherit it (isolation)."""
    business_id = _resolve(business_id)
    sa_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not sa_file:
        return None
    business = _business_row(business_id) or {}
    calendar_id = business.get("calendar_id")
    if not calendar_id and business_id == 1:
        calendar_id = os.environ.get("GOOGLE_CALENDAR_ID")
    if not calendar_id:
        return None
    return {"sa_file": sa_file, "calendar_id": calendar_id}


def enabled(business_id: int | None = None) -> bool:
    return config(business_id) is not None


def _tz_name(business_id: int | None = None) -> str:
    business_id = _resolve(business_id)
    env_tz = os.environ.get("BUSINESS_TIMEZONE")
    if business_id == 1 and env_tz:
        return env_tz
    business = _business_row(business_id)
    if business and business.get("timezone"):
        return business["timezone"]
    return env_tz or "UTC"


def business_tz(business_id: int | None = None) -> ZoneInfo:
    return ZoneInfo(_tz_name(business_id))


def _access_token() -> str:
    """Service-account JWT grant → access token, cached until expiry.

    The platform shares one service account across tenants, so the token is
    tenant-independent (only sa_file matters here)."""
    if _token_cache.get("token") and time.time() < _token_cache.get("expires_at", 0):
        return _token_cache["token"]

    sa_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not sa_file:
        raise CalendarError("Calendar not configured.")
    cfg = {"sa_file": sa_file}
    with open(cfg["sa_file"], encoding="utf-8") as f:
        sa = json.load(f)

    now = int(time.time())
    claims = {
        "iss": sa["client_email"],
        "scope": SCOPE,
        "aud": sa.get("token_uri", TOKEN_URL),
        "iat": now,
        "exp": now + 3600,
    }
    assertion = jwt.encode(claims, sa["private_key"], algorithm="RS256")
    response = httpx.post(
        sa.get("token_uri", TOKEN_URL),
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise CalendarError(f"Token exchange failed ({response.status_code}).")
    payload = response.json()
    _token_cache["token"] = payload["access_token"]
    _token_cache["expires_at"] = (
        time.time() + payload.get("expires_in", 3600) - TOKEN_SLACK_SECONDS
    )
    return _token_cache["token"]


def _headers() -> dict:
    return {"Authorization": f"Bearer {_access_token()}"}


def _event_times(appointment: dict, tz: str) -> tuple[dict, dict]:
    start = datetime.strptime(
        f"{appointment['date']} {appointment['time']}", "%Y-%m-%d %H:%M"
    )
    end = start + timedelta(minutes=appointment["duration_minutes"])
    return (
        {"dateTime": start.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": tz},
        {"dateTime": end.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": tz},
    )


def create_event(appointment: dict, business_id: int | None = None) -> str | None:
    """Push a booking to the calendar. Returns the event id, or None on any failure."""
    business_id = _resolve(business_id)
    cfg = config(business_id)
    if not cfg:
        return None
    try:
        from app.services import knowledge

        service = knowledge.get_service(appointment["service_id"], business_id) or {}
        service_name = service.get("name", appointment["service_id"].title())
        start, end = _event_times(appointment, _tz_name(business_id))
        response = httpx.post(
            f"{CALENDAR_API}/calendars/"
            f"{urllib.parse.quote(cfg['calendar_id'])}/events",
            headers=_headers(),
            json={
                "summary": f"{service_name} — {appointment['customer_name']}",
                "description": (
                    f"Booked by AI Secretary. Phone: {appointment['customer_phone']}. "
                    f"Appointment #{appointment['id']}."
                ),
                "start": start,
                "end": end,
            },
            timeout=30,
        )
        if response.status_code >= 400:
            raise CalendarError(f"Event create failed ({response.status_code}).")
        return response.json().get("id")
    except Exception as exc:  # noqa: BLE001 — AC-005: never block the booking
        logger.warning("Calendar push failed for appointment %s: %s",
                       appointment.get("id"), exc)
        return None


def delete_event(event_id: str, business_id: int | None = None) -> None:
    """Best-effort event removal (cancellations, reschedules)."""
    cfg = config(business_id)
    if not cfg or not event_id:
        return
    try:
        response = httpx.delete(
            f"{CALENDAR_API}/calendars/"
            f"{urllib.parse.quote(cfg['calendar_id'])}/events/{event_id}",
            headers=_headers(),
            timeout=30,
        )
        if response.status_code >= 400 and response.status_code != 404:
            raise CalendarError(f"Event delete failed ({response.status_code}).")
    except Exception as exc:  # noqa: BLE001 — AC-005
        logger.warning("Calendar delete failed for event %s: %s", event_id, exc)


def busy_intervals(
    date: str, business_id: int | None = None
) -> list[tuple[datetime, datetime]]:
    """Busy windows on `date` in time-of-day space (same space as booking's
    `_parse_time`: naive datetimes on 1900-01-01). Fails open to []."""
    cfg = config(business_id)
    if not cfg:
        return []
    try:
        tz = business_tz(business_id)
        day_start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=tz)
        day_end = day_start + timedelta(days=1)
        response = httpx.post(
            f"{CALENDAR_API}/freeBusy",
            headers=_headers(),
            json={
                "timeMin": day_start.isoformat(),
                "timeMax": day_end.isoformat(),
                "items": [{"id": cfg["calendar_id"]}],
            },
            timeout=30,
        )
        if response.status_code >= 400:
            raise CalendarError(f"freeBusy failed ({response.status_code}).")
        busy = response.json()["calendars"][cfg["calendar_id"]].get("busy", [])
        intervals = []
        for window in busy:
            start = _to_time_of_day(window["start"], tz, day_start, day_end, floor=True)
            end = _to_time_of_day(window["end"], tz, day_start, day_end, floor=False)
            if start < end:
                intervals.append((start, end))
        return intervals
    except Exception as exc:  # noqa: BLE001 — AC-005: fail open
        logger.warning("Calendar busy check failed for %s: %s", date, exc)
        return []


def _to_time_of_day(
    rfc3339: str, tz: ZoneInfo, day_start: datetime, day_end: datetime, floor: bool
) -> datetime:
    """RFC3339 instant → naive 1900-01-01 time-of-day in the business timezone,
    clamped to the queried day (handles multi-day and all-day busy windows)."""
    instant = datetime.fromisoformat(rfc3339).astimezone(tz)
    instant = max(day_start, min(instant, day_end))
    if instant >= day_end and floor:
        instant = day_end
    hhmm = instant.strftime("%H:%M") if instant < day_end else "23:59"
    return datetime.strptime(hhmm, "%H:%M")
