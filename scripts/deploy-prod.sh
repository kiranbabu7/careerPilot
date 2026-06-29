#!/usr/bin/env bash
# Deploy latest CareerPilot code on a production EC2 host.
#
# Production containers run from Docker images built at deploy time — they do
# NOT read the git checkout on disk. `git pull` + `docker compose restart`
# leaves old code running. This script pulls, rebuilds, and recreates services.
#
# Usage (from repo root on the server):
#   ./scripts/deploy-prod.sh
#   ./scripts/deploy-prod.sh --no-cache-frontend   # after NEXT_PUBLIC_* changes
#   ./scripts/deploy-prod.sh --branch main

set -euo pipefail

COMPOSE_FILE="docker-compose.prod.yml"
BRANCH=""
NO_CACHE_FRONTEND=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-cache-frontend)
      NO_CACHE_FRONTEND=true
      shift
      ;;
    --branch)
      BRANCH="${2:?--branch requires a branch name}"
      shift 2
      ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Expected $COMPOSE_FILE in $ROOT" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.example and set production values first." >&2
  exit 1
fi

echo "==> Git status before deploy"
git fetch --all --prune
if [[ -n "$BRANCH" ]]; then
  git checkout "$BRANCH"
fi
git pull --ff-only

echo "==> Current commit: $(git rev-parse --short HEAD) $(git log -1 --pretty=%s)"

echo "==> Rebuild and recreate application containers"
if [[ "$NO_CACHE_FRONTEND" == true ]]; then
  docker compose -f "$COMPOSE_FILE" build --no-cache frontend
  docker compose -f "$COMPOSE_FILE" up -d --build backend celery-worker celery-beat frontend caddy
else
  docker compose -f "$COMPOSE_FILE" up -d --build backend celery-worker celery-beat frontend
fi

echo "==> Service status"
docker compose -f "$COMPOSE_FILE" ps

API_DOMAIN="${CADDY_API_DOMAIN:-}"
if [[ -z "$API_DOMAIN" ]] && [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a && source .env && set +a
  API_DOMAIN="${CADDY_API_DOMAIN:-}"
fi

if [[ -n "$API_DOMAIN" ]]; then
  echo "==> Health check: https://${API_DOMAIN}/api/v1/health/ready/"
  curl -fsS "https://${API_DOMAIN}/api/v1/health/ready/" && echo
else
  echo "==> Skipping external health check (set CADDY_API_DOMAIN in .env)"
fi

echo "==> Deploy complete"
