"""
Sales Transaction Table Module for Mycelium

This module provides functions for interacting with the sales_transaction table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import sqlite3

from storage.db_utils import execute_query, execute_insert, execute_update, get_timestamp

def create_sales_transaction(sale_ts: str, total_amount: float = 0.0,
                           customer_id: Optional[int] = None,
                           notes: Optional[str] = None) -> int:
    """
    Create a new sales transaction record.
    
    Args:
        sale_ts (str): Timestamp of the sale
        total_amount (float, optional): Total amount of the sale (default 0.0)
        customer_id (int, optional): Reference to customer record
        notes (str, optional): Additional notes about the sale
        
    Returns:
        int: ID of the newly created sales transaction record
    """
    query = """
    INSERT INTO sales_transaction (customer_id, sale_ts, total_amount, notes)
    VALUES (?, ?, ?, ?)
    """
    return execute_insert(query, (customer_id, sale_ts, total_amount, notes))

def get_sales_transaction(sale_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific sales transaction record by sale_id.
    
    Args:
        sale_id (int): ID of the sales transaction record
        
    Returns:
        Optional[Dict[str, Any]]: Sales transaction data or None if not found
    """
    query = "SELECT * FROM sales_transaction WHERE sale_id = ? AND active = 1"
    results = execute_query(query, (sale_id,))
    return results[0] if results else None

def get_all_sales_transactions(include_inactive: bool = False) -> List[Dict[str, Any]]:
    """
    Get all sales transaction records.
    
    Args:
        include_inactive (bool, optional): Whether to include inactive records (default False)
        
    Returns:
        List[Dict[str, Any]]: List of all sales transaction records
    """
    if include_inactive:
        query = "SELECT * FROM sales_transaction ORDER BY sale_ts DESC"
        return execute_query(query, ())
    else:
        query = "SELECT * FROM sales_transaction WHERE active = 1 ORDER BY sale_ts DESC"
        return execute_query(query, ())

def get_sales_transactions_by_customer(customer_id: int, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """
    Get sales transaction records by customer_id.
    
    Args:
        customer_id (int): ID of the customer record
        include_inactive (bool, optional): Whether to include inactive records (default False)
        
    Returns:
        List[Dict[str, Any]]: List of sales transaction records for the customer
    """
    if include_inactive:
        query = "SELECT * FROM sales_transaction WHERE customer_id = ? ORDER BY sale_ts DESC"
        return execute_query(query, (customer_id,))
    else:
        query = "SELECT * FROM sales_transaction WHERE customer_id = ? AND active = 1 ORDER BY sale_ts DESC"
        return execute_query(query, (customer_id,))

def get_sales_transactions_by_date_range(start_date: str, end_date: Optional[str] = None,
                                       include_inactive: bool = False) -> List[Dict[str, Any]]:
    """
    Get sales transaction records within a date range based on sale_ts.
    
    Args:
        start_date (str): Start date for the range
        end_date (str, optional): End date for the range, defaults to current time if None
        include_inactive (bool, optional): Whether to include inactive records (default False)
        
    Returns:
        List[Dict[str, Any]]: List of sales transaction records in the date range
    """
    if end_date is None:
        end_date = get_timestamp()
    
    if include_inactive:
        query = """
        SELECT * FROM sales_transaction 
        WHERE sale_ts >= ? AND sale_ts <= ? 
        ORDER BY sale_ts DESC
        """
        return execute_query(query, (start_date, end_date))
    else:
        query = """
        SELECT * FROM sales_transaction 
        WHERE sale_ts >= ? AND sale_ts <= ? AND active = 1
        ORDER BY sale_ts DESC
        """
        return execute_query(query, (start_date, end_date))

def update_sales_transaction(sale_id: int, sale_ts: Optional[str] = None,
                           total_amount: Optional[float] = None,
                           customer_id: Optional[int] = None,
                           notes: Optional[str] = None) -> int:
    """
    Update a sales transaction record.
    
    Args:
        sale_id (int): ID of the sales transaction record to update
        sale_ts (str, optional): New sale timestamp
        total_amount (float, optional): New total amount
        customer_id (int, optional): New customer ID
        notes (str, optional): New notes
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []
    
    if sale_ts is not None:
        update_fields.append("sale_ts = ?")
        params.append(sale_ts)
    
    if total_amount is not None:
        update_fields.append("total_amount = ?")
        params.append(total_amount)
    
    if customer_id is not None:
        update_fields.append("customer_id = ?")
        params.append(customer_id)
    
    if notes is not None:
        update_fields.append("notes = ?")
        params.append(notes)
    
    if not update_fields:
        return 0  # Nothing to update
    
    # No updated_at field in this table
    
    # Add sale_id to params
    params.append(sale_id)
    
    query = f"""
    UPDATE sales_transaction
    SET {', '.join(update_fields)}
    WHERE sale_id = ? AND active = 1
    """
    
    return execute_update(query, tuple(params))

def update_sales_transaction_total(sale_id: int, total_amount: float) -> int:
    """
    Update the total_amount field of a sales transaction record.
    
    Args:
        sale_id (int): ID of the sales transaction record
        total_amount (float): New total amount
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE sales_transaction
    SET total_amount = ?
    WHERE sale_id = ? AND active = 1
    """
    return execute_update(query, (total_amount, sale_id))

def soft_delete_sales_transaction(sale_id: int) -> int:
    """
    Soft delete a sales transaction record by setting active = 0.
    
    Args:
        sale_id (int): ID of the sales transaction record to soft delete
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE sales_transaction
    SET active = 0
    WHERE sale_id = ? AND active = 1
    """
    return execute_update(query, (sale_id,))

def delete_sales_transaction(sale_id: int) -> int:
    """
    Hard delete a sales transaction record.
    
    Args:
        sale_id (int): ID of the sales transaction record to delete
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM sales_transaction WHERE sale_id = ?"
    return execute_update(query, (sale_id,))
