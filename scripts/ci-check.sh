#!/usr/bin/env bash
#
# ci-check.sh — strict CI gate. Any finding or missing tool fails the run.
#
# Usage:
#   scripts/ci-check.sh          ruff lint, ruff format, bandit, tracked-secret scan
#   scripts/ci-check.sh audit    pip-audit against requirements.txt
#
# Tools come from requirements-dev.txt; this script never installs anything.

set -euo pipefail
cd "$(dirname "$0")/.."

mode="${1:-lint}"

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "FAIL: $1 is not installed (pip install -r requirements-dev.txt)" >&2; exit 1; }
}

if [ "$mode" = "audit" ]; then
  need pip-audit
  echo "== pip-audit =="
  pip-audit -r requirements.txt
  echo "All checks passed."
  exit 0
elif [ "$mode" != "lint" ]; then
  echo "unknown mode: $mode (expected: lint | audit)" >&2
  exit 2
fi

need ruff
need bandit

echo "== ruff lint =="
ruff check .

echo "== ruff format (check only) =="
ruff format --check .

echo "== bandit (medium severity and above) =="
bandit -r . -q -ll \
  -x ./data,./logs,./.git,./__pycache__,./.ruff_cache,./.nicegui,./mycelium,./venv,./.venv

echo "== tracked-secret scan =="
leaks=0
while IFS= read -r f; do
  case "$f" in
    config/ca_root.pem) ;;  # the device CA public root is intentionally tracked
    *.pem|*.key|*pin_key|*storage_secret)
      echo "FAIL: tracked sensitive file: $f" >&2; leaks=1 ;;
  esac
done < <(git ls-files)
if git grep -lI -e 'PRIVATE KEY-----' -- . ':!scripts/ci-check.sh' >/dev/null; then
  echo "FAIL: a tracked file contains a PRIVATE KEY block" >&2; leaks=1
fi
if git ls-files | grep -qE '\.db$|^data/'; then
  echo "FAIL: database or data/ is tracked by git" >&2; leaks=1
fi
[ "$leaks" = 0 ] || exit 1

echo "All checks passed."
