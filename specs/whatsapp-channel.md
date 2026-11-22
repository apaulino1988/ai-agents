# Spec: whatsapp-channel (M3 — real channels)

**Version:** 0.1.0
**Created:** 2026-11-21
**PRD Reference:** docs/prd.md (M3: real-channels)
**Status:** Complete

## 1. Overview

Add WhatsApp as a second real messaging channel, reusing the Twilio channel
service built for SMS. Inbound: customers message the business on WhatsApp and
chat with the Secretary (book, ask questions, reply CONFIRM) exactly as over
SMS. Outbound: the Follow-up agent's reminders are delivered on the channel
the customer last used, with automatic SMS fallback when WhatsApp delivery is
rejected (e.g. the 24-hour session-window rule). Local development continues
to work with no Twilio account (outbox fallback).

### User Story

As a **customer who uses WhatsApp**, I want to message the business and
receive my reminders on WhatsApp, so that the conversation happens where I
already am — without the business needing to know or ask which app I use.

## 2. Acceptance Criteria

| ID | Criterion | Priority |
|----|-----------|----------|
| AC-001 | An inbound WhatsApp message (Twilio `From=whatsapp:+E164`) reaches the Secretary through the existing `/webhooks/sms` endpoint and gets a TwiML reply, with session continuity per phone | Must |
| AC-002 | `channels.send()` accepts a `channel` ("sms" \| "whatsapp"); WhatsApp sends use `whatsapp:`-prefixed From/To addresses against the same Twilio Messages API | Must |
| AC-003 | Each inbound message upserts the customer's preferred channel (`channel_prefs` by phone); Follow-up reminders are sent on that channel, defaulting to SMS when no preference exists | Must |
| AC-004 | A WhatsApp send rejected by Twilio (4xx — not a WhatsApp user, 24h window closed, template required) automatically falls back to SMS; the outbox records what actually happened | Must |
| AC-005 | Without Twilio credentials everything still works record-only: outbox channel `whatsapp-outbox` / `sms-outbox` | Must |
| AC-006 | Outbox `channel` values distinguish `whatsapp-twilio`, `whatsapp-outbox`, `sms-twilio`, `sms-outbox`, and fallback sends record the fallback reason | Should |
| AC-007 | Signature validation and CONFIRM flow work identically for WhatsApp inbound | Must |

## 3. User Test Cases

### TC-001: WhatsApp customer books an appointment

**Precondition:** Server running; Twilio sandbox joined from the customer's WhatsApp (or mocked webhook POST).
**Steps:**
1. Customer sends "Hi, do you have anything tomorrow morning?" to the business WhatsApp number.
2. Secretary replies with availability (TwiML).
3. Customer picks a slot and gives their name; Secretary books it.
**Expected Result:** Appointment created with the customer's phone (without the `whatsapp:` prefix); `channel_prefs` for that phone = whatsapp.
**Screenshot Checkpoint:** N/A (API-level; webhook response asserted in tests)
**Maps to:** TBD

### TC-002: Reminder arrives on WhatsApp with SMS fallback

**Precondition:** Customer from TC-001 has a booked appointment and a WhatsApp preference; Twilio creds set (mocked in tests).
**Steps:**
1. Follow-up agent runs its reminder task.
2. Channel service sends via WhatsApp.
3. (Variant) Twilio rejects with a 4xx window/template error.
**Expected Result:** Reminder delivered as `whatsapp-twilio`; in the variant, an SMS retry is sent and recorded as `sms-twilio` with fallback noted. Task is marked failed only if both channels fail.
**Screenshot Checkpoint:** N/A
**Maps to:** TBD

### TC-003: Web-chat customer defaults to SMS

**Precondition:** Appointment booked via web chat; the phone has no `channel_prefs` row.
**Steps:**
1. Follow-up agent sends the reminder.
**Expected Result:** Sent via SMS (`sms-twilio`, or `sms-outbox` without creds).
**Maps to:** TBD

## 4. Data Model

### channel_prefs (new table, migration-safe CREATE IF NOT EXISTS)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| phone | TEXT PRIMARY KEY | Yes | E.164, normalized without any `whatsapp:` prefix |
| preferred_channel | TEXT | Yes | `sms` or `whatsapp`; set from the customer's last inbound message |
| last_contact_at | TEXT | Yes | ISO timestamp of last inbound message (basis for the 24h window, future use) |

### outbox (existing — semantics extended)

`channel` gains values `whatsapp-twilio` / `whatsapp-outbox`; fallback sends
append a short reason (e.g. `sms-twilio (fallback: whatsapp 63016)`).

### Relationships

`channel_prefs.phone` matches `appointments.customer_phone` (no FK; phones are
the natural join key throughout the app).

## 5. API Contract

No new endpoints. `POST /webhooks/sms` (existing) now also receives WhatsApp
traffic: Twilio sends `From=whatsapp:+1555...`; the handler strips the prefix
for phone/session purposes, records the preference, and includes
`[Channel: WhatsApp ...]` context for the Secretary. Reply remains TwiML.

## 6. UI Behavior

N/A — no UI in this feature.

## 7. Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| WhatsApp send rejected (24h window / not a WhatsApp user / any 4xx) | Fall back to SMS automatically; record both attempts' outcome in outbox |
| Both WhatsApp and SMS fail | `ChannelError` raised → follow-up task marked failed (existing behavior) |
| Customer switches channels (texts SMS after using WhatsApp) | Preference updates to the most recent inbound channel |
| `whatsapp:` prefix leaking into stored phones | Normalize at the webhook boundary; all storage and lookups use bare E.164 |
| CONFIRM sent via WhatsApp | Works identically — same Secretary tool, phone matched after normalization |
| No Twilio creds | `whatsapp-outbox` record-only; no fallback chain triggered |

## 8. Dependencies

- `specs/sms-channel.md` (Complete) — channel service, webhook, CONFIRM flow, signature validation
- Twilio WhatsApp sandbox for live dev testing (production requires a WhatsApp-enabled sender)

## 9. Infrastructure Prerequisites

| Category | Requirement |
|----------|-------------|
| Environment variables | Existing `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`; new optional `TWILIO_WHATSAPP_FROM` (sandbox/sender number; WhatsApp sends disabled without it, falling back to SMS) |
| Registry images | N/A |
| Cloud quotas | N/A |
| Network reachability | Outbound HTTPS to api.twilio.com (same as SMS) |
| CI status | CI green on main (established 2026-11-21) |
| External secrets | Twilio sandbox: join code for test WhatsApp numbers |
| Database migrations | `channel_prefs` table — CREATE IF NOT EXISTS in `init_db` (same pattern as `confirmed_at`) |

**Verification before implementation:** unit tests mock httpx (no live creds needed); live smoke via Twilio sandbox is optional and manual.

## 10. Out of Scope (deferred)

- Approved message templates / Content SIDs (Beta — needed for compliant out-of-window business-initiated WhatsApp at scale)
- Inbound media (MMS/images), delivery-status callbacks, per-business numbers (M4 multi-tenant)

## 11. Revision History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-11-21 | 0.1.0 | Andres + Claude | Initial spec; routing = last-used channel, 24h handling = freeform + SMS fallback (human-decided) |
