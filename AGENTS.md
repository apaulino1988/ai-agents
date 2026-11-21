<!-- ADD:MANAGED:START version=0.11.0 maturity=poc generated=2026-11-20 -->

# ai-agents

A team of cooperating AI agents that handle office front-desk work for small businesses — booking appointments, following up with customers, and answering questions about services, quotes, and operating hours. MVP: a single AI Secretary agent (web chat).

## Engagement Protocol

- POC maturity — relaxed process. Specs are optional but encouraged; informal cycle planning.
- Autonomy: autonomous — execute full cycles independently, stop only for blockers.
- Solo project — no PR gate; commit conventionally (feat:, fix:, test:, docs:) straight to `main`.

## Spec-First Invariants

- PRD lives at `docs/prd.md`; feature specs in `specs/`; plans in `docs/plans/`.
- At POC, specs are optional — but write one before any feature that outlives the POC.

## TDD Discipline

- TDD encouraged, not enforced (spike quality mode, 50% coverage target).
- Tests: `pytest` (unit in `tests/unit`, integration in `tests/integration`). Lint: `ruff check .`.

## Maturity & Autonomy Ceiling

Project maturity: **poc**.

- Throwaway code is acceptable; prefer reusable service-layer tools for booking/knowledge (future agents share them).
- Promote to alpha via `/add:retro` once the Secretary works end-to-end.

Production deploys and merges to the default branch always require human approval.

## Pointers

- Stack: Python 3.12 + FastAPI, Claude API (Anthropic SDK), SQLite→PostgreSQL, React chat widget (Vite/TS).
- Run: `uvicorn app.main:app --reload` → http://localhost:8000
- Config: `.add/config.json` · Knowledge: `.add/learnings.md` · CI: `.github/workflows/ci.yml`

<!-- ADD:MANAGED:END -->

<!-- USER:AUTHORED:START -->
<!-- USER:AUTHORED:END -->
