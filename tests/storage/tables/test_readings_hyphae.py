"""
Tests for the readings_hyphae table module.

This module contains tests for the readings_hyphae table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.readings_hyphae import (
    create_reading, get_reading, get_device_readings,
    get_relay_state_history, update_reading, delete_reading, delete_device_readings
)
from storage.tables.device_hyphae import create_device_hyphae
from storage.db_utils import get_connection, execute_query, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test readings that might exist from previous test runs
        cursor.execute("DELETE FROM readings_hyphae WHERE device_id IN (SELECT device_id FROM device_hyphae WHERE device_name LIKE 'Test Hyphae%')")
        cursor.execute("DELETE FROM device_hyphae WHERE device_name LIKE 'Test Hyphae%'")
        conn.commit()
    finally:
        conn.close()

def test_readings_hyphae_crud():
    """Test CRUD operations for the readings_hyphae table."""
    print("\nTesting readings_hyphae table CRUD operations...")
    
    try:
        # Clean up any existing test data
        clean_test_data()
        
        # Create a test device first
        print("Creating test device...")
        device_id = create_device_hyphae(
            device_name="Test Hyphae Device",
            room_id=1,  # Assuming room_id 1 exists
            ip_address="192.168.1.200",
            mac_address="FF:EE:DD:CC:BB:AA"
        )
        
        # Now run the tests
        
        # 1. Test create_reading
        print("Testing create_reading...")
        timestamp1 = "2025-07-18 08:00:00"
        timestamp2 = "2025-07-18 08:15:00"
        timestamp3 = "2025-07-18 08:30:00"
        
        # Create readings with different combinations of optional parameters
        reading1_key = create_reading(device_id, timestamp1, 1, 1, 300, 0, "2025-07-18 08:00:00")
        reading2_key = create_reading(device_id, timestamp2, 2, 0, 600)
        reading3_key = create_reading(device_id, timestamp3, 1, 0)
        
        assert reading1_key[0] == device_id, f"Expected device_id {device_id}, got {reading1_key[0]}"
        assert reading1_key[1] == timestamp1, f"Expected timestamp {timestamp1}, got {reading1_key[1]}"
        assert reading1_key[2] == 1, f"Expected relay_number 1, got {reading1_key[2]}"
        
        # 2. Test get_reading
        print("Testing get_reading...")
        reading1 = get_reading(device_id, timestamp1, 1)
        assert reading1 is not None, "Failed to retrieve reading1"
        assert reading1['relay_state'] == 1, f"Expected relay_state 1, got {reading1['relay_state']}"
        assert reading1['cooldown'] == 300, f"Expected cooldown 300, got {reading1['cooldown']}"
        assert reading1['testing'] == 0, f"Expected testing 0, got {reading1['testing']}"
        assert reading1['hyphae_ts'] == "2025-07-18 08:00:00", f"Expected hyphae_ts '2025-07-18 08:00:00', got '{reading1['hyphae_ts']}'"
        
        reading3 = get_reading(device_id, timestamp3, 1)
        assert reading3 is not None, "Failed to retrieve reading3"
        assert reading3['relay_state'] == 0, f"Expected relay_state 0, got {reading3['relay_state']}"
        assert reading3['cooldown'] is None, f"Expected cooldown None, got {reading3['cooldown']}"
        assert reading3['testing'] == 0, f"Expected testing 0, got {reading3['testing']}"
        
        # 3. Test get_device_readings
        print("Testing get_device_readings...")
        all_readings = get_device_readings(device_id)
        assert len(all_readings) == 3, f"Expected 3 readings, got {len(all_readings)}"
        
        # Test with relay filtering
        relay1_readings = get_device_readings(device_id, relay_number=1)
        assert len(relay1_readings) == 2, f"Expected 2 readings for relay 1, got {len(relay1_readings)}"
        
        # Test with time range
        filtered_readings = get_device_readings(device_id, start_ts=timestamp2)
        assert len(filtered_readings) == 2, f"Expected 2 filtered readings, got {len(filtered_readings)}"
        
        limited_readings = get_device_readings(device_id, limit=1)
        assert len(limited_readings) == 1, f"Expected 1 limited reading, got {len(limited_readings)}"
        # The most recent reading should be first due to DESC order
        assert limited_readings[0]['reading_ts'] == timestamp3, f"Expected most recent reading {timestamp3}, got {limited_readings[0]['reading_ts']}"
        
        # 4. Test get_relay_state_history
        print("Testing get_relay_state_history...")
        relay1_history = get_relay_state_history(device_id, 1)
        assert len(relay1_history) == 2, f"Expected 2 history entries for relay 1, got {len(relay1_history)}"
        assert relay1_history[0]['reading_ts'] == timestamp3, f"Expected most recent timestamp {timestamp3}, got {relay1_history[0]['reading_ts']}"
        
        # 5. Test update_reading
        print("Testing update_reading...")
        rows_updated = update_reading(device_id, timestamp2, 2, relay_state=1, cooldown=450)
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_reading = get_reading(device_id, timestamp2, 2)
        assert updated_reading['relay_state'] == 1, f"Expected relay_state 1, got {updated_reading['relay_state']}"
        assert updated_reading['cooldown'] == 450, f"Expected cooldown 450, got {updated_reading['cooldown']}"
        
        # 6. Test delete_reading
        print("Testing delete_reading...")
        rows_deleted = delete_reading(device_id, timestamp3, 1)
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_reading = get_reading(device_id, timestamp3, 1)
        assert deleted_reading is None, f"Expected None for deleted reading, got {deleted_reading}"
        
        remaining_readings = get_device_readings(device_id)
        assert len(remaining_readings) == 2, f"Expected 2 remaining readings, got {len(remaining_readings)}"
        
        # 7. Test delete_device_readings with relay filtering
        print("Testing delete_device_readings with relay filtering...")
        rows_deleted_relay = delete_device_readings(device_id, relay_number=2)
        assert rows_deleted_relay == 1, f"Expected 1 row deleted for relay 2, got {rows_deleted_relay}"
        
        # 8. Test delete_device_readings for all remaining readings
        print("Testing delete_device_readings for all...")
        rows_deleted_bulk = delete_device_readings(device_id)
        assert rows_deleted_bulk == 1, f"Expected 1 row deleted in bulk, got {rows_deleted_bulk}"
        
        final_readings = get_device_readings(device_id)
        assert len(final_readings) == 0, f"Expected 0 final readings, got {len(final_readings)}"
        
        print("All readings_hyphae table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in readings_hyphae table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up test data
        clean_test_data()

if __name__ == "__main__":
    test_readings_hyphae_crud()
