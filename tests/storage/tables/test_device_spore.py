"""
Tests for the device_spore table module.

This module contains tests for the device_spore table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.device_spore import (
    create_device_spore, get_device_spore, get_device_spore_by_mac, get_all_device_spore,
    update_device_spore, update_device_status, deactivate_device_spore, 
    reactivate_device_spore, delete_device_spore
)
from storage.tables.device_hyphae import create_device_hyphae, delete_device_hyphae
from storage.tables.farms import create_farm, delete_farm
from storage.tables.grow_rooms import create_grow_room, delete_grow_room
from storage.db_utils import get_connection, execute_query, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test spore devices that might exist from previous test runs
        cursor.execute("DELETE FROM device_spore WHERE device_name LIKE 'Test Spore%'")
        # Delete any test hyphae devices that might exist from previous test runs
        cursor.execute("DELETE FROM device_hyphae WHERE device_name LIKE 'Test Hyphae%'")
        # Delete any test grow rooms that might exist from previous test runs
        cursor.execute("DELETE FROM grow_rooms WHERE room_name LIKE 'Test Room%'")
        # Delete any test farms that might exist from previous test runs
        cursor.execute("DELETE FROM farms WHERE farm_name LIKE 'Test Farm%'")
        conn.commit()
    finally:
        conn.close()

def test_device_spore_crud():
    """Test CRUD operations for the device_spore table."""
    print("\nTesting device_spore table CRUD operations...")
    
    try:
        # Clean up any existing test data
        clean_test_data()
        
        # Create a test farm and grow room first since device_spore has a foreign key to grow_rooms
        farm_id = create_farm("Test Farm for Spores", "Test Location", "Test Description")
        room_id = create_grow_room(farm_id, "Test Room for Spores", "Test Room Description")
        
        # Create a test hyphae device for association with spore devices
        hyphae_id = create_device_hyphae(
            room_id, "Test Hyphae Device", "192.168.1.100", "AA:BB:CC:00:11:22",
            mode_enabled=1, mode_operation=1, firmware_version="1.0.0", is_online=1
        )
        
        # Now run the tests
        
        # 1. Test create_device_spore
        print("Testing create_device_spore...")
        device1_id = create_device_spore(
            room_id, "Test Spore 1", "192.168.1.201", "DD:EE:FF:11:22:33",
            hyphae_id=hyphae_id, hyphae_present=1, firmware_version="1.0.0", is_online=1
        )
        device2_id = create_device_spore(
            room_id, "Test Spore 2", "192.168.1.202", "DD:EE:FF:11:22:44",
            firmware_version="1.0.1", is_online=0
        )
        device3_id = create_device_spore(
            room_id, "Test Spore 3", "192.168.1.203", "DD:EE:FF:11:22:55"
        )  # Minimal fields
        
        # IDs might not be 1, 2, 3 in the real database, so just check they're valid
        assert device1_id > 0, f"Expected device1_id to be positive, got {device1_id}"
        assert device2_id > 0, f"Expected device2_id to be positive, got {device2_id}"
        assert device3_id > 0, f"Expected device3_id to be positive, got {device3_id}"
        
        # 2. Test get_device_spore
        print("Testing get_device_spore...")
        device1 = get_device_spore(device1_id)
        assert device1 is not None, "Failed to retrieve device1"
        assert device1['device_name'] == "Test Spore 1", f"Expected device_name 'Test Spore 1', got '{device1['device_name']}'"
        assert device1['ip_address'] == "192.168.1.201", f"Expected ip_address '192.168.1.201', got '{device1['ip_address']}'"
        assert device1['mac_address'] == "DD:EE:FF:11:22:33", f"Expected mac_address 'DD:EE:FF:11:22:33', got '{device1['mac_address']}'"
        assert device1['hyphae_id'] == hyphae_id, f"Expected hyphae_id {hyphae_id}, got {device1['hyphae_id']}"
        assert device1['hyphae_present'] == 1, f"Expected hyphae_present 1, got {device1['hyphae_present']}"
        assert device1['firmware_version'] == "1.0.0", f"Expected firmware_version '1.0.0', got '{device1['firmware_version']}'"
        assert device1['is_online'] == 1, f"Expected is_online 1, got {device1['is_online']}"
        assert device1['active'] == 1, f"Expected active 1, got {device1['active']}"
        assert device1['room_id'] == room_id, f"Expected room_id {room_id}, got {device1['room_id']}"
        
        device3 = get_device_spore(device3_id)
        assert device3 is not None, "Failed to retrieve device3"
        assert device3['device_name'] == "Test Spore 3", f"Expected device_name 'Test Spore 3', got '{device3['device_name']}'"
        assert device3['hyphae_present'] == 0, f"Expected hyphae_present 0, got {device3['hyphae_present']}"
        assert device3['hyphae_id'] is None, f"Expected hyphae_id None, got {device3['hyphae_id']}"
        assert device3['is_online'] == 0, f"Expected is_online 0, got {device3['is_online']}"
        
        # 3. Test get_device_spore_by_mac
        print("Testing get_device_spore_by_mac...")
        device_by_mac = get_device_spore_by_mac("DD:EE:FF:11:22:44")
        assert device_by_mac is not None, "Failed to retrieve device by MAC address"
        assert device_by_mac['device_id'] == device2_id, f"Expected device_id {device2_id}, got {device_by_mac['device_id']}"
        
        # 4. Test get_all_device_spore
        print("Testing get_all_device_spore...")
        all_devices = get_all_device_spore()
        # Count only our test devices instead of assuming total count
        test_devices_count = sum(1 for device in all_devices if device['device_name'].startswith('Test Spore'))
        assert test_devices_count == 3, f"Expected 3 test devices, got {test_devices_count}"
        
        # Test filtering by room_id
        room_devices = get_all_device_spore(room_id=room_id)
        assert len(room_devices) == 3, f"Expected 3 devices for room_id {room_id}, got {len(room_devices)}"
        
        # Test filtering by hyphae_id
        hyphae_devices = get_all_device_spore(hyphae_id=hyphae_id)
        assert len(hyphae_devices) == 1, f"Expected 1 device for hyphae_id {hyphae_id}, got {len(hyphae_devices)}"
        
        # 5. Test update_device_spore
        print("Testing update_device_spore...")
        rows_updated = update_device_spore(
            device2_id, 
            device_name="Updated Spore 2", 
            ip_address="192.168.1.222",
            firmware_version="1.1.0",
            hyphae_id=hyphae_id,
            hyphae_present=1
        )
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_device = get_device_spore(device2_id)
        assert updated_device['device_name'] == "Updated Spore 2", f"Expected device_name 'Updated Spore 2', got '{updated_device['device_name']}'"
        assert updated_device['ip_address'] == "192.168.1.222", f"Expected ip_address '192.168.1.222', got '{updated_device['ip_address']}'"
        assert updated_device['firmware_version'] == "1.1.0", f"Expected firmware_version '1.1.0', got '{updated_device['firmware_version']}'"
        assert updated_device['hyphae_id'] == hyphae_id, f"Expected hyphae_id {hyphae_id}, got {updated_device['hyphae_id']}"
        assert updated_device['hyphae_present'] == 1, f"Expected hyphae_present 1, got {updated_device['hyphae_present']}"
        
        # Test removing hyphae association
        rows_updated = update_device_spore(device2_id, hyphae_present=0)
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_device = get_device_spore(device2_id)
        assert updated_device['hyphae_present'] == 0, f"Expected hyphae_present 0, got {updated_device['hyphae_present']}"
        assert updated_device['hyphae_id'] is None, f"Expected hyphae_id None, got {updated_device['hyphae_id']}"
        
        # 6. Test update_device_status
        print("Testing update_device_status...")
        rows_status_updated = update_device_status(device3_id, is_online=1)
        assert rows_status_updated == 1, f"Expected 1 row updated, got {rows_status_updated}"
        
        status_updated_device = get_device_spore(device3_id)
        assert status_updated_device['is_online'] == 1, f"Expected is_online 1, got {status_updated_device['is_online']}"
        assert status_updated_device['last_update'] is not None, "Expected last_update to be set"
        
        # 7. Test deactivate_device_spore
        print("Testing deactivate_device_spore...")
        rows_deactivated = deactivate_device_spore(device3_id, "Test deactivation")
        assert rows_deactivated == 1, f"Expected 1 row deactivated, got {rows_deactivated}"
        
        deactivated_device = get_device_spore(device3_id)
        assert deactivated_device['active'] == 0, f"Expected active 0, got {deactivated_device['active']}"
        assert deactivated_device['deactivation_reason'] == "Test deactivation", f"Expected deactivation_reason 'Test deactivation', got '{deactivated_device['deactivation_reason']}'"
        
        # 8. Test get_all_device_spore with active_only
        print("Testing get_all_device_spore with active_only...")
        active_devices = get_all_device_spore(room_id=room_id, active_only=True)
        assert len(active_devices) == 2, f"Expected 2 active devices, got {len(active_devices)}"
        
        all_devices_including_inactive = get_all_device_spore(room_id=room_id, active_only=False)
        assert len(all_devices_including_inactive) == 3, f"Expected 3 total devices, got {len(all_devices_including_inactive)}"
        
        # 9. Test reactivate_device_spore
        print("Testing reactivate_device_spore...")
        rows_reactivated = reactivate_device_spore(device3_id)
        assert rows_reactivated == 1, f"Expected 1 row reactivated, got {rows_reactivated}"
        
        reactivated_device = get_device_spore(device3_id)
        assert reactivated_device['active'] == 1, f"Expected active 1, got {reactivated_device['active']}"
        assert reactivated_device['deactivation_reason'] is None, f"Expected deactivation_reason None, got '{reactivated_device['deactivation_reason']}'"
        
        # 10. Test delete_device_spore
        print("Testing delete_device_spore...")
        rows_deleted = delete_device_spore(device3_id)
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_device = get_device_spore(device3_id)
        assert deleted_device is None, f"Expected None for deleted device, got {deleted_device}"
        
        remaining_devices = get_all_device_spore(room_id=room_id, active_only=False)
        assert len(remaining_devices) == 2, f"Expected 2 remaining devices, got {len(remaining_devices)}"
        
        # Clean up the test hyphae device, room, and farm
        delete_device_hyphae(hyphae_id)
        delete_grow_room(room_id)
        delete_farm(farm_id)
        
        print("All device_spore table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in device_spore table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_device_spore_crud()
