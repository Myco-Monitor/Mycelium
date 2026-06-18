"""
Tests for the farms table module.

This module contains tests for the farms table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.farms import (
    create_farm, get_farm, get_all_farms, 
    update_farm, deactivate_farm, reactivate_farm, delete_farm
)
from storage.db_utils import get_connection, execute_query, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    # Use the existing delete_farm function to hard delete test farms
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Find all test farms
        cursor.execute("SELECT farm_id FROM farms WHERE farm_name LIKE 'Test Farm%'")
        test_farm_ids = [row['farm_id'] for row in cursor.fetchall()]
        
        # Delete each test farm using the hard delete function
        for farm_id in test_farm_ids:
            delete_farm(farm_id)
            
    finally:
        conn.close()

def test_farms_crud():
    """Test CRUD operations for the farms table."""
    print("\nTesting farms table CRUD operations...")
    
    # No need to store original_get_connection since we're not patching it anymore
    try:
        # Clean up any existing test data
        clean_test_data()
        
        # Now run the tests
        
        # 1. Test create_farm
        print("Testing create_farm...")
        farm1_id = create_farm("Test Farm 1", "Location 1", "Description 1")
        farm2_id = create_farm("Test Farm 2", "Location 2", "Description 2")
        farm3_id = create_farm("Test Farm 3")  # Minimal fields
        
        # IDs might not be 1, 2, 3 in the real database, so just check they're valid
        assert farm1_id > 0, f"Expected farm1_id to be positive, got {farm1_id}"
        assert farm2_id > 0, f"Expected farm2_id to be positive, got {farm2_id}"
        assert farm3_id > 0, f"Expected farm3_id to be positive, got {farm3_id}"
        
        # 2. Test get_farm
        print("Testing get_farm...")
        farm1 = get_farm(farm1_id)
        assert farm1 is not None, "Failed to retrieve farm1"
        assert farm1['farm_name'] == "Test Farm 1", f"Expected farm_name 'Test Farm 1', got '{farm1['farm_name']}'"
        assert farm1['farm_loc'] == "Location 1", f"Expected farm_loc 'Location 1', got '{farm1['farm_loc']}'"
        assert farm1['farm_desc'] == "Description 1", f"Expected farm_desc 'Description 1', got '{farm1['farm_desc']}'"
        assert farm1['active'] == 1, f"Expected active 1, got {farm1['active']}"
        
        farm3 = get_farm(farm3_id)
        assert farm3 is not None, "Failed to retrieve farm3"
        assert farm3['farm_name'] == "Test Farm 3", f"Expected farm_name 'Test Farm 3', got '{farm3['farm_name']}'"
        assert farm3['farm_loc'] is None, f"Expected farm_loc None, got '{farm3['farm_loc']}'"
        assert farm3['farm_desc'] is None, f"Expected farm_desc None, got '{farm3['farm_desc']}'"
        
        # 3. Test get_all_farms
        print("Testing get_all_farms...")
        all_farms = get_all_farms()
        # Count only our test farms instead of assuming total count
        test_farms_count = sum(1 for farm in all_farms if farm['farm_name'].startswith('Test Farm'))
        assert test_farms_count == 3, f"Expected 3 test farms, got {test_farms_count}"
        
        # 4. Test update_farm
        print("Testing update_farm...")
        rows_updated = update_farm(farm1_id, farm_name="Updated Farm 1", farm_desc="Updated Description")
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_farm = get_farm(farm1_id)
        assert updated_farm['farm_name'] == "Updated Farm 1", f"Expected farm_name 'Updated Farm 1', got '{updated_farm['farm_name']}'"
        assert updated_farm['farm_loc'] == "Location 1", f"Expected farm_loc unchanged, got '{updated_farm['farm_loc']}'"
        assert updated_farm['farm_desc'] == "Updated Description", f"Expected farm_desc 'Updated Description', got '{updated_farm['farm_desc']}'"
        
        # 5. Test deactivate_farm
        print("Testing deactivate_farm...")
        rows_deactivated = deactivate_farm(farm2_id, "Test deactivation")
        assert rows_deactivated == 1, f"Expected 1 row deactivated, got {rows_deactivated}"
        
        deactivated_farm = get_farm(farm2_id)
        assert deactivated_farm['active'] == 0, f"Expected active 0, got {deactivated_farm['active']}"
        assert deactivated_farm['deactivation_reason'] == "Test deactivation", f"Expected deactivation_reason 'Test deactivation', got '{deactivated_farm['deactivation_reason']}'"
        
        # 6. Test get_all_farms with active_only
        print("Testing get_all_farms with active_only...")
        active_farms = get_all_farms(active_only=True)
        
        # Check if farm1 (now Updated Farm 1) is in active farms
        farm1_active = any(farm['farm_id'] == farm1_id for farm in active_farms)
        assert farm1_active, f"Farm1 (ID: {farm1_id}) should be active"
        
        # Check if farm3 is in active farms
        farm3_active = any(farm['farm_id'] == farm3_id for farm in active_farms)
        assert farm3_active, f"Farm3 (ID: {farm3_id}) should be active"
        
        # Check if farm2 is NOT in active farms (it was deactivated)
        farm2_active = any(farm['farm_id'] == farm2_id for farm in active_farms)
        assert not farm2_active, f"Farm2 (ID: {farm2_id}) should NOT be active"
        
        all_farms_including_inactive = get_all_farms(active_only=False)
        
        # Check if all three farms are in the results when including inactive
        farm1_exists = any(farm['farm_id'] == farm1_id for farm in all_farms_including_inactive)
        assert farm1_exists, f"Farm1 (ID: {farm1_id}) should exist in all farms"
        
        farm2_exists = any(farm['farm_id'] == farm2_id for farm in all_farms_including_inactive)
        assert farm2_exists, f"Farm2 (ID: {farm2_id}) should exist in all farms"
        
        farm3_exists = any(farm['farm_id'] == farm3_id for farm in all_farms_including_inactive)
        assert farm3_exists, f"Farm3 (ID: {farm3_id}) should exist in all farms"
        
        # 7. Test reactivate_farm
        print("Testing reactivate_farm...")
        rows_reactivated = reactivate_farm(farm2_id)
        assert rows_reactivated == 1, f"Expected 1 row reactivated, got {rows_reactivated}"
        
        reactivated_farm = get_farm(farm2_id)
        assert reactivated_farm['active'] == 1, f"Expected active 1, got {reactivated_farm['active']}"
        assert reactivated_farm['deactivation_reason'] is None, f"Expected deactivation_reason None, got '{reactivated_farm['deactivation_reason']}'"
        
        # 8. Test delete_farm
        print("Testing delete_farm...")
        rows_deleted = delete_farm(farm2_id)
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_farm = get_farm(farm2_id)
        assert deleted_farm is None, f"Expected None for deleted farm, got {deleted_farm}"
        
        remaining_farms = get_all_farms(active_only=False)
        
        # Check that farm1 and farm3 still exist
        farm1_exists = any(farm['farm_id'] == farm1_id for farm in remaining_farms)
        assert farm1_exists, f"Farm1 (ID: {farm1_id}) should still exist"
        
        farm3_exists = any(farm['farm_id'] == farm3_id for farm in remaining_farms)
        assert farm3_exists, f"Farm3 (ID: {farm3_id}) should still exist"
        
        # Check that farm2 no longer exists (it was deleted)
        farm2_exists = any(farm['farm_id'] == farm2_id for farm in remaining_farms)
        assert not farm2_exists, f"Farm2 (ID: {farm2_id}) should have been deleted"
        
        print("All farms table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in farms table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # No need to restore get_connection since we're using the actual one
        pass

if __name__ == "__main__":
    test_farms_crud()
