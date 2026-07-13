"""
CRUD operations for notification_log table.

Tracks notification delivery attempts and status.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

from storage.db_utils import get_connection


def log_notification(
    alert_id: int,
    notification_method: str,
    recipient: str,
    status: str,
    error_message: Optional[str] = None,
) -> int:
    """
    Log a notification attempt.

    Args:
        alert_id: ID of the alert being notified
        notification_method: 'email' or 'webhook'
        recipient: Email address or webhook URL
        status: 'sent', 'failed', or 'queued'
        error_message: Error message if failed

    Returns:
        int: ID of the log entry
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO notification_log
        (alert_id, notification_method, recipient, status, error_message)
        VALUES (?, ?, ?, ?, ?)
    """,
        (alert_id, notification_method, recipient, status, error_message),
    )

    conn.commit()
    log_id = cursor.lastrowid
    conn.close()

    return log_id


def get_logs_for_alert(alert_id: int) -> List[Dict[str, Any]]:
    """
    Get all notification logs for an alert.

    Args:
        alert_id: Alert ID

    Returns:
        List of log records
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM notification_log
        WHERE alert_id = ?
        ORDER BY sent_at DESC
    """,
        (alert_id,),
    )

    columns = [description[0] for description in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()
    return results


def get_failed_notifications(hours: int = 24) -> List[Dict[str, Any]]:
    """
    Get recent failed notifications.

    Args:
        hours: Number of hours to look back

    Returns:
        List of failed notification records
    """
    cutoff = (
        datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
    ).isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM notification_log
        WHERE status = 'failed'
        AND sent_at >= ?
        ORDER BY sent_at DESC
    """,
        (cutoff,),
    )

    columns = [description[0] for description in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()
    return results


def get_notification_stats(hours: int = 24) -> Dict[str, int]:
    """
    Get notification statistics.

    Args:
        hours: Number of hours to analyze

    Returns:
        Dictionary with statistics
    """
    cutoff = (
        datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
    ).isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
        FROM notification_log
        WHERE sent_at >= ?
    """,
        (cutoff,),
    )

    row = cursor.fetchone()
    conn.close()

    return {"total": row[0] or 0, "sent": row[1] or 0, "failed": row[2] or 0}


def cleanup_old_logs(days: int = 30) -> int:
    """
    Remove old notification logs.

    Args:
        days: Keep logs for this many days

    Returns:
        Number of records deleted
    """
    cutoff = (
        datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    ).isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM notification_log
        WHERE sent_at < ?
    """,
        (cutoff,),
    )

    conn.commit()
    deleted_count = cursor.rowcount
    conn.close()

    return deleted_count
