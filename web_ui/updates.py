"""Managed-appliance detection.

The in-field self-update UI (Settings -> Hub Updates) and the privileged updater
only make sense on a managed appliance (the Raspberry Pi hub image), where the app
runs under systemd as an unprivileged user with a root-owned updater it may invoke
via sudo. On a plain laptop/dev install none of that exists, so the UI must stay
hidden and the update path must never be offered.
"""

import os
from pathlib import Path

# Installed root-owned by the Pi-Image build (see build-image.sh); its presence is
# the on-disk signal that the appliance provisioned the update path.
UPDATER_PATH = Path("/usr/local/sbin/mycelium-update.sh")


def is_managed_appliance() -> bool:
    """True only when running as the managed hub appliance.

    Primary signal is the ``MYCELIUM_MANAGED=1`` environment variable set by the
    appliance's systemd unit (mycelium.service). The updater-script check is a
    fallback so detection still holds if someone launches run.py by hand on the Pi
    outside systemd. Both are false on a laptop, so the update UI never appears
    there.
    """
    return os.environ.get("MYCELIUM_MANAGED") == "1" or UPDATER_PATH.exists()
