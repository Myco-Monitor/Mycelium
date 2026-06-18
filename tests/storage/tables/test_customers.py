"""
Tests for the customers table module.

This module contains tests for the customers table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.customers import (
    create_customer, get_customer, get_all_customers, get_customers_by_farm,
    get_customers_by_type, search_customers, update_customer,
    deactivate_customer, reactivate_customer, delete_customer
)
from storage.tables.farms import create_farm
from storage.db_utils import get_connection, execute_query, get_timestamp, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test customer records that might exist from previous test runs
        cursor.execute("DELETE FROM customers WHERE customer_name LIKE 'Test Customer%'")
        cursor.execute("DELETE FROM farms WHERE farm_name LIKE 'Test Customer%'")
        conn.commit()
    finally:
        conn.close()

def test_customers_crud():
    """Test CRUD operations for the customers table."""
    print("\nTesting customers table CRUD operations...")
    
    try:
        # Clean up any existing test data
        clean_test_data()
        
        # Create test farm records first
        print("Creating test farm records...")
        farm_id1 = create_farm(
            farm_name="Test Customer Farm 1",
            farm_loc="Test Location 1",
            farm_desc="Test Farm 1 Description"
        )
        
        farm_id2 = create_farm(
            farm_name="Test Customer Farm 2",
            farm_loc="Test Location 2",
            farm_desc="Test Farm 2 Description"
        )
        
        # Now run the tests
        
        # 1. Test create_customer
        print("Testing create_customer...")
        customer_id1 = create_customer(
            customer_name="Test Customer 1",
            farm_id=farm_id1,
            customer_info="Test Info 1",
            customer_type="Retail",
            notes="Test notes 1"
        )
        
        customer_id2 = create_customer(
            customer_name="Test Customer 2",
            farm_id=farm_id1,
            customer_info="Test Info 2",
            customer_type="Wholesale",
            notes="Test notes 2"
        )
        
        customer_id3 = create_customer(
            customer_name="Test Customer 3",
            farm_id=farm_id2,
            customer_info="Test Info 3",
            customer_type="Retail",
            notes="Test notes 3"
        )
        
        assert customer_id1 > 0, f"Expected positive customer_id, got {customer_id1}"
        assert customer_id2 > 0, f"Expected positive customer_id, got {customer_id2}"
        assert customer_id3 > 0, f"Expected positive customer_id, got {customer_id3}"
        
        # 2. Test get_customer
        print("Testing get_customer...")
        customer1 = get_customer(customer_id1)
        assert customer1 is not None, "Failed to retrieve customer1"
        assert customer1['customer_name'] == "Test Customer 1", f"Expected customer_name 'Test Customer 1', got '{customer1['customer_name']}'"
        assert customer1['farm_id'] == farm_id1, f"Expected farm_id {farm_id1}, got {customer1['farm_id']}"
        assert customer1['customer_info'] == "Test Info 1", f"Expected customer_info 'Test Info 1', got '{customer1['customer_info']}'"
        assert customer1['customer_type'] == "Retail", f"Expected customer_type 'Retail', got '{customer1['customer_type']}'"
        assert customer1['notes'] == "Test notes 1", f"Expected notes 'Test notes 1', got '{customer1['notes']}'"
        assert customer1['active'] == 1, f"Expected active 1, got {customer1['active']}"
        
        # 3. Test get_all_customers
        print("Testing get_all_customers...")
        all_customers = get_all_customers()
        assert len(all_customers) >= 3, f"Expected at least 3 customer records, got {len(all_customers)}"
        
        # 4. Test get_customers_by_farm
        print("Testing get_customers_by_farm...")
        farm1_customers = get_customers_by_farm(farm_id1)
        assert len(farm1_customers) == 2, f"Expected 2 customer records for farm1, got {len(farm1_customers)}"
        
        farm2_customers = get_customers_by_farm(farm_id2)
        assert len(farm2_customers) == 1, f"Expected 1 customer record for farm2, got {len(farm2_customers)}"
        
        # 5. Test get_customers_by_type
        print("Testing get_customers_by_type...")
        retail_customers = get_customers_by_type("Retail")
        assert len(retail_customers) == 2, f"Expected 2 retail customer records, got {len(retail_customers)}"
        
        wholesale_customers = get_customers_by_type("Wholesale")
        assert len(wholesale_customers) == 1, f"Expected 1 wholesale customer record, got {len(wholesale_customers)}"
        
        # 6. Test search_customers
        print("Testing search_customers...")
        search_results1 = search_customers("Customer 1")
        assert len(search_results1) == 1, f"Expected 1 customer record for search 'Customer 1', got {len(search_results1)}"
        
        search_results2 = search_customers("Test Info")
        assert len(search_results2) == 3, f"Expected 3 customer records for search 'Test Info', got {len(search_results2)}"
        
        # 7. Test update_customer
        print("Testing update_customer...")
        rows_updated = update_customer(
            customer_id1,
            customer_name="Updated Test Customer 1",
            customer_info="Updated Test Info 1",
            notes="Updated test notes 1"
        )
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_customer = get_customer(customer_id1)
        assert updated_customer['customer_name'] == "Updated Test Customer 1", f"Expected customer_name 'Updated Test Customer 1', got '{updated_customer['customer_name']}'"
        assert updated_customer['customer_info'] == "Updated Test Info 1", f"Expected customer_info 'Updated Test Info 1', got '{updated_customer['customer_info']}'"
        assert updated_customer['notes'] == "Updated test notes 1", f"Expected notes 'Updated test notes 1', got '{updated_customer['notes']}'"
        assert updated_customer['farm_id'] == farm_id1, f"Expected farm_id unchanged at {farm_id1}, got {updated_customer['farm_id']}"
        assert updated_customer['customer_type'] == "Retail", f"Expected customer_type unchanged at 'Retail', got '{updated_customer['customer_type']}'"
        
        # 8. Test deactivate_customer
        print("Testing deactivate_customer...")
        rows_deactivated = deactivate_customer(customer_id2, "Test deactivation reason")
        assert rows_deactivated == 1, f"Expected 1 row deactivated, got {rows_deactivated}"
        
        deactivated_customer = get_customer(customer_id2)
        assert deactivated_customer is None, f"Expected None for deactivated customer when using get_customer, got {deactivated_customer}"
        
        deactivated_customer_with_inactive = get_customer(customer_id2, include_inactive=True)
        assert deactivated_customer_with_inactive is not None, "Failed to retrieve deactivated customer with include_inactive=True"
        assert deactivated_customer_with_inactive['active'] == 0, f"Expected active 0, got {deactivated_customer_with_inactive['active']}"
        assert deactivated_customer_with_inactive['deactivation_reason'] == "Test deactivation reason", f"Expected deactivation_reason 'Test deactivation reason', got '{deactivated_customer_with_inactive['deactivation_reason']}'"
        
        # Check if we can still get the deactivated record when including inactive
        all_customers_with_inactive = get_all_customers(include_inactive=True)
        assert len(all_customers_with_inactive) >= 3, f"Expected at least 3 customer records with inactive, got {len(all_customers_with_inactive)}"
        
        all_customers_active_only = get_all_customers(include_inactive=False)
        assert len(all_customers_active_only) == len(all_customers_with_inactive) - 1, f"Expected one less active record than total records"
        
        # 9. Test reactivate_customer
        print("Testing reactivate_customer...")
        rows_reactivated = reactivate_customer(customer_id2)
        assert rows_reactivated == 1, f"Expected 1 row reactivated, got {rows_reactivated}"
        
        reactivated_customer = get_customer(customer_id2)
        assert reactivated_customer is not None, "Failed to retrieve reactivated customer"
        assert reactivated_customer['active'] == 1, f"Expected active 1, got {reactivated_customer['active']}"
        assert reactivated_customer['deactivation_reason'] is None, f"Expected deactivation_reason None, got '{reactivated_customer['deactivation_reason']}'"
        
        # 10. Test delete_customer
        print("Testing delete_customer...")
        rows_deleted = delete_customer(customer_id3)
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_customer = get_customer(customer_id3, include_inactive=True)
        assert deleted_customer is None, f"Expected None for deleted customer, got {deleted_customer}"
        
        # Check if the deleted record is really gone
        all_customers_after_delete = get_all_customers(include_inactive=True)
        assert len(all_customers_after_delete) == len(all_customers_with_inactive) - 1, f"Expected one less record after delete"
        
        print("All customers table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in customers table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up test data
        clean_test_data()

if __name__ == "__main__":
    test_customers_crud()
