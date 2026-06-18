"""
Tests for the employees table module.

This module contains tests for the employees table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.employees import (
    create_employee, get_employee, get_all_employees, get_employees_by_farm,
    get_employees_by_role, search_employees, update_employee,
    deactivate_employee, reactivate_employee, delete_employee
)
from storage.tables.farms import create_farm
from storage.db_utils import get_connection, execute_query, get_timestamp, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test employee records that might exist from previous test runs
        cursor.execute("DELETE FROM employees WHERE emp_name LIKE 'Test Employee%'")
        cursor.execute("DELETE FROM farms WHERE farm_name LIKE 'Test Employee%'")
        conn.commit()
    finally:
        conn.close()

def test_employees_crud():
    """Test CRUD operations for the employees table."""
    print("\nTesting employees table CRUD operations...")
    
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
        
        # Create test farm records first
        print("Creating test farm records...")
        farm_id1 = create_farm(
            farm_name="Test Employee Farm 1",
            farm_loc="Test Location 1",
            farm_desc="Test Farm 1 Description"
        )
        
        farm_id2 = create_farm(
            farm_name="Test Employee Farm 2",
            farm_loc="Test Location 2",
            farm_desc="Test Farm 2 Description"
        )
        
        # Now run the tests
        
        # 1. Test create_employee
        print("Testing create_employee...")
        emp_id1 = create_employee(
            emp_name="Test Employee 1",
            farm_id=farm_id1,
            emp_role="Manager",
            emp_rate=25.0,
            emp_contact="test1@example.com",
            emp_start=yesterday_str
        )
        
        emp_id2 = create_employee(
            emp_name="Test Employee 2",
            farm_id=farm_id1,
            emp_role="Worker",
            emp_rate=18.0,
            emp_contact="test2@example.com"
        )
        
        emp_id3 = create_employee(
            emp_name="Test Employee 3",
            farm_id=farm_id2,
            emp_role="Manager",
            emp_rate=22.0,
            emp_contact="test3@example.com",
            emp_start=now_str
        )
        
        assert emp_id1 > 0, f"Expected positive emp_id, got {emp_id1}"
        assert emp_id2 > 0, f"Expected positive emp_id, got {emp_id2}"
        assert emp_id3 > 0, f"Expected positive emp_id, got {emp_id3}"
        
        # 2. Test get_employee
        print("Testing get_employee...")
        emp1 = get_employee(emp_id1)
        assert emp1 is not None, "Failed to retrieve emp1"
        assert emp1['emp_name'] == "Test Employee 1", f"Expected emp_name 'Test Employee 1', got '{emp1['emp_name']}'"
        assert emp1['farm_id'] == farm_id1, f"Expected farm_id {farm_id1}, got {emp1['farm_id']}"
        assert emp1['emp_role'] == "Manager", f"Expected emp_role 'Manager', got '{emp1['emp_role']}'"
        assert emp1['emp_rate'] == 25.0, f"Expected emp_rate 25.0, got {emp1['emp_rate']}"
        assert emp1['emp_contact'] == "test1@example.com", f"Expected emp_contact 'test1@example.com', got '{emp1['emp_contact']}'"
        assert emp1['emp_start'] == yesterday_str, f"Expected emp_start '{yesterday_str}', got '{emp1['emp_start']}'"
        assert emp1['active'] == 1, f"Expected active 1, got {emp1['active']}"
        
        # 3. Test get_all_employees
        print("Testing get_all_employees...")
        all_employees = get_all_employees()
        assert len(all_employees) >= 3, f"Expected at least 3 employee records, got {len(all_employees)}"
        
        # 4. Test get_employees_by_farm
        print("Testing get_employees_by_farm...")
        farm1_employees = get_employees_by_farm(farm_id1)
        assert len(farm1_employees) == 2, f"Expected 2 employee records for farm1, got {len(farm1_employees)}"
        
        farm2_employees = get_employees_by_farm(farm_id2)
        assert len(farm2_employees) == 1, f"Expected 1 employee record for farm2, got {len(farm2_employees)}"
        
        # 5. Test get_employees_by_role
        print("Testing get_employees_by_role...")
        manager_employees = get_employees_by_role("Manager")
        assert len(manager_employees) == 2, f"Expected 2 manager employee records, got {len(manager_employees)}"
        
        worker_employees = get_employees_by_role("Worker")
        assert len(worker_employees) == 1, f"Expected 1 worker employee record, got {len(worker_employees)}"
        
        # 6. Test search_employees
        print("Testing search_employees...")
        search_results1 = search_employees("Employee 1")
        assert len(search_results1) == 1, f"Expected 1 employee record for search 'Employee 1', got {len(search_results1)}"
        
        search_results2 = search_employees("@example.com")
        assert len(search_results2) == 3, f"Expected 3 employee records for search '@example.com', got {len(search_results2)}"
        
        # 7. Test update_employee
        print("Testing update_employee...")
        rows_updated = update_employee(
            emp_id1,
            emp_name="Updated Test Employee 1",
            emp_rate=26.0,
            emp_contact="updated1@example.com"
        )
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_employee = get_employee(emp_id1)
        assert updated_employee['emp_name'] == "Updated Test Employee 1", f"Expected emp_name 'Updated Test Employee 1', got '{updated_employee['emp_name']}'"
        assert updated_employee['emp_rate'] == 26.0, f"Expected emp_rate 26.0, got {updated_employee['emp_rate']}"
        assert updated_employee['emp_contact'] == "updated1@example.com", f"Expected emp_contact 'updated1@example.com', got '{updated_employee['emp_contact']}'"
        assert updated_employee['farm_id'] == farm_id1, f"Expected farm_id unchanged at {farm_id1}, got {updated_employee['farm_id']}"
        assert updated_employee['emp_role'] == "Manager", f"Expected emp_role unchanged at 'Manager', got '{updated_employee['emp_role']}'"
        
        # 8. Test deactivate_employee
        print("Testing deactivate_employee...")
        rows_deactivated = deactivate_employee(emp_id2, "Test deactivation reason")
        assert rows_deactivated == 1, f"Expected 1 row deactivated, got {rows_deactivated}"
        
        deactivated_employee = get_employee(emp_id2)
        assert deactivated_employee is None, f"Expected None for deactivated employee when using get_employee, got {deactivated_employee}"
        
        deactivated_employee_with_inactive = get_employee(emp_id2, include_inactive=True)
        assert deactivated_employee_with_inactive is not None, "Failed to retrieve deactivated employee with include_inactive=True"
        assert deactivated_employee_with_inactive['active'] == 0, f"Expected active 0, got {deactivated_employee_with_inactive['active']}"
        assert deactivated_employee_with_inactive['deactivation_reason'] == "Test deactivation reason", f"Expected deactivation_reason 'Test deactivation reason', got '{deactivated_employee_with_inactive['deactivation_reason']}'"
        
        # Check if we can still get the deactivated record when including inactive
        all_employees_with_inactive = get_all_employees(include_inactive=True)
        assert len(all_employees_with_inactive) >= 3, f"Expected at least 3 employee records with inactive, got {len(all_employees_with_inactive)}"
        
        all_employees_active_only = get_all_employees(include_inactive=False)
        assert len(all_employees_active_only) == len(all_employees_with_inactive) - 1, f"Expected one less active record than total records"
        
        # 9. Test reactivate_employee
        print("Testing reactivate_employee...")
        rows_reactivated = reactivate_employee(emp_id2)
        assert rows_reactivated == 1, f"Expected 1 row reactivated, got {rows_reactivated}"
        
        reactivated_employee = get_employee(emp_id2)
        assert reactivated_employee is not None, "Failed to retrieve reactivated employee"
        assert reactivated_employee['active'] == 1, f"Expected active 1, got {reactivated_employee['active']}"
        assert reactivated_employee['deactivation_reason'] is None, f"Expected deactivation_reason None, got '{reactivated_employee['deactivation_reason']}'"
        
        # 10. Test delete_employee
        print("Testing delete_employee...")
        rows_deleted = delete_employee(emp_id3)
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_employee = get_employee(emp_id3, include_inactive=True)
        assert deleted_employee is None, f"Expected None for deleted employee, got {deleted_employee}"
        
        # Check if the deleted record is really gone
        all_employees_after_delete = get_all_employees(include_inactive=True)
        assert len(all_employees_after_delete) == len(all_employees_with_inactive) - 1, f"Expected one less record after delete"
        
        print("All employees table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in employees table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up test data
        clean_test_data()

if __name__ == "__main__":
    test_employees_crud()
