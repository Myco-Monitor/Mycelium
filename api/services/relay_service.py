"""
Relay Control Service for Mycelium

This module provides services for controlling Hyphae relay devices,
including relay state management, testing, and schedule configuration.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from api.clients.auth_handler import DeviceAuthHandler
from api.clients.base_client import create_device_ssl_context, device_connector


class RelayOperationMode(Enum):
    """Operating modes for the Hyphae relay system."""

    OFF = 0
    TESTING = 1
    RUNNING = 2


@dataclass
class RelayState:
    """State of a single relay."""

    relay_number: int
    is_on: bool
    name: Optional[str] = None
    group: Optional[int] = None


@dataclass
class RelayConfig:
    """Configuration for a single relay."""

    relay_number: int
    name: str
    group: int
    enabled: bool = True


class RelayService:
    """
    Service for controlling Hyphae relay devices.

    Provides methods to:
    - Get relay states
    - Test individual relays
    - Set operation mode
    - Update relay configuration
    - Manage relay schedules
    """

    def __init__(self, timeout: float = 10.0):
        """
        Initialize the relay service.

        Args:
            timeout (float): Timeout for device requests in seconds
        """
        self.timeout = timeout
        self.logger = logging.getLogger("services.RelayService")

    async def get_relay_states(self, hyphae_ip: str) -> List[RelayState]:
        """
        Get the current state of all 6 relays.

        Args:
            hyphae_ip (str): IP address of the Hyphae device

        Returns:
            List[RelayState]: List of relay states (6 relays)
        """
        import aiohttp

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            ssl_ctx = create_device_ssl_context()
            connector = device_connector(ssl_ctx)
            async with aiohttp.ClientSession(
                timeout=timeout, connector=connector
            ) as session:
                async with session.get(
                    f"https://{hyphae_ip}/api/relay/state"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Response is array of booleans: [true, false, true, false, false, false]
                        if isinstance(data, list):
                            return [
                                RelayState(relay_number=i + 1, is_on=state)
                                for i, state in enumerate(data[:6])
                            ]
        except Exception as e:
            self.logger.error(f"Error getting relay states from {hyphae_ip}: {e}")

        # Return default off states if failed
        return [RelayState(relay_number=i, is_on=False) for i in range(1, 7)]

    async def get_relay_config(self, hyphae_ip: str) -> Optional[Dict[str, Any]]:
        """
        Get the current relay configuration.

        Args:
            hyphae_ip (str): IP address of the Hyphae device

        Returns:
            Optional[Dict]: Relay configuration or None if failed
        """
        import aiohttp

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            ssl_ctx = create_device_ssl_context()
            connector = device_connector(ssl_ctx)
            async with aiohttp.ClientSession(
                timeout=timeout, connector=connector
            ) as session:
                async with session.get(
                    f"https://{hyphae_ip}/api/relay/config"
                ) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception as e:
            self.logger.error(f"Error getting relay config from {hyphae_ip}: {e}")

        return None

    async def test_relay(
        self, hyphae_ip: str, pin: str, relay_number: int, duration_seconds: int = 5
    ) -> Dict[str, Any]:
        """
        Test a specific relay for a given duration.

        Args:
            hyphae_ip (str): IP address of the Hyphae device
            pin (str): Device PIN for authentication
            relay_number (int): Relay number (1-6)
            duration_seconds (int): Test duration in seconds (1-30)

        Returns:
            Dict: Result with 'success' and optional 'error'
        """
        if not 1 <= relay_number <= 6:
            return {"success": False, "error": "Relay number must be 1-6"}

        if not 1 <= duration_seconds <= 30:
            return {"success": False, "error": "Duration must be 1-30 seconds"}

        auth = DeviceAuthHandler(hyphae_ip, pin, timeout=self.timeout)
        payload = {"relay": relay_number, "duration": duration_seconds}

        result = await auth.make_authenticated_request(
            "POST", "/api/relay/test", json_data=payload
        )

        if result.get("success"):
            self.logger.info(
                f"Relay {relay_number} test started on {hyphae_ip} for {duration_seconds}s"
            )
        else:
            self.logger.warning(
                f"Relay test failed on {hyphae_ip}: {result.get('error')}"
            )

        return result

    async def set_operation_mode(
        self, hyphae_ip: str, pin: str, mode: RelayOperationMode
    ) -> Dict[str, Any]:
        """
        Set the operation mode for the relay system.

        Args:
            hyphae_ip (str): IP address of the Hyphae device
            pin (str): Device PIN for authentication
            mode (RelayOperationMode): The operation mode to set

        Returns:
            Dict: Result with 'success' and optional 'error'
        """
        auth = DeviceAuthHandler(hyphae_ip, pin, timeout=self.timeout)
        payload = {"mode": mode.value}

        result = await auth.make_authenticated_request(
            "POST", "/api/relay/mode", json_data=payload
        )

        if result.get("success"):
            self.logger.info(f"Operation mode set to {mode.name} on {hyphae_ip}")
        else:
            self.logger.warning(
                f"Failed to set operation mode on {hyphae_ip}: {result.get('error')}"
            )

        return result

    async def update_relay_config(
        self, hyphae_ip: str, pin: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update the relay configuration.

        Args:
            hyphae_ip (str): IP address of the Hyphae device
            pin (str): Device PIN for authentication
            config (Dict): New relay configuration

        Returns:
            Dict: Result with 'success' and optional 'error'
        """
        auth = DeviceAuthHandler(hyphae_ip, pin, timeout=self.timeout)

        result = await auth.make_authenticated_request(
            "POST", "/api/relay/config", json_data=config
        )

        if result.get("success"):
            self.logger.info(f"Relay config updated on {hyphae_ip}")
        else:
            self.logger.warning(
                f"Failed to update relay config on {hyphae_ip}: {result.get('error')}"
            )

        return result

    async def get_relay_schedules(self, hyphae_ip: str) -> List[Dict[str, Any]]:
        """
        Get the current relay schedule configuration.

        Args:
            hyphae_ip (str): IP address of the Hyphae device

        Returns:
            List[Dict]: List of schedule rules
        """
        import aiohttp

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            ssl_ctx = create_device_ssl_context()
            connector = device_connector(ssl_ctx)
            async with aiohttp.ClientSession(
                timeout=timeout, connector=connector
            ) as session:
                async with session.get(
                    f"https://{hyphae_ip}/api/relay/schedule"
                ) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception as e:
            self.logger.error(f"Error getting relay schedules from {hyphae_ip}: {e}")

        return []

    async def update_relay_schedule(
        self, hyphae_ip: str, pin: str, schedule: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update relay schedule rules.

        Args:
            hyphae_ip (str): IP address of the Hyphae device
            pin (str): Device PIN for authentication
            schedule (Dict): Schedule configuration

        Returns:
            Dict: Result with 'success' and optional 'error'
        """
        auth = DeviceAuthHandler(hyphae_ip, pin, timeout=self.timeout)

        result = await auth.make_authenticated_request(
            "POST", "/api/relay/schedule", json_data=schedule
        )

        if result.get("success"):
            self.logger.info(f"Relay schedule updated on {hyphae_ip}")
        else:
            self.logger.warning(
                f"Failed to update relay schedule on {hyphae_ip}: {result.get('error')}"
            )

        return result

    async def set_relay_groups(
        self, hyphae_ip: str, pin: str, groups: List[int]
    ) -> Dict[str, Any]:
        """
        Set relay group assignments.

        Args:
            hyphae_ip (str): IP address of the Hyphae device
            pin (str): Device PIN for authentication
            groups (List[int]): List of 6 group assignments (0-3 for each relay)

        Returns:
            Dict: Result with 'success' and optional 'error'
        """
        if len(groups) != 6:
            return {"success": False, "error": "Must provide 6 group assignments"}

        if not all(0 <= g <= 3 for g in groups):
            return {"success": False, "error": "Group values must be 0-3"}

        auth = DeviceAuthHandler(hyphae_ip, pin, timeout=self.timeout)
        payload = {"groups": groups}

        result = await auth.make_authenticated_request(
            "POST", "/api/relay/groups/set", json_data=payload
        )

        if result.get("success"):
            self.logger.info(f"Relay groups updated on {hyphae_ip}")
        else:
            self.logger.warning(
                f"Failed to update relay groups on {hyphae_ip}: {result.get('error')}"
            )

        return result

    async def get_operation_mode(self, hyphae_ip: str) -> Optional[RelayOperationMode]:
        """
        Get the current operation mode.

        Args:
            hyphae_ip (str): IP address of the Hyphae device

        Returns:
            Optional[RelayOperationMode]: Current mode or None if failed
        """
        import aiohttp

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            ssl_ctx = create_device_ssl_context()
            connector = device_connector(ssl_ctx)
            async with aiohttp.ClientSession(
                timeout=timeout, connector=connector
            ) as session:
                async with session.get(
                    f"https://{hyphae_ip}/api/relay/mode"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        mode_value = data.get("mode", 0)
                        return RelayOperationMode(mode_value)
        except Exception as e:
            self.logger.error(f"Error getting operation mode from {hyphae_ip}: {e}")

        return None
