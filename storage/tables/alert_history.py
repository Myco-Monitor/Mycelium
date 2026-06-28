"""
CRUD operations for alert_history table.

Tracks triggered alerts and their resolution status.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from storage.db_utils import get_connection


def create_alert(
    rule_id: int,
    alert_message: str,
    device_id: Optional[int] = None,
    device_type: Optional[str] = None,
    alert_value: Optional[float] = None,
) -> int:
    """
    Create a new alert record.

    Args:
        rule_id: ID of the rule that triggered the alert
        alert_message: Human-readable alert message
        device_id: Device that triggered the alert
        device_type: 'spore' or 'hyphae'
        alert_value: The value that triggered the alert

    Returns:
        int: ID of the new alert
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO alert_history
        (rule_id, device_id, device_type, alert_message, alert_value)
        VALUES (?, ?, ?, ?, ?)
    """,
        (rule_id, device_id, device_type, alert_message, alert_value),
    )

    conn.commit()
    alert_id = cursor.lastrowid
    conn.close()

    return alert_id


def get_alert(alert_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific alert by ID.

    Args:
        alert_id: Alert ID

    Returns:
        Alert record or None
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT ah.*, ar.rule_name, ar.rule_type
        FROM alert_history ah
        JOIN alert_rules ar ON ah.rule_id = ar.rule_id
        WHERE ah.alert_id = ?
    """,
        (alert_id,),
    )

    row = cursor.fetchone()
    if row:
        columns = [description[0] for description in cursor.description]
        result = dict(zip(columns, row))
    else:
        result = None

    conn.close()
    return result


def get_active_alerts() -> List[Dict[str, Any]]:
    """
    Get all unresolved alerts.

    Returns:
        List of active alert records
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ah.*, ar.rule_name, ar.rule_type
        FROM alert_history ah
        JOIN alert_rules ar ON ah.rule_id = ar.rule_id
        WHERE ah.resolved_at IS NULL
        ORDER BY ah.triggered_at DESC
    """)

    columns = [description[0] for description in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()
    return results


def get_unacknowledged_alerts() -> List[Dict[str, Any]]:
    """
    Get all unacknowledged alerts.

    Returns:
        List of unacknowledged alert records
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ah.*, ar.rule_name, ar.rule_type
        FROM alert_history ah
        JOIN alert_rules ar ON ah.rule_id = ar.rule_id
        WHERE ah.acknowledged = 0
        ORDER BY ah.triggered_at DESC
    """)

    columns = [description[0] for description in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()
    return results


def get_alert_history(days: int = 7, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get alert history for the past N days.

    Args:
        days: Number of days to look back
        limit: Maximum number of records

    Returns:
        List of alert records
    """
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT ah.*, ar.rule_name, ar.rule_type
        FROM alert_history ah
        JOIN alert_rules ar ON ah.rule_id = ar.rule_id
        WHERE ah.triggered_at >= ?
        ORDER BY ah.triggered_at DESC
        LIMIT ?
    """,
        (cutoff, limit),
    )

    columns = [description[0] for description in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()
    return results


def get_alerts_for_device(
    device_id: int, device_type: str, days: int = 7
) -> List[Dict[str, Any]]:
    """
    Get alerts for a specific device.

    Args:
        device_id: Device ID
        device_type: 'spore' or 'hyphae'
        days: Number of days to look back

    Returns:
        List of alert records
    """
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT ah.*, ar.rule_name, ar.rule_type
        FROM alert_history ah
        JOIN alert_rules ar ON ah.rule_id = ar.rule_id
        WHERE ah.device_id = ? AND ah.device_type = ?
        AND ah.triggered_at >= ?
        ORDER BY ah.triggered_at DESC
    """,
        (device_id, device_type, cutoff),
    )

    columns = [description[0] for description in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()
    return results


def resolve_alert(alert_id: int) -> bool:
    """
    Mark an alert as resolved.

    Args:
        alert_id: Alert ID

    Returns:
        True if updated
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE alert_history
        SET resolved_at = CURRENT_TIMESTAMP
        WHERE alert_id = ?
    """,
        (alert_id,),
    )

    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()

    return updated


def acknowledge_alert(alert_id: int, user_id: int, notes: Optional[str] = None) -> bool:
    """
    Acknowledge an alert.

    Args:
        alert_id: Alert ID
        user_id: User acknowledging the alert
        notes: Optional notes

    Returns:
        True if updated
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE alert_history
        SET acknowledged = 1,
            acknowledged_by = ?,
            acknowledged_at = CURRENT_TIMESTAMP,
            notes = ?
        WHERE alert_id = ?
    """,
        (user_id, notes, alert_id),
    )

    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()

    return updated


def has_active_alert(rule_id: int, device_id: Optional[int]) -> bool:
    """
    Return True if an unresolved alert already exists for this rule + device.

    This collapses repeated triggers of the same condition into a single active
    alert: while one is open (unresolved), no new alert is created; once it is
    resolved (e.g. the reading drops back below the threshold, or the user
    resolves it), the next trigger opens exactly one new alert.

    Deliberately uses no time window. The previous time-based dedup compared a
    local-time ISO cutoff (``datetime.now().isoformat()``, e.g.
    ``2026-06-28T19:04:30``) against the DB's UTC ``CURRENT_TIMESTAMP``
    ``triggered_at`` (e.g. ``2026-06-28 23:33:56`` -- space separator, UTC), so
    the string comparison always failed and a fresh alert was created on every
    poll.

    Args:
        rule_id: Rule ID
        device_id: Device ID (can be None for rule-wide alerts)

    Returns:
        True if an active (unresolved) alert exists
    """
    conn = get_connection()
    cursor = conn.cursor()

    if device_id is not None:
        cursor.execute(
            """
            SELECT COUNT(*) FROM alert_history
            WHERE rule_id = ? AND device_id = ? AND resolved_at IS NULL
            """,
            (rule_id, device_id),
        )
    else:
        cursor.execute(
            """
            SELECT COUNT(*) FROM alert_history
            WHERE rule_id = ? AND device_id IS NULL AND resolved_at IS NULL
            """,
            (rule_id,),
        )

    count = cursor.fetchone()[0]
    conn.close()

    return count > 0


def auto_resolve_for_rule_device(rule_id: int, device_id: int) -> int:
    """
    Auto-resolve all active alerts for a rule/device combination.

    Args:
        rule_id: Rule ID
        device_id: Device ID

    Returns:
        Number of alerts resolved
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE alert_history
        SET resolved_at = CURRENT_TIMESTAMP
        WHERE rule_id = ?
        AND device_id = ?
        AND resolved_at IS NULL
    """,
        (rule_id, device_id),
    )

    conn.commit()
    resolved_count = cursor.rowcount
    conn.close()

    return resolved_count


def get_alert_counts() -> Dict[str, int]:
    """
    Get alert counts by status.

    Returns:
        Dictionary with counts
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN resolved_at IS NULL THEN 1 ELSE 0 END) as active,
            SUM(CASE WHEN acknowledged = 0 THEN 1 ELSE 0 END) as unacknowledged
        FROM alert_history
        WHERE triggered_at >= datetime('now', '-24 hours')
    """)

    row = cursor.fetchone()
    conn.close()

    return {
        "total_24h": row[0] or 0,
        "active": row[1] or 0,
        "unacknowledged": row[2] or 0,
    }


def cleanup_old_alerts(days: int = 30) -> int:
    """
    Remove old resolved alerts.

    Args:
        days: Keep resolved alerts for this many days

    Returns:
        Number of records deleted
    """
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM alert_history
        WHERE resolved_at IS NOT NULL
        AND resolved_at < ?
    """,
        (cutoff,),
    )

    conn.commit()
    deleted_count = cursor.rowcount
    conn.close()

    return deleted_count
