# Production Runbook — Lightsail

Spec: `specs/aws-deploy.md`. Everything here is copy-paste. The instance
hosts the full stack via Docker Compose at `/opt/ai-agents/`.

## One-time provisioning (human, ~30 min)

1. **Lightsail console** → Create instance → Linux, **Ubuntu 24.04 LTS**,
   dual-stack, **1 GB RAM** plan (~$5/mo — confirm current price at create).
   Name: `ai-agents-prod`.
2. Networking tab → attach a **static IP**. Open ports **80** and **443**
   (22 is open by default; restrict its source to "my IP" ideally).
3. DNS: at the domain registrar add `A` record `api.<domain>` → the static
   IP. (Until a domain exists, use `<static-ip>.sslip.io` as PROD_HOST —
   Caddy will still get a certificate.)
4. SSH in (console browser SSH or `ssh -i <key> ubuntu@<ip>`), then:

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker ubuntu && newgrp docker
sudo mkdir -p /opt/ai-agents/{data,secrets} && sudo chown -R ubuntu:ubuntu /opt/ai-agents
```

5. Copy files to the instance (from the repo, on your machine):

```bash
scp deploy/docker-compose.prod.yml deploy/Caddyfile deploy/litestream.yml deploy/restore.sh ubuntu@<ip>:/opt/ai-agents/
scp .env.production.example ubuntu@<ip>:/opt/ai-agents/.env     # then FILL IT on the instance
scp data/google-sa.json ubuntu@<ip>:/opt/ai-agents/secrets/
ssh ubuntu@<ip> "chmod 600 /opt/ai-agents/.env && chmod +x /opt/ai-agents/restore.sh"
```

6. **Migrating existing local data (optional):** back up first, then
   `scp secretary.db ubuntu@<ip>:/opt/ai-agents/data/` — it auto-migrates
   to multi-tenant schema on first boot.
7. GHCR package is public (public repo) — no registry login needed on the
   instance. First start: `cd /opt/ai-agents && docker compose -f docker-compose.prod.yml up -d`
   (add `--profile backup` once LITESTREAM_* vars are set and the S3 bucket
   exists: S3 console → create bucket, IAM user with that bucket only).

## Deploy a new version

CI pushes `ghcr.io/apaulino1988/ai-agents:{latest,<sha>}` on every green
main build. Deploying is always manual:

```bash
DEPLOY_HOST=<ip-or-host> ./deploy/deploy.sh            # latest
TAG=<git-sha> DEPLOY_HOST=<ip> ./deploy/deploy.sh      # specific version
```

## Rollback

```bash
TAG=<previous-known-good-sha> DEPLOY_HOST=<ip> ./deploy/deploy.sh
```

(Find SHAs: `gh run list` / `git log --oneline` — every main commit has an image.)

## Logs & status

```bash
ssh ubuntu@<ip> "cd /opt/ai-agents && docker compose -f docker-compose.prod.yml ps"
ssh ubuntu@<ip> "cd /opt/ai-agents && docker compose -f docker-compose.prod.yml logs -f app"
curl https://<PROD_HOST>/health
```

## Backup & restore

- Continuous: Litestream (`--profile backup`) streams every DB change to S3.
- Weekly: Lightsail console → instance → Snapshots → enable automatic.
- Restore drill / disaster: `ssh ubuntu@<ip> "/opt/ai-agents/restore.sh"`
  (stops app, restores from S3, restarts; keeps a pre-restore copy).

## Webhook cutover (once, after first successful deploy)

1. Twilio: update the SMS number's webhook AND the WhatsApp sender's
   webhook (Senders API) to `https://<PROD_HOST>/webhooks/sms`.
2. Set `TWILIO_VALIDATE=true` in `/opt/ai-agents/.env`, restart app.
3. Run live smoke (`docs/smoke-test.md`) against the prod URL.
4. Retire the cloudflared tunnel routine (docs/smoke-test.md note).

## Instance reboot / AWS maintenance

Everything has `restart: unless-stopped`; after reboot verify
`curl https://<PROD_HOST>/health`. Disk check: `df -h /`.
