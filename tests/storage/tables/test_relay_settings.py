"""
Tests for the relay_settings table module.

This module contains tests for the relay_settings table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.relay_settings import (
    create_relay_setting, get_relay_setting, get_device_relay_settings,
    get_group_relay_settings, update_relay_setting, delete_relay_setting,
    delete_device_relay_settings, delete_group_relay_settings
)
from storage.tables.device_hyphae import create_device_hyphae
from storage.db_utils import get_connection, execute_query, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test relay settings that might exist from previous test runs
        cursor.execute("DELETE FROM relay_settings WHERE device_id IN (SELECT device_id FROM device_hyphae WHERE device_name LIKE 'Test Relay%')")
        cursor.execute("DELETE FROM device_hyphae WHERE device_name LIKE 'Test Relay%'")
        conn.commit()
    finally:
        conn.close()

def test_relay_settings_crud():
    """Test CRUD operations for the relay_settings table."""
    print("\nTesting relay_settings table CRUD operations...")
    
    try:
        # Clean up any existing test data
        clean_test_data()
        
        # Create a test device first
        print("Creating test device...")
        device_id = create_device_hyphae(
            device_name="Test Relay Device",
            room_id=1,  # Assuming room_id 1 exists
            ip_address="192.168.1.201",
            mac_address="11:22:33:44:55:66"
        )
        
        # Now run the tests
        
        # 1. Test create_relay_setting
        print("Testing create_relay_setting...")
        relay1_key = create_relay_setting(device_id, 1, 1, "Fan")
        relay2_key = create_relay_setting(device_id, 2, 1, "Humidifier")
        relay3_key = create_relay_setting(device_id, 3, 2, "Light")
        relay4_key = create_relay_setting(device_id, 4, 2)  # No name
        
        assert relay1_key[0] == device_id, f"Expected device_id {device_id}, got {relay1_key[0]}"
        assert relay1_key[1] == 1, f"Expected relay_number 1, got {relay1_key[1]}"
        
        # 2. Test get_relay_setting
        print("Testing get_relay_setting...")
        relay1 = get_relay_setting(device_id, 1)
        assert relay1 is not None, "Failed to retrieve relay1"
        assert relay1['relay_name'] == "Fan", f"Expected relay_name 'Fan', got '{relay1['relay_name']}'"
        assert relay1['group_num'] == 1, f"Expected group_num 1, got {relay1['group_num']}"
        
        relay4 = get_relay_setting(device_id, 4)
        assert relay4 is not None, "Failed to retrieve relay4"
        assert relay4['relay_name'] is None, f"Expected relay_name None, got '{relay4['relay_name']}'"
        assert relay4['group_num'] == 2, f"Expected group_num 2, got {relay4['group_num']}"
        
        # 3. Test get_device_relay_settings
        print("Testing get_device_relay_settings...")
        all_relays = get_device_relay_settings(device_id)
        assert len(all_relays) == 4, f"Expected 4 relay settings, got {len(all_relays)}"
        
        # 4. Test get_group_relay_settings
        print("Testing get_group_relay_settings...")
        group1_relays = get_group_relay_settings(device_id, 1)
        assert len(group1_relays) == 2, f"Expected 2 relay settings in group 1, got {len(group1_relays)}"
        
        group2_relays = get_group_relay_settings(device_id, 2)
        assert len(group2_relays) == 2, f"Expected 2 relay settings in group 2, got {len(group2_relays)}"
        
        # 5. Test update_relay_setting
        print("Testing update_relay_setting...")
        rows_updated = update_relay_setting(device_id, 4, relay_name="Heater")
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_relay = get_relay_setting(device_id, 4)
        assert updated_relay['relay_name'] == "Heater", f"Expected relay_name 'Heater', got '{updated_relay['relay_name']}'"
        assert updated_relay['group_num'] == 2, f"Expected group_num unchanged at 2, got {updated_relay['group_num']}"
        
        # Change group number
        rows_updated = update_relay_setting(device_id, 3, group_num=1)
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_relay = get_relay_setting(device_id, 3)
        assert updated_relay['group_num'] == 1, f"Expected group_num 1, got {updated_relay['group_num']}"
        
        # 6. Test delete_relay_setting
        print("Testing delete_relay_setting...")
        rows_deleted = delete_relay_setting(device_id, 4)
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_relay = get_relay_setting(device_id, 4)
        assert deleted_relay is None, f"Expected None for deleted relay, got {deleted_relay}"
        
        remaining_relays = get_device_relay_settings(device_id)
        assert len(remaining_relays) == 3, f"Expected 3 remaining relay settings, got {len(remaining_relays)}"
        
        # 7. Test delete_group_relay_settings
        print("Testing delete_group_relay_settings...")
        # After moving relay 3 to group 1, group 1 should have 3 relays
        group1_count = len(get_group_relay_settings(device_id, 1))
        assert group1_count == 3, f"Expected 3 relay settings in group 1, got {group1_count}"
        
        rows_deleted_group = delete_group_relay_settings(device_id, 1)
        assert rows_deleted_group == 3, f"Expected 3 rows deleted for group 1, got {rows_deleted_group}"
        
        remaining_relays = get_device_relay_settings(device_id)
        assert len(remaining_relays) == 0, f"Expected 0 remaining relay settings, got {len(remaining_relays)}"
        
        # 8. Test delete_device_relay_settings (recreate some relays first)
        print("Testing delete_device_relay_settings...")
        create_relay_setting(device_id, 1, 1, "Fan")
        create_relay_setting(device_id, 2, 1, "Humidifier")
        
        device_relays = get_device_relay_settings(device_id)
        assert len(device_relays) == 2, f"Expected 2 relay settings, got {len(device_relays)}"
        
        rows_deleted_device = delete_device_relay_settings(device_id)
        assert rows_deleted_device == 2, f"Expected 2 rows deleted for device, got {rows_deleted_device}"
        
        final_relays = get_device_relay_settings(device_id)
        assert len(final_relays) == 0, f"Expected 0 final relay settings, got {len(final_relays)}"
        
        print("All relay_settings table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in relay_settings table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up test data
        clean_test_data()

if __name__ == "__main__":
    test_relay_settings_crud()
