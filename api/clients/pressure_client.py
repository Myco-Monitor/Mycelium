"""
Pressure API Client for Mycelium

This module provides a client for fetching BMP581 pressure data from Hyphae devices.
Pressure data is used for CO2 sensor calibration and environmental monitoring.

Endpoints implemented:
- GET /api/pressure - Get current pressure reading from BMP581 sensor
- GET /api/pressure/history - Get pressure history
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from api.clients.base_client import BaseApiClient, ApiError


@dataclass
class PressureReading:
    """Data class for pressure readings from Hyphae BMP581 sensor."""

    pressure_hpa: int
    source: str
    healthy: bool
    timestamp: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "pressure_hpa": self.pressure_hpa,
            "source": self.source,
            "healthy": self.healthy,
            "timestamp": self.timestamp,
        }


class PressureClient(BaseApiClient):
    """
    Client for fetching pressure data from Hyphae BMP581 sensors.

    Attributes:
        device_name (str): Name of the Hyphae device
        device_id (int): Database ID of the Hyphae device
    """

    def __init__(
        self,
        base_url: str,
        device_name: str,
        device_id: int,
        timeout: int = 10,
        max_retries: int = 3,
        retry_delay: int = 1,
    ):
        """
        Initialize the Pressure client.

        Args:
            base_url (str): Base URL for the device API (e.g., "http://192.168.1.100")
            device_name (str): Name of the Hyphae device
            device_id (int): Database ID of the Hyphae device
            timeout (int): Default timeout for requests in seconds
            max_retries (int): Maximum number of retries for failed requests
            retry_delay (int): Initial delay between retries in seconds
        """
        super().__init__(
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            request_limit=10,
            request_period=1,
        )
        self.device_name = device_name
        self.device_id = device_id
        self.logger = logging.getLogger(f"api.PressureClient.{device_name}")

    async def check_connection(self) -> bool:
        """
        Check if the Hyphae device's pressure endpoint is reachable.

        Returns:
            bool: True if the device is reachable, False otherwise
        """
        try:
            await self.get_current_pressure()
            return True
        except ApiError:
            return False

    async def get_current_pressure(self) -> Optional[PressureReading]:
        """
        Get current pressure reading from Hyphae's BMP581 sensor.

        Returns:
            Optional[PressureReading]: Current pressure reading or None if failed

        Raises:
            ApiError: If the request fails
        """
        try:
            data = await self.get("/api/pressure")
            return PressureReading(
                pressure_hpa=data.get("pressure_hpa", 0),
                source=data.get("source", "BMP581"),
                healthy=data.get("healthy", False),
                timestamp=data.get("timestamp", 0),
            )
        except ApiError as e:
            self.logger.error(f"Failed to get current pressure: {e}")
            raise

    async def get_pressure_history(self) -> List[PressureReading]:
        """
        Get pressure history from Hyphae device.

        Returns:
            List[PressureReading]: List of historical pressure readings

        Raises:
            ApiError: If the request fails
        """
        try:
            data = await self.get("/api/pressure/history")
            readings = []
            for r in data.get("readings", []):
                readings.append(
                    PressureReading(
                        pressure_hpa=r.get("pressure_hpa", 0),
                        source="BMP581",
                        healthy=True,
                        timestamp=r.get("timestamp", 0),
                    )
                )
            return readings
        except ApiError as e:
            self.logger.error(f"Failed to get pressure history: {e}")
            raise

    def validate_pressure(self, pressure_hpa: int) -> bool:
        """
        Validate that a pressure reading is within expected range.

        Args:
            pressure_hpa: Pressure value in hectopascals

        Returns:
            bool: True if pressure is valid (970-1050 hPa range)
        """
        return 970 <= pressure_hpa <= 1050
