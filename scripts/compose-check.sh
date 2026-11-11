#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
export BACKEND_IMAGE=shield:local RELEASE_ID=compose-test
export COMPOSE_ENV_FILES=${RUNTIME_ENV_FILE:-.env.local}
docker compose build --build-arg SOURCE_REVISION="${GITHUB_SHA:-development}" api1
docker run --rm --entrypoint sh "$BACKEND_IMAGE" -c 'test -f /app/scripts/deploy.sh && test -f /app/compose.production.yaml'
docker compose up -d --wait postgres redis
docker compose run --rm --no-deps migrate
docker compose run --rm --no-deps -e FAKE_INFERENCE=false api1 python scripts/inference_check.py
docker compose up -d --wait api1 api2 worker dispatcher nginx
docker compose run --rm --no-deps api1 python scripts/smoke.py http://nginx
# Persist a harmless sentinel row, recreate DB/API containers, then verify the same row.
docker compose exec -T postgres psql -U shield -d shield -v ON_ERROR_STOP=1 -c "INSERT INTO operational_checks(name) VALUES ('persistence') ON CONFLICT DO NOTHING"
docker compose up -d --force-recreate --wait postgres api1 api2
docker compose exec -T postgres psql -U shield -d shield -v ON_ERROR_STOP=1 -c "DO \$\$ BEGIN IF NOT EXISTS(SELECT 1 FROM operational_checks WHERE name='persistence') THEN RAISE EXCEPTION 'lost data'; END IF; END \$\$"
sleep 6
docker compose run --rm --no-deps api1 python scripts/smoke.py http://nginx
