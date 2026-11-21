# Session Handoff — ai-agents

**Written:** 2026-11-21 (post whatsapp-channel TDD cycle)
**Branch:** main @ `4944ea4` (pushed, CI green)

## State

- **M3 sms-channel: COMPLETE** (96f6b8b). Twilio SMS both directions, outbox
  fallback, signature validation, CONFIRM flow, ES/EN.
- **M3 whatsapp-channel: COMPLETE** (4944ea4). Inbound WhatsApp via the same
  webhook (normalized `whatsapp:` addresses), outbound reminders route by
  last-used channel (`channel_prefs`, SMS default), WhatsApp rejections fall
  back to SMS with reason recorded. First strict RED→GREEN cycle (red commit
  2df05a0) and first formal /add:verify run; coverage measured at **80%**.
- 48/48 tests, ruff clean, CI green. Uncommitted: spec status flip to
  Complete, L-009 learning, this handoff (commit with next deploy).

## Next up (M3 remainder)

- **External calendars (Google/Outlook)** — the last M3 roadmap item.
- Twilio sandbox live smoke test for WhatsApp (manual, optional).
- Toward Beta: coverage now measured (80% > 50% ✓); still needed: mypy
  installed, PR workflow, second environment (AWS).

## Decisions / gotchas

- Reminder routing = customer's last inbound channel; SMS default (human-decided).
- 24h WhatsApp window: freeform + automatic SMS fallback; templates deferred to Beta.
- `TWILIO_WHATSAPP_FROM` enables WhatsApp sends; without it they go via SMS.
- ADD plugin cache lacks scripts/check-test-count.py (L-009) — RED/GREEN
  snapshots in .add/cycles/cycle-1/ are manual (pytest --collect-only).
- Write this handoff at every session end.
