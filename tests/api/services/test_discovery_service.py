"""
Tests for the Discovery service.

This module contains tests for the DiscoveryService class.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp
from aiohttp import ClientResponseError, ClientConnectorError

from api.services.discovery_service import DiscoveryService
from api.clients.base_client import ApiError, ApiErrorType

class TestDiscoveryService:
    """Tests for the DiscoveryService class."""
    
    @pytest.fixture
    def discovery_service(self, mock_sqlite_connection):
        """Create a DiscoveryService instance for testing."""
        return DiscoveryService(db_connection=mock_sqlite_connection)
    
    @pytest.mark.asyncio
    async def test_scan_ip_range(self, discovery_service):
        """Test scanning an IP range."""
        # Mock the scan_ip method
        discovery_service.scan_ip = AsyncMock()
        discovery_service.scan_ip.side_effect = [
            {"ip": "192.168.1.100", "device_type": "spore", "info": {"device_name": "Test Spore"}},
            {"ip": "192.168.1.101", "device_type": "hyphae", "info": {"device_name": "Test Hyphae"}},
            None,  # Not a device
            None,  # Not a device
        ]
        
        # Scan IP range
        result = await discovery_service.scan_ip_range("192.168.1", 100, 103)
        
        # Verify result
        assert len(result) == 2
        assert result[0]["ip"] == "192.168.1.100"
        assert result[0]["device_type"] == "spore"
        assert result[0]["info"]["device_name"] == "Test Spore"
        assert result[1]["ip"] == "192.168.1.101"
        assert result[1]["device_type"] == "hyphae"
        assert result[1]["info"]["device_name"] == "Test Hyphae"
        
        # Verify scan_ip calls
        assert discovery_service.scan_ip.call_count == 4
        discovery_service.scan_ip.assert_any_call("192.168.1.100")
        discovery_service.scan_ip.assert_any_call("192.168.1.101")
        discovery_service.scan_ip.assert_any_call("192.168.1.102")
        discovery_service.scan_ip.assert_any_call("192.168.1.103")
    
    @pytest.mark.asyncio
    async def test_scan_ip(self, discovery_service):
        """Test scanning a single IP."""
        # Mock the _check_device_type method
        discovery_service._check_device_type = AsyncMock(return_value=("spore", {"device_name": "Test Spore"}))
        
        # Scan IP
        result = await discovery_service.scan_ip("192.168.1.100")
        
        # Verify result
        assert result["ip"] == "192.168.1.100"
        assert result["device_type"] == "spore"
        assert result["info"]["device_name"] == "Test Spore"
        
        # Verify _check_device_type calls
        discovery_service._check_device_type.assert_called_once_with("192.168.1.100")
    
    @pytest.mark.asyncio
    async def test_scan_ip_error(self, discovery_service):
        """Test scanning a single IP with error."""
        # Mock the _check_device_type method
        discovery_service._check_device_type = AsyncMock(side_effect=Exception("Connection error"))
        
        # Scan IP
        result = await discovery_service.scan_ip("192.168.1.100")
        
        # Verify result
        assert result is None
        
        # Verify _check_device_type calls
        discovery_service._check_device_type.assert_called_once_with("192.168.1.100")
    
    @pytest.mark.asyncio
    async def test_check_device_type_spore(self, discovery_service, mock_aiohttp_session):
        """Test checking device type for a Spore device."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://192.168.1.100/api/info",
            status=200,
            text="""
            Device Name: Test Spore
            MAC Address: 00:11:22:33:44:55
            IP Address: 192.168.1.100
            Firmware Version: 1.0.0
            Uptime: 3600
            """
        )
        
        # Check device type
        device_type, info = await discovery_service._check_device_type("192.168.1.100")
        
        # Verify result
        assert device_type == "spore"
        assert info["device_name"] == "Test Spore"
        assert info["mac_address"] == "00:11:22:33:44:55"
        assert info["ip_address"] == "192.168.1.100"
        assert info["firmware_version"] == "1.0.0"
        assert info["uptime"] == 3600
    
    @pytest.mark.asyncio
    async def test_check_device_type_hyphae(self, discovery_service, mock_aiohttp_session):
        """Test checking device type for a Hyphae device."""
        # Configure mock response for Spore endpoint (should fail)
        mock_aiohttp_session.add_response(
            "http://192.168.1.101/api/info",
            status=404,
            text="Not Found"
        )
        
        # Configure mock response for Hyphae endpoint
        mock_aiohttp_session.add_response(
            "http://192.168.1.101/api/info",
            status=200,
            json={
                "device_name": "Test Hyphae",
                "mac_address": "00:11:22:33:44:55",
                "ip_address": "192.168.1.101",
                "firmware_version": "1.0.0",
                "uptime": 3600,
                "relay_count": 6
            }
        )
        
        # Check device type
        device_type, info = await discovery_service._check_device_type("192.168.1.101")
        
        # Verify result
        assert device_type == "hyphae"
        assert info["device_name"] == "Test Hyphae"
        assert info["mac_address"] == "00:11:22:33:44:55"
        assert info["ip_address"] == "192.168.1.101"
        assert info["firmware_version"] == "1.0.0"
        assert info["uptime"] == 3600
        assert info["relay_count"] == 6
    
    @pytest.mark.asyncio
    async def test_check_device_type_unknown(self, discovery_service, mock_aiohttp_session):
        """Test checking device type for an unknown device."""
        # Configure mock response for both endpoints (should fail)
        mock_aiohttp_session.add_response(
            "http://192.168.1.102/api/info",
            status=404,
            text="Not Found"
        )
        
        # Check device type
        with pytest.raises(Exception) as excinfo:
            await discovery_service._check_device_type("192.168.1.102")
        
        # Verify error
        assert "Unknown device type" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_register_device_spore(self, discovery_service, mock_sqlite_connection):
        """Test registering a Spore device."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT id FROM device_spore WHERE mac_address = ?",
            ("00:11:22:33:44:55",),
            fetchone=None
        )
        mock_sqlite_connection.add_query_result(
            "SELECT id FROM device_spore WHERE ip_address = ?",
            ("192.168.1.100",),
            fetchone=None
        )
        mock_sqlite_connection.add_query_result(
            "SELECT id FROM rooms WHERE name = ?",
            ("Default Room",),
            fetchone=(1,)
        )
        mock_sqlite_connection.add_query_result(
            "INSERT INTO device_spore (room_id, device_name, ip_address, mac_address, firmware_version, is_online) VALUES (?, ?, ?, ?, ?, ?)",
            (1, "Test Spore", "192.168.1.100", "00:11:22:33:44:55", "1.0.0", 1),
            lastrowid=1
        )
        
        # Create device info
        device_info = {
            "ip": "192.168.1.100",
            "device_type": "spore",
            "info": {
                "device_name": "Test Spore",
                "mac_address": "00:11:22:33:44:55",
                "ip_address": "192.168.1.100",
                "firmware_version": "1.0.0",
                "uptime": 3600
            }
        }
        
        # Register device
        result = await discovery_service.register_device(device_info)
        
        # Verify result
        assert result["device_id"] == 1
        assert result["device_type"] == "spore"
        assert result["device_name"] == "Test Spore"
        assert result["is_new"] is True
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT id FROM device_spore WHERE mac_address = ?",
            ("00:11:22:33:44:55",)
        )
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT id FROM device_spore WHERE ip_address = ?",
            ("192.168.1.100",)
        )
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT id FROM rooms WHERE name = ?",
            ("Default Room",)
        )
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "INSERT INTO device_spore (room_id, device_name, ip_address, mac_address, firmware_version, is_online) VALUES (?, ?, ?, ?, ?, ?)",
            (1, "Test Spore", "192.168.1.100", "00:11:22:33:44:55", "1.0.0", 1)
        )
    
    @pytest.mark.asyncio
    async def test_register_device_hyphae(self, discovery_service, mock_sqlite_connection):
        """Test registering a Hyphae device."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT id FROM device_hyphae WHERE mac_address = ?",
            ("00:11:22:33:44:55",),
            fetchone=None
        )
        mock_sqlite_connection.add_query_result(
            "SELECT id FROM device_hyphae WHERE ip_address = ?",
            ("192.168.1.101",),
            fetchone=None
        )
        mock_sqlite_connection.add_query_result(
            "SELECT id FROM rooms WHERE name = ?",
            ("Default Room",),
            fetchone=(1,)
        )
        mock_sqlite_connection.add_query_result(
            "INSERT INTO device_hyphae (room_id, device_name, ip_address, mac_address, firmware_version, is_online, relay_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "Test Hyphae", "192.168.1.101", "00:11:22:33:44:55", "1.0.0", 1, 6),
            lastrowid=1
        )
        
        # Create device info
        device_info = {
            "ip": "192.168.1.101",
            "device_type": "hyphae",
            "info": {
                "device_name": "Test Hyphae",
                "mac_address": "00:11:22:33:44:55",
                "ip_address": "192.168.1.101",
                "firmware_version": "1.0.0",
                "uptime": 3600,
                "relay_count": 6
            }
        }
        
        # Register device
        result = await discovery_service.register_device(device_info)
        
        # Verify result
        assert result["device_id"] == 1
        assert result["device_type"] == "hyphae"
        assert result["device_name"] == "Test Hyphae"
        assert result["is_new"] is True
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT id FROM device_hyphae WHERE mac_address = ?",
            ("00:11:22:33:44:55",)
        )
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT id FROM device_hyphae WHERE ip_address = ?",
            ("192.168.1.101",)
        )
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT id FROM rooms WHERE name = ?",
            ("Default Room",)
        )
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "INSERT INTO device_hyphae (room_id, device_name, ip_address, mac_address, firmware_version, is_online, relay_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "Test Hyphae", "192.168.1.101", "00:11:22:33:44:55", "1.0.0", 1, 6)
        )
    
    @pytest.mark.asyncio
    async def test_register_device_existing(self, discovery_service, mock_sqlite_connection):
        """Test registering an existing device."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "SELECT id FROM device_spore WHERE mac_address = ?",
            ("00:11:22:33:44:55",),
            fetchone=(1,)
        )
        mock_sqlite_connection.add_query_result(
            "UPDATE device_spore SET ip_address = ?, firmware_version = ?, is_online = ? WHERE id = ?",
            ("192.168.1.100", "1.0.0", 1, 1)
        )
        mock_sqlite_connection.add_query_result(
            "SELECT device_name FROM device_spore WHERE id = ?",
            (1,),
            fetchone=("Test Spore",)
        )
        
        # Create device info
        device_info = {
            "ip": "192.168.1.100",
            "device_type": "spore",
            "info": {
                "device_name": "Test Spore",
                "mac_address": "00:11:22:33:44:55",
                "ip_address": "192.168.1.100",
                "firmware_version": "1.0.0",
                "uptime": 3600
            }
        }
        
        # Register device
        result = await discovery_service.register_device(device_info)
        
        # Verify result
        assert result["device_id"] == 1
        assert result["device_type"] == "spore"
        assert result["device_name"] == "Test Spore"
        assert result["is_new"] is False
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT id FROM device_spore WHERE mac_address = ?",
            ("00:11:22:33:44:55",)
        )
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "UPDATE device_spore SET ip_address = ?, firmware_version = ?, is_online = ? WHERE id = ?",
            ("192.168.1.100", "1.0.0", 1, 1)
        )
        mock_sqlite_connection.cursor().execute.assert_any_call(
            "SELECT device_name FROM device_spore WHERE id = ?",
            (1,)
        )
    
    @pytest.mark.asyncio
    async def test_link_devices(self, discovery_service, mock_sqlite_connection):
        """Test linking a Spore device to a Hyphae device."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "UPDATE device_spore SET hyphae_id = ?, hyphae_present = ? WHERE id = ?",
            (2, 1, 1)
        )
        
        # Link devices
        result = await discovery_service.link_devices(1, 2)
        
        # Verify result
        assert result is True
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once_with(
            "UPDATE device_spore SET hyphae_id = ?, hyphae_present = ? WHERE id = ?",
            (2, 1, 1)
        )
    
    @pytest.mark.asyncio
    async def test_unlink_devices(self, discovery_service, mock_sqlite_connection):
        """Test unlinking a Spore device from a Hyphae device."""
        # Configure mock database
        mock_sqlite_connection.add_query_result(
            "UPDATE device_spore SET hyphae_id = NULL, hyphae_present = ? WHERE id = ?",
            (0, 1)
        )
        
        # Unlink devices
        result = await discovery_service.unlink_devices(1)
        
        # Verify result
        assert result is True
        
        # Verify database calls
        mock_sqlite_connection.cursor().execute.assert_called_once_with(
            "UPDATE device_spore SET hyphae_id = NULL, hyphae_present = ? WHERE id = ?",
            (0, 1)
        )
    
    @pytest.mark.asyncio
    async def test_discover_devices(self, discovery_service):
        """Test discovering devices."""
        # Mock the scan_ip_range method
        discovery_service.scan_ip_range = AsyncMock(return_value=[
            {"ip": "192.168.1.100", "device_type": "spore", "info": {"device_name": "Test Spore"}},
            {"ip": "192.168.1.101", "device_type": "hyphae", "info": {"device_name": "Test Hyphae"}}
        ])
        
        # Mock the register_device method
        discovery_service.register_device = AsyncMock(side_effect=[
            {"device_id": 1, "device_type": "spore", "device_name": "Test Spore", "is_new": True},
            {"device_id": 2, "device_type": "hyphae", "device_name": "Test Hyphae", "is_new": True}
        ])
        
        # Discover devices
        result = await discovery_service.discover_devices(["192.168.1"], [100, 110])
        
        # Verify result
        assert len(result) == 2
        assert result[0]["device_id"] == 1
        assert result[0]["device_type"] == "spore"
        assert result[0]["device_name"] == "Test Spore"
        assert result[0]["is_new"] is True
        assert result[1]["device_id"] == 2
        assert result[1]["device_type"] == "hyphae"
        assert result[1]["device_name"] == "Test Hyphae"
        assert result[1]["is_new"] is True
        
        # Verify scan_ip_range calls
        discovery_service.scan_ip_range.assert_called_once_with("192.168.1", 100, 110)
        
        # Verify register_device calls
        assert discovery_service.register_device.call_count == 2
        discovery_service.register_device.assert_any_call({"ip": "192.168.1.100", "device_type": "spore", "info": {"device_name": "Test Spore"}})
        discovery_service.register_device.assert_any_call({"ip": "192.168.1.101", "device_type": "hyphae", "info": {"device_name": "Test Hyphae"}})
