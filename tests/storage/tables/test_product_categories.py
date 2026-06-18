"""
Tests for the product_categories table module.

This module contains tests for the product_categories table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.product_categories import (
    create_product_category, get_product_category, get_all_product_categories,
    get_product_categories_by_name, get_product_categories_by_type,
    update_product_category, deactivate_product_category, delete_product_category,
    get_category_usage_count, can_delete_category
)
from storage.db_utils import get_connection, execute_query, get_timestamp, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test product categories that might exist from previous test runs
        cursor.execute("DELETE FROM product_categories WHERE category_name LIKE 'Test Category%'")
        conn.commit()
    finally:
        conn.close()

def test_product_categories_crud():
    """Test CRUD operations for the product_categories table."""
    print("\nTesting product_categories table CRUD operations...")
    
    try:
        # Clean up any existing test data
        clean_test_data()
        
        # Test 1: Create product categories
        print("Test 1: Creating product categories...")
        
        mushroom_id = create_product_category(
            category_name="Test Category Mushrooms",
            category_type="mushroom",
            category_desc="Various mushroom species for cultivation"
        )
        
        substrate_id = create_product_category(
            category_name="Test Category Substrate",
            category_type="substrate",
            category_desc="Growing mediums and substrates"
        )
        
        equipment_id = create_product_category(
            category_name="Test Category Equipment",
            category_type="equipment",
            category_desc="Farm equipment and tools"
        )
        
        print(f"Created categories with IDs: {mushroom_id}, {substrate_id}, {equipment_id}")
        assert mushroom_id > 0, "Failed to create mushroom category"
        assert substrate_id > 0, "Failed to create substrate category"
        assert equipment_id > 0, "Failed to create equipment category"
        
        # Test 2: Get specific product category
        print("Test 2: Getting specific product category...")
        
        mushroom_category = get_product_category(mushroom_id)
        assert mushroom_category is not None, "Failed to retrieve mushroom category"
        assert mushroom_category['category_name'] == "Test Category Mushrooms"
        assert mushroom_category['category_type'] == "mushroom"
        assert mushroom_category['active'] == 1
        print(f"Retrieved category: {mushroom_category['category_name']}")
        
        # Test 3: Get all product categories
        print("Test 3: Getting all product categories...")
        
        all_categories = get_all_product_categories()
        test_categories = [cat for cat in all_categories if cat['category_name'].startswith('Test Category')]
        assert len(test_categories) == 3, f"Expected 3 test categories, got {len(test_categories)}"
        print(f"Found {len(test_categories)} test categories")
        
        # Test 4: Get categories by name (partial match)
        print("Test 4: Getting categories by name...")
        
        mushroom_categories = get_product_categories_by_name("Mushroom")
        test_mushroom_categories = [cat for cat in mushroom_categories if cat['category_name'].startswith('Test Category')]
        assert len(test_mushroom_categories) == 1, f"Expected 1 mushroom category, got {len(test_mushroom_categories)}"
        print(f"Found {len(test_mushroom_categories)} mushroom categories")
        
        # Test 5: Get categories by type
        print("Test 5: Getting categories by type...")
        
        substrate_categories = get_product_categories_by_type("substrate")
        test_substrate_categories = [cat for cat in substrate_categories if cat['category_name'].startswith('Test Category')]
        assert len(test_substrate_categories) == 1, f"Expected 1 substrate category, got {len(test_substrate_categories)}"
        print(f"Found {len(test_substrate_categories)} substrate categories")
        
        # Test 6: Update product category
        print("Test 6: Updating product category...")
        
        rows_affected = update_product_category(
            mushroom_id,
            category_name="Test Category Updated Mushrooms",
            category_desc="Updated description for mushrooms"
        )
        assert rows_affected == 1, f"Expected 1 row affected, got {rows_affected}"
        
        updated_category = get_product_category(mushroom_id)
        assert updated_category['category_name'] == "Test Category Updated Mushrooms"
        assert updated_category['category_desc'] == "Updated description for mushrooms"
        print("Successfully updated category")
        
        # Test 7: Test usage count (should be 0 since no cost_of_goods records reference it)
        print("Test 7: Testing usage count...")
        
        usage_count = get_category_usage_count(mushroom_id)
        assert usage_count == 0, f"Expected 0 usage count, got {usage_count}"
        
        can_delete = can_delete_category(mushroom_id)
        assert can_delete == True, "Category should be deletable when not in use"
        print(f"Category usage count: {usage_count}, can delete: {can_delete}")
        
        # Test 8: Deactivate category (soft delete)
        print("Test 8: Deactivating category...")
        
        rows_affected = deactivate_product_category(substrate_id)
        assert rows_affected == 1, f"Expected 1 row affected, got {rows_affected}"
        
        deactivated_category = get_product_category(substrate_id)
        assert deactivated_category['active'] == 0, "Category should be deactivated"
        
        # Check that deactivated categories don't appear in active-only queries
        active_categories = get_all_product_categories(active_only=True)
        test_active_categories = [cat for cat in active_categories if cat['category_name'].startswith('Test Category')]
        assert len(test_active_categories) == 2, f"Expected 2 active test categories, got {len(test_active_categories)}"
        print("Successfully deactivated category")
        
        # Test 9: Delete category (hard delete)
        print("Test 9: Deleting category...")
        
        rows_affected = delete_product_category(equipment_id)
        assert rows_affected == 1, f"Expected 1 row affected, got {rows_affected}"
        
        deleted_category = get_product_category(equipment_id)
        assert deleted_category is None, "Deleted category should not be retrievable"
        print("Successfully deleted category")
        
        # Test 10: Edge cases
        print("Test 10: Testing edge cases...")
        
        # Try to get non-existent category
        non_existent = get_product_category(99999)
        assert non_existent is None, "Non-existent category should return None"
        
        # Try to update non-existent category
        rows_affected = update_product_category(99999, category_name="Non-existent")
        assert rows_affected == 0, "Updating non-existent category should affect 0 rows"
        
        # Try to delete non-existent category
        rows_affected = delete_product_category(99999)
        assert rows_affected == 0, "Deleting non-existent category should affect 0 rows"
        
        print("Edge cases handled correctly")
        
        print("✅ All product_categories CRUD tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        raise
    finally:
        # Clean up test data
        clean_test_data()

if __name__ == "__main__":
    test_product_categories_crud()
