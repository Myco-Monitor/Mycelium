"""
Hyphae Device API Client for Mycelium

This module provides a client for interacting with Hyphae devices.
Hyphae devices are environmental controllers that manage relays for equipment.

Endpoints implemented:
- GET /api/system/info - Get system information
- GET /api/weather/current - Get weather data
- GET /api/spore/readings - Get spore device readings
- GET /api/relay/config - Get relay configuration
- POST /api/relay/config - Set relay configuration
- GET /api/relay/state - Get current relay states
- POST /api/relay/test - Test a relay
- GET /api/relay/thresholds - Get dynamic control thresholds
- POST /api/relay/thresholds - Set dynamic control thresholds
- GET /api/relay/schedule - Get relay schedule
- POST /api/relay/schedule - Set relay schedule
- POST /api/relay/mode - Set device mode
- GET /api/relay/cooldown - Check relay cooldown status
"""

import logging
from typing import Dict, Any

from api.clients.base_client import BaseApiClient, ApiError, ApiErrorType


class HyphaeClient(BaseApiClient):
    """
    Client for interacting with Hyphae devices.

    Attributes:
        device_name (str): Name of the device
        device_id (int): Database ID of the device
        pin (str): PIN for authenticated operations
    """

    def __init__(
        self,
        base_url: str,
        device_name: str,
        device_id: int,
        pin: str = None,
        timeout: int = 10,
        max_retries: int = 3,
        retry_delay: int = 1,
        use_tls: bool = False,
    ):
        """
        Initialize the Hyphae client.

        Args:
            base_url (str): Base URL for the device API (e.g., "https://hyphae-0001.local")
            device_name (str): Name of the device
            device_id (int): Database ID of the device
            pin (str, optional): PIN for authenticated operations
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
            # Hyphae devices can handle about 10 requests per second
            request_limit=10,
            request_period=1,
        )
        self.device_name = device_name
        self.device_id = device_id
        self.pin = pin
        self.logger = logging.getLogger(f"api.HyphaeClient.{device_name}")

    async def check_connection(self) -> bool:
        """
        Check if the Hyphae device is reachable.

        Returns:
            bool: True if the device is reachable, False otherwise
        """
        try:
            await self.get_info()
            return True
        except ApiError:
            return False

    async def get_system_info(self) -> Dict[str, Any]:
        """
        Get system information from the device.

        Returns:
            Dict[str, Any]: System information including uptime, signal strength, etc.

        Raises:
            ApiError: If the request fails
        """
        try:
            return await self.get("/api/system/info")
        except ApiError as e:
            self.logger.error(f"Failed to get system info: {e}")
            raise

    async def get_weather_data(self) -> Dict[str, Any]:
        """
        Get current weather data from the device.

        Returns:
            Dict[str, Any]: Weather data including temperature, humidity, pressure, etc.

        Raises:
            ApiError: If the request fails
        """
        try:
            return await self.get("/api/weather/current")
        except ApiError as e:
            self.logger.error(f"Failed to get weather data: {e}")
            raise

    async def get_pressure(self) -> Dict[str, Any]:
        """
        Get current BMP581 pressure reading from the device.

        Returns:
            Dict[str, Any]: Pressure data with keys:
                - pressure_hpa (int): Pressure in hectopascals
                - source (str): Sensor identifier (e.g., "BMP581")
                - healthy (bool): Sensor health status
                - timestamp (int): Unix timestamp of reading

        Raises:
            ApiError: If the request fails
        """
        try:
            return await self.get("/api/pressure")
        except ApiError as e:
            self.logger.error(f"Failed to get pressure: {e}")
            raise

    async def get_pressure_history(self) -> Dict[str, Any]:
        """
        Get pressure history from the device.

        Returns:
            Dict[str, Any]: Pressure history with keys:
                - readings (list): List of pressure readings
                - count (int): Number of readings

        Raises:
            ApiError: If the request fails
        """
        try:
            return await self.get("/api/pressure/history")
        except ApiError as e:
            self.logger.error(f"Failed to get pressure history: {e}")
            raise

    async def get_spore_readings(self) -> Dict[str, Any]:
        """
        Get spore device readings from the Hyphae device.

        Returns:
            Dict[str, Any]: Spore device readings collected by the Hyphae device

        Raises:
            ApiError: If the request fails
        """
        try:
            return await self.get("/api/spore/readings")
        except ApiError as e:
            self.logger.error(f"Failed to get spore readings: {e}")
            raise

    async def get_relay_config(self) -> Dict[str, Any]:
        """
        Get the relay configuration from the device.

        Returns:
            Dict[str, Any]: Relay configuration

        Raises:
            ApiError: If the request fails
        """
        try:
            return await self.get("/api/relay/config")
        except ApiError as e:
            self.logger.error(f"Failed to get relay configuration: {e}")
            raise

    async def get_relay_state(self) -> Dict[str, Any]:
        """
        Get the current relay states from the device.

        Returns:
            Dict[str, Any]: Current relay states, cooldowns, and testing status

        Raises:
            ApiError: If the request fails
        """
        try:
            return await self.get("/api/relay/state")
        except ApiError as e:
            self.logger.error(f"Failed to get relay states: {e}")
            raise

    async def get_relay_thresholds(self) -> Dict[str, Any]:
        """
        Get the dynamic control thresholds from the device.

        Returns:
            Dict[str, Any]: Dynamic control thresholds

        Raises:
            ApiError: If the request fails
        """
        try:
            return await self.get("/api/relay/thresholds")
        except ApiError as e:
            self.logger.error(f"Failed to get relay thresholds: {e}")
            raise

    async def get_relay_schedule(self) -> Dict[str, Any]:
        """
        Get the relay group schedule from the device.

        Returns:
            Dict[str, Any]: Relay group schedule

        Raises:
            ApiError: If the request fails
        """
        try:
            return await self.get("/api/relay/schedule")
        except ApiError as e:
            self.logger.error(f"Failed to get relay schedule: {e}")
            raise

    async def set_relay_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update the relay configuration on the device.

        Args:
            config (Dict[str, Any]): New relay configuration

        Returns:
            Dict[str, Any]: Response from the device

        Raises:
            ApiError: If the request fails or the PIN is not set
        """
        if not self.pin:
            raise ApiError(
                message="PIN is required for setting relay configuration",
                error_type=ApiErrorType.AUTHENTICATION,
            )

        try:
            # Add PIN to the configuration
            config_with_pin = {**config, "pin": self.pin}
            return await self.post("/api/relay/config", json_data=config_with_pin)
        except ApiError as e:
            self.logger.error(f"Failed to set relay configuration: {e}")
            raise

    async def test_relay(self, relay_number: int) -> Dict[str, Any]:
        """
        Test a relay on the device.

        Args:
            relay_number (int): Number of the relay to test (1-6)

        Returns:
            Dict[str, Any]: Response from the device

        Raises:
            ApiError: If the request fails, the relay number is invalid, or the PIN is not set
        """
        if not self.pin:
            raise ApiError(
                message="PIN is required for testing relays",
                error_type=ApiErrorType.AUTHENTICATION,
            )

        if not 1 <= relay_number <= 6:
            raise ApiError(
                message=f"Relay number must be between 1 and 6, got {relay_number}",
                error_type=ApiErrorType.VALIDATION,
            )

        try:
            return await self.post(
                "/api/relay/test", json_data={"relay": relay_number, "pin": self.pin}
            )
        except ApiError as e:
            self.logger.error(f"Failed to test relay {relay_number}: {e}")
            raise

    async def set_relay_thresholds(self, thresholds: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update the dynamic control thresholds on the device.

        Args:
            thresholds (Dict[str, Any]): New dynamic control thresholds

        Returns:
            Dict[str, Any]: Response from the device

        Raises:
            ApiError: If the request fails or the PIN is not set
        """
        if not self.pin:
            raise ApiError(
                message="PIN is required for setting relay thresholds",
                error_type=ApiErrorType.AUTHENTICATION,
            )

        try:
            # Add PIN to the thresholds
            thresholds_with_pin = {**thresholds, "pin": self.pin}
            return await self.post(
                "/api/relay/thresholds", json_data=thresholds_with_pin
            )
        except ApiError as e:
            self.logger.error(f"Failed to set relay thresholds: {e}")
            raise

    async def set_relay_schedule(self, schedule: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update the relay group schedule on the device.

        Args:
            schedule (Dict[str, Any]): New relay group schedule

        Returns:
            Dict[str, Any]: Response from the device

        Raises:
            ApiError: If the request fails or the PIN is not set
        """
        if not self.pin:
            raise ApiError(
                message="PIN is required for setting relay schedule",
                error_type=ApiErrorType.AUTHENTICATION,
            )

        try:
            # Add PIN to the schedule
            schedule_with_pin = {**schedule, "pin": self.pin}
            return await self.post("/api/relay/schedule", json_data=schedule_with_pin)
        except ApiError as e:
            self.logger.error(f"Failed to set relay schedule: {e}")
            raise

    async def set_relay_mode(self, mode: int) -> Dict[str, Any]:
        """
        Change the relay operation mode on the device.

        Args:
            mode (int): New operation mode (0=manual, 1=scheduled)

        Returns:
            Dict[str, Any]: Response from the device

        Raises:
            ApiError: If the request fails, the mode is invalid, or the PIN is not set
        """
        if not self.pin:
            raise ApiError(
                message="PIN is required for setting relay mode",
                error_type=ApiErrorType.AUTHENTICATION,
            )

        if mode not in [0, 1]:
            raise ApiError(
                message=f"Mode must be 0 (manual) or 1 (scheduled), got {mode}",
                error_type=ApiErrorType.VALIDATION,
            )

        try:
            return await self.post(
                "/api/relay/mode", json_data={"mode": mode, "pin": self.pin}
            )
        except ApiError as e:
            self.logger.error(f"Failed to set relay mode to {mode}: {e}")
            raise

    async def get_relay_cooldown_status(self, relay_number: int) -> Dict[str, Any]:
        """
        Check the cooldown status of a specific relay.

        Args:
            relay_number (int): Number of the relay to check (1-6)

        Returns:
            Dict[str, Any]: Cooldown status information

        Raises:
            ApiError: If the request fails or relay number is invalid
        """
        if not 1 <= relay_number <= 6:
            raise ApiError(
                message=f"Relay number must be between 1 and 6, got {relay_number}",
                error_type=ApiErrorType.VALIDATION,
            )

        try:
            return await self.get(f"/api/relay/cooldown?relay={relay_number}")
        except ApiError as e:
            self.logger.error(
                f"Failed to get relay {relay_number} cooldown status: {e}"
            )
            raise

    async def get_info(self) -> Dict[str, Any]:
        """
        Get information about the device using system info endpoint.

        Returns:
            Dict[str, Any]: Device information

        Raises:
            ApiError: If the request fails
        """
        try:
            return await self.get_system_info()
        except ApiError as e:
            self.logger.error(f"Failed to get device info: {e}")
            raise

    async def get_device_info(self) -> Dict[str, Any]:
        """
        Get information about the Hyphae device.
        COPIED from SporeClient.get_info() with endpoint adaptation.

        Returns:
            Dict[str, Any]: Device information with the following keys:
                - wifi_signal (int): WiFi signal strength in dBm
                - memory_total (int): Total memory in KB
                - memory_used (int): Used memory in KB
                - memory_free (int): Free memory in KB
                - relay_states (List[int]): Relay states [0,1,0,1,0,1]
                - cache_size (int): Cache size in entries
                - connected_spores (int): Number of connected Spore devices

        Raises:
            ApiError: If the request fails
        """
        try:
            response = await self.get("/hyphae-info", parse_json=False)
            return self._parse_info(response)
        except ApiError as e:
            self.logger.error(f"Failed to get device info: {e}")
            raise

    def _parse_info(self, info_text: str) -> Dict[str, Any]:
        """
        Parse device information from plain text.
        COPIED from SporeClient._parse_info() with Hyphae field additions.

        Args:
            info_text (str): Plain text device information

        Returns:
            Dict[str, Any]: Parsed device information
        """
        import re

        info = {}

        # EXACT COPY of Spore parsing patterns
        wifi_match = re.search(r"WiFi Signal Strength: (-?\d+) dBm", info_text)
        if wifi_match:
            info["wifi_signal"] = int(wifi_match.group(1))

        total_match = re.search(r"Total Memory: (\d+) KB", info_text)
        used_match = re.search(r"Used Memory: (\d+) KB", info_text)
        free_match = re.search(r"Free Memory: (\d+) KB", info_text)

        if total_match:
            info["memory_total"] = int(total_match.group(1))
        if used_match:
            info["memory_used"] = int(used_match.group(1))
        if free_match:
            info["memory_free"] = int(free_match.group(1))

        # ADD Hyphae-specific parsing (NEW)
        relay_match = re.search(r"Relay States: \[([0-1,]+)\]", info_text)
        if relay_match:
            relay_values = [int(x) for x in relay_match.group(1).split(",")]
            info["relay_states"] = relay_values

        cache_match = re.search(r"Cache Size: (\d+) entries", info_text)
        if cache_match:
            info["cache_size"] = int(cache_match.group(1))

        spore_match = re.search(r"Connected Spores: (\d+)", info_text)
        if spore_match:
            info["connected_spores"] = int(spore_match.group(1))

        return info
