# Implementation Plan: multi-tenant

**Spec:** specs/multi-tenant.md v0.2.0 (Approved)
**Cycle:** cycle-3
**Created:** 2026-11-22

## Approach

Thread tenancy through the stack with the smallest possible surface change:

1. **Service layer takes explicit `business_id: int = 1` parameters.**
   Default `1` = the migrated original business, so every existing call site
   and all 59 existing tests remain valid without modification.
2. **Request layer resolves the tenant once** (webhook `To` number, chat
   `business` slug) and bridges it to the agent/tool layer via a
   `ContextVar` (`app/tenant.py`) — `agent.run_turn(history, msg)` keeps its
   2-arg signature, so existing monkeypatched tests keep working.
3. **Profiles move file → DB.** `businesses.profile` JSON column;
   `db.connect()` seeds business id=1 from `data/business.json` + env vars
   when the table is empty. `knowledge.*` reads from the DB per tenant.
4. **Default-tenant env fallback.** For business 1 only, `TWILIO_FROM_NUMBER`,
   `TWILIO_WHATSAPP_FROM`, `GOOGLE_CALENDAR_ID`, `BUSINESS_TIMEZONE` still
   work as overrides (keeps existing tests and the live deployment working).
   Other tenants use only their row values — no cross-tenant leakage.

## Steps

| # | Step | Files |
|---|------|-------|
| 1 | Schema: `businesses` table; `business_id` columns (DEFAULT 1) on appointments, conversation_log, agent_tasks, channel_prefs, outbox; channel_prefs rebuilt with PK (business_id, phone); seed default business | app/db.py |
| 2 | Tenants service: get/create/update/list, get_by_slug, get_by_number (twilio_number OR whatsapp_sender), default-business helpers | app/services/tenants.py (new) |
| 3 | Knowledge from DB per tenant (business_id params; drop file lru_cache; keep business_file() for seeding) | app/services/knowledge.py |
| 4 | Booking per tenant (filter + insert business_id; availability uses tenant hours/services/calendar) | app/services/booking.py |
| 5 | Calendar per tenant (calendar_id/timezone from row; env fallback for business 1; shared platform SA) | app/services/calendar.py |
| 6 | Channels per tenant (From numbers from row w/ default fallback; prefs keyed (business_id, phone)); outbox rows carry business_id | app/services/channels.py, outbox.py |
| 7 | Tasks per tenant (business_id on rows; schedule_confirmation scoped) | app/services/tasks.py |
| 8 | Tenant ContextVar bridge; agents read it for prompts/tools; followup uses task.business_id | app/tenant.py (new), app/agent.py, app/tools.py, app/followup_agent.py |
| 9 | API: webhook To-routing (+ polite decline for unknown), /chat slug, admin CRUD endpoints (ADMIN_TOKEN) | app/main.py |
| 10 | conftest: autouse temp-DB fixture (safety; no test bodies change) | tests/unit/conftest.py |

## Test Strategy

New `tests/unit/test_multi_tenant.py`, `test_AC_NNN_*` naming, one or more
tests per AC-001…AC-009. Existing 59 tests must stay green untouched
(AC-003). Agent LLM calls are always monkeypatched.

## Risks

- channel_prefs PK rebuild: table-copy migration must be idempotent.
- Seeding on every connect: must be a cheap existence check.
- PG portability (AC-009): plain INTEGER/TEXT only in new DDL.
