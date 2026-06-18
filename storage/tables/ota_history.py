"""
OTA History table operations for Mycelium.

Logs OTA firmware update events for auditing and troubleshooting.
"""

from storage.db_utils import execute_query, execute_insert, get_timestamp


def create_ota_event(device_id, device_type, firmware_name, status, error_message=None):
    """Log an OTA event."""
    query = """
    INSERT INTO ota_history (device_id, device_type, firmware_name, status, error_message, started_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """
    return execute_insert(query, (device_id, device_type, firmware_name, status, error_message, get_timestamp()))


def get_ota_history(device_id=None, device_type=None, limit=50):
    """Get OTA history, optionally filtered by device."""
    conditions = []
    params = []

    if device_id is not None:
        conditions.append("device_id = ?")
        params.append(device_id)
    if device_type:
        conditions.append("device_type = ?")
        params.append(device_type)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT * FROM ota_history {where} ORDER BY started_at DESC LIMIT ?"
    params.append(limit)
    return execute_query(query, tuple(params))


def get_recent_ota_events(hours=24):
    """Get OTA events from the last N hours."""
    query = """
    SELECT * FROM ota_history
    WHERE started_at >= datetime('now', ? || ' hours')
    ORDER BY started_at DESC
    """
    return execute_query(query, (f"-{hours}",))
