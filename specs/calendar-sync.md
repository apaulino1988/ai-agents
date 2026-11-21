# Spec: calendar-sync (M3 — real channels)

**Version:** 0.1.0
**Created:** 2026-11-21
**PRD Reference:** docs/prd.md (M3: real-channels — final item)
**Status:** Implementing

## 1. Overview

Connect the business's real Google Calendar to the booking service, in both
directions that matter for Alpha: bookings made by the Secretary appear as
calendar events (push), and busy events already on the calendar block the
agent's availability (busy-block), so the Secretary never double-books over
the owner's real life. Provider-agnostic interface with Google as the Alpha
implementation (Outlook follows in M4). Mirrors the Twilio pattern: without
credentials, everything behaves exactly as today.

### User Story

As a **business owner**, I want the AI Secretary to work from my real
calendar — writing bookings onto it and respecting what's already there — so
that I have one trustworthy calendar and no double bookings.

## 2. Acceptance Criteria

| ID | Criterion | Priority |
|----|-----------|----------|
| AC-001 | Without Google credentials, booking/availability/cancel behave exactly as today — no calendar calls, no errors | Must |
| AC-002 | A new booking creates a Google Calendar event (service name, customer, correct start/end from date+time+duration); the event id is stored on the appointment | Must |
| AC-003 | Cancelling an appointment deletes its calendar event; rescheduling moves it (delete + recreate acceptable) | Must |
| AC-004 | `check_availability` excludes slots that overlap busy intervals from the calendar (freeBusy query), merged with existing booking conflicts | Must |
| AC-005 | Calendar outage or API errors never block the customer: booking/cancel succeed with the push logged as failed; busy-check failures fail open (local availability only) | Must |
| AC-006 | Calendar access goes through a provider interface; Google is the only Alpha provider (Outlook = M4) | Should |
| AC-007 | Google auth is a service account (JWT grant exchanged for an access token via httpx — no Google SDK), configured by env vars | Must |

## 3. User Test Cases

### TC-001: Booking lands on the real calendar

**Precondition:** Google creds configured (mocked in tests); calendar empty.
**Steps:**
1. Customer books "haircut tomorrow 10:00" via any channel.
2. Booking service inserts the appointment and pushes a calendar event.
**Expected Result:** Event created with correct title ("Haircut — {customer}"), start 10:00, end 10:00+duration; `appointments.calendar_event_id` set.
**Screenshot Checkpoint:** N/A (API-level)
**Maps to:** TBD

### TC-002: Owner's dentist appointment blocks the slot

**Precondition:** Calendar has a busy event tomorrow 10:00–11:00 (mocked freeBusy).
**Steps:**
1. Customer asks for availability tomorrow.
**Expected Result:** No offered slot overlaps 10:00–11:00; slots outside it are unaffected.
**Maps to:** TBD

### TC-003: Calendar down, customer still books

**Precondition:** Google creds configured; calendar API returns 503 (mocked).
**Steps:**
1. Customer books a slot.
**Expected Result:** Appointment is created and confirmed to the customer; `calendar_event_id` is NULL; failure is logged, not raised.
**Maps to:** TBD

### TC-004: Cancellation cleans up the event

**Precondition:** Appointment with a stored `calendar_event_id`.
**Steps:**
1. Customer cancels.
**Expected Result:** Calendar DELETE called for that event id; appointment status cancelled.
**Maps to:** TBD

## 4. Data Model

### appointments (existing — extended, additive migration)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| calendar_event_id | TEXT | No | Google event id; NULL when calendar disabled or push failed |

### Relationships

One appointment ↔ zero or one calendar event. No new tables; the calendar is
not a local store, it's an external system of record for the owner's time.

## 5. API Contract

No new HTTP endpoints. Internal provider interface (`app/services/calendar.py`):

- `enabled() -> bool` — creds present
- `create_event(appointment: dict) -> str | None` — returns event id; never raises to callers (logs and returns None)
- `delete_event(event_id: str) -> None` — best-effort
- `busy_intervals(date: str) -> list[tuple[datetime, datetime]]` — freeBusy; empty list on failure (fail open)

Google REST endpoints used: `POST .../calendars/{id}/events`, `DELETE .../events/{eventId}`, `POST .../freeBusy`, token exchange at `oauth2.googleapis.com/token`.

## 6. UI Behavior

N/A — no UI in this feature.

## 7. Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| Calendar API 4xx/5xx on push | Appointment succeeds; event id NULL; warning logged |
| freeBusy failure | Fail open: local availability only; warning logged |
| Busy event partially overlapping a slot | Slot excluded (any overlap blocks) |
| Cancel when event push originally failed (NULL id) | Skip calendar delete silently |
| All-day busy events | Treated as busy for the whole business day |
| Reschedule | Old event deleted, new one created; new id stored |
| Token expiry | Tokens cached with expiry; refreshed on demand |

## 8. Dependencies

- `specs/secretary-agent.md` booking service (service layer, reused by tools)
- New runtime deps: `PyJWT` + `cryptography` (RS256 service-account JWT signing); still no Google SDK
- Google Cloud: a service account with the Calendar API enabled, its JSON key, and the business calendar shared with the service-account email (editor role)

## 9. Infrastructure Prerequisites

| Category | Requirement |
|----------|-------------|
| Environment variables | `GOOGLE_SERVICE_ACCOUNT_FILE` (path to JSON key), `GOOGLE_CALENDAR_ID` (calendar to use). Both unset → feature disabled (AC-001) |
| Registry images | N/A |
| Cloud quotas | Google Calendar API default quota (ample for Alpha) |
| Network reachability | Outbound HTTPS to oauth2.googleapis.com and www.googleapis.com |
| CI status | CI green on main |
| External secrets | Service-account JSON key — gitignored path (e.g. `data/google-sa.json`), never committed (WL-001) |
| Database migrations | `appointments.calendar_event_id` — additive ALTER in `db._migrate` (same pattern as `confirmed_at`) |

**Verification before implementation:** unit tests mock httpx and the token exchange; live verification is a manual smoke with a real service account (optional at Alpha).

## 10. Out of Scope (deferred)

- Outlook/Microsoft Graph provider (M4, behind the same interface)
- Inbound edits: moving/deleting events on the calendar does not reschedule/cancel appointments (no push notifications/polling)
- Per-business calendars (M4 multi-tenant), attendee invites to customers, Google Meet links

## 11. Revision History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-11-21 | 0.1.0 | Andres + Claude | Initial spec; provider = Google first, scope = push + busy-block (human-decided) |
