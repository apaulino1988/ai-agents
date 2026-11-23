#!/usr/bin/env bash
# Manual production deploy (spec: aws-deploy AC-005 — never automatic).
# Usage: DEPLOY_HOST=<ip-or-host> [DEPLOY_USER=ubuntu] [TAG=latest] ./deploy/deploy.sh
set -euo pipefail

DEPLOY_HOST="${DEPLOY_HOST:?Set DEPLOY_HOST to the Lightsail instance address}"
DEPLOY_USER="${DEPLOY_USER:-ubuntu}"
TAG="${TAG:-latest}"
APP_DIR="/opt/ai-agents"

echo ">>> Deploying ghcr.io/apaulino1988/ai-agents:${TAG} to ${DEPLOY_USER}@${DEPLOY_HOST}"
read -r -p "Proceed with PRODUCTION deploy? [y/N] " answer
[[ "${answer}" == "y" || "${answer}" == "Y" ]] || { echo "Aborted."; exit 1; }

ssh "${DEPLOY_USER}@${DEPLOY_HOST}" bash -s <<EOF
set -euo pipefail
cd ${APP_DIR}
# Pin the tag for this deploy (rollback = rerun with previous TAG)
sed -i "s|ghcr.io/apaulino1988/ai-agents:.*|ghcr.io/apaulino1988/ai-agents:${TAG}|" docker-compose.prod.yml
docker compose -f docker-compose.prod.yml pull app
docker compose -f docker-compose.prod.yml up -d
sleep 5
curl -fsS http://localhost:8000/health || curl -fsS https://\$(grep ^PROD_HOST .env | cut -d= -f2)/health
echo "health OK"
docker image prune -f >/dev/null
EOF

echo ">>> Deploy complete. Verify: https://<PROD_HOST>/health"
