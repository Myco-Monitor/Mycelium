"""
Schedule Settings Table Module for Mycelium

This module provides functions for interacting with the schedule_settings table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Tuple, Any

from storage.db_utils import (
    execute_query,
    execute_insert,
    execute_update,
    get_timestamp,
)


def create_schedule_setting(
    device_id: int,
    group_num: int,
    on_time: Optional[str] = None,
    off_time: Optional[str] = None,
) -> Tuple[int, int]:
    """
    Create a new schedule setting record.

    Args:
        device_id (int): ID of the hyphae device
        group_num (int): Group number for the schedule
        on_time (str, optional): Time to turn on the relay group (format: HH:MM)
        off_time (str, optional): Time to turn off the relay group (format: HH:MM)

    Returns:
        Tuple[int, int]: Tuple of device_id and group_num of the newly created setting
    """
    query = """
    INSERT INTO schedule_settings (device_id, group_num, on_time, off_time)
    VALUES (?, ?, ?, ?)
    """
    execute_insert(query, (device_id, group_num, on_time, off_time))
    return (device_id, group_num)


def get_schedule_setting(device_id: int, group_num: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific schedule setting by device_id and group_num.

    Args:
        device_id (int): ID of the hyphae device
        group_num (int): Group number for the schedule

    Returns:
        Optional[Dict[str, Any]]: Schedule setting data or None if not found
    """
    query = "SELECT * FROM schedule_settings WHERE device_id = ? AND group_num = ?"
    results = execute_query(query, (device_id, group_num))
    return results[0] if results else None


def get_device_schedule_settings(device_id: int) -> List[Dict[str, Any]]:
    """
    Get all schedule settings for a specific device.

    Args:
        device_id (int): ID of the hyphae device

    Returns:
        List[Dict[str, Any]]: List of schedule setting records
    """
    query = "SELECT * FROM schedule_settings WHERE device_id = ? ORDER BY group_num"
    return execute_query(query, (device_id,))


def update_schedule_setting(
    device_id: int,
    group_num: int,
    on_time: Optional[str] = None,
    off_time: Optional[str] = None,
) -> int:
    """
    Update a schedule setting record.

    Args:
        device_id (int): ID of the hyphae device
        group_num (int): Group number for the schedule
        on_time (str, optional): New time to turn on the relay group
        off_time (str, optional): New time to turn off the relay group

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []

    if on_time is not None:
        update_fields.append("on_time = ?")
        params.append(on_time)

    if off_time is not None:
        update_fields.append("off_time = ?")
        params.append(off_time)

    if not update_fields:
        return 0  # Nothing to update

    # Add updated_at timestamp
    update_fields.append("updated_at = ?")
    params.append(get_timestamp())

    # Add device_id and group_num to params
    params.append(device_id)
    params.append(group_num)

    query = f"""
    UPDATE schedule_settings
    SET {", ".join(update_fields)}
    WHERE device_id = ? AND group_num = ?
    """

    return execute_update(query, tuple(params))


def delete_schedule_setting(device_id: int, group_num: int) -> int:
    """
    Delete a schedule setting record.

    Args:
        device_id (int): ID of the hyphae device
        group_num (int): Group number for the schedule

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM schedule_settings WHERE device_id = ? AND group_num = ?"
    return execute_update(query, (device_id, group_num))


def delete_device_schedule_settings(device_id: int) -> int:
    """
    Delete all schedule settings for a specific device.

    Args:
        device_id (int): ID of the hyphae device

    Returns:
        int: Number of rows affected
    """
    query = "DELETE FROM schedule_settings WHERE device_id = ?"
    return execute_update(query, (device_id,))
