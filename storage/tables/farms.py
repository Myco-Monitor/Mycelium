"""
Farms Table Module for Mycelium

This module provides functions for interacting with the farms table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Any

from storage.db_utils import (
    execute_query,
    execute_insert,
    execute_update,
    get_timestamp,
)


def create_farm(
    farm_name: str, farm_loc: Optional[str] = None, farm_desc: Optional[str] = None
) -> int:
    """
    Create a new farm record.

    Args:
        farm_name (str): Name of the farm
        farm_loc (str, optional): Location of the farm
        farm_desc (str, optional): Description of the farm

    Returns:
        int: ID of the newly created farm
    """
    query = """
    INSERT INTO farms (farm_name, farm_loc, farm_desc)
    VALUES (?, ?, ?)
    """
    return execute_insert(query, (farm_name, farm_loc, farm_desc))


def get_farm(farm_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a farm by ID.

    Args:
        farm_id (int): ID of the farm to retrieve

    Returns:
        Optional[Dict[str, Any]]: Farm data or None if not found
    """
    query = "SELECT * FROM farms WHERE farm_id = ?"
    results = execute_query(query, (farm_id,))
    return results[0] if results else None


def get_all_farms(active_only: bool = True) -> List[Dict[str, Any]]:
    """
    Get all farms, optionally filtering for active farms only.

    Args:
        active_only (bool): If True, return only active farms

    Returns:
        List[Dict[str, Any]]: List of farm records
    """
    query = "SELECT * FROM farms"
    if active_only:
        query += " WHERE active = 1"
    query += " ORDER BY farm_name"
    return execute_query(query)


def update_farm(
    farm_id: int,
    farm_name: Optional[str] = None,
    farm_loc: Optional[str] = None,
    farm_desc: Optional[str] = None,
) -> int:
    """
    Update a farm record.

    Args:
        farm_id (int): ID of the farm to update
        farm_name (str, optional): New name for the farm
        farm_loc (str, optional): New location for the farm
        farm_desc (str, optional): New description for the farm

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []

    if farm_name is not None:
        update_fields.append("farm_name = ?")
        params.append(farm_name)

    if farm_loc is not None:
        update_fields.append("farm_loc = ?")
        params.append(farm_loc)

    if farm_desc is not None:
        update_fields.append("farm_desc = ?")
        params.append(farm_desc)

    # Add updated_at timestamp
    update_fields.append("updated_at = ?")
    params.append(get_timestamp())

    # Add farm_id to params
    params.append(farm_id)

    if not update_fields:
        return 0  # Nothing to update

    query = f"""
    UPDATE farms
    SET {", ".join(update_fields)}
    WHERE farm_id = ?
    """

    return execute_update(query, tuple(params))


def deactivate_farm(farm_id: int, reason: Optional[str] = None) -> int:
    """
    Deactivate a farm.

    Args:
        farm_id (int): ID of the farm to deactivate
        reason (str, optional): Reason for deactivation

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE farms
    SET active = 0, deactivation_reason = ?, updated_at = ?
    WHERE farm_id = ?
    """
    return execute_update(query, (reason, get_timestamp(), farm_id))


def reactivate_farm(farm_id: int) -> int:
    """
    Reactivate a previously deactivated farm.

    Args:
        farm_id (int): ID of the farm to reactivate

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE farms
    SET active = 1, deactivation_reason = NULL, updated_at = ?
    WHERE farm_id = ?
    """
    return execute_update(query, (get_timestamp(), farm_id))


def delete_farm(farm_id: int) -> int:
    """
    Delete a farm record.

    Note: This is a hard delete and should be used with caution.
    Consider using deactivate_farm instead for most cases.

    Args:
        farm_id (int): ID of the farm to delete

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM farms WHERE farm_id = ?"
    return execute_update(query, (farm_id,))


def get_farm_statistics(farm_id: int) -> Dict[str, Any]:
    """
    Get statistics for a farm.

    Args:
        farm_id (int): ID of the farm

    Returns:
        Dict[str, Any]: Farm statistics including room/device counts
    """
    # Get room count
    room_query = (
        "SELECT COUNT(*) as count FROM grow_rooms WHERE farm_id = ? AND active = 1"
    )
    room_result = execute_query(room_query, (farm_id,))
    room_count = room_result[0]["count"] if room_result else 0

    # Get spore device count
    spore_query = """
        SELECT COUNT(*) as count FROM device_spore ds
        JOIN grow_rooms gr ON ds.room_id = gr.room_id
        WHERE gr.farm_id = ? AND ds.active = 1
    """
    spore_result = execute_query(spore_query, (farm_id,))
    spore_count = spore_result[0]["count"] if spore_result else 0

    # Get hyphae device count
    hyphae_query = """
        SELECT COUNT(*) as count FROM device_hyphae dh
        JOIN grow_rooms gr ON dh.room_id = gr.room_id
        WHERE gr.farm_id = ? AND dh.active = 1
    """
    hyphae_result = execute_query(hyphae_query, (farm_id,))
    hyphae_count = hyphae_result[0]["count"] if hyphae_result else 0

    # Get online device counts
    online_spore_query = """
        SELECT COUNT(*) as count FROM device_spore ds
        JOIN grow_rooms gr ON ds.room_id = gr.room_id
        WHERE gr.farm_id = ? AND ds.active = 1 AND ds.is_online = 1
    """
    online_spore_result = execute_query(online_spore_query, (farm_id,))
    online_spore = online_spore_result[0]["count"] if online_spore_result else 0

    online_hyphae_query = """
        SELECT COUNT(*) as count FROM device_hyphae dh
        JOIN grow_rooms gr ON dh.room_id = gr.room_id
        WHERE gr.farm_id = ? AND dh.active = 1 AND dh.is_online = 1
    """
    online_hyphae_result = execute_query(online_hyphae_query, (farm_id,))
    online_hyphae = online_hyphae_result[0]["count"] if online_hyphae_result else 0

    total_devices = spore_count + hyphae_count
    online_devices = online_spore + online_hyphae
    online_pct = (online_devices / total_devices * 100) if total_devices > 0 else 0

    # Get latest readings averages
    readings_query = """
        SELECT
            AVG(rs.temp) as avg_temp,
            AVG(rs.humidity) as avg_humidity,
            AVG(rs.co2) as avg_co2
        FROM readings_spore rs
        JOIN device_spore ds ON rs.device_id = ds.device_id
        JOIN grow_rooms gr ON ds.room_id = gr.room_id
        WHERE gr.farm_id = ?
        AND rs.reading_ts >= datetime('now', '-1 hour')
    """
    readings_result = execute_query(readings_query, (farm_id,))
    env_data = readings_result[0] if readings_result else {}

    return {
        "room_count": room_count,
        "spore_count": spore_count,
        "hyphae_count": hyphae_count,
        "total_devices": total_devices,
        "online_devices": online_devices,
        "online_pct": round(online_pct, 1),
        "avg_temp": round(env_data.get("avg_temp") or 0, 1),
        "avg_humidity": round(env_data.get("avg_humidity") or 0, 1),
        "avg_co2": round(env_data.get("avg_co2") or 0, 0),
    }
