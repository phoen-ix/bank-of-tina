#!/usr/bin/env bash
# The e2e suite (e2e/tests, inventory in e2e/COVERAGE.md) against a throwaway
# stack: build the prod image, start app + MariaDB + Mailpit under their own
# compose project, run Playwright, tear it all down.
#
#   scripts/e2e.sh                          # the whole suite
#   scripts/e2e.sh tests/search.spec.ts     # extra args go to `playwright test`
#
# PORT_BASE (default 24100, the fleet port block): the app on
# 127.0.0.1:PORT_BASE. MAILPIT_PORT (default PORT_BASE+5): Mailpit's web UI and
# API. COMPOSE_PROJECT_NAME (default bank-of-tina_e2e): must end in _e2e or
# _docs. The checkout's .env is never read. ARTIFACTS: Playwright's results and HTML
# report, and the stack log on failure (default: a temp dir). The stack uses
# named volumes only (docker-compose.e2e.yml), never the checkout's
# mariadb-data/ or uploads/. Node + `npm ci` + `npx playwright install
# chromium` in e2e/ are the caller's.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ARTIFACTS="${ARTIFACTS:-$(mktemp -d)}"
mkdir -p "$ARTIFACTS"
ARTIFACTS="$(cd "$ARTIFACTS" && pwd)"
export PORT_BASE="${PORT_BASE:-24100}"
export MAILPIT_PORT="${MAILPIT_PORT:-$((PORT_BASE + 5))}"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bank-of-tina_e2e}"

# Teardown runs `down -v`: only ever a throwaway project.
case "$COMPOSE_PROJECT_NAME" in
  *_e2e | *_docs) ;;
  *) echo "e2e: COMPOSE_PROJECT_NAME must end in _e2e or _docs, not '$COMPOSE_PROJECT_NAME'" >&2
     exit 1 ;;
esac

# Compose requires these (${VAR:?}); test-only values. The checkout's .env is never read.
export SECRET_KEY=e2e-secret-key-not-a-secret DB_PASSWORD=e2e-db-not-a-secret
export DB_ROOT_PASSWORD=e2e-root-not-a-secret DB_USER=tina DB_NAME=bank_of_tina
# The rate limits key on the client address. Trusting one proxy hop lets every
# test be its own client (X-Forwarded-For, e2e/tests/fixtures.ts).
export BEHIND_PROXY=1
# Mailpit (the `mail` profile of docker-compose.e2e.yml) receives what the app sends.
export COMPOSE_PROFILES=mail

compose() { docker compose --env-file /dev/null -f docker-compose.yml -f docker-compose.e2e.yml "$@"; }
teardown() {
  rc=$?
  [ "$rc" = 0 ] || compose logs --tail=300 >"$ARTIFACTS/stack.log" 2>&1 || true
  compose down -v --remove-orphans --rmi local || true
  exit "$rc"
}
trap teardown EXIT

compose build web
compose up -d --wait
cd e2e
E2E_BASE_URL="http://localhost:$PORT_BASE" MAILPIT_URL="http://localhost:$MAILPIT_PORT" E2E_STACK=1 \
  PLAYWRIGHT_HTML_OUTPUT_DIR="$ARTIFACTS/playwright-report" PLAYWRIGHT_HTML_OPEN=never \
  npx playwright test --output "$ARTIFACTS/test-results" "$@"
