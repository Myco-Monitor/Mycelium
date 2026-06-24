"""
Spore Data Service for Mycelium

This module provides services for handling Spore device data, including:
- Data transformation
- Data storage
- Data validation
- Duplicate detection
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from api.clients.spore_client import SporeClient
from storage.tables.device_spore import update_device_status, get_device_spore
from storage.tables.readings_spore import create_reading, get_latest_reading


class SporeDataService:
    """
    Service for handling Spore device data.

    This service is responsible for:
    - Transforming data from the Spore API client
    - Storing data in the database
    - Validating data
    - Detecting and handling duplicates
    """

    def __init__(self):
        """Initialize the Spore data service."""
        self.logger = logging.getLogger("api.SporeDataService")
        self.clients: Dict[int, SporeClient] = {}

    async def initialize_client(self, device_id: int) -> SporeClient:
        """
        Initialize a Spore client for a device.

        Args:
            device_id (int): ID of the device

        Returns:
            SporeClient: The initialized client

        Raises:
            ValueError: If the device is not found or is not a Spore device
        """
        # Get device information from the database
        device = get_device_spore(device_id)
        if not device:
            raise ValueError(f"Device with ID {device_id} not found")

        # Create a new client if one doesn't exist for this device
        if device_id not in self.clients:
            base_url = f"https://{device['hostname']}"
            client = SporeClient(
                base_url=base_url,
                device_name=device["device_name"],
                device_id=device_id,
            )
            self.clients[device_id] = client
            self.logger.info(
                f"Initialized client for Spore device {device['device_name']} ({device_id})"
            )

        return self.clients[device_id]

    async def get_client(self, device_id: int) -> SporeClient:
        """
        Get a Spore client for a device, initializing it if necessary.

        Args:
            device_id (int): ID of the device

        Returns:
            SporeClient: The client

        Raises:
            ValueError: If the device is not found or is not a Spore device
        """
        if device_id not in self.clients:
            return await self.initialize_client(device_id)
        return self.clients[device_id]

    async def check_device_connection(self, device_id: int) -> bool:
        """
        Check if a device is reachable.

        Args:
            device_id (int): ID of the device

        Returns:
            bool: True if the device is reachable, False otherwise
        """
        try:
            client = await self.get_client(device_id)
            is_connected = await client.check_connection()

            # Update device status in the database
            update_device_status(device_id, 1 if is_connected else 0)

            return is_connected
        except Exception as e:
            self.logger.error(f"Error checking connection for device {device_id}: {e}")

            # Update device status in the database
            update_device_status(device_id, 0)

            return False

    async def get_latest_reading(self, device_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the latest reading from a device.

        Args:
            device_id (int): ID of the device

        Raises on failure so the polling service owns device status and backoff
        (it distinguishes a transient mDNS miss from a genuine outage). Other
        callers read stored readings from the database, not this method.

        Returns:
            Optional[Dict[str, Any]]: The stored latest reading.
        """
        client = await self.get_client(device_id)
        reading = await client.get_latest_reading()

        # Transform and store the reading
        stored_reading = await self.store_reading(device_id, reading)
        return stored_reading

    async def get_all_readings(self, device_id: int) -> List[Dict[str, Any]]:
        """
        Get all cached readings from a device.

        Args:
            device_id (int): ID of the device

        Returns:
            List[Dict[str, Any]]: List of readings
        """
        try:
            client = await self.get_client(device_id)
            readings = await client.get_all_readings()

            # Transform and store each reading
            stored_readings = []
            for reading in readings:
                stored_reading = await self.store_reading(device_id, reading)
                if stored_reading:
                    stored_readings.append(stored_reading)

            # Update device status
            update_device_status(device_id, 1)

            return stored_readings
        except Exception as e:
            self.logger.error(f"Error getting all readings for device {device_id}: {e}")

            # Update device status
            update_device_status(device_id, 0)

            return []

    async def set_ambient_pressure(self, device_id: int, pressure: int) -> bool:
        """
        Set the ambient pressure for a device.

        Args:
            device_id (int): ID of the device
            pressure (int): Ambient pressure in mbar (700-1200)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            client = await self.get_client(device_id)
            await client.set_ambient_pressure(pressure)

            # Update device status
            update_device_status(device_id, 1)

            return True
        except Exception as e:
            self.logger.error(
                f"Error setting ambient pressure for device {device_id}: {e}"
            )

            # Update device status
            update_device_status(device_id, 0)

            return False

    async def get_device_info(self, device_id: int) -> Optional[Dict[str, Any]]:
        """
        Get information about a device.

        Args:
            device_id (int): ID of the device

        Returns:
            Optional[Dict[str, Any]]: Device information, or None if the device is not reachable
        """
        try:
            client = await self.get_client(device_id)
            info = await client.get_info()

            # Update device status
            update_device_status(device_id, 1)

            return info
        except Exception as e:
            self.logger.error(f"Error getting device info for device {device_id}: {e}")

            # Update device status
            update_device_status(device_id, 0)

            return None

    async def store_reading(
        self, device_id: int, reading: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Transform and store a reading in the database.

        Args:
            device_id (int): ID of the device
            reading (Dict[str, Any]): Reading from the device

        Returns:
            Optional[Dict[str, Any]]: The stored reading, or None if the reading is invalid or a duplicate
        """
        try:
            # Validate the reading
            if not self._validate_reading(reading):
                self.logger.warning(
                    f"Invalid reading for device {device_id}: {reading}"
                )
                return None

            # Transform the reading
            transformed_reading = self._transform_reading(device_id, reading)

            # Check for duplicates
            if self._is_duplicate(device_id, transformed_reading):
                self.logger.debug(
                    f"Duplicate reading for device {device_id}: {transformed_reading}"
                )
                return None

            # Store the reading
            reading_id = create_reading(
                device_id=device_id,
                reading_ts=transformed_reading["timestamp"],
                co2=transformed_reading["co2"],
                humidity=transformed_reading["humidity"],
                temp=transformed_reading["temperature"],
            )

            # Add the reading ID to the transformed reading
            transformed_reading["reading_id"] = reading_id

            return transformed_reading
        except Exception as e:
            self.logger.error(f"Error storing reading for device {device_id}: {e}")
            return None

    def _validate_reading(self, reading: Dict[str, Any]) -> bool:
        """
        Validate a reading from a device.

        Args:
            reading (Dict[str, Any]): Reading from the device

        Returns:
            bool: True if the reading is valid, False otherwise
        """
        # Check that all required fields are present
        required_fields = ["device_name", "co2", "temperature", "humidity", "timestamp"]
        if not all(field in reading for field in required_fields):
            return False

        # Check that numeric fields are within reasonable ranges
        try:
            co2 = float(reading["co2"])
            temperature = float(reading["temperature"])
            humidity = float(reading["humidity"])

            # CO₂ should be between 0 and 10000 ppm (0.1%)
            if not 0 <= co2 <= 10000:
                return False

            # Temperature should be between -40 and 85°C (sensor limits)
            if not -40 <= temperature <= 85:
                return False

            # Humidity should be between 0 and 100%
            if not 0 <= humidity <= 100:
                return False

            return True
        except (ValueError, TypeError):
            return False

    def _transform_reading(
        self, device_id: int, reading: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform a reading from a device.

        Args:
            device_id (int): ID of the device
            reading (Dict[str, Any]): Reading from the device

        Returns:
            Dict[str, Any]: Transformed reading
        """
        # Parse the timestamp
        try:
            # Try to parse the timestamp as ISO format
            timestamp = datetime.fromisoformat(reading["timestamp"])
        except (ValueError, TypeError):
            # If that fails, use the current time
            timestamp = datetime.now()

        # Format the timestamp as ISO format
        timestamp_str = timestamp.isoformat()

        # Return the transformed reading
        return {
            "device_id": device_id,
            "co2": float(reading["co2"]),
            "temperature": float(reading["temperature"]),
            "humidity": float(reading["humidity"]),
            "timestamp": timestamp_str,
        }

    def _is_duplicate(self, device_id: int, reading: Dict[str, Any]) -> bool:
        """
        Check if a reading is a duplicate.

        A reading is considered a duplicate if there is already a reading
        with the same device ID, CO₂, temperature, and humidity within
        the last minute.

        Args:
            device_id (int): ID of the device
            reading (Dict[str, Any]): Reading from the device

        Returns:
            bool: True if the reading is a duplicate, False otherwise
        """
        # Get the latest reading for this device
        latest_reading = get_latest_reading(device_id)
        if not latest_reading:
            return False

        # Parse the timestamps
        try:
            latest_timestamp = datetime.fromisoformat(latest_reading["reading_ts"])
            current_timestamp = datetime.fromisoformat(reading["timestamp"])
        except (ValueError, TypeError):
            # If we can't parse the timestamps, assume it's not a duplicate
            return False

        # Check if the readings are within 1 minute of each other
        if abs((current_timestamp - latest_timestamp).total_seconds()) > 60:
            return False

        # Check if the values are the same
        if (
            abs(float(latest_reading["co2"]) - float(reading["co2"])) < 1
            and abs(float(latest_reading["temp"]) - float(reading["temperature"])) < 0.1
            and abs(float(latest_reading["humidity"]) - float(reading["humidity"]))
            < 0.1
        ):
            return True

        return False
