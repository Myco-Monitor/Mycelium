"""
Tests for the schedule_settings table module.

This module contains tests for the schedule_settings table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.schedule_settings import (
    create_schedule_setting, get_schedule_setting, get_device_schedule_settings,
    update_schedule_setting, delete_schedule_setting, delete_device_schedule_settings
)
from storage.tables.device_hyphae import create_device_hyphae
from storage.db_utils import get_connection, execute_query, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test schedule settings that might exist from previous test runs
        cursor.execute("DELETE FROM schedule_settings WHERE device_id IN (SELECT device_id FROM device_hyphae WHERE device_name LIKE 'Test Schedule%')")
        cursor.execute("DELETE FROM device_hyphae WHERE device_name LIKE 'Test Schedule%'")
        conn.commit()
    finally:
        conn.close()

def test_schedule_settings_crud():
    """Test CRUD operations for the schedule_settings table."""
    print("\nTesting schedule_settings table CRUD operations...")
    
    try:
        # Clean up any existing test data
        clean_test_data()
        
        # Create a test device first
        print("Creating test device...")
        device_id = create_device_hyphae(
            device_name="Test Schedule Device",
            room_id=1,  # Assuming room_id 1 exists
            ip_address="192.168.1.202",
            mac_address="22:33:44:55:66:77"
        )
        
        # Now run the tests
        
        # 1. Test create_schedule_setting
        print("Testing create_schedule_setting...")
        schedule1_key = create_schedule_setting(device_id, 1, "08:00", "20:00")
        schedule2_key = create_schedule_setting(device_id, 2, "06:00", "18:00")
        schedule3_key = create_schedule_setting(device_id, 3)  # No times specified
        
        assert schedule1_key[0] == device_id, f"Expected device_id {device_id}, got {schedule1_key[0]}"
        assert schedule1_key[1] == 1, f"Expected group_num 1, got {schedule1_key[1]}"
        
        # 2. Test get_schedule_setting
        print("Testing get_schedule_setting...")
        schedule1 = get_schedule_setting(device_id, 1)
        assert schedule1 is not None, "Failed to retrieve schedule1"
        assert schedule1['on_time'] == "08:00", f"Expected on_time '08:00', got '{schedule1['on_time']}'"
        assert schedule1['off_time'] == "20:00", f"Expected off_time '20:00', got '{schedule1['off_time']}'"
        
        schedule3 = get_schedule_setting(device_id, 3)
        assert schedule3 is not None, "Failed to retrieve schedule3"
        assert schedule3['on_time'] is None, f"Expected on_time None, got '{schedule3['on_time']}'"
        assert schedule3['off_time'] is None, f"Expected off_time None, got '{schedule3['off_time']}'"
        
        # 3. Test get_device_schedule_settings
        print("Testing get_device_schedule_settings...")
        all_schedules = get_device_schedule_settings(device_id)
        assert len(all_schedules) == 3, f"Expected 3 schedule settings, got {len(all_schedules)}"
        
        # 4. Test update_schedule_setting
        print("Testing update_schedule_setting...")
        rows_updated = update_schedule_setting(device_id, 3, on_time="10:00", off_time="22:00")
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_schedule = get_schedule_setting(device_id, 3)
        assert updated_schedule['on_time'] == "10:00", f"Expected on_time '10:00', got '{updated_schedule['on_time']}'"
        assert updated_schedule['off_time'] == "22:00", f"Expected off_time '22:00', got '{updated_schedule['off_time']}'"
        
        # Update just one field
        rows_updated = update_schedule_setting(device_id, 2, on_time="07:00")
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_schedule = get_schedule_setting(device_id, 2)
        assert updated_schedule['on_time'] == "07:00", f"Expected on_time '07:00', got '{updated_schedule['on_time']}'"
        assert updated_schedule['off_time'] == "18:00", f"Expected off_time unchanged at '18:00', got '{updated_schedule['off_time']}'"
        
        # 5. Test delete_schedule_setting
        print("Testing delete_schedule_setting...")
        rows_deleted = delete_schedule_setting(device_id, 3)
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_schedule = get_schedule_setting(device_id, 3)
        assert deleted_schedule is None, f"Expected None for deleted schedule, got {deleted_schedule}"
        
        remaining_schedules = get_device_schedule_settings(device_id)
        assert len(remaining_schedules) == 2, f"Expected 2 remaining schedule settings, got {len(remaining_schedules)}"
        
        # 6. Test delete_device_schedule_settings
        print("Testing delete_device_schedule_settings...")
        rows_deleted_device = delete_device_schedule_settings(device_id)
        assert rows_deleted_device == 2, f"Expected 2 rows deleted for device, got {rows_deleted_device}"
        
        final_schedules = get_device_schedule_settings(device_id)
        assert len(final_schedules) == 0, f"Expected 0 final schedule settings, got {len(final_schedules)}"
        
        print("All schedule_settings table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in schedule_settings table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up test data
        clean_test_data()

if __name__ == "__main__":
    test_schedule_settings_crud()
