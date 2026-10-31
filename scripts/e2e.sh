#!/usr/bin/env bash
# The e2e suite (e2e/tests, inventory in e2e/COVERAGE.md) against a throwaway
# stack: build the prod image, start app + MariaDB + Mailpit under their own
# compose project, run Playwright, tear it all down.
#
#   scripts/e2e.sh                          # the whole suite
#   scripts/e2e.sh tests/search.spec.ts     # extra args go to `playwright test`
#
# PORT_BASE (default 5000): the app on 127.0.0.1:PORT_BASE, Mailpit's web UI and
# API on PORT_BASE+5. COMPOSE_PROJECT_NAME (default bank-of-tina_e2e): never
# the checkout's live `bank-of-tina`. ARTIFACTS: Playwright's results and HTML
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
export PORT_BASE="${PORT_BASE:-5000}"
export MAILPIT_PORT="$((PORT_BASE + 5))"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bank-of-tina_e2e}"

case "$COMPOSE_PROJECT_NAME" in
  bank-of-tina | phytotron | phytotron-dev | vib | fileheron | keyb-dev)
    echo "e2e: refusing the live project name '$COMPOSE_PROJECT_NAME'" >&2
    exit 1 ;;
esac

# Compose requires these (${VAR:?}); test-only values. Exported values win over a .env.
export SECRET_KEY=e2e-secret-key-not-a-secret DB_PASSWORD=e2e-db-not-a-secret
export DB_ROOT_PASSWORD=e2e-root-not-a-secret DB_USER=tina DB_NAME=bank_of_tina
# The rate limits key on the client address. Trusting one proxy hop lets every
# test be its own client (X-Forwarded-For, e2e/tests/fixtures.ts).
export BEHIND_PROXY=1
# Mailpit (the `mail` profile of docker-compose.e2e.yml) receives what the app sends.
export COMPOSE_PROFILES=mail

compose() { docker compose -f docker-compose.yml -f docker-compose.e2e.yml "$@"; }
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
