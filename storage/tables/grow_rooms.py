"""
Grow Rooms Table Module for Mycelium

This module provides functions for interacting with the grow_rooms table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Any

from storage.db_utils import (
    execute_query,
    execute_insert,
    execute_update,
    get_timestamp,
)


def create_grow_room(
    farm_id: int, room_name: str, room_desc: Optional[str] = None
) -> int:
    """
    Create a new grow room record.

    Args:
        farm_id (int): ID of the farm this room belongs to
        room_name (str): Name of the grow room
        room_desc (str, optional): Description of the grow room

    Returns:
        int: ID of the newly created grow room
    """
    query = """
    INSERT INTO grow_rooms (farm_id, room_name, room_desc)
    VALUES (?, ?, ?)
    """
    return execute_insert(query, (farm_id, room_name, room_desc))


def get_grow_room(room_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a grow room by ID.

    Args:
        room_id (int): ID of the grow room to retrieve

    Returns:
        Optional[Dict[str, Any]]: Grow room data or None if not found
    """
    query = "SELECT * FROM grow_rooms WHERE room_id = ?"
    results = execute_query(query, (room_id,))
    return results[0] if results else None


def get_all_grow_rooms(
    farm_id: Optional[int] = None, active_only: bool = True
) -> List[Dict[str, Any]]:
    """
    Get all grow rooms, optionally filtering by farm ID and active status.

    Args:
        farm_id (int, optional): If provided, filter rooms by farm ID
        active_only (bool): If True, return only active rooms

    Returns:
        List[Dict[str, Any]]: List of grow room records
    """
    query = "SELECT * FROM grow_rooms"
    conditions = []
    params = []

    if farm_id is not None:
        conditions.append("farm_id = ?")
        params.append(farm_id)

    if active_only:
        conditions.append("active = 1")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY room_name"
    return execute_query(query, tuple(params))


def update_grow_room(
    room_id: int, room_name: Optional[str] = None, room_desc: Optional[str] = None
) -> int:
    """
    Update a grow room record.

    Args:
        room_id (int): ID of the grow room to update
        room_name (str, optional): New name for the grow room
        room_desc (str, optional): New description for the grow room

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []

    if room_name is not None:
        update_fields.append("room_name = ?")
        params.append(room_name)

    if room_desc is not None:
        update_fields.append("room_desc = ?")
        params.append(room_desc)

    # Add updated_at timestamp
    update_fields.append("updated_at = ?")
    params.append(get_timestamp())

    # Add room_id to params
    params.append(room_id)

    if not update_fields:
        return 0  # Nothing to update

    query = f"""
    UPDATE grow_rooms
    SET {", ".join(update_fields)}
    WHERE room_id = ?
    """

    return execute_update(query, tuple(params))


def deactivate_grow_room(room_id: int, reason: Optional[str] = None) -> int:
    """
    Deactivate a grow room.

    Args:
        room_id (int): ID of the grow room to deactivate
        reason (str, optional): Reason for deactivation

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE grow_rooms
    SET active = 0, deactivation_reason = ?, updated_at = ?
    WHERE room_id = ?
    """
    return execute_update(query, (reason, get_timestamp(), room_id))


def reactivate_grow_room(room_id: int) -> int:
    """
    Reactivate a previously deactivated grow room.

    Args:
        room_id (int): ID of the grow room to reactivate

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE grow_rooms
    SET active = 1, deactivation_reason = NULL, updated_at = ?
    WHERE room_id = ?
    """
    return execute_update(query, (get_timestamp(), room_id))


def delete_grow_room(room_id: int) -> int:
    """
    Delete a grow room record.

    Note: This is a hard delete and should be used with caution.
    Consider using deactivate_grow_room instead for most cases.

    Args:
        room_id (int): ID of the grow room to delete

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM grow_rooms WHERE room_id = ?"
    return execute_update(query, (room_id,))
