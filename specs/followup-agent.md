# Spec: followup-agent (M2 — agent teamwork)

**Status:** In progress · **Maturity:** POC · **Created:** 2026-11-21

## Goal
Prove agents collaborate as a team: the Secretary agent delegates work to a
Follow-up agent through a handoff protocol, and the Follow-up agent completes
it independently — the M2 success criterion.

## The handoff protocol
- Shared **agent task queue** (`agent_tasks` table): `{from_agent, to_agent,
  task_type, payload, due_at, status: pending|done|failed, result}`.
- The **Secretary decides to delegate**: a new `schedule_followup` tool creates
  a task for the Follow-up agent after a successful booking or reschedule.
  Delegation is the agent's choice (prompted behavior), not hardcoded in the
  booking service.
- The **Follow-up agent** is a separate Claude agent (own system prompt, own
  tools: `get_appointment`, `send_message`). It processes due tasks: composes a
  personalized confirmation reminder and sends it.
- **Channel:** reminders land in an `outbox` table (the M3 SMS/WhatsApp channel
  stand-in). Reviewable via `GET /outbox`.

## Behavior requirements
1. After booking, the Secretary schedules a follow-up confirmation due 24h
   before the appointment (immediately if booked <24h ahead).
2. The Follow-up agent's reminder includes service, date, time, location, and
   asks the customer to confirm or call to reschedule. Friendly, SMS-length.
3. Tasks are processed by `POST /agents/followup/run` (processes due tasks;
   `include_future=true` processes everything — for demos and cron later).
4. A failed task is marked `failed` with the error; it never blocks others.
5. Agents never expose internal mechanics to the customer beyond "you'll get a
   reminder."

## Interfaces
- `POST /agents/followup/run?include_future=` → `{processed, results[]}`
- `GET /agents/tasks` → task queue contents
- `GET /outbox` → outbound messages

## Test cases
- Task service: create, due-filtering (future vs now), complete, fail.
- `schedule_followup` tool creates a task with due_at = appointment − 24h.
- Outbox: record + list.
- API: endpoints respond; run with empty queue processes 0.
- Live (manual): book via chat → task appears → run → reminder in outbox.

## Out of scope
Real SMS delivery (M3), inbound replies (M3), recurring reminder schedules,
cron scheduling (run endpoint is the trigger for now).
