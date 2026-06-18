"""
Tests for the OpenWeatherMap API client.

This module contains tests for the WeatherClient class.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from api.clients.weather_client import WeatherClient
from api.clients.base_client import ApiError, ApiErrorType

class TestWeatherClient:
    """Tests for the WeatherClient class."""
    
    @pytest.fixture
    def weather_client(self):
        """Create a WeatherClient instance for testing."""
        return WeatherClient(
            api_key="test_api_key",
            location_name="Test City",
            location_id=1
        )
    
    @pytest.mark.asyncio
    async def test_get_current_weather_by_zip(self, weather_client, mock_aiohttp_session):
        """Test getting current weather by ZIP code."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "https://api.openweathermap.org/data/2.5/weather?zip=12345,us&appid=test_api_key&units=metric",
            status=200,
            json={
                "main": {
                    "temp": 23.5,
                    "feels_like": 24.0,
                    "temp_min": 22.0,
                    "temp_max": 25.0,
                    "pressure": 1013,
                    "humidity": 45
                },
                "wind": {
                    "speed": 5.2,
                    "deg": 180
                },
                "clouds": {
                    "all": 75
                },
                "weather": [
                    {
                        "id": 800,
                        "main": "Clear",
                        "description": "clear sky",
                        "icon": "01d"
                    }
                ],
                "dt": 1626619200,
                "name": "Test City"
            }
        )
        
        # Make request
        result = await weather_client.get_current_weather_by_zip("12345")
        
        # Verify result
        assert result["temperature"] == 23.5
        assert result["feels_like"] == 24.0
        assert result["humidity"] == 45
        assert result["pressure"] == 1013
        assert result["wind_speed"] == 5.2
        assert result["wind_direction"] == 180
        assert result["cloud_coverage"] == 75
        assert result["condition"] == "Clear"
        assert result["condition_description"] == "clear sky"
        assert result["timestamp"] == 1626619200
        assert result["location_name"] == "Test City"
    
    @pytest.mark.asyncio
    async def test_get_current_weather_by_coords(self, weather_client, mock_aiohttp_session):
        """Test getting current weather by coordinates."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "https://api.openweathermap.org/data/2.5/weather?lat=40.7128&lon=-74.006&appid=test_api_key&units=metric",
            status=200,
            json={
                "main": {
                    "temp": 23.5,
                    "feels_like": 24.0,
                    "temp_min": 22.0,
                    "temp_max": 25.0,
                    "pressure": 1013,
                    "humidity": 45
                },
                "wind": {
                    "speed": 5.2,
                    "deg": 180
                },
                "clouds": {
                    "all": 75
                },
                "weather": [
                    {
                        "id": 800,
                        "main": "Clear",
                        "description": "clear sky",
                        "icon": "01d"
                    }
                ],
                "dt": 1626619200,
                "name": "New York"
            }
        )
        
        # Make request
        result = await weather_client.get_current_weather_by_coords(40.7128, -74.006)
        
        # Verify result
        assert result["temperature"] == 23.5
        assert result["feels_like"] == 24.0
        assert result["humidity"] == 45
        assert result["pressure"] == 1013
        assert result["wind_speed"] == 5.2
        assert result["wind_direction"] == 180
        assert result["cloud_coverage"] == 75
        assert result["condition"] == "Clear"
        assert result["condition_description"] == "clear sky"
        assert result["timestamp"] == 1626619200
        assert result["location_name"] == "New York"
    
    @pytest.mark.asyncio
    async def test_get_forecast_by_zip(self, weather_client, mock_aiohttp_session):
        """Test getting forecast by ZIP code."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "https://api.openweathermap.org/data/2.5/forecast?zip=12345,us&appid=test_api_key&units=metric",
            status=200,
            json={
                "list": [
                    {
                        "dt": 1626619200,
                        "main": {
                            "temp": 23.5,
                            "feels_like": 24.0,
                            "temp_min": 22.0,
                            "temp_max": 25.0,
                            "pressure": 1013,
                            "humidity": 45
                        },
                        "wind": {
                            "speed": 5.2,
                            "deg": 180
                        },
                        "clouds": {
                            "all": 75
                        },
                        "weather": [
                            {
                                "id": 800,
                                "main": "Clear",
                                "description": "clear sky",
                                "icon": "01d"
                            }
                        ],
                        "dt_txt": "2023-07-18 12:00:00"
                    },
                    {
                        "dt": 1626630000,
                        "main": {
                            "temp": 24.5,
                            "feels_like": 25.0,
                            "temp_min": 23.0,
                            "temp_max": 26.0,
                            "pressure": 1012,
                            "humidity": 40
                        },
                        "wind": {
                            "speed": 4.8,
                            "deg": 190
                        },
                        "clouds": {
                            "all": 65
                        },
                        "weather": [
                            {
                                "id": 801,
                                "main": "Clouds",
                                "description": "few clouds",
                                "icon": "02d"
                            }
                        ],
                        "dt_txt": "2023-07-18 15:00:00"
                    }
                ],
                "city": {
                    "name": "Test City"
                }
            }
        )
        
        # Make request
        result = await weather_client.get_forecast_by_zip("12345")
        
        # Verify result
        assert len(result["forecast"]) == 2
        assert result["location_name"] == "Test City"
        
        # Check first forecast entry
        assert result["forecast"][0]["temperature"] == 23.5
        assert result["forecast"][0]["feels_like"] == 24.0
        assert result["forecast"][0]["humidity"] == 45
        assert result["forecast"][0]["pressure"] == 1013
        assert result["forecast"][0]["wind_speed"] == 5.2
        assert result["forecast"][0]["wind_direction"] == 180
        assert result["forecast"][0]["cloud_coverage"] == 75
        assert result["forecast"][0]["condition"] == "Clear"
        assert result["forecast"][0]["condition_description"] == "clear sky"
        assert result["forecast"][0]["timestamp"] == 1626619200
        assert result["forecast"][0]["datetime"] == "2023-07-18 12:00:00"
        
        # Check second forecast entry
        assert result["forecast"][1]["temperature"] == 24.5
        assert result["forecast"][1]["feels_like"] == 25.0
        assert result["forecast"][1]["humidity"] == 40
        assert result["forecast"][1]["pressure"] == 1012
        assert result["forecast"][1]["wind_speed"] == 4.8
        assert result["forecast"][1]["wind_direction"] == 190
        assert result["forecast"][1]["cloud_coverage"] == 65
        assert result["forecast"][1]["condition"] == "Clouds"
        assert result["forecast"][1]["condition_description"] == "few clouds"
        assert result["forecast"][1]["timestamp"] == 1626630000
        assert result["forecast"][1]["datetime"] == "2023-07-18 15:00:00"
    
    @pytest.mark.asyncio
    async def test_get_forecast_by_coords(self, weather_client, mock_aiohttp_session):
        """Test getting forecast by coordinates."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "https://api.openweathermap.org/data/2.5/forecast?lat=40.7128&lon=-74.006&appid=test_api_key&units=metric",
            status=200,
            json={
                "list": [
                    {
                        "dt": 1626619200,
                        "main": {
                            "temp": 23.5,
                            "feels_like": 24.0,
                            "temp_min": 22.0,
                            "temp_max": 25.0,
                            "pressure": 1013,
                            "humidity": 45
                        },
                        "wind": {
                            "speed": 5.2,
                            "deg": 180
                        },
                        "clouds": {
                            "all": 75
                        },
                        "weather": [
                            {
                                "id": 800,
                                "main": "Clear",
                                "description": "clear sky",
                                "icon": "01d"
                            }
                        ],
                        "dt_txt": "2023-07-18 12:00:00"
                    }
                ],
                "city": {
                    "name": "New York"
                }
            }
        )
        
        # Make request
        result = await weather_client.get_forecast_by_coords(40.7128, -74.006)
        
        # Verify result
        assert len(result["forecast"]) == 1
        assert result["location_name"] == "New York"
        
        # Check forecast entry
        assert result["forecast"][0]["temperature"] == 23.5
        assert result["forecast"][0]["feels_like"] == 24.0
        assert result["forecast"][0]["humidity"] == 45
        assert result["forecast"][0]["pressure"] == 1013
        assert result["forecast"][0]["wind_speed"] == 5.2
        assert result["forecast"][0]["wind_direction"] == 180
        assert result["forecast"][0]["cloud_coverage"] == 75
        assert result["forecast"][0]["condition"] == "Clear"
        assert result["forecast"][0]["condition_description"] == "clear sky"
        assert result["forecast"][0]["timestamp"] == 1626619200
        assert result["forecast"][0]["datetime"] == "2023-07-18 12:00:00"
    
    @pytest.mark.asyncio
    async def test_get_air_pollution_by_coords(self, weather_client, mock_aiohttp_session):
        """Test getting air pollution by coordinates."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "https://api.openweathermap.org/data/2.5/air_pollution?lat=40.7128&lon=-74.006&appid=test_api_key",
            status=200,
            json={
                "list": [
                    {
                        "dt": 1626619200,
                        "main": {
                            "aqi": 2
                        },
                        "components": {
                            "co": 250.34,
                            "no": 5.67,
                            "no2": 10.23,
                            "o3": 80.56,
                            "so2": 2.45,
                            "pm2_5": 8.12,
                            "pm10": 12.34,
                            "nh3": 1.23
                        }
                    }
                ]
            }
        )
        
        # Make request
        result = await weather_client.get_air_pollution_by_coords(40.7128, -74.006)
        
        # Verify result
        assert result["timestamp"] == 1626619200
        assert result["aqi"] == 2
        assert result["co"] == 250.34
        assert result["no"] == 5.67
        assert result["no2"] == 10.23
        assert result["o3"] == 80.56
        assert result["so2"] == 2.45
        assert result["pm2_5"] == 8.12
        assert result["pm10"] == 12.34
        assert result["nh3"] == 1.23
    
    @pytest.mark.asyncio
    async def test_api_error(self, weather_client, mock_aiohttp_session):
        """Test handling API errors."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "https://api.openweathermap.org/data/2.5/weather?zip=12345,us&appid=test_api_key&units=metric",
            status=401,
            json={
                "cod": 401,
                "message": "Invalid API key"
            }
        )
        
        # Make request and verify exception
        with pytest.raises(ApiError) as excinfo:
            await weather_client.get_current_weather_by_zip("12345")
        
        # Verify error details
        error = excinfo.value
        assert error.status_code == 401
        assert error.error_type == ApiErrorType.AUTHENTICATION
        assert "Invalid API key" in error.message
    
    @pytest.mark.asyncio
    async def test_check_connection(self, weather_client, mock_aiohttp_session):
        """Test checking connection."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "https://api.openweathermap.org/data/2.5/weather?lat=0&lon=0&appid=test_api_key&units=metric",
            status=200,
            json={
                "main": {
                    "temp": 23.5,
                    "humidity": 45
                },
                "dt": 1626619200,
                "name": "Test"
            }
        )
        
        # Make request
        result = await weather_client.check_connection()
        
        # Verify result
        assert result is True
    
    @pytest.mark.asyncio
    async def test_check_connection_error(self, weather_client, mock_aiohttp_session):
        """Test checking connection with error."""
        # Configure mock to raise connection error
        mock_aiohttp_session.get.side_effect = asyncio.TimeoutError()
        
        # Make request
        result = await weather_client.check_connection()
        
        # Verify result
        assert result is False
