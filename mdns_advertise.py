"""Advertise the Mycelium host as ``mycelium.local`` on the LAN via mDNS.

Publishes an mDNS record so any computer on the network can reach the UI at
``https://mycelium.local:<port>`` -- consistent with the device naming scheme
(``spore-NNNN.local`` / ``hyphae-NNNN.local``). Degrades gracefully: if zeroconf
is missing or the host is offline, it just doesn't advertise (the cert SAN still
covers the real hostname and LAN IP, so those URLs keep working).
"""

import logging
import socket

from cert_manager import primary_lan_ip

logger = logging.getLogger("mycelium.mdns")

_zc = None
_info = None


def start(port: int) -> bool:
    """Register ``mycelium.local`` -> this host:port over mDNS. Returns success."""
    global _zc, _info
    try:
        from zeroconf import Zeroconf, ServiceInfo
    except ImportError:
        logger.warning("zeroconf not installed; not advertising mycelium.local")
        return False

    ip = primary_lan_ip()
    if not ip:
        logger.warning("No LAN IP found; not advertising mycelium.local")
        return False

    try:
        _zc = Zeroconf()
        _info = ServiceInfo(
            "_https._tcp.local.",
            "Mycelium._https._tcp.local.",
            addresses=[socket.inet_aton(ip)],
            port=port,
            server="mycelium.local.",
            properties={"path": "/"},
        )
        _zc.register_service(_info)
        logger.info("Advertising mycelium.local -> %s:%d via mDNS", ip, port)
        return True
    except Exception as e:  # noqa: BLE001 - advertising is best-effort
        logger.warning("Failed to advertise mycelium.local: %s", e)
        stop()
        return False


def stop() -> None:
    """Unregister and tear down the mDNS advertisement."""
    global _zc, _info
    try:
        if _zc and _info:
            _zc.unregister_service(_info)
        if _zc:
            _zc.close()
    except Exception:  # noqa: BLE001
        pass
    _zc = None
    _info = None
