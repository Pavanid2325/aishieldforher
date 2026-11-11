#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
[[ -f .releases/previous ]] || { echo 'No previous successful release'; exit 1; }
read -r image release < .releases/previous
# Forward migrations are idempotent. No schema downgrade or volume deletion.
exec bash scripts/deploy.sh "$image" "$release"
