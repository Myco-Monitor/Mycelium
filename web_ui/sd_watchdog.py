"""systemd watchdog heartbeat, sent from the asyncio event loop.

A managed hub runs under a unit with ``WatchdogSec=`` (see the Pi-Image
``mycelium.service``). systemd then hands the process ``$NOTIFY_SOCKET`` and
``$WATCHDOG_USEC`` and expects a ``WATCHDOG=1`` datagram at least that often;
a late one gets the service killed and, with ``Restart=``, started again.

The heartbeat is an asyncio task on the one event loop that serves every
page, the REST API, and device polling, so what systemd measures is that
loop's liveness. A handler that wedges the loop leaves a hub that answers
ping but never serves a page, never polls a device, and never crashes — the
one failure ``Restart=on-failure`` cannot see. With the heartbeat it is a
restart a couple of minutes later instead of a power cycle.

Outside systemd, or under a unit without ``WatchdogSec=``, the environment
variables are absent and start() is a no-op. Pure stdlib: the notify
protocol is one datagram on a unix socket (sd_notify(3)).
"""

import asyncio
import logging
import os
import socket
from typing import Optional

logger = logging.getLogger(__name__)

# Heartbeats per deadline. Three leaves two missed beats of slack for
# scheduling jitter before a genuinely stuck loop is called stuck.
BEATS_PER_DEADLINE = 3


def _notify(sock_path: str, payload: bytes) -> None:
    """Send one sd_notify datagram. A leading '@' means an abstract socket."""
    addr = "\0" + sock_path[1:] if sock_path.startswith("@") else sock_path
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
        sock.connect(addr)
        sock.sendall(payload)


def heartbeat_interval() -> Optional[float]:
    """Seconds between beats, or None when no watchdog is armed for this PID."""
    sock_path = os.environ.get("NOTIFY_SOCKET")
    usec = os.environ.get("WATCHDOG_USEC")
    if not sock_path or not usec:
        return None
    # systemd names the PID it is watching; a forked child must stay quiet
    # so the parent's silence is not masked by it
    pid = os.environ.get("WATCHDOG_PID")
    if pid and pid != str(os.getpid()):
        return None
    try:
        deadline = int(usec) / 1_000_000
    except ValueError:
        return None
    if deadline <= 0:
        return None
    return max(1.0, deadline / BEATS_PER_DEADLINE)


def start() -> Optional[asyncio.Task]:
    """Start the heartbeat task on the running loop; None when not armed.

    Call from an on_startup hook. The task is never cancelled on purpose:
    systemd keeps the deadline armed through shutdown, so the beats must
    continue until the process exits with the loop.
    """
    interval = heartbeat_interval()
    if interval is None:
        return None
    sock_path = os.environ["NOTIFY_SOCKET"]

    async def _beat():
        while True:
            try:
                _notify(sock_path, b"WATCHDOG=1")
            except OSError as e:
                logger.warning(f"systemd watchdog notify failed: {e}")
            await asyncio.sleep(interval)

    logger.info(
        f"systemd watchdog armed: heartbeat every {interval:.0f}s "
        f"(deadline {interval * BEATS_PER_DEADLINE:.0f}s)"
    )
    return asyncio.create_task(_beat())
