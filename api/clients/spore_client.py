"""
Spore Device API Client for Mycelium

This module provides a client for interacting with Spore devices.
Spore devices are environmental sensors that measure CO₂, temperature, and humidity.

Endpoints implemented:
- GET /api/readings/latest - Retrieve latest sensor data
- GET /api/readings/all - Retrieve historical sensor data
- POST /api/ambient-pressure - Set ambient pressure for calibration
- GET /spore-info - Get device information
"""

import re
import csv
import logging
from io import StringIO
from typing import Dict, List, Any

from api.clients.base_client import BaseApiClient, ApiError, ApiErrorType


class SporeClient(BaseApiClient):
    """
    Client for interacting with Spore devices.

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
        Initialize the Spore client.

        Args:
            base_url (str): Base URL for the device API (e.g., "https://spore-0001.local")
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
            # Spore devices can handle about 10 requests per second
            request_limit=10,
            request_period=1,
        )
        self.device_name = device_name
        self.device_id = device_id
        self.logger = logging.getLogger(f"api.SporeClient.{device_name}")

    async def check_connection(self) -> bool:
        """
        Check if the Spore device is reachable.

        Returns:
            bool: True if the device is reachable, False otherwise
        """
        try:
            await self.get_info()
            return True
        except ApiError:
            return False

    async def get_latest_reading(self) -> Dict[str, Any]:
        """
        Get the latest sensor reading from the device.

        Returns:
            Dict[str, Any]: The latest sensor reading with the following keys:
                - device_name (str): Name of the device
                - co2 (float): CO₂ level in ppm
                - temperature (float): Temperature in °C
                - humidity (float): Relative humidity in %
                - timestamp (int): Unix timestamp of the reading

        Raises:
            ApiError: If the request fails
        """
        try:
            # /api/readings/latest returns JSON
            response = await self.get("/api/readings/latest", parse_json=True)
            return {
                "device_name": response.get("device_name", self.device_name),
                "co2": float(response.get("co2", 0)),
                "temperature": float(response.get("temperature", 0)),
                "humidity": float(response.get("humidity", 0)),
                "timestamp": response.get("timestamp", 0),
            }
        except ApiError as e:
            self.logger.error(f"Failed to get latest reading: {e}")
            raise

    async def get_all_readings(self) -> List[Dict[str, Any]]:
        """
        Get all cached sensor readings from the device.

        Note: This clears the reading cache on the device.

        Returns:
            List[Dict[str, Any]]: List of sensor readings, each with the same format
                as the return value of get_latest_reading()

        Raises:
            ApiError: If the request fails
        """
        try:
            response = await self.get("/api/readings/all", parse_json=False)
            readings = []

            # Split the response into lines and parse each line
            for line in response.strip().split("\n"):
                if line:
                    readings.append(self._parse_reading(line))

            return readings
        except ApiError as e:
            self.logger.error(f"Failed to get all readings: {e}")
            raise

    async def set_ambient_pressure(self, pressure: int) -> str:
        """
        Set the ambient pressure for sensor calibration.

        Args:
            pressure (int): Ambient pressure in mbar (700-1200)

        Returns:
            str: Success message from the device

        Raises:
            ApiError: If the request fails or the pressure is out of range
        """
        # Validate pressure range
        if not 700 <= pressure <= 1200:
            raise ApiError(
                message=f"Pressure must be between 700 and 1200 mbar, got {pressure}",
                error_type=ApiErrorType.VALIDATION,
            )

        try:
            # Send pressure as plain text in the request body
            response = await self.post(
                "/api/ambient-pressure",
                data=str(pressure),
                headers={"Content-Type": "text/plain"},
                parse_json=False,
            )
            return response
        except ApiError as e:
            self.logger.error(f"Failed to set ambient pressure: {e}")
            raise

    async def get_info(self) -> Dict[str, Any]:
        """
        Get information about the device.

        Returns:
            Dict[str, Any]: Device information with the following keys:
                - wifi_signal (int): WiFi signal strength in dBm
                - memory_total (int): Total memory in KB
                - memory_used (int): Used memory in KB
                - memory_free (int): Free memory in KB
                - weather_status (str): Weather data status

        Raises:
            ApiError: If the request fails
        """
        try:
            response = await self.get("/spore-info", parse_json=False)
            return self._parse_info(response)
        except ApiError as e:
            self.logger.error(f"Failed to get device info: {e}")
            raise

    def _parse_reading(self, reading_text: str) -> Dict[str, Any]:
        """
        Parse a sensor reading from plain text.

        Args:
            reading_text (str): Plain text reading in the format:
                device_name,co2,temperature,humidity,timestamp

        Returns:
            Dict[str, Any]: Parsed reading
        """
        try:
            # Use CSV reader to handle potential commas in the device name
            reader = csv.reader(StringIO(reading_text))
            row = next(reader)

            if len(row) != 5:
                raise ValueError(f"Expected 5 values, got {len(row)}")

            device_name, co2, temperature, humidity, timestamp = row

            # Convert values to appropriate types
            return {
                "device_name": device_name,
                "co2": float(co2),
                "temperature": float(temperature),
                "humidity": float(humidity),
                "timestamp": timestamp,
            }
        except (ValueError, StopIteration) as e:
            raise ApiError(
                message=f"Failed to parse reading: {e}",
                error_type=ApiErrorType.VALIDATION,
                response_body=reading_text,
            )

    def _parse_info(self, info_text: str) -> Dict[str, Any]:
        """
        Parse device information from plain text.

        Args:
            info_text (str): Plain text device information

        Returns:
            Dict[str, Any]: Parsed device information
        """
        info = {}

        # Extract WiFi signal strength (format: "WiFi Signal Strength: -45 dBm")
        wifi_match = re.search(r"WiFi Signal Strength: (-?\d+) dBm", info_text)
        if wifi_match:
            info["wifi_signal"] = int(wifi_match.group(1))

        # Extract memory information (format: "Total Memory: 512 KB\nUsed Memory: 256 KB\nFree Memory: 256 KB")
        total_match = re.search(r"Total Memory: (\d+) KB", info_text)
        used_match = re.search(r"Used Memory: (\d+) KB", info_text)
        free_match = re.search(r"Free Memory: (\d+) KB", info_text)

        if total_match:
            info["memory_total"] = int(total_match.group(1))
        if used_match:
            info["memory_used"] = int(used_match.group(1))
        if free_match:
            info["memory_free"] = int(free_match.group(1))

        # Extract weather data status (look for lines about weather)
        for line in info_text.split("\n"):
            line = line.strip()
            if "weather" in line.lower() or "hyphae" in line.lower():
                info["weather_status"] = line

        return info
