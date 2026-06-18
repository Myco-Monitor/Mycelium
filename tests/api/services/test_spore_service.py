"""
Tests for the Spore service.

This module contains tests for the SporeService class.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import datetime

from api.services.spore_service import SporeService
from api.clients.spore_client import SporeClient
from api.clients.base_client import ApiError, ApiErrorType

class TestSporeService:
    """Tests for the SporeService class."""
    
    @pytest.fixture
    def mock_spore_client(self):
        """Create a mock SporeClient for testing."""
        mock_client = AsyncMock(spec=SporeClient)
        mock_client.device_id = 1
        mock_client.device_name = "Test Spore"
        mock_client.base_url = "http://spore.example.com"
        return mock_client
    
    @pytest.fixture
    def spore_service(self, mock_spore_client, mock_sqlite_connection):
        """Create a SporeService instance for testing."""
        return SporeService(db_connection=mock_sqlite_connection)
    
    @pytest.mark.asyncio
    async def test_get_latest_reading(self, spore_service, mock_spore_client):
        """Test getting the latest reading."""
        # Configure mock client
        mock_spore_client.get_latest_reading.return_value = {
            "temperature": 23.5,
            "humidity": 45.2,
            "pressure": 1013.2,
            "timestamp": "2023-07-18T12:34:56"
        }
        
        # Make request
        result = await spore_service.get_latest_reading(mock_spore_client)
        
        # Verify result
        assert result["temperature"] == 23.5
        assert result["humidity"] == 45.2
        assert result["pressure"] == 1013.2
        assert result["timestamp"] == "2023-07-18T12:34:56"
        assert result["device_id"] == 1
    
    @pytest.mark.asyncio
    async def test_store_reading(self, spore_service, mock_spore_client, mock_sqlite_connection):
        """Test storing a reading."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT COUNT(*) FROM spore_readings WHERE device_id = ? AND timestamp = ?",
            (1, "2023-07-18T12:34:56"),
            fetchone=(0,)
        )
        mock_sqlite_connection.add_query_result(
            "INSERT INTO spore_readings (device_id, temperature, humidity, pressure, timestamp) VALUES (?, ?, ?, ?, ?)",
            (1, 23.5, 45.2, 1013.2, "2023-07-18T12:34:56"),
            lastrowid=1
        )
        
        # Create reading
        reading = {
            "temperature": 23.5,
            "humidity": 45.2,
            "pressure": 1013.2,
            "timestamp": "2023-07-18T12:34:56",
            "device_id": 1
        }
        
        # Store reading
        result = await spore_service.store_reading(reading)
        
        # Verify result
        assert result is True
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT COUNT(*) FROM spore_readings WHERE device_id = ? AND timestamp = ?",
            (1, "2023-07-18T12:34:56")
        )
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "INSERT INTO spore_readings (device_id, temperature, humidity, pressure, timestamp) VALUES (?, ?, ?, ?, ?)",
            (1, 23.5, 45.2, 1013.2, "2023-07-18T12:34:56")
        )
    
    @pytest.mark.asyncio
    async def test_store_reading_duplicate(self, spore_service, mock_spore_client, mock_sqlite_connection):
        """Test storing a duplicate reading."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT COUNT(*) FROM spore_readings WHERE device_id = ? AND timestamp = ?",
            (1, "2023-07-18T12:34:56"),
            fetchone=(1,)
        )
        
        # Create reading
        reading = {
            "temperature": 23.5,
            "humidity": 45.2,
            "pressure": 1013.2,
            "timestamp": "2023-07-18T12:34:56",
            "device_id": 1
        }
        
        # Store reading
        result = await spore_service.store_reading(reading)
        
        # Verify result
        assert result is False
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once_with(
            "SELECT COUNT(*) FROM spore_readings WHERE device_id = ? AND timestamp = ?",
            (1, "2023-07-18T12:34:56")
        )
    
    @pytest.mark.asyncio
    async def test_get_readings_for_device(self, spore_service, mock_sqlite_connection):
        """Test getting readings for a device."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT temperature, humidity, pressure, timestamp FROM spore_readings WHERE device_id = ? ORDER BY timestamp DESC LIMIT ?",
            (1, 10),
            fetchall=[
                (23.5, 45.2, 1013.2, "2023-07-18T12:34:56"),
                (23.6, 45.3, 1013.3, "2023-07-18T12:35:56")
            ]
        )
        
        # Get readings
        result = await spore_service.get_readings_for_device(1, limit=10)
        
        # Verify result
        assert len(result) == 2
        assert result[0]["temperature"] == 23.5
        assert result[0]["humidity"] == 45.2
        assert result[0]["pressure"] == 1013.2
        assert result[0]["timestamp"] == "2023-07-18T12:34:56"
        
        assert result[1]["temperature"] == 23.6
        assert result[1]["humidity"] == 45.3
        assert result[1]["pressure"] == 1013.3
        assert result[1]["timestamp"] == "2023-07-18T12:35:56"
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once_with(
            "SELECT temperature, humidity, pressure, timestamp FROM spore_readings WHERE device_id = ? ORDER BY timestamp DESC LIMIT ?",
            (1, 10)
        )
    
    @pytest.mark.asyncio
    async def test_get_readings_for_device_with_timerange(self, spore_service, mock_sqlite_connection):
        """Test getting readings for a device with a time range."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT temperature, humidity, pressure, timestamp FROM spore_readings WHERE device_id = ? AND timestamp BETWEEN ? AND ? ORDER BY timestamp DESC",
            (1, "2023-07-18T00:00:00", "2023-07-18T23:59:59"),
            fetchall=[
                (23.5, 45.2, 1013.2, "2023-07-18T12:34:56"),
                (23.6, 45.3, 1013.3, "2023-07-18T12:35:56")
            ]
        )
        
        # Get readings
        result = await spore_service.get_readings_for_device(
            1,
            start_time="2023-07-18T00:00:00",
            end_time="2023-07-18T23:59:59"
        )
        
        # Verify result
        assert len(result) == 2
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once_with(
            "SELECT temperature, humidity, pressure, timestamp FROM spore_readings WHERE device_id = ? AND timestamp BETWEEN ? AND ? ORDER BY timestamp DESC",
            (1, "2023-07-18T00:00:00", "2023-07-18T23:59:59")
        )
    
    @pytest.mark.asyncio
    async def test_get_device_info(self, spore_service, mock_spore_client):
        """Test getting device info."""
        # Configure mock client
        mock_spore_client.get_info.return_value = {
            "device_name": "Test Spore",
            "mac_address": "00:11:22:33:44:55",
            "ip_address": "192.168.1.100",
            "firmware_version": "1.0.0",
            "uptime": 3600
        }
        
        # Make request
        result = await spore_service.get_device_info(mock_spore_client)
        
        # Verify result
        assert result["device_name"] == "Test Spore"
        assert result["mac_address"] == "00:11:22:33:44:55"
        assert result["ip_address"] == "192.168.1.100"
        assert result["firmware_version"] == "1.0.0"
        assert result["uptime"] == 3600
    
    @pytest.mark.asyncio
    async def test_update_device_status(self, spore_service, mock_sqlite_connection):
        """Test updating device status."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "UPDATE device_spore SET is_online = ?, last_seen = ? WHERE id = ?",
            (1, "2023-07-18T12:34:56", 1)
        )
        
        # Update status
        result = await spore_service.update_device_status(1, True, "2023-07-18T12:34:56")
        
        # Verify result
        assert result is True
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once_with(
            "UPDATE device_spore SET is_online = ?, last_seen = ? WHERE id = ?",
            (1, "2023-07-18T12:34:56", 1)
        )
    
    @pytest.mark.asyncio
    async def test_set_ambient_pressure(self, spore_service, mock_spore_client):
        """Test setting ambient pressure."""
        # Configure mock client
        mock_spore_client.set_ambient_pressure.return_value = True
        
        # Make request
        result = await spore_service.set_ambient_pressure(mock_spore_client, 1013.2)
        
        # Verify result
        assert result is True
        
        # Verify client calls
        mock_spore_client.set_ambient_pressure.assert_called_once_with(1013.2)
    
    @pytest.mark.asyncio
    async def test_poll_device(self, spore_service, mock_spore_client):
        """Test polling a device."""
        # Configure mock client
        mock_spore_client.get_latest_reading.return_value = {
            "temperature": 23.5,
            "humidity": 45.2,
            "pressure": 1013.2,
            "timestamp": "2023-07-18T12:34:56"
        }
        
        # Configure mock service methods
        spore_service.store_reading = AsyncMock(return_value=True)
        spore_service.update_device_status = AsyncMock(return_value=True)
        
        # Poll device
        result = await spore_service.poll_device(mock_spore_client)
        
        # Verify result
        assert result is True
        
        # Verify client calls
        mock_spore_client.get_latest_reading.assert_called_once()
        
        # Verify service calls
        spore_service.store_reading.assert_called_once()
        spore_service.update_device_status.assert_called_once_with(1, True, "2023-07-18T12:34:56")
    
    @pytest.mark.asyncio
    async def test_poll_device_error(self, spore_service, mock_spore_client):
        """Test polling a device with error."""
        # Configure mock client
        mock_spore_client.get_latest_reading.side_effect = ApiError(
            status_code=500,
            error_type=ApiErrorType.SERVER_ERROR,
            message="Internal Server Error"
        )
        
        # Configure mock service methods
        spore_service.update_device_status = AsyncMock(return_value=True)
        
        # Poll device
        result = await spore_service.poll_device(mock_spore_client)
        
        # Verify result
        assert result is False
        
        # Verify client calls
        mock_spore_client.get_latest_reading.assert_called_once()
        
        # Verify service calls
        spore_service.update_device_status.assert_called_once_with(1, False, None)
