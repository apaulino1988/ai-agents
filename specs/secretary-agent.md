# Spec: secretary-agent (M1 MVP)

**Status:** In progress · **Maturity:** POC · **Created:** 2026-11-20

## Goal
A Claude-powered AI Secretary that handles a small business's front office over web chat: answers questions about services, hours, pricing/quotes, and books/reschedules/cancels appointments — end-to-end, with zero human intervention.

## User stories
- As a **customer**, I can ask what services the business offers, what they cost, and when it's open, and get accurate answers.
- As a **customer**, I can book an appointment: the agent checks availability, collects my name and phone, and confirms a slot.
- As a **customer**, I can find, reschedule, or cancel my existing appointment by phone number.
- As a **business owner**, I configure my business once in `data/business.json` (services, prices, hours, policies) and the agent answers from it.
- As a **business owner**, every conversation is logged so I can review accuracy.

## Behavior requirements
1. Agent answers business-info questions from the configured profile only — it must not invent services, prices, or hours.
2. Booking flow: check availability → collect name + phone → book → confirm with appointment ID. No double-booking (single-provider calendar, non-overlapping slots).
3. Appointments respect business hours and service duration; 30-minute slot grid.
4. If the agent can't help, it says so and offers the business phone number (graceful escalation).
5. Conversations are multi-turn with state held per session.

## Architecture
- **Backend:** FastAPI (`app/`), SQLite via stdlib `sqlite3` (`secretary.db`).
- **AI:** Anthropic Python SDK, model `claude-opus-5`, manual tool-use loop; business profile in a cached system prompt; booking operations exposed as tools (`check_availability`, `book_appointment`, `cancel_appointment`, `reschedule_appointment`, `find_appointments`).
- **Frontend:** single static chat page (`static/index.html`) served by FastAPI — the React widget is a later feature.
- **Reusability constraint (M2):** booking + knowledge live in `app/services/` as plain Python, independent of the agent, so future agents (Follow-up) share them.

## Test cases
- Availability excludes booked slots, closed days, and slots that would run past closing.
- Booking a taken slot fails with a clear error; cancel frees the slot; reschedule moves it.
- Knowledge profile loads; service/price lookups correct; system prompt contains hours and prices.
- API smoke: app starts, serves the chat page and health endpoint (agent calls not tested without API key).

## Out of scope (per PRD)
Multi-agent handoffs, SMS/WhatsApp, external calendars, multi-language, multi-tenant dashboard, auth.
