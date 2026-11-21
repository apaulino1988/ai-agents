# ai-agents — Product Requirements Document

**Version:** 0.1.0
**Created:** 2026-11-20
**Author:** Andres
**Status:** Draft

## 1. Problem Statement

Small service businesses (clinics, salons, repair shops, law offices) spend significant staff time on repetitive front-office work: booking and rescheduling appointments, following up with customers, and answering the same questions about services, pricing/quotes, and operating hours. Hiring front-desk staff is expensive, and missed calls or slow responses lose business.

**ai-agents** is a platform of cooperating AI agents that work together as an office team. Each agent has a role — the first is an **AI Secretary** that handles inbound customer conversations: answering business-information questions, providing quotes, and booking appointments. Later agents (e.g., a Follow-up agent for reminders and confirmations) join the team and collaborate through handoffs, so the agents function like staff who delegate to one another.

**Value proposition:** A small business gets a reliable, always-available front office at a fraction of the cost of staff, and customers get instant, accurate answers and friction-free booking.

## 2. Target Users

| User | Role | Needs |
|------|------|-------|
| Small business owners | Buy and configure the agent team | Easy setup of business info (services, hours, pricing); confidence agents answer correctly; visibility into bookings |
| The business's customers | Chat with the agents | Instant answers about services/quotes/hours; book, reschedule, or cancel appointments without waiting |
| Office staff / receptionists | Supervise the agents | See conversations, handle escalations, take over when the agent is stuck |

## 3. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| End-to-end bookings | Agent books/reschedules/cancels with zero human intervention | % of booking conversations completed without escalation |
| Accurate business answers | >90% accuracy on services, quotes, and hours questions | Scored test set of representative customer questions |
| Agent team collaboration | Demonstrated handoff between two agents completing a task | Secretary → Follow-up handoff works end-to-end (post-MVP) |
| Business adoption | First real businesses onboarded and actively using the agents | Count of onboarded/paying businesses |

## 4. Scope

### In Scope (MVP — M1: Secretary agent alone)

- **AI Secretary agent** powered by the Claude API with tool use:
  - Answers questions about the business: services offered, operating hours, location, policies
  - Provides quotes / pricing information from configured business data
  - Books, reschedules, and cancels appointments against an internal availability calendar
- **Business knowledge base:** simple configuration of a business's services, hours, pricing (per-business data the agent draws answers from)
- **Appointments store:** SQLite-backed booking database with availability rules
- **Web chat interface:** minimal embeddable chat widget (TypeScript/React) talking to the FastAPI backend
- **Conversation logging** for review and accuracy evaluation

### Out of Scope (MVP)

- Multi-agent handoffs and the Follow-up agent (M2 — this is the core differentiator, but the Secretary must work solo first)
- Voice/phone calls
- SMS / WhatsApp channels (planned — Twilio or similar, post-MVP)
- External calendar integration (Google Calendar / Outlook — planned post-MVP; MVP uses internal calendar)
- Multi-language support (planned — English + Spanish, post-MVP)
- Multi-tenant dashboard and self-serve business onboarding
- Payments / deposits

## 5. Architecture

### Tech Stack

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Language (backend) | Python | 3.12 | Best ecosystem for AI/LLM work |
| Language (frontend) | TypeScript | 5.x | Minimal chat widget only |
| Backend Framework | FastAPI | 0.115+ | Async API for chat + future webhooks (Twilio, calendars) |
| AI | Claude API (Anthropic SDK) | latest | Agent loop with tool use: booking, FAQ lookup, quotes |
| Frontend Framework | React | 18 | Embeddable chat widget, Vite bundler |
| Database | SQLite → PostgreSQL | PG 16 | SQLite for local dev/POC; PostgreSQL in production |
| Auth | TBD | — | Not needed for POC; required before onboarding real businesses |

### Infrastructure

| Component | Choice | Notes |
|-----------|--------|-------|
| Git Host | GitHub | Remote to be created (`gh repo create`) |
| Cloud Provider | AWS | Likely ECS Fargate or App Runner + RDS PostgreSQL |
| CI/CD | GitHub Actions | `.github/workflows/ci.yml` (scaffolded by ADD: ruff + pytest) |
| Containers | None | Run directly for POC; Docker added when deploying to AWS |
| IaC | None | Revisit at deploy time |

### Environment Strategy

| Environment | Purpose | URL | Deploy Trigger |
|-------------|---------|-----|----------------|
| Local | Development & unit tests | http://localhost:8000 | Manual (`uvicorn app.main:app --reload`) |
| Production | Live businesses | TBD | Manual via `/add:deploy` (requires approval) |

**Environment Tier:** 2 (local + production)

### Multi-Agent Direction (post-MVP)

The long-term architecture is a team of role-based agents (Secretary, Follow-up, more later) coordinated through handoffs and shared context (business knowledge base + conversation/appointment state). The MVP deliberately builds the Secretary as a single agent, but booking/knowledge tools should be written as reusable services so later agents can share them.

## 6. Milestones & Roadmap

### Current Maturity: ALPHA (promoted 2026-11-21, retro-verified)

### Roadmap

| Milestone | Goal | Target Maturity | Status | Success Criteria |
|-----------|------|-----------------|--------|------------------|
| M1: secretary-mvp | One solid AI Secretary: FAQs, quotes, bookings via web chat | poc → alpha | ✅ DONE 2026-11-21 | Met: live booking completed end-to-end with zero human help |
| M2: agent-teamwork | Follow-up agent + handoff protocol; agents collaborate as a team | alpha | ✅ DONE 2026-11-21 | Met: Secretary delegated to Follow-up; reminder completed across agents |
| M3: real-channels | SMS/WhatsApp (Twilio), external calendars (Google/Outlook), multi-language (EN/ES) | beta | NOW | A real business runs on real channels with its real calendar |
| M4: onboarding | Multi-tenant setup, business dashboard, AWS production deployment | beta | LATER | First paying businesses onboarded self-serve |

### Milestone Detail

#### M1: secretary-mvp [DONE]
**Goal:** Prove a Claude-powered Secretary agent can answer business questions accurately and complete bookings end-to-end through a web chat.
**Appetite:** Small — a working POC, not a polished product.
**Target maturity:** poc (promote to alpha on completion)
**Features:**
- `business-knowledge` — configurable business data (services, hours, pricing) + agent answers from it
- `appointment-booking` — availability model, booking/reschedule/cancel tools, SQLite store
- `secretary-agent` — Claude agent loop wiring tools together with conversation state
- `chat-widget` — minimal web chat UI talking to the FastAPI backend
**Success criteria:**
- [ ] Agent answers services/hours/pricing questions >90% accurately on a test question set
- [ ] A customer books an appointment start-to-finish with no human intervention
- [ ] Conversations are logged and reviewable

### Maturity Promotion Path

| From | To | Requirements |
|------|----|-------------|
| poc → alpha | Secretary POC works end-to-end; specs written for features in flight; tests accompany new code |
| alpha → beta | >50% coverage; PR workflow; CI green; 2+ environments live; spec-driven evidence |
| beta → ga | >80% coverage; protected branches; release tags; full quality gates blocking |

## 7. Key Features

### Feature 1: Business Knowledge & Answers
Per-business configuration (services, hours, pricing, policies) that the Secretary uses to answer customer questions and generate quotes. Accuracy is measured against a test set.

### Feature 2: Appointment Booking
Availability rules + bookings stored in the database, exposed to the agent as tools (`check_availability`, `book_appointment`, `reschedule`, `cancel`). Designed as a service layer reusable by future agents.

### Feature 3: Secretary Agent
Claude-powered conversational agent with tool use, system-prompted with the business's profile, maintaining conversation state and escalating gracefully when it can't help.

### Feature 4: Chat Widget
Minimal embeddable React chat UI (the POC front door; SMS/WhatsApp come in M3).

## 8. Non-Functional Requirements

- **Performance:** Chat responses feel conversational (< ~5s per turn including LLM latency); no hard SLA at POC stage.
- **Security:** API keys server-side only; per-business data isolation designed in from the start (even though POC is single-tenant); no PII beyond what booking requires.
- **Accessibility:** Chat widget keyboard-navigable; full a11y pass deferred to beta.
- **Languages:** English only in MVP; architecture should not hard-code English (multi-language planned).

## 9. Open Questions

- Which AWS compute target (ECS Fargate vs App Runner vs Lambda) once we deploy?
- Calendar strategy for M3: integrate Google/Outlook per business, or keep internal calendar as source of truth with sync?
- Which messaging provider for SMS/WhatsApp (Twilio vs alternatives)?
- Pricing model for businesses (per seat, per conversation, flat)?

## 10. Revision History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-11-20 | 0.1.0 | Andres | Initial draft from /add:init interview |
