#!/usr/bin/env bash
# Restore the SQLite DB from the Litestream S3 replica (spec: aws-deploy AC-006).
# Run ON the instance from /opt/ai-agents. Stops the app during restore.
set -euo pipefail

cd /opt/ai-agents
echo ">>> Stopping app..."
docker compose -f docker-compose.prod.yml stop app

TS="$(date +%Y%m%d-%H%M%S)"
[ -f data/secretary.db ] && cp data/secretary.db "data/secretary.db.pre-restore-${TS}"

echo ">>> Restoring from S3 replica..."
docker run --rm --env-file .env -v "$(pwd)/data:/data" -v "$(pwd)/litestream.yml:/etc/litestream.yml:ro" \
  litestream/litestream:latest restore -config /etc/litestream.yml -o /data/secretary.db /data/secretary.db

echo ">>> Starting app..."
docker compose -f docker-compose.prod.yml up -d app
curl -fsS http://localhost:8000/health && echo "health OK — restore complete (pre-restore copy: data/secretary.db.pre-restore-${TS})"
