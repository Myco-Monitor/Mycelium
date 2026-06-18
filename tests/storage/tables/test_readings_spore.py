"""
Tests for the readings_spore table module.

This module contains tests for the readings_spore table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.readings_spore import (
    create_reading, get_reading, get_device_readings,
    update_reading, delete_reading, delete_device_readings
)
from storage.tables.device_spore import create_device_spore
from storage.db_utils import get_connection, execute_query, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test readings that might exist from previous test runs
        cursor.execute("DELETE FROM readings_spore WHERE device_id IN (SELECT device_id FROM device_spore WHERE device_name LIKE 'Test Spore%')")
        cursor.execute("DELETE FROM device_spore WHERE device_name LIKE 'Test Spore%'")
        conn.commit()
    finally:
        conn.close()

def test_readings_spore_crud():
    """Test CRUD operations for the readings_spore table."""
    print("\nTesting readings_spore table CRUD operations...")
    
    try:
        # Clean up any existing test data
        clean_test_data()
        
        # Create a test device first
        print("Creating test device...")
        device_id = create_device_spore(
            device_name="Test Spore Device",
            room_id=1,  # Assuming room_id 1 exists
            ip_address="192.168.1.100",
            mac_address="AA:BB:CC:DD:EE:FF"
        )
        
        # Now run the tests
        
        # 1. Test create_reading
        print("Testing create_reading...")
        timestamp1 = "2025-07-18 08:00:00"
        timestamp2 = "2025-07-18 08:15:00"
        timestamp3 = "2025-07-18 08:30:00"
        
        # Create readings with different combinations of optional parameters
        reading1_key = create_reading(device_id, timestamp1, 800.5, 65.2, 22.5, "2025-07-18 08:00:00")
        reading2_key = create_reading(device_id, timestamp2, 850.0, 67.0, 23.0)
        reading3_key = create_reading(device_id, timestamp3, co2=900.0)
        
        assert reading1_key[0] == device_id, f"Expected device_id {device_id}, got {reading1_key[0]}"
        assert reading1_key[1] == timestamp1, f"Expected timestamp {timestamp1}, got {reading1_key[1]}"
        
        # 2. Test get_reading
        print("Testing get_reading...")
        reading1 = get_reading(device_id, timestamp1)
        assert reading1 is not None, "Failed to retrieve reading1"
        assert reading1['co2'] == 800.5, f"Expected co2 800.5, got {reading1['co2']}"
        assert reading1['humidity'] == 65.2, f"Expected humidity 65.2, got {reading1['humidity']}"
        assert reading1['temp'] == 22.5, f"Expected temp 22.5, got {reading1['temp']}"
        assert reading1['spore_ts'] == "2025-07-18 08:00:00", f"Expected spore_ts '2025-07-18 08:00:00', got '{reading1['spore_ts']}'"
        
        reading3 = get_reading(device_id, timestamp3)
        assert reading3 is not None, "Failed to retrieve reading3"
        assert reading3['co2'] == 900.0, f"Expected co2 900.0, got {reading3['co2']}"
        assert reading3['humidity'] is None, f"Expected humidity None, got {reading3['humidity']}"
        assert reading3['temp'] is None, f"Expected temp None, got {reading3['temp']}"
        
        # 3. Test get_device_readings
        print("Testing get_device_readings...")
        all_readings = get_device_readings(device_id)
        assert len(all_readings) == 3, f"Expected 3 readings, got {len(all_readings)}"
        
        # Test with time range
        filtered_readings = get_device_readings(device_id, start_ts=timestamp2)
        assert len(filtered_readings) == 2, f"Expected 2 filtered readings, got {len(filtered_readings)}"
        
        limited_readings = get_device_readings(device_id, limit=1)
        assert len(limited_readings) == 1, f"Expected 1 limited reading, got {len(limited_readings)}"
        # The most recent reading should be first due to DESC order
        assert limited_readings[0]['reading_ts'] == timestamp3, f"Expected most recent reading {timestamp3}, got {limited_readings[0]['reading_ts']}"
        
        # 4. Test update_reading
        print("Testing update_reading...")
        rows_updated = update_reading(device_id, timestamp2, co2=875.0, temp=24.0)
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_reading = get_reading(device_id, timestamp2)
        assert updated_reading['co2'] == 875.0, f"Expected co2 875.0, got {updated_reading['co2']}"
        assert updated_reading['humidity'] == 67.0, f"Expected humidity unchanged at 67.0, got {updated_reading['humidity']}"
        assert updated_reading['temp'] == 24.0, f"Expected temp 24.0, got {updated_reading['temp']}"
        
        # 5. Test delete_reading
        print("Testing delete_reading...")
        rows_deleted = delete_reading(device_id, timestamp3)
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_reading = get_reading(device_id, timestamp3)
        assert deleted_reading is None, f"Expected None for deleted reading, got {deleted_reading}"
        
        remaining_readings = get_device_readings(device_id)
        assert len(remaining_readings) == 2, f"Expected 2 remaining readings, got {len(remaining_readings)}"
        
        # 6. Test delete_device_readings
        print("Testing delete_device_readings...")
        rows_deleted_bulk = delete_device_readings(device_id)
        assert rows_deleted_bulk == 2, f"Expected 2 rows deleted in bulk, got {rows_deleted_bulk}"
        
        final_readings = get_device_readings(device_id)
        assert len(final_readings) == 0, f"Expected 0 final readings, got {len(final_readings)}"
        
        print("All readings_spore table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in readings_spore table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up test data
        clean_test_data()

if __name__ == "__main__":
    test_readings_spore_crud()
