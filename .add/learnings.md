# Project Learnings — ai-agents

> **Tier 3: Project-Specific Knowledge**
>
> This file is maintained automatically by ADD agents. Entries are added at checkpoints
> (after verify, TDD cycles, deployments, away sessions) and reviewed during retrospectives.
>
> This is one of three knowledge tiers agents read before starting work:
> 1. **Tier 1: Plugin-Global** (`knowledge/global.md`) — universal ADD best practices
> 2. **Tier 2: User-Local** (`~/.claude/add/library.md`) — your cross-project wisdom
> 3. **Tier 3: Project-Specific** (this file) — discoveries specific to this project
>
> **Agents:** Read ALL three tiers before starting work.
> **Humans:** Review with `/add:retro --agent-summary` or during full `/add:retro`.

## Technical Discoveries
<!-- Things learned about the tech stack, libraries, APIs, infrastructure -->
<!-- Format: - {date}: {discovery}. Source: {how we learned this}. -->

## Architecture Decisions
<!-- Decisions made and their rationale -->
<!-- Format: - {date}: Chose {X} over {Y} because {reason}. -->
- 2026-11-20: Chose single Secretary agent for MVP over multi-agent framework first, because proving one agent delivers value end-to-end de-risks the product before investing in orchestration. Source: /add:init interview (Q4).
- 2026-11-20: Booking/knowledge logic goes in a reusable service layer exposed as agent tools, so future agents (Follow-up) can share them in M2. Source: /add:init interview.

## What Worked
<!-- Patterns, approaches, tools that proved effective -->
- 2026-11-21 (retro): Speed — zero → two working agents in 2 days. Live demos (real booking, real handoff) over test-only verification. Full entries in .add/learnings.json (L-001…L-006).

## What Didn't Work
<!-- Patterns, approaches, tools that caused problems -->

## Agent Checkpoints
<!-- Automatic entries from verification, TDD cycles, deploys, away sessions -->
<!-- These are processed and archived during /add:retro -->
- 2026-11-21 [post-verify] followup-agent + handoff protocol: agent task queue (agent_tasks) as the delegation mechanism; Secretary delegates via schedule_followup tool (agent decision, not hardcoded); Follow-up agent runs its own Claude loop and writes reminders to outbox (M3 SMS stand-in). Live demo: booking → task (due appt-24h) → reminder sent, end-to-end across both agents. 28/28 tests, ruff clean.
- 2026-11-20 [post-verify] secretary-agent first build: FastAPI + Claude (claude-opus-5, manual tool-use loop, cached system prompt), SQLite booking service, static chat page. ruff clean, 18/18 unit tests pass. Agent chat untested live — requires ANTHROPIC_API_KEY in .env. Python on this machine is 3.14.6 (not 3.12 as configured); all deps compatible.

## Profile Update Candidates
<!-- Cross-project patterns flagged for promotion to ~/.claude/add/profile.md -->
<!-- Only promoted during /add:retro with human confirmation -->
