# Session Handoff — ai-agents

**Written:** 2026-11-21 (live smoke test session, evening)
**Branch:** main @ `f559f73` (pushed, CI green)

## Live smoke status (2026-11-21 evening)

- **SMS:** inbound → webhook → agent → reply verified live; final delivery
  blocked by err 30034 (A2P 10DLC registration — defer to M4/AWS).
- **WhatsApp:** sandbox was OFFLINE (joins always failed). Registered the
  trial number as a REAL sender via Meta embedded signup:
  `whatsapp:+19086638552` "Paulino AI Agents", sender ONLINE, webhook set via
  Senders API. Inbound → webhook → agent → API reply verified live; delivery
  blocked by err 63051 (Meta business verification pending — email awaited).
  Hourly auto-retest cron running in session.
- **Google Calendar:** ✅ PASSED 2026-11-22 — push (A), busy-block (B),
  fail-open (C) all verified against the real calendar
  (owner's Gmail calendar, America/New_York; SA key at data/google-sa.json).
- **WhatsApp:** ✅ PASSED 2026-11-22 — full conversational loop live
  (Spanish, booking #5, reminder via preference routing, CONFIRM).
- **M3 LIVE SMOKE: ALL PASS CRITERIA MET.** Retro run 2026-11-22: PRD M3 →
  DONE, M4 (onboarding) now current milestone; L-011..L-014 recorded, all
  promoted to library (WL-006..WL-009). Remaining: commit the pending files
  via /add:deploy (smoke-test.md, .gitignore, prd, config, handoff,
  learnings, retro, observations, whatsapp spec).
- Tunnel URL rotates on restart: currently
  `https://softball-seat-cameron-courtesy.trycloudflare.com` — SMS number
  webhook updated via API on each rotation; WhatsApp sender webhook too.
- Twilio creds in `.env` only (were briefly pasted into docs/smoke-test.md —
  scrubbed before any commit). TWILIO_FROM_NUMBER=+19086638552.
- User decision: finish M3 before starting M4 or any new agent.

## State

- **M3 roadmap is CODE-COMPLETE.** All three items shipped today:
  - sms-channel (96f6b8b) — Twilio SMS both directions, CONFIRM, ES/EN
  - whatsapp-channel (4944ea4) — same webhook, preference routing, SMS fallback
  - calendar-sync (f559f73) — Google Calendar push + busy-block, service-account
    auth, fail-open; provider interface ready for Outlook (M4)
- 59/59 tests, 82% coverage, ruff clean, CI green. Strict RED→GREEN on both
  cycles today (snapshots in .add/cycles/cycle-1 and cycle-2).
- Uncommitted: L-010 learning + this handoff (ride the next commit).

## M3 milestone close-out (pending)

- PRD still says M3 "NOW": its success criterion is "a real business runs on
  real channels with its real calendar" — code is done, but LIVE verification
  needs human setup: Twilio number + WhatsApp sandbox join, Google service
  account + calendar share (see .env.example). Flip PRD M3 → DONE at the next
  retro once live smoke passes.
- Beta promotion checklist: coverage 82% ✓ measured; still missing: mypy
  installed, PR workflow on protected main, second environment (AWS).

## Next up

- Live smoke test of all three M3 integrations (human-assisted).
- Then M4: onboarding — multi-tenant, business dashboard, AWS deploy.

## Decisions / gotchas

- Calendar: Google-first behind provider interface; push + busy-block; fail
  open everywhere (calendar never blocks a customer). Human-decided.
- zoneinfo on Windows requires the tzdata pip package (L-010).
- ADD plugin cache lacks check-test-count.py (L-009) — snapshots are manual.
- Write this handoff at every session end.
