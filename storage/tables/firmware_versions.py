"""
Firmware Versions table operations for Mycelium.

Tracks firmware binary files uploaded for OTA updates.
"""

from storage.db_utils import (
    execute_query,
    execute_insert,
    execute_update,
    get_timestamp,
)


def create_firmware_version(
    device_type, version, file_path, file_hash, file_size, release_notes=None
):
    """Create a new firmware version record."""
    query = """
    INSERT INTO firmware_versions (device_type, version, file_path, file_hash, file_size, release_notes, uploaded_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    return execute_insert(
        query,
        (
            device_type,
            version,
            file_path,
            file_hash,
            file_size,
            release_notes,
            get_timestamp(),
        ),
    )


def get_all_firmware_versions(device_type=None):
    """Get all firmware versions, optionally filtered by device type."""
    if device_type:
        query = "SELECT * FROM firmware_versions WHERE device_type = ? ORDER BY uploaded_at DESC"
        return execute_query(query, (device_type,))
    query = "SELECT * FROM firmware_versions ORDER BY uploaded_at DESC"
    return execute_query(query)


def get_firmware_version(version_id):
    """Get a single firmware version by ID."""
    query = "SELECT * FROM firmware_versions WHERE version_id = ?"
    results = execute_query(query, (version_id,))
    return results[0] if results else None


def get_latest_firmware(device_type):
    """Get the latest firmware version for a device type."""
    query = "SELECT * FROM firmware_versions WHERE device_type = ? ORDER BY uploaded_at DESC LIMIT 1"
    results = execute_query(query, (device_type,))
    return results[0] if results else None


def delete_firmware_version(version_id):
    """Delete a firmware version record."""
    query = "DELETE FROM firmware_versions WHERE version_id = ?"
    return execute_update(query, (version_id,))
