#!/usr/bin/env bash
# mycelium-update.sh - privileged "apply a release tag" primitive for a MANAGED
# Mycelium appliance (e.g. the Raspberry Pi hub image).
#
# This is the one privileged step of the in-field self-update feature. Its source
# of truth lives here in the Mycelium repo (the feature is Mycelium's), but on the
# appliance it is installed to a ROOT-OWNED path and the unprivileged `mycelium`
# app user is granted sudo to run ONLY this script (see the Pi-Image sudoers rule).
# It must therefore stay minimal and validate its input strictly.
#
# Invoked by the app as:  sudo -n <installed-path>/mycelium-update.sh
# The target tag is read from a request FILE (not argv) so the sudoers rule can be
# argument-free and un-abusable.
#
# Flow: read+validate tag -> fetch+checkout -> rebuild venv -> smoke test
#       -> (auto-rollback on failure) -> update .baked-version -> deferred restart.
# Emits a single JSON object on stdout describing the outcome.
#
# Appliance layout is fixed (this only runs when MYCELIUM_MANAGED=1):
set -uo pipefail

APP_DIR=/opt/mycelium/app
VENV=/opt/mycelium/venv
APP_USER=mycelium
SERVICE=mycelium.service
REQUEST=/run/mycelium/update-request.json
BAKED=/opt/mycelium/.baked-version

# git run against the app checkout; safe.directory because the repo is owned by
# `mycelium` while we run as root (git would otherwise refuse "dubious ownership").
gitc() { git -C "$APP_DIR" -c safe.directory="$APP_DIR" "$@"; }

json_escape() { printf '%s' "$1" | jq -R -s .; }
fail_json() { printf '{"result":"failed","error":%s}\n' "$(json_escape "$*")"; exit 1; }

current_version() { "$VENV/bin/python" -c 'import version; print(version.__version__)' 2>/dev/null || echo unknown; }

# Fetch + hard-checkout a tag and rebuild the venv. Returns non-zero on any step.
install_ref() {
    local ref="$1"
    # All build chatter goes to stderr so stdout carries only the final JSON.
    gitc fetch --tags --force --prune origin       >&2 || return 1
    gitc checkout --force --detach "refs/tags/$ref" >&2 || return 1
    "$VENV/bin/pip" install --quiet -r "$APP_DIR/requirements.txt" >&2 || return 1
    chown -R "$APP_USER:$APP_USER" "$APP_DIR" "$VENV" 2>/dev/null || true
    return 0
}

# Smoke test a freshly installed ref: the venv imports the framework AND the
# checkout reports the expected version. Deliberately NOT `pip check` (the app's
# numpy/pandas pins can flag benign resolver noise and cause false rollbacks).
smoke_ok() {
    local expected="$1"
    "$VENV/bin/python" -c \
        'import sys, version, nicegui; sys.exit(0 if version.__version__ == sys.argv[1] else 3)' \
        "$expected" >/dev/null 2>&1
}

# --- Preconditions ------------------------------------------------------------
[ "$(id -u)" -eq 0 ] || { echo "must run as root" >&2; exit 1; }
for c in jq git; do command -v "$c" >/dev/null || { echo "$c not installed" >&2; exit 1; }; done
[ -d "$APP_DIR/.git" ]     || fail_json "no git checkout at $APP_DIR"
[ -x "$VENV/bin/python" ]  || fail_json "no venv python at $VENV"

# --- Read + strictly validate the requested tag -------------------------------
[ -f "$REQUEST" ] || fail_json "no update request at $REQUEST"
REF="$(jq -r '.ref // ""' "$REQUEST" 2>/dev/null || echo "")"
rm -f "$REQUEST"
printf '%s' "$REF" | grep -qE '^v[0-9]+\.[0-9]+\.[0-9]+$' \
    || fail_json "invalid or missing tag: '${REF}' (expected vX.Y.Z)"

# Rollback anchor: the currently checked-out tag (fallback to .baked-version).
prev_ref="$(gitc describe --tags --exact-match 2>/dev/null || true)"
[ -n "$prev_ref" ] || prev_ref="$(sed -n 's/^ref=//p' "$BAKED" 2>/dev/null | head -n1)"
from_version="$(current_version)"

# --- Apply --------------------------------------------------------------------
if ! install_ref "$REF"; then
    if [ -n "$prev_ref" ] && install_ref "$prev_ref"; then
        printf '{"result":"rolled_back","from":"%s","to":"%s","reason":%s}\n' \
            "$from_version" "$prev_ref" "$(json_escape "install of $REF failed")"
        exit 1
    fi
    fail_json "install of $REF failed and rollback failed"
fi

# --- Smoke test before we commit to it ----------------------------------------
new_version="$(current_version)"
expected="${REF#v}"
if ! smoke_ok "$expected"; then
    if [ -n "$prev_ref" ] && install_ref "$prev_ref"; then
        printf '{"result":"rolled_back","from":"%s","to":"%s","reason":%s}\n' \
            "$from_version" "$prev_ref" "$(json_escape "smoke test failed for $REF (got version '$new_version')")"
        exit 1
    fi
    fail_json "smoke test failed for $REF and rollback failed"
fi

# --- Record what we installed (mirror install-mycelium.sh's .baked-version) ----
sha="$(gitc rev-parse --short HEAD 2>/dev/null || echo unknown)"
repo="$(gitc remote get-url origin 2>/dev/null || echo unknown)"
printf 'version=%s\nref=%s\nsha=%s\nrepo=%s\n' "$new_version" "$REF" "$sha" "$repo" > "$BAKED"
chown "$APP_USER:$APP_USER" "$BAKED" 2>/dev/null || true

# --- Deferred restart so the caller gets this response before its service dies --
systemd-run --on-active=5 systemctl restart "$SERVICE" >/dev/null 2>&1 \
    || ( sleep 5; systemctl restart "$SERVICE" ) &

printf '{"result":"success","from":"%s","to":"%s","ref":"%s","restart_in_s":5}\n' \
    "$from_version" "$new_version" "$REF"
exit 0
