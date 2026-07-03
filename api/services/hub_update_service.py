"""Hub self-update service (managed appliance only).

Owns the in-field "update the hub to the newest release" logic for the Mycelium
app. The *version check* is pure Python here (an anonymous ``git ls-remote``
against the checkout's own origin) so it has no dependency on the appliance layer.
*Applying* an update is the one privileged step: it is delegated to a root-owned
script the appliance grants us sudo for (see deploy/mycelium-update.sh and the
Pi-Image sudoers rule). The target tag is handed to that script via a request
file, never on the command line.

All functions here are blocking (subprocess/network) and are meant to be called
from the UI via ``nicegui.run.io_bound`` so they never block the event loop.
"""

import json
import logging
import os
import re
import subprocess
from pathlib import Path

from version import __version__

logger = logging.getLogger("api.HubUpdateService")

# Appliance layout (see Pi-Image). Overridable via env for testing.
APP_DIR = os.environ.get("MYCELIUM_APP_DIR", "/opt/mycelium/app")
UPDATER_SCRIPT = os.environ.get("MYCELIUM_UPDATER", "/usr/local/sbin/mycelium-update.sh")
REQUEST_PATH = os.environ.get("MYCELIUM_UPDATE_REQUEST", "/run/mycelium/update-request.json")

_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def get_current_version() -> str:
    """The running app version (version.py is the single source of truth)."""
    return __version__


def _semver_tuple(v: str) -> tuple:
    """Parse 'X.Y.Z' -> (X, Y, Z); unparseable -> (0, 0, 0) so it never wins."""
    try:
        return tuple(int(p) for p in v.split("."))
    except (ValueError, AttributeError):
        return (0, 0, 0)


def _repo_url() -> str:
    """Origin URL of the app checkout, so the check works against whatever repo
    this hub was built from (fork-safe, no hardcoded URL)."""
    out = subprocess.run(
        ["git", "-C", APP_DIR, "remote", "get-url", "origin"],
        capture_output=True, text=True, timeout=10,
    )
    return out.stdout.strip()


def check_for_update() -> dict:
    """Compare the running version to the newest vX.Y.Z release tag on origin.

    Returns a dict with current_version, latest_version, latest_ref,
    update_available; or an 'error' key on failure. Never raises.
    """
    current = get_current_version()
    try:
        url = _repo_url()
        if not url:
            return {"current_version": current, "error": "no git origin on this install"}
        out = subprocess.run(
            ["git", "ls-remote", "--tags", "--refs", url, "v*"],
            capture_output=True, text=True, timeout=25,
        )
        if out.returncode != 0:
            return {"current_version": current, "error": (out.stderr or "ls-remote failed").strip()}

        tags = []
        for line in out.stdout.splitlines():
            name = line.strip().split("/")[-1] if line.strip() else ""
            if _TAG_RE.match(name):
                tags.append(name)
        if not tags:
            return {
                "current_version": current, "latest_version": current,
                "latest_ref": None, "update_available": False,
            }

        latest_ref = max(tags, key=lambda t: _semver_tuple(t[1:]))
        latest_version = latest_ref[1:]
        update_available = _semver_tuple(latest_version) > _semver_tuple(current)
        return {
            "current_version": current,
            "latest_version": latest_version,
            "latest_ref": latest_ref,
            "update_available": update_available,
        }
    except subprocess.TimeoutExpired:
        return {"current_version": current, "error": "timed out contacting the release server"}
    except Exception as e:  # noqa: BLE001 - surface any failure to the UI, don't crash
        logger.exception("check_for_update failed")
        return {"current_version": current, "error": str(e)}


def apply_update(ref: str) -> dict:
    """Apply release tag `ref` via the privileged updater. Returns the script's
    JSON result: {"result": "success"|"failed"|"rolled_back", ...}. Never raises.

    Writes the requested tag to the request file, then runs the root-owned script
    with `sudo -n`. The script validates the tag again, rebuilds, smoke-tests,
    auto-rolls-back on failure, and defers the service restart.
    """
    if not _TAG_RE.match(ref or ""):
        return {"result": "failed", "error": f"invalid tag '{ref}' (expected vX.Y.Z)"}

    try:
        # /run/mycelium is the app service's RuntimeDirectory (0700, mycelium-owned).
        Path(REQUEST_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(REQUEST_PATH, "w") as f:
            json.dump({"ref": ref}, f)
    except OSError as e:
        return {"result": "failed", "error": f"could not stage update request: {e}"}

    try:
        proc = subprocess.run(
            ["sudo", "-n", UPDATER_SCRIPT],
            capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        return {"result": "failed", "error": "update timed out"}
    except Exception as e:  # noqa: BLE001
        logger.exception("apply_update failed to invoke updater")
        return {"result": "failed", "error": str(e)}

    # The script prints exactly one JSON line on stdout (build output goes to
    # stderr). Parse the last non-empty stdout line; fall back to stderr on noise.
    for line in reversed(proc.stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            break
    detail = (proc.stderr or proc.stdout or "no output").strip()
    return {"result": "failed", "error": f"updater returned no result (rc={proc.returncode}): {detail[:500]}"}
