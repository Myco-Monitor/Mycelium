"""
Harvest Table Module for Mycelium

This module provides functions for interacting with the harvest table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import sqlite3

from storage.db_utils import execute_query, execute_insert, execute_update, get_timestamp

def create_harvest(harvest_ts: str, total_wt: float, trimmed_wt: float,
                  bulk_id: Optional[int] = None, unit_id: Optional[int] = None,
                  weight_used: float = 0.0) -> int:
    """
    Create a new harvest record.
    
    Args:
        harvest_ts (str): Timestamp of the harvest
        total_wt (float): Total weight of the harvest
        trimmed_wt (float): Trimmed weight of the harvest
        bulk_id (int, optional): Reference to bulk record
        unit_id (int, optional): Reference to cost_of_goods unit
        weight_used (float, optional): Weight already used (default 0.0)
        
    Returns:
        int: ID of the newly created harvest record
    """
    query = """
    INSERT INTO harvest (harvest_ts, bulk_id, total_wt, trimmed_wt, unit_id, weight_used)
    VALUES (?, ?, ?, ?, ?, ?)
    """
    return execute_insert(query, (harvest_ts, bulk_id, total_wt, trimmed_wt, unit_id, weight_used))

def get_harvest(harvest_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific harvest record by harvest_id.
    
    Args:
        harvest_id (int): ID of the harvest record
        
    Returns:
        Optional[Dict[str, Any]]: Harvest data or None if not found
    """
    query = "SELECT * FROM harvest WHERE harvest_id = ?"
    results = execute_query(query, (harvest_id,))
    return results[0] if results else None

def get_all_harvests() -> List[Dict[str, Any]]:
    """
    Get all harvest records.
    
    Returns:
        List[Dict[str, Any]]: List of all harvest records
    """
    query = "SELECT * FROM harvest ORDER BY harvest_ts DESC"
    return execute_query(query, ())

def get_harvests_by_bulk(bulk_id: int) -> List[Dict[str, Any]]:
    """
    Get harvest records by bulk_id.
    
    Args:
        bulk_id (int): ID of the bulk record
        
    Returns:
        List[Dict[str, Any]]: List of harvest records for the bulk
    """
    query = "SELECT * FROM harvest WHERE bulk_id = ? ORDER BY harvest_ts DESC"
    return execute_query(query, (bulk_id,))

def get_harvests_by_unit(unit_id: int) -> List[Dict[str, Any]]:
    """
    Get harvest records by unit_id.
    
    Args:
        unit_id (int): ID of the cost_of_goods unit
        
    Returns:
        List[Dict[str, Any]]: List of harvest records for the unit
    """
    query = "SELECT * FROM harvest WHERE unit_id = ? ORDER BY harvest_ts DESC"
    return execute_query(query, (unit_id,))

def get_harvests_by_date_range(start_date: str, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get harvest records within a date range based on harvest_ts.
    
    Args:
        start_date (str): Start date for the range
        end_date (str, optional): End date for the range, defaults to current time if None
        
    Returns:
        List[Dict[str, Any]]: List of harvest records in the date range
    """
    if end_date is None:
        end_date = get_timestamp()
        
    query = """
    SELECT * FROM harvest 
    WHERE harvest_ts >= ? AND harvest_ts <= ? 
    ORDER BY harvest_ts DESC
    """
    return execute_query(query, (start_date, end_date))

def get_available_harvests() -> List[Dict[str, Any]]:
    """
    Get harvests that have available weight (total_wt > weight_used).
    
    Returns:
        List[Dict[str, Any]]: List of harvests with available weight
    """
    query = """
    SELECT * FROM harvest 
    WHERE total_wt > weight_used 
    ORDER BY harvest_ts
    """
    return execute_query(query, ())

def update_harvest(harvest_id: int, harvest_ts: Optional[str] = None,
                  total_wt: Optional[float] = None, trimmed_wt: Optional[float] = None,
                  bulk_id: Optional[int] = None, unit_id: Optional[int] = None,
                  weight_used: Optional[float] = None) -> int:
    """
    Update a harvest record.
    
    Args:
        harvest_id (int): ID of the harvest record to update
        harvest_ts (str, optional): New harvest timestamp
        total_wt (float, optional): New total weight
        trimmed_wt (float, optional): New trimmed weight
        bulk_id (int, optional): New bulk ID
        unit_id (int, optional): New unit ID
        weight_used (float, optional): New weight used
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []
    
    if harvest_ts is not None:
        update_fields.append("harvest_ts = ?")
        params.append(harvest_ts)
    
    if total_wt is not None:
        update_fields.append("total_wt = ?")
        params.append(total_wt)
    
    if trimmed_wt is not None:
        update_fields.append("trimmed_wt = ?")
        params.append(trimmed_wt)
    
    if bulk_id is not None:
        update_fields.append("bulk_id = ?")
        params.append(bulk_id)
    
    if unit_id is not None:
        update_fields.append("unit_id = ?")
        params.append(unit_id)
    
    if weight_used is not None:
        update_fields.append("weight_used = ?")
        params.append(weight_used)
    
    if not update_fields:
        return 0  # Nothing to update
    
    # Add harvest_id to params
    params.append(harvest_id)
    
    query = f"""
    UPDATE harvest
    SET {', '.join(update_fields)}
    WHERE harvest_id = ?
    """
    
    return execute_update(query, tuple(params))

def update_harvest_weight_used(harvest_id: int, additional_weight: float) -> int:
    """
    Update the weight_used field by adding the additional weight.
    
    Args:
        harvest_id (int): ID of the harvest record
        additional_weight (float): Additional weight to add to weight_used
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE harvest
    SET weight_used = weight_used + ?
    WHERE harvest_id = ?
    """
    return execute_update(query, (additional_weight, harvest_id))

def delete_harvest(harvest_id: int) -> int:
    """
    Delete a harvest record.
    
    Args:
        harvest_id (int): ID of the harvest record to delete
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM harvest WHERE harvest_id = ?"
    return execute_update(query, (harvest_id,))
