"""
Sales Detail Table Module for Mycelium

This module provides functions for interacting with the sales_detail table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Any

from storage.db_utils import execute_query, execute_insert, execute_update


def create_sales_detail(
    sale_id: int,
    harvest_id: int,
    weight_used: float,
    price: float,
    line_total: float,
    unit_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> int:
    """
    Create a new sales detail record.

    Args:
        sale_id (int): Reference to sales_transaction record
        harvest_id (int): Reference to harvest record
        weight_used (float): Weight used from the harvest
        price (float): Price per unit
        line_total (float): Total price for this line item
        unit_id (int, optional): Reference to cost_of_goods record
        notes (str, optional): Additional notes about the sale detail

    Returns:
        int: ID of the newly created sales detail record
    """
    query = """
    INSERT INTO sales_detail (sale_id, harvest_id, unit_id, weight_used, price, line_total, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    return execute_insert(
        query, (sale_id, harvest_id, unit_id, weight_used, price, line_total, notes)
    )


def get_sales_detail(detail_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific sales detail record by detail_id.

    Args:
        detail_id (int): ID of the sales detail record

    Returns:
        Optional[Dict[str, Any]]: Sales detail data or None if not found
    """
    query = "SELECT * FROM sales_detail WHERE detail_id = ?"
    results = execute_query(query, (detail_id,))
    return results[0] if results else None


def get_all_sales_details() -> List[Dict[str, Any]]:
    """
    Get all sales detail records.

    Returns:
        List[Dict[str, Any]]: List of all sales detail records
    """
    query = "SELECT * FROM sales_detail ORDER BY detail_id"
    return execute_query(query, ())


def get_sales_details_by_sale(sale_id: int) -> List[Dict[str, Any]]:
    """
    Get sales detail records by sale_id.

    Args:
        sale_id (int): ID of the sales transaction record

    Returns:
        List[Dict[str, Any]]: List of sales detail records for the sale
    """
    query = "SELECT * FROM sales_detail WHERE sale_id = ? ORDER BY detail_id"
    return execute_query(query, (sale_id,))


def get_sales_details_by_harvest(harvest_id: int) -> List[Dict[str, Any]]:
    """
    Get sales detail records by harvest_id.

    Args:
        harvest_id (int): ID of the harvest record

    Returns:
        List[Dict[str, Any]]: List of sales detail records for the harvest
    """
    query = "SELECT * FROM sales_detail WHERE harvest_id = ? ORDER BY detail_id"
    return execute_query(query, (harvest_id,))


def get_sales_details_by_unit(unit_id: int) -> List[Dict[str, Any]]:
    """
    Get sales detail records by unit_id.

    Args:
        unit_id (int): ID of the cost_of_goods unit record

    Returns:
        List[Dict[str, Any]]: List of sales detail records for the unit
    """
    query = "SELECT * FROM sales_detail WHERE unit_id = ? ORDER BY detail_id"
    return execute_query(query, (unit_id,))


def update_sales_detail(
    detail_id: int,
    weight_used: Optional[float] = None,
    price: Optional[float] = None,
    line_total: Optional[float] = None,
    notes: Optional[str] = None,
) -> int:
    """
    Update a sales detail record.

    Args:
        detail_id (int): ID of the sales detail record to update
        weight_used (float, optional): New weight used
        price (float, optional): New price
        line_total (float, optional): New line total
        notes (str, optional): New notes

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []

    if weight_used is not None:
        update_fields.append("weight_used = ?")
        params.append(weight_used)

    if price is not None:
        update_fields.append("price = ?")
        params.append(price)

    if line_total is not None:
        update_fields.append("line_total = ?")
        params.append(line_total)

    if notes is not None:
        update_fields.append("notes = ?")
        params.append(notes)

    if not update_fields:
        return 0  # Nothing to update

    # Add detail_id to params
    params.append(detail_id)

    query = f"""
    UPDATE sales_detail
    SET {", ".join(update_fields)}
    WHERE detail_id = ?
    """

    return execute_update(query, tuple(params))


def delete_sales_detail(detail_id: int) -> int:
    """
    Delete a sales detail record.

    Args:
        detail_id (int): ID of the sales detail record to delete

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM sales_detail WHERE detail_id = ?"
    return execute_update(query, (detail_id,))


def calculate_total_for_sale(sale_id: int) -> float:
    """
    Calculate the total amount for a sale based on its detail records.

    Args:
        sale_id (int): ID of the sales transaction record

    Returns:
        float: Total amount for the sale
    """
    query = "SELECT SUM(line_total) as total FROM sales_detail WHERE sale_id = ?"
    result = execute_query(query, (sale_id,))
    return result[0]["total"] if result and result[0]["total"] is not None else 0.0
