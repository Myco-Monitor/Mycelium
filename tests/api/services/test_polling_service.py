"""
Tests for the Polling service.

This module contains tests for the PollingService class.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import datetime

from api.services.polling_service import PollingService
from api.services.spore_service import SporeService
from api.services.hyphae_service import HyphaeService
from api.services.weather_service import WeatherService
from api.clients.base_client import ApiError, ApiErrorType

class TestPollingService:
    """Tests for the PollingService class."""
    
    @pytest.fixture
    def mock_spore_service(self):
        """Create a mock SporeService for testing."""
        mock_service = AsyncMock(spec=SporeService)
        return mock_service
    
    @pytest.fixture
    def mock_hyphae_service(self):
        """Create a mock HyphaeService for testing."""
        mock_service = AsyncMock(spec=HyphaeService)
        return mock_service
    
    @pytest.fixture
    def mock_weather_service(self):
        """Create a mock WeatherService for testing."""
        mock_service = AsyncMock(spec=WeatherService)
        return mock_service
    
    @pytest.fixture
    def polling_service(self, mock_spore_service, mock_hyphae_service, mock_weather_service, mock_sqlite_connection):
        """Create a PollingService instance for testing."""
        return PollingService(
            db_connection=mock_sqlite_connection,
            spore_service=mock_spore_service,
            hyphae_service=mock_hyphae_service,
            weather_service=mock_weather_service
        )
    
    @pytest.mark.asyncio
    async def test_get_spore_devices(self, polling_service, mock_sqlite_connection):
        """Test getting Spore devices."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT id, device_name, ip_address, mac_address FROM device_spore WHERE is_online = ?",
            (1,),
            fetchall=[
                (1, "Spore 1", "192.168.1.100", "00:11:22:33:44:55"),
                (2, "Spore 2", "192.168.1.101", "00:11:22:33:44:66")
            ]
        )
        
        # Get Spore devices
        result = await polling_service.get_spore_devices()
        
        # Verify result
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[0]["device_name"] == "Spore 1"
        assert result[0]["ip_address"] == "192.168.1.100"
        assert result[0]["mac_address"] == "00:11:22:33:44:55"
        assert result[1]["id"] == 2
        assert result[1]["device_name"] == "Spore 2"
        assert result[1]["ip_address"] == "192.168.1.101"
        assert result[1]["mac_address"] == "00:11:22:33:44:66"
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once_with(
            "SELECT id, device_name, ip_address, mac_address FROM device_spore WHERE is_online = ?",
            (1,)
        )
    
    @pytest.mark.asyncio
    async def test_get_hyphae_devices(self, polling_service, mock_sqlite_connection):
        """Test getting Hyphae devices."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT id, device_name, ip_address, mac_address FROM device_hyphae WHERE is_online = ?",
            (1,),
            fetchall=[
                (1, "Hyphae 1", "192.168.1.200", "00:11:22:33:44:77"),
                (2, "Hyphae 2", "192.168.1.201", "00:11:22:33:44:88")
            ]
        )
        
        # Get Hyphae devices
        result = await polling_service.get_hyphae_devices()
        
        # Verify result
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[0]["device_name"] == "Hyphae 1"
        assert result[0]["ip_address"] == "192.168.1.200"
        assert result[0]["mac_address"] == "00:11:22:33:44:77"
        assert result[1]["id"] == 2
        assert result[1]["device_name"] == "Hyphae 2"
        assert result[1]["ip_address"] == "192.168.1.201"
        assert result[1]["mac_address"] == "00:11:22:33:44:88"
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once_with(
            "SELECT id, device_name, ip_address, mac_address FROM device_hyphae WHERE is_online = ?",
            (1,)
        )
    
    @pytest.mark.asyncio
    async def test_get_weather_locations(self, polling_service, mock_sqlite_connection):
        """Test getting weather locations."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT id, name, zip_code, latitude, longitude FROM weather_locations WHERE is_active = ?",
            (1,),
            fetchall=[
                (1, "Location 1", "12345", 40.7128, -74.006),
                (2, "Location 2", "67890", 34.0522, -118.2437)
            ]
        )
        
        # Get weather locations
        result = await polling_service.get_weather_locations()
        
        # Verify result
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[0]["name"] == "Location 1"
        assert result[0]["zip_code"] == "12345"
        assert result[0]["latitude"] == 40.7128
        assert result[0]["longitude"] == -74.006
        assert result[1]["id"] == 2
        assert result[1]["name"] == "Location 2"
        assert result[1]["zip_code"] == "67890"
        assert result[1]["latitude"] == 34.0522
        assert result[1]["longitude"] == -118.2437
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once_with(
            "SELECT id, name, zip_code, latitude, longitude FROM weather_locations WHERE is_active = ?",
            (1,)
        )
    
    @pytest.mark.asyncio
    async def test_poll_spore_devices(self, polling_service, mock_spore_service):
        """Test polling Spore devices."""
        # Configure mock service
        mock_spore_service.poll_device.side_effect = [
            True,  # Success
            False  # Failure
        ]
        
        # Configure mock get_spore_devices
        polling_service.get_spore_devices = AsyncMock(return_value=[
            {"id": 1, "device_name": "Spore 1", "ip_address": "192.168.1.100", "mac_address": "00:11:22:33:44:55"},
            {"id": 2, "device_name": "Spore 2", "ip_address": "192.168.1.101", "mac_address": "00:11:22:33:44:66"}
        ])
        
        # Poll Spore devices
        result = await polling_service.poll_spore_devices()
        
        # Verify result
        assert result == {"success": 1, "failure": 1}
        
        # Verify service calls
        assert mock_spore_service.poll_device.call_count == 2
        mock_spore_service.poll_device.assert_any_call(1, "192.168.1.100")
        mock_spore_service.poll_device.assert_any_call(2, "192.168.1.101")
    
    @pytest.mark.asyncio
    async def test_poll_hyphae_devices(self, polling_service, mock_hyphae_service):
        """Test polling Hyphae devices."""
        # Configure mock service
        mock_hyphae_service.poll_device.side_effect = [
            True,  # Success
            False  # Failure
        ]
        
        # Configure mock get_hyphae_devices
        polling_service.get_hyphae_devices = AsyncMock(return_value=[
            {"id": 1, "device_name": "Hyphae 1", "ip_address": "192.168.1.200", "mac_address": "00:11:22:33:44:77"},
            {"id": 2, "device_name": "Hyphae 2", "ip_address": "192.168.1.201", "mac_address": "00:11:22:33:44:88"}
        ])
        
        # Poll Hyphae devices
        result = await polling_service.poll_hyphae_devices()
        
        # Verify result
        assert result == {"success": 1, "failure": 1}
        
        # Verify service calls
        assert mock_hyphae_service.poll_device.call_count == 2
        mock_hyphae_service.poll_device.assert_any_call(1, "192.168.1.200")
        mock_hyphae_service.poll_device.assert_any_call(2, "192.168.1.201")
    
    @pytest.mark.asyncio
    async def test_poll_weather_locations(self, polling_service, mock_weather_service):
        """Test polling weather locations."""
        # Configure mock service
        mock_weather_service.poll_weather.side_effect = [
            True,  # Success
            False  # Failure
        ]
        
        # Configure mock get_weather_locations
        polling_service.get_weather_locations = AsyncMock(return_value=[
            {"id": 1, "name": "Location 1", "zip_code": "12345", "latitude": 40.7128, "longitude": -74.006},
            {"id": 2, "name": "Location 2", "zip_code": "67890", "latitude": 34.0522, "longitude": -118.2437}
        ])
        
        # Poll weather locations
        result = await polling_service.poll_weather_locations()
        
        # Verify result
        assert result == {"success": 1, "failure": 1}
        
        # Verify service calls
        assert mock_weather_service.poll_weather.call_count == 2
        # We can't verify the exact calls because the WeatherClient is created inside the method
    
    @pytest.mark.asyncio
    async def test_poll_all(self, polling_service):
        """Test polling all devices and locations."""
        # Configure mock methods
        polling_service.poll_spore_devices = AsyncMock(return_value={"success": 2, "failure": 1})
        polling_service.poll_hyphae_devices = AsyncMock(return_value={"success": 1, "failure": 1})
        polling_service.poll_weather_locations = AsyncMock(return_value={"success": 2, "failure": 0})
        
        # Poll all
        result = await polling_service.poll_all()
        
        # Verify result
        assert result["spore"] == {"success": 2, "failure": 1}
        assert result["hyphae"] == {"success": 1, "failure": 1}
        assert result["weather"] == {"success": 2, "failure": 0}
        assert result["total_success"] == 5
        assert result["total_failure"] == 2
        
        # Verify method calls
        polling_service.poll_spore_devices.assert_called_once()
        polling_service.poll_hyphae_devices.assert_called_once()
        polling_service.poll_weather_locations.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_polling(self, polling_service):
        """Test starting polling."""
        # Mock the poll_all method
        polling_service.poll_all = AsyncMock(return_value={
            "spore": {"success": 2, "failure": 1},
            "hyphae": {"success": 1, "failure": 1},
            "weather": {"success": 2, "failure": 0},
            "total_success": 5,
            "total_failure": 2
        })
        
        # Mock asyncio.sleep to avoid waiting
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # Configure the mock to raise an exception after the first call to stop the loop
            mock_sleep.side_effect = [None, Exception("Stop polling")]
            
            # Start polling
            with pytest.raises(Exception, match="Stop polling"):
                await polling_service.start_polling(interval_seconds=60)
            
            # Verify poll_all calls
            assert polling_service.poll_all.call_count == 2
            
            # Verify sleep calls
            mock_sleep.assert_called_with(60)
    
    @pytest.mark.asyncio
    async def test_update_device_status(self, polling_service, mock_sqlite_connection):
        """Test updating device status."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "UPDATE device_spore SET is_online = ? WHERE id = ?",
            (0, 1)
        )
        
        # Update device status
        result = await polling_service.update_device_status("spore", 1, False)
        
        # Verify result
        assert result is True
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once_with(
            "UPDATE device_spore SET is_online = ? WHERE id = ?",
            (0, 1)
        )
    
    @pytest.mark.asyncio
    async def test_update_device_status_invalid_type(self, polling_service):
        """Test updating device status with invalid device type."""
        # Update device status
        with pytest.raises(ValueError) as excinfo:
            await polling_service.update_device_status("invalid", 1, True)
        
        # Verify error
        assert "Invalid device type" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_get_polling_stats(self, polling_service, mock_sqlite_connection):
        """Test getting polling stats."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT COUNT(*) FROM device_spore WHERE is_online = ?",
            (1,),
            fetchone=(3,)
        )
        mock_sqlite_connection.add_query_result(
            "SELECT COUNT(*) FROM device_spore WHERE is_online = ?",
            (0,),
            fetchone=(1,)
        )
        mock_sqlite_connection.add_query_result(
            "SELECT COUNT(*) FROM device_hyphae WHERE is_online = ?",
            (1,),
            fetchone=(2,)
        )
        mock_sqlite_connection.add_query_result(
            "SELECT COUNT(*) FROM device_hyphae WHERE is_online = ?",
            (0,),
            fetchone=(1,)
        )
        mock_sqlite_connection.add_query_result(
            "SELECT COUNT(*) FROM weather_locations WHERE is_active = ?",
            (1,),
            fetchone=(2,)
        )
        
        # Get polling stats
        result = await polling_service.get_polling_stats()
        
        # Verify result
        assert result["spore"]["online"] == 3
        assert result["spore"]["offline"] == 1
        assert result["spore"]["total"] == 4
        assert result["hyphae"]["online"] == 2
        assert result["hyphae"]["offline"] == 1
        assert result["hyphae"]["total"] == 3
        assert result["weather"]["active"] == 2
        assert result["total_devices"] == 7
        assert result["online_devices"] == 5
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT COUNT(*) FROM device_spore WHERE is_online = ?",
            (1,)
        )
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT COUNT(*) FROM device_spore WHERE is_online = ?",
            (0,)
        )
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT COUNT(*) FROM device_hyphae WHERE is_online = ?",
            (1,)
        )
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT COUNT(*) FROM device_hyphae WHERE is_online = ?",
            (0,)
        )
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT COUNT(*) FROM weather_locations WHERE is_active = ?",
            (1,)
        )
