# Cycle 3 — Multi-Tenant Foundation

**Milestone:** M4 — onboarding
**Maturity:** alpha
**Status:** EXECUTED (pending Andres's review sign-off for --complete)
**Started:** 2026-11-22
**Completed:** 2026-11-22 (implementation + verify; same session as planning)
**Duration Budget:** ~3 days (owner mostly away — conservative scope, high autonomy)

## Work Items

| Feature | Current Pos | Target Pos | Assigned | Est. Effort | Validation |
|---------|-------------|-----------|----------|-------------|------------|
| multi-tenant | NOT_SHAPED | IN_PROGRESS | Claude (primary) | ~1 day spec + ~1-2 days TDD | Spec approved async by Andres; all acceptance criteria passing in tests; existing 59-test suite stays green |

## Dependencies & Serialization

Single feature, single thread. Internally serialized:

```
spec draft (specs/multi-tenant.md)
    ↓ (async approval by Andres — blocker gate)
TDD cycle: tenant model + data isolation (RED → GREEN → REFACTOR)
    ↓
migrate existing single-tenant data to default tenant
    ↓
verify: full suite green, channel webhooks resolve tenant correctly
```

multi-tenant is the foundation for every other M4 feature
(business-dashboard, self-serve-onboarding, aws-deploy config,
a2p-registration per-business). Nothing else starts this cycle.

## Parallel Strategy

Single-threaded execution (alpha, wip_limit=1). Features advance sequentially.

## Validation Criteria

### Per-Item Validation
- multi-tenant:
  - Spec at `specs/multi-tenant.md` approved by Andres (async OK)
  - Tenant/business entity with per-business isolation of: knowledge base,
    appointments, conversations, channel identities (Twilio numbers / WhatsApp
    senders map to a tenant), calendar credentials
  - Existing single-tenant data migrates cleanly to a default tenant
  - Inbound webhook routing resolves tenant from the receiving number/sender
  - No cross-tenant data leakage (explicit tests)
  - All new code TDD (strict RED → GREEN, snapshots in .add/cycles/cycle-3/)

### Cycle Success Criteria
- [ ] multi-tenant reaches IN_PROGRESS (spec approved, implementation underway or done)
- [ ] All acceptance criteria verified by tests
- [ ] Code review completed (self-review via /add:reviewer; Andres skim on return)
- [ ] No regressions — 59/59 pre-existing tests still green, coverage ≥ 82%

## Agent Autonomy & Checkpoints

Alpha + owner mostly away → high autonomy:
- Claude drafts the spec and proceeds to TDD only after Andres approves it
  (spec approval is the one hard checkpoint).
- Risky/irreversible decisions deferred: no schema choices that block the
  SQLite → PostgreSQL move (M4 aws-deploy), no changes to live Twilio/Meta
  webhook config beyond the existing tunnel-rotation routine.
- Blockers flagged async in `.add/handoff.md`; batch questions for check-ins.

## Notes

- **Meta business verification: likely cleared** (checked 2026-11-22):
  sender whatsapp:+19086638552 is ONLINE, quality HIGH, messaging limit
  250 customers/24hr (was Unavailable while err 63051 pending). Confirm with
  the next real delivery; no config change needed this cycle.
- **AWS budget constraint (Andres, 2026-11-22):** when aws-deploy is planned
  (future cycle), keep it minimal/cheap — e.g., App Runner + smallest RDS, or
  defer RDS. Multi-tenant schema design this cycle should not assume
  expensive infra.
- **Known deferred:** A2P 10DLC registration (US SMS delivery), Outlook
  calendar provider, business-dashboard UX (`/add:ux` required before that
  feature enters a cycle — alpha UI gate).
- Beta promotion gaps tracked: PR workflow on protected main, 2nd environment
  (aws-deploy), mypy. Not in this cycle's scope.
