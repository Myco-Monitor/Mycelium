"""
Readings Weather Table Module for Mycelium

This module provides functions for interacting with the readings_weather table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Tuple, Any

from storage.db_utils import execute_query, execute_insert, execute_update


def create_reading(
    device_id: int,
    reading_ts: str,
    current_temp: Optional[float] = None,
    feels_like: Optional[float] = None,
    humidity: Optional[float] = None,
    ambient_pressure: Optional[float] = None,
) -> Tuple[int, str]:
    """
    Create a new weather reading record.

    Args:
        device_id (int): ID of the device
        reading_ts (str): Timestamp of the reading
        current_temp (float, optional): Current temperature reading
        feels_like (float, optional): Feels like temperature reading
        humidity (float, optional): Humidity level reading
        ambient_pressure (float, optional): Ambient pressure reading

    Returns:
        Tuple[int, str]: Tuple of device_id and reading_ts of the newly created reading
    """
    query = """
    INSERT INTO readings_weather (device_id, reading_ts, current_temp, feels_like, 
                                humidity, ambient_pressure)
    VALUES (?, ?, ?, ?, ?, ?)
    """
    execute_insert(
        query,
        (device_id, reading_ts, current_temp, feels_like, humidity, ambient_pressure),
    )
    return (device_id, reading_ts)


def get_reading(device_id: int, reading_ts: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific weather reading by device_id and timestamp.

    Args:
        device_id (int): ID of the device
        reading_ts (str): Timestamp of the reading

    Returns:
        Optional[Dict[str, Any]]: Reading data or None if not found
    """
    query = "SELECT * FROM readings_weather WHERE device_id = ? AND reading_ts = ?"
    results = execute_query(query, (device_id, reading_ts))
    return results[0] if results else None


def get_device_readings(
    device_id: int,
    limit: int = 100,
    start_ts: Optional[str] = None,
    end_ts: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get weather readings for a specific device with optional time range filtering.

    Args:
        device_id (int): ID of the device
        limit (int, optional): Maximum number of readings to return
        start_ts (str, optional): Start timestamp for filtering
        end_ts (str, optional): End timestamp for filtering

    Returns:
        List[Dict[str, Any]]: List of reading records
    """
    query = "SELECT * FROM readings_weather WHERE device_id = ?"
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


def get_latest_weather(device_id: int) -> Optional[Dict[str, Any]]:
    """
    Get the most recent weather reading for a specific device.

    Args:
        device_id (int): ID of the device

    Returns:
        Optional[Dict[str, Any]]: Most recent reading data or None if not found
    """
    query = """
    SELECT * FROM readings_weather 
    WHERE device_id = ? 
    ORDER BY reading_ts DESC 
    LIMIT 1
    """
    results = execute_query(query, (device_id,))
    return results[0] if results else None


def update_reading(
    device_id: int,
    reading_ts: str,
    current_temp: Optional[float] = None,
    feels_like: Optional[float] = None,
    humidity: Optional[float] = None,
    ambient_pressure: Optional[float] = None,
) -> int:
    """
    Update a weather reading record.

    Args:
        device_id (int): ID of the device
        reading_ts (str): Timestamp of the reading
        current_temp (float, optional): New current temperature reading
        feels_like (float, optional): New feels like temperature reading
        humidity (float, optional): New humidity level reading
        ambient_pressure (float, optional): New ambient pressure reading

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []

    if current_temp is not None:
        update_fields.append("current_temp = ?")
        params.append(current_temp)

    if feels_like is not None:
        update_fields.append("feels_like = ?")
        params.append(feels_like)

    if humidity is not None:
        update_fields.append("humidity = ?")
        params.append(humidity)

    if ambient_pressure is not None:
        update_fields.append("ambient_pressure = ?")
        params.append(ambient_pressure)

    if not update_fields:
        return 0  # Nothing to update

    # Add device_id and reading_ts to params
    params.append(device_id)
    params.append(reading_ts)

    query = f"""
    UPDATE readings_weather
    SET {", ".join(update_fields)}
    WHERE device_id = ? AND reading_ts = ?
    """

    return execute_update(query, tuple(params))


def delete_reading(device_id: int, reading_ts: str) -> int:
    """
    Delete a weather reading record.

    Args:
        device_id (int): ID of the device
        reading_ts (str): Timestamp of the reading

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM readings_weather WHERE device_id = ? AND reading_ts = ?"
    return execute_update(query, (device_id, reading_ts))


def delete_device_readings(
    device_id: int, start_ts: Optional[str] = None, end_ts: Optional[str] = None
) -> int:
    """
    Delete multiple weather readings for a specific device with optional time range filtering.

    Args:
        device_id (int): ID of the device
        start_ts (str, optional): Start timestamp for filtering
        end_ts (str, optional): End timestamp for filtering

    Returns:
        int: Number of rows affected
    """
    query = "DELETE FROM readings_weather WHERE device_id = ?"
    params = [device_id]

    if start_ts:
        query += " AND reading_ts >= ?"
        params.append(start_ts)

    if end_ts:
        query += " AND reading_ts <= ?"
        params.append(end_ts)

    return execute_update(query, tuple(params))
