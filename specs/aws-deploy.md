# Spec: aws-deploy (M4 — onboarding)

**Version:** 0.1.0 (DRAFT — awaiting Andres's approval)
**Created:** 2026-11-23
**PRD Reference:** docs/prd.md (M4: onboarding)
**Status:** Draft

## 1. Overview

Put the ai-agents platform on a permanent, cheap AWS production environment:
a single Lightsail VM running the app in Docker behind Caddy (automatic
HTTPS), with SQLite on the instance's persistent disk and continuous backup
to S3. This kills the cloudflared-tunnel/webhook-rotation routine, gives
Twilio and Meta a stable HTTPS endpoint (enabling signature validation), and
closes the beta-promotion "second environment" gap.

**Architecture decision (research 2026-11-23):** App Runner
[stopped accepting new customers 2026-04-30](https://dev.to/parag477/aws-app-runner-is-dead-heres-what-you-should-use-instead-2026-1hp7)
and neither it nor ECS Express Mode offers a persistent filesystem for
SQLite. A [Lightsail](https://aws.amazon.com/lightsail/) instance has fixed
pricing and a real disk — the only architecture that satisfies both the
< $15/mo ceiling (Andres, 2026-11-23) and "no RDS this cycle."

### User Story

As the **platform operator**, I want the service running 24/7 at a stable
public HTTPS URL for under $15/month, so that real businesses' customers
reach it without my laptop, tunnels, or babysitting.

## 2. Cost Model (ceiling: $15/mo)

| Item | Monthly |
|------|---------|
| Lightsail instance, 1 GB RAM / 40 GB SSD, dual-stack IPv4 | ~$5.00 (verify current tier in console; [snapshot of 2026 tiers](https://dev.to/vamsi_0fe326ce8584827fca5/aws-lightsail-pricing-in-2026-a-complete-breakdown-before-you-commit-3n66)) |
| S3 backup bucket (Litestream, few MB) | < $0.25 |
| Lightsail instance snapshot (weekly, ~2 GB retained) | ~$0.10 |
| **Total** | **~$5.50/mo** |

One-time: $0 AWS; domain (~$12/yr) comes from the LLC plan and is shared
with the business site. GHCR image hosting is free (public repo).

## 3. Acceptance Criteria

| ID | Criterion | Priority |
|----|-----------|----------|
| AC-001 | `Dockerfile` builds a production image (python:3.12-slim, non-root user, `requirements.txt` without dev deps, uvicorn entrypoint); image contains NO secrets and NO SQLite file | Must |
| AC-002 | `docker-compose.prod.yml` runs app + Caddy; Caddy terminates HTTPS with an auto-provisioned certificate for the production hostname | Must |
| AC-003 | SQLite lives on the host disk (bind mount), survives container restarts and redeploys; `SECRETARY_DB_PATH` points at it | Must |
| AC-004 | Secrets come only from a host-side `.env` (chmod 600), never baked into the image or compose file; `.env.production.example` documents every var incl. `ADMIN_TOKEN`, `TWILIO_VALIDATE=true` | Must |
| AC-005 | GitHub Actions builds and pushes `ghcr.io/apaulino1988/ai-agents` on main (CI-green only); DEPLOY to the instance is a separate manual step (`deploy/deploy.sh` over SSH) — never automatic (config: deploy requires approval) | Must |
| AC-006 | Litestream replicates the SQLite DB to S3 continuously; restore procedure documented and tested once | Should |
| AC-007 | After cutover: Twilio SMS number + WhatsApp sender webhooks point at `https://<prod-host>/webhooks/sms`; `TWILIO_VALIDATE=true` enabled (stable URL at last); live smoke passes (WhatsApp round-trip + calendar) | Must |
| AC-008 | `docs/runbook-prod.md`: deploy, rollback (previous image tag), logs, backup-restore, instance reboot — each a copy-paste command block | Must |
| AC-009 | Health monitoring: uptime check hitting `/health` every 5 min with email alert (free tier of UptimeRobot or AWS synthetics-lite equivalent) | Should |

## 4. Test Strategy

Infra feature — unit-test surface is small; verification is checklist-driven:

- Unit: Dockerfile lint (hadolint optional), compose config validation
  (`docker compose config`), and a test that the app boots with
  `SECRETARY_DB_PATH` pointing at a mounted path (already covered by
  existing suite's env handling).
- Live verify (human-gated): AC-003 persistence across `docker compose up`
  redeploy; AC-007 smoke per `docs/smoke-test.md` against the prod URL.

## 5. Implementation Plan (summary)

1. `Dockerfile` + `.dockerignore` (exclude .env, *.db, data/google-sa.json,
   .add, tests) — split `requirements-prod.txt` (drop pytest/ruff).
2. `deploy/docker-compose.prod.yml` (app + Caddy + Litestream sidecar),
   `deploy/Caddyfile`, `.env.production.example`.
3. `.github/workflows/ci.yml`: add build+push-to-GHCR job (on main, after
   tests pass).
4. `deploy/deploy.sh`: SSH pull + up + health check; `deploy/restore.sh`.
5. `docs/runbook-prod.md`.
6. Human: create Lightsail instance + static IP, point DNS A record, run
   first deploy together (approval gate), cut webhooks over, enable
   TWILIO_VALIDATE, run live smoke.

## 6. Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| Instance reboot | Docker restart policy `unless-stopped` brings everything back; DB intact on disk |
| Redeploy while a webhook arrives | Seconds of 502; Twilio retries webhooks — acceptable at alpha |
| Disk full | Litestream + logs are tiny; 40 GB is years of headroom; runbook documents df check |
| Cert renewal | Caddy automatic; no action |
| SQLite corruption / instance loss | Restore from Litestream S3 replica (AC-006) or weekly snapshot; documented drill |
| Scale beyond one instance | Out of scope — that's the PostgreSQL/RDS milestone trigger |

## 7. Dependencies

- Multi-tenant (Complete) — prod DB migrates automatically on first boot
  (back up local secretary.db before cutover if it's copied up).
- Human gates: AWS account access, domain/DNS, deploy approval (cycle-4 plan).
- Does NOT depend on the LLC or 10DLC.

## 8. Out of Scope (deferred)

- PostgreSQL/RDS, multi-instance, autoscaling (schema already PG-portable)
- IaC (Terraform) — a 1-VM setup doesn't earn it yet; runbook instead
- CI-triggered auto-deploy (config forbids; revisit at beta with PR workflow)
- Staging environment (beta)

## 9. Revision History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-11-23 | 0.1.0 | Claude (draft for async approval) | Initial draft; Lightsail over App Runner (closed to new customers) — cost ~$5.50/mo |
