"""
Bulk Table Module for Mycelium

This module provides functions for interacting with the bulk table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Any

from storage.db_utils import (
    execute_query,
    execute_insert,
    execute_update,
    get_timestamp,
)


def create_bulk(
    total_wt: float,
    bag_wt: float,
    bag_count: int,
    spawn_id: Optional[int] = None,
    unit_id: Optional[int] = None,
    bag_id: Optional[int] = None,
    prep_notes: Optional[str] = None,
    start_ts: Optional[str] = None,
    colonized_ts: Optional[str] = None,
    finished_ts: Optional[str] = None,
) -> int:
    """
    Create a new bulk record.

    Args:
        total_wt (float): Total weight of bulk substrate
        bag_wt (float): Weight per bag
        bag_count (int): Number of bags
        spawn_id (int, optional): Reference to spawn record
        unit_id (int, optional): Reference to cost_of_goods unit
        bag_id (int, optional): Reference to cost_of_goods bag
        prep_notes (str, optional): Preparation notes
        start_ts (str, optional): Start timestamp
        colonized_ts (str, optional): Colonization timestamp
        finished_ts (str, optional): Finished timestamp

    Returns:
        int: ID of the newly created bulk record
    """
    query = """
    INSERT INTO bulk (spawn_id, unit_id, total_wt, bag_id, bag_wt, bag_count, 
                     prep_notes, start_ts, colonized_ts, finished_ts)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    return execute_insert(
        query,
        (
            spawn_id,
            unit_id,
            total_wt,
            bag_id,
            bag_wt,
            bag_count,
            prep_notes,
            start_ts,
            colonized_ts,
            finished_ts,
        ),
    )


def get_bulk(bulk_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific bulk record by bulk_id.

    Args:
        bulk_id (int): ID of the bulk record

    Returns:
        Optional[Dict[str, Any]]: Bulk data or None if not found
    """
    query = "SELECT * FROM bulk WHERE bulk_id = ?"
    results = execute_query(query, (bulk_id,))
    return results[0] if results else None


def get_all_bulk() -> List[Dict[str, Any]]:
    """
    Get all bulk records.

    Returns:
        List[Dict[str, Any]]: List of all bulk records
    """
    query = "SELECT * FROM bulk ORDER BY start_ts DESC"
    return execute_query(query, ())


def get_bulk_by_spawn(spawn_id: int) -> List[Dict[str, Any]]:
    """
    Get bulk records by spawn_id.

    Args:
        spawn_id (int): ID of the spawn record

    Returns:
        List[Dict[str, Any]]: List of bulk records for the spawn
    """
    query = "SELECT * FROM bulk WHERE spawn_id = ? ORDER BY start_ts DESC"
    return execute_query(query, (spawn_id,))


def get_bulk_by_unit(unit_id: int) -> List[Dict[str, Any]]:
    """
    Get bulk records by unit_id.

    Args:
        unit_id (int): ID of the cost_of_goods unit

    Returns:
        List[Dict[str, Any]]: List of bulk records for the unit
    """
    query = "SELECT * FROM bulk WHERE unit_id = ? ORDER BY start_ts DESC"
    return execute_query(query, (unit_id,))


def get_bulk_by_bag(bag_id: int) -> List[Dict[str, Any]]:
    """
    Get bulk records by bag_id.

    Args:
        bag_id (int): ID of the cost_of_goods bag

    Returns:
        List[Dict[str, Any]]: List of bulk records for the bag
    """
    query = "SELECT * FROM bulk WHERE bag_id = ? ORDER BY start_ts DESC"
    return execute_query(query, (bag_id,))


def get_bulk_by_date_range(
    start_date: str, end_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get bulk records within a date range based on start_ts.

    Args:
        start_date (str): Start date for the range
        end_date (str, optional): End date for the range, defaults to current time if None

    Returns:
        List[Dict[str, Any]]: List of bulk records in the date range
    """
    if end_date is None:
        end_date = get_timestamp()

    query = """
    SELECT * FROM bulk 
    WHERE start_ts >= ? AND start_ts <= ? 
    ORDER BY start_ts DESC
    """
    return execute_query(query, (start_date, end_date))


def get_active_bulk() -> List[Dict[str, Any]]:
    """
    Get active bulk records (started but not finished).

    Returns:
        List[Dict[str, Any]]: List of active bulk records
    """
    query = """
    SELECT * FROM bulk 
    WHERE start_ts IS NOT NULL AND finished_ts IS NULL 
    ORDER BY start_ts
    """
    return execute_query(query, ())


def get_colonized_bulk() -> List[Dict[str, Any]]:
    """
    Get colonized but not finished bulk records.

    Returns:
        List[Dict[str, Any]]: List of colonized bulk records
    """
    query = """
    SELECT * FROM bulk 
    WHERE colonized_ts IS NOT NULL AND finished_ts IS NULL 
    ORDER BY colonized_ts
    """
    return execute_query(query, ())


def update_bulk(
    bulk_id: int,
    total_wt: Optional[float] = None,
    bag_wt: Optional[float] = None,
    bag_count: Optional[int] = None,
    spawn_id: Optional[int] = None,
    unit_id: Optional[int] = None,
    bag_id: Optional[int] = None,
    prep_notes: Optional[str] = None,
    start_ts: Optional[str] = None,
    colonized_ts: Optional[str] = None,
    finished_ts: Optional[str] = None,
) -> int:
    """
    Update a bulk record.

    Args:
        bulk_id (int): ID of the bulk record to update
        total_wt (float, optional): New total weight
        bag_wt (float, optional): New bag weight
        bag_count (int, optional): New bag count
        spawn_id (int, optional): New spawn ID
        unit_id (int, optional): New unit ID
        bag_id (int, optional): New bag ID
        prep_notes (str, optional): New preparation notes
        start_ts (str, optional): New start timestamp
        colonized_ts (str, optional): New colonization timestamp
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

    if spawn_id is not None:
        update_fields.append("spawn_id = ?")
        params.append(spawn_id)

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

    if colonized_ts is not None:
        update_fields.append("colonized_ts = ?")
        params.append(colonized_ts)

    if finished_ts is not None:
        update_fields.append("finished_ts = ?")
        params.append(finished_ts)

    if not update_fields:
        return 0  # Nothing to update

    # Add bulk_id to params
    params.append(bulk_id)

    query = f"""
    UPDATE bulk
    SET {", ".join(update_fields)}
    WHERE bulk_id = ?
    """

    return execute_update(query, tuple(params))


def update_bulk_status(
    bulk_id: int,
    start_ts: Optional[str] = None,
    colonized_ts: Optional[str] = None,
    finished_ts: Optional[str] = None,
) -> int:
    """
    Update the status timestamps of a bulk record.

    Args:
        bulk_id (int): ID of the bulk record
        start_ts (str, optional): New start timestamp
        colonized_ts (str, optional): New colonization timestamp
        finished_ts (str, optional): New finished timestamp

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # This is a convenience function that calls update_bulk with only timestamp fields
    return update_bulk(
        bulk_id, start_ts=start_ts, colonized_ts=colonized_ts, finished_ts=finished_ts
    )


def delete_bulk(bulk_id: int) -> int:
    """
    Delete a bulk record.

    Args:
        bulk_id (int): ID of the bulk record to delete

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM bulk WHERE bulk_id = ?"
    return execute_update(query, (bulk_id,))
