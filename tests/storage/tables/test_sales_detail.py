"""
Tests for the sales_detail table module.

This module contains tests for the sales_detail table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.sales_detail import (
    create_sales_detail, get_sales_detail, get_all_sales_details,
    get_sales_details_by_sale, get_sales_details_by_harvest,
    get_sales_details_by_unit, update_sales_detail,
    delete_sales_detail, calculate_total_for_sale
)
from storage.tables.sales_transaction import create_sales_transaction, update_sales_transaction_total
from storage.tables.harvest import create_harvest, update_harvest_weight_used
from storage.tables.bulk import create_bulk
from storage.tables.cost_of_goods import create_cost_of_goods
from storage.tables.farms import create_farm
from storage.tables.customers import create_customer
from storage.db_utils import get_connection, execute_query, get_timestamp, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test sales_detail records that might exist from previous test runs
        cursor.execute("DELETE FROM sales_detail WHERE sale_id IN (SELECT sale_id FROM sales_transaction WHERE customer_id IN (SELECT customer_id FROM customers WHERE customer_name LIKE 'Test Sales Detail%'))")
        cursor.execute("DELETE FROM sales_transaction WHERE customer_id IN (SELECT customer_id FROM customers WHERE customer_name LIKE 'Test Sales Detail%')")
        cursor.execute("DELETE FROM harvest WHERE unit_id IN (SELECT unit_id FROM cost_of_goods WHERE item_name LIKE 'Test Sales Detail%')")
        cursor.execute("DELETE FROM bulk WHERE unit_id IN (SELECT unit_id FROM cost_of_goods WHERE item_name LIKE 'Test Sales Detail%')")
        cursor.execute("DELETE FROM customers WHERE customer_name LIKE 'Test Sales Detail%'")
        cursor.execute("DELETE FROM cost_of_goods WHERE item_name LIKE 'Test Sales Detail%'")
        cursor.execute("DELETE FROM farms WHERE farm_name LIKE 'Test Sales Detail%'")
        conn.commit()
    finally:
        conn.close()

def test_sales_detail_crud():
    """Test CRUD operations for the sales_detail table."""
    print("\nTesting sales_detail table CRUD operations...")
    
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
        
        # Create test farm, customer, cost_of_goods, bulk, harvest, and sales_transaction records first
        print("Creating test prerequisite records...")
        farm_id = create_farm(
            farm_name="Test Sales Detail Farm",
            farm_loc="Test Location",
            farm_desc="Test Farm Description"
        )
        
        customer_id = create_customer(
            customer_name="Test Sales Detail Customer",
            farm_id=farm_id,
            customer_type="Retail"
        )
        
        unit_id1 = create_cost_of_goods(
            item_name="Test Sales Detail Unit 1",
            item_cost=40.0,
            item_count=1,
            weight_lbs=15.0
        )
        
        unit_id2 = create_cost_of_goods(
            item_name="Test Sales Detail Unit 2",
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
        
        harvest_id2 = create_harvest(
            harvest_ts=yesterday_str,
            total_wt=3.0,
            trimmed_wt=2.8,
            bulk_id=bulk_id2,
            unit_id=unit_id2
        )
        
        sale_id = create_sales_transaction(
            sale_ts=now_str,
            total_amount=0.0,  # Will be updated later
            customer_id=customer_id,
            notes="Test sale for sales_detail test"
        )
        
        # Now run the tests
        
        # 1. Test create_sales_detail
        print("Testing create_sales_detail...")
        detail_id1 = create_sales_detail(
            sale_id=sale_id,
            harvest_id=harvest_id1,
            weight_used=2.0,
            price=15.0,
            line_total=30.0,
            unit_id=unit_id1,
            notes="Test sales detail 1"
        )
        
        detail_id2 = create_sales_detail(
            sale_id=sale_id,
            harvest_id=harvest_id2,
            weight_used=1.5,
            price=12.0,
            line_total=18.0,
            unit_id=unit_id2,
            notes="Test sales detail 2"
        )
        
        assert detail_id1 > 0, f"Expected positive detail_id, got {detail_id1}"
        assert detail_id2 > 0, f"Expected positive detail_id, got {detail_id2}"
        
        # 2. Test get_sales_detail
        print("Testing get_sales_detail...")
        detail1 = get_sales_detail(detail_id1)
        assert detail1 is not None, "Failed to retrieve detail1"
        assert detail1['sale_id'] == sale_id, f"Expected sale_id {sale_id}, got {detail1['sale_id']}"
        assert detail1['harvest_id'] == harvest_id1, f"Expected harvest_id {harvest_id1}, got {detail1['harvest_id']}"
        assert detail1['unit_id'] == unit_id1, f"Expected unit_id {unit_id1}, got {detail1['unit_id']}"
        assert detail1['weight_used'] == 2.0, f"Expected weight_used 2.0, got {detail1['weight_used']}"
        assert detail1['price'] == 15.0, f"Expected price 15.0, got {detail1['price']}"
        assert detail1['line_total'] == 30.0, f"Expected line_total 30.0, got {detail1['line_total']}"
        assert detail1['notes'] == "Test sales detail 1", f"Expected notes 'Test sales detail 1', got '{detail1['notes']}'"
        
        # 3. Test get_all_sales_details
        print("Testing get_all_sales_details...")
        all_details = get_all_sales_details()
        assert len(all_details) >= 2, f"Expected at least 2 sales detail records, got {len(all_details)}"
        
        # 4. Test get_sales_details_by_sale
        print("Testing get_sales_details_by_sale...")
        sale_details = get_sales_details_by_sale(sale_id)
        assert len(sale_details) == 2, f"Expected 2 sales detail records for sale, got {len(sale_details)}"
        
        # 5. Test get_sales_details_by_harvest
        print("Testing get_sales_details_by_harvest...")
        harvest1_details = get_sales_details_by_harvest(harvest_id1)
        assert len(harvest1_details) == 1, f"Expected 1 sales detail record for harvest1, got {len(harvest1_details)}"
        
        harvest2_details = get_sales_details_by_harvest(harvest_id2)
        assert len(harvest2_details) == 1, f"Expected 1 sales detail record for harvest2, got {len(harvest2_details)}"
        
        # 6. Test get_sales_details_by_unit
        print("Testing get_sales_details_by_unit...")
        unit1_details = get_sales_details_by_unit(unit_id1)
        assert len(unit1_details) == 1, f"Expected 1 sales detail record for unit1, got {len(unit1_details)}"
        
        unit2_details = get_sales_details_by_unit(unit_id2)
        assert len(unit2_details) == 1, f"Expected 1 sales detail record for unit2, got {len(unit2_details)}"
        
        # 7. Test update_sales_detail
        print("Testing update_sales_detail...")
        rows_updated = update_sales_detail(
            detail_id1,
            weight_used=2.5,
            price=16.0,
            line_total=40.0,
            notes="Updated test sales detail 1"
        )
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_detail = get_sales_detail(detail_id1)
        assert updated_detail['weight_used'] == 2.5, f"Expected weight_used 2.5, got {updated_detail['weight_used']}"
        assert updated_detail['price'] == 16.0, f"Expected price 16.0, got {updated_detail['price']}"
        assert updated_detail['line_total'] == 40.0, f"Expected line_total 40.0, got {updated_detail['line_total']}"
        assert updated_detail['notes'] == "Updated test sales detail 1", f"Expected notes 'Updated test sales detail 1', got '{updated_detail['notes']}'"
        
        # 8. Test calculate_total_for_sale
        print("Testing calculate_total_for_sale...")
        sale_total = calculate_total_for_sale(sale_id)
        assert sale_total == 58.0, f"Expected sale total 58.0, got {sale_total}"
        
        # Update the sales transaction total
        update_sales_transaction_total(sale_id, sale_total)
        
        # 9. Test update_harvest_weight_used
        print("Testing update_harvest_weight_used...")
        # Update the harvest weight used
        update_harvest_weight_used(harvest_id1, 2.5)
        update_harvest_weight_used(harvest_id2, 1.5)
        
        # 10. Test delete_sales_detail
        print("Testing delete_sales_detail...")
        rows_deleted = delete_sales_detail(detail_id2)
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_detail = get_sales_detail(detail_id2)
        assert deleted_detail is None, f"Expected None for deleted detail, got {deleted_detail}"
        
        # Check if the deleted record is really gone
        all_details_after_delete = get_all_sales_details()
        assert len(all_details_after_delete) == len(all_details) - 1, f"Expected one less record after delete"
        
        # Recalculate the sale total after deleting a detail
        new_sale_total = calculate_total_for_sale(sale_id)
        assert new_sale_total == 40.0, f"Expected new sale total 40.0, got {new_sale_total}"
        
        # Update the sales transaction total again
        update_sales_transaction_total(sale_id, new_sale_total)
        
        print("All sales_detail table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in sales_detail table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up test data
        clean_test_data()

if __name__ == "__main__":
    test_sales_detail_crud()
