# Spec: multi-tenant (M4 — onboarding)

**Version:** 0.2.0
**Created:** 2026-11-22
**PRD Reference:** docs/prd.md (M4: onboarding)
**Status:** Approved (Andres, 2026-11-22)

## 1. Overview

Turn the single-business app into a multi-tenant platform: every business
(tenant) gets its own knowledge profile, appointments, conversations, channel
identities, and calendar credentials — fully isolated from every other
tenant. This is the foundation for M4's dashboard, self-serve onboarding,
and AWS deployment; none of those can start until data is tenant-scoped.

The current deployment (one business, `data/business.json`, one Twilio
number) becomes tenant #1 via automatic migration — zero behavior change for
the live smoke setup.

### User Story

As a **platform operator**, I want each business's data and channels fully
isolated per tenant, so that onboarding a second business never risks
leaking bookings, conversations, or messages across businesses.

## 2. Acceptance Criteria

| ID | Criterion | Priority |
|----|-----------|----------|
| AC-001 | A `businesses` table holds per-tenant identity: id, slug, name, profile (JSON — same shape as business.json), timezone, twilio_number, whatsapp_sender, calendar_id, status | Must |
| AC-002 | All tenant-owned tables (`appointments`, `conversation_log`, `agent_tasks`, `channel_prefs`, `outbox`) carry `business_id`; every query in services filters by it | Must |
| AC-003 | Existing databases migrate additively: a default business (id=1) is created from `data/business.json` and all pre-existing rows are backfilled to it; 59 existing tests stay green | Must |
| AC-004 | Inbound Twilio webhooks resolve the tenant from the `To` number (SMS) / `To` sender (WhatsApp); unknown destination numbers get a polite TwiML decline and a logged warning | Must |
| AC-005 | Web chat resolves the tenant from a `business` slug (query param / request field); missing or unknown slug falls back to the default business (POC-compat) | Must |
| AC-006 | Knowledge, booking, calendar, and follow-up services all operate per-tenant (profile, availability, calendar push, reminders); no module reads the global `data/business.json` directly anymore | Must |
| AC-007 | Cross-tenant isolation is proven by tests: two seeded businesses, same customer phone in both, bookings/preferences/reminders never cross | Must |
| AC-008 | Minimal admin API to create/update a business (bearer token via `ADMIN_TOKEN` env var); full CRUD UI deferred to business-dashboard | Must |
| AC-009 | Schema stays PostgreSQL-portable (no SQLite-only types; plain INTEGER/TEXT; JSON stored as TEXT) | Must |

## 3. User Test Cases

### TC-001: Two businesses, same customer, no leakage

**Precondition:** Businesses A and B seeded with different services/hours; customer phone +1555… exists in both.
**Steps:**
1. Customer books with A via A's webhook number; books with B via web chat slug.
2. Ask A's Secretary "what are my appointments?"; run B's Follow-up reminders.
**Expected Result:** A sees only A's booking; B's reminder references only B's appointment and goes out branded/configured per B.
**Maps to:** AC-002, AC-004, AC-005, AC-007

### TC-002: Existing deployment upgrades in place

**Precondition:** A pre-multi-tenant `secretary.db` with real bookings; `data/business.json` present.
**Steps:**
1. Start the app (connect triggers migration).
**Expected Result:** Default business id=1 created from business.json; all rows backfilled; webhook and chat behave exactly as before.
**Maps to:** AC-003

### TC-003: Unknown inbound number

**Steps:** POST a Twilio webhook with a `To` number no business owns.
**Expected Result:** Polite TwiML reply ("number not in service"), warning logged, nothing persisted to any tenant.
**Maps to:** AC-004

## 4. Data Model

### businesses (new)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | INTEGER PRIMARY KEY | Yes | Tenant key, used in all FK columns |
| slug | TEXT UNIQUE | Yes | URL-safe identifier for web chat / future dashboard |
| name | TEXT | Yes | Display name |
| profile | TEXT (JSON) | Yes | Same shape as data/business.json (services, hours, pricing, policies) |
| timezone | TEXT | Yes | IANA tz (e.g. America/New_York) |
| twilio_number | TEXT | No | E.164; inbound SMS routing key + outbound From |
| whatsapp_sender | TEXT | No | E.164 (stored bare, no prefix); WhatsApp routing key |
| calendar_id | TEXT | No | Google Calendar id; NULL = calendar sync off for tenant |
| status | TEXT | Yes | active \| suspended (suspended tenants decline politely) |
| created_at | TEXT | Yes | ISO timestamp |

### Existing tables — additive `business_id INTEGER NOT NULL DEFAULT 1`

`appointments`, `conversation_log`, `agent_tasks`, `channel_prefs`, `outbox`.
`channel_prefs` uniqueness becomes `(business_id, phone)` (new composite
unique index; old PK retired via table rebuild if needed — SQLite-safe,
PG-portable).

### Migration

Additive, same `_migrate` pattern as `confirmed_at`: CREATE businesses IF NOT
EXISTS; if empty, seed id=1 from `data/business.json` +
`TWILIO_FROM_NUMBER`/`TWILIO_WHATSAPP_FROM`/`GOOGLE_CALENDAR_ID` env; ALTER
ADD `business_id` columns (default 1 backfills existing rows).

## 5. API Contract

- `POST /chat` — accepts optional `business` slug (body field); default slug when omitted.
- `POST /webhooks/sms` — unchanged URL; handler resolves tenant from `To`.
- `POST /admin/businesses`, `PUT /admin/businesses/{slug}` — create/update tenant (AC-008); `Authorization: Bearer $ADMIN_TOKEN`; 404s when token unset.
- Per-tenant Google SA: single platform service account (current key) shared across tenants; each tenant shares their calendar with it — no per-tenant key storage this cycle.

## 6. UI Behavior

No new UI. Chat widget gains an optional `data-business` attribute → slug
sent with each message (single HTML attribute, not a UI feature; dashboard
and onboarding UIs are separate M4 features gated on /add:ux).

## 7. Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| Webhook `To` matches no business | Polite decline TwiML + warning log; nothing stored (TC-003) |
| Two businesses claim the same twilio_number | Rejected at create/update time (unique index) |
| Suspended business receives a message | Polite "currently unavailable" reply; logged |
| Same phone, prefs differ per business | `(business_id, phone)` scoping: WhatsApp with A, SMS with B |
| Tenant without calendar_id | Calendar sync skipped (existing fail-open semantics) |
| Tenant without twilio_number sends reminders | Outbox record-only fallback (existing behavior, per tenant) |
| `lru_cache` on knowledge profile | Cache keyed per business_id (or dropped — profiles now come from DB) |

## 8. Dependencies

- All M1–M3 specs (Complete). No external/new services.
- Does NOT depend on aws-deploy; schema must stay PG-portable for it (AC-009).

## 9. Infrastructure Prerequisites

| Category | Requirement |
|----------|-------------|
| Environment variables | New: `ADMIN_TOKEN` (optional; admin API disabled without it). Existing Twilio/Google vars become the default tenant's seed values |
| Database migrations | Additive (businesses table + business_id columns), auto-run in `connect()` |
| CI status | Green on main (f559f73 lineage) |

**Verification before implementation:** none external — pure refactor + schema work, mocked tests.

## 10. Out of Scope (deferred)

- Business dashboard UI, self-serve signup (separate M4 features)
- Per-tenant Twilio subaccounts / number purchase, per-tenant A2P 10DLC
- Per-tenant Google service accounts or OAuth
- PostgreSQL cutover itself (aws-deploy); this spec only keeps the schema portable
- Billing/plans

## 11. Resolved Questions (Andres, 2026-11-22)

1. **Default web-chat fallback (AC-005):** missing slug maps to tenant #1 (demo page keeps working).
2. **Admin API (AC-008):** IN scope this cycle (promoted to Must — also needed to seed isolation tests).
3. **Profile storage:** in the database (JSON column on businesses) — no local file state, AWS-ready.

## 12. Revision History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-11-22 | 0.1.0 | Claude (draft for async approval) | Initial draft per cycle-3 plan |
| 2026-11-22 | 0.2.0 | Andres + Claude | Approved; §11 resolved (default-slug fallback YES, admin API IN/Must, profiles in DB) |
