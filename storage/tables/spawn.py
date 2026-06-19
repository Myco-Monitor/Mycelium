"""
Spawn Table Module for Mycelium

This module provides functions for interacting with the spawn table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Any

from storage.db_utils import (
    execute_query,
    execute_insert,
    execute_update,
    get_timestamp,
)


def create_spawn(
    total_wt: float,
    bag_wt: float,
    bag_count: int,
    unit_id: Optional[int] = None,
    bag_id: Optional[int] = None,
    prep_notes: Optional[str] = None,
    start_ts: Optional[str] = None,
    inoculated_ts: Optional[str] = None,
    finished_ts: Optional[str] = None,
) -> int:
    """
    Create a new spawn record.

    Args:
        total_wt (float): Total weight of spawn
        bag_wt (float): Weight per bag
        bag_count (int): Number of bags
        unit_id (int, optional): Reference to cost_of_goods unit
        bag_id (int, optional): Reference to cost_of_goods bag
        prep_notes (str, optional): Preparation notes
        start_ts (str, optional): Start timestamp
        inoculated_ts (str, optional): Inoculation timestamp
        finished_ts (str, optional): Finished timestamp

    Returns:
        int: ID of the newly created spawn record
    """
    query = """
    INSERT INTO spawn (unit_id, total_wt, bag_id, bag_wt, bag_count, 
                      prep_notes, start_ts, inoculated_ts, finished_ts)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    return execute_insert(
        query,
        (
            unit_id,
            total_wt,
            bag_id,
            bag_wt,
            bag_count,
            prep_notes,
            start_ts,
            inoculated_ts,
            finished_ts,
        ),
    )


def get_spawn(spawn_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific spawn record by spawn_id.

    Args:
        spawn_id (int): ID of the spawn record

    Returns:
        Optional[Dict[str, Any]]: Spawn data or None if not found
    """
    query = "SELECT * FROM spawn WHERE spawn_id = ?"
    results = execute_query(query, (spawn_id,))
    return results[0] if results else None


def get_all_spawn() -> List[Dict[str, Any]]:
    """
    Get all spawn records.

    Returns:
        List[Dict[str, Any]]: List of all spawn records
    """
    query = "SELECT * FROM spawn ORDER BY created_at DESC"
    return execute_query(query, ())


def get_spawn_by_unit(unit_id: int) -> List[Dict[str, Any]]:
    """
    Get spawn records by unit_id.

    Args:
        unit_id (int): ID of the cost_of_goods unit

    Returns:
        List[Dict[str, Any]]: List of spawn records for the unit
    """
    query = "SELECT * FROM spawn WHERE unit_id = ? ORDER BY created_at DESC"
    return execute_query(query, (unit_id,))


def get_spawn_by_bag(bag_id: int) -> List[Dict[str, Any]]:
    """
    Get spawn records by bag_id.

    Args:
        bag_id (int): ID of the cost_of_goods bag

    Returns:
        List[Dict[str, Any]]: List of spawn records for the bag
    """
    query = "SELECT * FROM spawn WHERE bag_id = ? ORDER BY created_at DESC"
    return execute_query(query, (bag_id,))


def get_spawn_by_date_range(
    start_date: str, end_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get spawn records within a date range based on start_ts.

    Args:
        start_date (str): Start date for the range
        end_date (str, optional): End date for the range, defaults to current time if None

    Returns:
        List[Dict[str, Any]]: List of spawn records in the date range
    """
    if end_date is None:
        end_date = get_timestamp()

    query = """
    SELECT * FROM spawn 
    WHERE start_ts >= ? AND start_ts <= ? 
    ORDER BY start_ts DESC
    """
    return execute_query(query, (start_date, end_date))


def get_active_spawn() -> List[Dict[str, Any]]:
    """
    Get active spawn records (started but not finished).

    Returns:
        List[Dict[str, Any]]: List of active spawn records
    """
    query = """
    SELECT * FROM spawn 
    WHERE start_ts IS NOT NULL AND finished_ts IS NULL 
    ORDER BY start_ts
    """
    return execute_query(query, ())


def update_spawn(
    spawn_id: int,
    total_wt: Optional[float] = None,
    bag_wt: Optional[float] = None,
    bag_count: Optional[int] = None,
    unit_id: Optional[int] = None,
    bag_id: Optional[int] = None,
    prep_notes: Optional[str] = None,
    start_ts: Optional[str] = None,
    inoculated_ts: Optional[str] = None,
    finished_ts: Optional[str] = None,
) -> int:
    """
    Update a spawn record.

    Args:
        spawn_id (int): ID of the spawn record to update
        total_wt (float, optional): New total weight
        bag_wt (float, optional): New bag weight
        bag_count (int, optional): New bag count
        unit_id (int, optional): New unit ID
        bag_id (int, optional): New bag ID
        prep_notes (str, optional): New preparation notes
        start_ts (str, optional): New start timestamp
        inoculated_ts (str, optional): New inoculation timestamp
        finished_ts (str, optional): New finished timestamp

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []

    if total_wt is not None:
        update_fields.append("total_wt = ?")
        params.append(total_wt)

    if bag_wt is not None:
        update_fields.append("bag_wt = ?")
        params.append(bag_wt)

    if bag_count is not None:
        update_fields.append("bag_count = ?")
        params.append(bag_count)

    if unit_id is not None:
        update_fields.append("unit_id = ?")
        params.append(unit_id)

    if bag_id is not None:
        update_fields.append("bag_id = ?")
        params.append(bag_id)

    if prep_notes is not None:
        update_fields.append("prep_notes = ?")
        params.append(prep_notes)

    if start_ts is not None:
        update_fields.append("start_ts = ?")
        params.append(start_ts)

    if inoculated_ts is not None:
        update_fields.append("inoculated_ts = ?")
        params.append(inoculated_ts)

    if finished_ts is not None:
        update_fields.append("finished_ts = ?")
        params.append(finished_ts)

    if not update_fields:
        return 0  # Nothing to update

    # Add updated_at timestamp
    update_fields.append("updated_at = ?")
    params.append(get_timestamp())

    # Add spawn_id to params
    params.append(spawn_id)

    query = f"""
    UPDATE spawn
    SET {", ".join(update_fields)}
    WHERE spawn_id = ?
    """

    return execute_update(query, tuple(params))


def update_spawn_status(
    spawn_id: int,
    start_ts: Optional[str] = None,
    inoculated_ts: Optional[str] = None,
    finished_ts: Optional[str] = None,
) -> int:
    """
    Update the status timestamps of a spawn record.

    Args:
        spawn_id (int): ID of the spawn record
        start_ts (str, optional): New start timestamp
        inoculated_ts (str, optional): New inoculation timestamp
        finished_ts (str, optional): New finished timestamp

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # This is a convenience function that calls update_spawn with only timestamp fields
    return update_spawn(
        spawn_id,
        start_ts=start_ts,
        inoculated_ts=inoculated_ts,
        finished_ts=finished_ts,
    )


def delete_spawn(spawn_id: int) -> int:
    """
    Delete a spawn record.

    Args:
        spawn_id (int): ID of the spawn record to delete

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM spawn WHERE spawn_id = ?"
    return execute_update(query, (spawn_id,))
