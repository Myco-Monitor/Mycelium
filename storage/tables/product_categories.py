"""
Product Categories Table Module for Mycelium

This module provides functions for interacting with the product_categories table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import sqlite3

from storage.db_utils import execute_query, execute_insert, execute_update, get_timestamp

def create_product_category(category_name: str, category_type: Optional[str] = None, 
                           category_desc: Optional[str] = None, active: int = 1) -> int:
    """
    Create a new product category record.
    
    Args:
        category_name (str): Name of the product category
        category_type (str, optional): Type classification (mushroom, substrate, equipment, etc.)
        category_desc (str, optional): Description of the product category
        active (int, optional): Active status (1=active, 0=deleted), defaults to 1
        
    Returns:
        int: ID of the newly created record (item_id)
    """
    query = """
    INSERT INTO product_categories (category_name, category_type, category_desc, active)
    VALUES (?, ?, ?, ?)
    """
    return execute_insert(query, (category_name, category_type, category_desc, active))

def get_product_category(item_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific product category record by item_id.
    
    Args:
        item_id (int): ID of the product category record
        
    Returns:
        Optional[Dict[str, Any]]: Product category data or None if not found
    """
    query = "SELECT * FROM product_categories WHERE item_id = ?"
    result = execute_query(query, (item_id,))
    return result[0] if result else None

def get_all_product_categories(active_only: bool = True) -> List[Dict[str, Any]]:
    """
    Get all product category records.
    
    Args:
        active_only (bool, optional): If True, only return active categories, defaults to True
        
    Returns:
        List[Dict[str, Any]]: List of all product category records
    """
    if active_only:
        query = "SELECT * FROM product_categories WHERE active = 1 ORDER BY category_name"
    else:
        query = "SELECT * FROM product_categories ORDER BY category_name"
    return execute_query(query)

def get_product_categories_by_name(category_name: str) -> List[Dict[str, Any]]:
    """
    Get product category records by name (partial match).
    
    Args:
        category_name (str): Name pattern to search for
        
    Returns:
        List[Dict[str, Any]]: List of matching product category records
    """
    query = """
    SELECT * FROM product_categories 
    WHERE category_name LIKE ? AND active = 1
    ORDER BY category_name
    """
    return execute_query(query, (f"%{category_name}%",))

def get_product_categories_by_type(category_type: str) -> List[Dict[str, Any]]:
    """
    Get product category records by type.
    
    Args:
        category_type (str): Type to filter by
        
    Returns:
        List[Dict[str, Any]]: List of product category records with matching type
    """
    query = """
    SELECT * FROM product_categories 
    WHERE category_type = ? AND active = 1
    ORDER BY category_name
    """
    return execute_query(query, (category_type,))

def update_product_category(item_id: int, category_name: Optional[str] = None,
                           category_type: Optional[str] = None, category_desc: Optional[str] = None,
                           active: Optional[int] = None) -> int:
    """
    Update a product category record.
    
    Args:
        item_id (int): ID of the product category record to update
        category_name (str, optional): New category name
        category_type (str, optional): New category type
        category_desc (str, optional): New category description
        active (int, optional): New active status
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build dynamic update query
    set_clauses = []
    params = []
    
    if category_name is not None:
        set_clauses.append("category_name = ?")
        params.append(category_name)
    
    if category_type is not None:
        set_clauses.append("category_type = ?")
        params.append(category_type)
    
    if category_desc is not None:
        set_clauses.append("category_desc = ?")
        params.append(category_desc)
    
    if active is not None:
        set_clauses.append("active = ?")
        params.append(active)
    
    if not set_clauses:
        return 0  # No updates to make
    
    # Always update the updated_at timestamp
    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    params.append(item_id)
    
    query = f"""
    UPDATE product_categories 
    SET {', '.join(set_clauses)}
    WHERE item_id = ?
    """
    
    return execute_update(query, params)

def deactivate_product_category(item_id: int) -> int:
    """
    Deactivate a product category record (soft delete).
    
    Args:
        item_id (int): ID of the product category record to deactivate
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    return update_product_category(item_id, active=0)

def delete_product_category(item_id: int) -> int:
    """
    Delete a product category record (hard delete).
    
    Args:
        item_id (int): ID of the product category record to delete
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM product_categories WHERE item_id = ?"
    return execute_update(query, (item_id,))

def get_category_usage_count(item_id: int) -> int:
    """
    Get the count of cost_of_goods records using this category.
    
    Args:
        item_id (int): ID of the product category
        
    Returns:
        int: Number of cost_of_goods records using this category
    """
    query = "SELECT COUNT(*) as count FROM cost_of_goods WHERE item_id = ?"
    result = execute_query(query, (item_id,))
    return result[0]['count'] if result else 0

def can_delete_category(item_id: int) -> bool:
    """
    Check if a product category can be safely deleted.
    
    Args:
        item_id (int): ID of the product category
        
    Returns:
        bool: True if category can be deleted (no references), False otherwise
    """
    return get_category_usage_count(item_id) == 0
