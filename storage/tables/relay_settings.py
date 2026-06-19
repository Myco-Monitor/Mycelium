"""
Relay Settings Table Module for Mycelium

This module provides functions for interacting with the relay_settings table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Tuple, Any

from storage.db_utils import (
    execute_query,
    execute_insert,
    execute_update,
    get_timestamp,
)


def create_relay_setting(relay_data: Dict[str, Any]) -> Tuple[int, int]:
    """
    Create a new relay setting record.

    Args:
        relay_data (Dict[str, Any]): Dictionary containing relay setting data with keys:
            - device_id (int): ID of the hyphae device
            - relay_number (int): Number of the relay
            - group_num (int): Group number for the relay
            - relay_name (str, optional): Name for the relay

    Returns:
        Tuple[int, int]: Tuple of device_id and relay_number of the newly created setting
    """
    device_id = relay_data.get("device_id")
    relay_number = relay_data.get("relay_number")
    group_num = relay_data.get("group_num")
    relay_name = relay_data.get("relay_name")

    query = """
    INSERT INTO relay_settings (device_id, relay_number, group_num, relay_name)
    VALUES (?, ?, ?, ?)
    """
    execute_insert(query, (device_id, relay_number, group_num, relay_name))
    return (device_id, relay_number)


def get_relay_setting(device_id: int, relay_number: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific relay setting by device_id and relay_number.

    Args:
        device_id (int): ID of the hyphae device
        relay_number (int): Number of the relay

    Returns:
        Optional[Dict[str, Any]]: Relay setting data or None if not found
    """
    query = "SELECT * FROM relay_settings WHERE device_id = ? AND relay_number = ?"
    results = execute_query(query, (device_id, relay_number))
    return results[0] if results else None


def get_device_relay_settings(device_id: int) -> List[Dict[str, Any]]:
    """
    Get all relay settings for a specific device.

    Args:
        device_id (int): ID of the hyphae device

    Returns:
        List[Dict[str, Any]]: List of relay setting records
    """
    query = "SELECT * FROM relay_settings WHERE device_id = ? ORDER BY relay_number"
    return execute_query(query, (device_id,))


def get_group_relay_settings(device_id: int, group_num: int) -> List[Dict[str, Any]]:
    """
    Get all relay settings for a specific group in a device.

    Args:
        device_id (int): ID of the hyphae device
        group_num (int): Group number to filter by

    Returns:
        List[Dict[str, Any]]: List of relay setting records in the group
    """
    query = """
    SELECT * FROM relay_settings 
    WHERE device_id = ? AND group_num = ? 
    ORDER BY relay_number
    """
    return execute_query(query, (device_id, group_num))


def update_relay_setting(
    device_id: int,
    relay_number: int,
    group_num: Optional[int] = None,
    relay_name: Optional[str] = None,
) -> int:
    """
    Update a relay setting record.

    Args:
        device_id (int): ID of the hyphae device
        relay_number (int): Number of the relay
        group_num (int, optional): New group number for the relay
        relay_name (str, optional): New name for the relay

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []

    if group_num is not None:
        update_fields.append("group_num = ?")
        params.append(group_num)

    if relay_name is not None:
        update_fields.append("relay_name = ?")
        params.append(relay_name)

    if not update_fields:
        return 0  # Nothing to update

    # Add updated_at timestamp
    update_fields.append("updated_at = ?")
    params.append(get_timestamp())

    # Add device_id and relay_number to params
    params.append(device_id)
    params.append(relay_number)

    query = f"""
    UPDATE relay_settings
    SET {", ".join(update_fields)}
    WHERE device_id = ? AND relay_number = ?
    """

    return execute_update(query, tuple(params))


def delete_relay_setting(device_id: int, relay_number: int) -> int:
    """
    Delete a relay setting record.

    Args:
        device_id (int): ID of the hyphae device
        relay_number (int): Number of the relay

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM relay_settings WHERE device_id = ? AND relay_number = ?"
    return execute_update(query, (device_id, relay_number))


def delete_device_relay_settings(device_id: int) -> int:
    """
    Delete all relay settings for a specific device.

    Args:
        device_id (int): ID of the hyphae device

    Returns:
        int: Number of rows affected
    """
    query = "DELETE FROM relay_settings WHERE device_id = ?"
    return execute_update(query, (device_id,))


def delete_group_relay_settings(device_id: int, group_num: int) -> int:
    """
    Delete all relay settings for a specific group in a device.

    Args:
        device_id (int): ID of the hyphae device
        group_num (int): Group number to filter by

    Returns:
        int: Number of rows affected
    """
    query = "DELETE FROM relay_settings WHERE device_id = ? AND group_num = ?"
    return execute_update(query, (device_id, group_num))
