"""
Tests for the harvest table module.

This module contains tests for the harvest table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.harvest import (
    create_harvest, get_harvest, get_all_harvests, get_harvests_by_bulk,
    get_harvests_by_unit, get_harvests_by_date_range, get_available_harvests,
    update_harvest, update_harvest_weight_used, delete_harvest
)
from storage.tables.bulk import create_bulk
from storage.tables.cost_of_goods import create_cost_of_goods
from storage.db_utils import get_connection, execute_query, get_timestamp, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test harvest records that might exist from previous test runs
        cursor.execute("DELETE FROM harvest WHERE unit_id IN (SELECT unit_id FROM cost_of_goods WHERE item_name LIKE 'Test Harvest%')")
        cursor.execute("DELETE FROM bulk WHERE unit_id IN (SELECT unit_id FROM cost_of_goods WHERE item_name LIKE 'Test Harvest%')")
        cursor.execute("DELETE FROM cost_of_goods WHERE item_name LIKE 'Test Harvest%'")
        conn.commit()
    finally:
        conn.close()

def test_harvest_crud():
    """Test CRUD operations for the harvest table."""
    print("\nTesting harvest table CRUD operations...")
    
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
            item_name="Test Harvest Unit",
            item_cost=40.0,
            item_count=1,
            weight_lbs=15.0
        )
        
        # Create test bulk record
        print("Creating test bulk record...")
        bulk_id = create_bulk(
            total_wt=10.0,
            bag_wt=2.0,
            bag_count=5,
            unit_id=unit_id,
            start_ts=yesterday_str,
            colonized_ts=yesterday_str,
            finished_ts=now_str
        )
        
        # Now run the tests
        
        # 1. Test create_harvest
        print("Testing create_harvest...")
        harvest_id1 = create_harvest(
            harvest_ts=now_str,
            total_wt=5.0,
            trimmed_wt=4.5,
            bulk_id=bulk_id,
            unit_id=unit_id
        )
        
        harvest_id2 = create_harvest(
            harvest_ts=yesterday_str,
            total_wt=3.0,
            trimmed_wt=2.8,
            bulk_id=bulk_id,
            weight_used=1.0
        )
        
        harvest_id3 = create_harvest(
            harvest_ts=tomorrow_str,
            total_wt=2.0,
            trimmed_wt=1.8,
            unit_id=unit_id
        )
        
        assert harvest_id1 > 0, f"Expected positive harvest_id, got {harvest_id1}"
        assert harvest_id2 > 0, f"Expected positive harvest_id, got {harvest_id2}"
        assert harvest_id3 > 0, f"Expected positive harvest_id, got {harvest_id3}"
        
        # 2. Test get_harvest
        print("Testing get_harvest...")
        harvest1 = get_harvest(harvest_id1)
        assert harvest1 is not None, "Failed to retrieve harvest1"
        assert harvest1['total_wt'] == 5.0, f"Expected total_wt 5.0, got {harvest1['total_wt']}"
        assert harvest1['trimmed_wt'] == 4.5, f"Expected trimmed_wt 4.5, got {harvest1['trimmed_wt']}"
        assert harvest1['bulk_id'] == bulk_id, f"Expected bulk_id {bulk_id}, got {harvest1['bulk_id']}"
        assert harvest1['unit_id'] == unit_id, f"Expected unit_id {unit_id}, got {harvest1['unit_id']}"
        assert harvest1['weight_used'] == 0.0, f"Expected weight_used 0.0, got {harvest1['weight_used']}"
        assert harvest1['harvest_ts'] == now_str, f"Expected harvest_ts '{now_str}', got '{harvest1['harvest_ts']}'"
        
        # 3. Test get_all_harvests
        print("Testing get_all_harvests...")
        all_harvests = get_all_harvests()
        assert len(all_harvests) >= 3, f"Expected at least 3 harvest records, got {len(all_harvests)}"
        
        # 4. Test get_harvests_by_bulk
        print("Testing get_harvests_by_bulk...")
        bulk_harvests = get_harvests_by_bulk(bulk_id)
        assert len(bulk_harvests) == 2, f"Expected 2 harvest records for bulk, got {len(bulk_harvests)}"
        
        # 5. Test get_harvests_by_unit
        print("Testing get_harvests_by_unit...")
        unit_harvests = get_harvests_by_unit(unit_id)
        assert len(unit_harvests) == 2, f"Expected 2 harvest records for unit, got {len(unit_harvests)}"
        
        # 6. Test get_harvests_by_date_range
        print("Testing get_harvests_by_date_range...")
        # Test with just start date
        recent_harvests = get_harvests_by_date_range(yesterday_str)
        assert len(recent_harvests) >= 2, f"Expected at least 2 recent harvest records, got {len(recent_harvests)}"
        
        # Test with start and end date
        yesterday_harvests = get_harvests_by_date_range(yesterday_str, yesterday_str)
        assert len(yesterday_harvests) >= 1, f"Expected at least 1 harvest record from yesterday, got {len(yesterday_harvests)}"
        
        # 7. Test get_available_harvests
        print("Testing get_available_harvests...")
        available_harvests = get_available_harvests()
        assert len(available_harvests) >= 3, f"Expected at least 3 available harvest records, got {len(available_harvests)}"
        
        # 8. Test update_harvest
        print("Testing update_harvest...")
        rows_updated = update_harvest(
            harvest_id1,
            total_wt=5.5,
            trimmed_wt=5.0
        )
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_harvest = get_harvest(harvest_id1)
        assert updated_harvest['total_wt'] == 5.5, f"Expected total_wt 5.5, got {updated_harvest['total_wt']}"
        assert updated_harvest['trimmed_wt'] == 5.0, f"Expected trimmed_wt 5.0, got {updated_harvest['trimmed_wt']}"
        assert updated_harvest['bulk_id'] == bulk_id, f"Expected bulk_id unchanged at {bulk_id}, got {updated_harvest['bulk_id']}"
        
        # 9. Test update_harvest_weight_used
        print("Testing update_harvest_weight_used...")
        rows_updated = update_harvest_weight_used(harvest_id1, 2.0)
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_weight = get_harvest(harvest_id1)
        assert updated_weight['weight_used'] == 2.0, f"Expected weight_used 2.0, got {updated_weight['weight_used']}"
        
        # Add more weight to test cumulative updates
        rows_updated = update_harvest_weight_used(harvest_id1, 1.5)
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_weight_again = get_harvest(harvest_id1)
        assert updated_weight_again['weight_used'] == 3.5, f"Expected weight_used 3.5, got {updated_weight_again['weight_used']}"
        
        # After updating weight used, check available harvests again
        available_harvests_after = get_available_harvests()
        # All harvests should still have available weight
        assert len(available_harvests_after) >= 3, f"Expected at least 3 available harvest records, got {len(available_harvests_after)}"
        
        # Update harvest to use all weight
        rows_updated = update_harvest(harvest_id3, weight_used=2.0)
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        # Check if available harvests decreased
        available_harvests_final = get_available_harvests()
        assert len(available_harvests_final) < len(available_harvests), f"Expected fewer available harvest records after using all weight"
        
        # 10. Test delete_harvest
        print("Testing delete_harvest...")
        rows_deleted = delete_harvest(harvest_id2)
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_harvest = get_harvest(harvest_id2)
        assert deleted_harvest is None, f"Expected None for deleted harvest, got {deleted_harvest}"
        
        remaining_harvests = get_all_harvests()
        assert len(remaining_harvests) >= 2, f"Expected at least 2 remaining harvest records, got {len(remaining_harvests)}"
        
        print("All harvest table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in harvest table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up test data
        clean_test_data()

if __name__ == "__main__":
    test_harvest_crud()
