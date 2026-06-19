"""
Readings Pressure Table Module for Mycelium

This module provides functions for interacting with the readings_pressure table
in the Mycelium database. Stores BMP581 pressure readings from Hyphae devices.
"""

from typing import Dict, List, Optional, Tuple, Any

from storage.db_utils import execute_query, execute_insert, execute_update


def create_reading(
    hyphae_id: int,
    reading_ts: str,
    pressure_hpa: int,
    source: str = "BMP581",
    healthy: int = 1,
) -> Tuple[int, str]:
    """
    Create a new pressure reading record.

    Args:
        hyphae_id (int): ID of the Hyphae device
        reading_ts (str): Timestamp of the reading (ISO format)
        pressure_hpa (int): Pressure reading in hectopascals
        source (str, optional): Sensor source identifier (default: "BMP581")
        healthy (int, optional): Health status flag (1=healthy, 0=unhealthy)

    Returns:
        Tuple[int, str]: Tuple of hyphae_id and reading_ts of the newly created reading
    """
    query = """
    INSERT INTO readings_pressure (hyphae_id, reading_ts, pressure_hpa, source, healthy)
    VALUES (?, ?, ?, ?, ?)
    """
    execute_insert(query, (hyphae_id, reading_ts, pressure_hpa, source, healthy))
    return (hyphae_id, reading_ts)


def get_reading(hyphae_id: int, reading_ts: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific pressure reading by hyphae_id and timestamp.

    Args:
        hyphae_id (int): ID of the Hyphae device
        reading_ts (str): Timestamp of the reading

    Returns:
        Optional[Dict[str, Any]]: Reading data or None if not found
    """
    query = "SELECT * FROM readings_pressure WHERE hyphae_id = ? AND reading_ts = ?"
    results = execute_query(query, (hyphae_id, reading_ts))
    return results[0] if results else None


def get_device_readings(
    hyphae_id: int,
    limit: int = 100,
    start_ts: Optional[str] = None,
    end_ts: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get pressure readings for a specific Hyphae device with optional time range filtering.

    Args:
        hyphae_id (int): ID of the Hyphae device
        limit (int, optional): Maximum number of readings to return
        start_ts (str, optional): Start timestamp for filtering
        end_ts (str, optional): End timestamp for filtering

    Returns:
        List[Dict[str, Any]]: List of reading records
    """
    query = "SELECT * FROM readings_pressure WHERE hyphae_id = ?"
    params: List[Any] = [hyphae_id]

    if start_ts:
        query += " AND reading_ts >= ?"
        params.append(start_ts)

    if end_ts:
        query += " AND reading_ts <= ?"
        params.append(end_ts)

    query += " ORDER BY reading_ts DESC LIMIT ?"
    params.append(limit)

    return execute_query(query, tuple(params))


def get_latest_pressure(hyphae_id: int) -> Optional[Dict[str, Any]]:
    """
    Get the most recent pressure reading for a specific Hyphae device.

    Args:
        hyphae_id (int): ID of the Hyphae device

    Returns:
        Optional[Dict[str, Any]]: Most recent reading data or None if not found
    """
    query = """
    SELECT * FROM readings_pressure
    WHERE hyphae_id = ?
    ORDER BY reading_ts DESC
    LIMIT 1
    """
    results = execute_query(query, (hyphae_id,))
    return results[0] if results else None


def update_reading(
    hyphae_id: int,
    reading_ts: str,
    pressure_hpa: Optional[int] = None,
    source: Optional[str] = None,
    healthy: Optional[int] = None,
) -> int:
    """
    Update a pressure reading record.

    Args:
        hyphae_id (int): ID of the Hyphae device
        reading_ts (str): Timestamp of the reading
        pressure_hpa (int, optional): New pressure reading in hectopascals
        source (str, optional): New sensor source identifier
        healthy (int, optional): New health status flag

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    update_fields = []
    params: List[Any] = []

    if pressure_hpa is not None:
        update_fields.append("pressure_hpa = ?")
        params.append(pressure_hpa)

    if source is not None:
        update_fields.append("source = ?")
        params.append(source)

    if healthy is not None:
        update_fields.append("healthy = ?")
        params.append(healthy)

    if not update_fields:
        return 0

    params.append(hyphae_id)
    params.append(reading_ts)

    query = f"""
    UPDATE readings_pressure
    SET {", ".join(update_fields)}
    WHERE hyphae_id = ? AND reading_ts = ?
    """

    return execute_update(query, tuple(params))


def delete_reading(hyphae_id: int, reading_ts: str) -> int:
    """
    Delete a pressure reading record.

    Args:
        hyphae_id (int): ID of the Hyphae device
        reading_ts (str): Timestamp of the reading

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM readings_pressure WHERE hyphae_id = ? AND reading_ts = ?"
    return execute_update(query, (hyphae_id, reading_ts))


def delete_device_readings(
    hyphae_id: int, start_ts: Optional[str] = None, end_ts: Optional[str] = None
) -> int:
    """
    Delete multiple pressure readings for a specific Hyphae device.

    Args:
        hyphae_id (int): ID of the Hyphae device
        start_ts (str, optional): Start timestamp for filtering
        end_ts (str, optional): End timestamp for filtering

    Returns:
        int: Number of rows affected
    """
    query = "DELETE FROM readings_pressure WHERE hyphae_id = ?"
    params: List[Any] = [hyphae_id]

    if start_ts:
        query += " AND reading_ts >= ?"
        params.append(start_ts)

    if end_ts:
        query += " AND reading_ts <= ?"
        params.append(end_ts)

    return execute_update(query, tuple(params))
