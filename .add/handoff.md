# Session Handoff — ai-agents

**Written:** 2026-11-22 (cycle-3 planning session, evening)
**Branch:** main @ `4c86e37` (pushed, clean tree before this session's files)

## State

- **M3 fully closed:** committed, pushed, CI green, repo public. M4
  (onboarding) is the active milestone.
- **Cycle 3 planned** (`.add/cycles/cycle-3.md`): multi-tenant foundation
  ONLY. Owner mostly away → high autonomy, spec approval is the one hard
  checkpoint. Config `planning.current_cycle` = cycle-3.
- **Spec drafted, AWAITING APPROVAL:** `specs/multi-tenant.md` (Status:
  Draft). Three open questions for Andres in §11 (default-slug fallback,
  admin API in/out, profile in DB vs files). Do NOT start TDD until Andres
  approves the spec.
- **Meta business verification: likely cleared.** Senders API (2026-11-22):
  whatsapp:+19086638552 ONLINE, quality HIGH, messaging limit 250
  customers/24hr (was Unavailable under err 63051). Confirm with next real
  delivery. L-016 records the check technique.
- Uncommitted: cycle-3.md, specs/multi-tenant.md, config.json,
  observations.md, learnings (L-016), this handoff — commit via /add:deploy
  after spec approval or at next session end.

## Next up

1. Andres reviews/approves `specs/multi-tenant.md` (answer §11 questions).
2. Then `/add:tdd-cycle specs/multi-tenant.md` (strict RED→GREEN, snapshots
   to `.add/cycles/cycle-3/`).
3. After multi-tenant: next cycle candidates — aws-deploy (KEEP CHEAP:
   Andres flagged budget; App Runner + smallest RDS or defer RDS),
   a2p-registration (long external waits — start early), business-dashboard
   (BLOCKED on /add:ux first, alpha UI gate).

## Decisions / gotchas

- Cycle-3 decisions (Andres, 2026-11-22): multi-tenant only; mostly away;
  AWS must stay cheap when planned.
- Schema must stay PostgreSQL-portable (AC-009) — don't block the PG move.
- Tunnel URL rotates on restart (see docs/smoke-test.md routine); webhooks
  re-pointed via Twilio API each rotation; TWILIO_VALIDATE stays unset
  behind tunnel.
- Secrets drift risk: always `git status` + inspect before commits (3 past
  near-misses).
- Write this handoff at every session end.
