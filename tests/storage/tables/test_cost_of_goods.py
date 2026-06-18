"""
Tests for the cost_of_goods table module.

This module contains tests for the cost_of_goods table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.cost_of_goods import (
    create_cost_of_goods, get_cost_of_goods, get_all_cost_of_goods,
    get_cost_of_goods_by_name, get_cost_of_goods_by_date_range,
    get_available_cost_of_goods, update_cost_of_goods, update_usage,
    delete_cost_of_goods, get_cost_of_goods_by_item_id,
    get_cost_of_goods_with_category, get_available_cost_of_goods_by_category
)
from storage.tables.product_categories import (
    create_product_category, delete_product_category
)
from storage.db_utils import get_connection, execute_query, get_timestamp, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test cost of goods records that might exist from previous test runs
        cursor.execute("DELETE FROM cost_of_goods WHERE item_name LIKE 'Test Item%'")
        # Delete any test product categories that might exist from previous test runs
        cursor.execute("DELETE FROM product_categories WHERE category_name LIKE 'Test Category%'")
        conn.commit()
    finally:
        conn.close()

def test_cost_of_goods_crud():
    """Test CRUD operations for the cost_of_goods table."""
    print("\nTesting cost_of_goods table CRUD operations...")
    
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
        
        # First, create test product categories
        print("Creating test product categories...")
        
        mushroom_category_id = create_product_category(
            category_name="Test Category Mushrooms",
            category_type="mushroom",
            category_desc="Test mushroom category"
        )
        
        substrate_category_id = create_product_category(
            category_name="Test Category Substrate",
            category_type="substrate",
            category_desc="Test substrate category"
        )
        
        print(f"Created categories: mushroom_id={mushroom_category_id}, substrate_id={substrate_category_id}")
        
        # Now run the tests
        
        # 1. Test create_cost_of_goods with item_id
        print("Testing create_cost_of_goods with item_id...")
        unit_id1 = create_cost_of_goods(
            item_id=mushroom_category_id,
            item_name="Test Item 1 - Oyster Mushroom Spawn",
            item_cost=10.50,
            item_count=100,
            weight_lbs=25.5,
            purchase_ts=yesterday_str
        )
        
        unit_id2 = create_cost_of_goods(
            item_id=substrate_category_id,
            item_name="Test Item 2 - Straw Pellets",
            item_cost=15.75,
            item_count=50,
            weight_lbs=12.25,
            item_used=10,
            used_weight=2.5,
            purchase_ts=now_str
        )
        
        unit_id3 = create_cost_of_goods(
            item_id=mushroom_category_id,
            item_name="Test Item 3 - Shiitake Spawn",
            item_cost=5.25,
            item_count=200,
            weight_lbs=40.0,
            purchase_ts=tomorrow_str
        )
        
        assert unit_id1 > 0, f"Expected positive unit_id, got {unit_id1}"
        assert unit_id2 > 0, f"Expected positive unit_id, got {unit_id2}"
        assert unit_id3 > 0, f"Expected positive unit_id, got {unit_id3}"
        
        # 2. Test get_cost_of_goods
        print("Testing get_cost_of_goods...")
        item1 = get_cost_of_goods(unit_id1)
        assert item1 is not None, "Failed to retrieve item1"
        assert item1['item_id'] == mushroom_category_id, f"Expected item_id {mushroom_category_id}, got {item1['item_id']}"
        assert item1['item_name'] == "Test Item 1 - Oyster Mushroom Spawn", f"Expected item_name 'Test Item 1 - Oyster Mushroom Spawn', got '{item1['item_name']}'"
        assert item1['item_cost'] == 10.50, f"Expected item_cost 10.50, got {item1['item_cost']}"
        assert item1['item_count'] == 100, f"Expected item_count 100, got {item1['item_count']}"
        assert item1['weight_lbs'] == 25.5, f"Expected weight_lbs 25.5, got {item1['weight_lbs']}"
        assert item1['item_used'] == 0, f"Expected item_used 0, got {item1['item_used']}"
        assert item1['used_weight'] == 0.0, f"Expected used_weight 0.0, got {item1['used_weight']}"
        assert item1['purchase_ts'] == yesterday_str, f"Expected purchase_ts '{yesterday_str}', got '{item1['purchase_ts']}'"
        
        # 3. Test get_all_cost_of_goods
        print("Testing get_all_cost_of_goods...")
        all_items = get_all_cost_of_goods()
        assert len(all_items) >= 3, f"Expected at least 3 cost of goods records, got {len(all_items)}"
        
        # 4. Test get_cost_of_goods_by_name
        print("Testing get_cost_of_goods_by_name...")
        items_by_name = get_cost_of_goods_by_name("Test Item")
        assert len(items_by_name) == 3, f"Expected 3 items with 'Test Item' in name, got {len(items_by_name)}"
        
        special_items = get_cost_of_goods_by_name("Special")
        assert len(special_items) == 1, f"Expected 1 item with 'Special' in name, got {len(special_items)}"
        assert special_items[0]['item_name'] == "Test Item 3 Special", f"Expected item_name 'Test Item 3 Special', got '{special_items[0]['item_name']}'"
        
        # 5. Test get_cost_of_goods_by_date_range
        print("Testing get_cost_of_goods_by_date_range...")
        # Test with just start date (should include now and tomorrow)
        items_from_now = get_cost_of_goods_by_date_range(now_str)
        assert len(items_from_now) >= 1, f"Expected at least 1 item from now onwards, got {len(items_from_now)}"
        
        # Test with start and end date (should only include yesterday and now)
        items_yesterday_to_now = get_cost_of_goods_by_date_range(yesterday_str, now_str)
        assert len(items_yesterday_to_now) >= 2, f"Expected at least 2 items from yesterday to now, got {len(items_yesterday_to_now)}"
        
        # Test with narrow range (should only include now)
        items_now_only = get_cost_of_goods_by_date_range(now_str, now_str)
        assert len(items_now_only) >= 1, f"Expected at least 1 item from now, got {len(items_now_only)}"
        
        # 6. Test get_available_cost_of_goods
        print("Testing get_available_cost_of_goods...")
        available_items = get_available_cost_of_goods()
        assert len(available_items) >= 3, f"Expected at least 3 available items, got {len(available_items)}"
        
        # 7. Test update_cost_of_goods
        print("Testing update_cost_of_goods...")
        rows_updated = update_cost_of_goods(
            unit_id1,
            item_name="Test Item 1 Updated",
            item_cost=12.75,
            weight_lbs=30.0
        )
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_item = get_cost_of_goods(unit_id1)
        assert updated_item['item_name'] == "Test Item 1 Updated", f"Expected item_name 'Test Item 1 Updated', got '{updated_item['item_name']}'"
        assert updated_item['item_cost'] == 12.75, f"Expected item_cost 12.75, got {updated_item['item_cost']}"
        assert updated_item['weight_lbs'] == 30.0, f"Expected weight_lbs 30.0, got {updated_item['weight_lbs']}"
        assert updated_item['item_count'] == 100, f"Expected item_count unchanged at 100, got {updated_item['item_count']}"
        
        # 8. Test update_usage
        print("Testing update_usage...")
        # Update usage for item1
        rows_updated = update_usage(unit_id1, additional_used=25, additional_weight=7.5)
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_item = get_cost_of_goods(unit_id1)
        assert updated_item['item_used'] == 25, f"Expected item_used 25, got {updated_item['item_used']}"
        assert updated_item['used_weight'] == 7.5, f"Expected used_weight 7.5, got {updated_item['used_weight']}"
        
        # Update usage again
        rows_updated = update_usage(unit_id1, additional_used=15, additional_weight=5.0)
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_item = get_cost_of_goods(unit_id1)
        assert updated_item['item_used'] == 40, f"Expected item_used 40, got {updated_item['item_used']}"
        assert updated_item['used_weight'] == 12.5, f"Expected used_weight 12.5, got {updated_item['used_weight']}"
        
        # Test that usage cannot exceed limits
        rows_updated = update_usage(unit_id1, additional_used=1000, additional_weight=1000.0)
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_item = get_cost_of_goods(unit_id1)
        assert updated_item['item_used'] == 100, f"Expected item_used capped at 100, got {updated_item['item_used']}"
        assert updated_item['used_weight'] == 30.0, f"Expected used_weight capped at 30.0, got {updated_item['used_weight']}"
        
        # 9. Test new item_id-related functions
        print("Testing new item_id-related functions...")
        
        # Test get_cost_of_goods_by_item_id
        mushroom_items = get_cost_of_goods_by_item_id(mushroom_category_id)
        assert len(mushroom_items) == 2, f"Expected 2 mushroom items, got {len(mushroom_items)}"
        assert all(item['category_name'] == 'Test Category Mushrooms' for item in mushroom_items), "All items should have mushroom category"
        
        substrate_items = get_cost_of_goods_by_item_id(substrate_category_id)
        assert len(substrate_items) == 1, f"Expected 1 substrate item, got {len(substrate_items)}"
        assert substrate_items[0]['category_name'] == 'Test Category Substrate', "Item should have substrate category"
        
        # Test get_cost_of_goods_with_category
        all_items_with_category = get_cost_of_goods_with_category()
        test_items_with_category = [item for item in all_items_with_category if item['item_name'].startswith('Test Item')]
        assert len(test_items_with_category) == 3, f"Expected 3 test items with category, got {len(test_items_with_category)}"
        assert all('category_name' in item for item in test_items_with_category), "All items should have category_name"
        
        # Test get_available_cost_of_goods_by_category
        available_mushroom_items = get_available_cost_of_goods_by_category(mushroom_category_id)
        # unit_id1 is fully used (100/100), unit_id3 should be available (0/200)
        assert len(available_mushroom_items) == 1, f"Expected 1 available mushroom item, got {len(available_mushroom_items)}"
        assert available_mushroom_items[0]['unit_id'] == unit_id3, "Available item should be unit_id3"
        
        available_substrate_items = get_available_cost_of_goods_by_category(substrate_category_id)
        # unit_id2 has some usage (10/50), so should be available
        assert len(available_substrate_items) == 1, f"Expected 1 available substrate item, got {len(available_substrate_items)}"
        assert available_substrate_items[0]['unit_id'] == unit_id2, "Available item should be unit_id2"
        
        print("✅ All item_id-related function tests passed!")
        
        # 10. Test delete_cost_of_goods
        print("Testing delete_cost_of_goods...")
        rows_deleted = delete_cost_of_goods(unit_id3)
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_item = get_cost_of_goods(unit_id3)
        assert deleted_item is None, f"Expected None for deleted item, got {deleted_item}"
        
        remaining_items = get_cost_of_goods_by_name("Test Item")
        assert len(remaining_items) == 2, f"Expected 2 remaining items, got {len(remaining_items)}"
        
        print("All cost_of_goods table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in cost_of_goods table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up test data
        clean_test_data()

if __name__ == "__main__":
    test_cost_of_goods_crud()
