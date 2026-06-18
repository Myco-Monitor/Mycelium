"""
API Clients Package for Mycelium

This package contains API clients for interacting with various devices and services.
"""

from api.clients.base_client import BaseApiClient, ApiError, ApiErrorType
from api.clients.spore_client import SporeClient
from api.clients.hyphae_client import HyphaeClient
from api.clients.weather_client import OpenWeatherMapClient
from api.clients.pressure_client import PressureClient, PressureReading
from api.clients.auth_handler import DeviceAuthHandler, AuthResult, AuthenticationError

__all__ = [
    "BaseApiClient",
    "ApiError",
    "ApiErrorType",
    "SporeClient",
    "HyphaeClient",
    "OpenWeatherMapClient",
    "PressureClient",
    "PressureReading",
    "DeviceAuthHandler",
    "AuthResult",
    "AuthenticationError",
]
