# Active Learnings (9 of 9)

> Pre-filtered by severity and date. Full data: `.add/learnings.json`

### anti-pattern
- **[high]** Secrets go only in gitignored .env, never .env.example (L-004, 2026-11-21)
  User pasted a real API key into the tracked .env.example â€” would have leaked to GitHub on next push. Moved to .env and restored the placeholder before any commit. Always double-check which env file receives a secret; .env.example is public documentation.
### architecture
- **[high]** Task-queue handoff is the multi-agent protocol (L-001, 2026-11-21)
  agent_tasks table (from_agent, to_agent, task_type, payload, due_at, status) is the delegation mechanism. The delegating agent decides via a tool call (schedule_followup); the receiving agent runs its own Claude loop independently. Proven live: Secretary booked, delegated, Follow-up composed and sent the reminder. Reuse for every future role.
- **[medium]** Service layer separation enables agent reuse (L-002, 2026-11-21)
  booking/knowledge as plain Python services (no agent imports) meant the Follow-up agent reused them with zero changes â€” validating the design constraint set at init. Keep all business capability in app/services/, agents only orchestrate.
### technical
- **[medium]** Bare pytest and python -m pytest resolve imports differently (L-008, 2026-11-21)
  `python -m pytest` adds the cwd to sys.path; bare `pytest` does not. A repo with no root conftest.py/pyproject can pass locally and fail collection in CI with ModuleNotFoundError. Fix: an empty root conftest.py (or pythonpath in pyproject). Also: verify CI is actually green after scaffolding it — this repo's CI had failed on every run since creation without being noticed.
- **[medium]** Windows zombie socket can hold a port after process death (L-005, 2026-11-21)
  A killed PID (5664) remained in netstat as LISTENING on 127.0.0.1:8000 with no live process. New binds fail with WinError 10048. Fastest fix: use another port; a reboot clears the zombie entry.
- **[medium]** gh OAuth needs 'workflow' scope to push CI files (L-006, 2026-11-20)
  A default `gh auth login` token lacks the workflow scope; pushing .github/workflows/*.yml is rejected by GitHub. Fix: `gh auth refresh -h github.com -s workflow` (device-code flow).
- **[low]** ADD 0.11.0 plugin cache ships without scripts/check-test-count.py (L-009, 2026-11-21)
  The tdd-cycle skill's RED/GREEN snapshot command points at {plugin}/../../scripts/check-test-count.py, which does not exist in the installed plugin cache. Workaround: manual snapshot JSON from `pytest --collect-only -q` (functions list + count) at .add/cycles/cycle-N/, compared by hand at verify Gate 3.5. Report upstream to MountainUnicorn/add.
- **[low]** FastAPI form webhooks need python-multipart (L-007, 2026-11-21)
  Twilio posts form-encoded bodies; FastAPI/Starlette form parsing requires the python-multipart package or every webhook request 500s. It is easy to miss locally because nothing imports it directly. Fix: add python-multipart to requirements whenever a route reads request.form().
- **[low]** Machine Python is 3.14.6, not configured 3.12 (L-003, 2026-11-20)
  All dependencies (fastapi, anthropic, pydantic) are compatible with 3.14.6. Config updated to match reality at the 2026-11-21 retro.

---
*Auto-generated. Do not edit — regenerated on each learning write.*
