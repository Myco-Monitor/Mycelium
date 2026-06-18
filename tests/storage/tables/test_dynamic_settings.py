"""
Tests for the dynamic_settings table module.

This module contains tests for the dynamic_settings table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.dynamic_settings import (
    create_dynamic_setting, get_dynamic_setting, get_device_dynamic_settings,
    get_group_dynamic_settings, get_parameter_dynamic_settings,
    update_dynamic_setting, delete_dynamic_setting, delete_device_dynamic_settings,
    delete_group_dynamic_settings, delete_parameter_dynamic_settings
)
from storage.tables.device_hyphae import create_device_hyphae
from storage.db_utils import get_connection, execute_query, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test dynamic settings that might exist from previous test runs
        cursor.execute("DELETE FROM dynamic_settings WHERE device_id IN (SELECT device_id FROM device_hyphae WHERE device_name LIKE 'Test Dynamic%')")
        cursor.execute("DELETE FROM device_hyphae WHERE device_name LIKE 'Test Dynamic%'")
        conn.commit()
    finally:
        conn.close()

def test_dynamic_settings_crud():
    """Test CRUD operations for the dynamic_settings table."""
    print("\nTesting dynamic_settings table CRUD operations...")
    
    try:
        # Clean up any existing test data
        clean_test_data()
        
        # Create a test device first
        print("Creating test device...")
        device_id = create_device_hyphae(
            device_name="Test Dynamic Device",
            room_id=1,  # Assuming room_id 1 exists
            ip_address="192.168.1.204",
            mac_address="44:55:66:77:88:99"
        )
        
        # Now run the tests
        
        # 1. Test create_dynamic_setting
        print("Testing create_dynamic_setting...")
        setting1_key = create_dynamic_setting(device_id, 1, "temperature", 18.0, 25.0, 1)
        setting2_key = create_dynamic_setting(device_id, 1, "humidity", 60.0, 80.0, 2)
        setting3_key = create_dynamic_setting(device_id, 2, "temperature", 20.0, 28.0, 1)
        setting4_key = create_dynamic_setting(device_id, 2, "co2", 800.0, 1200.0, 3)
        
        assert setting1_key[0] == device_id, f"Expected device_id {device_id}, got {setting1_key[0]}"
        assert setting1_key[1] == 1, f"Expected group_num 1, got {setting1_key[1]}"
        assert setting1_key[2] == "temperature", f"Expected parameter 'temperature', got '{setting1_key[2]}'"
        
        # 2. Test get_dynamic_setting
        print("Testing get_dynamic_setting...")
        setting1 = get_dynamic_setting(device_id, 1, "temperature")
        assert setting1 is not None, "Failed to retrieve setting1"
        assert setting1['low_threshold'] == 18.0, f"Expected low_threshold 18.0, got {setting1['low_threshold']}"
        assert setting1['high_threshold'] == 25.0, f"Expected high_threshold 25.0, got {setting1['high_threshold']}"
        assert setting1['behavior'] == 1, f"Expected behavior 1, got {setting1['behavior']}"
        
        setting4 = get_dynamic_setting(device_id, 2, "co2")
        assert setting4 is not None, "Failed to retrieve setting4"
        assert setting4['low_threshold'] == 800.0, f"Expected low_threshold 800.0, got {setting4['low_threshold']}"
        assert setting4['high_threshold'] == 1200.0, f"Expected high_threshold 1200.0, got {setting4['high_threshold']}"
        assert setting4['behavior'] == 3, f"Expected behavior 3, got {setting4['behavior']}"
        
        # 3. Test get_device_dynamic_settings
        print("Testing get_device_dynamic_settings...")
        all_settings = get_device_dynamic_settings(device_id)
        assert len(all_settings) == 4, f"Expected 4 dynamic settings, got {len(all_settings)}"
        
        # 4. Test get_group_dynamic_settings
        print("Testing get_group_dynamic_settings...")
        group1_settings = get_group_dynamic_settings(device_id, 1)
        assert len(group1_settings) == 2, f"Expected 2 dynamic settings in group 1, got {len(group1_settings)}"
        
        group2_settings = get_group_dynamic_settings(device_id, 2)
        assert len(group2_settings) == 2, f"Expected 2 dynamic settings in group 2, got {len(group2_settings)}"
        
        # 5. Test get_parameter_dynamic_settings
        print("Testing get_parameter_dynamic_settings...")
        temp_settings = get_parameter_dynamic_settings(device_id, "temperature")
        assert len(temp_settings) == 2, f"Expected 2 temperature dynamic settings, got {len(temp_settings)}"
        
        # 6. Test update_dynamic_setting
        print("Testing update_dynamic_setting...")
        rows_updated = update_dynamic_setting(device_id, 2, "co2", low_threshold=900.0, high_threshold=1500.0)
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_setting = get_dynamic_setting(device_id, 2, "co2")
        assert updated_setting['low_threshold'] == 900.0, f"Expected low_threshold 900.0, got {updated_setting['low_threshold']}"
        assert updated_setting['high_threshold'] == 1500.0, f"Expected high_threshold 1500.0, got {updated_setting['high_threshold']}"
        assert updated_setting['behavior'] == 3, f"Expected behavior unchanged at 3, got {updated_setting['behavior']}"
        
        # Update just one field and behavior
        rows_updated = update_dynamic_setting(device_id, 1, "humidity", high_threshold=85.0, behavior=1)
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_setting = get_dynamic_setting(device_id, 1, "humidity")
        assert updated_setting['low_threshold'] == 60.0, f"Expected low_threshold unchanged at 60.0, got {updated_setting['low_threshold']}"
        assert updated_setting['high_threshold'] == 85.0, f"Expected high_threshold 85.0, got {updated_setting['high_threshold']}"
        assert updated_setting['behavior'] == 1, f"Expected behavior 1, got {updated_setting['behavior']}"
        
        # 7. Test delete_dynamic_setting
        print("Testing delete_dynamic_setting...")
        rows_deleted = delete_dynamic_setting(device_id, 2, "co2")
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_setting = get_dynamic_setting(device_id, 2, "co2")
        assert deleted_setting is None, f"Expected None for deleted setting, got {deleted_setting}"
        
        remaining_settings = get_device_dynamic_settings(device_id)
        assert len(remaining_settings) == 3, f"Expected 3 remaining dynamic settings, got {len(remaining_settings)}"
        
        # 8. Test delete_parameter_dynamic_settings
        print("Testing delete_parameter_dynamic_settings...")
        rows_deleted_param = delete_parameter_dynamic_settings(device_id, "temperature")
        assert rows_deleted_param == 2, f"Expected 2 rows deleted for temperature, got {rows_deleted_param}"
        
        remaining_settings = get_device_dynamic_settings(device_id)
        assert len(remaining_settings) == 1, f"Expected 1 remaining dynamic setting, got {len(remaining_settings)}"
        assert remaining_settings[0]['parameter'] == "humidity", f"Expected remaining parameter 'humidity', got '{remaining_settings[0]['parameter']}'"
        
        # 9. Test delete_group_dynamic_settings (recreate some settings first)
        print("Testing delete_group_dynamic_settings...")
        create_dynamic_setting(device_id, 2, "temperature", 20.0, 28.0, 1)
        create_dynamic_setting(device_id, 2, "co2", 900.0, 1500.0, 3)
        
        group2_settings = get_group_dynamic_settings(device_id, 2)
        assert len(group2_settings) == 2, f"Expected 2 dynamic settings in group 2, got {len(group2_settings)}"
        
        rows_deleted_group = delete_group_dynamic_settings(device_id, 2)
        assert rows_deleted_group == 2, f"Expected 2 rows deleted for group 2, got {rows_deleted_group}"
        
        remaining_settings = get_device_dynamic_settings(device_id)
        assert len(remaining_settings) == 1, f"Expected 1 remaining dynamic setting, got {len(remaining_settings)}"
        assert remaining_settings[0]['group_num'] == 1, f"Expected remaining group_num 1, got {remaining_settings[0]['group_num']}"
        
        # 10. Test delete_device_dynamic_settings
        print("Testing delete_device_dynamic_settings...")
        rows_deleted_device = delete_device_dynamic_settings(device_id)
        assert rows_deleted_device == 1, f"Expected 1 row deleted for device, got {rows_deleted_device}"
        
        final_settings = get_device_dynamic_settings(device_id)
        assert len(final_settings) == 0, f"Expected 0 final dynamic settings, got {len(final_settings)}"
        
        print("All dynamic_settings table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in dynamic_settings table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up test data
        clean_test_data()

if __name__ == "__main__":
    test_dynamic_settings_crud()
