"""
Device Sentinel Table Module for Mycelium

This module provides functions for interacting with the device_sentinel table
in the Mycelium database.

A Sentinel is the grower-environment air-quality monitor (SEN66 PM/VOC/NOx/
CO2/T/RH + BMP581 pressure). It usually sits outside any grow tent, so its
room assignment is optional (room_id may be NULL).
"""

from typing import Dict, List, Optional, Any

from storage.db_utils import (
    execute_query,
    execute_insert,
    execute_update,
    get_timestamp,
)
from storage.tables.device_spore import normalize_device_host


def create_device_sentinel(
    device_name: str,
    hostname: str,
    mac_address: str,
    room_id: Optional[int] = None,
    firmware_version: Optional[str] = None,
    is_online: int = 0,
) -> int:
    """
    Create a new device_sentinel record.

    Args:
        device_name (str): Name of the device
        hostname (str): mDNS hostname (sentinel-NNNN.local) or host:port
        mac_address (str): MAC address of the device (must be unique)
        room_id (int, optional): Grow room this device is associated with, if any
        firmware_version (str, optional): Version of the firmware running on the device
        is_online (int, optional): Whether the device is currently online (0=offline, 1=online)

    Returns:
        int: ID of the newly created device
    """
    hostname = normalize_device_host(hostname)
    query = """
    INSERT INTO device_sentinel (device_name, room_id, hostname, mac_address,
                                 firmware_version, is_online)
    VALUES (?, ?, ?, ?, ?, ?)
    """
    return execute_insert(
        query,
        (device_name, room_id, hostname, mac_address, firmware_version, is_online),
    )


def get_device_sentinel(device_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a device_sentinel by ID.

    Args:
        device_id (int): ID of the device to retrieve

    Returns:
        Optional[Dict[str, Any]]: Device data or None if not found
    """
    query = "SELECT * FROM device_sentinel WHERE device_id = ?"
    results = execute_query(query, (device_id,))
    return results[0] if results else None


def get_device_sentinel_by_mac(mac_address: str) -> Optional[Dict[str, Any]]:
    """
    Get a device_sentinel by MAC address.

    Args:
        mac_address (str): MAC address of the device to retrieve

    Returns:
        Optional[Dict[str, Any]]: Device data or None if not found
    """
    query = "SELECT * FROM device_sentinel WHERE mac_address = ?"
    results = execute_query(query, (mac_address,))
    return results[0] if results else None


def get_device_sentinel_by_hostname(hostname: str) -> Optional[Dict[str, Any]]:
    """
    Get a device_sentinel by hostname.

    Args:
        hostname (str): Hostname of the device to retrieve

    Returns:
        Optional[Dict[str, Any]]: Device data or None if not found
    """
    query = "SELECT * FROM device_sentinel WHERE hostname = ?"
    results = execute_query(query, (hostname,))
    return results[0] if results else None


def get_all_device_sentinel(
    room_id: Optional[int] = None,
    active_only: bool = True,
) -> List[Dict[str, Any]]:
    """
    Get all device_sentinel records with room names, optionally filtered.

    Args:
        room_id (int, optional): If provided, filter devices by room ID
        active_only (bool): If True, return only active devices

    Returns:
        List[Dict[str, Any]]: List of device records with room_name/farm_id
            (both None for a Sentinel with no room assigned)
    """
    query = """
    SELECT dsn.*, gr.room_name, gr.farm_id
    FROM device_sentinel dsn
    LEFT JOIN grow_rooms gr ON dsn.room_id = gr.room_id
    """
    conditions = []
    params = []

    if room_id is not None:
        conditions.append("dsn.room_id = ?")
        params.append(room_id)

    if active_only:
        conditions.append("dsn.active = 1")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY dsn.device_name"
    return execute_query(query, tuple(params))


def update_device_sentinel(
    device_id: int,
    device_name: Optional[str] = None,
    hostname: Optional[str] = None,
    firmware_version: Optional[str] = None,
) -> int:
    """
    Update a device_sentinel record.

    Args:
        device_id (int): ID of the device to update
        device_name (str, optional): New name for the device
        hostname (str, optional): New hostname for the device
        firmware_version (str, optional): New firmware version for the device

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    update_fields = []
    params = []

    if device_name is not None:
        update_fields.append("device_name = ?")
        params.append(device_name)

    if hostname is not None:
        update_fields.append("hostname = ?")
        params.append(normalize_device_host(hostname))

    if firmware_version is not None:
        update_fields.append("firmware_version = ?")
        params.append(firmware_version)

    if not update_fields:
        return 0  # Nothing to update

    # device_sentinel uses created_at as its updated_at marker (like device_spore)
    update_fields.append("created_at = ?")
    params.append(get_timestamp())
    params.append(device_id)

    query = f"""
    UPDATE device_sentinel
    SET {", ".join(update_fields)}
    WHERE device_id = ?
    """
    return execute_update(query, tuple(params))


def set_device_room(device_id: int, room_id: Optional[int]) -> int:
    """
    Assign a Sentinel to a grow room, or clear the assignment with None.

    Args:
        device_id (int): ID of the device
        room_id (int, optional): Room to associate with, or None for no room

    Returns:
        int: Number of rows affected
    """
    query = """
    UPDATE device_sentinel
    SET room_id = ?, created_at = ?
    WHERE device_id = ?
    """
    return execute_update(query, (room_id, get_timestamp(), device_id))


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
    UPDATE device_sentinel
    SET is_online = ?, last_update = ?, created_at = ?
    WHERE device_id = ?
    """
    return execute_update(query, (is_online, last_update, get_timestamp(), device_id))


def set_device_online(device_id: int, is_online: int) -> int:
    """Set only the online flag, leaving last_update untouched.

    Use when marking a device offline so that last_update keeps meaning "last time
    the device was actually reachable", not last check.

    Args:
        device_id (int): ID of the device
        is_online (int): New online status (0=offline, 1=online)

    Returns:
        int: Number of rows affected
    """
    query = """
    UPDATE device_sentinel
    SET is_online = ?, created_at = ?
    WHERE device_id = ?
    """
    return execute_update(query, (is_online, get_timestamp(), device_id))


def update_device_diagnostics(
    device_id: int,
    wifi_rssi: Optional[int] = None,
    heap_free_kb: Optional[int] = None,
    heap_min_free_kb: Optional[int] = None,
    uptime_sec: Optional[int] = None,
) -> int:
    """
    Update a Sentinel's latest diagnostics snapshot (from /api/diagnostics).

    Only fields passed as non-None are written; the row's created_at marker is
    deliberately left untouched (diagnostics refreshes are not user edits).

    Args:
        device_id (int): ID of the Sentinel device
        wifi_rssi (int, optional): WiFi RSSI in dBm
        heap_free_kb (int, optional): Current free heap in KB
        heap_min_free_kb (int, optional): Minimum free heap since boot in KB
        uptime_sec (int, optional): Device uptime in seconds

    Returns:
        int: Number of rows updated
    """
    update_fields = []
    params: List[Any] = []
    for column, value in (
        ("wifi_rssi", wifi_rssi),
        ("heap_free_kb", heap_free_kb),
        ("heap_min_free_kb", heap_min_free_kb),
        ("uptime_sec", uptime_sec),
    ):
        if value is not None:
            update_fields.append(f"{column} = ?")
            params.append(value)

    if not update_fields:
        return 0

    params.append(device_id)
    query = f"""
    UPDATE device_sentinel
    SET {", ".join(update_fields)}
    WHERE device_id = ?
    """
    return execute_update(query, tuple(params))


def deactivate_device_sentinel(device_id: int, reason: Optional[str] = None) -> int:
    """
    Deactivate a device_sentinel.

    Args:
        device_id (int): ID of the device to deactivate
        reason (str, optional): Reason for deactivation

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE device_sentinel
    SET active = 0, deactivation_reason = ?, created_at = ?
    WHERE device_id = ?
    """
    return execute_update(query, (reason, get_timestamp(), device_id))


def reactivate_device_sentinel(device_id: int) -> int:
    """
    Reactivate a previously deactivated device_sentinel.

    Args:
        device_id (int): ID of the device to reactivate

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE device_sentinel
    SET active = 1, deactivation_reason = NULL, created_at = ?
    WHERE device_id = ?
    """
    return execute_update(query, (get_timestamp(), device_id))


def delete_device_sentinel(device_id: int) -> int:
    """
    Delete a device_sentinel record.

    Note: This is a hard delete and should be used with caution.
    Consider using deactivate_device_sentinel instead for most cases.

    Args:
        device_id (int): ID of the device to delete

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM device_sentinel WHERE device_id = ?"
    return execute_update(query, (device_id,))


def get_devices_by_farm(farm_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
    """
    Get all Sentinel devices belonging to a specific farm.

    Only room-assigned Sentinels belong to a farm (farms are reached through
    grow rooms); unassigned ones appear in the global list only.

    Args:
        farm_id (int): ID of the farm
        active_only (bool): If True, return only active devices

    Returns:
        List[Dict[str, Any]]: List of device records
    """
    query = """
    SELECT dsn.*, gr.room_name, f.farm_name
    FROM device_sentinel dsn
    JOIN grow_rooms gr ON dsn.room_id = gr.room_id
    JOIN farms f ON gr.farm_id = f.farm_id
    WHERE f.farm_id = ?
    """

    if active_only:
        query += " AND dsn.active = 1"

    query += " ORDER BY dsn.device_name"
    return execute_query(query, (farm_id,))


def get_all_devices(active_only: bool = True) -> List[Dict[str, Any]]:
    """
    Alias for get_all_device_sentinel for consistent naming across device tables.

    Args:
        active_only (bool): If True, return only active devices

    Returns:
        List[Dict[str, Any]]: List of device records with room names
    """
    return get_all_device_sentinel(active_only=active_only)
