"""
Calibration History table operations for Mycelium.

Logs CO2 sensor calibration events for Spore devices.
"""

from storage.db_utils import execute_query, execute_insert, get_timestamp


def create_calibration_event(device_id, cal_type, target_ppm, status, notes=None):
    """Log a calibration event."""
    query = """
    INSERT INTO calibration_history (device_id, cal_type, target_ppm, status, started_at, notes)
    VALUES (?, ?, ?, ?, ?, ?)
    """
    return execute_insert(query, (device_id, cal_type, target_ppm, status, get_timestamp(), notes))


def get_calibration_history(device_id=None, limit=50):
    """Get calibration history, optionally filtered by device."""
    if device_id is not None:
        query = "SELECT * FROM calibration_history WHERE device_id = ? ORDER BY started_at DESC LIMIT ?"
        return execute_query(query, (device_id, limit))
    query = "SELECT * FROM calibration_history ORDER BY started_at DESC LIMIT ?"
    return execute_query(query, (limit,))


def get_last_calibration(device_id):
    """Get the most recent calibration for a device."""
    query = "SELECT * FROM calibration_history WHERE device_id = ? ORDER BY started_at DESC LIMIT 1"
    results = execute_query(query, (device_id,))
    return results[0] if results else None
