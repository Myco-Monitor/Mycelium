"""
Sentinel Device API Client for Mycelium

This module provides a client for interacting with Sentinel devices — the
grower-environment air-quality monitor (SEN66 PM/VOC/NOx/CO2/T/RH + BMP581
pressure) that sits outside the grow tents.

Endpoints implemented:
- GET /api/readings/latest - Latest cached reading (also carries firmware_version)
- GET /api/diagnostics - System health snapshot (firmware 1.1.0+)

Differences from Spore worth knowing:
- Every sensor channel may be JSON null (channel unavailable: sensor warming
  up or faulted). Nulls are passed through as None, never coerced to 0.
- When the device has no reading yet the reply is a reduced shape carrying
  "error": "no data" and no measurement keys at all.
- There is no /api/status; the running firmware version rides along in
  /api/readings/latest instead.
- "timestamp" is Unix seconds and 0 until the device's NTP sync completes;
  "age_sec" (monotonic uptime delta) is the reliable freshness signal.
"""

import logging
import math
from typing import Dict, Any, Optional

from api.clients.base_client import BaseApiClient, ApiError

# Sensor channels in /api/readings/latest, all float|null.
CHANNELS = (
    "co2",
    "temperature",
    "humidity",
    "pm1",
    "pm2_5",
    "pm4",
    "pm10",
    "voc",
    "nox",
    "pressure_hpa",
)


def _num(value) -> Optional[float]:
    """Coerce a JSON number to float, mapping null/NaN/garbage to None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


class SentinelClient(BaseApiClient):
    """
    Client for interacting with Sentinel devices.

    Attributes:
        device_name (str): Name of the device
        device_id (int): Database ID of the device
    """

    def __init__(
        self,
        base_url: str,
        device_name: str,
        device_id: int,
        timeout: int = 10,
        max_retries: int = 3,
        retry_delay: int = 1,
        use_tls: bool = False,
    ):
        """
        Initialize the Sentinel client.

        Args:
            base_url (str): Base URL for the device API (e.g., "https://sentinel-0001.local")
            device_name (str): Name of the device
            device_id (int): Database ID of the device
            timeout (int): Default timeout for requests in seconds
            max_retries (int): Maximum number of retries for failed requests
            retry_delay (int): Initial delay between retries in seconds
            use_tls (bool): Whether to use HTTPS with MycoMonitor CA cert
        """
        super().__init__(
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            use_tls=use_tls,
            # Same 3-socket HTTPS server as Spore: about 10 requests per second
            request_limit=10,
            request_period=1,
        )
        self.device_name = device_name
        self.device_id = device_id
        self.logger = logging.getLogger(f"api.SentinelClient.{device_name}")

    async def check_connection(self) -> bool:
        """
        Check if the Sentinel device is reachable.

        Returns:
            bool: True if the device is reachable, False otherwise
        """
        try:
            await self.get_latest_reading()
            return True
        except ApiError:
            return False

    async def get_latest_reading(self) -> Dict[str, Any]:
        """
        Get the latest sensor reading from the device.

        Returns:
            Dict[str, Any]: The latest reading with keys:
                - device_name (str)
                - firmware_version (str): running image version ("" if absent)
                - error (str|None): "no data" when the device has no reading yet
                - sen66_ok / bmp581_ok (bool): sensor health flags
                - age_sec (int|None): seconds since the reading was cached
                - timestamp (int): Unix seconds, 0 until NTP sync
                - co2, temperature, humidity, pm1, pm2_5, pm4, pm10, voc, nox,
                  pressure_hpa (float|None): sensor channels, None = unavailable

        Raises:
            ApiError: If the request fails
        """
        try:
            response = await self.get("/api/readings/latest", parse_json=True)
        except ApiError as e:
            self.logger.error(f"Failed to get latest reading: {e}")
            raise
        if not isinstance(response, dict):
            response = {}

        reading = {
            "device_name": response.get("device_name", self.device_name),
            "firmware_version": response.get("firmware_version") or "",
            "error": response.get("error"),
            "sen66_ok": bool(response.get("sen66_ok", False)),
            "bmp581_ok": bool(response.get("bmp581_ok", False)),
            "age_sec": response.get("age_sec"),
            "timestamp": response.get("timestamp", 0),
        }
        for channel in CHANNELS:
            reading[channel] = _num(response.get(channel))
        return reading

    async def get_diagnostics(self) -> Dict[str, Any]:
        """
        Get device diagnostics from /api/diagnostics (firmware 1.1.0+).

        Returns:
            Dict[str, Any]: Diagnostics JSON including a "system" object
                (uptime_sec, heap_free_kb, heap_min_free_kb, wifi_rssi_dbm),
                a "sensors" object (sen66_ok, bmp581_ok), and recent errors.

        Raises:
            ApiError: If the request fails (RESOURCE_NOT_FOUND on older firmware)
        """
        try:
            return await self.get("/api/diagnostics", parse_json=True)
        except ApiError as e:
            self.logger.debug(f"Failed to get device diagnostics: {e}")
            raise
