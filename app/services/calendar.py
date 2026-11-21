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

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"
SCOPE = "https://www.googleapis.com/auth/calendar"
TOKEN_SLACK_SECONDS = 60  # refresh slightly before expiry

_token_cache: dict = {}


class CalendarError(Exception):
    """Internal calendar failure; callers log it, never surface to customers."""


def config() -> dict | None:
    sa_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    calendar_id = os.environ.get("GOOGLE_CALENDAR_ID")
    if sa_file and calendar_id:
        return {"sa_file": sa_file, "calendar_id": calendar_id}
    return None


def enabled() -> bool:
    return config() is not None


def business_tz() -> ZoneInfo:
    return ZoneInfo(os.environ.get("BUSINESS_TIMEZONE", "UTC"))


def _access_token() -> str:
    """Service-account JWT grant → access token, cached until expiry."""
    if _token_cache.get("token") and time.time() < _token_cache.get("expires_at", 0):
        return _token_cache["token"]

    cfg = config()
    if not cfg:
        raise CalendarError("Calendar not configured.")
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


def _event_times(appointment: dict) -> tuple[dict, dict]:
    start = datetime.strptime(
        f"{appointment['date']} {appointment['time']}", "%Y-%m-%d %H:%M"
    )
    end = start + timedelta(minutes=appointment["duration_minutes"])
    tz = os.environ.get("BUSINESS_TIMEZONE", "UTC")
    return (
        {"dateTime": start.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": tz},
        {"dateTime": end.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": tz},
    )


def create_event(appointment: dict) -> str | None:
    """Push a booking to the calendar. Returns the event id, or None on any failure."""
    cfg = config()
    if not cfg:
        return None
    try:
        from app.services import knowledge

        service = knowledge.get_service(appointment["service_id"]) or {}
        service_name = service.get("name", appointment["service_id"].title())
        start, end = _event_times(appointment)
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


def delete_event(event_id: str) -> None:
    """Best-effort event removal (cancellations, reschedules)."""
    cfg = config()
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


def busy_intervals(date: str) -> list[tuple[datetime, datetime]]:
    """Busy windows on `date` in time-of-day space (same space as booking's
    `_parse_time`: naive datetimes on 1900-01-01). Fails open to []."""
    cfg = config()
    if not cfg:
        return []
    try:
        tz = business_tz()
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
