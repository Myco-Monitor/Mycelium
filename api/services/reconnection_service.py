"""
Data Reconnection Service for Mycelium

When a device transitions from offline to online, pulls its cached
readings to fill in data gaps from the offline period.

- Spore: GET /api/readings/raw/all and GET /api/readings/ema/all
- Hyphae: GET /api/pressure/history and GET /api/errors/history
"""

import logging
from typing import Set

from storage.tables.device_spore import get_device_spore
from storage.tables.device_hyphae import get_device_hyphae


class ReconnectionService:
    """Pulls cached data from devices after they come back online."""

    def __init__(self):
        self.logger = logging.getLogger("api.ReconnectionService")
        # Track which devices were offline last check
        self._offline_devices: Set[str] = set()  # "spore:id" or "hyphae:id"

    def mark_offline(self, device_type: str, device_id: int):
        """Mark a device as offline for reconnection tracking."""
        self._offline_devices.add(f"{device_type}:{device_id}")

    def mark_online(self, device_type: str, device_id: int) -> bool:
        """
        Mark a device as online. Returns True if it was previously offline
        (indicating a reconnection event that should trigger data pull).
        """
        key = f"{device_type}:{device_id}"
        was_offline = key in self._offline_devices
        self._offline_devices.discard(key)
        return was_offline

    async def handle_reconnection(self, device_type: str, device_id: int):
        """
        Pull cached data from a device that just came back online.

        Should be called by the polling service when a device transitions
        from offline to online.
        """
        self.logger.info(
            f"Reconnection detected: {device_type} {device_id} — pulling cached data"
        )

        if device_type == "spore":
            await self._pull_spore_cached_data(device_id)
        elif device_type == "hyphae":
            await self._pull_hyphae_cached_data(device_id)

    async def _pull_spore_cached_data(self, device_id: int):
        """Pull cached readings from a Spore device."""
        device = get_device_spore(device_id)
        if not device:
            return

        ip = device.get("hostname")
        if not ip:
            return

        session = await self._create_session()
        try:
            # Pull raw readings cache
            async with session.get(
                f"https://{ip}/api/readings/raw/all",
                timeout=__import__("aiohttp").ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    readings = (
                        data if isinstance(data, list) else data.get("readings", [])
                    )
                    self.logger.info(
                        f"Pulled {len(readings)} cached raw readings from Spore {device_id}"
                    )
                    # Store readings
                    self._store_spore_readings(device_id, readings)

            # Pull EMA readings cache
            async with session.get(
                f"https://{ip}/api/readings/ema/all",
                timeout=__import__("aiohttp").ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    readings = (
                        data if isinstance(data, list) else data.get("readings", [])
                    )
                    self.logger.info(
                        f"Pulled {len(readings)} cached EMA readings from Spore {device_id}"
                    )

        except Exception as e:
            self.logger.warning(
                f"Failed to pull cached data from Spore {device_id}: {e}"
            )
        finally:
            await session.close()

    async def _pull_hyphae_cached_data(self, device_id: int):
        """Pull cached data from a Hyphae device."""
        device = get_device_hyphae(device_id)
        if not device:
            return

        ip = device.get("hostname")
        if not ip:
            return

        session = await self._create_session()
        try:
            # Pull pressure history
            async with session.get(
                f"https://{ip}/api/pressure/history",
                timeout=__import__("aiohttp").ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    entries = (
                        data if isinstance(data, list) else data.get("history", [])
                    )
                    self.logger.info(
                        f"Pulled {len(entries)} cached pressure entries from Hyphae {device_id}"
                    )

            # Pull error history
            async with session.get(
                f"https://{ip}/api/errors/history",
                timeout=__import__("aiohttp").ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    errors = data if isinstance(data, list) else data.get("errors", [])
                    self.logger.info(
                        f"Pulled {len(errors)} cached error entries from Hyphae {device_id}"
                    )

        except Exception as e:
            self.logger.warning(
                f"Failed to pull cached data from Hyphae {device_id}: {e}"
            )
        finally:
            await session.close()

    async def _create_session(self):
        """Create an aiohttp session with MycoMonitor CA cert."""
        from api.clients.base_client import create_device_ssl_context, device_connector
        import aiohttp

        connector = device_connector(create_device_ssl_context())
        return aiohttp.ClientSession(connector=connector)

    def _store_spore_readings(self, device_id: int, readings: list):
        """Store cached spore readings into the database."""
        try:
            from storage.tables.readings_spore import create_reading

            for reading in readings:
                create_reading(
                    device_id=device_id,
                    temperature=reading.get("temperature"),
                    humidity=reading.get("humidity"),
                    co2=reading.get("co2"),
                    reading_ts=reading.get("timestamp"),
                )
        except Exception as e:
            self.logger.warning(
                f"Failed to store cached readings for Spore {device_id}: {e}"
            )
