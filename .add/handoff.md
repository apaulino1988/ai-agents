# Session Handoff — ai-agents

**Written:** 2026-11-23 (cycle-3 closed + cycle-4 planned; paused by Andres, resuming tomorrow)
**Branch:** main @ `76e999d` (pushed, CI green)

## State

- **Cycle 3 CLOSED** (988e6f1): multi-tenant foundation VERIFIED — all 4
  success criteria met, Andres signed off via /add:cycle --complete. M4 is
  1/5 features done; PRD now carries the M4 hill chart.
- **Cycle 4 PLANNED, not started** (`.add/cycles/cycle-4.md`, config
  current_cycle=cycle-4): aws-deploy (< $15/mo hard ceiling, NO RDS) +
  a2p-registration (10DLC as Standard brand under the LLC).
- **SCOPE CHANGE (Andres, 2026-11-23): forming "Paulino AI Agents LLC" in
  Maryland (PG County).** Full formation/launch plan delivered as Claude Doc
  **"Paulino AI Agents LLC — Formation & Launch Plan"**
  (claude.ai/artifact/AgorRWiFKpQQi6BG9dRxYx) — researched 2026-11-23:
  $100 MD online filing ~7 business days; FinCEN BOI not required for US
  companies; MD 3% IT-services tax (since 2025-07) likely applies — register
  sales/use at formation, CPA to confirm; PG County home-office U&O = one
  DPIE call (301-883-3840 opt 2) to confirm if needed.
- Meta verification likely cleared (sender ONLINE, 250/24hr); confirm with
  next live delivery; submit LLC docs in Meta Business Manager once formed.

## Next up (tomorrow)

**Claude (autonomous):**
1. Draft `specs/aws-deploy.md` (App Runner smallest instance, SQLite on
   storage, Dockerfile, secrets via env, webhook re-point kills tunnel
   routine) → Andres approves async → build.
2. Draft `docs/a2p-runbook.md` (brand fields prefilled from LLC data,
   campaign use-case text prewritten) so filing is 30 min post-EIN.

**Andres (human gates, in order):**
1. File the LLC + get EIN (doc Steps 1–3).
2. AWS account/billing access for Claude.
3. Approve first deploy (config: requires_approval).
4. Pay/file 10DLC brand+campaign (~$48) when EIN arrives.

## Decisions / gotchas

- Cycle-4 decisions (Andres 2026-11-23): AWS ceiling < $15/mo; mostly away;
  LLC over sole-prop for 10DLC.
- 10DLC brand name must EXACTLY match "Paulino AI Agents LLC".
- ADMIN_TOKEN gates the admin API (unset = 404); set a strong value in .env
  before live use; never commit it.
- Live DB auto-migrates to multi-tenant on next app start; back up
  secretary.db before first prod start.
- business-dashboard still BLOCKED on /add:ux (alpha UI gate).
- Beta promotion gaps: PR workflow, 2nd env (aws-deploy), mypy.
- Secrets drift risk: git status + scan before every commit.
- Write this handoff at every session end.
