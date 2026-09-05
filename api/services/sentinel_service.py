"""
Sentinel Data Service for Mycelium

This module provides services for handling Sentinel device data, including:
- Data transformation
- Data storage
- Data validation
- Duplicate detection

Mirrors SporeDataService. The notable differences: every channel may be None
(the firmware reports null for an unavailable channel), a reachable device
with no reading yet answers with an "error" field instead of measurements,
and the running firmware version arrives with every reading (Sentinel has no
/api/status), so it is recorded from the poll itself.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from api.clients.base_client import ApiError, ApiErrorType
from api.clients.sentinel_client import SentinelClient, CHANNELS
from storage.tables.device_sentinel import (
    update_device_status,
    update_device_sentinel,
    update_device_diagnostics,
    get_device_sentinel,
)
from storage.tables.readings_sentinel import create_reading, get_latest_reading

# Sanity ranges per channel; a non-None value outside its range rejects the
# whole reading (Spore parity). None is always allowed — it means "unavailable".
_RANGES = {
    "pm1": (0, 1000),
    "pm2_5": (0, 1000),
    "pm4": (0, 1000),
    "pm10": (0, 1000),
    "co2": (0, 10000),
    "temperature": (-40, 85),
    "humidity": (0, 100),
    "voc": (0, 500),
    "nox": (0, 500),
    "pressure_hpa": (300, 1100),
}

# Reading key -> readings_sentinel column (only temperature is renamed).
_COLUMNS = {channel: channel for channel in CHANNELS}
_COLUMNS["temperature"] = "temp"


class SentinelDataService:
    """
    Service for handling Sentinel device data.

    This service is responsible for:
    - Transforming data from the Sentinel API client
    - Storing data in the database
    - Validating data
    - Detecting and handling duplicates
    """

    def __init__(self):
        """Initialize the Sentinel data service."""
        self.logger = logging.getLogger("api.SentinelDataService")
        self.clients: Dict[int, SentinelClient] = {}
        # Last firmware version written per device, so a version that rides
        # along with every reading costs a DB write only when it changes.
        self._fw_versions: Dict[int, Optional[str]] = {}

    async def initialize_client(self, device_id: int) -> SentinelClient:
        """
        Initialize a Sentinel client for a device.

        Args:
            device_id (int): ID of the device

        Returns:
            SentinelClient: The initialized client

        Raises:
            ValueError: If the device is not found
        """
        device = get_device_sentinel(device_id)
        if not device:
            raise ValueError(f"Device with ID {device_id} not found")

        if device_id not in self.clients:
            base_url = f"https://{device['hostname']}"
            client = SentinelClient(
                base_url=base_url,
                device_name=device["device_name"],
                device_id=device_id,
            )
            self.clients[device_id] = client
            self._fw_versions[device_id] = device.get("firmware_version")
            self.logger.info(
                f"Initialized client for Sentinel device {device['device_name']} ({device_id})"
            )

        return self.clients[device_id]

    async def get_client(self, device_id: int) -> SentinelClient:
        """
        Get a Sentinel client for a device, initializing it if necessary.

        Args:
            device_id (int): ID of the device

        Returns:
            SentinelClient: The client
        """
        if device_id not in self.clients:
            return await self.initialize_client(device_id)
        return self.clients[device_id]

    async def check_device_connection(self, device_id: int) -> bool:
        """
        Check if a device is reachable and record the result.

        Args:
            device_id (int): ID of the device

        Returns:
            bool: True if the device is reachable, False otherwise
        """
        try:
            client = await self.get_client(device_id)
            is_connected = await client.check_connection()
            update_device_status(device_id, 1 if is_connected else 0)
            return is_connected
        except Exception as e:
            self.logger.error(f"Error checking connection for device {device_id}: {e}")
            update_device_status(device_id, 0)
            return False

    async def get_latest_reading(self, device_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch the device's latest reading and store it.

        Raises on transport failure so the polling service owns device status
        and backoff (it distinguishes a transient mDNS miss from a genuine
        outage). A reachable device that has no reading yet ("error" in the
        reply) is NOT a failure: nothing is stored and None is returned.

        Args:
            device_id (int): ID of the device

        Returns:
            Optional[Dict[str, Any]]: The stored reading, or None if nothing
                was stored (no data yet, invalid, or duplicate).
        """
        client = await self.get_client(device_id)
        reading = await client.get_latest_reading()

        self._record_firmware_version(device_id, reading.get("firmware_version"))

        if reading.get("error"):
            self.logger.debug(
                f"Sentinel device {device_id} has no reading yet: {reading['error']}"
            )
            return None

        return await self.store_reading(device_id, reading)

    def _record_firmware_version(self, device_id: int, version: Optional[str]):
        """Persist the running firmware version when it differs from the stored one."""
        version = (version or "").strip()
        if not version or self._fw_versions.get(device_id) == version:
            return
        try:
            device = get_device_sentinel(device_id)
            if device and device.get("firmware_version") != version:
                update_device_sentinel(device_id, firmware_version=version)
                self.logger.info(
                    f"Recorded firmware version {version} for Sentinel device {device_id}"
                )
            self._fw_versions[device_id] = version
        except Exception as e:
            self.logger.warning(
                f"Could not record firmware version for Sentinel device {device_id}: {e}"
            )

    async def refresh_diagnostics(self, device_id: int) -> None:
        """
        Fetch the device's diagnostics snapshot and record it in the DB.

        Reads /api/diagnostics and stores the system stats (WiFi RSSI, heap,
        uptime) on the device row for the health dashboard. Called by the
        polling service at a slower cadence than readings. Never raises:
        failures are logged and the poll cycle continues unaffected. Firmware
        older than 1.1.0 has no such endpoint; that 404 is logged at debug.

        Args:
            device_id (int): ID of the device
        """
        try:
            client = await self.get_client(device_id)
            diagnostics = await client.get_diagnostics()
            system = (
                diagnostics.get("system") if isinstance(diagnostics, dict) else None
            )
            if not isinstance(system, dict):
                self.logger.debug(
                    f"Sentinel device {device_id} returned no diagnostics system object"
                )
                return
            update_device_diagnostics(
                device_id,
                wifi_rssi=system.get("wifi_rssi_dbm"),
                heap_free_kb=system.get("heap_free_kb"),
                heap_min_free_kb=system.get("heap_min_free_kb"),
                uptime_sec=system.get("uptime_sec"),
            )
        except ApiError as e:
            if e.error_type is ApiErrorType.RESOURCE_NOT_FOUND:
                self.logger.debug(
                    f"Sentinel device {device_id} has no /api/diagnostics "
                    "(firmware older than 1.1.0)"
                )
            else:
                self.logger.warning(
                    f"Failed to refresh diagnostics for Sentinel device {device_id}: {e}"
                )
        except Exception as e:
            self.logger.warning(
                f"Failed to refresh diagnostics for Sentinel device {device_id}: {e}"
            )

    async def store_reading(
        self, device_id: int, reading: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Transform and store a reading in the database.

        Args:
            device_id (int): ID of the device
            reading (Dict[str, Any]): Reading from the device client

        Returns:
            Optional[Dict[str, Any]]: The stored reading, or None if the reading
                is invalid or a duplicate
        """
        try:
            if not self._validate_reading(reading):
                self.logger.warning(
                    f"Invalid reading for device {device_id}: {reading}"
                )
                return None

            transformed = self._transform_reading(device_id, reading)

            if self._is_duplicate(device_id, transformed):
                self.logger.debug(
                    f"Duplicate reading for device {device_id}: {transformed}"
                )
                return None

            columns = {_COLUMNS[channel]: transformed[channel] for channel in CHANNELS}
            create_reading(
                device_id=device_id, reading_ts=transformed["timestamp"], **columns
            )
            return transformed
        except Exception as e:
            self.logger.error(f"Error storing reading for device {device_id}: {e}")
            return None

    def _validate_reading(self, reading: Dict[str, Any]) -> bool:
        """
        Validate a reading from a device.

        A reading is valid when it carries no error, has a timestamp, has at
        least one channel with data, and every present channel is within its
        sanity range.

        Args:
            reading (Dict[str, Any]): Reading from the device client

        Returns:
            bool: True if the reading is valid, False otherwise
        """
        if reading.get("error") or "timestamp" not in reading:
            return False

        present = 0
        for channel, (low, high) in _RANGES.items():
            value = reading.get(channel)
            if value is None:
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                return False
            if not low <= value <= high:
                return False
            present += 1

        return present > 0

    def _transform_reading(
        self, device_id: int, reading: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform a reading from a device into the stored shape.

        Args:
            device_id (int): ID of the device
            reading (Dict[str, Any]): Reading from the device client

        Returns:
            Dict[str, Any]: Transformed reading (device_id, timestamp + channels)
        """
        # Parse the timestamp. Persisted timestamps are naive UTC: devices
        # report UTC (NTP), and aware values are converted before storage.
        timestamp = None
        ts_raw = reading.get("timestamp")
        if isinstance(ts_raw, (int, float)) and ts_raw > 1_600_000_000:
            # Unix epoch from the device (0 means clock not yet NTP-synced)
            timestamp = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
        elif isinstance(ts_raw, str):
            try:
                timestamp = datetime.fromisoformat(ts_raw)
            except ValueError:
                pass
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        if timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)

        transformed = {"device_id": device_id, "timestamp": timestamp.isoformat()}
        for channel in CHANNELS:
            value = reading.get(channel)
            transformed[channel] = None if value is None else float(value)
        return transformed

    def _is_duplicate(self, device_id: int, reading: Dict[str, Any]) -> bool:
        """
        Check if a reading is a duplicate.

        A reading is a duplicate if the stored latest reading is within one
        minute and has the same CO2, temperature and humidity (Spore rule).
        A None on either side of any of the three means "not a duplicate".

        Args:
            device_id (int): ID of the device
            reading (Dict[str, Any]): Transformed reading

        Returns:
            bool: True if the reading is a duplicate, False otherwise
        """
        latest = get_latest_reading(device_id)
        if not latest:
            return False

        try:
            latest_ts = datetime.fromisoformat(latest["reading_ts"])
            current_ts = datetime.fromisoformat(reading["timestamp"])
        except (ValueError, TypeError):
            return False

        if abs((current_ts - latest_ts).total_seconds()) > 60:
            return False

        pairs = (
            (latest.get("co2"), reading.get("co2"), 1.0),
            (latest.get("temp"), reading.get("temperature"), 0.1),
            (latest.get("humidity"), reading.get("humidity"), 0.1),
        )
        for stored, new, tolerance in pairs:
            if stored is None or new is None:
                return False
            if abs(float(stored) - float(new)) >= tolerance:
                return False
        return True
