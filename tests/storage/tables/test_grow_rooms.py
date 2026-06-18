"""
Tests for the grow_rooms table module.

This module contains tests for the grow_rooms table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.grow_rooms import (
    create_grow_room, get_grow_room, get_all_grow_rooms, 
    update_grow_room, deactivate_grow_room, reactivate_grow_room, delete_grow_room
)
from storage.tables.farms import create_farm, delete_farm
from storage.db_utils import get_connection, execute_query, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test grow rooms that might exist from previous test runs
        cursor.execute("DELETE FROM grow_rooms WHERE room_name LIKE 'Test Room%'")
        # Delete any test farms that might exist from previous test runs
        cursor.execute("DELETE FROM farms WHERE farm_name LIKE 'Test Farm%'")
        conn.commit()
    finally:
        conn.close()

def test_grow_rooms_crud():
    """Test CRUD operations for the grow_rooms table."""
    print("\nTesting grow_rooms table CRUD operations...")
    
    try:
        # Clean up any existing test data
        clean_test_data()
        
        # Create a test farm first since grow_rooms has a foreign key to farms
        farm_id = create_farm("Test Farm for Rooms", "Test Location", "Test Description")
        
        # Now run the tests
        
        # 1. Test create_grow_room
        print("Testing create_grow_room...")
        room1_id = create_grow_room(farm_id, "Test Room 1", "Description 1")
        room2_id = create_grow_room(farm_id, "Test Room 2", "Description 2")
        room3_id = create_grow_room(farm_id, "Test Room 3")  # Minimal fields
        
        # IDs might not be 1, 2, 3 in the real database, so just check they're valid
        assert room1_id > 0, f"Expected room1_id to be positive, got {room1_id}"
        assert room2_id > 0, f"Expected room2_id to be positive, got {room2_id}"
        assert room3_id > 0, f"Expected room3_id to be positive, got {room3_id}"
        
        # 2. Test get_grow_room
        print("Testing get_grow_room...")
        room1 = get_grow_room(room1_id)
        assert room1 is not None, "Failed to retrieve room1"
        assert room1['room_name'] == "Test Room 1", f"Expected room_name 'Test Room 1', got '{room1['room_name']}'"
        assert room1['room_desc'] == "Description 1", f"Expected room_desc 'Description 1', got '{room1['room_desc']}'"
        assert room1['active'] == 1, f"Expected active 1, got {room1['active']}"
        assert room1['farm_id'] == farm_id, f"Expected farm_id {farm_id}, got {room1['farm_id']}"
        
        room3 = get_grow_room(room3_id)
        assert room3 is not None, "Failed to retrieve room3"
        assert room3['room_name'] == "Test Room 3", f"Expected room_name 'Test Room 3', got '{room3['room_name']}'"
        assert room3['room_desc'] is None, f"Expected room_desc None, got '{room3['room_desc']}'"
        
        # 3. Test get_all_grow_rooms
        print("Testing get_all_grow_rooms...")
        all_rooms = get_all_grow_rooms()
        # Count only our test rooms instead of assuming total count
        test_rooms_count = sum(1 for room in all_rooms if room['room_name'].startswith('Test Room'))
        assert test_rooms_count == 3, f"Expected 3 test rooms, got {test_rooms_count}"
        
        # Test filtering by farm_id
        farm_rooms = get_all_grow_rooms(farm_id=farm_id)
        assert len(farm_rooms) == 3, f"Expected 3 rooms for farm_id {farm_id}, got {len(farm_rooms)}"
        
        # 4. Test update_grow_room
        print("Testing update_grow_room...")
        rows_updated = update_grow_room(room1_id, room_name="Updated Room 1", room_desc="Updated Description")
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_room = get_grow_room(room1_id)
        assert updated_room['room_name'] == "Updated Room 1", f"Expected room_name 'Updated Room 1', got '{updated_room['room_name']}'"
        assert updated_room['room_desc'] == "Updated Description", f"Expected room_desc 'Updated Description', got '{updated_room['room_desc']}'"
        
        # 5. Test deactivate_grow_room
        print("Testing deactivate_grow_room...")
        rows_deactivated = deactivate_grow_room(room2_id, "Test deactivation")
        assert rows_deactivated == 1, f"Expected 1 row deactivated, got {rows_deactivated}"
        
        deactivated_room = get_grow_room(room2_id)
        assert deactivated_room['active'] == 0, f"Expected active 0, got {deactivated_room['active']}"
        assert deactivated_room['deactivation_reason'] == "Test deactivation", f"Expected deactivation_reason 'Test deactivation', got '{deactivated_room['deactivation_reason']}'"
        
        # 6. Test get_all_grow_rooms with active_only
        print("Testing get_all_grow_rooms with active_only...")
        active_rooms = get_all_grow_rooms(farm_id=farm_id, active_only=True)
        assert len(active_rooms) == 2, f"Expected 2 active rooms, got {len(active_rooms)}"
        
        all_rooms_including_inactive = get_all_grow_rooms(farm_id=farm_id, active_only=False)
        assert len(all_rooms_including_inactive) == 3, f"Expected 3 total rooms, got {len(all_rooms_including_inactive)}"
        
        # 7. Test reactivate_grow_room
        print("Testing reactivate_grow_room...")
        rows_reactivated = reactivate_grow_room(room2_id)
        assert rows_reactivated == 1, f"Expected 1 row reactivated, got {rows_reactivated}"
        
        reactivated_room = get_grow_room(room2_id)
        assert reactivated_room['active'] == 1, f"Expected active 1, got {reactivated_room['active']}"
        assert reactivated_room['deactivation_reason'] is None, f"Expected deactivation_reason None, got '{reactivated_room['deactivation_reason']}'"
        
        # 8. Test delete_grow_room
        print("Testing delete_grow_room...")
        rows_deleted = delete_grow_room(room3_id)
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_room = get_grow_room(room3_id)
        assert deleted_room is None, f"Expected None for deleted room, got {deleted_room}"
        
        remaining_rooms = get_all_grow_rooms(farm_id=farm_id, active_only=False)
        assert len(remaining_rooms) == 2, f"Expected 2 remaining rooms, got {len(remaining_rooms)}"
        
        # Clean up the test farm
        delete_farm(farm_id)
        
        print("All grow_rooms table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in grow_rooms table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_grow_rooms_crud()
