"""
Ambient Pressure Distribution Service for Mycelium

After each Hyphae BMP581 pressure reading, pushes the latest pressure
to all associated Spore devices via POST /api/ambient-pressure.

This centralizes the pressure distribution through Mycelium instead of
relying on direct Hyphae-to-Spore communication.
"""

import asyncio
import logging
from typing import Dict, Any, Optional

from storage.tables.device_spore import get_all_device_spore


def sea_level_to_station_pressure(sea_level_hpa: float, altitude_m: float) -> float:
    """
    Approximate local station pressure from sea-level pressure and altitude.

    Uses the international barometric formula (ISA, constant 288.15 K). This is
    an approximation that ignores local temperature, which is acceptable for
    CO2 sensor pressure compensation.

    Args:
        sea_level_hpa: Sea-level-reduced pressure (OWM main.pressure), hPa.
        altitude_m: Device altitude above sea level, meters.

    Returns:
        float: Approximate station (local) pressure in hPa.
    """
    return sea_level_hpa * (1.0 - (0.0065 * altitude_m) / 288.15) ** 5.25588


class PressureDistributionService:
    """Distributes ambient pressure readings from Hyphae to associated Spores."""

    def __init__(self):
        self.logger = logging.getLogger("api.PressureDistributionService")
        # Last whole-hPa value actually sent to each Spore (device_id -> int).
        # Enforces "send a whole value, and only when it changed by >= 1 hPa".
        self._last_sent: Dict[int, int] = {}
        # Coarse per-Hyphae guard (whole hPa) to skip the sweep when unchanged.
        self._last_pressure: Dict[int, int] = {}

    async def distribute_pressure(self, hyphae_id: int, pressure_hpa: float):
        """
        Push ambient pressure to all Spore devices associated with this Hyphae.

        Args:
            hyphae_id: Database ID of the Hyphae device that reported pressure.
            pressure_hpa: Pressure in hectopascals from BMP581.
        """
        value = int(round(pressure_hpa))
        # Skip the whole sweep if this Hyphae's whole-hPa value hasn't changed.
        if self._last_pressure.get(hyphae_id) == value:
            return
        self._last_pressure[hyphae_id] = value

        # Get all Spore devices (filter to those associated with this Hyphae)
        spores = get_all_device_spore()
        associated = [s for s in spores if s.get("hyphae_id") == hyphae_id]

        if not associated:
            return

        results = await asyncio.gather(
            *[self._push_pressure_to_spore(spore, value) for spore in associated],
            return_exceptions=True,
        )
        sent = sum(1 for r in results if r is True)
        if sent:
            self.logger.info(
                f"Distributed pressure {value} hPa from Hyphae {hyphae_id} "
                f"to {sent} Spore(s)"
            )

    async def distribute_weather_pressure(
        self,
        farm_id: Optional[int],
        sea_level_hpa: Optional[float],
        grnd_level_hpa: Optional[float],
    ):
        """
        Push OpenWeatherMap-derived ambient pressure to opted-in Spores.

        Targets Spores that (a) belong to this farm — or any farm when farm_id is
        None, since user_settings.farm_id is not populated today — (b) have weather
        pressure relay enabled, and (c) have NO linked Hyphae — a linked Hyphae's
        local barometer always wins, so those Spores are skipped here.

        Pressure value, per Spore:
          - Use OWM grnd_level (true ground-level pressure) when available.
          - Otherwise approximate station pressure from sea-level pressure using
            the Spore's configured altitude_m.
          - If neither is available, skip the Spore (it keeps its 1013 hPa
            sea-level default rather than receiving a misleading value).

        Args:
            farm_id: Farm whose Spores should receive this location's weather.
            sea_level_hpa: OWM main.pressure (sea-level-reduced), may be None.
            grnd_level_hpa: OWM main.grnd_level, may be None.
        """
        spores = get_all_device_spore()
        eligible = [
            s
            for s in spores
            if (farm_id is None or s.get("farm_id") == farm_id)
            and s.get("weather_pressure_enabled")
            and not s.get("hyphae_id")
            and s.get("is_online")  # can't push to an unreachable device
        ]
        if not eligible:
            return

        tasks = []
        for spore in eligible:
            if grnd_level_hpa is not None:
                pressure_hpa = grnd_level_hpa
            elif sea_level_hpa is not None and spore.get("altitude_m") is not None:
                pressure_hpa = sea_level_to_station_pressure(
                    sea_level_hpa, spore["altitude_m"]
                )
            else:
                # No usable pressure for this Spore (no grnd_level, no altitude).
                continue

            # _push_pressure_to_spore rounds to a whole hPa and only sends when it
            # changed by >= 1 from the last value sent to this Spore.
            tasks.append(self._push_pressure_to_spore(spore, pressure_hpa))

        if not tasks:
            return

        results = await asyncio.gather(*tasks, return_exceptions=True)
        sent = sum(1 for r in results if r is True)
        if sent:
            self.logger.info(
                f"Distributed weather pressure to {sent} Spore(s) "
                f"(grnd_level={grnd_level_hpa}, sea_level={sea_level_hpa})"
            )

    async def _push_pressure_to_spore(
        self, spore: Dict[str, Any], pressure_hpa: float
    ) -> bool:
        """Push a pressure value to one Spore.

        Enforces the two rules for what a Spore receives:
          1. A whole hPa value (the firmware parses the body with strtol).
          2. Only sent when it changed by >= 1 hPa from the last value sent to
             this Spore (no resend on an unchanged whole value).

        The "last sent" value is recorded only on a successful (HTTP 200) push, so
        a failed push is retried on the next cycle rather than being suppressed.

        Returns True if a value was actually sent.
        """
        ip = spore.get("hostname")
        if not ip:
            return False

        device_id = spore.get("device_id")
        value = int(round(pressure_hpa))  # rule 1: whole hPa only

        # rule 2: skip if unchanged from the last value sent to this Spore.
        if device_id is not None and self._last_sent.get(device_id) == value:
            return False

        import aiohttp
        from api.clients.base_client import device_connector

        # device_connector forces IPv4 + glibc/Avahi resolution so the device's
        # .local hostname resolves under uvloop (see _SystemResolver).
        connector = device_connector()
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    f"https://{ip}/api/ambient-pressure",
                    data=str(value),
                    headers={"Content-Type": "text/plain"},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        if device_id is not None:
                            self._last_sent[device_id] = value
                        self.logger.debug(
                            f"Pressure {value} hPa pushed to Spore {spore.get('device_name', ip)}"
                        )
                        return True
                    self.logger.warning(
                        f"Failed to push pressure to Spore {ip}: HTTP {resp.status}"
                    )
                    return False
        except Exception as e:
            self.logger.warning(f"Failed to push pressure to Spore {ip}: {e}")
            return False
