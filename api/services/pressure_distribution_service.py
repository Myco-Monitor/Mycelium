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
        self._last_pressure: Dict[int, float] = {}  # hyphae_id -> last pressure hPa
        self._last_weather_pressure: Dict[
            int, int
        ] = {}  # spore device_id -> last pushed hPa

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
        associated = [s for s in spores if s.get("hyphae_id") == hyphae_id]

        if not associated:
            return

        self.logger.info(
            f"Distributing pressure {pressure_hpa} hPa from Hyphae {hyphae_id} "
            f"to {len(associated)} Spore(s)"
        )

        tasks = [
            self._push_pressure_to_spore(spore, pressure_hpa) for spore in associated
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def distribute_weather_pressure(
        self,
        farm_id: int,
        sea_level_hpa: Optional[float],
        grnd_level_hpa: Optional[float],
    ):
        """
        Push OpenWeatherMap-derived ambient pressure to opted-in Spores.

        Targets Spores that (a) belong to this farm, (b) have weather pressure
        relay enabled, and (c) have NO linked Hyphae — a linked Hyphae's local
        barometer always wins, so those Spores are skipped here.

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
            if s.get("farm_id") == farm_id
            and s.get("weather_pressure_enabled")
            and not s.get("hyphae_id")
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

            pressure_int = int(round(pressure_hpa))

            # Skip if unchanged since last push to this Spore.
            if self._last_weather_pressure.get(spore["device_id"]) == pressure_int:
                continue
            self._last_weather_pressure[spore["device_id"]] = pressure_int

            tasks.append(self._push_pressure_to_spore(spore, pressure_int))

        if not tasks:
            return

        self.logger.info(
            f"Distributing weather pressure to {len(tasks)} Spore(s) on farm {farm_id} "
            f"(grnd_level={grnd_level_hpa}, sea_level={sea_level_hpa})"
        )
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _push_pressure_to_spore(self, spore: Dict[str, Any], pressure_hpa: float):
        """Push pressure to a single Spore device."""
        ip = spore.get("hostname")
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
                    json={"pressure": int(pressure_hpa)},
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
