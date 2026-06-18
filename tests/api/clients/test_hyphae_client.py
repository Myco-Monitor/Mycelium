"""
Tests for the Hyphae API client.

This module contains tests for the HyphaeClient class.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from api.clients.hyphae_client import HyphaeClient
from api.clients.base_client import ApiError, ApiErrorType

class TestHyphaeClient:
    """Tests for the HyphaeClient class."""
    
    @pytest.fixture
    def hyphae_client(self):
        """Create a HyphaeClient instance for testing."""
        return HyphaeClient(
            base_url="http://hyphae.example.com",
            device_name="Test Hyphae",
            device_id=1,
            pin="1234"
        )
    
    @pytest.mark.asyncio
    async def test_get_latest_reading(self, hyphae_client, mock_aiohttp_session):
        """Test getting the latest reading."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://hyphae.example.com/api/get-latest-reading",
            status=200,
            text="""
            Temperature: 23.5 C
            Humidity: 45.2 %
            Relay States: 1,0,1,0,1,0
            Timestamp: 2023-07-18T12:34:56
            """
        )
        
        # Make request
        result = await hyphae_client.get_latest_reading()
        
        # Verify result
        assert result["temperature"] == 23.5
        assert result["humidity"] == 45.2
        assert result["relay_states"] == [1, 0, 1, 0, 1, 0]
        assert result["timestamp"] == "2023-07-18T12:34:56"
    
    @pytest.mark.asyncio
    async def test_get_all_readings(self, hyphae_client, mock_aiohttp_session):
        """Test getting all readings."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://hyphae.example.com/api/get-all-readings",
            status=200,
            text="""
            Temperature: 23.5 C, Humidity: 45.2 %, Relay States: 1,0,1,0,1,0, Timestamp: 2023-07-18T12:34:56
            Temperature: 23.6 C, Humidity: 45.3 %, Relay States: 1,0,1,0,1,1, Timestamp: 2023-07-18T12:35:56
            Temperature: 23.7 C, Humidity: 45.4 %, Relay States: 1,0,1,0,0,1, Timestamp: 2023-07-18T12:36:56
            """
        )
        
        # Make request
        result = await hyphae_client.get_all_readings()
        
        # Verify result
        assert len(result) == 3
        assert result[0]["temperature"] == 23.5
        assert result[0]["humidity"] == 45.2
        assert result[0]["relay_states"] == [1, 0, 1, 0, 1, 0]
        assert result[0]["timestamp"] == "2023-07-18T12:34:56"
        
        assert result[1]["temperature"] == 23.6
        assert result[1]["humidity"] == 45.3
        assert result[1]["relay_states"] == [1, 0, 1, 0, 1, 1]
        assert result[1]["timestamp"] == "2023-07-18T12:35:56"
        
        assert result[2]["temperature"] == 23.7
        assert result[2]["humidity"] == 45.4
        assert result[2]["relay_states"] == [1, 0, 1, 0, 0, 1]
        assert result[2]["timestamp"] == "2023-07-18T12:36:56"
    
    @pytest.mark.asyncio
    async def test_get_relay_config(self, hyphae_client, mock_aiohttp_session):
        """Test getting relay configuration."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://hyphae.example.com/api/get-relay-config",
            status=200,
            json={
                "relays": [
                    {"name": "Relay 1", "group": 1, "type": "fan"},
                    {"name": "Relay 2", "group": 1, "type": "light"},
                    {"name": "Relay 3", "group": 2, "type": "humidifier"},
                    {"name": "Relay 4", "group": 2, "type": "heater"},
                    {"name": "Relay 5", "group": 3, "type": "fan"},
                    {"name": "Relay 6", "group": 3, "type": "light"}
                ]
            }
        )
        
        # Make request
        result = await hyphae_client.get_relay_config()
        
        # Verify result
        assert len(result["relays"]) == 6
        assert result["relays"][0]["name"] == "Relay 1"
        assert result["relays"][0]["group"] == 1
        assert result["relays"][0]["type"] == "fan"
    
    @pytest.mark.asyncio
    async def test_set_relay_config(self, hyphae_client, mock_aiohttp_session):
        """Test setting relay configuration."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://hyphae.example.com/api/set-relay-config",
            status=200,
            json={"success": True}
        )
        
        # Create config
        config = {
            "relays": [
                {"name": "Relay 1", "group": 1, "type": "fan"},
                {"name": "Relay 2", "group": 1, "type": "light"},
                {"name": "Relay 3", "group": 2, "type": "humidifier"},
                {"name": "Relay 4", "group": 2, "type": "heater"},
                {"name": "Relay 5", "group": 3, "type": "fan"},
                {"name": "Relay 6", "group": 3, "type": "light"}
            ]
        }
        
        # Make request
        result = await hyphae_client.set_relay_config(config)
        
        # Verify result
        assert result is True
    
    @pytest.mark.asyncio
    async def test_set_relay_config_no_pin(self, hyphae_client, mock_aiohttp_session):
        """Test setting relay configuration without a PIN."""
        # Create client without PIN
        client = HyphaeClient(
            base_url="http://hyphae.example.com",
            device_name="Test Hyphae",
            device_id=1
        )
        
        # Create config
        config = {
            "relays": [
                {"name": "Relay 1", "group": 1, "type": "fan"}
            ]
        }
        
        # Make request and verify exception
        with pytest.raises(ApiError) as excinfo:
            await client.set_relay_config(config)
        
        # Verify error details
        error = excinfo.value
        assert error.error_type == ApiErrorType.AUTHENTICATION
        assert "PIN is required" in error.message
    
    @pytest.mark.asyncio
    async def test_get_relay_state(self, hyphae_client, mock_aiohttp_session):
        """Test getting relay states."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://hyphae.example.com/api/get-relay-state",
            status=200,
            json={
                "states": [1, 0, 1, 0, 1, 0],
                "timestamp": "2023-07-18T12:34:56"
            }
        )
        
        # Make request
        result = await hyphae_client.get_relay_state()
        
        # Verify result
        assert result["states"] == [1, 0, 1, 0, 1, 0]
        assert result["timestamp"] == "2023-07-18T12:34:56"
    
    @pytest.mark.asyncio
    async def test_test_relay(self, hyphae_client, mock_aiohttp_session):
        """Test testing a relay."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://hyphae.example.com/api/test-relay/1",
            status=200,
            json={"success": True}
        )
        
        # Make request
        result = await hyphae_client.test_relay(1)
        
        # Verify result
        assert result is True
    
    @pytest.mark.asyncio
    async def test_test_relay_no_pin(self, hyphae_client, mock_aiohttp_session):
        """Test testing a relay without a PIN."""
        # Create client without PIN
        client = HyphaeClient(
            base_url="http://hyphae.example.com",
            device_name="Test Hyphae",
            device_id=1
        )
        
        # Make request and verify exception
        with pytest.raises(ApiError) as excinfo:
            await client.test_relay(1)
        
        # Verify error details
        error = excinfo.value
        assert error.error_type == ApiErrorType.AUTHENTICATION
        assert "PIN is required" in error.message
    
    @pytest.mark.asyncio
    async def test_get_relay_thresholds(self, hyphae_client, mock_aiohttp_session):
        """Test getting relay thresholds."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://hyphae.example.com/api/get-relay-thresholds",
            status=200,
            json={
                "groups": [
                    {"group_id": 1, "sensor_type": "temperature", "min_value": 20, "max_value": 25},
                    {"group_id": 2, "sensor_type": "humidity", "min_value": 40, "max_value": 60}
                ]
            }
        )
        
        # Make request
        result = await hyphae_client.get_relay_thresholds()
        
        # Verify result
        assert len(result["groups"]) == 2
        assert result["groups"][0]["group_id"] == 1
        assert result["groups"][0]["sensor_type"] == "temperature"
        assert result["groups"][0]["min_value"] == 20
        assert result["groups"][0]["max_value"] == 25
    
    @pytest.mark.asyncio
    async def test_set_relay_thresholds(self, hyphae_client, mock_aiohttp_session):
        """Test setting relay thresholds."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://hyphae.example.com/api/set-relay-thresholds",
            status=200,
            json={"success": True}
        )
        
        # Create thresholds
        thresholds = {
            "groups": [
                {"group_id": 1, "sensor_type": "temperature", "min_value": 20, "max_value": 25},
                {"group_id": 2, "sensor_type": "humidity", "min_value": 40, "max_value": 60}
            ]
        }
        
        # Make request
        result = await hyphae_client.set_relay_thresholds(thresholds)
        
        # Verify result
        assert result is True
    
    @pytest.mark.asyncio
    async def test_get_relay_schedule(self, hyphae_client, mock_aiohttp_session):
        """Test getting relay schedule."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://hyphae.example.com/api/get-relay-schedule",
            status=200,
            json={
                "entries": [
                    {"group_id": 1, "day": 1, "start": "08:00", "end": "20:00"},
                    {"group_id": 2, "day": 1, "start": "10:00", "end": "18:00"}
                ]
            }
        )
        
        # Make request
        result = await hyphae_client.get_relay_schedule()
        
        # Verify result
        assert len(result["entries"]) == 2
        assert result["entries"][0]["group_id"] == 1
        assert result["entries"][0]["day"] == 1
        assert result["entries"][0]["start"] == "08:00"
        assert result["entries"][0]["end"] == "20:00"
    
    @pytest.mark.asyncio
    async def test_set_relay_schedule(self, hyphae_client, mock_aiohttp_session):
        """Test setting relay schedule."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://hyphae.example.com/api/set-relay-schedule",
            status=200,
            json={"success": True}
        )
        
        # Create schedule
        schedule = {
            "entries": [
                {"group_id": 1, "day": 1, "start": "08:00", "end": "20:00"},
                {"group_id": 2, "day": 1, "start": "10:00", "end": "18:00"}
            ]
        }
        
        # Make request
        result = await hyphae_client.set_relay_schedule(schedule)
        
        # Verify result
        assert result is True
    
    @pytest.mark.asyncio
    async def test_set_relay_mode(self, hyphae_client, mock_aiohttp_session):
        """Test setting relay mode."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://hyphae.example.com/api/set-relay-mode/1",
            status=200,
            json={"success": True}
        )
        
        # Make request
        result = await hyphae_client.set_relay_mode(1)
        
        # Verify result
        assert result is True
    
    @pytest.mark.asyncio
    async def test_get_info(self, hyphae_client, mock_aiohttp_session):
        """Test getting device info."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://hyphae.example.com/api/info",
            status=200,
            json={
                "device_name": "Test Hyphae",
                "mac_address": "00:11:22:33:44:55",
                "ip_address": "192.168.1.100",
                "firmware_version": "1.0.0",
                "uptime": 3600,
                "relay_count": 6
            }
        )
        
        # Make request
        result = await hyphae_client.get_info()
        
        # Verify result
        assert result["device_name"] == "Test Hyphae"
        assert result["mac_address"] == "00:11:22:33:44:55"
        assert result["ip_address"] == "192.168.1.100"
        assert result["firmware_version"] == "1.0.0"
        assert result["uptime"] == 3600
        assert result["relay_count"] == 6
    
    @pytest.mark.asyncio
    async def test_check_connection(self, hyphae_client, mock_aiohttp_session):
        """Test checking connection."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://hyphae.example.com/api/info",
            status=200,
            json={
                "device_name": "Test Hyphae",
                "mac_address": "00:11:22:33:44:55",
                "ip_address": "192.168.1.100",
                "firmware_version": "1.0.0",
                "uptime": 3600,
                "relay_count": 6
            }
        )
        
        # Make request
        result = await hyphae_client.check_connection()
        
        # Verify result
        assert result is True
    
    @pytest.mark.asyncio
    async def test_check_connection_error(self, hyphae_client, mock_aiohttp_session):
        """Test checking connection with error."""
        # Configure mock to raise connection error
        mock_aiohttp_session.get.side_effect = asyncio.TimeoutError()
        
        # Make request
        result = await hyphae_client.check_connection()
        
        # Verify result
        assert result is False
