"""
Employees Table Module for Mycelium

This module provides functions for interacting with the employees table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import sqlite3

from storage.db_utils import execute_query, execute_insert, execute_update, get_timestamp

def create_employee(emp_name: str, farm_id: Optional[int] = None,
                   emp_role: Optional[str] = None, emp_rate: Optional[float] = None,
                   emp_contact: Optional[str] = None, emp_start: Optional[str] = None) -> int:
    """
    Create a new employee record.
    
    Args:
        emp_name (str): Name of the employee
        farm_id (int, optional): Reference to farm record
        emp_role (str, optional): Role of the employee
        emp_rate (float, optional): Hourly rate of the employee
        emp_contact (str, optional): Contact information for the employee
        emp_start (str, optional): Start date of the employee
        
    Returns:
        int: ID of the newly created employee record
    """
    # If emp_start is not provided, use current timestamp
    if emp_start is None:
        emp_start = get_timestamp()
        
    query = """
    INSERT INTO employees (farm_id, emp_name, emp_role, emp_rate, emp_contact, emp_start)
    VALUES (?, ?, ?, ?, ?, ?)
    """
    return execute_insert(query, (farm_id, emp_name, emp_role, emp_rate, emp_contact, emp_start))

def get_employee(emp_id: int, include_inactive: bool = False) -> Optional[Dict[str, Any]]:
    """
    Get a specific employee record by emp_id.
    
    Args:
        emp_id (int): ID of the employee record
        include_inactive (bool, optional): Whether to include inactive records (default False)
        
    Returns:
        Optional[Dict[str, Any]]: Employee data or None if not found
    """
    if include_inactive:
        query = "SELECT * FROM employees WHERE emp_id = ?"
        return execute_query(query, (emp_id,))[0] if execute_query(query, (emp_id,)) else None
    else:
        query = "SELECT * FROM employees WHERE emp_id = ? AND active = 1"
        return execute_query(query, (emp_id,))[0] if execute_query(query, (emp_id,)) else None

def get_all_employees(include_inactive: bool = False) -> List[Dict[str, Any]]:
    """
    Get all employee records.
    
    Args:
        include_inactive (bool, optional): Whether to include inactive records (default False)
        
    Returns:
        List[Dict[str, Any]]: List of all employee records
    """
    if include_inactive:
        query = "SELECT * FROM employees ORDER BY emp_name"
        return execute_query(query, ())
    else:
        query = "SELECT * FROM employees WHERE active = 1 ORDER BY emp_name"
        return execute_query(query, ())

def get_employees_by_farm(farm_id: int, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """
    Get employee records by farm_id.
    
    Args:
        farm_id (int): ID of the farm record
        include_inactive (bool, optional): Whether to include inactive records (default False)
        
    Returns:
        List[Dict[str, Any]]: List of employee records for the farm
    """
    if include_inactive:
        query = "SELECT * FROM employees WHERE farm_id = ? ORDER BY emp_name"
        return execute_query(query, (farm_id,))
    else:
        query = "SELECT * FROM employees WHERE farm_id = ? AND active = 1 ORDER BY emp_name"
        return execute_query(query, (farm_id,))

def get_employees_by_role(emp_role: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """
    Get employee records by emp_role.
    
    Args:
        emp_role (str): Role of the employee
        include_inactive (bool, optional): Whether to include inactive records (default False)
        
    Returns:
        List[Dict[str, Any]]: List of employee records with the specified role
    """
    if include_inactive:
        query = "SELECT * FROM employees WHERE emp_role = ? ORDER BY emp_name"
        return execute_query(query, (emp_role,))
    else:
        query = "SELECT * FROM employees WHERE emp_role = ? AND active = 1 ORDER BY emp_name"
        return execute_query(query, (emp_role,))

def search_employees(search_term: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """
    Search for employees by name or contact information.
    
    Args:
        search_term (str): Term to search for in emp_name or emp_contact
        include_inactive (bool, optional): Whether to include inactive records (default False)
        
    Returns:
        List[Dict[str, Any]]: List of matching employee records
    """
    search_pattern = f"%{search_term}%"
    
    if include_inactive:
        query = """
        SELECT * FROM employees 
        WHERE emp_name LIKE ? OR emp_contact LIKE ? 
        ORDER BY emp_name
        """
        return execute_query(query, (search_pattern, search_pattern))
    else:
        query = """
        SELECT * FROM employees 
        WHERE (emp_name LIKE ? OR emp_contact LIKE ?) AND active = 1
        ORDER BY emp_name
        """
        return execute_query(query, (search_pattern, search_pattern))

def update_employee(emp_id: int, emp_name: Optional[str] = None,
                   farm_id: Optional[int] = None, emp_role: Optional[str] = None,
                   emp_rate: Optional[float] = None, emp_contact: Optional[str] = None,
                   emp_start: Optional[str] = None) -> int:
    """
    Update an employee record.
    
    Args:
        emp_id (int): ID of the employee record to update
        emp_name (str, optional): New employee name
        farm_id (int, optional): New farm ID
        emp_role (str, optional): New employee role
        emp_rate (float, optional): New employee rate
        emp_contact (str, optional): New employee contact information
        emp_start (str, optional): New employee start date
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []
    
    if emp_name is not None:
        update_fields.append("emp_name = ?")
        params.append(emp_name)
    
    if farm_id is not None:
        update_fields.append("farm_id = ?")
        params.append(farm_id)
    
    if emp_role is not None:
        update_fields.append("emp_role = ?")
        params.append(emp_role)
    
    if emp_rate is not None:
        update_fields.append("emp_rate = ?")
        params.append(emp_rate)
    
    if emp_contact is not None:
        update_fields.append("emp_contact = ?")
        params.append(emp_contact)
    
    if emp_start is not None:
        update_fields.append("emp_start = ?")
        params.append(emp_start)
    
    if not update_fields:
        return 0  # Nothing to update
    
    # Add updated_at timestamp
    update_fields.append("updated_at = ?")
    params.append(get_timestamp())
    
    # Add emp_id to params
    params.append(emp_id)
    
    query = f"""
    UPDATE employees
    SET {', '.join(update_fields)}
    WHERE emp_id = ? AND active = 1
    """
    
    return execute_update(query, tuple(params))

def deactivate_employee(emp_id: int, deactivation_reason: Optional[str] = None) -> int:
    """
    Deactivate an employee record by setting active = 0.
    
    Args:
        emp_id (int): ID of the employee record to deactivate
        deactivation_reason (str, optional): Reason for deactivation
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE employees
    SET active = 0, deactivation_reason = ?, updated_at = ?
    WHERE emp_id = ? AND active = 1
    """
    return execute_update(query, (deactivation_reason, get_timestamp(), emp_id))

def reactivate_employee(emp_id: int) -> int:
    """
    Reactivate an employee record by setting active = 1.
    
    Args:
        emp_id (int): ID of the employee record to reactivate
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = """
    UPDATE employees
    SET active = 1, deactivation_reason = NULL, updated_at = ?
    WHERE emp_id = ? AND active = 0
    """
    return execute_update(query, (get_timestamp(), emp_id))

def delete_employee(emp_id: int) -> int:
    """
    Hard delete an employee record.
    
    Args:
        emp_id (int): ID of the employee record to delete
        
    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM employees WHERE emp_id = ?"
    return execute_update(query, (emp_id,))
