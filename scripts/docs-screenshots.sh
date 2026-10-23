#!/usr/bin/env bash
# Regenerate the docs screenshots: build the prod image, and for each UI
# language start a throwaway stack under its own compose project, seed it
# through the web forms (e2e/docs/seed.ts), run the docs tour
# (e2e/docs/tour.spec.ts) and tear the stack down again.
#
#   scripts/docs-screenshots.sh [outdir]      # default: docs/screenshots
#
# PORT_BASE (default 5000): the app on 127.0.0.1:PORT_BASE.
# COMPOSE_PROJECT_NAME (default bank-of-tina_docs): never the checkout's live
# `bank-of-tina` project. ARTIFACTS: where Playwright's test results go
# (default: a temp dir). DOCS_LANGS (default "en de"): which screenshot sets.
# The stack uses named volumes only (docker-compose.e2e.yml), never the
# checkout's mariadb-data/ or uploads/. Node + `npm ci` in e2e/ are the caller's.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUT="$(mkdir -p "${1:-docs/screenshots}" && cd "${1:-docs/screenshots}" && pwd)"
ARTIFACTS="${ARTIFACTS:-$(mktemp -d)}"
export PORT_BASE="${PORT_BASE:-5000}"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bank-of-tina_docs}"

case "$COMPOSE_PROJECT_NAME" in
  bank-of-tina | phytotron | phytotron-dev | vib | fileheron | keyb-dev)
    echo "docs-screenshots: refusing the live project name '$COMPOSE_PROJECT_NAME'" >&2
    exit 1 ;;
esac

# Compose requires these (${VAR:?}); test-only values. Exported values win over a .env.
export SECRET_KEY=docs-secret-key-not-a-secret DB_PASSWORD=docs-db-not-a-secret
export DB_ROOT_PASSWORD=docs-root-not-a-secret DB_USER=tina DB_NAME=bank_of_tina

compose() { docker compose -f docker-compose.yml -f docker-compose.e2e.yml "$@"; }
teardown() {
  rc=$?
  [ "$rc" = 0 ] || compose logs --tail=200 >"$ARTIFACTS/stack.log" 2>&1 || true
  compose down -v --remove-orphans --rmi local || true
  exit "$rc"
}
trap teardown EXIT

compose build web
for lang in ${DOCS_LANGS:-en de}; do
  # A fresh stack per language: the demo data is seeded in the UI's language.
  compose down -v --remove-orphans
  compose up -d --wait
  (cd e2e && E2E_BASE_URL="http://localhost:$PORT_BASE" DOCS_SCREENSHOT_DIR="$OUT" \
    DOCS_WEB_CONTAINER="$COMPOSE_PROJECT_NAME-web" \
    npx playwright test -c playwright.docs.config.ts --project "$lang" --output "$ARTIFACTS/test-results-$lang")
done
echo "docs-screenshots: $(find "$OUT" -name '*.png' | wc -l) PNGs in $OUT"
