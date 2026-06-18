"""
Tests for the spawn table module.

This module contains tests for the spawn table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.spawn import (
    create_spawn, get_spawn, get_all_spawn, get_spawn_by_unit,
    get_spawn_by_bag, get_spawn_by_date_range, get_active_spawn,
    update_spawn, update_spawn_status, delete_spawn
)
from storage.tables.cost_of_goods import create_cost_of_goods
from storage.db_utils import get_connection, execute_query, get_timestamp, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test spawn records that might exist from previous test runs
        cursor.execute("DELETE FROM spawn WHERE unit_id IN (SELECT unit_id FROM cost_of_goods WHERE item_name LIKE 'Test Spawn%')")
        cursor.execute("DELETE FROM cost_of_goods WHERE item_name LIKE 'Test Spawn%'")
        conn.commit()
    finally:
        conn.close()

def test_spawn_crud():
    """Test CRUD operations for the spawn table."""
    print("\nTesting spawn table CRUD operations...")
    
    try:
        # Clean up any existing test data
        clean_test_data()
        
        # Get current timestamp and timestamps for testing date ranges
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)
        
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        yesterday_str = yesterday.strftime("%Y-%m-%d %H:%M:%S")
        tomorrow_str = tomorrow.strftime("%Y-%m-%d %H:%M:%S")
        
        # Create test cost_of_goods records first
        print("Creating test cost_of_goods records...")
        unit_id = create_cost_of_goods(
            item_name="Test Spawn Unit",
            item_cost=25.0,
            item_count=10,
            weight_lbs=5.0
        )
        
        bag_id = create_cost_of_goods(
            item_name="Test Spawn Bags",
            item_cost=15.0,
            item_count=50,
            weight_lbs=2.5
        )
        
        # Now run the tests
        
        # 1. Test create_spawn
        print("Testing create_spawn...")
        spawn_id1 = create_spawn(
            total_wt=4.0,
            bag_wt=1.0,
            bag_count=4,
            unit_id=unit_id,
            bag_id=bag_id,
            prep_notes="Test preparation notes",
            start_ts=yesterday_str
        )
        
        spawn_id2 = create_spawn(
            total_wt=3.0,
            bag_wt=1.0,
            bag_count=3,
            unit_id=unit_id,
            start_ts=now_str,
            inoculated_ts=now_str
        )
        
        spawn_id3 = create_spawn(
            total_wt=2.0,
            bag_wt=1.0,
            bag_count=2,
            bag_id=bag_id
        )
        
        assert spawn_id1 > 0, f"Expected positive spawn_id, got {spawn_id1}"
        assert spawn_id2 > 0, f"Expected positive spawn_id, got {spawn_id2}"
        assert spawn_id3 > 0, f"Expected positive spawn_id, got {spawn_id3}"
        
        # 2. Test get_spawn
        print("Testing get_spawn...")
        spawn1 = get_spawn(spawn_id1)
        assert spawn1 is not None, "Failed to retrieve spawn1"
        assert spawn1['total_wt'] == 4.0, f"Expected total_wt 4.0, got {spawn1['total_wt']}"
        assert spawn1['bag_wt'] == 1.0, f"Expected bag_wt 1.0, got {spawn1['bag_wt']}"
        assert spawn1['bag_count'] == 4, f"Expected bag_count 4, got {spawn1['bag_count']}"
        assert spawn1['unit_id'] == unit_id, f"Expected unit_id {unit_id}, got {spawn1['unit_id']}"
        assert spawn1['bag_id'] == bag_id, f"Expected bag_id {bag_id}, got {spawn1['bag_id']}"
        assert spawn1['prep_notes'] == "Test preparation notes", f"Expected prep_notes 'Test preparation notes', got '{spawn1['prep_notes']}'"
        assert spawn1['start_ts'] == yesterday_str, f"Expected start_ts '{yesterday_str}', got '{spawn1['start_ts']}'"
        assert spawn1['inoculated_ts'] is None, f"Expected inoculated_ts None, got '{spawn1['inoculated_ts']}'"
        assert spawn1['finished_ts'] is None, f"Expected finished_ts None, got '{spawn1['finished_ts']}'"
        
        # 3. Test get_all_spawn
        print("Testing get_all_spawn...")
        all_spawn = get_all_spawn()
        assert len(all_spawn) >= 3, f"Expected at least 3 spawn records, got {len(all_spawn)}"
        
        # 4. Test get_spawn_by_unit
        print("Testing get_spawn_by_unit...")
        unit_spawn = get_spawn_by_unit(unit_id)
        assert len(unit_spawn) == 2, f"Expected 2 spawn records for unit, got {len(unit_spawn)}"
        
        # 5. Test get_spawn_by_bag
        print("Testing get_spawn_by_bag...")
        bag_spawn = get_spawn_by_bag(bag_id)
        assert len(bag_spawn) == 2, f"Expected 2 spawn records for bag, got {len(bag_spawn)}"
        
        # 6. Test get_spawn_by_date_range
        print("Testing get_spawn_by_date_range...")
        # Test with just start date
        recent_spawn = get_spawn_by_date_range(yesterday_str)
        assert len(recent_spawn) >= 2, f"Expected at least 2 recent spawn records, got {len(recent_spawn)}"
        
        # Test with start and end date
        yesterday_spawn = get_spawn_by_date_range(yesterday_str, yesterday_str)
        assert len(yesterday_spawn) >= 1, f"Expected at least 1 spawn record from yesterday, got {len(yesterday_spawn)}"
        
        # 7. Test get_active_spawn
        print("Testing get_active_spawn...")
        active_spawn = get_active_spawn()
        assert len(active_spawn) >= 1, f"Expected at least 1 active spawn record, got {len(active_spawn)}"
        
        # 8. Test update_spawn
        print("Testing update_spawn...")
        rows_updated = update_spawn(
            spawn_id1,
            total_wt=4.5,
            bag_count=5,
            prep_notes="Updated preparation notes"
        )
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_spawn = get_spawn(spawn_id1)
        assert updated_spawn['total_wt'] == 4.5, f"Expected total_wt 4.5, got {updated_spawn['total_wt']}"
        assert updated_spawn['bag_count'] == 5, f"Expected bag_count 5, got {updated_spawn['bag_count']}"
        assert updated_spawn['prep_notes'] == "Updated preparation notes", f"Expected prep_notes 'Updated preparation notes', got '{updated_spawn['prep_notes']}'"
        assert updated_spawn['bag_wt'] == 1.0, f"Expected bag_wt unchanged at 1.0, got {updated_spawn['bag_wt']}"
        
        # 9. Test update_spawn_status
        print("Testing update_spawn_status...")
        rows_updated = update_spawn_status(
            spawn_id1,
            inoculated_ts=now_str,
            finished_ts=tomorrow_str
        )
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_status = get_spawn(spawn_id1)
        assert updated_status['inoculated_ts'] == now_str, f"Expected inoculated_ts '{now_str}', got '{updated_status['inoculated_ts']}'"
        assert updated_status['finished_ts'] == tomorrow_str, f"Expected finished_ts '{tomorrow_str}', got '{updated_status['finished_ts']}'"
        assert updated_status['start_ts'] == yesterday_str, f"Expected start_ts unchanged at '{yesterday_str}', got '{updated_status['start_ts']}'"
        
        # After updating status, check active spawn again
        active_spawn_after = get_active_spawn()
        assert len(active_spawn_after) < len(active_spawn), f"Expected fewer active spawn records after finishing one"
        
        # 10. Test delete_spawn
        print("Testing delete_spawn...")
        rows_deleted = delete_spawn(spawn_id3)
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_spawn = get_spawn(spawn_id3)
        assert deleted_spawn is None, f"Expected None for deleted spawn, got {deleted_spawn}"
        
        remaining_spawn = get_all_spawn()
        assert len(remaining_spawn) >= 2, f"Expected at least 2 remaining spawn records, got {len(remaining_spawn)}"
        
        print("All spawn table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in spawn table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up test data
        clean_test_data()

if __name__ == "__main__":
    test_spawn_crud()
