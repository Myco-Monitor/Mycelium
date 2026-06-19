"""
CRUD operations for alert_rules table.

Manages alert rule configurations for device monitoring.
"""

from typing import Optional, Dict, Any, List

from storage.db_utils import get_connection


def create_rule(
    rule_name: str,
    rule_type: str,
    device_type: Optional[str] = None,
    device_id: Optional[int] = None,
    room_id: Optional[int] = None,
    metric: Optional[str] = None,
    threshold_value: Optional[float] = None,
    threshold_duration_minutes: int = 5,
    notification_method: str = "ui",
    notification_target: Optional[str] = None,
) -> int:
    """
    Create a new alert rule.

    Args:
        rule_name: Human-readable name for the rule
        rule_type: One of 'offline', 'threshold_high', 'threshold_low', 'error', 'degraded'
        device_type: Optional filter for 'spore' or 'hyphae'
        device_id: Optional specific device ID
        room_id: Optional filter by room
        metric: Metric to monitor ('co2', 'temperature', 'humidity')
        threshold_value: Value that triggers alert
        threshold_duration_minutes: How long condition must persist
        notification_method: 'ui', 'email', or 'webhook'
        notification_target: Email or webhook URL for notifications

    Returns:
        int: ID of the new rule
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO alert_rules
        (rule_name, rule_type, device_type, device_id, room_id, metric,
         threshold_value, threshold_duration_minutes, notification_method, notification_target)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            rule_name,
            rule_type,
            device_type,
            device_id,
            room_id,
            metric,
            threshold_value,
            threshold_duration_minutes,
            notification_method,
            notification_target,
        ),
    )

    conn.commit()
    rule_id = cursor.lastrowid
    conn.close()

    return rule_id


def get_rule(rule_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific alert rule by ID.

    Args:
        rule_id: Rule ID

    Returns:
        Rule record or None
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM alert_rules WHERE rule_id = ?", (rule_id,))

    row = cursor.fetchone()
    if row:
        columns = [description[0] for description in cursor.description]
        result = dict(zip(columns, row))
    else:
        result = None

    conn.close()
    return result


def get_all_rules(enabled_only: bool = True) -> List[Dict[str, Any]]:
    """
    Get all alert rules.

    Args:
        enabled_only: If True, only return enabled rules

    Returns:
        List of rule records
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM alert_rules"
    if enabled_only:
        query += " WHERE enabled = 1"
    query += " ORDER BY rule_name"

    cursor.execute(query)

    columns = [description[0] for description in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()
    return results


def get_rules_by_type(rule_type: str) -> List[Dict[str, Any]]:
    """
    Get all enabled rules of a specific type.

    Args:
        rule_type: Rule type to filter by

    Returns:
        List of matching rules
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM alert_rules
        WHERE rule_type = ? AND enabled = 1
        ORDER BY rule_name
    """,
        (rule_type,),
    )

    columns = [description[0] for description in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()
    return results


def get_rules_for_device(device_id: int, device_type: str) -> List[Dict[str, Any]]:
    """
    Get all rules that apply to a specific device.

    Args:
        device_id: Device ID
        device_type: 'spore' or 'hyphae'

    Returns:
        List of applicable rules
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM alert_rules
        WHERE enabled = 1
        AND (device_id = ? OR device_id IS NULL)
        AND (device_type = ? OR device_type IS NULL)
        ORDER BY rule_name
    """,
        (device_id, device_type),
    )

    columns = [description[0] for description in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()
    return results


# Columns that update_rule() is permitted to write. Keys become SQL identifiers
# (they can't be parameterized), so they are whitelisted to prevent any
# identifier injection from caller-supplied kwargs (e.g. web form field names).
_UPDATABLE_COLUMNS = frozenset(
    {
        "rule_name",
        "rule_type",
        "device_type",
        "device_id",
        "room_id",
        "metric",
        "threshold_value",
        "threshold_duration_minutes",
        "notification_method",
        "notification_target",
        "enabled",
    }
)


def update_rule(rule_id: int, **kwargs) -> bool:
    """
    Update a rule with given fields.

    Args:
        rule_id: Rule ID to update
        **kwargs: Fields to update (must be names in _UPDATABLE_COLUMNS)

    Returns:
        True if updated

    Raises:
        ValueError: if an unknown column name is supplied
    """
    if not kwargs:
        return False

    invalid = set(kwargs) - _UPDATABLE_COLUMNS
    if invalid:
        raise ValueError(f"Unknown alert_rules column(s): {', '.join(sorted(invalid))}")

    # Build SET clause. Column names are whitelisted above; values are parameterized.
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [rule_id]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        f"""
        UPDATE alert_rules
        SET {fields}, updated_at = CURRENT_TIMESTAMP
        WHERE rule_id = ?
    """,
        values,
    )

    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()

    return updated


def toggle_rule(rule_id: int, enabled: bool) -> bool:
    """
    Enable or disable a rule.

    Args:
        rule_id: Rule ID
        enabled: True to enable, False to disable

    Returns:
        True if updated
    """
    return update_rule(rule_id, enabled=1 if enabled else 0)


def delete_rule(rule_id: int) -> bool:
    """
    Delete an alert rule.

    Args:
        rule_id: Rule ID to delete

    Returns:
        True if deleted
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM alert_rules WHERE rule_id = ?", (rule_id,))

    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()

    return deleted


def get_rules_count() -> Dict[str, int]:
    """
    Get count of rules by type.

    Returns:
        Dictionary with rule type counts
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT rule_type, COUNT(*) as count
        FROM alert_rules
        WHERE enabled = 1
        GROUP BY rule_type
    """)

    results = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()

    return results
