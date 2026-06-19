"""
Readings Hyphae Table Module for Mycelium

This module provides functions for interacting with the readings_hyphae table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Tuple, Any

from storage.db_utils import execute_query, execute_insert, execute_update


def create_reading(
    device_id: int,
    reading_ts: str,
    relay_number: int,
    relay_state: int,
    cooldown: Optional[int] = None,
    testing: int = 0,
    hyphae_ts: Optional[str] = None,
) -> Tuple[int, str, int]:
    """
    Create a new hyphae device reading record.

    Args:
        device_id (int): ID of the hyphae device
        reading_ts (str): Timestamp of the reading
        relay_number (int): Number of the relay
        relay_state (int): State of the relay (0=off, 1=on)
        cooldown (int, optional): Cooldown period in seconds
        testing (int, optional): Whether this is a test reading (0=no, 1=yes)
        hyphae_ts (str, optional): Original timestamp from the hyphae device

    Returns:
        Tuple[int, str, int]: Tuple of device_id, reading_ts, and relay_number of the newly created reading
    """
    query = """
    INSERT INTO readings_hyphae (device_id, reading_ts, relay_number, relay_state, 
                               cooldown, testing, hyphae_ts)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    execute_insert(
        query,
        (
            device_id,
            reading_ts,
            relay_number,
            relay_state,
            cooldown,
            testing,
            hyphae_ts,
        ),
    )
    return (device_id, reading_ts, relay_number)


def get_reading(
    device_id: int, reading_ts: str, relay_number: int
) -> Optional[Dict[str, Any]]:
    """
    Get a specific hyphae reading by device_id, timestamp, and relay_number.

    Args:
        device_id (int): ID of the hyphae device
        reading_ts (str): Timestamp of the reading
        relay_number (int): Number of the relay

    Returns:
        Optional[Dict[str, Any]]: Reading data or None if not found
    """
    query = """
    SELECT * FROM readings_hyphae 
    WHERE device_id = ? AND reading_ts = ? AND relay_number = ?
    """
    results = execute_query(query, (device_id, reading_ts, relay_number))
    return results[0] if results else None


def get_device_readings(
    device_id: int,
    relay_number: Optional[int] = None,
    limit: int = 100,
    start_ts: Optional[str] = None,
    end_ts: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get readings for a specific hyphae device with optional relay and time range filtering.

    Args:
        device_id (int): ID of the hyphae device
        relay_number (int, optional): If provided, filter by specific relay number
        limit (int, optional): Maximum number of readings to return
        start_ts (str, optional): Start timestamp for filtering
        end_ts (str, optional): End timestamp for filtering

    Returns:
        List[Dict[str, Any]]: List of reading records
    """
    query = "SELECT * FROM readings_hyphae WHERE device_id = ?"
    params = [device_id]

    if relay_number is not None:
        query += " AND relay_number = ?"
        params.append(relay_number)

    if start_ts:
        query += " AND reading_ts >= ?"
        params.append(start_ts)

    if end_ts:
        query += " AND reading_ts <= ?"
        params.append(end_ts)

    query += " ORDER BY reading_ts DESC LIMIT ?"
    params.append(limit)

    return execute_query(query, tuple(params))


def get_relay_state_history(
    device_id: int, relay_number: int, limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get the history of state changes for a specific relay.

    Args:
        device_id (int): ID of the hyphae device
        relay_number (int): Number of the relay
        limit (int, optional): Maximum number of records to return

    Returns:
        List[Dict[str, Any]]: List of relay state change records
    """
    query = """
    SELECT * FROM readings_hyphae 
    WHERE device_id = ? AND relay_number = ?
    ORDER BY reading_ts DESC LIMIT ?
    """
    return execute_query(query, (device_id, relay_number, limit))


def update_reading(
    device_id: int,
    reading_ts: str,
    relay_number: int,
    relay_state: Optional[int] = None,
    cooldown: Optional[int] = None,
    testing: Optional[int] = None,
    hyphae_ts: Optional[str] = None,
) -> int:
    """
    Update a hyphae reading record.

    Args:
        device_id (int): ID of the hyphae device
        reading_ts (str): Timestamp of the reading
        relay_number (int): Number of the relay
        relay_state (int, optional): New state of the relay
        cooldown (int, optional): New cooldown period
        testing (int, optional): New testing flag
        hyphae_ts (str, optional): New original timestamp from the hyphae device

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []

    if relay_state is not None:
        update_fields.append("relay_state = ?")
        params.append(relay_state)

    if cooldown is not None:
        update_fields.append("cooldown = ?")
        params.append(cooldown)

    if testing is not None:
        update_fields.append("testing = ?")
        params.append(testing)

    if hyphae_ts is not None:
        update_fields.append("hyphae_ts = ?")
        params.append(hyphae_ts)

    if not update_fields:
        return 0  # Nothing to update

    # Add device_id, reading_ts, and relay_number to params
    params.append(device_id)
    params.append(reading_ts)
    params.append(relay_number)

    query = f"""
    UPDATE readings_hyphae
    SET {", ".join(update_fields)}
    WHERE device_id = ? AND reading_ts = ? AND relay_number = ?
    """

    return execute_update(query, tuple(params))


def delete_reading(device_id: int, reading_ts: str, relay_number: int) -> int:
    """
    Delete a hyphae reading record.

    Args:
        device_id (int): ID of the hyphae device
        reading_ts (str): Timestamp of the reading
        relay_number (int): Number of the relay

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    DELETE FROM readings_hyphae 
    WHERE device_id = ? AND reading_ts = ? AND relay_number = ?
    """
    return execute_update(query, (device_id, reading_ts, relay_number))


def delete_device_readings(
    device_id: int,
    relay_number: Optional[int] = None,
    start_ts: Optional[str] = None,
    end_ts: Optional[str] = None,
) -> int:
    """
    Delete multiple readings for a specific hyphae device with optional relay and time range filtering.

    Args:
        device_id (int): ID of the hyphae device
        relay_number (int, optional): If provided, filter by specific relay number
        start_ts (str, optional): Start timestamp for filtering
        end_ts (str, optional): End timestamp for filtering

    Returns:
        int: Number of rows affected
    """
    query = "DELETE FROM readings_hyphae WHERE device_id = ?"
    params = [device_id]

    if relay_number is not None:
        query += " AND relay_number = ?"
        params.append(relay_number)

    if start_ts:
        query += " AND reading_ts >= ?"
        params.append(start_ts)

    if end_ts:
        query += " AND reading_ts <= ?"
        params.append(end_ts)

    return execute_update(query, tuple(params))


def get_latest_reading(device_id: int) -> Optional[Dict[str, Any]]:
    """
    Get the most recent reading for a hyphae device.

    Args:
        device_id (int): ID of the hyphae device

    Returns:
        Optional[Dict[str, Any]]: Latest reading data or None if no readings exist
    """
    query = """
    SELECT * FROM readings_hyphae
    WHERE device_id = ?
    ORDER BY reading_ts DESC
    LIMIT 1
    """
    results = execute_query(query, (device_id,))
    return results[0] if results else None
