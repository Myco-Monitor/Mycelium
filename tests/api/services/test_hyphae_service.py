"""
Tests for the Hyphae service.

This module contains tests for the HyphaeService class.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import datetime

from api.services.hyphae_service import HyphaeService
from api.clients.hyphae_client import HyphaeClient
from api.clients.base_client import ApiError, ApiErrorType

class TestHyphaeService:
    """Tests for the HyphaeService class."""
    
    @pytest.fixture
    def mock_hyphae_client(self):
        """Create a mock HyphaeClient for testing."""
        mock_client = AsyncMock(spec=HyphaeClient)
        mock_client.device_id = 1
        mock_client.device_name = "Test Hyphae"
        mock_client.base_url = "http://hyphae.example.com"
        mock_client.pin = "1234"
        return mock_client
    
    @pytest.fixture
    def hyphae_service(self, mock_hyphae_client, mock_sqlite_connection):
        """Create a HyphaeService instance for testing."""
        return HyphaeService(db_connection=mock_sqlite_connection)
    
    @pytest.mark.asyncio
    async def test_get_latest_reading(self, hyphae_service, mock_hyphae_client):
        """Test getting the latest reading."""
        # Configure mock client
        mock_hyphae_client.get_latest_reading.return_value = {
            "temperature": 23.5,
            "humidity": 45.2,
            "relay_states": [1, 0, 1, 0, 1, 0],
            "timestamp": "2023-07-18T12:34:56"
        }
        
        # Make request
        result = await hyphae_service.get_latest_reading(mock_hyphae_client)
        
        # Verify result
        assert result["temperature"] == 23.5
        assert result["humidity"] == 45.2
        assert result["relay_states"] == [1, 0, 1, 0, 1, 0]
        assert result["timestamp"] == "2023-07-18T12:34:56"
        assert result["device_id"] == 1
    
    @pytest.mark.asyncio
    async def test_store_reading(self, hyphae_service, mock_hyphae_client, mock_sqlite_connection):
        """Test storing a reading."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT COUNT(*) FROM hyphae_readings WHERE device_id = ? AND timestamp = ?",
            (1, "2023-07-18T12:34:56"),
            fetchone=(0,)
        )
        mock_sqlite_connection.add_query_result(
            "INSERT INTO hyphae_readings (device_id, temperature, humidity, relay_states, timestamp) VALUES (?, ?, ?, ?, ?)",
            (1, 23.5, 45.2, "1,0,1,0,1,0", "2023-07-18T12:34:56"),
            lastrowid=1
        )
        
        # Create reading
        reading = {
            "temperature": 23.5,
            "humidity": 45.2,
            "relay_states": [1, 0, 1, 0, 1, 0],
            "timestamp": "2023-07-18T12:34:56",
            "device_id": 1
        }
        
        # Store reading
        result = await hyphae_service.store_reading(reading)
        
        # Verify result
        assert result is True
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT COUNT(*) FROM hyphae_readings WHERE device_id = ? AND timestamp = ?",
            (1, "2023-07-18T12:34:56")
        )
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "INSERT INTO hyphae_readings (device_id, temperature, humidity, relay_states, timestamp) VALUES (?, ?, ?, ?, ?)",
            (1, 23.5, 45.2, "1,0,1,0,1,0", "2023-07-18T12:34:56")
        )
    
    @pytest.mark.asyncio
    async def test_store_reading_duplicate(self, hyphae_service, mock_hyphae_client, mock_sqlite_connection):
        """Test storing a duplicate reading."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT COUNT(*) FROM hyphae_readings WHERE device_id = ? AND timestamp = ?",
            (1, "2023-07-18T12:34:56"),
            fetchone=(1,)
        )
        
        # Create reading
        reading = {
            "temperature": 23.5,
            "humidity": 45.2,
            "relay_states": [1, 0, 1, 0, 1, 0],
            "timestamp": "2023-07-18T12:34:56",
            "device_id": 1
        }
        
        # Store reading
        result = await hyphae_service.store_reading(reading)
        
        # Verify result
        assert result is False
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once_with(
            "SELECT COUNT(*) FROM hyphae_readings WHERE device_id = ? AND timestamp = ?",
            (1, "2023-07-18T12:34:56")
        )
    
    @pytest.mark.asyncio
    async def test_get_readings_for_device(self, hyphae_service, mock_sqlite_connection):
        """Test getting readings for a device."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT temperature, humidity, relay_states, timestamp FROM hyphae_readings WHERE device_id = ? ORDER BY timestamp DESC LIMIT ?",
            (1, 10),
            fetchall=[
                (23.5, 45.2, "1,0,1,0,1,0", "2023-07-18T12:34:56"),
                (23.6, 45.3, "1,0,1,0,1,1", "2023-07-18T12:35:56")
            ]
        )
        
        # Get readings
        result = await hyphae_service.get_readings_for_device(1, limit=10)
        
        # Verify result
        assert len(result) == 2
        assert result[0]["temperature"] == 23.5
        assert result[0]["humidity"] == 45.2
        assert result[0]["relay_states"] == [1, 0, 1, 0, 1, 0]
        assert result[0]["timestamp"] == "2023-07-18T12:34:56"
        
        assert result[1]["temperature"] == 23.6
        assert result[1]["humidity"] == 45.3
        assert result[1]["relay_states"] == [1, 0, 1, 0, 1, 1]
        assert result[1]["timestamp"] == "2023-07-18T12:35:56"
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once_with(
            "SELECT temperature, humidity, relay_states, timestamp FROM hyphae_readings WHERE device_id = ? ORDER BY timestamp DESC LIMIT ?",
            (1, 10)
        )
    
    @pytest.mark.asyncio
    async def test_get_device_info(self, hyphae_service, mock_hyphae_client):
        """Test getting device info."""
        # Configure mock client
        mock_hyphae_client.get_info.return_value = {
            "device_name": "Test Hyphae",
            "mac_address": "00:11:22:33:44:55",
            "ip_address": "192.168.1.100",
            "firmware_version": "1.0.0",
            "uptime": 3600,
            "relay_count": 6
        }
        
        # Make request
        result = await hyphae_service.get_device_info(mock_hyphae_client)
        
        # Verify result
        assert result["device_name"] == "Test Hyphae"
        assert result["mac_address"] == "00:11:22:33:44:55"
        assert result["ip_address"] == "192.168.1.100"
        assert result["firmware_version"] == "1.0.0"
        assert result["uptime"] == 3600
        assert result["relay_count"] == 6
    
    @pytest.mark.asyncio
    async def test_update_device_status(self, hyphae_service, mock_sqlite_connection):
        """Test updating device status."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "UPDATE device_hyphae SET is_online = ?, last_seen = ? WHERE id = ?",
            (1, "2023-07-18T12:34:56", 1)
        )
        
        # Update status
        result = await hyphae_service.update_device_status(1, True, "2023-07-18T12:34:56")
        
        # Verify result
        assert result is True
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once_with(
            "UPDATE device_hyphae SET is_online = ?, last_seen = ? WHERE id = ?",
            (1, "2023-07-18T12:34:56", 1)
        )
    
    @pytest.mark.asyncio
    async def test_get_relay_config(self, hyphae_service, mock_hyphae_client):
        """Test getting relay configuration."""
        # Configure mock client
        mock_hyphae_client.get_relay_config.return_value = {
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
        result = await hyphae_service.get_relay_config(mock_hyphae_client)
        
        # Verify result
        assert len(result["relays"]) == 6
        assert result["relays"][0]["name"] == "Relay 1"
        assert result["relays"][0]["group"] == 1
        assert result["relays"][0]["type"] == "fan"
    
    @pytest.mark.asyncio
    async def test_set_relay_config(self, hyphae_service, mock_hyphae_client, mock_sqlite_connection):
        """Test setting relay configuration."""
        # Configure mock client
        mock_hyphae_client.set_relay_config.return_value = True
        
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "UPDATE device_hyphae SET relay_config = ? WHERE id = ?",
            ('{"relays":[{"name":"Relay 1","group":1,"type":"fan"},{"name":"Relay 2","group":1,"type":"light"},{"name":"Relay 3","group":2,"type":"humidifier"},{"name":"Relay 4","group":2,"type":"heater"},{"name":"Relay 5","group":3,"type":"fan"},{"name":"Relay 6","group":3,"type":"light"}]}', 1)
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
        result = await hyphae_service.set_relay_config(mock_hyphae_client, config)
        
        # Verify result
        assert result is True
        
        # Verify client calls
        mock_hyphae_client.set_relay_config.assert_called_once_with(config)
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_relay_thresholds(self, hyphae_service, mock_hyphae_client):
        """Test getting relay thresholds."""
        # Configure mock client
        mock_hyphae_client.get_relay_thresholds.return_value = {
            "groups": [
                {"group_id": 1, "sensor_type": "temperature", "min_value": 20, "max_value": 25},
                {"group_id": 2, "sensor_type": "humidity", "min_value": 40, "max_value": 60}
            ]
        }
        
        # Make request
        result = await hyphae_service.get_relay_thresholds(mock_hyphae_client)
        
        # Verify result
        assert len(result["groups"]) == 2
        assert result["groups"][0]["group_id"] == 1
        assert result["groups"][0]["sensor_type"] == "temperature"
        assert result["groups"][0]["min_value"] == 20
        assert result["groups"][0]["max_value"] == 25
    
    @pytest.mark.asyncio
    async def test_set_relay_thresholds(self, hyphae_service, mock_hyphae_client, mock_sqlite_connection):
        """Test setting relay thresholds."""
        # Configure mock client
        mock_hyphae_client.set_relay_thresholds.return_value = True
        
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "UPDATE device_hyphae SET relay_thresholds = ? WHERE id = ?",
            ('{"groups":[{"group_id":1,"sensor_type":"temperature","min_value":20,"max_value":25},{"group_id":2,"sensor_type":"humidity","min_value":40,"max_value":60}]}', 1)
        )
        
        # Create thresholds
        thresholds = {
            "groups": [
                {"group_id": 1, "sensor_type": "temperature", "min_value": 20, "max_value": 25},
                {"group_id": 2, "sensor_type": "humidity", "min_value": 40, "max_value": 60}
            ]
        }
        
        # Make request
        result = await hyphae_service.set_relay_thresholds(mock_hyphae_client, thresholds)
        
        # Verify result
        assert result is True
        
        # Verify client calls
        mock_hyphae_client.set_relay_thresholds.assert_called_once_with(thresholds)
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_relay_schedule(self, hyphae_service, mock_hyphae_client):
        """Test getting relay schedule."""
        # Configure mock client
        mock_hyphae_client.get_relay_schedule.return_value = {
            "entries": [
                {"group_id": 1, "day": 1, "start": "08:00", "end": "20:00"},
                {"group_id": 2, "day": 1, "start": "10:00", "end": "18:00"}
            ]
        }
        
        # Make request
        result = await hyphae_service.get_relay_schedule(mock_hyphae_client)
        
        # Verify result
        assert len(result["entries"]) == 2
        assert result["entries"][0]["group_id"] == 1
        assert result["entries"][0]["day"] == 1
        assert result["entries"][0]["start"] == "08:00"
        assert result["entries"][0]["end"] == "20:00"
    
    @pytest.mark.asyncio
    async def test_set_relay_schedule(self, hyphae_service, mock_hyphae_client, mock_sqlite_connection):
        """Test setting relay schedule."""
        # Configure mock client
        mock_hyphae_client.set_relay_schedule.return_value = True
        
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "UPDATE device_hyphae SET relay_schedule = ? WHERE id = ?",
            ('{"entries":[{"group_id":1,"day":1,"start":"08:00","end":"20:00"},{"group_id":2,"day":1,"start":"10:00","end":"18:00"}]}', 1)
        )
        
        # Create schedule
        schedule = {
            "entries": [
                {"group_id": 1, "day": 1, "start": "08:00", "end": "20:00"},
                {"group_id": 2, "day": 1, "start": "10:00", "end": "18:00"}
            ]
        }
        
        # Make request
        result = await hyphae_service.set_relay_schedule(mock_hyphae_client, schedule)
        
        # Verify result
        assert result is True
        
        # Verify client calls
        mock_hyphae_client.set_relay_schedule.assert_called_once_with(schedule)
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_set_relay_mode(self, hyphae_service, mock_hyphae_client, mock_sqlite_connection):
        """Test setting relay mode."""
        # Configure mock client
        mock_hyphae_client.set_relay_mode.return_value = True
        
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "UPDATE device_hyphae SET relay_mode = ? WHERE id = ?",
            (1, 1)
        )
        
        # Make request
        result = await hyphae_service.set_relay_mode(mock_hyphae_client, 1)
        
        # Verify result
        assert result is True
        
        # Verify client calls
        mock_hyphae_client.set_relay_mode.assert_called_once_with(1)
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_test_relay(self, hyphae_service, mock_hyphae_client):
        """Test testing a relay."""
        # Configure mock client
        mock_hyphae_client.test_relay.return_value = True
        
        # Make request
        result = await hyphae_service.test_relay(mock_hyphae_client, 1)
        
        # Verify result
        assert result is True
        
        # Verify client calls
        mock_hyphae_client.test_relay.assert_called_once_with(1)
    
    @pytest.mark.asyncio
    async def test_poll_device(self, hyphae_service, mock_hyphae_client):
        """Test polling a device."""
        # Configure mock client
        mock_hyphae_client.get_latest_reading.return_value = {
            "temperature": 23.5,
            "humidity": 45.2,
            "relay_states": [1, 0, 1, 0, 1, 0],
            "timestamp": "2023-07-18T12:34:56"
        }
        
        # Configure mock service methods
        hyphae_service.store_reading = AsyncMock(return_value=True)
        hyphae_service.update_device_status = AsyncMock(return_value=True)
        
        # Poll device
        result = await hyphae_service.poll_device(mock_hyphae_client)
        
        # Verify result
        assert result is True
        
        # Verify client calls
        mock_hyphae_client.get_latest_reading.assert_called_once()
        
        # Verify service calls
        hyphae_service.store_reading.assert_called_once()
        hyphae_service.update_device_status.assert_called_once_with(1, True, "2023-07-18T12:34:56")
    
    @pytest.mark.asyncio
    async def test_poll_device_error(self, hyphae_service, mock_hyphae_client):
        """Test polling a device with error."""
        # Configure mock client
        mock_hyphae_client.get_latest_reading.side_effect = ApiError(
            status_code=500,
            error_type=ApiErrorType.SERVER_ERROR,
            message="Internal Server Error"
        )
        
        # Configure mock service methods
        hyphae_service.update_device_status = AsyncMock(return_value=True)
        
        # Poll device
        result = await hyphae_service.poll_device(mock_hyphae_client)
        
        # Verify result
        assert result is False
        
        # Verify client calls
        mock_hyphae_client.get_latest_reading.assert_called_once()
        
        # Verify service calls
        hyphae_service.update_device_status.assert_called_once_with(1, False, None)
