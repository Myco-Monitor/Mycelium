"""
Ambient Pressure Distribution Service for Mycelium

After each Hyphae BMP581 pressure reading, pushes the latest pressure
to all associated Spore devices via POST /api/ambient-pressure.

This centralizes the pressure distribution through Mycelium instead of
relying on direct Hyphae-to-Spore communication.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional

from storage.tables.device_spore import get_all_device_spore
from storage.tables.device_hyphae import get_device_hyphae


class PressureDistributionService:
    """Distributes ambient pressure readings from Hyphae to associated Spores."""

    def __init__(self):
        self.logger = logging.getLogger("api.PressureDistributionService")
        self._last_pressure: Dict[int, float] = {}  # hyphae_id -> last pressure hPa

    async def distribute_pressure(self, hyphae_id: int, pressure_hpa: float):
        """
        Push ambient pressure to all Spore devices associated with this Hyphae.

        Args:
            hyphae_id: Database ID of the Hyphae device that reported pressure.
            pressure_hpa: Pressure in hectopascals from BMP581.
        """
        # Skip if pressure hasn't changed
        if self._last_pressure.get(hyphae_id) == pressure_hpa:
            return

        self._last_pressure[hyphae_id] = pressure_hpa

        # Get all Spore devices (filter to those associated with this Hyphae)
        spores = get_all_device_spore()
        associated = [s for s in spores if s.get('hyphae_id') == hyphae_id]

        if not associated:
            return

        self.logger.info(
            f"Distributing pressure {pressure_hpa} hPa from Hyphae {hyphae_id} "
            f"to {len(associated)} Spore(s)"
        )

        tasks = [
            self._push_pressure_to_spore(spore, pressure_hpa)
            for spore in associated
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _push_pressure_to_spore(self, spore: Dict[str, Any], pressure_hpa: float):
        """Push pressure to a single Spore device."""
        ip = spore.get('ip_address')
        if not ip:
            return

        import aiohttp
        from api.clients.base_client import create_device_ssl_context

        ssl_ctx = create_device_ssl_context()
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    f"https://{ip}/api/ambient-pressure",
                    json={'pressure': int(pressure_hpa)},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        self.logger.debug(
                            f"Pressure {pressure_hpa} hPa pushed to Spore {spore.get('device_name', ip)}"
                        )
                    else:
                        self.logger.warning(
                            f"Failed to push pressure to Spore {ip}: HTTP {resp.status}"
                        )
        except Exception as e:
            self.logger.warning(f"Failed to push pressure to Spore {ip}: {e}")
