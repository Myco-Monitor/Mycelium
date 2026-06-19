"""
Hyphae Data Service for Mycelium

This module provides services for handling Hyphae device data, including:
- Data transformation and storage
- Configuration management
- Relay control
- Schedule and threshold management
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from api.clients.hyphae_client import HyphaeClient
from storage.tables.device_hyphae import update_device_status, get_device_hyphae
from storage.tables.readings_hyphae import create_reading, get_latest_reading
from storage.tables.relay_settings import (
    create_relay_setting,
    update_relay_setting,
    get_device_relay_settings,
)
from storage.tables.schedule_settings import (
    create_schedule_setting,
    update_schedule_setting,
    get_device_schedule_settings,
)
from storage.tables.dynamic_settings import (
    create_dynamic_setting,
    update_dynamic_setting,
    get_device_dynamic_settings,
)


class HyphaeDataService:
    """
    Service for handling Hyphae device data.

    This service is responsible for:
    - Transforming and storing data from the Hyphae API client
    - Managing device configurations
    - Controlling relays
    - Managing schedules and thresholds
    """

    def __init__(self):
        """Initialize the Hyphae data service."""
        self.logger = logging.getLogger("api.HyphaeDataService")
        self.clients: Dict[int, HyphaeClient] = {}

        # Cache for device configurations
        self._config_cache: Dict[int, Dict[str, Any]] = {}
        self._config_cache_time: Dict[int, datetime] = {}
        self._config_cache_ttl = timedelta(minutes=5)

    async def initialize_client(
        self, device_id: int, pin: Optional[str] = None
    ) -> HyphaeClient:
        """
        Initialize a Hyphae client for a device.

        Args:
            device_id (int): ID of the device
            pin (str, optional): PIN for authenticated operations

        Returns:
            HyphaeClient: The initialized client

        Raises:
            ValueError: If the device is not found or is not a Hyphae device
        """
        # Get device information from the database
        device = get_device_hyphae(device_id)
        if not device:
            raise ValueError(f"Device with ID {device_id} not found")

        # Create a new client if one doesn't exist for this device
        if device_id not in self.clients:
            base_url = f"https://{device['hostname']}"
            client = HyphaeClient(
                base_url=base_url,
                device_name=device["device_name"],
                device_id=device_id,
                pin=pin,
            )
            self.clients[device_id] = client
            self.logger.info(
                f"Initialized client for Hyphae device {device['device_name']} ({device_id})"
            )

        # Update the PIN if provided
        elif pin is not None:
            self.clients[device_id].pin = pin

        return self.clients[device_id]

    async def get_client(
        self, device_id: int, pin: Optional[str] = None
    ) -> HyphaeClient:
        """
        Get a Hyphae client for a device, initializing it if necessary.

        Args:
            device_id (int): ID of the device
            pin (str, optional): PIN for authenticated operations

        Returns:
            HyphaeClient: The client

        Raises:
            ValueError: If the device is not found or is not a Hyphae device
        """
        if device_id not in self.clients:
            return await self.initialize_client(device_id, pin)

        # Update the PIN if provided
        if pin is not None:
            self.clients[device_id].pin = pin

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

        Returns:
            Optional[Dict[str, Any]]: The latest reading, or None if the device is not reachable
        """
        try:
            client = await self.get_client(device_id)
            reading = await client.get_system_info()

            # Transform and store the reading
            stored_reading = await self.store_reading(device_id, reading)

            # Update device status
            update_device_status(device_id, 1)

            return stored_reading
        except Exception as e:
            self.logger.error(
                f"Error getting latest reading for device {device_id}: {e}"
            )

            # Update device status
            update_device_status(device_id, 0)

            return None

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

    async def get_relay_config(
        self, device_id: int, use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get the relay configuration for a device.

        Args:
            device_id (int): ID of the device
            use_cache (bool): Whether to use the cached configuration if available

        Returns:
            Optional[Dict[str, Any]]: The relay configuration, or None if the device is not reachable
        """
        # Check if we have a cached configuration
        if use_cache and device_id in self._config_cache:
            cache_time = self._config_cache_time.get(device_id)
            if cache_time and datetime.now() - cache_time < self._config_cache_ttl:
                return self._config_cache[device_id]

        try:
            client = await self.get_client(device_id)
            config = await client.get_relay_config()

            # Cache the configuration
            self._config_cache[device_id] = config
            self._config_cache_time[device_id] = datetime.now()

            # Update device status
            update_device_status(device_id, 1)

            # Store the configuration in the database
            await self.store_relay_config(device_id, config)

            return config
        except Exception as e:
            self.logger.error(
                f"Error getting relay configuration for device {device_id}: {e}"
            )

            # Update device status
            update_device_status(device_id, 0)

            return None

    async def set_relay_config(
        self, device_id: int, config: Dict[str, Any], pin: str
    ) -> bool:
        """
        Set the relay configuration for a device.

        Args:
            device_id (int): ID of the device
            config (Dict[str, Any]): New relay configuration
            pin (str): PIN for authentication

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            client = await self.get_client(device_id, pin)
            await client.set_relay_config(config)

            # Update the cache
            self._config_cache[device_id] = config
            self._config_cache_time[device_id] = datetime.now()

            # Update device status
            update_device_status(device_id, 1)

            # Store the configuration in the database
            await self.store_relay_config(device_id, config)

            return True
        except Exception as e:
            self.logger.error(
                f"Error setting relay configuration for device {device_id}: {e}"
            )

            # Update device status
            update_device_status(device_id, 0)

            return False

    async def get_relay_state(self, device_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the current relay states for a device.

        Args:
            device_id (int): ID of the device

        Returns:
            Optional[Dict[str, Any]]: The relay states, or None if the device is not reachable
        """
        try:
            client = await self.get_client(device_id)
            state = await client.get_relay_state()

            # Update device status
            update_device_status(device_id, 1)

            return state
        except Exception as e:
            self.logger.error(f"Error getting relay states for device {device_id}: {e}")

            # Update device status
            update_device_status(device_id, 0)

            return None

    async def test_relay(self, device_id: int, relay_number: int, pin: str) -> bool:
        """
        Test a relay on a device.

        Args:
            device_id (int): ID of the device
            relay_number (int): Number of the relay to test (1-6)
            pin (str): PIN for authentication

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            client = await self.get_client(device_id, pin)
            await client.test_relay(relay_number)

            # Update device status
            update_device_status(device_id, 1)

            return True
        except Exception as e:
            self.logger.error(
                f"Error testing relay {relay_number} for device {device_id}: {e}"
            )

            # Update device status
            update_device_status(device_id, 0)

            return False

    async def get_relay_thresholds(self, device_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the dynamic control thresholds for a device.

        Args:
            device_id (int): ID of the device

        Returns:
            Optional[Dict[str, Any]]: The dynamic control thresholds, or None if the device is not reachable
        """
        try:
            client = await self.get_client(device_id)
            thresholds = await client.get_relay_thresholds()

            # Update device status
            update_device_status(device_id, 1)

            # Store the thresholds in the database
            await self.store_dynamic_settings(device_id, thresholds)

            return thresholds
        except Exception as e:
            self.logger.error(
                f"Error getting relay thresholds for device {device_id}: {e}"
            )

            # Update device status
            update_device_status(device_id, 0)

            return None

    async def set_relay_thresholds(
        self, device_id: int, thresholds: Dict[str, Any], pin: str
    ) -> bool:
        """
        Set the dynamic control thresholds for a device.

        Args:
            device_id (int): ID of the device
            thresholds (Dict[str, Any]): New dynamic control thresholds
            pin (str): PIN for authentication

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            client = await self.get_client(device_id, pin)
            await client.set_relay_thresholds(thresholds)

            # Update device status
            update_device_status(device_id, 1)

            # Store the thresholds in the database
            await self.store_dynamic_settings(device_id, thresholds)

            return True
        except Exception as e:
            self.logger.error(
                f"Error setting relay thresholds for device {device_id}: {e}"
            )

            # Update device status
            update_device_status(device_id, 0)

            return False

    async def get_relay_schedule(self, device_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the relay group schedule for a device.

        Args:
            device_id (int): ID of the device

        Returns:
            Optional[Dict[str, Any]]: The relay group schedule, or None if the device is not reachable
        """
        try:
            client = await self.get_client(device_id)
            schedule = await client.get_relay_schedule()

            # Update device status
            update_device_status(device_id, 1)

            # Store the schedule in the database
            await self.store_schedule_settings(device_id, schedule)

            return schedule
        except Exception as e:
            self.logger.error(
                f"Error getting relay schedule for device {device_id}: {e}"
            )

            # Update device status
            update_device_status(device_id, 0)

            return None

    async def set_relay_schedule(
        self, device_id: int, schedule: Dict[str, Any], pin: str
    ) -> bool:
        """
        Set the relay group schedule for a device.

        Args:
            device_id (int): ID of the device
            schedule (Dict[str, Any]): New relay group schedule
            pin (str): PIN for authentication

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            client = await self.get_client(device_id, pin)
            await client.set_relay_schedule(schedule)

            # Update device status
            update_device_status(device_id, 1)

            # Store the schedule in the database
            await self.store_schedule_settings(device_id, schedule)

            return True
        except Exception as e:
            self.logger.error(
                f"Error setting relay schedule for device {device_id}: {e}"
            )

            # Update device status
            update_device_status(device_id, 0)

            return False

    async def set_relay_mode(self, device_id: int, mode: int, pin: str) -> bool:
        """
        Set the relay operation mode for a device.

        Args:
            device_id (int): ID of the device
            mode (int): New operation mode (0=manual, 1=scheduled)
            pin (str): PIN for authentication

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            client = await self.get_client(device_id, pin)
            await client.set_relay_mode(mode)

            # Update device status
            update_device_status(device_id, 1)

            return True
        except Exception as e:
            self.logger.error(f"Error setting relay mode for device {device_id}: {e}")

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

            # Extract relay states and store each one
            relay_states = transformed_reading.get("relay_states", [])
            reading_ts = transformed_reading["timestamp"]

            for relay_number, relay_state in enumerate(relay_states, start=1):
                create_reading(
                    device_id=device_id,
                    reading_ts=reading_ts,
                    relay_number=relay_number,
                    relay_state=relay_state,
                )

            return transformed_reading
        except Exception as e:
            self.logger.error(f"Error storing reading for device {device_id}: {e}")
            return None

    async def store_relay_config(self, device_id: int, config: Dict[str, Any]) -> bool:
        """
        Store relay configuration in the database.

        Args:
            device_id (int): ID of the device
            config (Dict[str, Any]): Relay configuration

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get existing relay settings
            existing_settings = get_device_relay_settings(device_id)

            # Extract relay configuration
            relays = config.get("relays", [])

            for i, relay in enumerate(relays):
                relay_number = i + 1
                relay_name = relay.get("name", f"Relay {relay_number}")
                group_num = relay.get("group", 0)

                # Check if this relay already exists in the database
                existing_relay = next(
                    (r for r in existing_settings if r["relay_number"] == relay_number),
                    None,
                )

                if existing_relay:
                    # Update existing relay
                    update_relay_setting(
                        device_id=device_id,
                        relay_number=relay_number,
                        group_num=group_num,
                        relay_name=relay_name,
                    )
                else:
                    # Create new relay
                    create_relay_setting(
                        {
                            "device_id": device_id,
                            "relay_number": relay_number,
                            "group_num": group_num,
                            "relay_name": relay_name,
                        }
                    )

            return True
        except Exception as e:
            self.logger.error(
                f"Error storing relay configuration for device {device_id}: {e}"
            )
            return False

    async def store_dynamic_settings(
        self, device_id: int, thresholds: Dict[str, Any]
    ) -> bool:
        """
        Store dynamic control thresholds in the database.

        Args:
            device_id (int): ID of the device
            thresholds (Dict[str, Any]): Dynamic control thresholds

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get existing dynamic settings
            existing_settings = get_device_dynamic_settings(device_id)

            # Extract threshold groups
            groups = thresholds.get("groups", [])

            for group in groups:
                group_num = group.get("group_id", 0)
                parameter = group.get("sensor_type", "temperature")
                low_threshold = group.get("min_value", 0.0)
                high_threshold = group.get("max_value", 100.0)
                behavior = group.get("behavior", 0)

                # Check if this group already exists in the database
                existing_group = next(
                    (
                        g
                        for g in existing_settings
                        if g["group_num"] == group_num and g["parameter"] == parameter
                    ),
                    None,
                )

                if existing_group:
                    # Update existing group
                    update_dynamic_setting(
                        device_id=device_id,
                        group_num=group_num,
                        parameter=parameter,
                        low_threshold=low_threshold,
                        high_threshold=high_threshold,
                        behavior=behavior,
                    )
                else:
                    # Create new group
                    create_dynamic_setting(
                        device_id=device_id,
                        group_num=group_num,
                        parameter=parameter,
                        low_threshold=low_threshold,
                        high_threshold=high_threshold,
                        behavior=behavior,
                    )

            return True
        except Exception as e:
            self.logger.error(
                f"Error storing dynamic settings for device {device_id}: {e}"
            )
            return False

    async def store_schedule_settings(
        self, device_id: int, schedule: Dict[str, Any]
    ) -> bool:
        """
        Store relay group schedule in the database.

        Args:
            device_id (int): ID of the device
            schedule (Dict[str, Any]): Relay group schedule

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get existing schedule settings
            existing_settings = get_device_schedule_settings(device_id)

            # Extract schedule entries
            entries = schedule.get("entries", [])

            for entry in entries:
                group_num = entry.get("group_id", 0)
                on_time = entry.get("start", "00:00")
                off_time = entry.get("end", "00:00")

                # Check if this entry already exists in the database
                existing_entry = next(
                    (e for e in existing_settings if e["group_num"] == group_num), None
                )

                if existing_entry:
                    # Update existing entry
                    update_schedule_setting(
                        device_id=device_id,
                        group_num=group_num,
                        on_time=on_time,
                        off_time=off_time,
                    )
                else:
                    # Create new entry
                    create_schedule_setting(
                        device_id=device_id,
                        group_num=group_num,
                        on_time=on_time,
                        off_time=off_time,
                    )

            return True
        except Exception as e:
            self.logger.error(
                f"Error storing schedule settings for device {device_id}: {e}"
            )
            return False

    def _validate_reading(self, reading: Dict[str, Any]) -> bool:
        """
        Validate a reading from a device.

        Args:
            reading (Dict[str, Any]): Reading from the device

        Returns:
            bool: True if the reading is valid, False otherwise
        """
        # Check that we have a timestamp
        if "timestamp" not in reading:
            return False

        # Check that we have at least one of temperature, humidity, or relay_states
        if not any(
            key in reading for key in ["temperature", "humidity", "relay_states"]
        ):
            return False

        # Validate temperature if present
        if "temperature" in reading:
            try:
                temperature = float(reading["temperature"])
                if not -40 <= temperature <= 85:
                    return False
            except (ValueError, TypeError):
                return False

        # Validate humidity if present
        if "humidity" in reading:
            try:
                humidity = float(reading["humidity"])
                if not 0 <= humidity <= 100:
                    return False
            except (ValueError, TypeError):
                return False

        # Validate relay_states if present
        if "relay_states" in reading:
            if not isinstance(reading["relay_states"], list):
                return False

            # Check that all relay states are 0 or 1
            for state in reading["relay_states"]:
                if state not in [0, 1]:
                    return False

        return True

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
            timestamp = datetime.fromisoformat(reading.get("timestamp", ""))
        except (ValueError, TypeError):
            # If that fails, use the current time
            timestamp = datetime.now()

        # Format the timestamp as ISO format
        timestamp_str = timestamp.isoformat()

        # Extract and transform fields
        transformed = {"device_id": device_id, "timestamp": timestamp_str}

        # Add temperature if present
        if "temperature" in reading:
            transformed["temperature"] = float(reading["temperature"])

        # Add humidity if present
        if "humidity" in reading:
            transformed["humidity"] = float(reading["humidity"])

        # Add relay states if present
        if "relay_states" in reading:
            transformed["relay_states"] = reading["relay_states"]

        return transformed

    def _is_duplicate(self, device_id: int, reading: Dict[str, Any]) -> bool:
        """
        Check if a reading is a duplicate.

        A reading is considered a duplicate if there is already a reading
        with the same device ID and timestamp within the last minute.

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

        # If timestamps are very close (within 1 second), consider it a duplicate
        if abs((current_timestamp - latest_timestamp).total_seconds()) < 1:
            return True

        return False
