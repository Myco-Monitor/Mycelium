"""
Pressure Data Service for Mycelium

This module provides services for handling BMP581 pressure data from Hyphae devices:
- Data transformation
- Data storage
- Data validation
- Duplicate detection
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from api.clients.pressure_client import PressureClient, PressureReading
from storage.tables.device_hyphae import update_device_status, get_device_hyphae
from storage.tables.readings_pressure import (
    create_reading,
    get_latest_pressure,
    get_device_readings,
)


class PressureDataService:
    """
    Service for handling pressure data from Hyphae BMP581 sensors.

    This service is responsible for:
    - Managing pressure clients for Hyphae devices
    - Transforming data from the pressure API
    - Storing pressure readings in the database
    - Validating pressure data
    - Detecting and handling duplicates
    """

    # Pressure validation range (hPa)
    PRESSURE_MIN = 970
    PRESSURE_MAX = 1050

    def __init__(self):
        """Initialize the Pressure data service."""
        self.logger = logging.getLogger("api.PressureDataService")
        self.clients: Dict[int, PressureClient] = {}

    async def initialize_client(self, device_id: int) -> PressureClient:
        """
        Initialize a Pressure client for a Hyphae device.

        Args:
            device_id (int): ID of the Hyphae device

        Returns:
            PressureClient: The initialized client

        Raises:
            ValueError: If the device is not found
        """
        device = get_device_hyphae(device_id)
        if not device:
            raise ValueError(f"Hyphae device with ID {device_id} not found")

        if device_id not in self.clients:
            base_url = f"https://{device['hostname']}"
            client = PressureClient(
                base_url=base_url,
                device_name=device["device_name"],
                device_id=device_id,
            )
            self.clients[device_id] = client
            self.logger.info(
                f"Initialized pressure client for Hyphae {device['device_name']} ({device_id})"
            )

        return self.clients[device_id]

    async def get_client(self, device_id: int) -> PressureClient:
        """
        Get a Pressure client for a device, initializing it if necessary.

        Args:
            device_id (int): ID of the Hyphae device

        Returns:
            PressureClient: The client

        Raises:
            ValueError: If the device is not found
        """
        if device_id not in self.clients:
            return await self.initialize_client(device_id)
        return self.clients[device_id]

    async def check_device_connection(self, device_id: int) -> bool:
        """
        Check if a Hyphae device's pressure endpoint is reachable.

        Args:
            device_id (int): ID of the Hyphae device

        Returns:
            bool: True if the device is reachable, False otherwise
        """
        try:
            client = await self.get_client(device_id)
            is_connected = await client.check_connection()
            update_device_status(device_id, 1 if is_connected else 0)
            return is_connected
        except Exception as e:
            self.logger.error(
                f"Error checking pressure connection for device {device_id}: {e}"
            )
            update_device_status(device_id, 0)
            return False

    async def fetch_and_store_pressure(
        self, device_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch current pressure from a Hyphae device and store it.

        Args:
            device_id (int): ID of the Hyphae device

        Returns:
            Optional[Dict[str, Any]]: The stored reading, or None if failed
        """
        try:
            client = await self.get_client(device_id)
            reading = await client.get_current_pressure()

            if reading:
                stored = await self.store_reading(device_id, reading)
                update_device_status(device_id, 1)
                return stored

            return None
        except Exception as e:
            self.logger.error(f"Error fetching pressure for device {device_id}: {e}")
            update_device_status(device_id, 0)
            return None

    async def get_latest_reading(self, device_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the latest stored pressure reading for a device.

        Args:
            device_id (int): ID of the Hyphae device

        Returns:
            Optional[Dict[str, Any]]: Latest pressure reading or None
        """
        return get_latest_pressure(device_id)

    async def get_pressure_history(
        self, device_id: int, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get pressure history for a device from the database.

        Args:
            device_id (int): ID of the Hyphae device
            limit (int): Maximum number of readings to return

        Returns:
            List[Dict[str, Any]]: List of pressure readings
        """
        return get_device_readings(device_id, limit=limit)

    async def store_reading(
        self, device_id: int, reading: PressureReading
    ) -> Optional[Dict[str, Any]]:
        """
        Transform and store a pressure reading in the database.

        Args:
            device_id (int): ID of the Hyphae device
            reading (PressureReading): Reading from the device

        Returns:
            Optional[Dict[str, Any]]: The stored reading, or None if invalid/duplicate
        """
        try:
            if not self._validate_reading(reading):
                self.logger.warning(
                    f"Invalid pressure reading for device {device_id}: {reading}"
                )
                return None

            transformed = self._transform_reading(device_id, reading)

            if self._is_duplicate(device_id, transformed):
                self.logger.debug(f"Duplicate pressure reading for device {device_id}")
                return None

            create_reading(
                hyphae_id=device_id,
                reading_ts=transformed["reading_ts"],
                pressure_hpa=transformed["pressure_hpa"],
                source=transformed["source"],
                healthy=transformed["healthy"],
            )

            self.logger.debug(
                f"Stored pressure reading for device {device_id}: "
                f"{transformed['pressure_hpa']} hPa"
            )
            return transformed

        except Exception as e:
            self.logger.error(
                f"Error storing pressure reading for device {device_id}: {e}"
            )
            return None

    def _validate_reading(self, reading: PressureReading) -> bool:
        """
        Validate a pressure reading.

        Args:
            reading (PressureReading): Reading to validate

        Returns:
            bool: True if valid, False otherwise
        """
        if not reading.healthy:
            return False

        if not self.PRESSURE_MIN <= reading.pressure_hpa <= self.PRESSURE_MAX:
            return False

        return True

    def _transform_reading(
        self, device_id: int, reading: PressureReading
    ) -> Dict[str, Any]:
        """
        Transform a pressure reading for storage.

        Args:
            device_id (int): ID of the Hyphae device
            reading (PressureReading): Reading from the device

        Returns:
            Dict[str, Any]: Transformed reading
        """
        # Device epoch is UTC; store naive UTC like every persisted timestamp
        if reading.timestamp:
            timestamp = datetime.fromtimestamp(reading.timestamp, tz=timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)
        timestamp = timestamp.replace(tzinfo=None)

        return {
            "hyphae_id": device_id,
            "reading_ts": timestamp.isoformat(),
            "pressure_hpa": reading.pressure_hpa,
            "source": reading.source,
            "healthy": 1 if reading.healthy else 0,
        }

    def _is_duplicate(self, device_id: int, reading: Dict[str, Any]) -> bool:
        """
        Check if a pressure reading is a duplicate.

        A reading is considered a duplicate if there is already a reading
        with the same pressure value within the last minute.

        Args:
            device_id (int): ID of the Hyphae device
            reading (Dict[str, Any]): Transformed reading

        Returns:
            bool: True if duplicate, False otherwise
        """
        latest = get_latest_pressure(device_id)
        if not latest:
            return False

        try:
            latest_ts = datetime.fromisoformat(latest["reading_ts"])
            current_ts = datetime.fromisoformat(reading["reading_ts"])
        except (ValueError, TypeError):
            return False

        # Check if readings are within 1 minute
        if abs((current_ts - latest_ts).total_seconds()) > 60:
            return False

        # Check if pressure is identical (within 1 hPa tolerance)
        if abs(latest["pressure_hpa"] - reading["pressure_hpa"]) < 1:
            return True

        return False
