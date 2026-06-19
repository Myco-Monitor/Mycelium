"""
Labour Table Module for Mycelium

This module provides functions for interacting with the labour table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Any

from storage.db_utils import execute_query, execute_insert, execute_update


def create_labour(
    emp_id: int,
    task_type: str,
    work_date: str,
    hours_worked: float,
    notes: Optional[str] = None,
) -> int:
    """
    Create a new labour record.

    Args:
        emp_id (int): Reference to employees record
        task_type (str): Type of task performed
        work_date (str): Date when the work was performed
        hours_worked (float): Number of hours worked
        notes (str, optional): Additional notes about the labour

    Returns:
        int: ID of the newly created labour record
    """
    query = """
    INSERT INTO labour (emp_id, task_type, work_date, hours_worked, notes)
    VALUES (?, ?, ?, ?, ?)
    """
    return execute_insert(query, (emp_id, task_type, work_date, hours_worked, notes))


def get_labour(labour_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific labour record by labour_id.

    Args:
        labour_id (int): ID of the labour record

    Returns:
        Optional[Dict[str, Any]]: Labour data or None if not found
    """
    query = "SELECT * FROM labour WHERE labour_id = ?"
    results = execute_query(query, (labour_id,))
    return results[0] if results else None


def get_all_labour() -> List[Dict[str, Any]]:
    """
    Get all labour records.

    Returns:
        List[Dict[str, Any]]: List of all labour records
    """
    query = "SELECT * FROM labour ORDER BY work_date DESC"
    return execute_query(query, ())


def get_labour_by_employee(emp_id: int) -> List[Dict[str, Any]]:
    """
    Get labour records by emp_id.

    Args:
        emp_id (int): ID of the employee record

    Returns:
        List[Dict[str, Any]]: List of labour records for the employee
    """
    query = "SELECT * FROM labour WHERE emp_id = ? ORDER BY work_date DESC"
    return execute_query(query, (emp_id,))


def get_labour_by_task_type(task_type: str) -> List[Dict[str, Any]]:
    """
    Get labour records by task_type.

    Args:
        task_type (str): Type of task

    Returns:
        List[Dict[str, Any]]: List of labour records for the task type
    """
    query = "SELECT * FROM labour WHERE task_type = ? ORDER BY work_date DESC"
    return execute_query(query, (task_type,))


def get_labour_by_date_range(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    Get labour records within a date range.

    Args:
        start_date (str): Start date of the range (inclusive)
        end_date (str): End date of the range (inclusive)

    Returns:
        List[Dict[str, Any]]: List of labour records within the date range
    """
    query = (
        "SELECT * FROM labour WHERE work_date BETWEEN ? AND ? ORDER BY work_date DESC"
    )
    return execute_query(query, (start_date, end_date))


def get_labour_by_employee_and_date_range(
    emp_id: int, start_date: str, end_date: str
) -> List[Dict[str, Any]]:
    """
    Get labour records for a specific employee within a date range.

    Args:
        emp_id (int): ID of the employee record
        start_date (str): Start date of the range (inclusive)
        end_date (str): End date of the range (inclusive)

    Returns:
        List[Dict[str, Any]]: List of labour records for the employee within the date range
    """
    query = """
    SELECT * FROM labour 
    WHERE emp_id = ? AND work_date BETWEEN ? AND ? 
    ORDER BY work_date DESC
    """
    return execute_query(query, (emp_id, start_date, end_date))


def calculate_total_hours_by_employee(
    emp_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None
) -> float:
    """
    Calculate total hours worked by an employee, optionally within a date range.

    Args:
        emp_id (int): ID of the employee record
        start_date (str, optional): Start date of the range (inclusive)
        end_date (str, optional): End date of the range (inclusive)

    Returns:
        float: Total hours worked
    """
    if start_date and end_date:
        query = """
        SELECT SUM(hours_worked) as total_hours FROM labour 
        WHERE emp_id = ? AND work_date BETWEEN ? AND ?
        """
        result = execute_query(query, (emp_id, start_date, end_date))
    else:
        query = "SELECT SUM(hours_worked) as total_hours FROM labour WHERE emp_id = ?"
        result = execute_query(query, (emp_id,))

    return (
        result[0]["total_hours"]
        if result and result[0]["total_hours"] is not None
        else 0.0
    )


def calculate_total_hours_by_task_type(
    task_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None
) -> float:
    """
    Calculate total hours worked on a specific task type, optionally within a date range.

    Args:
        task_type (str): Type of task
        start_date (str, optional): Start date of the range (inclusive)
        end_date (str, optional): End date of the range (inclusive)

    Returns:
        float: Total hours worked
    """
    if start_date and end_date:
        query = """
        SELECT SUM(hours_worked) as total_hours FROM labour 
        WHERE task_type = ? AND work_date BETWEEN ? AND ?
        """
        result = execute_query(query, (task_type, start_date, end_date))
    else:
        query = (
            "SELECT SUM(hours_worked) as total_hours FROM labour WHERE task_type = ?"
        )
        result = execute_query(query, (task_type,))

    return (
        result[0]["total_hours"]
        if result and result[0]["total_hours"] is not None
        else 0.0
    )


def update_labour(
    labour_id: int,
    task_type: Optional[str] = None,
    work_date: Optional[str] = None,
    hours_worked: Optional[float] = None,
    notes: Optional[str] = None,
) -> int:
    """
    Update a labour record.

    Args:
        labour_id (int): ID of the labour record to update
        task_type (str, optional): New task type
        work_date (str, optional): New work date
        hours_worked (float, optional): New hours worked
        notes (str, optional): New notes

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []

    if task_type is not None:
        update_fields.append("task_type = ?")
        params.append(task_type)

    if work_date is not None:
        update_fields.append("work_date = ?")
        params.append(work_date)

    if hours_worked is not None:
        update_fields.append("hours_worked = ?")
        params.append(hours_worked)

    if notes is not None:
        update_fields.append("notes = ?")
        params.append(notes)

    if not update_fields:
        return 0  # Nothing to update

    # Add labour_id to params
    params.append(labour_id)

    query = f"""
    UPDATE labour
    SET {", ".join(update_fields)}
    WHERE labour_id = ?
    """

    return execute_update(query, tuple(params))


def delete_labour(labour_id: int) -> int:
    """
    Delete a labour record.

    Args:
        labour_id (int): ID of the labour record to delete

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM labour WHERE labour_id = ?"
    return execute_update(query, (labour_id,))
