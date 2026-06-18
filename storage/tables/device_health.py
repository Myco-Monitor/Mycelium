"""
CRUD operations for device_health_log table.

Tracks device health check results over time for monitoring and analytics.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from storage.db_utils import get_connection


def log_health_check(
    device_id: int,
    device_type: str,
    is_online: bool,
    response_time_ms: Optional[int] = None,
    error_message: Optional[str] = None,
    http_status_code: Optional[int] = None
) -> int:
    """
    Log a health check result.

    Args:
        device_id: Device ID
        device_type: 'spore' or 'hyphae'
        is_online: Whether device responded successfully
        response_time_ms: Response time in milliseconds
        error_message: Error message if failed
        http_status_code: HTTP status code if available

    Returns:
        int: ID of the new log entry
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO device_health_log
        (device_id, device_type, is_online, response_time_ms, error_message, http_status_code)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (device_id, device_type, 1 if is_online else 0, response_time_ms, error_message, http_status_code))

    conn.commit()
    log_id = cursor.lastrowid
    conn.close()

    return log_id


def get_health_history(
    device_id: int,
    device_type: str,
    hours: int = 24
) -> List[Dict[str, Any]]:
    """
    Get health check history for a device.

    Args:
        device_id: Device ID
        device_type: 'spore' or 'hyphae'
        hours: Number of hours to look back

    Returns:
        List of health check records
    """
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM device_health_log
        WHERE device_id = ? AND device_type = ?
        AND check_time >= ?
        ORDER BY check_time DESC
    """, (device_id, device_type, cutoff))

    columns = [description[0] for description in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()
    return results


def get_recent_status(
    device_id: int,
    device_type: str
) -> Optional[Dict[str, Any]]:
    """
    Get most recent health check for a device.

    Args:
        device_id: Device ID
        device_type: 'spore' or 'hyphae'

    Returns:
        Most recent health check record or None
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM device_health_log
        WHERE device_id = ? AND device_type = ?
        ORDER BY check_time DESC LIMIT 1
    """, (device_id, device_type))

    row = cursor.fetchone()
    if row:
        columns = [description[0] for description in cursor.description]
        result = dict(zip(columns, row))
    else:
        result = None

    conn.close()
    return result


def calculate_uptime(
    device_id: int,
    device_type: str,
    hours: int = 24
) -> float:
    """
    Calculate uptime percentage over a period.

    Args:
        device_id: Device ID
        device_type: 'spore' or 'hyphae'
        hours: Number of hours to calculate over

    Returns:
        Uptime percentage (0.0 to 100.0)
    """
    history = get_health_history(device_id, device_type, hours)
    if not history:
        return 0.0

    online_count = sum(1 for h in history if h.get('is_online'))
    return (online_count / len(history)) * 100


def calculate_avg_response_time(
    device_id: int,
    device_type: str,
    hours: int = 24
) -> Optional[float]:
    """
    Calculate average response time over a period.

    Args:
        device_id: Device ID
        device_type: 'spore' or 'hyphae'
        hours: Number of hours to calculate over

    Returns:
        Average response time in milliseconds, or None if no data
    """
    history = get_health_history(device_id, device_type, hours)
    response_times = [h['response_time_ms'] for h in history if h.get('response_time_ms') is not None]

    if not response_times:
        return None

    return sum(response_times) / len(response_times)


def get_device_health_metrics(
    device_id: int,
    device_type: str
) -> Dict[str, Any]:
    """
    Get comprehensive health metrics for a device.

    Args:
        device_id: Device ID
        device_type: 'spore' or 'hyphae'

    Returns:
        Dictionary with uptime, response times, and recent status
    """
    return {
        'uptime_24h': calculate_uptime(device_id, device_type, 24),
        'uptime_7d': calculate_uptime(device_id, device_type, 168),
        'avg_response_24h': calculate_avg_response_time(device_id, device_type, 24),
        'recent_status': get_recent_status(device_id, device_type),
        'check_count_24h': len(get_health_history(device_id, device_type, 24))
    }


def cleanup_old_records(days: int = 7) -> int:
    """
    Remove health records older than specified days.

    Args:
        days: Number of days to keep

    Returns:
        Number of records deleted
    """
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM device_health_log
        WHERE check_time < ?
    """, (cutoff,))

    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    return deleted_count


def get_all_devices_health_summary() -> List[Dict[str, Any]]:
    """
    Get health summary for all devices.

    Returns:
        List of device health summaries
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get latest health check for each device
    cursor.execute("""
        SELECT
            device_id,
            device_type,
            MAX(check_time) as last_check,
            (SELECT is_online FROM device_health_log h2
             WHERE h2.device_id = h1.device_id
             AND h2.device_type = h1.device_type
             ORDER BY check_time DESC LIMIT 1) as is_online,
            (SELECT response_time_ms FROM device_health_log h2
             WHERE h2.device_id = h1.device_id
             AND h2.device_type = h1.device_type
             ORDER BY check_time DESC LIMIT 1) as last_response_ms
        FROM device_health_log h1
        GROUP BY device_id, device_type
    """)

    columns = [description[0] for description in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()
    return results
