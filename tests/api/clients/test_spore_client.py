"""
Tests for the Spore API client.

This module contains tests for the SporeClient class.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from api.clients.spore_client import SporeClient
from api.clients.base_client import ApiError, ApiErrorType

class TestSporeClient:
    """Tests for the SporeClient class."""
    
    @pytest.fixture
    def spore_client(self):
        """Create a SporeClient instance for testing."""
        return SporeClient(
            base_url="http://spore.example.com",
            device_name="Test Spore",
            device_id=1
        )
    
    @pytest.mark.asyncio
    async def test_get_latest_reading(self, spore_client, mock_aiohttp_session):
        """Test getting the latest reading."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://spore.example.com/api/get-latest-reading",
            status=200,
            text="""
            Temperature: 23.5 C
            Humidity: 45.2 %
            Pressure: 1013.2 hPa
            Timestamp: 2023-07-18T12:34:56
            """
        )
        
        # Make request
        result = await spore_client.get_latest_reading()
        
        # Verify result
        assert result["temperature"] == 23.5
        assert result["humidity"] == 45.2
        assert result["pressure"] == 1013.2
        assert result["timestamp"] == "2023-07-18T12:34:56"
    
    @pytest.mark.asyncio
    async def test_get_all_readings(self, spore_client, mock_aiohttp_session):
        """Test getting all readings."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://spore.example.com/api/get-all-readings",
            status=200,
            text="""
            Temperature: 23.5 C, Humidity: 45.2 %, Pressure: 1013.2 hPa, Timestamp: 2023-07-18T12:34:56
            Temperature: 23.6 C, Humidity: 45.3 %, Pressure: 1013.3 hPa, Timestamp: 2023-07-18T12:35:56
            Temperature: 23.7 C, Humidity: 45.4 %, Pressure: 1013.4 hPa, Timestamp: 2023-07-18T12:36:56
            """
        )
        
        # Make request
        result = await spore_client.get_all_readings()
        
        # Verify result
        assert len(result) == 3
        assert result[0]["temperature"] == 23.5
        assert result[0]["humidity"] == 45.2
        assert result[0]["pressure"] == 1013.2
        assert result[0]["timestamp"] == "2023-07-18T12:34:56"
        
        assert result[1]["temperature"] == 23.6
        assert result[1]["humidity"] == 45.3
        assert result[1]["pressure"] == 1013.3
        assert result[1]["timestamp"] == "2023-07-18T12:35:56"
        
        assert result[2]["temperature"] == 23.7
        assert result[2]["humidity"] == 45.4
        assert result[2]["pressure"] == 1013.4
        assert result[2]["timestamp"] == "2023-07-18T12:36:56"
    
    @pytest.mark.asyncio
    async def test_set_ambient_pressure(self, spore_client, mock_aiohttp_session):
        """Test setting ambient pressure."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://spore.example.com/api/set-ambient-pressure",
            status=200,
            text="OK: Ambient pressure set to 1013.2 hPa"
        )
        
        # Make request
        result = await spore_client.set_ambient_pressure(1013.2)
        
        # Verify result
        assert result is True
    
    @pytest.mark.asyncio
    async def test_set_ambient_pressure_error(self, spore_client, mock_aiohttp_session):
        """Test error when setting ambient pressure."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://spore.example.com/api/set-ambient-pressure",
            status=400,
            text="ERROR: Invalid pressure value"
        )
        
        # Make request and verify exception
        with pytest.raises(ApiError) as excinfo:
            await spore_client.set_ambient_pressure(1013.2)
        
        # Verify error details
        error = excinfo.value
        assert error.status_code == 400
        assert error.error_type == ApiErrorType.VALIDATION
        assert "Invalid pressure value" in error.message
    
    @pytest.mark.asyncio
    async def test_get_info(self, spore_client, mock_aiohttp_session):
        """Test getting device info."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://spore.example.com/api/info",
            status=200,
            text="""
            Device Name: Test Spore
            MAC Address: 00:11:22:33:44:55
            IP Address: 192.168.1.100
            Firmware Version: 1.0.0
            Uptime: 3600
            """
        )
        
        # Make request
        result = await spore_client.get_info()
        
        # Verify result
        assert result["device_name"] == "Test Spore"
        assert result["mac_address"] == "00:11:22:33:44:55"
        assert result["ip_address"] == "192.168.1.100"
        assert result["firmware_version"] == "1.0.0"
        assert result["uptime"] == 3600
    
    @pytest.mark.asyncio
    async def test_check_connection(self, spore_client, mock_aiohttp_session):
        """Test checking connection."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://spore.example.com/api/info",
            status=200,
            text="""
            Device Name: Test Spore
            MAC Address: 00:11:22:33:44:55
            IP Address: 192.168.1.100
            Firmware Version: 1.0.0
            Uptime: 3600
            """
        )
        
        # Make request
        result = await spore_client.check_connection()
        
        # Verify result
        assert result is True
    
    @pytest.mark.asyncio
    async def test_check_connection_error(self, spore_client, mock_aiohttp_session):
        """Test checking connection with error."""
        # Configure mock to raise connection error
        mock_aiohttp_session.get.side_effect = asyncio.TimeoutError()
        
        # Make request
        result = await spore_client.check_connection()
        
        # Verify result
        assert result is False
    
    @pytest.mark.asyncio
    async def test_parse_reading_line(self, spore_client):
        """Test parsing a reading line."""
        # Test with a valid line
        line = "Temperature: 23.5 C, Humidity: 45.2 %, Pressure: 1013.2 hPa, Timestamp: 2023-07-18T12:34:56"
        result = spore_client._parse_reading_line(line)
        
        # Verify result
        assert result["temperature"] == 23.5
        assert result["humidity"] == 45.2
        assert result["pressure"] == 1013.2
        assert result["timestamp"] == "2023-07-18T12:34:56"
        
        # Test with a line missing some values
        line = "Temperature: 23.5 C, Humidity: 45.2 %, Timestamp: 2023-07-18T12:34:56"
        result = spore_client._parse_reading_line(line)
        
        # Verify result
        assert result["temperature"] == 23.5
        assert result["humidity"] == 45.2
        assert "pressure" not in result
        assert result["timestamp"] == "2023-07-18T12:34:56"
        
        # Test with an invalid line
        line = "Invalid line"
        result = spore_client._parse_reading_line(line)
        
        # Verify result
        assert result == {}
