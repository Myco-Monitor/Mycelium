"""
Dynamic Settings Table Module for Mycelium

This module provides functions for interacting with the dynamic_settings table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Tuple, Any

from storage.db_utils import (
    execute_query,
    execute_insert,
    execute_update,
    get_timestamp,
)


def create_dynamic_setting(
    device_id: int,
    group_num: int,
    parameter: str,
    low_threshold: float,
    high_threshold: float,
    behavior: int,
) -> Tuple[int, int, str]:
    """
    Create a new dynamic setting record.

    Args:
        device_id (int): ID of the hyphae device
        group_num (int): Group number for the setting
        parameter (str): Parameter being monitored (e.g., 'temperature', 'humidity')
        low_threshold (float): Low threshold value
        high_threshold (float): High threshold value
        behavior (int): Behavior code for the setting

    Returns:
        Tuple[int, int, str]: Tuple of device_id, group_num, and parameter of the newly created setting
    """
    query = """
    INSERT INTO dynamic_settings (device_id, group_num, parameter, low_threshold, high_threshold, behavior)
    VALUES (?, ?, ?, ?, ?, ?)
    """
    execute_insert(
        query,
        (device_id, group_num, parameter, low_threshold, high_threshold, behavior),
    )
    return (device_id, group_num, parameter)


def get_dynamic_setting(
    device_id: int, group_num: int, parameter: str
) -> Optional[Dict[str, Any]]:
    """
    Get a specific dynamic setting by device_id, group_num, and parameter.

    Args:
        device_id (int): ID of the hyphae device
        group_num (int): Group number for the setting
        parameter (str): Parameter being monitored

    Returns:
        Optional[Dict[str, Any]]: Dynamic setting data or None if not found
    """
    query = """
    SELECT * FROM dynamic_settings 
    WHERE device_id = ? AND group_num = ? AND parameter = ?
    """
    results = execute_query(query, (device_id, group_num, parameter))
    return results[0] if results else None


def get_device_dynamic_settings(device_id: int) -> List[Dict[str, Any]]:
    """
    Get all dynamic settings for a specific device.

    Args:
        device_id (int): ID of the hyphae device

    Returns:
        List[Dict[str, Any]]: List of dynamic setting records
    """
    query = """
    SELECT * FROM dynamic_settings 
    WHERE device_id = ? 
    ORDER BY group_num, parameter
    """
    return execute_query(query, (device_id,))


def get_group_dynamic_settings(device_id: int, group_num: int) -> List[Dict[str, Any]]:
    """
    Get all dynamic settings for a specific group in a device.

    Args:
        device_id (int): ID of the hyphae device
        group_num (int): Group number to filter by

    Returns:
        List[Dict[str, Any]]: List of dynamic setting records in the group
    """
    query = """
    SELECT * FROM dynamic_settings 
    WHERE device_id = ? AND group_num = ? 
    ORDER BY parameter
    """
    return execute_query(query, (device_id, group_num))


def get_parameter_dynamic_settings(
    device_id: int, parameter: str
) -> List[Dict[str, Any]]:
    """
    Get all dynamic settings for a specific parameter in a device.

    Args:
        device_id (int): ID of the hyphae device
        parameter (str): Parameter to filter by

    Returns:
        List[Dict[str, Any]]: List of dynamic setting records for the parameter
    """
    query = """
    SELECT * FROM dynamic_settings 
    WHERE device_id = ? AND parameter = ? 
    ORDER BY group_num
    """
    return execute_query(query, (device_id, parameter))


def update_dynamic_setting(
    device_id: int,
    group_num: int,
    parameter: str,
    low_threshold: Optional[float] = None,
    high_threshold: Optional[float] = None,
    behavior: Optional[int] = None,
) -> int:
    """
    Update a dynamic setting record.

    Args:
        device_id (int): ID of the hyphae device
        group_num (int): Group number for the setting
        parameter (str): Parameter being monitored
        low_threshold (float, optional): New low threshold value
        high_threshold (float, optional): New high threshold value
        behavior (int, optional): New behavior code

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []

    if low_threshold is not None:
        update_fields.append("low_threshold = ?")
        params.append(low_threshold)

    if high_threshold is not None:
        update_fields.append("high_threshold = ?")
        params.append(high_threshold)

    if behavior is not None:
        update_fields.append("behavior = ?")
        params.append(behavior)

    if not update_fields:
        return 0  # Nothing to update

    # Add updated_at timestamp
    update_fields.append("updated_at = ?")
    params.append(get_timestamp())

    # Add device_id, group_num, and parameter to params
    params.append(device_id)
    params.append(group_num)
    params.append(parameter)

    query = f"""
    UPDATE dynamic_settings
    SET {", ".join(update_fields)}
    WHERE device_id = ? AND group_num = ? AND parameter = ?
    """

    return execute_update(query, tuple(params))


def delete_dynamic_setting(device_id: int, group_num: int, parameter: str) -> int:
    """
    Delete a dynamic setting record.

    Args:
        device_id (int): ID of the hyphae device
        group_num (int): Group number for the setting
        parameter (str): Parameter being monitored

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    DELETE FROM dynamic_settings 
    WHERE device_id = ? AND group_num = ? AND parameter = ?
    """
    return execute_update(query, (device_id, group_num, parameter))


def delete_device_dynamic_settings(device_id: int) -> int:
    """
    Delete all dynamic settings for a specific device.

    Args:
        device_id (int): ID of the hyphae device

    Returns:
        int: Number of rows affected
    """
    query = "DELETE FROM dynamic_settings WHERE device_id = ?"
    return execute_update(query, (device_id,))


def delete_group_dynamic_settings(device_id: int, group_num: int) -> int:
    """
    Delete all dynamic settings for a specific group in a device.

    Args:
        device_id (int): ID of the hyphae device
        group_num (int): Group number to filter by

    Returns:
        int: Number of rows affected
    """
    query = "DELETE FROM dynamic_settings WHERE device_id = ? AND group_num = ?"
    return execute_update(query, (device_id, group_num))


def delete_parameter_dynamic_settings(device_id: int, parameter: str) -> int:
    """
    Delete all dynamic settings for a specific parameter in a device.

    Args:
        device_id (int): ID of the hyphae device
        parameter (str): Parameter to filter by

    Returns:
        int: Number of rows affected
    """
    query = "DELETE FROM dynamic_settings WHERE device_id = ? AND parameter = ?"
    return execute_update(query, (device_id, parameter))
