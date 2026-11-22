# M3 Live Smoke Test — Checklist

Verifies the M3 success criterion live: *a real business runs on real
channels with its real calendar.* One-time account setup (~30 min), then the
test itself (~10 min). All config goes in `.env` (never `.env.example`).

## 0. Server + public URL (needed for inbound webhooks)

- [ ] `uvicorn app.main:app --reload` (http://localhost:8000)
- [ ] Tunnel it: `ngrok http 8000` (or `cloudflared tunnel --url http://localhost:8000`)
      → note the public HTTPS URL, call it `$TUNNEL`
- [ ] Leave `TWILIO_VALIDATE` unset for this test: signature validation checks
      the exact URL, and behind a tunnel/proxy `request.url` won't match what
      Twilio signed. Turn it on at AWS deploy time instead.

## 1. Twilio SMS

- [ ] Create account at twilio.com (free trial is fine)
- [ ] Trial caveats: SMS only to phone numbers you verify in the console, and
      messages carry a trial prefix — both fine for a smoke test
- [ ] Get your trial phone number (Phone Numbers → Manage → Active numbers)
- [ ] Console home → copy **Account SID** and **Auth Token**
- [ ] `.env`:
      ```
      TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
      TWILIO_AUTH_TOKEN=<auth token from console home>
      TWILIO_FROM_NUMBER=+1xxxxxxxxxx
      ```
- [ ] Point the number at the app: Active numbers → your number → Messaging
      Configuration → *A message comes in* → Webhook, POST, `$TUNNEL/webhooks/sms`
- [ ] Verify your personal cell (Phone Numbers → Verified Caller IDs)

**Test:** text the Twilio number "What are your hours?" → Secretary answers.
Then book an appointment entirely over SMS.

> **Result 2026-11-21:** Verified end-to-end up to carrier delivery. Inbound
> SMS → webhook → agent → TwiML reply all worked (two exchanges, 200 OK), but
> Twilio refused final delivery with **error 30034**: US carriers block SMS
> from local numbers without **A2P 10DLC registration** — even on trial, no
> bypass. The full conversational test runs on WhatsApp instead (section 2,
> same pipeline). Register 10DLC or a verified toll-free number at AWS deploy
> time (M4); both need business details and a multi-day review.

## 2. Twilio WhatsApp (real sender — sandbox was OFFLINE on this account)

> **Result 2026-11-21:** The sandbox never worked (sender status OFFLINE,
> every `join` failed) — registered the trial number as a **real WhatsApp
> sender** instead via Meta embedded signup: `whatsapp:+19086638552`,
> profile "Paulino AI Agents", status ONLINE. Live test: inbound WhatsApp →
> webhook → agent → API reply all verified; final delivery blocked by
> **error 63051** (Meta locks new WABAs until business verification
> completes — email pending). Retest delivery when Meta's email arrives.
> Webhook on the sender is set via API (`messaging.twilio.com/v2/Channels/
> Senders/{sid}`), not console.

- [x] Register number as WhatsApp sender (Meta embedded signup, SMS code)
- [x] `.env`: `TWILIO_WHATSAPP_FROM=whatsapp:+19086638552`
- [x] Sender webhook → `$TUNNEL/webhooks/sms`, POST
- [x] Meta business verification complete (~3h) → delivery works

> **PASSED 2026-11-22:** Full conversational test live on WhatsApp — Spanish
> detection ("¿Tienen cita mañana?" → correct "Sunday closed" + Monday slots),
> booking (appt #5, agent confirmed phone number with customer before using
> it), reminder routed to WhatsApp via preference routing (status: read),
> "Confirm" reply → confirmed_at set. Bonus finding: follow-up agent refused
> to send to an invalid number (old test data) instead of guessing — correct
> fail-safe. Gotcha log: quick tunnel died twice (Cloudflare drops them;
> webhooks re-pointed via API each time; death-watch monitor added), and a
> message sent during sender webhook UPDATING failed with 63007 — wait ~1 min
> after webhook changes.

**Test:** WhatsApp the sandbox "¿Tienen cita mañana?" → Secretary answers in
Spanish. Book one. Then trigger the reminder (`POST
localhost:8000/agents/followup/run?include_future=true`) → it should arrive
**on WhatsApp** (you last contacted via WhatsApp — preference routing). Reply
CONFIRM → appointment confirmed.

## 3. Google Calendar

- [ ] console.cloud.google.com → New project (e.g. `ai-agents-smoke`)
- [ ] APIs & Services → Library → enable **Google Calendar API**
- [ ] IAM & Admin → Service Accounts → Create (no roles needed) → Keys →
      Add key → JSON → save as `data/google-sa.json` (gitignored — verify with
      `git status`, it must NOT appear)
- [ ] Google Calendar (calendar.google.com) → your business calendar →
      Settings and sharing → *Share with specific people* → add the service
      account's email (`...@...iam.gserviceaccount.com`) with **Make changes
      to events**
- [ ] Same settings page → copy **Calendar ID**
- [ ] `.env`:
      ```
      GOOGLE_SERVICE_ACCOUNT_FILE=data/google-sa.json
      GOOGLE_CALENDAR_ID=<calendar id>
      BUSINESS_TIMEZONE=<your IANA tz, e.g. America/New_York>
      ```

**Test A (push):** book via any channel → event appears on the calendar
within seconds; cancel → event disappears.
**Test B (busy-block):** drop a manual event on the calendar tomorrow
10:00–11:00 → ask the Secretary for tomorrow's availability → no slot
overlapping 10:00–11:00 is offered.
**Test C (fail open):** temporarily rename `data/google-sa.json` → booking
still works, event id stays NULL, warning in server log.

> **PASSED 2026-11-22 (all three):** A — booking #8 created real event
> "Dental Cleaning & Exam — Smoke Test A" (Mon 12:00 ET, confirmed); cancel
> set the Google event to cancelled. B — manual 10:00–11:00 block appeared in
> freeBusy and no offered slot overlapped it. C — with a bogus key path:
> warning logged, busy failed open to [], booking succeeded with NULL event
> id. Note: the downloaded key was `ai-agents-smoke-*.json` (NOT gitignored) —
> renamed to `data/google-sa.json`; always rename SA keys to the gitignored
> name on download.

## Pass criteria (= M3 DONE)

- [x] SMS inbound → webhook → agent reply end-to-end (outbound delivery
      pending A2P 10DLC registration — carrier rule, not code; see §1)
- [x] WhatsApp conversation + booking + reminder on WhatsApp + CONFIRM
      (carried the full conversational test SMS couldn't finish — PASSED
      2026-11-22, appt #5)
- [x] Booking appears on the real calendar; busy time blocks availability
      (PASSED 2026-11-22; fail-open verified too)
- [x] Restart the server between tests — everything survives (4 restarts
      during the smoke run; appointments, prefs, confirmations all persisted)

When all boxes tick: run `/add:retro` to flip PRD M3 → DONE.
