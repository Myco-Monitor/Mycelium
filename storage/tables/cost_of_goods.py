"""
Cost of Goods Table Module for Mycelium

This module provides functions for interacting with the cost_of_goods table
in the Mycelium database.
"""

from typing import Dict, List, Optional, Any

from storage.db_utils import (
    execute_query,
    execute_insert,
    execute_update,
    get_timestamp,
)


def create_cost_of_goods(
    item_id: int,
    item_name: str,
    item_cost: float,
    item_count: int,
    weight_lbs: float,
    item_used: int = 0,
    used_weight: float = 0.0,
    purchase_ts: Optional[str] = None,
) -> int:
    """
    Create a new cost of goods record.

    Args:
        item_id (int): Reference to product category
        item_name (str): Name of the item
        item_cost (float): Cost of the item
        item_count (int): Count of items
        weight_lbs (float): Weight in pounds
        item_used (int, optional): Number of items used, defaults to 0
        used_weight (float, optional): Weight used, defaults to 0.0
        purchase_ts (str, optional): Purchase timestamp

    Returns:
        int: ID of the newly created record (unit_id)
    """
    query = """
    INSERT INTO cost_of_goods (item_id, item_name, item_cost, item_count, weight_lbs, 
                              item_used, used_weight, purchase_ts)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    return execute_insert(
        query,
        (
            item_id,
            item_name,
            item_cost,
            item_count,
            weight_lbs,
            item_used,
            used_weight,
            purchase_ts,
        ),
    )


def get_cost_of_goods(unit_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific cost of goods record by unit_id.

    Args:
        unit_id (int): ID of the cost of goods record

    Returns:
        Optional[Dict[str, Any]]: Cost of goods data or None if not found
    """
    query = "SELECT * FROM cost_of_goods WHERE unit_id = ?"
    results = execute_query(query, (unit_id,))
    return results[0] if results else None


def get_all_cost_of_goods() -> List[Dict[str, Any]]:
    """
    Get all cost of goods records.

    Returns:
        List[Dict[str, Any]]: List of all cost of goods records
    """
    query = "SELECT * FROM cost_of_goods ORDER BY purchase_ts DESC"
    return execute_query(query, ())


def get_cost_of_goods_by_name(item_name: str) -> List[Dict[str, Any]]:
    """
    Get cost of goods records by item name.

    Args:
        item_name (str): Name of the item to search for

    Returns:
        List[Dict[str, Any]]: List of matching cost of goods records
    """
    query = (
        "SELECT * FROM cost_of_goods WHERE item_name LIKE ? ORDER BY purchase_ts DESC"
    )
    return execute_query(query, (f"%{item_name}%",))


def get_cost_of_goods_by_date_range(
    start_date: str, end_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get cost of goods records within a date range.

    Args:
        start_date (str): Start date for the range
        end_date (str, optional): End date for the range, defaults to current time if None

    Returns:
        List[Dict[str, Any]]: List of cost of goods records in the date range
    """
    if end_date is None:
        end_date = get_timestamp()

    query = """
    SELECT * FROM cost_of_goods 
    WHERE purchase_ts >= ? AND purchase_ts <= ? 
    ORDER BY purchase_ts DESC
    """
    return execute_query(query, (start_date, end_date))


def get_available_cost_of_goods() -> List[Dict[str, Any]]:
    """
    Get cost of goods records that still have available items.

    Returns:
        List[Dict[str, Any]]: List of cost of goods records with available items
    """
    query = """
    SELECT * FROM cost_of_goods 
    WHERE item_count > item_used OR weight_lbs > used_weight 
    ORDER BY purchase_ts
    """
    return execute_query(query, ())


def update_cost_of_goods(
    unit_id: int,
    item_id: Optional[int] = None,
    item_name: Optional[str] = None,
    item_cost: Optional[float] = None,
    item_count: Optional[int] = None,
    weight_lbs: Optional[float] = None,
    item_used: Optional[int] = None,
    used_weight: Optional[float] = None,
    purchase_ts: Optional[str] = None,
) -> int:
    """
    Update a cost of goods record.

    Args:
        unit_id (int): ID of the cost of goods record to update
        item_id (int, optional): New product category reference
        item_name (str, optional): New item name
        item_cost (float, optional): New item cost
        item_count (int, optional): New item count
        weight_lbs (float, optional): New weight in pounds
        item_used (int, optional): New number of items used
        used_weight (float, optional): New weight used
        purchase_ts (str, optional): New purchase timestamp

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the query dynamically based on which fields are provided
    update_fields = []
    params = []

    if item_id is not None:
        update_fields.append("item_id = ?")
        params.append(item_id)

    if item_name is not None:
        update_fields.append("item_name = ?")
        params.append(item_name)

    if item_cost is not None:
        update_fields.append("item_cost = ?")
        params.append(item_cost)

    if item_count is not None:
        update_fields.append("item_count = ?")
        params.append(item_count)

    if weight_lbs is not None:
        update_fields.append("weight_lbs = ?")
        params.append(weight_lbs)

    if item_used is not None:
        update_fields.append("item_used = ?")
        params.append(item_used)

    if used_weight is not None:
        update_fields.append("used_weight = ?")
        params.append(used_weight)

    if purchase_ts is not None:
        update_fields.append("purchase_ts = ?")
        params.append(purchase_ts)

    if not update_fields:
        return 0  # Nothing to update

    # Add updated_at timestamp
    update_fields.append("updated_at = ?")
    params.append(get_timestamp())

    # Add unit_id to params
    params.append(unit_id)

    query = f"""
    UPDATE cost_of_goods
    SET {", ".join(update_fields)}
    WHERE unit_id = ?
    """

    return execute_update(query, tuple(params))


def update_usage(
    unit_id: int, additional_used: int = 0, additional_weight: float = 0.0
) -> int:
    """
    Update the usage counts for a cost of goods record.

    Args:
        unit_id (int): ID of the cost of goods record
        additional_used (int, optional): Additional items used
        additional_weight (float, optional): Additional weight used

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    if additional_used == 0 and additional_weight == 0.0:
        return 0  # Nothing to update

    # Get current values
    current = get_cost_of_goods(unit_id)
    if not current:
        return 0

    # Calculate new values
    new_used = current["item_used"] + additional_used
    new_weight = current["used_weight"] + additional_weight

    # Ensure we don't exceed the available amounts
    if new_used > current["item_count"]:
        new_used = current["item_count"]

    if new_weight > current["weight_lbs"]:
        new_weight = current["weight_lbs"]

    # Update the record
    query = """
    UPDATE cost_of_goods
    SET item_used = ?, used_weight = ?, updated_at = ?
    WHERE unit_id = ?
    """

    return execute_update(query, (new_used, new_weight, get_timestamp(), unit_id))


def get_cost_of_goods_by_item_id(item_id: int) -> List[Dict[str, Any]]:
    """
    Get cost of goods records by product category (item_id).

    Args:
        item_id (int): Product category ID to filter by

    Returns:
        List[Dict[str, Any]]: List of cost of goods records for the category
    """
    query = """
    SELECT cog.*, pc.category_name, pc.category_type 
    FROM cost_of_goods cog
    JOIN product_categories pc ON cog.item_id = pc.item_id
    WHERE cog.item_id = ?
    ORDER BY cog.purchase_ts DESC
    """
    return execute_query(query, (item_id,))


def get_cost_of_goods_with_category() -> List[Dict[str, Any]]:
    """
    Get all cost of goods records with their category information.

    Returns:
        List[Dict[str, Any]]: List of cost of goods records with category details
    """
    query = """
    SELECT cog.*, pc.category_name, pc.category_type, pc.category_desc
    FROM cost_of_goods cog
    JOIN product_categories pc ON cog.item_id = pc.item_id
    WHERE pc.active = 1
    ORDER BY cog.purchase_ts DESC
    """
    return execute_query(query)


def get_available_cost_of_goods_by_category(item_id: int) -> List[Dict[str, Any]]:
    """
    Get available cost of goods records for a specific category.

    Args:
        item_id (int): Product category ID to filter by

    Returns:
        List[Dict[str, Any]]: List of available cost of goods records for the category
    """
    query = """
    SELECT cog.*, pc.category_name, pc.category_type
    FROM cost_of_goods cog
    JOIN product_categories pc ON cog.item_id = pc.item_id
    WHERE cog.item_id = ? AND cog.item_used < cog.item_count
    ORDER BY cog.purchase_ts
    """
    return execute_query(query, (item_id,))


def delete_cost_of_goods(unit_id: int) -> int:
    """
    Delete a cost of goods record.

    Args:
        unit_id (int): ID of the cost of goods record to delete

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM cost_of_goods WHERE unit_id = ?"
    return execute_update(query, (unit_id,))
