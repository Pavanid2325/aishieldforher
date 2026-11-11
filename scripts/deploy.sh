#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
exec 9>.deploy.lock
flock -n 9 || { echo 'Another deployment is active'; exit 1; }
image=${1:?immutable ECR image required}
release=${2:?commit SHA required}
[[ "$image" =~ ^[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/[a-z0-9/_-]+@sha256:[a-f0-9]{64}$ ]] || exit 2
[[ "$release" =~ ^[a-f0-9]{40}$ ]] || exit 2
[[ -f .env && -r deploy/nginx.production.conf ]] || exit 2
mkdir -p .releases
chmod 700 .releases
compose=(docker compose -f compose.yaml -f compose.production.yaml)
# Credentials are read by Compose from the protected runtime .env; never source it as shell code.
export BACKEND_IMAGE="$image" RELEASE_ID="$release"
export RUNTIME_ENV_FILE=.env
"${compose[@]}" config --quiet
registry=${image%%/*}
region=$(cut -d. -f4 <<<"$registry")
aws ecr get-login-password --region "$region" | docker login --username AWS --password-stdin "$registry" >/dev/null
"${compose[@]}" pull api1 api2 worker dispatcher nginx redis
revision=$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$image")
[[ "$revision" == "$release" ]] || { echo 'Image revision does not match requested release'; exit 2; }
previous=''
[[ ! -f .releases/current ]] || previous=$(cat .releases/current)
rollback_on_failure() {
    trap - ERR
    echo 'Deployment failed; attempting previous application image'
    if [[ -n "$previous" ]]; then
        read -r BACKEND_IMAGE RELEASE_ID <<<"$previous"
        export BACKEND_IMAGE RELEASE_ID
        "${compose[@]}" up -d --no-build api1 api2 worker dispatcher redis nginx
        "${compose[@]}" run --rm --no-deps api1 python scripts/smoke.py && echo 'Previous release verified' || echo 'ROLLBACK VERIFICATION FAILED; operator action required'
    else
        echo 'No previously successful release exists'
    fi
    exit 1
}
trap rollback_on_failure ERR
"${compose[@]}" run --rm --no-deps migrate python scripts/validate_production.py
# One migration step, serialized by a PostgreSQL transaction advisory lock.
"${compose[@]}" run --rm --no-deps migrate
"${compose[@]}" up -d --no-build api1 api2 worker dispatcher redis nginx
# TLS hostname must match the public certificate; smoke script uses configured public hostname.
"${compose[@]}" run --rm --no-deps api1 python scripts/smoke.py
"${compose[@]}" exec -T dispatcher python scripts/check_dispatcher.py
[[ -z "$previous" ]] || printf '%s\n' "$previous" > .releases/previous
printf '%s %s\n' "$image" "$release" > .releases/current.tmp
mv .releases/current.tmp .releases/current
trap - ERR
echo "Release $release verified"
