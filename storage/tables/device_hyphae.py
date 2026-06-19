"""
Device Hyphae Table Module for Mycelium

This module provides functions for interacting with the device_hyphae table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Any

from storage.db_utils import (
    execute_query,
    execute_insert,
    execute_update,
    get_timestamp,
)


def create_device_hyphae(
    room_id: int,
    device_name: str,
    hostname: str,
    mac_address: str,
    mode_enabled: int = 0,
    mode_operation: int = 0,
    firmware_version: Optional[str] = None,
    is_online: int = 0,
) -> int:
    """
    Create a new device_hyphae record.

    Args:
        room_id (int): ID of the grow room this device belongs to
        device_name (str): Name of the device
        hostname (str): IP address of the device
        mac_address (str): MAC address of the device (must be unique)
        mode_enabled (int, optional): Whether the device mode is enabled (0=disabled, 1=enabled)
        mode_operation (int, optional): Operation mode of the device (0=default)
        firmware_version (str, optional): Version of the firmware running on the device
        is_online (int, optional): Whether the device is currently online (0=offline, 1=online)

    Returns:
        int: ID of the newly created device
    """
    query = """
    INSERT INTO device_hyphae (room_id, device_name, hostname, mac_address, 
                              mode_enabled, mode_operation, firmware_version, is_online)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    return execute_insert(
        query,
        (
            room_id,
            device_name,
            hostname,
            mac_address,
            mode_enabled,
            mode_operation,
            firmware_version,
            is_online,
        ),
    )


def get_device_hyphae(device_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a device_hyphae by ID.

    Args:
        device_id (int): ID of the device to retrieve

    Returns:
        Optional[Dict[str, Any]]: Device data or None if not found
    """
    query = "SELECT * FROM device_hyphae WHERE device_id = ?"
    results = execute_query(query, (device_id,))
    return results[0] if results else None


def get_device_hyphae_by_mac(mac_address: str) -> Optional[Dict[str, Any]]:
    """
    Get a device_hyphae by MAC address.

    Args:
        mac_address (str): MAC address of the device to retrieve

    Returns:
        Optional[Dict[str, Any]]: Device data or None if not found
    """
    query = "SELECT * FROM device_hyphae WHERE mac_address = ?"
    results = execute_query(query, (mac_address,))
    return results[0] if results else None


def get_device_hyphae_by_hostname(hostname: str) -> Optional[Dict[str, Any]]:
    """
    Get a device_hyphae by IP address.

    Args:
        hostname (str): IP address of the device to retrieve

    Returns:
        Optional[Dict[str, Any]]: Device data or None if not found
    """
    query = "SELECT * FROM device_hyphae WHERE hostname = ?"
    results = execute_query(query, (hostname,))
    return results[0] if results else None


def get_all_device_hyphae(
    room_id: Optional[int] = None, active_only: bool = True
) -> List[Dict[str, Any]]:
    """
    Get all device_hyphae records with room names, optionally filtering by room ID and active status.

    Args:
        room_id (int, optional): If provided, filter devices by room ID
        active_only (bool): If True, return only active devices

    Returns:
        List[Dict[str, Any]]: List of device records with room names
    """
    query = """
    SELECT dh.*, gr.room_name, gr.farm_id
    FROM device_hyphae dh
    LEFT JOIN grow_rooms gr ON dh.room_id = gr.room_id
    """
    conditions = []
    params = []

    if room_id is not None:
        conditions.append("dh.room_id = ?")
        params.append(room_id)

    if active_only:
        conditions.append("dh.active = 1")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY dh.device_name"
    return execute_query(query, tuple(params))


def update_device_hyphae(
    device_id: int,
    device_name: Optional[str] = None,
    hostname: Optional[str] = None,
    firmware_version: Optional[str] = None,
    mode_enabled: Optional[int] = None,
    mode_operation: Optional[int] = None,
) -> int:
    """
    Update a device_hyphae record.

    Args:
        device_id (int): ID of the device to update
        device_name (str, optional): New name for the device
        hostname (str, optional): New IP address for the device
        firmware_version (str, optional): New firmware version for the device
        mode_enabled (int, optional): New mode enabled status (0=disabled, 1=enabled)
        mode_operation (int, optional): New operation mode

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []

    if device_name is not None:
        update_fields.append("device_name = ?")
        params.append(device_name)

    if hostname is not None:
        update_fields.append("hostname = ?")
        params.append(hostname)

    if firmware_version is not None:
        update_fields.append("firmware_version = ?")
        params.append(firmware_version)

    if mode_enabled is not None:
        update_fields.append("mode_enabled = ?")
        params.append(mode_enabled)

    if mode_operation is not None:
        update_fields.append("mode_operation = ?")
        params.append(mode_operation)

    # Add updated_at timestamp
    update_fields.append("updated_at = ?")
    params.append(get_timestamp())

    # Add device_id to params
    params.append(device_id)

    if not update_fields:
        return 0  # Nothing to update

    query = f"""
    UPDATE device_hyphae
    SET {", ".join(update_fields)}
    WHERE device_id = ?
    """

    return execute_update(query, tuple(params))


def update_device_status(
    device_id: int, is_online: int, last_update: Optional[str] = None
) -> int:
    """
    Update a device's online status and last update time.

    Args:
        device_id (int): ID of the device to update
        is_online (int): New online status (0=offline, 1=online)
        last_update (str, optional): Timestamp of the last update. If None, current time is used.

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    if last_update is None:
        last_update = get_timestamp()

    query = """
    UPDATE device_hyphae
    SET is_online = ?, last_update = ?, updated_at = ?
    WHERE device_id = ?
    """
    return execute_update(query, (is_online, last_update, get_timestamp(), device_id))


def deactivate_device_hyphae(device_id: int, reason: Optional[str] = None) -> int:
    """
    Deactivate a device_hyphae.

    Args:
        device_id (int): ID of the device to deactivate
        reason (str, optional): Reason for deactivation

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE device_hyphae
    SET active = 0, deactivation_reason = ?, updated_at = ?
    WHERE device_id = ?
    """
    return execute_update(query, (reason, get_timestamp(), device_id))


def reactivate_device_hyphae(device_id: int) -> int:
    """
    Reactivate a previously deactivated device_hyphae.

    Args:
        device_id (int): ID of the device to reactivate

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE device_hyphae
    SET active = 1, deactivation_reason = NULL, updated_at = ?
    WHERE device_id = ?
    """
    return execute_update(query, (get_timestamp(), device_id))


def delete_device_hyphae(device_id: int) -> int:
    """
    Delete a device_hyphae record.

    Note: This is a hard delete and should be used with caution.
    Consider using deactivate_device_hyphae instead for most cases.

    Args:
        device_id (int): ID of the device to delete

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM device_hyphae WHERE device_id = ?"
    return execute_update(query, (device_id,))


def get_devices_by_farm(farm_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
    """
    Get all Hyphae devices belonging to a specific farm.

    Args:
        farm_id (int): ID of the farm
        active_only (bool): If True, return only active devices

    Returns:
        List[Dict[str, Any]]: List of device records
    """
    query = """
    SELECT dh.*, gr.room_name, f.farm_name
    FROM device_hyphae dh
    JOIN grow_rooms gr ON dh.room_id = gr.room_id
    JOIN farms f ON gr.farm_id = f.farm_id
    WHERE f.farm_id = ?
    """

    if active_only:
        query += " AND dh.active = 1"

    query += " ORDER BY dh.device_name"
    return execute_query(query, (farm_id,))


def get_all_devices(active_only: bool = True) -> List[Dict[str, Any]]:
    """
    Alias for get_all_device_hyphae for consistent naming.

    Args:
        active_only (bool): If True, return only active devices

    Returns:
        List[Dict[str, Any]]: List of device records with room names
    """
    return get_all_device_hyphae(active_only=active_only)
