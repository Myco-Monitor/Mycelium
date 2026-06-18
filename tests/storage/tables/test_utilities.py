"""
Tests for the utilities table module.

This module contains tests for the utilities table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.utilities import (
    create_utility, get_utility, get_all_utilities, get_utilities_by_farm,
    get_utilities_by_room, get_utilities_by_name, get_utilities_by_date_range,
    get_unpaid_utilities, get_overdue_utilities, get_utilities_by_farm_and_date_range,
    calculate_total_cost_by_farm, calculate_total_cost_by_utility_name,
    update_utility, mark_utility_paid, delete_utility
)
from storage.db_utils import get_connection, execute_query, get_timestamp, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test utility records that might exist from previous test runs
        cursor.execute("DELETE FROM utilities WHERE util_name LIKE 'Test Utility%'")
        conn.commit()
    finally:
        conn.close()

def test_utilities_crud():
    """Test CRUD operations for the utilities table."""
    print("\nTesting utilities table CRUD operations...")
    
    try:
        # Clean up any existing test data
        clean_test_data()
        
        # Get current timestamp and timestamps for testing date ranges
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)
        next_week = now + timedelta(days=7)
        
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        yesterday_str = yesterday.strftime("%Y-%m-%d %H:%M:%S")
        tomorrow_str = tomorrow.strftime("%Y-%m-%d %H:%M:%S")
        next_week_str = next_week.strftime("%Y-%m-%d %H:%M:%S")
        
        # Test 1: Create utility records
        print("Test 1: Creating utility records...")
        
        # Create test farm first (assuming farm_id 1 exists or create it)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO farms (farm_id, farm_name) VALUES (1, 'Test Farm')")
        cursor.execute("INSERT OR IGNORE INTO grow_rooms (room_id, farm_id, room_name) VALUES (1, 1, 'Test Room')")
        conn.commit()
        conn.close()
        
        utility1_id = create_utility(
            util_name="Test Utility Electric",
            util_cost=150.75,
            util_recd=yesterday_str,
            util_dued=tomorrow_str,
            farm_id=1,
            util_note="Monthly electric bill"
        )
        
        utility2_id = create_utility(
            util_name="Test Utility Water",
            util_cost=89.50,
            util_recd=yesterday_str,
            util_dued=next_week_str,
            farm_id=1,
            room_id=1,
            util_note="Water bill for grow room"
        )
        
        utility3_id = create_utility(
            util_name="Test Utility Gas",
            util_cost=45.25,
            util_recd=now_str,
            util_dued=yesterday_str,  # Overdue
            farm_id=1,
            util_paid=now_str  # Already paid
        )
        
        print(f"Created utilities with IDs: {utility1_id}, {utility2_id}, {utility3_id}")
        
        # Test 2: Get specific utility
        print("Test 2: Getting specific utility...")
        utility = get_utility(utility1_id)
        assert utility is not None, "Should retrieve the utility record"
        assert utility['util_name'] == "Test Utility Electric", "Utility name should match"
        assert utility['util_cost'] == 150.75, "Utility cost should match"
        assert utility['farm_id'] == 1, "Farm ID should match"
        print("✓ Get specific utility passed")
        
        # Test 3: Get all utilities
        print("Test 3: Getting all utilities...")
        all_utilities = get_all_utilities()
        test_utilities = [u for u in all_utilities if u['util_name'].startswith('Test Utility')]
        assert len(test_utilities) >= 3, "Should have at least 3 test utilities"
        print("✓ Get all utilities passed")
        
        # Test 4: Get utilities by farm
        print("Test 4: Getting utilities by farm...")
        farm_utilities = get_utilities_by_farm(1)
        test_farm_utilities = [u for u in farm_utilities if u['util_name'].startswith('Test Utility')]
        assert len(test_farm_utilities) == 3, "Should have 3 test utilities for farm 1"
        print("✓ Get utilities by farm passed")
        
        # Test 5: Get utilities by room
        print("Test 5: Getting utilities by room...")
        room_utilities = get_utilities_by_room(1)
        test_room_utilities = [u for u in room_utilities if u['util_name'].startswith('Test Utility')]
        assert len(test_room_utilities) == 1, "Should have 1 test utility for room 1"
        assert test_room_utilities[0]['util_name'] == "Test Utility Water", "Should be the water utility"
        print("✓ Get utilities by room passed")
        
        # Test 6: Get utilities by name
        print("Test 6: Getting utilities by name...")
        electric_utilities = get_utilities_by_name("Electric")
        test_electric = [u for u in electric_utilities if u['util_name'].startswith('Test Utility')]
        assert len(test_electric) >= 1, "Should find electric utility"
        assert test_electric[0]['util_name'] == "Test Utility Electric", "Should find the electric utility"
        print("✓ Get utilities by name passed")
        
        # Test 7: Get utilities by date range
        print("Test 7: Getting utilities by date range...")
        date_range_utilities = get_utilities_by_date_range(yesterday_str, next_week_str, "due")
        test_date_utilities = [u for u in date_range_utilities if u['util_name'].startswith('Test Utility')]
        assert len(test_date_utilities) >= 2, "Should find utilities in date range"
        print("✓ Get utilities by date range passed")
        
        # Test 8: Get unpaid utilities
        print("Test 8: Getting unpaid utilities...")
        unpaid_utilities = get_unpaid_utilities()
        test_unpaid = [u for u in unpaid_utilities if u['util_name'].startswith('Test Utility')]
        assert len(test_unpaid) == 2, "Should have 2 unpaid test utilities"
        print("✓ Get unpaid utilities passed")
        
        # Test 9: Get overdue utilities
        print("Test 9: Getting overdue utilities...")
        overdue_utilities = get_overdue_utilities()
        test_overdue = [u for u in overdue_utilities if u['util_name'].startswith('Test Utility')]
        # Note: utility3 is paid so shouldn't be in overdue list
        assert len(test_overdue) == 0, "Should have 0 overdue test utilities (gas bill was paid)"
        print("✓ Get overdue utilities passed")
        
        # Test 10: Get utilities by farm and date range
        print("Test 10: Getting utilities by farm and date range...")
        farm_date_utilities = get_utilities_by_farm_and_date_range(1, yesterday_str, next_week_str, "due")
        test_farm_date = [u for u in farm_date_utilities if u['util_name'].startswith('Test Utility')]
        assert len(test_farm_date) >= 2, "Should find utilities for farm in date range"
        print("✓ Get utilities by farm and date range passed")
        
        # Test 11: Calculate total cost by farm
        print("Test 11: Calculating total cost by farm...")
        total_cost = calculate_total_cost_by_farm(1)
        expected_total = 150.75 + 89.50 + 45.25  # All three utilities
        assert abs(total_cost - expected_total) < 0.01, f"Total cost should be {expected_total}, got {total_cost}"
        
        # Test with paid_only=True
        paid_total = calculate_total_cost_by_farm(1, paid_only=True)
        assert abs(paid_total - 45.25) < 0.01, f"Paid total should be 45.25, got {paid_total}"
        print("✓ Calculate total cost by farm passed")
        
        # Test 12: Calculate total cost by utility name
        print("Test 12: Calculating total cost by utility name...")
        electric_total = calculate_total_cost_by_utility_name("Electric")
        assert abs(electric_total - 150.75) < 0.01, f"Electric total should be 150.75, got {electric_total}"
        print("✓ Calculate total cost by utility name passed")
        
        # Test 13: Update utility
        print("Test 13: Updating utility...")
        rows_affected = update_utility(
            utility1_id,
            util_cost=175.00,
            util_note="Updated electric bill"
        )
        assert rows_affected == 1, "Should update 1 row"
        
        updated_utility = get_utility(utility1_id)
        assert updated_utility['util_cost'] == 175.00, "Cost should be updated"
        assert updated_utility['util_note'] == "Updated electric bill", "Note should be updated"
        print("✓ Update utility passed")
        
        # Test 14: Mark utility as paid
        print("Test 14: Marking utility as paid...")
        rows_affected = mark_utility_paid(utility1_id)
        assert rows_affected == 1, "Should update 1 row"
        
        paid_utility = get_utility(utility1_id)
        assert paid_utility['util_paid'] is not None, "Utility should be marked as paid"
        print("✓ Mark utility as paid passed")
        
        # Test 15: Delete utility
        print("Test 15: Deleting utility...")
        rows_affected = delete_utility(utility3_id)
        assert rows_affected == 1, "Should delete 1 row"
        
        deleted_utility = get_utility(utility3_id)
        assert deleted_utility is None, "Utility should be deleted"
        print("✓ Delete utility passed")
        
        # Test 16: Edge cases
        print("Test 16: Testing edge cases...")
        
        # Test getting non-existent utility
        non_existent = get_utility(99999)
        assert non_existent is None, "Should return None for non-existent utility"
        
        # Test updating non-existent utility
        rows_affected = update_utility(99999, util_cost=100.0)
        assert rows_affected == 0, "Should not update non-existent utility"
        
        # Test deleting non-existent utility
        rows_affected = delete_utility(99999)
        assert rows_affected == 0, "Should not delete non-existent utility"
        
        print("✓ Edge cases passed")
        
        print("✅ All utilities table tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        raise
    finally:
        # Clean up test data
        clean_test_data()
        
        # Clean up test farm and room
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM grow_rooms WHERE room_id = 1 AND room_name = 'Test Room'")
            cursor.execute("DELETE FROM farms WHERE farm_id = 1 AND farm_name = 'Test Farm'")
            conn.commit()
        finally:
            conn.close()

if __name__ == "__main__":
    test_utilities_crud()
