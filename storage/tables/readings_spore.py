"""
Readings Spore Table Module for Mycelium

This module provides functions for interacting with the readings_spore table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import sqlite3

from storage.db_utils import execute_query, execute_insert, execute_update, get_timestamp

def create_reading(device_id: int, reading_ts: str, co2: Optional[float] = None,
                  humidity: Optional[float] = None, temp: Optional[float] = None,
                  spore_ts: Optional[str] = None) -> Tuple[int, str]:
    """
    Create a new spore device reading record.
    
    Args:
        device_id (int): ID of the spore device
        reading_ts (str): Timestamp of the reading
        co2 (float, optional): CO2 level reading
        humidity (float, optional): Humidity level reading
        temp (float, optional): Temperature reading
        spore_ts (str, optional): Original timestamp from the spore device
        
    Returns:
        Tuple[int, str]: Tuple of device_id and reading_ts of the newly created reading
    """
    query = """
    INSERT INTO readings_spore (device_id, reading_ts, co2, humidity, temp, spore_ts)
    VALUES (?, ?, ?, ?, ?, ?)
    """
    execute_insert(query, (device_id, reading_ts, co2, humidity, temp, spore_ts))
    return (device_id, reading_ts)

def get_reading(device_id: int, reading_ts: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific spore reading by device_id and timestamp.
    
    Args:
        device_id (int): ID of the spore device
        reading_ts (str): Timestamp of the reading
        
    Returns:
        Optional[Dict[str, Any]]: Reading data or None if not found
    """
    query = "SELECT * FROM readings_spore WHERE device_id = ? AND reading_ts = ?"
    results = execute_query(query, (device_id, reading_ts))
    return results[0] if results else None

def get_device_readings(device_id: int, limit: int = 100, 
                       start_ts: Optional[str] = None, 
                       end_ts: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get readings for a specific spore device with optional time range filtering.
    
    Args:
        device_id (int): ID of the spore device
        limit (int, optional): Maximum number of readings to return
        start_ts (str, optional): Start timestamp for filtering
        end_ts (str, optional): End timestamp for filtering
        
    Returns:
        List[Dict[str, Any]]: List of reading records
    """
    query = "SELECT * FROM readings_spore WHERE device_id = ?"
    params = [device_id]
    
    if start_ts:
        query += " AND reading_ts >= ?"
        params.append(start_ts)
    
    if end_ts:
        query += " AND reading_ts <= ?"
        params.append(end_ts)
    
    query += " ORDER BY reading_ts DESC LIMIT ?"
    params.append(limit)
    
    return execute_query(query, tuple(params))

def update_reading(device_id: int, reading_ts: str, co2: Optional[float] = None,
                  humidity: Optional[float] = None, temp: Optional[float] = None,
                  spore_ts: Optional[str] = None) -> int:
    """
    Update a spore reading record.
    
    Args:
        device_id (int): ID of the spore device
        reading_ts (str): Timestamp of the reading
        co2 (float, optional): New CO2 level reading
        humidity (float, optional): New humidity level reading
        temp (float, optional): New temperature reading
        spore_ts (str, optional): New original timestamp from the spore device
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []
    
    if co2 is not None:
        update_fields.append("co2 = ?")
        params.append(co2)
    
    if humidity is not None:
        update_fields.append("humidity = ?")
        params.append(humidity)
    
    if temp is not None:
        update_fields.append("temp = ?")
        params.append(temp)
    
    if spore_ts is not None:
        update_fields.append("spore_ts = ?")
        params.append(spore_ts)
    
    if not update_fields:
        return 0  # Nothing to update
    
    # Add device_id and reading_ts to params
    params.append(device_id)
    params.append(reading_ts)
    
    query = f"""
    UPDATE readings_spore
    SET {', '.join(update_fields)}
    WHERE device_id = ? AND reading_ts = ?
    """
    
    return execute_update(query, tuple(params))

def delete_reading(device_id: int, reading_ts: str) -> int:
    """
    Delete a spore reading record.
    
    Args:
        device_id (int): ID of the spore device
        reading_ts (str): Timestamp of the reading
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM readings_spore WHERE device_id = ? AND reading_ts = ?"
    return execute_update(query, (device_id, reading_ts))

def delete_device_readings(device_id: int,
                          start_ts: Optional[str] = None,
                          end_ts: Optional[str] = None) -> int:
    """
    Delete multiple readings for a specific spore device with optional time range filtering.

    Args:
        device_id (int): ID of the spore device
        start_ts (str, optional): Start timestamp for filtering
        end_ts (str, optional): End timestamp for filtering

    Returns:
        int: Number of rows affected
    """
    query = "DELETE FROM readings_spore WHERE device_id = ?"
    params = [device_id]

    if start_ts:
        query += " AND reading_ts >= ?"
        params.append(start_ts)

    if end_ts:
        query += " AND reading_ts <= ?"
        params.append(end_ts)

    return execute_update(query, tuple(params))


def get_latest_reading(device_id: int) -> Optional[Dict[str, Any]]:
    """
    Get the most recent reading for a spore device.

    Args:
        device_id (int): ID of the spore device

    Returns:
        Optional[Dict[str, Any]]: Latest reading data or None if no readings exist
    """
    query = """
    SELECT * FROM readings_spore
    WHERE device_id = ?
    ORDER BY reading_ts DESC
    LIMIT 1
    """
    results = execute_query(query, (device_id,))
    return results[0] if results else None
