"""
Utilities Table Module for Mycelium

This module provides functions for interacting with the utilities table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Any

from storage.db_utils import (
    execute_query,
    execute_insert,
    execute_update,
    get_timestamp,
)


def create_utility(
    util_name: str,
    util_cost: float,
    util_recd: str,
    util_dued: str,
    farm_id: int,
    util_paid: Optional[str] = None,
    util_note: Optional[str] = None,
    room_id: Optional[int] = None,
) -> int:
    """
    Create a new utility record.

    Args:
        util_name (str): Name of the bill/company
        util_cost (float): Cost of the bill/company
        util_recd (str): Date the bill was received
        util_dued (str): Due date of the bill
        farm_id (int): Reference to farm record
        util_paid (str, optional): Date the bill was paid
        util_note (str, optional): Notes about the bill
        room_id (int, optional): Reference to room record

    Returns:
        int: ID of the newly created utility record (unit_id)
    """
    query = """
    INSERT INTO utilities (util_name, util_cost, util_recd, util_dued, util_paid, 
                          util_note, farm_id, room_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    return execute_insert(
        query,
        (
            util_name,
            util_cost,
            util_recd,
            util_dued,
            util_paid,
            util_note,
            farm_id,
            room_id,
        ),
    )


def get_utility(unit_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific utility record by unit_id.

    Args:
        unit_id (int): ID of the utility record

    Returns:
        Optional[Dict[str, Any]]: Utility data or None if not found
    """
    query = "SELECT * FROM utilities WHERE unit_id = ?"
    results = execute_query(query, (unit_id,))
    return results[0] if results else None


def get_all_utilities() -> List[Dict[str, Any]]:
    """
    Get all utility records.

    Returns:
        List[Dict[str, Any]]: List of all utility records
    """
    query = "SELECT * FROM utilities ORDER BY util_dued DESC"
    return execute_query(query)


def get_utilities_by_farm(farm_id: int) -> List[Dict[str, Any]]:
    """
    Get utility records by farm_id.

    Args:
        farm_id (int): ID of the farm record

    Returns:
        List[Dict[str, Any]]: List of utility records for the farm
    """
    query = "SELECT * FROM utilities WHERE farm_id = ? ORDER BY util_dued DESC"
    return execute_query(query, (farm_id,))


def get_utilities_by_room(room_id: int) -> List[Dict[str, Any]]:
    """
    Get utility records by room_id.

    Args:
        room_id (int): ID of the room record

    Returns:
        List[Dict[str, Any]]: List of utility records for the room
    """
    query = "SELECT * FROM utilities WHERE room_id = ? ORDER BY util_dued DESC"
    return execute_query(query, (room_id,))


def get_utilities_by_name(util_name: str) -> List[Dict[str, Any]]:
    """
    Get utility records by utility name.

    Args:
        util_name (str): Name of the utility/company to search for

    Returns:
        List[Dict[str, Any]]: List of matching utility records
    """
    query = "SELECT * FROM utilities WHERE util_name LIKE ? ORDER BY util_dued DESC"
    return execute_query(query, (f"%{util_name}%",))


def get_utilities_by_date_range(
    start_date: str, end_date: str, date_type: str = "due"
) -> List[Dict[str, Any]]:
    """
    Get utility records within a date range.

    Args:
        start_date (str): Start date of the range (inclusive)
        end_date (str): End date of the range (inclusive)
        date_type (str): Type of date to filter by ('due', 'received', 'paid')

    Returns:
        List[Dict[str, Any]]: List of utility records within the date range
    """
    date_column = {
        "due": "util_dued",
        "received": "util_recd",
        "paid": "util_paid",
    }.get(date_type, "util_dued")

    query = f"SELECT * FROM utilities WHERE {date_column} BETWEEN ? AND ? ORDER BY {date_column} DESC"
    return execute_query(query, (start_date, end_date))


def get_unpaid_utilities() -> List[Dict[str, Any]]:
    """
    Get all unpaid utility records.

    Returns:
        List[Dict[str, Any]]: List of unpaid utility records
    """
    query = "SELECT * FROM utilities WHERE util_paid IS NULL ORDER BY util_dued ASC"
    return execute_query(query)


def get_overdue_utilities() -> List[Dict[str, Any]]:
    """
    Get all overdue utility records (unpaid and past due date).

    Returns:
        List[Dict[str, Any]]: List of overdue utility records
    """
    current_date = get_timestamp()
    query = """
    SELECT * FROM utilities 
    WHERE util_paid IS NULL AND util_dued < ? 
    ORDER BY util_dued ASC
    """
    return execute_query(query, (current_date,))


def get_utilities_by_farm_and_date_range(
    farm_id: int, start_date: str, end_date: str, date_type: str = "due"
) -> List[Dict[str, Any]]:
    """
    Get utility records for a specific farm within a date range.

    Args:
        farm_id (int): ID of the farm record
        start_date (str): Start date of the range (inclusive)
        end_date (str): End date of the range (inclusive)
        date_type (str): Type of date to filter by ('due', 'received', 'paid')

    Returns:
        List[Dict[str, Any]]: List of utility records for the farm within the date range
    """
    date_column = {
        "due": "util_dued",
        "received": "util_recd",
        "paid": "util_paid",
    }.get(date_type, "util_dued")

    query = f"""
    SELECT * FROM utilities 
    WHERE farm_id = ? AND {date_column} BETWEEN ? AND ? 
    ORDER BY {date_column} DESC
    """
    return execute_query(query, (farm_id, start_date, end_date))


def calculate_total_cost_by_farm(
    farm_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    paid_only: bool = False,
) -> float:
    """
    Calculate total utility costs for a specific farm, optionally within a date range.

    Args:
        farm_id (int): ID of the farm record
        start_date (str, optional): Start date of the range (inclusive)
        end_date (str, optional): End date of the range (inclusive)
        paid_only (bool): If True, only include paid utilities

    Returns:
        float: Total utility costs
    """
    base_query = "SELECT SUM(util_cost) as total FROM utilities WHERE farm_id = ?"
    params = [farm_id]

    if paid_only:
        base_query += " AND util_paid IS NOT NULL"

    if start_date and end_date:
        base_query += " AND util_dued BETWEEN ? AND ?"
        params.extend([start_date, end_date])

    results = execute_query(base_query, tuple(params))
    return results[0]["total"] if results and results[0]["total"] is not None else 0.0


def calculate_total_cost_by_utility_name(
    util_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    paid_only: bool = False,
) -> float:
    """
    Calculate total costs for a specific utility name, optionally within a date range.

    Args:
        util_name (str): Name of the utility/company
        start_date (str, optional): Start date of the range (inclusive)
        end_date (str, optional): End date of the range (inclusive)
        paid_only (bool): If True, only include paid utilities

    Returns:
        float: Total utility costs
    """
    base_query = "SELECT SUM(util_cost) as total FROM utilities WHERE util_name LIKE ?"
    params = [f"%{util_name}%"]

    if paid_only:
        base_query += " AND util_paid IS NOT NULL"

    if start_date and end_date:
        base_query += " AND util_dued BETWEEN ? AND ?"
        params.extend([start_date, end_date])

    results = execute_query(base_query, tuple(params))
    return results[0]["total"] if results and results[0]["total"] is not None else 0.0


def update_utility(
    unit_id: int,
    util_name: Optional[str] = None,
    util_cost: Optional[float] = None,
    util_recd: Optional[str] = None,
    util_dued: Optional[str] = None,
    util_paid: Optional[str] = None,
    util_note: Optional[str] = None,
    room_id: Optional[int] = None,
) -> int:
    """
    Update a utility record.

    Args:
        unit_id (int): ID of the utility record to update
        util_name (str, optional): New utility name
        util_cost (float, optional): New utility cost
        util_recd (str, optional): New received date
        util_dued (str, optional): New due date
        util_paid (str, optional): New paid date
        util_note (str, optional): New notes
        room_id (int, optional): New room ID

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the update query dynamically based on provided parameters
    update_fields = []
    params = []

    if util_name is not None:
        update_fields.append("util_name = ?")
        params.append(util_name)

    if util_cost is not None:
        update_fields.append("util_cost = ?")
        params.append(util_cost)

    if util_recd is not None:
        update_fields.append("util_recd = ?")
        params.append(util_recd)

    if util_dued is not None:
        update_fields.append("util_dued = ?")
        params.append(util_dued)

    if util_paid is not None:
        update_fields.append("util_paid = ?")
        params.append(util_paid)

    if util_note is not None:
        update_fields.append("util_note = ?")
        params.append(util_note)

    if room_id is not None:
        update_fields.append("room_id = ?")
        params.append(room_id)

    if not update_fields:
        return 0  # No fields to update

    # Add updated_at timestamp
    update_fields.append("updated_at = ?")
    params.append(get_timestamp())

    # Add the unit_id for the WHERE clause
    params.append(unit_id)

    query = f"UPDATE utilities SET {', '.join(update_fields)} WHERE unit_id = ?"
    return execute_update(query, tuple(params))


def mark_utility_paid(unit_id: int, paid_date: Optional[str] = None) -> int:
    """
    Mark a utility as paid.

    Args:
        unit_id (int): ID of the utility record
        paid_date (str, optional): Date the bill was paid, defaults to current timestamp

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    if paid_date is None:
        paid_date = get_timestamp()

    return update_utility(unit_id, util_paid=paid_date)


def delete_utility(unit_id: int) -> int:
    """
    Delete a utility record.

    Args:
        unit_id (int): ID of the utility record to delete

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM utilities WHERE unit_id = ?"
    return execute_update(query, (unit_id,))
