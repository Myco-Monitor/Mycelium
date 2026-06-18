"""
Tests for the labour table module.

This module contains tests for the labour table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.labour import (
    create_labour, get_labour, get_all_labour, get_labour_by_employee,
    get_labour_by_task_type, get_labour_by_date_range, get_labour_by_employee_and_date_range,
    calculate_total_hours_by_employee, calculate_total_hours_by_task_type,
    update_labour, delete_labour
)
from storage.tables.employees import create_employee
from storage.tables.farms import create_farm
from storage.db_utils import get_connection, execute_query, get_timestamp, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test labour records that might exist from previous test runs
        cursor.execute("DELETE FROM labour WHERE emp_id IN (SELECT emp_id FROM employees WHERE emp_name LIKE 'Test Labour%')")
        cursor.execute("DELETE FROM employees WHERE emp_name LIKE 'Test Labour%'")
        cursor.execute("DELETE FROM farms WHERE farm_name LIKE 'Test Labour%'")
        conn.commit()
    finally:
        conn.close()

def test_labour_crud():
    """Test CRUD operations for the labour table."""
    print("\nTesting labour table CRUD operations...")
    
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
        
        # Create test farm and employee records first
        print("Creating test farm and employee records...")
        farm_id = create_farm(
            farm_name="Test Labour Farm",
            farm_loc="Test Location",
            farm_desc="Test Farm Description"
        )
        
        emp_id1 = create_employee(
            emp_name="Test Labour Employee 1",
            farm_id=farm_id,
            emp_role="Manager",
            emp_rate=25.0,
            emp_contact="test1@example.com",
            emp_start=yesterday_str
        )
        
        emp_id2 = create_employee(
            emp_name="Test Labour Employee 2",
            farm_id=farm_id,
            emp_role="Worker",
            emp_rate=18.0,
            emp_contact="test2@example.com"
        )
        
        # Now run the tests
        
        # 1. Test create_labour
        print("Testing create_labour...")
        labour_id1 = create_labour(
            emp_id=emp_id1,
            task_type="Harvesting",
            work_date=yesterday_str,
            hours_worked=8.0,
            notes="Test labour record 1"
        )
        
        labour_id2 = create_labour(
            emp_id=emp_id1,
            task_type="Packaging",
            work_date=now_str,
            hours_worked=4.0,
            notes="Test labour record 2"
        )
        
        labour_id3 = create_labour(
            emp_id=emp_id2,
            task_type="Harvesting",
            work_date=two_days_ago_str,
            hours_worked=6.0,
            notes="Test labour record 3"
        )
        
        assert labour_id1 > 0, f"Expected positive labour_id, got {labour_id1}"
        assert labour_id2 > 0, f"Expected positive labour_id, got {labour_id2}"
        assert labour_id3 > 0, f"Expected positive labour_id, got {labour_id3}"
        
        # 2. Test get_labour
        print("Testing get_labour...")
        labour1 = get_labour(labour_id1)
        assert labour1 is not None, "Failed to retrieve labour1"
        assert labour1['emp_id'] == emp_id1, f"Expected emp_id {emp_id1}, got {labour1['emp_id']}"
        assert labour1['task_type'] == "Harvesting", f"Expected task_type 'Harvesting', got '{labour1['task_type']}'"
        assert labour1['work_date'] == yesterday_str, f"Expected work_date '{yesterday_str}', got '{labour1['work_date']}'"
        assert labour1['hours_worked'] == 8.0, f"Expected hours_worked 8.0, got {labour1['hours_worked']}"
        assert labour1['notes'] == "Test labour record 1", f"Expected notes 'Test labour record 1', got '{labour1['notes']}'"
        
        # 3. Test get_all_labour
        print("Testing get_all_labour...")
        all_labour = get_all_labour()
        assert len(all_labour) >= 3, f"Expected at least 3 labour records, got {len(all_labour)}"
        
        # 4. Test get_labour_by_employee
        print("Testing get_labour_by_employee...")
        emp1_labour = get_labour_by_employee(emp_id1)
        assert len(emp1_labour) == 2, f"Expected 2 labour records for emp1, got {len(emp1_labour)}"
        
        emp2_labour = get_labour_by_employee(emp_id2)
        assert len(emp2_labour) == 1, f"Expected 1 labour record for emp2, got {len(emp2_labour)}"
        
        # 5. Test get_labour_by_task_type
        print("Testing get_labour_by_task_type...")
        harvesting_labour = get_labour_by_task_type("Harvesting")
        assert len(harvesting_labour) == 2, f"Expected 2 harvesting labour records, got {len(harvesting_labour)}"
        
        packaging_labour = get_labour_by_task_type("Packaging")
        assert len(packaging_labour) == 1, f"Expected 1 packaging labour record, got {len(packaging_labour)}"
        
        # 6. Test get_labour_by_date_range
        print("Testing get_labour_by_date_range...")
        date_range_labour = get_labour_by_date_range(two_days_ago_str, now_str)
        assert len(date_range_labour) == 3, f"Expected 3 labour records in date range, got {len(date_range_labour)}"
        
        yesterday_to_now_labour = get_labour_by_date_range(yesterday_str, now_str)
        assert len(yesterday_to_now_labour) == 2, f"Expected 2 labour records from yesterday to now, got {len(yesterday_to_now_labour)}"
        
        # 7. Test get_labour_by_employee_and_date_range
        print("Testing get_labour_by_employee_and_date_range...")
        emp1_date_range_labour = get_labour_by_employee_and_date_range(emp_id1, yesterday_str, now_str)
        assert len(emp1_date_range_labour) == 2, f"Expected 2 labour records for emp1 in date range, got {len(emp1_date_range_labour)}"
        
        emp2_date_range_labour = get_labour_by_employee_and_date_range(emp_id2, yesterday_str, now_str)
        assert len(emp2_date_range_labour) == 0, f"Expected 0 labour records for emp2 in date range, got {len(emp2_date_range_labour)}"
        
        # 8. Test calculate_total_hours_by_employee
        print("Testing calculate_total_hours_by_employee...")
        emp1_total_hours = calculate_total_hours_by_employee(emp_id1)
        assert emp1_total_hours == 12.0, f"Expected 12.0 total hours for emp1, got {emp1_total_hours}"
        
        emp2_total_hours = calculate_total_hours_by_employee(emp_id2)
        assert emp2_total_hours == 6.0, f"Expected 6.0 total hours for emp2, got {emp2_total_hours}"
        
        emp1_date_range_hours = calculate_total_hours_by_employee(emp_id1, yesterday_str, now_str)
        assert emp1_date_range_hours == 12.0, f"Expected 12.0 hours for emp1 in date range, got {emp1_date_range_hours}"
        
        # 9. Test calculate_total_hours_by_task_type
        print("Testing calculate_total_hours_by_task_type...")
        harvesting_total_hours = calculate_total_hours_by_task_type("Harvesting")
        assert harvesting_total_hours == 14.0, f"Expected 14.0 total hours for harvesting, got {harvesting_total_hours}"
        
        packaging_total_hours = calculate_total_hours_by_task_type("Packaging")
        assert packaging_total_hours == 4.0, f"Expected 4.0 total hours for packaging, got {packaging_total_hours}"
        
        harvesting_date_range_hours = calculate_total_hours_by_task_type("Harvesting", yesterday_str, now_str)
        assert harvesting_date_range_hours == 8.0, f"Expected 8.0 hours for harvesting in date range, got {harvesting_date_range_hours}"
        
        # 10. Test update_labour
        print("Testing update_labour...")
        rows_updated = update_labour(
            labour_id1,
            task_type="Harvesting and Cleaning",
            hours_worked=9.0,
            notes="Updated test labour record 1"
        )
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_labour = get_labour(labour_id1)
        assert updated_labour['task_type'] == "Harvesting and Cleaning", f"Expected task_type 'Harvesting and Cleaning', got '{updated_labour['task_type']}'"
        assert updated_labour['hours_worked'] == 9.0, f"Expected hours_worked 9.0, got {updated_labour['hours_worked']}"
        assert updated_labour['notes'] == "Updated test labour record 1", f"Expected notes 'Updated test labour record 1', got '{updated_labour['notes']}'"
        assert updated_labour['work_date'] == yesterday_str, f"Expected work_date unchanged at '{yesterday_str}', got '{updated_labour['work_date']}'"
        
        # 11. Test delete_labour
        print("Testing delete_labour...")
        rows_deleted = delete_labour(labour_id3)
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_labour = get_labour(labour_id3)
        assert deleted_labour is None, f"Expected None for deleted labour, got {deleted_labour}"
        
        # Check if the deleted record is really gone
        all_labour_after_delete = get_all_labour()
        assert len(all_labour_after_delete) == len(all_labour) - 1, f"Expected one less record after delete"
        
        # Recalculate totals after update and delete
        new_emp1_total_hours = calculate_total_hours_by_employee(emp_id1)
        assert new_emp1_total_hours == 13.0, f"Expected 13.0 total hours for emp1 after update, got {new_emp1_total_hours}"
        
        new_harvesting_total_hours = calculate_total_hours_by_task_type("Harvesting and Cleaning")
        assert new_harvesting_total_hours == 9.0, f"Expected 9.0 total hours for 'Harvesting and Cleaning', got {new_harvesting_total_hours}"
        
        print("All labour table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in labour table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up test data
        clean_test_data()

if __name__ == "__main__":
    test_labour_crud()
