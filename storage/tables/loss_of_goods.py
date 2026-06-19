"""
Loss of Goods Table Module for Mycelium

This module provides functions for interacting with the loss_of_goods table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Any

from storage.db_utils import execute_query, execute_insert, execute_update


def create_loss_of_goods(
    item_type: str,
    source_type: str,
    loss_date: str,
    quantity: float,
    farm_id: Optional[int] = None,
    source_id: Optional[int] = None,
    reason: Optional[str] = None,
    notes: Optional[str] = None,
) -> int:
    """
    Create a new loss of goods record.

    Args:
        item_type (str): Type of item lost
        source_type (str): Type of source (e.g., 'spawn', 'bulk', 'harvest')
        loss_date (str): Date when the loss occurred
        quantity (float): Quantity lost
        farm_id (int, optional): Reference to farm record
        source_id (int, optional): Reference to source record (e.g., spawn_id, bulk_id, harvest_id)
        reason (str, optional): Reason for the loss
        notes (str, optional): Additional notes about the loss

    Returns:
        int: ID of the newly created loss of goods record
    """
    query = """
    INSERT INTO loss_of_goods (farm_id, item_type, source_id, source_type, loss_date, quantity, reason, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    return execute_insert(
        query,
        (
            farm_id,
            item_type,
            source_id,
            source_type,
            loss_date,
            quantity,
            reason,
            notes,
        ),
    )


def get_loss_of_goods(loss_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific loss of goods record by loss_id.

    Args:
        loss_id (int): ID of the loss of goods record

    Returns:
        Optional[Dict[str, Any]]: Loss of goods data or None if not found
    """
    query = "SELECT * FROM loss_of_goods WHERE loss_id = ?"
    results = execute_query(query, (loss_id,))
    return results[0] if results else None


def get_all_loss_of_goods() -> List[Dict[str, Any]]:
    """
    Get all loss of goods records.

    Returns:
        List[Dict[str, Any]]: List of all loss of goods records
    """
    query = "SELECT * FROM loss_of_goods ORDER BY loss_date DESC"
    return execute_query(query, ())


def get_loss_of_goods_by_farm(farm_id: int) -> List[Dict[str, Any]]:
    """
    Get loss of goods records by farm_id.

    Args:
        farm_id (int): ID of the farm record

    Returns:
        List[Dict[str, Any]]: List of loss of goods records for the farm
    """
    query = "SELECT * FROM loss_of_goods WHERE farm_id = ? ORDER BY loss_date DESC"
    return execute_query(query, (farm_id,))


def get_loss_of_goods_by_item_type(item_type: str) -> List[Dict[str, Any]]:
    """
    Get loss of goods records by item_type.

    Args:
        item_type (str): Type of item

    Returns:
        List[Dict[str, Any]]: List of loss of goods records for the item type
    """
    query = "SELECT * FROM loss_of_goods WHERE item_type = ? ORDER BY loss_date DESC"
    return execute_query(query, (item_type,))


def get_loss_of_goods_by_source(
    source_id: int, source_type: str
) -> List[Dict[str, Any]]:
    """
    Get loss of goods records by source_id and source_type.

    Args:
        source_id (int): ID of the source record
        source_type (str): Type of source

    Returns:
        List[Dict[str, Any]]: List of loss of goods records for the source
    """
    query = "SELECT * FROM loss_of_goods WHERE source_id = ? AND source_type = ? ORDER BY loss_date DESC"
    return execute_query(query, (source_id, source_type))


def get_loss_of_goods_by_date_range(
    start_date: str, end_date: str
) -> List[Dict[str, Any]]:
    """
    Get loss of goods records within a date range.

    Args:
        start_date (str): Start date of the range (inclusive)
        end_date (str): End date of the range (inclusive)

    Returns:
        List[Dict[str, Any]]: List of loss of goods records within the date range
    """
    query = "SELECT * FROM loss_of_goods WHERE loss_date BETWEEN ? AND ? ORDER BY loss_date DESC"
    return execute_query(query, (start_date, end_date))


def get_loss_of_goods_by_farm_and_date_range(
    farm_id: int, start_date: str, end_date: str
) -> List[Dict[str, Any]]:
    """
    Get loss of goods records for a specific farm within a date range.

    Args:
        farm_id (int): ID of the farm record
        start_date (str): Start date of the range (inclusive)
        end_date (str): End date of the range (inclusive)

    Returns:
        List[Dict[str, Any]]: List of loss of goods records for the farm within the date range
    """
    query = """
    SELECT * FROM loss_of_goods 
    WHERE farm_id = ? AND loss_date BETWEEN ? AND ? 
    ORDER BY loss_date DESC
    """
    return execute_query(query, (farm_id, start_date, end_date))


def calculate_total_loss_by_item_type(
    item_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None
) -> float:
    """
    Calculate total quantity lost for a specific item type, optionally within a date range.

    Args:
        item_type (str): Type of item
        start_date (str, optional): Start date of the range (inclusive)
        end_date (str, optional): End date of the range (inclusive)

    Returns:
        float: Total quantity lost
    """
    if start_date and end_date:
        query = """
        SELECT SUM(quantity) as total_loss FROM loss_of_goods 
        WHERE item_type = ? AND loss_date BETWEEN ? AND ?
        """
        result = execute_query(query, (item_type, start_date, end_date))
    else:
        query = (
            "SELECT SUM(quantity) as total_loss FROM loss_of_goods WHERE item_type = ?"
        )
        result = execute_query(query, (item_type,))

    return (
        result[0]["total_loss"]
        if result and result[0]["total_loss"] is not None
        else 0.0
    )


def calculate_total_loss_by_farm(
    farm_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None
) -> float:
    """
    Calculate total quantity lost for a specific farm, optionally within a date range.

    Args:
        farm_id (int): ID of the farm record
        start_date (str, optional): Start date of the range (inclusive)
        end_date (str, optional): End date of the range (inclusive)

    Returns:
        float: Total quantity lost
    """
    if start_date and end_date:
        query = """
        SELECT SUM(quantity) as total_loss FROM loss_of_goods 
        WHERE farm_id = ? AND loss_date BETWEEN ? AND ?
        """
        result = execute_query(query, (farm_id, start_date, end_date))
    else:
        query = (
            "SELECT SUM(quantity) as total_loss FROM loss_of_goods WHERE farm_id = ?"
        )
        result = execute_query(query, (farm_id,))

    return (
        result[0]["total_loss"]
        if result and result[0]["total_loss"] is not None
        else 0.0
    )


def update_loss_of_goods(
    loss_id: int,
    item_type: Optional[str] = None,
    source_type: Optional[str] = None,
    loss_date: Optional[str] = None,
    quantity: Optional[float] = None,
    reason: Optional[str] = None,
    notes: Optional[str] = None,
) -> int:
    """
    Update a loss of goods record.

    Args:
        loss_id (int): ID of the loss of goods record to update
        item_type (str, optional): New item type
        source_type (str, optional): New source type
        loss_date (str, optional): New loss date
        quantity (float, optional): New quantity
        reason (str, optional): New reason
        notes (str, optional): New notes

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []

    if item_type is not None:
        update_fields.append("item_type = ?")
        params.append(item_type)

    if source_type is not None:
        update_fields.append("source_type = ?")
        params.append(source_type)

    if loss_date is not None:
        update_fields.append("loss_date = ?")
        params.append(loss_date)

    if quantity is not None:
        update_fields.append("quantity = ?")
        params.append(quantity)

    if reason is not None:
        update_fields.append("reason = ?")
        params.append(reason)

    if notes is not None:
        update_fields.append("notes = ?")
        params.append(notes)

    if not update_fields:
        return 0  # Nothing to update

    # Add loss_id to params
    params.append(loss_id)

    query = f"""
    UPDATE loss_of_goods
    SET {", ".join(update_fields)}
    WHERE loss_id = ?
    """

    return execute_update(query, tuple(params))


def delete_loss_of_goods(loss_id: int) -> int:
    """
    Delete a loss of goods record.

    Args:
        loss_id (int): ID of the loss of goods record to delete

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM loss_of_goods WHERE loss_id = ?"
    return execute_update(query, (loss_id,))
