# Session Handoff — ai-agents

**Written:** 2026-11-22 (cycle-3 planning + execution session, late evening)
**Branch:** main @ `fd502de` (pushed; CI was pending at session end — check it)

## State

- **Cycle 3 EXECUTED in one session:** multi-tenant foundation shipped.
  - Spec `specs/multi-tenant.md` v0.2.0 Approved by Andres (AnswerQuestions:
    default-slug fallback YES, admin API IN, profiles in DB) → Complete.
  - Full TDD: RED (21 new tests, snapshot committed 9e24e98) → GREEN (80/80)
    → REFACTOR (db.connect now a closing contextmanager — killed 414
    unclosed-connection warnings) → VERIFY (ruff clean, 85% coverage).
  - Shipped in fd502de: businesses table (profile JSON in DB), business_id on
    all tenant tables, in-place legacy migration (original deployment =
    tenant 1), webhook To-number routing + polite decline, chat slug routing,
    admin API (ADMIN_TOKEN bearer, hidden when unset), tenant ContextVar
    bridge (L-017), default-tenant env fallbacks (L-018).
- **Meta business verification: likely cleared** (sender ONLINE, quality
  HIGH, 250 customers/24hr — was err 63051). Confirm with next live delivery
  (L-016: Senders API check technique).
- Cycle plan `.add/cycles/cycle-3.md` status EXECUTED; run
  `/add:cycle --complete` after Andres reviews the diff (alpha asks for a
  human skim — he was mostly away during execution).
- Uncommitted: spec status flip, cycle-3.md status, observations, L-016..018,
  this handoff (ride the next commit).

## Next up

1. Andres: skim fd502de (especially app/services/tenants.py, app/main.py
   webhook routing) and confirm CI green → `/add:cycle --complete`.
2. Next cycle candidates (M4): aws-deploy (KEEP CHEAP — Andres: App Runner +
   smallest RDS or defer RDS; also closes a beta-promotion gap),
   a2p-registration (long external waits — start early),
   business-dashboard (BLOCKED on /add:ux first — alpha UI gate).
3. Live smoke idea for multi-tenant: create a 2nd test business via admin
   API, point a spare number at it (needs a 2nd Twilio number — defer).

## Decisions / gotchas

- ADMIN_TOKEN env var now gates the admin API (unset = endpoints 404).
  Add a strong value to `.env` before using it live; never commit it.
- Live DB migrates automatically on next app start (seeds tenant 1 from
  data/business.json + env). data/business.json is now a SEED only —
  runtime profile edits go through the admin API / DB.
- channel_prefs was rebuilt with PK (business_id, phone) — migration is
  idempotent (tested), but take a backup copy of secretary.db before first
  prod start anyway.
- Tunnel URL rotates on restart (docs/smoke-test.md routine).
- Secrets drift risk: always `git status` + scan before commits.
- Write this handoff at every session end.
