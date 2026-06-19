"""
OpenWeatherMap API Client for Mycelium

This module provides a client for interacting with the OpenWeatherMap API.
It retrieves weather data for a specific location and stores it in the database.
"""

import logging
from typing import Dict, Any

from api.clients.base_client import BaseApiClient, ApiError, ApiErrorType


class OpenWeatherMapClient(BaseApiClient):
    """
    Client for interacting with the OpenWeatherMap API.

    Attributes:
        api_key (str): API key for OpenWeatherMap
        location (Dict[str, Any]): Location information (zip code, country code, lat, lon)
        units (str): Units for weather data (metric, imperial, standard)
    """

    def __init__(
        self,
        api_key: str,
        location: Dict[str, Any],
        units: str = "metric",
        timeout: int = 10,
        max_retries: int = 3,
        retry_delay: int = 1,
    ):
        """
        Initialize the OpenWeatherMap client.

        Args:
            api_key (str): API key for OpenWeatherMap
            location (Dict[str, Any]): Location information with one of the following:
                - zip (str): ZIP code with optional country code (e.g., "12345,us")
                - lat (float) and lon (float): Latitude and longitude
            units (str): Units for weather data (metric, imperial, standard)
            timeout (int): Default timeout for requests in seconds
            max_retries (int): Maximum number of retries for failed requests
            retry_delay (int): Initial delay between retries in seconds
        """
        super().__init__(
            base_url="https://api.openweathermap.org",
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            # OpenWeatherMap free tier allows 60 calls per minute
            request_limit=60,
            request_period=60,
        )
        self.api_key = api_key
        self.location = location
        self.units = units
        self.logger = logging.getLogger("api.OpenWeatherMapClient")

    async def check_connection(self) -> bool:
        """
        Check if the OpenWeatherMap API is reachable.

        Returns:
            bool: True if the API is reachable, False otherwise
        """
        try:
            await self.get_current_weather()
            return True
        except ApiError:
            return False

    async def get_current_weather(self) -> Dict[str, Any]:
        """
        Get current weather data for the configured location.

        Returns:
            Dict[str, Any]: Current weather data

        Raises:
            ApiError: If the request fails
        """
        try:
            # Build query parameters based on location type
            params = {"appid": self.api_key, "units": self.units}

            if "zip" in self.location:
                params["zip"] = self.location["zip"]
                endpoint = "/data/2.5/weather"
            elif "lat" in self.location and "lon" in self.location:
                params["lat"] = self.location["lat"]
                params["lon"] = self.location["lon"]
                endpoint = "/data/2.5/weather"
            else:
                raise ApiError(
                    message="Invalid location configuration",
                    error_type=ApiErrorType.VALIDATION,
                )

            return await self.get(endpoint, params=params)
        except ApiError as e:
            self.logger.error(f"Failed to get current weather: {e}")
            raise

    async def get_forecast(self, days: int = 5) -> Dict[str, Any]:
        """
        Get weather forecast for the configured location.

        Args:
            days (int): Number of days for the forecast (1-16)

        Returns:
            Dict[str, Any]: Weather forecast data

        Raises:
            ApiError: If the request fails
        """
        try:
            # Validate days
            if not 1 <= days <= 16:
                raise ApiError(
                    message=f"Days must be between 1 and 16, got {days}",
                    error_type=ApiErrorType.VALIDATION,
                )

            # Build query parameters based on location type
            params = {"appid": self.api_key, "units": self.units, "cnt": days}

            if "zip" in self.location:
                params["zip"] = self.location["zip"]
                endpoint = "/data/2.5/forecast/daily"
            elif "lat" in self.location and "lon" in self.location:
                params["lat"] = self.location["lat"]
                params["lon"] = self.location["lon"]
                endpoint = "/data/2.5/forecast/daily"
            else:
                raise ApiError(
                    message="Invalid location configuration",
                    error_type=ApiErrorType.VALIDATION,
                )

            return await self.get(endpoint, params=params)
        except ApiError as e:
            self.logger.error(f"Failed to get forecast: {e}")
            raise

    async def get_air_pollution(self) -> Dict[str, Any]:
        """
        Get air pollution data for the configured location.

        Note: This endpoint requires latitude and longitude coordinates.

        Returns:
            Dict[str, Any]: Air pollution data

        Raises:
            ApiError: If the request fails or coordinates are not available
        """
        try:
            # Check if we have coordinates
            if "lat" not in self.location or "lon" not in self.location:
                raise ApiError(
                    message="Air pollution data requires latitude and longitude coordinates",
                    error_type=ApiErrorType.VALIDATION,
                )

            params = {
                "appid": self.api_key,
                "lat": self.location["lat"],
                "lon": self.location["lon"],
            }

            return await self.get("/data/2.5/air_pollution", params=params)
        except ApiError as e:
            self.logger.error(f"Failed to get air pollution data: {e}")
            raise
