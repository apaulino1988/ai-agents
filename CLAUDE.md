# ai-agents

A team of cooperating AI agents that handle office front-desk work for small businesses — booking appointments, following up with customers, and answering questions about services, quotes, and operating hours. The MVP is a single **AI Secretary** agent (web chat: FAQs, quotes, bookings); multi-agent teamwork (Follow-up agent, handoffs) comes next.

## Methodology

This project follows **Agent Driven Development (ADD)** — specs drive agents, humans architect and decide, trust-but-verify ensures quality.

- **PRD:** docs/prd.md
- **Specs:** specs/
- **Plans:** docs/plans/
- **Config:** .add/config.json

Document hierarchy: PRD → Spec → Plan → User Test Cases → Automated Tests → Implementation

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend | Python + FastAPI | 3.12 / 0.115+ |
| AI | Claude API (Anthropic SDK) | latest |
| Database | SQLite (dev) → PostgreSQL (prod) | PG 16 |
| Frontend | React chat widget (Vite, TypeScript 5.x) | 18 |

## Commands

### Development
```
uvicorn app.main:app --reload    # Start local dev (http://localhost:8000)
pytest                           # Run unit tests
ruff check .                     # Lint check
mypy app --ignore-missing-imports  # Type check (non-blocking at POC)
```

### ADD Workflow
```
/add:spec {feature}                  # Create feature specification
/add:plan specs/{feature}.md         # Create implementation plan
/add:tdd-cycle specs/{feature}.md    # Execute TDD cycle
/add:verify                          # Run quality gates
/add:deploy                          # Commit and deploy
/add:away {duration}                 # Human stepping away
/add:back                            # Human returning
```

## Architecture

### Key Directories
```
app/            # FastAPI backend (agent loop, tools, API)  — created with first feature
widget/         # React chat widget                          — created with chat-widget feature
specs/          # Feature specifications
docs/plans/     # Implementation plans
docs/prd.md     # Product requirements
tests/          # unit / integration / e2e
.add/           # ADD config, learnings, retros, cycles
```

### Environments

- **Local:** `uvicorn app.main:app --reload` at http://localhost:8000, SQLite database
- **Production:** AWS (compute target TBD — ECS Fargate / App Runner), PostgreSQL; deploys are manual and require approval

### Design constraint

Booking and business-knowledge logic live in a **service layer exposed to the agent as tools** — future agents (Follow-up, etc.) must be able to reuse the same tools when multi-agent teamwork lands in M2.

## Quality Gates

- **Mode:** spike (POC maturity)
- **Coverage threshold:** 50%
- **Type checking:** non-blocking
- **E2E required:** no

All gates defined in `.add/config.json`. Run `/add:verify` to check.

## Source Control

- **Git host:** GitHub (remote not yet created)
- **Branching:** trunk-based on `main`; short-lived feature branches optional
- **Commits:** Conventional commits (feat:, fix:, test:, refactor:, docs:)
- **CI/CD:** GitHub Actions (`.github/workflows/ci.yml` — ruff + pytest)

## Collaboration

- **Autonomy level:** autonomous — execute full cycles independently, stop only for blockers
- **Review gates:** none at POC (solo); production deploys always require approval
- **Deploy approval:** required
