"""
Tests for the loss_of_goods table module.

This module contains tests for the loss_of_goods table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.loss_of_goods import (
    create_loss_of_goods, get_loss_of_goods, get_all_loss_of_goods,
    get_loss_of_goods_by_farm, get_loss_of_goods_by_item_type,
    get_loss_of_goods_by_source, get_loss_of_goods_by_date_range,
    get_loss_of_goods_by_farm_and_date_range, calculate_total_loss_by_item_type,
    calculate_total_loss_by_farm, update_loss_of_goods, delete_loss_of_goods
)
from storage.tables.farms import create_farm
from storage.tables.bulk import create_bulk
from storage.tables.cost_of_goods import create_cost_of_goods
from storage.tables.harvest import create_harvest
from storage.db_utils import get_connection, execute_query, get_timestamp, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test loss_of_goods records that might exist from previous test runs
        cursor.execute("DELETE FROM loss_of_goods WHERE item_type LIKE 'Test Loss%'")
        cursor.execute("DELETE FROM harvest WHERE bulk_id IN (SELECT bulk_id FROM bulk WHERE unit_id IN (SELECT unit_id FROM cost_of_goods WHERE item_name LIKE 'Test Loss%'))")
        cursor.execute("DELETE FROM bulk WHERE unit_id IN (SELECT unit_id FROM cost_of_goods WHERE item_name LIKE 'Test Loss%')")
        cursor.execute("DELETE FROM cost_of_goods WHERE item_name LIKE 'Test Loss%'")
        cursor.execute("DELETE FROM farms WHERE farm_name LIKE 'Test Loss%'")
        conn.commit()
    finally:
        conn.close()

def test_loss_of_goods_crud():
    """Test CRUD operations for the loss_of_goods table."""
    print("\nTesting loss_of_goods table CRUD operations...")
    
    try:
        # Clean up any existing test data
        clean_test_data()
        
        # Get current timestamp and timestamps for testing date ranges
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)
        tomorrow = now + timedelta(days=1)
        
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        yesterday_str = yesterday.strftime("%Y-%m-%d %H:%M:%S")
        two_days_ago_str = two_days_ago.strftime("%Y-%m-%d %H:%M:%S")
        tomorrow_str = tomorrow.strftime("%Y-%m-%d %H:%M:%S")
        
        # Create test farm, cost_of_goods, bulk, and harvest records first
        print("Creating test prerequisite records...")
        farm_id = create_farm(
            farm_name="Test Loss Farm",
            farm_loc="Test Location",
            farm_desc="Test Farm Description"
        )
        
        unit_id1 = create_cost_of_goods(
            item_name="Test Loss Unit 1",
            item_cost=40.0,
            item_count=1,
            weight_lbs=15.0
        )
        
        unit_id2 = create_cost_of_goods(
            item_name="Test Loss Unit 2",
            item_cost=30.0,
            item_count=1,
            weight_lbs=10.0
        )
        
        bulk_id1 = create_bulk(
            total_wt=10.0,
            bag_wt=2.0,
            bag_count=5,
            unit_id=unit_id1,
            start_ts=yesterday_str,
            colonized_ts=yesterday_str,
            finished_ts=now_str
        )
        
        bulk_id2 = create_bulk(
            total_wt=8.0,
            bag_wt=1.5,
            bag_count=4,
            unit_id=unit_id2,
            start_ts=yesterday_str,
            colonized_ts=yesterday_str,
            finished_ts=now_str
        )
        
        harvest_id1 = create_harvest(
            harvest_ts=now_str,
            total_wt=5.0,
            trimmed_wt=4.5,
            bulk_id=bulk_id1,
            unit_id=unit_id1
        )
        
        # Now run the tests
        
        # 1. Test create_loss_of_goods
        print("Testing create_loss_of_goods...")
        loss_id1 = create_loss_of_goods(
            item_type="Test Loss Bulk",
            source_type="bulk",
            source_id=bulk_id1,
            loss_date=yesterday_str,
            quantity=2.0,
            farm_id=farm_id,
            reason="Contamination",
            notes="Test loss of goods record 1"
        )
        
        loss_id2 = create_loss_of_goods(
            item_type="Test Loss Harvest",
            source_type="harvest",
            source_id=harvest_id1,
            loss_date=now_str,
            quantity=1.0,
            farm_id=farm_id,
            reason="Spoilage",
            notes="Test loss of goods record 2"
        )
        
        loss_id3 = create_loss_of_goods(
            item_type="Test Loss Other",
            source_type="other",
            loss_date=two_days_ago_str,
            quantity=3.0,
            farm_id=farm_id,
            reason="Miscellaneous",
            notes="Test loss of goods record 3"
        )
        
        assert loss_id1 > 0, f"Expected positive loss_id, got {loss_id1}"
        assert loss_id2 > 0, f"Expected positive loss_id, got {loss_id2}"
        assert loss_id3 > 0, f"Expected positive loss_id, got {loss_id3}"
        
        # 2. Test get_loss_of_goods
        print("Testing get_loss_of_goods...")
        loss1 = get_loss_of_goods(loss_id1)
        assert loss1 is not None, "Failed to retrieve loss1"
        assert loss1['farm_id'] == farm_id, f"Expected farm_id {farm_id}, got {loss1['farm_id']}"
        assert loss1['item_type'] == "Test Loss Bulk", f"Expected item_type 'Test Loss Bulk', got '{loss1['item_type']}'"
        assert loss1['source_id'] == bulk_id1, f"Expected source_id {bulk_id1}, got {loss1['source_id']}"
        assert loss1['source_type'] == "bulk", f"Expected source_type 'bulk', got '{loss1['source_type']}'"
        assert loss1['loss_date'] == yesterday_str, f"Expected loss_date '{yesterday_str}', got '{loss1['loss_date']}'"
        assert loss1['quantity'] == 2.0, f"Expected quantity 2.0, got {loss1['quantity']}"
        assert loss1['reason'] == "Contamination", f"Expected reason 'Contamination', got '{loss1['reason']}'"
        assert loss1['notes'] == "Test loss of goods record 1", f"Expected notes 'Test loss of goods record 1', got '{loss1['notes']}'"
        
        # 3. Test get_all_loss_of_goods
        print("Testing get_all_loss_of_goods...")
        all_losses = get_all_loss_of_goods()
        assert len(all_losses) >= 3, f"Expected at least 3 loss of goods records, got {len(all_losses)}"
        
        # 4. Test get_loss_of_goods_by_farm
        print("Testing get_loss_of_goods_by_farm...")
        farm_losses = get_loss_of_goods_by_farm(farm_id)
        assert len(farm_losses) == 3, f"Expected 3 loss of goods records for farm, got {len(farm_losses)}"
        
        # 5. Test get_loss_of_goods_by_item_type
        print("Testing get_loss_of_goods_by_item_type...")
        bulk_losses = get_loss_of_goods_by_item_type("Test Loss Bulk")
        assert len(bulk_losses) == 1, f"Expected 1 loss of goods record for 'Test Loss Bulk', got {len(bulk_losses)}"
        
        harvest_losses = get_loss_of_goods_by_item_type("Test Loss Harvest")
        assert len(harvest_losses) == 1, f"Expected 1 loss of goods record for 'Test Loss Harvest', got {len(harvest_losses)}"
        
        # 6. Test get_loss_of_goods_by_source
        print("Testing get_loss_of_goods_by_source...")
        bulk1_losses = get_loss_of_goods_by_source(bulk_id1, "bulk")
        assert len(bulk1_losses) == 1, f"Expected 1 loss of goods record for bulk1, got {len(bulk1_losses)}"
        
        harvest1_losses = get_loss_of_goods_by_source(harvest_id1, "harvest")
        assert len(harvest1_losses) == 1, f"Expected 1 loss of goods record for harvest1, got {len(harvest1_losses)}"
        
        # 7. Test get_loss_of_goods_by_date_range
        print("Testing get_loss_of_goods_by_date_range...")
        date_range_losses = get_loss_of_goods_by_date_range(two_days_ago_str, now_str)
        assert len(date_range_losses) == 3, f"Expected 3 loss of goods records in date range, got {len(date_range_losses)}"
        
        yesterday_to_now_losses = get_loss_of_goods_by_date_range(yesterday_str, now_str)
        assert len(yesterday_to_now_losses) == 2, f"Expected 2 loss of goods records from yesterday to now, got {len(yesterday_to_now_losses)}"
        
        # 8. Test get_loss_of_goods_by_farm_and_date_range
        print("Testing get_loss_of_goods_by_farm_and_date_range...")
        farm_date_range_losses = get_loss_of_goods_by_farm_and_date_range(farm_id, yesterday_str, now_str)
        assert len(farm_date_range_losses) == 2, f"Expected 2 loss of goods records for farm in date range, got {len(farm_date_range_losses)}"
        
        # 9. Test calculate_total_loss_by_item_type
        print("Testing calculate_total_loss_by_item_type...")
        bulk_total_loss = calculate_total_loss_by_item_type("Test Loss Bulk")
        assert bulk_total_loss == 2.0, f"Expected 2.0 total loss for 'Test Loss Bulk', got {bulk_total_loss}"
        
        harvest_total_loss = calculate_total_loss_by_item_type("Test Loss Harvest")
        assert harvest_total_loss == 1.0, f"Expected 1.0 total loss for 'Test Loss Harvest', got {harvest_total_loss}"
        
        # 10. Test calculate_total_loss_by_farm
        print("Testing calculate_total_loss_by_farm...")
        farm_total_loss = calculate_total_loss_by_farm(farm_id)
        assert farm_total_loss == 6.0, f"Expected 6.0 total loss for farm, got {farm_total_loss}"
        
        farm_date_range_loss = calculate_total_loss_by_farm(farm_id, yesterday_str, now_str)
        assert farm_date_range_loss == 3.0, f"Expected 3.0 total loss for farm in date range, got {farm_date_range_loss}"
        
        # 11. Test update_loss_of_goods
        print("Testing update_loss_of_goods...")
        rows_updated = update_loss_of_goods(
            loss_id1,
            item_type="Test Loss Bulk Updated",
            quantity=2.5,
            reason="Contamination - Updated",
            notes="Updated test loss of goods record 1"
        )
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_loss = get_loss_of_goods(loss_id1)
        assert updated_loss['item_type'] == "Test Loss Bulk Updated", f"Expected item_type 'Test Loss Bulk Updated', got '{updated_loss['item_type']}'"
        assert updated_loss['quantity'] == 2.5, f"Expected quantity 2.5, got {updated_loss['quantity']}"
        assert updated_loss['reason'] == "Contamination - Updated", f"Expected reason 'Contamination - Updated', got '{updated_loss['reason']}'"
        assert updated_loss['notes'] == "Updated test loss of goods record 1", f"Expected notes 'Updated test loss of goods record 1', got '{updated_loss['notes']}'"
        assert updated_loss['source_id'] == bulk_id1, f"Expected source_id unchanged at {bulk_id1}, got {updated_loss['source_id']}"
        assert updated_loss['source_type'] == "bulk", f"Expected source_type unchanged at 'bulk', got '{updated_loss['source_type']}'"
        
        # 12. Test delete_loss_of_goods
        print("Testing delete_loss_of_goods...")
        rows_deleted = delete_loss_of_goods(loss_id3)
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_loss = get_loss_of_goods(loss_id3)
        assert deleted_loss is None, f"Expected None for deleted loss, got {deleted_loss}"
        
        # Check if the deleted record is really gone
        all_losses_after_delete = get_all_loss_of_goods()
        assert len(all_losses_after_delete) == len(all_losses) - 1, f"Expected one less record after delete"
        
        # Recalculate totals after update and delete
        new_farm_total_loss = calculate_total_loss_by_farm(farm_id)
        assert new_farm_total_loss == 3.5, f"Expected 3.5 total loss for farm after update and delete, got {new_farm_total_loss}"
        
        print("All loss_of_goods table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in loss_of_goods table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up test data
        clean_test_data()

if __name__ == "__main__":
    test_loss_of_goods_crud()
