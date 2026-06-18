"""
Device Spore Table Module for Mycelium

This module provides functions for interacting with the device_spore table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import sqlite3

from storage.db_utils import execute_query, execute_insert, execute_update, get_timestamp

def create_device_spore(room_id: int, device_name: str, ip_address: str, mac_address: str,
                       hyphae_id: Optional[int] = None, hyphae_present: int = 0, 
                       firmware_version: Optional[str] = None, is_online: int = 0) -> int:
    """
    Create a new device_spore record.
    
    Args:
        room_id (int): ID of the grow room this device belongs to
        device_name (str): Name of the device
        ip_address (str): IP address of the device
        mac_address (str): MAC address of the device (must be unique)
        hyphae_id (int, optional): ID of the associated hyphae device
        hyphae_present (int, optional): Whether a hyphae device is present (0=no, 1=yes)
        firmware_version (str, optional): Version of the firmware running on the device
        is_online (int, optional): Whether the device is currently online (0=offline, 1=online)
        
    Returns:
        int: ID of the newly created device
    """
    query = """
    INSERT INTO device_spore (room_id, device_name, ip_address, mac_address, 
                             hyphae_id, hyphae_present, firmware_version, is_online)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    return execute_insert(query, (room_id, device_name, ip_address, mac_address, 
                                 hyphae_id, hyphae_present, firmware_version, is_online))

def get_device_spore(device_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a device_spore by ID.
    
    Args:
        device_id (int): ID of the device to retrieve
        
    Returns:
        Optional[Dict[str, Any]]: Device data or None if not found
    """
    query = "SELECT * FROM device_spore WHERE device_id = ?"
    results = execute_query(query, (device_id,))
    return results[0] if results else None

def get_device_spore_by_mac(mac_address: str) -> Optional[Dict[str, Any]]:
    """
    Get a device_spore by MAC address.
    
    Args:
        mac_address (str): MAC address of the device to retrieve
        
    Returns:
        Optional[Dict[str, Any]]: Device data or None if not found
    """
    query = "SELECT * FROM device_spore WHERE mac_address = ?"
    results = execute_query(query, (mac_address,))
    return results[0] if results else None

def get_all_device_spore(room_id: Optional[int] = None, hyphae_id: Optional[int] = None, 
                        active_only: bool = True) -> List[Dict[str, Any]]:
    """
    Get all device_spore records with room names, optionally filtering by room ID, hyphae ID, and active status.
    
    Args:
        room_id (int, optional): If provided, filter devices by room ID
        hyphae_id (int, optional): If provided, filter devices by hyphae ID
        active_only (bool): If True, return only active devices
        
    Returns:
        List[Dict[str, Any]]: List of device records with room names
    """
    query = """
    SELECT ds.*, gr.room_name, gr.farm_id
    FROM device_spore ds
    LEFT JOIN grow_rooms gr ON ds.room_id = gr.room_id
    """
    conditions = []
    params = []
    
    if room_id is not None:
        conditions.append("ds.room_id = ?")
        params.append(room_id)
    
    if hyphae_id is not None:
        conditions.append("ds.hyphae_id = ?")
        params.append(hyphae_id)
    
    if active_only:
        conditions.append("ds.active = 1")
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY ds.device_name"
    return execute_query(query, tuple(params))

def update_device_spore(device_id: int, device_name: Optional[str] = None, 
                       ip_address: Optional[str] = None, firmware_version: Optional[str] = None,
                       hyphae_id: Optional[int] = None, hyphae_present: Optional[int] = None) -> int:
    """
    Update a device_spore record.
    
    Args:
        device_id (int): ID of the device to update
        device_name (str, optional): New name for the device
        ip_address (str, optional): New IP address for the device
        firmware_version (str, optional): New firmware version for the device
        hyphae_id (int, optional): New associated hyphae device ID
        hyphae_present (int, optional): New hyphae present status (0=no, 1=yes)
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []
    
    if device_name is not None:
        update_fields.append("device_name = ?")
        params.append(device_name)
    
    if ip_address is not None:
        update_fields.append("ip_address = ?")
        params.append(ip_address)
    
    if firmware_version is not None:
        update_fields.append("firmware_version = ?")
        params.append(firmware_version)
    
    if hyphae_id is not None:
        update_fields.append("hyphae_id = ?")
        params.append(hyphae_id)
        # If setting hyphae_id, also set hyphae_present to 1
        if hyphae_id > 0 and hyphae_present is None:
            update_fields.append("hyphae_present = 1")
    
    if hyphae_present is not None:
        update_fields.append("hyphae_present = ?")
        params.append(hyphae_present)
        # If setting hyphae_present to 0, also set hyphae_id to NULL
        if hyphae_present == 0:
            update_fields.append("hyphae_id = NULL")
    
    # Add updated_at timestamp
    update_fields.append("created_at = ?")  # Note: device_spore uses created_at for updates
    params.append(get_timestamp())
    
    # Add device_id to params
    params.append(device_id)
    
    if not update_fields:
        return 0  # Nothing to update
    
    query = f"""
    UPDATE device_spore
    SET {', '.join(update_fields)}
    WHERE device_id = ?
    """
    
    return execute_update(query, tuple(params))

def update_device_status(device_id: int, is_online: int, last_update: Optional[str] = None) -> int:
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
    UPDATE device_spore
    SET is_online = ?, last_update = ?, created_at = ?
    WHERE device_id = ?
    """
    return execute_update(query, (is_online, last_update, get_timestamp(), device_id))

def deactivate_device_spore(device_id: int, reason: Optional[str] = None) -> int:
    """
    Deactivate a device_spore.
    
    Args:
        device_id (int): ID of the device to deactivate
        reason (str, optional): Reason for deactivation
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE device_spore
    SET active = 0, deactivation_reason = ?, created_at = ?
    WHERE device_id = ?
    """
    return execute_update(query, (reason, get_timestamp(), device_id))

def reactivate_device_spore(device_id: int) -> int:
    """
    Reactivate a previously deactivated device_spore.
    
    Args:
        device_id (int): ID of the device to reactivate
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE device_spore
    SET active = 1, deactivation_reason = NULL, created_at = ?
    WHERE device_id = ?
    """
    return execute_update(query, (get_timestamp(), device_id))

def delete_device_spore(device_id: int) -> int:
    """
    Delete a device_spore record.

    Note: This is a hard delete and should be used with caution.
    Consider using deactivate_device_spore instead for most cases.

    Args:
        device_id (int): ID of the device to delete

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM device_spore WHERE device_id = ?"
    return execute_update(query, (device_id,))


def link_spore_to_hyphae(spore_id: int, hyphae_id: int) -> int:
    """
    Link a Spore device to a Hyphae controller.

    Args:
        spore_id (int): ID of the Spore device to link
        hyphae_id (int): ID of the Hyphae controller to link to

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE device_spore
    SET hyphae_id = ?, hyphae_present = 1, created_at = ?
    WHERE device_id = ?
    """
    return execute_update(query, (hyphae_id, get_timestamp(), spore_id))


def unlink_spore_from_hyphae(spore_id: int) -> int:
    """
    Remove a Spore's association with its Hyphae controller.

    Args:
        spore_id (int): ID of the Spore device to unlink

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE device_spore
    SET hyphae_id = NULL, hyphae_present = 0, created_at = ?
    WHERE device_id = ?
    """
    return execute_update(query, (get_timestamp(), spore_id))


def get_spores_by_hyphae(hyphae_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
    """
    Get all Spore devices linked to a specific Hyphae controller.

    Args:
        hyphae_id (int): ID of the Hyphae controller
        active_only (bool): If True, return only active devices

    Returns:
        List[Dict[str, Any]]: List of Spore device records
    """
    query = """
    SELECT ds.*, gr.room_name
    FROM device_spore ds
    LEFT JOIN grow_rooms gr ON ds.room_id = gr.room_id
    WHERE ds.hyphae_id = ?
    """
    params = [hyphae_id]

    if active_only:
        query += " AND ds.active = 1"

    query += " ORDER BY ds.device_name"
    return execute_query(query, tuple(params))


def get_unlinked_spores(active_only: bool = True) -> List[Dict[str, Any]]:
    """
    Get all Spore devices not linked to any Hyphae controller.

    Args:
        active_only (bool): If True, return only active devices

    Returns:
        List[Dict[str, Any]]: List of unlinked Spore device records
    """
    query = """
    SELECT ds.*, gr.room_name
    FROM device_spore ds
    LEFT JOIN grow_rooms gr ON ds.room_id = gr.room_id
    WHERE ds.hyphae_id IS NULL
    """

    if active_only:
        query += " AND ds.active = 1"

    query += " ORDER BY ds.device_name"
    return execute_query(query, ())


def get_device_spore_by_ip(ip_address: str) -> Optional[Dict[str, Any]]:
    """
    Get a device_spore by IP address.

    Args:
        ip_address (str): IP address of the device to retrieve

    Returns:
        Optional[Dict[str, Any]]: Device data or None if not found
    """
    query = "SELECT * FROM device_spore WHERE ip_address = ?"
    results = execute_query(query, (ip_address,))
    return results[0] if results else None


def get_devices_by_farm(farm_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
    """
    Get all Spore devices belonging to a specific farm.

    Args:
        farm_id (int): ID of the farm
        active_only (bool): If True, return only active devices

    Returns:
        List[Dict[str, Any]]: List of device records
    """
    query = """
    SELECT ds.*, gr.room_name, f.farm_name
    FROM device_spore ds
    JOIN grow_rooms gr ON ds.room_id = gr.room_id
    JOIN farms f ON gr.farm_id = f.farm_id
    WHERE f.farm_id = ?
    """

    if active_only:
        query += " AND ds.active = 1"

    query += " ORDER BY ds.device_name"
    return execute_query(query, (farm_id,))


def get_all_devices(active_only: bool = True) -> List[Dict[str, Any]]:
    """
    Alias for get_all_device_spore for consistent naming.

    Args:
        active_only (bool): If True, return only active devices

    Returns:
        List[Dict[str, Any]]: List of device records with room names
    """
    return get_all_device_spore(active_only=active_only)
