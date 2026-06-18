"""
Tests for the sales_transaction table module.

This module contains tests for the sales_transaction table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.sales_transaction import (
    create_sales_transaction, get_sales_transaction, get_all_sales_transactions,
    get_sales_transactions_by_customer, get_sales_transactions_by_date_range,
    update_sales_transaction, update_sales_transaction_total,
    soft_delete_sales_transaction, delete_sales_transaction
)
from storage.tables.customers import create_customer
from storage.tables.farms import create_farm
from storage.db_utils import get_connection, execute_query, get_timestamp, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test sales_transaction records that might exist from previous test runs
        cursor.execute("DELETE FROM sales_transaction WHERE customer_id IN (SELECT customer_id FROM customers WHERE customer_name LIKE 'Test Sales%')")
        cursor.execute("DELETE FROM customers WHERE customer_name LIKE 'Test Sales%'")
        cursor.execute("DELETE FROM farms WHERE farm_name LIKE 'Test Sales%'")
        conn.commit()
    finally:
        conn.close()

def test_sales_transaction_crud():
    """Test CRUD operations for the sales_transaction table."""
    print("\nTesting sales_transaction table CRUD operations...")
    
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
        
        # Create test farm and customer records first
        print("Creating test farm and customer records...")
        farm_id = create_farm(
            farm_name="Test Sales Farm",
            farm_loc="Test Location",
            farm_desc="Test Sales Farm Description"
        )
        
        customer_id1 = create_customer(
            customer_name="Test Sales Customer 1",
            farm_id=farm_id,
            customer_type="Retail"
        )
        
        customer_id2 = create_customer(
            customer_name="Test Sales Customer 2",
            farm_id=farm_id,
            customer_type="Wholesale"
        )
        
        # Now run the tests
        
        # 1. Test create_sales_transaction
        print("Testing create_sales_transaction...")
        sale_id1 = create_sales_transaction(
            sale_ts=now_str,
            total_amount=100.0,
            customer_id=customer_id1,
            notes="Test sale 1"
        )
        
        sale_id2 = create_sales_transaction(
            sale_ts=yesterday_str,
            total_amount=75.0,
            customer_id=customer_id1,
            notes="Test sale 2"
        )
        
        sale_id3 = create_sales_transaction(
            sale_ts=now_str,
            total_amount=150.0,
            customer_id=customer_id2,
            notes="Test sale 3"
        )
        
        assert sale_id1 > 0, f"Expected positive sale_id, got {sale_id1}"
        assert sale_id2 > 0, f"Expected positive sale_id, got {sale_id2}"
        assert sale_id3 > 0, f"Expected positive sale_id, got {sale_id3}"
        
        # 2. Test get_sales_transaction
        print("Testing get_sales_transaction...")
        sale1 = get_sales_transaction(sale_id1)
        assert sale1 is not None, "Failed to retrieve sale1"
        assert sale1['total_amount'] == 100.0, f"Expected total_amount 100.0, got {sale1['total_amount']}"
        assert sale1['customer_id'] == customer_id1, f"Expected customer_id {customer_id1}, got {sale1['customer_id']}"
        assert sale1['notes'] == "Test sale 1", f"Expected notes 'Test sale 1', got '{sale1['notes']}'"
        assert sale1['sale_ts'] == now_str, f"Expected sale_ts '{now_str}', got '{sale1['sale_ts']}'"
        assert sale1['active'] == 1, f"Expected active 1, got {sale1['active']}"
        
        # 3. Test get_all_sales_transactions
        print("Testing get_all_sales_transactions...")
        all_sales = get_all_sales_transactions()
        assert len(all_sales) >= 3, f"Expected at least 3 sales transaction records, got {len(all_sales)}"
        
        # 4. Test get_sales_transactions_by_customer
        print("Testing get_sales_transactions_by_customer...")
        customer1_sales = get_sales_transactions_by_customer(customer_id1)
        assert len(customer1_sales) == 2, f"Expected 2 sales transaction records for customer1, got {len(customer1_sales)}"
        
        customer2_sales = get_sales_transactions_by_customer(customer_id2)
        assert len(customer2_sales) == 1, f"Expected 1 sales transaction record for customer2, got {len(customer2_sales)}"
        
        # 5. Test get_sales_transactions_by_date_range
        print("Testing get_sales_transactions_by_date_range...")
        # Test with just start date
        recent_sales = get_sales_transactions_by_date_range(yesterday_str)
        assert len(recent_sales) >= 3, f"Expected at least 3 recent sales transaction records, got {len(recent_sales)}"
        
        # Test with start and end date
        yesterday_sales = get_sales_transactions_by_date_range(yesterday_str, yesterday_str)
        assert len(yesterday_sales) >= 1, f"Expected at least 1 sales transaction record from yesterday, got {len(yesterday_sales)}"
        
        # 6. Test update_sales_transaction
        print("Testing update_sales_transaction...")
        rows_updated = update_sales_transaction(
            sale_id1,
            total_amount=110.0,
            notes="Updated test sale 1"
        )
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_sale = get_sales_transaction(sale_id1)
        assert updated_sale['total_amount'] == 110.0, f"Expected total_amount 110.0, got {updated_sale['total_amount']}"
        assert updated_sale['notes'] == "Updated test sale 1", f"Expected notes 'Updated test sale 1', got '{updated_sale['notes']}'"
        assert updated_sale['customer_id'] == customer_id1, f"Expected customer_id unchanged at {customer_id1}, got {updated_sale['customer_id']}"
        
        # 7. Test update_sales_transaction_total
        print("Testing update_sales_transaction_total...")
        rows_updated = update_sales_transaction_total(sale_id1, 120.0)
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_total = get_sales_transaction(sale_id1)
        assert updated_total['total_amount'] == 120.0, f"Expected total_amount 120.0, got {updated_total['total_amount']}"
        
        # 8. Test soft_delete_sales_transaction
        print("Testing soft_delete_sales_transaction...")
        rows_deleted = soft_delete_sales_transaction(sale_id2)
        assert rows_deleted == 1, f"Expected 1 row soft deleted, got {rows_deleted}"
        
        soft_deleted_sale = get_sales_transaction(sale_id2)
        assert soft_deleted_sale is None, f"Expected None for soft deleted sale when using get_sales_transaction, got {soft_deleted_sale}"
        
        # Check if we can still get the soft deleted record when including inactive
        all_sales_with_inactive = get_all_sales_transactions(include_inactive=True)
        assert len(all_sales_with_inactive) >= 3, f"Expected at least 3 sales transaction records with inactive, got {len(all_sales_with_inactive)}"
        
        all_sales_active_only = get_all_sales_transactions(include_inactive=False)
        assert len(all_sales_active_only) == len(all_sales_with_inactive) - 1, f"Expected one less active record than total records"
        
        # 9. Test delete_sales_transaction
        print("Testing delete_sales_transaction...")
        rows_hard_deleted = delete_sales_transaction(sale_id3)
        assert rows_hard_deleted == 1, f"Expected 1 row hard deleted, got {rows_hard_deleted}"
        
        hard_deleted_sale = get_sales_transaction(sale_id3)
        assert hard_deleted_sale is None, f"Expected None for hard deleted sale, got {hard_deleted_sale}"
        
        # Check if the hard deleted record is really gone
        all_sales_after_delete = get_all_sales_transactions(include_inactive=True)
        assert len(all_sales_after_delete) == len(all_sales_with_inactive) - 1, f"Expected one less record after hard delete"
        
        print("All sales_transaction table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in sales_transaction table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up test data
        clean_test_data()

if __name__ == "__main__":
    test_sales_transaction_crud()
