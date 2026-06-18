"""
Tests for the bulk table module.

This module contains tests for the bulk table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.bulk import (
    create_bulk, get_bulk, get_all_bulk, get_bulk_by_spawn,
    get_bulk_by_unit, get_bulk_by_bag, get_bulk_by_date_range,
    get_active_bulk, get_colonized_bulk, update_bulk, update_bulk_status, delete_bulk
)
from storage.tables.spawn import create_spawn
from storage.tables.cost_of_goods import create_cost_of_goods
from storage.db_utils import get_connection, execute_query, get_timestamp, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test bulk records that might exist from previous test runs
        cursor.execute("DELETE FROM bulk WHERE unit_id IN (SELECT unit_id FROM cost_of_goods WHERE item_name LIKE 'Test Bulk%')")
        cursor.execute("DELETE FROM spawn WHERE unit_id IN (SELECT unit_id FROM cost_of_goods WHERE item_name LIKE 'Test Bulk%')")
        cursor.execute("DELETE FROM cost_of_goods WHERE item_name LIKE 'Test Bulk%'")
        conn.commit()
    finally:
        conn.close()

def test_bulk_crud():
    """Test CRUD operations for the bulk table."""
    print("\nTesting bulk table CRUD operations...")
    
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
            item_name="Test Bulk Unit",
            item_cost=30.0,
            item_count=5,
            weight_lbs=10.0
        )
        
        bag_id = create_cost_of_goods(
            item_name="Test Bulk Bags",
            item_cost=20.0,
            item_count=30,
            weight_lbs=3.0
        )
        
        # Create test spawn record
        print("Creating test spawn record...")
        spawn_id = create_spawn(
            total_wt=5.0,
            bag_wt=1.0,
            bag_count=5,
            unit_id=unit_id,
            bag_id=bag_id,
            start_ts=yesterday_str,
            inoculated_ts=yesterday_str,
            finished_ts=now_str
        )
        
        # Now run the tests
        
        # 1. Test create_bulk
        print("Testing create_bulk...")
        bulk_id1 = create_bulk(
            total_wt=8.0,
            bag_wt=2.0,
            bag_count=4,
            spawn_id=spawn_id,
            unit_id=unit_id,
            bag_id=bag_id,
            prep_notes="Test bulk preparation notes",
            start_ts=yesterday_str
        )
        
        bulk_id2 = create_bulk(
            total_wt=6.0,
            bag_wt=2.0,
            bag_count=3,
            spawn_id=spawn_id,
            unit_id=unit_id,
            start_ts=now_str,
            colonized_ts=now_str
        )
        
        bulk_id3 = create_bulk(
            total_wt=4.0,
            bag_wt=2.0,
            bag_count=2,
            bag_id=bag_id
        )
        
        assert bulk_id1 > 0, f"Expected positive bulk_id, got {bulk_id1}"
        assert bulk_id2 > 0, f"Expected positive bulk_id, got {bulk_id2}"
        assert bulk_id3 > 0, f"Expected positive bulk_id, got {bulk_id3}"
        
        # 2. Test get_bulk
        print("Testing get_bulk...")
        bulk1 = get_bulk(bulk_id1)
        assert bulk1 is not None, "Failed to retrieve bulk1"
        assert bulk1['total_wt'] == 8.0, f"Expected total_wt 8.0, got {bulk1['total_wt']}"
        assert bulk1['bag_wt'] == 2.0, f"Expected bag_wt 2.0, got {bulk1['bag_wt']}"
        assert bulk1['bag_count'] == 4, f"Expected bag_count 4, got {bulk1['bag_count']}"
        assert bulk1['spawn_id'] == spawn_id, f"Expected spawn_id {spawn_id}, got {bulk1['spawn_id']}"
        assert bulk1['unit_id'] == unit_id, f"Expected unit_id {unit_id}, got {bulk1['unit_id']}"
        assert bulk1['bag_id'] == bag_id, f"Expected bag_id {bag_id}, got {bulk1['bag_id']}"
        assert bulk1['prep_notes'] == "Test bulk preparation notes", f"Expected prep_notes 'Test bulk preparation notes', got '{bulk1['prep_notes']}'"
        assert bulk1['start_ts'] == yesterday_str, f"Expected start_ts '{yesterday_str}', got '{bulk1['start_ts']}'"
        assert bulk1['colonized_ts'] is None, f"Expected colonized_ts None, got '{bulk1['colonized_ts']}'"
        assert bulk1['finished_ts'] is None, f"Expected finished_ts None, got '{bulk1['finished_ts']}'"
        
        # 3. Test get_all_bulk
        print("Testing get_all_bulk...")
        all_bulk = get_all_bulk()
        assert len(all_bulk) >= 3, f"Expected at least 3 bulk records, got {len(all_bulk)}"
        
        # 4. Test get_bulk_by_spawn
        print("Testing get_bulk_by_spawn...")
        spawn_bulk = get_bulk_by_spawn(spawn_id)
        assert len(spawn_bulk) == 2, f"Expected 2 bulk records for spawn, got {len(spawn_bulk)}"
        
        # 5. Test get_bulk_by_unit
        print("Testing get_bulk_by_unit...")
        unit_bulk = get_bulk_by_unit(unit_id)
        assert len(unit_bulk) == 2, f"Expected 2 bulk records for unit, got {len(unit_bulk)}"
        
        # 6. Test get_bulk_by_bag
        print("Testing get_bulk_by_bag...")
        bag_bulk = get_bulk_by_bag(bag_id)
        assert len(bag_bulk) == 2, f"Expected 2 bulk records for bag, got {len(bag_bulk)}"
        
        # 7. Test get_bulk_by_date_range
        print("Testing get_bulk_by_date_range...")
        # Test with just start date
        recent_bulk = get_bulk_by_date_range(yesterday_str)
        assert len(recent_bulk) >= 2, f"Expected at least 2 recent bulk records, got {len(recent_bulk)}"
        
        # Test with start and end date
        yesterday_bulk = get_bulk_by_date_range(yesterday_str, yesterday_str)
        assert len(yesterday_bulk) >= 1, f"Expected at least 1 bulk record from yesterday, got {len(yesterday_bulk)}"
        
        # 8. Test get_active_bulk
        print("Testing get_active_bulk...")
        active_bulk = get_active_bulk()
        assert len(active_bulk) >= 2, f"Expected at least 2 active bulk records, got {len(active_bulk)}"
        
        # 9. Test get_colonized_bulk
        print("Testing get_colonized_bulk...")
        colonized_bulk = get_colonized_bulk()
        assert len(colonized_bulk) >= 1, f"Expected at least 1 colonized bulk record, got {len(colonized_bulk)}"
        
        # 10. Test update_bulk
        print("Testing update_bulk...")
        rows_updated = update_bulk(
            bulk_id1,
            total_wt=9.0,
            bag_count=5,
            prep_notes="Updated bulk preparation notes"
        )
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_bulk = get_bulk(bulk_id1)
        assert updated_bulk['total_wt'] == 9.0, f"Expected total_wt 9.0, got {updated_bulk['total_wt']}"
        assert updated_bulk['bag_count'] == 5, f"Expected bag_count 5, got {updated_bulk['bag_count']}"
        assert updated_bulk['prep_notes'] == "Updated bulk preparation notes", f"Expected prep_notes 'Updated bulk preparation notes', got '{updated_bulk['prep_notes']}'"
        assert updated_bulk['bag_wt'] == 2.0, f"Expected bag_wt unchanged at 2.0, got {updated_bulk['bag_wt']}"
        
        # 11. Test update_bulk_status
        print("Testing update_bulk_status...")
        rows_updated = update_bulk_status(
            bulk_id1,
            colonized_ts=now_str,
            finished_ts=tomorrow_str
        )
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_status = get_bulk(bulk_id1)
        assert updated_status['colonized_ts'] == now_str, f"Expected colonized_ts '{now_str}', got '{updated_status['colonized_ts']}'"
        assert updated_status['finished_ts'] == tomorrow_str, f"Expected finished_ts '{tomorrow_str}', got '{updated_status['finished_ts']}'"
        assert updated_status['start_ts'] == yesterday_str, f"Expected start_ts unchanged at '{yesterday_str}', got '{updated_status['start_ts']}'"
        
        # After updating status, check active bulk again
        active_bulk_after = get_active_bulk()
        assert len(active_bulk_after) < len(active_bulk), f"Expected fewer active bulk records after finishing one"
        
        # Note: The colonized_bulk check might not always decrease if there are other colonized records
        # that aren't part of our test, so we'll just verify the specific record's status
        updated_colonized = get_bulk(bulk_id1)
        assert updated_colonized['finished_ts'] is not None, "Expected finished_ts to be set after status update"
        
        # 12. Test delete_bulk
        print("Testing delete_bulk...")
        rows_deleted = delete_bulk(bulk_id3)
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_bulk = get_bulk(bulk_id3)
        assert deleted_bulk is None, f"Expected None for deleted bulk, got {deleted_bulk}"
        
        remaining_bulk = get_all_bulk()
        assert len(remaining_bulk) >= 2, f"Expected at least 2 remaining bulk records, got {len(remaining_bulk)}"
        
        print("All bulk table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in bulk table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up test data
        clean_test_data()

if __name__ == "__main__":
    test_bulk_crud()
