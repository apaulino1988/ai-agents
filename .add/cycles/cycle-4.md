# Cycle 4 — Production Path: AWS Deploy + A2P Registration

**Milestone:** M4 — onboarding
**Maturity:** alpha
**Status:** PLANNED
**Started:** TBD
**Completed:** TBD
**Duration Budget:** ~1 week elapsed (owner mostly away; external review queues
dominate — Twilio/TCR vetting and LLC approval run on outside clocks)

## Work Items

| Feature | Current Pos | Target Pos | Assigned | Est. Effort | Validation |
|---------|-------------|-----------|----------|-------------|------------|
| aws-deploy | NOT_SHAPED | IN_PROGRESS | Claude (spec+code) + Andres (AWS account) | spec ~0.5d, infra ~1-2d | Spec approved async; app live on App Runner; /health green from the internet; cost model < $15/mo |
| a2p-registration | NOT_SHAPED | SPECCED (filing gated on LLC EIN) | Andres (LLC, filing) + Claude (runbook, API prep) | runbook ~0.5d; filing 30min once EIN exists | Runbook complete; brand+campaign filed when EIN arrives; delivery to a US number verified when approved |

## Dependencies & Serialization

```
LLC formation (Andres — external, ~1-2 weeks; plan: Claude Doc
"Paulino AI Agents LLC — Formation & Launch Plan")
    ↓ EIN
a2p-registration: file Standard brand "Paulino AI Agents LLC" + campaign
    ↓ (TCR/Twilio vetting, days–weeks)
US SMS delivery unblocked (err 30034 resolved)

aws-deploy (parallel, independent):
    spec → Dockerfile + App Runner config → deploy → smoke → repoint webhooks
    (human gate: AWS account/billing access + approval before first deploy —
    config says deploy_approval_required: true)
```

## Parallel Strategy

Single-threaded execution in-session (alpha). The two features interleave only
at human gates; no file contention (a2p produces docs/runbooks, aws-deploy
produces infra files).

## Validation Criteria

### Per-Item Validation
- aws-deploy:
  - `specs/aws-deploy.md` approved by Andres (async OK)
  - Monthly cost ceiling **< $15/mo** (Andres 2026-11-23): App Runner smallest
    instance; SQLite on attached storage or defer RDS — NO RDS this cycle
  - Dockerfile + deploy pipeline documented; secrets via env (never in image)
  - Live /health + a real webhook round-trip from Twilio to AWS URL (kills the
    cloudflared-tunnel rotation routine)
  - Deploy requires Andres's explicit approval (config gate)
- a2p-registration:
  - `docs/a2p-runbook.md`: exact Twilio steps, fees, campaign use-case text
    (prewritten), brand fields mapped to LLC data — so filing is a 30-minute
    task the day the EIN arrives
  - Brand name must EXACTLY match "Paulino AI Agents LLC"
  - After approval: live SMS delivered to a US handset (closes M3's deferred
    carrier-edge gap)

### Cycle Success Criteria
- [ ] aws-deploy reaches IN_PROGRESS+ (spec approved, app deployed or deploy
      pending only on Andres's approval gate)
- [ ] a2p-registration reaches SPECCED (runbook done); FILED if EIN arrives
      within the cycle
- [ ] No regressions — full suite green, coverage ≥ 85%
- [ ] No new monthly cost beyond the $15 AWS ceiling + ~$50 one-time 10DLC

## Agent Autonomy & Checkpoints

Owner mostly away. Claude autonomously: specs, Dockerfile, deploy config,
runbook, tests. Hard human gates (batched in handoff + this plan):
1. LLC filing + EIN (Andres, personal/legal — see the Formation & Launch doc)
2. AWS account credentials/billing (Andres)
3. Deploy approval before anything goes live (config: requires_approval)
4. 10DLC brand filing payment (Andres's card, ~$48)

## Notes

- **Scope change recorded (2026-11-23):** Andres chose LLC formation in
  Maryland over sole-prop 10DLC. Business plan delivered as Claude Doc
  "Paulino AI Agents LLC — Formation & Launch Plan". 10DLC now files as a
  Standard brand under the LLC EIN — better throughput, no 1k/day sole-prop cap.
- Meta business verification: submit LLC docs in Meta Business Manager once
  formed (doc §"How the LLC unblocks the platform").
- Stripe account creation follows LLC+EIN (not an ADD feature; tracked in doc).
- business-dashboard remains BLOCKED on /add:ux (alpha UI gate).
- Beta promotion: aws-deploy closes the "2nd environment" gap; PR workflow +
  mypy remain.
