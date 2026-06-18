"""
Customers Table Module for Mycelium

This module provides functions for interacting with the customers table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import sqlite3

from storage.db_utils import execute_query, execute_insert, execute_update, get_timestamp

def create_customer(customer_name: str, farm_id: Optional[int] = None,
                   customer_info: Optional[str] = None, customer_type: Optional[str] = None,
                   notes: Optional[str] = None) -> int:
    """
    Create a new customer record.
    
    Args:
        customer_name (str): Name of the customer
        farm_id (int, optional): Reference to farm record
        customer_info (str, optional): Additional customer information
        customer_type (str, optional): Type of customer (e.g., Retail, Wholesale)
        notes (str, optional): Additional notes about the customer
        
    Returns:
        int: ID of the newly created customer record
    """
    query = """
    INSERT INTO customers (farm_id, customer_name, customer_info, customer_type, notes)
    VALUES (?, ?, ?, ?, ?)
    """
    return execute_insert(query, (farm_id, customer_name, customer_info, customer_type, notes))

def get_customer(customer_id: int, include_inactive: bool = False) -> Optional[Dict[str, Any]]:
    """
    Get a specific customer record by customer_id.
    
    Args:
        customer_id (int): ID of the customer record
        include_inactive (bool, optional): Whether to include inactive records (default False)
        
    Returns:
        Optional[Dict[str, Any]]: Customer data or None if not found
    """
    if include_inactive:
        query = "SELECT * FROM customers WHERE customer_id = ?"
        return execute_query(query, (customer_id,))[0] if execute_query(query, (customer_id,)) else None
    else:
        query = "SELECT * FROM customers WHERE customer_id = ? AND active = 1"
        return execute_query(query, (customer_id,))[0] if execute_query(query, (customer_id,)) else None

def get_all_customers(include_inactive: bool = False) -> List[Dict[str, Any]]:
    """
    Get all customer records.
    
    Args:
        include_inactive (bool, optional): Whether to include inactive records (default False)
        
    Returns:
        List[Dict[str, Any]]: List of all customer records
    """
    if include_inactive:
        query = "SELECT * FROM customers ORDER BY customer_name"
        return execute_query(query, ())
    else:
        query = "SELECT * FROM customers WHERE active = 1 ORDER BY customer_name"
        return execute_query(query, ())

def get_customers_by_farm(farm_id: int, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """
    Get customer records by farm_id.
    
    Args:
        farm_id (int): ID of the farm record
        include_inactive (bool, optional): Whether to include inactive records (default False)
        
    Returns:
        List[Dict[str, Any]]: List of customer records for the farm
    """
    if include_inactive:
        query = "SELECT * FROM customers WHERE farm_id = ? ORDER BY customer_name"
        return execute_query(query, (farm_id,))
    else:
        query = "SELECT * FROM customers WHERE farm_id = ? AND active = 1 ORDER BY customer_name"
        return execute_query(query, (farm_id,))

def get_customers_by_type(customer_type: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """
    Get customer records by customer_type.
    
    Args:
        customer_type (str): Type of customer
        include_inactive (bool, optional): Whether to include inactive records (default False)
        
    Returns:
        List[Dict[str, Any]]: List of customer records of the specified type
    """
    if include_inactive:
        query = "SELECT * FROM customers WHERE customer_type = ? ORDER BY customer_name"
        return execute_query(query, (customer_type,))
    else:
        query = "SELECT * FROM customers WHERE customer_type = ? AND active = 1 ORDER BY customer_name"
        return execute_query(query, (customer_type,))

def search_customers(search_term: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """
    Search for customers by name or info.
    
    Args:
        search_term (str): Term to search for in customer_name or customer_info
        include_inactive (bool, optional): Whether to include inactive records (default False)
        
    Returns:
        List[Dict[str, Any]]: List of matching customer records
    """
    search_pattern = f"%{search_term}%"
    
    if include_inactive:
        query = """
        SELECT * FROM customers 
        WHERE customer_name LIKE ? OR customer_info LIKE ? 
        ORDER BY customer_name
        """
        return execute_query(query, (search_pattern, search_pattern))
    else:
        query = """
        SELECT * FROM customers 
        WHERE (customer_name LIKE ? OR customer_info LIKE ?) AND active = 1
        ORDER BY customer_name
        """
        return execute_query(query, (search_pattern, search_pattern))

def update_customer(customer_id: int, customer_name: Optional[str] = None,
                   farm_id: Optional[int] = None, customer_info: Optional[str] = None,
                   customer_type: Optional[str] = None, notes: Optional[str] = None) -> int:
    """
    Update a customer record.
    
    Args:
        customer_id (int): ID of the customer record to update
        customer_name (str, optional): New customer name
        farm_id (int, optional): New farm ID
        customer_info (str, optional): New customer info
        customer_type (str, optional): New customer type
        notes (str, optional): New notes
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []
    
    if customer_name is not None:
        update_fields.append("customer_name = ?")
        params.append(customer_name)
    
    if farm_id is not None:
        update_fields.append("farm_id = ?")
        params.append(farm_id)
    
    if customer_info is not None:
        update_fields.append("customer_info = ?")
        params.append(customer_info)
    
    if customer_type is not None:
        update_fields.append("customer_type = ?")
        params.append(customer_type)
    
    if notes is not None:
        update_fields.append("notes = ?")
        params.append(notes)
    
    if not update_fields:
        return 0  # Nothing to update
    
    # Add updated_at timestamp
    update_fields.append("updated_at = ?")
    params.append(get_timestamp())
    
    # Add customer_id to params
    params.append(customer_id)
    
    query = f"""
    UPDATE customers
    SET {', '.join(update_fields)}
    WHERE customer_id = ? AND active = 1
    """
    
    return execute_update(query, tuple(params))

def deactivate_customer(customer_id: int, deactivation_reason: Optional[str] = None) -> int:
    """
    Deactivate a customer record by setting active = 0.
    
    Args:
        customer_id (int): ID of the customer record to deactivate
        deactivation_reason (str, optional): Reason for deactivation
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE customers
    SET active = 0, deactivation_reason = ?, updated_at = ?
    WHERE customer_id = ? AND active = 1
    """
    return execute_update(query, (deactivation_reason, get_timestamp(), customer_id))

def reactivate_customer(customer_id: int) -> int:
    """
    Reactivate a customer record by setting active = 1.
    
    Args:
        customer_id (int): ID of the customer record to reactivate
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE customers
    SET active = 1, deactivation_reason = NULL, updated_at = ?
    WHERE customer_id = ? AND active = 0
    """
    return execute_update(query, (get_timestamp(), customer_id))

def delete_customer(customer_id: int) -> int:
    """
    Hard delete a customer record.
    
    Args:
        customer_id (int): ID of the customer record to delete
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM customers WHERE customer_id = ?"
    return execute_update(query, (customer_id,))
