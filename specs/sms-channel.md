# Spec: sms-channel (M3 — real channels)

**Status:** Complete · **Maturity:** Alpha · **Created:** 2026-11-21

## Goal
Replace the outbox stand-in with a real SMS channel (Twilio) in both
directions: the Follow-up agent's reminders are delivered as real SMS, and
customers can text the business — chat with the Secretary, book, and reply
CONFIRM to reminders — entirely over SMS.

## User stories
- As a **customer**, I receive my appointment reminder as a real text message.
- As a **customer**, I can reply CONFIRM and my appointment is marked confirmed.
- As a **customer**, I can text the business to ask questions or book — same
  Secretary, new channel.
- As a **Spanish-speaking customer**, the agents reply in my language.
- As a **developer**, everything still works without Twilio credentials
  (messages fall back to the outbox) so local dev needs no account.

## Design

### Outbound — channel service (`app/services/channels.py`)
- `send(to_phone, body, ...)`: if `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` +
  `TWILIO_FROM_NUMBER` are set, deliver via the Twilio REST API (direct httpx
  call — no SDK dependency); otherwise record-only.
- Every message is recorded in `outbox` either way; `channel` field says what
  happened: `sms-twilio` (delivered) or `sms-outbox` (recorded only).
- Twilio HTTP errors raise `ChannelError` → the Follow-up task is marked
  failed, never silently lost.
- The Follow-up agent's `send_message` tool now routes through this service.

### Inbound — webhook (`POST /webhooks/sms`)
- Twilio posts form-encoded `From`/`Body`. Reply is TwiML
  (`<Response><Message>…</Message></Response>`, XML-escaped).
- Conversation state keyed by phone (`session_id = sms:{phone}`) so SMS
  threads are continuous, like web sessions.
- The message is passed to the Secretary with channel context
  (`[Channel: SMS. Customer phone: …]`) so it never has to ask for the number.
- **Signature validation**: HMAC-SHA1 per Twilio's scheme
  (base64(HMAC-SHA1(auth_token, url + sorted(k+v)))), enforced when
  `TWILIO_VALIDATE=true`. Off by default for local development.

### Confirmation flow
- `appointments.confirmed_at` column (migration-safe ALTER for existing DBs).
- New `confirm_appointment` service + Secretary tool: when a customer replies
  CONFIRM, the Secretary finds their upcoming appointment by phone and
  confirms it.

### Language
- Secretary and Follow-up prompts: reply in the customer's language
  (ES/EN first-class).

## Test cases
- Channel: no creds → outbox-only record; creds set (mocked httpx) → Twilio
  called with correct URL/payload, channel `sms-twilio`; Twilio 4xx →
  `ChannelError`.
- Signature validation: valid signature accepted, tampered rejected.
- Webhook: valid POST returns TwiML with the agent reply (agent mocked);
  missing From/Body → 400; validation on + bad signature → 403.
- Confirm: booked → confirmed (`confirmed_at` set); cancelled → error;
  Secretary tool dispatch works.

## Out of scope
WhatsApp (same Twilio API, follow-up feature), external calendars, inbound
MMS, delivery-status callbacks, per-business Twilio numbers (multi-tenant is
M4).
