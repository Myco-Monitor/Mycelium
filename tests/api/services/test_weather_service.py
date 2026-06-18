"""
Tests for the Weather service.

This module contains tests for the WeatherService class.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import json

from api.services.weather_service import WeatherService
from api.clients.weather_client import WeatherClient
from api.clients.base_client import ApiError, ApiErrorType

class TestWeatherService:
    """Tests for the WeatherService class."""
    
    @pytest.fixture
    def mock_weather_client(self):
        """Create a mock WeatherClient for testing."""
        mock_client = AsyncMock(spec=WeatherClient)
        mock_client.location_id = 1
        mock_client.location_name = "Test City"
        mock_client.api_key = "test_api_key"
        return mock_client
    
    @pytest.fixture
    def weather_service(self, mock_weather_client, mock_sqlite_connection):
        """Create a WeatherService instance for testing."""
        return WeatherService(db_connection=mock_sqlite_connection)
    
    @pytest.mark.asyncio
    async def test_get_current_weather(self, weather_service, mock_weather_client):
        """Test getting current weather."""
        # Configure mock client
        mock_weather_client.get_current_weather_by_zip.return_value = {
            "temperature": 23.5,
            "feels_like": 24.0,
            "humidity": 45,
            "pressure": 1013,
            "wind_speed": 5.2,
            "wind_direction": 180,
            "cloud_coverage": 75,
            "condition": "Clear",
            "condition_description": "clear sky",
            "timestamp": 1626619200,
            "location_name": "Test City"
        }
        
        # Make request
        result = await weather_service.get_current_weather(mock_weather_client, zip_code="12345")
        
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
        assert result["location_id"] == 1
    
    @pytest.mark.asyncio
    async def test_get_current_weather_by_coords(self, weather_service, mock_weather_client):
        """Test getting current weather by coordinates."""
        # Configure mock client
        mock_weather_client.get_current_weather_by_coords.return_value = {
            "temperature": 23.5,
            "feels_like": 24.0,
            "humidity": 45,
            "pressure": 1013,
            "wind_speed": 5.2,
            "wind_direction": 180,
            "cloud_coverage": 75,
            "condition": "Clear",
            "condition_description": "clear sky",
            "timestamp": 1626619200,
            "location_name": "Test City"
        }
        
        # Make request
        result = await weather_service.get_current_weather(
            mock_weather_client, 
            latitude=40.7128, 
            longitude=-74.006
        )
        
        # Verify result
        assert result["temperature"] == 23.5
        assert result["location_name"] == "Test City"
        assert result["location_id"] == 1
    
    @pytest.mark.asyncio
    async def test_store_current_weather(self, weather_service, mock_sqlite_connection):
        """Test storing current weather."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT COUNT(*) FROM weather_current WHERE location_id = ? AND timestamp = ?",
            (1, 1626619200),
            fetchone=(0,)
        )
        mock_sqlite_connection.add_query_result(
            "INSERT INTO weather_current (location_id, temperature, feels_like, humidity, pressure, wind_speed, wind_direction, cloud_coverage, condition, condition_description, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, 23.5, 24.0, 45, 1013, 5.2, 180, 75, "Clear", "clear sky", 1626619200),
            lastrowid=1
        )
        
        # Create weather data
        weather_data = {
            "temperature": 23.5,
            "feels_like": 24.0,
            "humidity": 45,
            "pressure": 1013,
            "wind_speed": 5.2,
            "wind_direction": 180,
            "cloud_coverage": 75,
            "condition": "Clear",
            "condition_description": "clear sky",
            "timestamp": 1626619200,
            "location_name": "Test City",
            "location_id": 1
        }
        
        # Store weather data
        result = await weather_service.store_current_weather(weather_data)
        
        # Verify result
        assert result is True
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT COUNT(*) FROM weather_current WHERE location_id = ? AND timestamp = ?",
            (1, 1626619200)
        )
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "INSERT INTO weather_current (location_id, temperature, feels_like, humidity, pressure, wind_speed, wind_direction, cloud_coverage, condition, condition_description, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, 23.5, 24.0, 45, 1013, 5.2, 180, 75, "Clear", "clear sky", 1626619200)
        )
    
    @pytest.mark.asyncio
    async def test_store_current_weather_duplicate(self, weather_service, mock_sqlite_connection):
        """Test storing duplicate current weather."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT COUNT(*) FROM weather_current WHERE location_id = ? AND timestamp = ?",
            (1, 1626619200),
            fetchone=(1,)
        )
        
        # Create weather data
        weather_data = {
            "temperature": 23.5,
            "feels_like": 24.0,
            "humidity": 45,
            "pressure": 1013,
            "wind_speed": 5.2,
            "wind_direction": 180,
            "cloud_coverage": 75,
            "condition": "Clear",
            "condition_description": "clear sky",
            "timestamp": 1626619200,
            "location_name": "Test City",
            "location_id": 1
        }
        
        # Store weather data
        result = await weather_service.store_current_weather(weather_data)
        
        # Verify result
        assert result is False
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once_with(
            "SELECT COUNT(*) FROM weather_current WHERE location_id = ? AND timestamp = ?",
            (1, 1626619200)
        )
    
    @pytest.mark.asyncio
    async def test_get_forecast(self, weather_service, mock_weather_client):
        """Test getting forecast."""
        # Configure mock client
        mock_weather_client.get_forecast_by_zip.return_value = {
            "forecast": [
                {
                    "temperature": 23.5,
                    "feels_like": 24.0,
                    "humidity": 45,
                    "pressure": 1013,
                    "wind_speed": 5.2,
                    "wind_direction": 180,
                    "cloud_coverage": 75,
                    "condition": "Clear",
                    "condition_description": "clear sky",
                    "timestamp": 1626619200,
                    "datetime": "2023-07-18 12:00:00"
                },
                {
                    "temperature": 24.5,
                    "feels_like": 25.0,
                    "humidity": 40,
                    "pressure": 1012,
                    "wind_speed": 4.8,
                    "wind_direction": 190,
                    "cloud_coverage": 65,
                    "condition": "Clouds",
                    "condition_description": "few clouds",
                    "timestamp": 1626630000,
                    "datetime": "2023-07-18 15:00:00"
                }
            ],
            "location_name": "Test City"
        }
        
        # Make request
        result = await weather_service.get_forecast(mock_weather_client, zip_code="12345")
        
        # Verify result
        assert len(result["forecast"]) == 2
        assert result["location_name"] == "Test City"
        assert result["location_id"] == 1
        
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
    
    @pytest.mark.asyncio
    async def test_store_forecast(self, weather_service, mock_sqlite_connection):
        """Test storing forecast."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT COUNT(*) FROM weather_forecast WHERE location_id = ? AND timestamp = ?",
            (1, 1626619200),
            fetchone=(0,)
        )
        mock_sqlite_connection.add_query_result(
            "INSERT INTO weather_forecast (location_id, temperature, feels_like, humidity, pressure, wind_speed, wind_direction, cloud_coverage, condition, condition_description, timestamp, datetime) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, 23.5, 24.0, 45, 1013, 5.2, 180, 75, "Clear", "clear sky", 1626619200, "2023-07-18 12:00:00"),
            lastrowid=1
        )
        
        # Create forecast data
        forecast_data = {
            "forecast": [
                {
                    "temperature": 23.5,
                    "feels_like": 24.0,
                    "humidity": 45,
                    "pressure": 1013,
                    "wind_speed": 5.2,
                    "wind_direction": 180,
                    "cloud_coverage": 75,
                    "condition": "Clear",
                    "condition_description": "clear sky",
                    "timestamp": 1626619200,
                    "datetime": "2023-07-18 12:00:00"
                }
            ],
            "location_name": "Test City",
            "location_id": 1
        }
        
        # Store forecast data
        result = await weather_service.store_forecast(forecast_data)
        
        # Verify result
        assert result is True
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT COUNT(*) FROM weather_forecast WHERE location_id = ? AND timestamp = ?",
            (1, 1626619200)
        )
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "INSERT INTO weather_forecast (location_id, temperature, feels_like, humidity, pressure, wind_speed, wind_direction, cloud_coverage, condition, condition_description, timestamp, datetime) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, 23.5, 24.0, 45, 1013, 5.2, 180, 75, "Clear", "clear sky", 1626619200, "2023-07-18 12:00:00")
        )
    
    @pytest.mark.asyncio
    async def test_get_air_pollution(self, weather_service, mock_weather_client):
        """Test getting air pollution."""
        # Configure mock client
        mock_weather_client.get_air_pollution_by_coords.return_value = {
            "timestamp": 1626619200,
            "aqi": 2,
            "co": 250.34,
            "no": 5.67,
            "no2": 10.23,
            "o3": 80.56,
            "so2": 2.45,
            "pm2_5": 8.12,
            "pm10": 12.34,
            "nh3": 1.23
        }
        
        # Make request
        result = await weather_service.get_air_pollution(mock_weather_client, latitude=40.7128, longitude=-74.006)
        
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
        assert result["location_id"] == 1
    
    @pytest.mark.asyncio
    async def test_store_air_pollution(self, weather_service, mock_sqlite_connection):
        """Test storing air pollution."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT COUNT(*) FROM weather_air_pollution WHERE location_id = ? AND timestamp = ?",
            (1, 1626619200),
            fetchone=(0,)
        )
        mock_sqlite_connection.add_query_result(
            "INSERT INTO weather_air_pollution (location_id, aqi, co, no, no2, o3, so2, pm2_5, pm10, nh3, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, 2, 250.34, 5.67, 10.23, 80.56, 2.45, 8.12, 12.34, 1.23, 1626619200),
            lastrowid=1
        )
        
        # Create air pollution data
        pollution_data = {
            "timestamp": 1626619200,
            "aqi": 2,
            "co": 250.34,
            "no": 5.67,
            "no2": 10.23,
            "o3": 80.56,
            "so2": 2.45,
            "pm2_5": 8.12,
            "pm10": 12.34,
            "nh3": 1.23,
            "location_id": 1
        }
        
        # Store air pollution data
        result = await weather_service.store_air_pollution(pollution_data)
        
        # Verify result
        assert result is True
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT COUNT(*) FROM weather_air_pollution WHERE location_id = ? AND timestamp = ?",
            (1, 1626619200)
        )
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "INSERT INTO weather_air_pollution (location_id, aqi, co, no, no2, o3, so2, pm2_5, pm10, nh3, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, 2, 250.34, 5.67, 10.23, 80.56, 2.45, 8.12, 12.34, 1.23, 1626619200)
        )
    
    @pytest.mark.asyncio
    async def test_poll_weather(self, weather_service, mock_weather_client):
        """Test polling weather."""
        # Configure mock client
        mock_weather_client.get_current_weather_by_zip.return_value = {
            "temperature": 23.5,
            "feels_like": 24.0,
            "humidity": 45,
            "pressure": 1013,
            "wind_speed": 5.2,
            "wind_direction": 180,
            "cloud_coverage": 75,
            "condition": "Clear",
            "condition_description": "clear sky",
            "timestamp": 1626619200,
            "location_name": "Test City"
        }
        
        mock_weather_client.get_forecast_by_zip.return_value = {
            "forecast": [
                {
                    "temperature": 23.5,
                    "feels_like": 24.0,
                    "humidity": 45,
                    "pressure": 1013,
                    "wind_speed": 5.2,
                    "wind_direction": 180,
                    "cloud_coverage": 75,
                    "condition": "Clear",
                    "condition_description": "clear sky",
                    "timestamp": 1626619200,
                    "datetime": "2023-07-18 12:00:00"
                }
            ],
            "location_name": "Test City"
        }
        
        mock_weather_client.get_air_pollution_by_coords.return_value = {
            "timestamp": 1626619200,
            "aqi": 2,
            "co": 250.34,
            "no": 5.67,
            "no2": 10.23,
            "o3": 80.56,
            "so2": 2.45,
            "pm2_5": 8.12,
            "pm10": 12.34,
            "nh3": 1.23
        }
        
        # Configure mock service methods
        weather_service.store_current_weather = AsyncMock(return_value=True)
        weather_service.store_forecast = AsyncMock(return_value=True)
        weather_service.store_air_pollution = AsyncMock(return_value=True)
        
        # Configure mock database for location info
        mock_sqlite_connection.add_query_result(
            "SELECT latitude, longitude FROM weather_locations WHERE id = ?",
            (1,),
            fetchone=(40.7128, -74.006)
        )
        
        # Poll weather
        result = await weather_service.poll_weather(mock_weather_client, zip_code="12345")
        
        # Verify result
        assert result is True
        
        # Verify client calls
        mock_weather_client.get_current_weather_by_zip.assert_called_once_with("12345")
        mock_weather_client.get_forecast_by_zip.assert_called_once_with("12345")
        mock_weather_client.get_air_pollution_by_coords.assert_called_once_with(40.7128, -74.006)
        
        # Verify service calls
        weather_service.store_current_weather.assert_called_once()
        weather_service.store_forecast.assert_called_once()
        weather_service.store_air_pollution.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_poll_weather_error(self, weather_service, mock_weather_client):
        """Test polling weather with error."""
        # Configure mock client
        mock_weather_client.get_current_weather_by_zip.side_effect = ApiError(
            status_code=500,
            error_type=ApiErrorType.SERVER_ERROR,
            message="Internal Server Error"
        )
        
        # Poll weather
        result = await weather_service.poll_weather(mock_weather_client, zip_code="12345")
        
        # Verify result
        assert result is False
        
        # Verify client calls
        mock_weather_client.get_current_weather_by_zip.assert_called_once_with("12345")
        
        # Verify service calls
        assert not weather_service.store_current_weather.called
        assert not weather_service.store_forecast.called
        assert not weather_service.store_air_pollution.called
