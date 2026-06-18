"""
Device PIN Storage Module for Mycelium

This module provides secure storage for device PINs using Fernet symmetric encryption.
PINs are encrypted before storage and decrypted on retrieval.
"""

import os
import secrets
from typing import Optional, Dict, Any, List
from pathlib import Path
from cryptography.fernet import Fernet

from storage.db_utils import execute_query, execute_insert, execute_update, get_timestamp


# Key file location
KEY_FILE = Path(__file__).parent.parent.parent / "data" / ".pin_key"


def _get_or_create_key() -> bytes:
    """
    Get or create the encryption key for PIN storage.

    The key is stored in a file in the data directory.
    If the file doesn't exist, a new key is generated.

    Returns:
        bytes: The encryption key
    """
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()

    # Generate new key
    key = Fernet.generate_key()

    # Ensure parent directory exists
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write key with restrictive permissions
    KEY_FILE.write_bytes(key)
    os.chmod(KEY_FILE, 0o600)

    return key


def _get_cipher() -> Fernet:
    """
    Get the Fernet cipher instance.

    Returns:
        Fernet: The cipher for encryption/decryption
    """
    key = _get_or_create_key()
    return Fernet(key)


def store_device_pin(device_id: int, device_type: str, pin: str) -> bool:
    """
    Store an encrypted PIN for a device.

    Args:
        device_id (int): ID of the device
        device_type (str): Type of device ('spore' or 'hyphae')
        pin (str): The 5-digit PIN to store

    Returns:
        bool: True if successful
    """
    if device_type not in ('spore', 'hyphae'):
        raise ValueError("device_type must be 'spore' or 'hyphae'")

    if not pin or len(pin) != 5 or not pin.isdigit():
        raise ValueError("PIN must be a 5-digit number")

    cipher = _get_cipher()
    encrypted_pin = cipher.encrypt(pin.encode()).decode()

    # Try to update existing record first
    query = """
    UPDATE device_pins
    SET encrypted_pin = ?, updated_at = ?
    WHERE device_id = ? AND device_type = ?
    """
    rows_affected = execute_update(query, (encrypted_pin, get_timestamp(), device_id, device_type))

    if rows_affected == 0:
        # Insert new record
        query = """
        INSERT INTO device_pins (device_id, device_type, encrypted_pin, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """
        timestamp = get_timestamp()
        execute_insert(query, (device_id, device_type, encrypted_pin, timestamp, timestamp))

    return True


def get_device_pin(device_id: int, device_type: str) -> Optional[str]:
    """
    Retrieve and decrypt a device PIN.

    Args:
        device_id (int): ID of the device
        device_type (str): Type of device ('spore' or 'hyphae')

    Returns:
        Optional[str]: The decrypted PIN, or None if not found
    """
    query = """
    SELECT encrypted_pin FROM device_pins
    WHERE device_id = ? AND device_type = ?
    """
    results = execute_query(query, (device_id, device_type))

    if not results:
        return None

    try:
        cipher = _get_cipher()
        encrypted_pin = results[0]['encrypted_pin']
        return cipher.decrypt(encrypted_pin.encode()).decode()
    except Exception:
        # Decryption failed (possibly corrupted or key changed)
        return None


def has_stored_pin(device_id: int, device_type: str) -> bool:
    """
    Check if a device has a stored PIN.

    Args:
        device_id (int): ID of the device
        device_type (str): Type of device ('spore' or 'hyphae')

    Returns:
        bool: True if a PIN is stored for this device
    """
    query = """
    SELECT 1 FROM device_pins
    WHERE device_id = ? AND device_type = ?
    """
    results = execute_query(query, (device_id, device_type))
    return len(results) > 0


def delete_device_pin(device_id: int, device_type: str) -> bool:
    """
    Delete a stored device PIN.

    Args:
        device_id (int): ID of the device
        device_type (str): Type of device ('spore' or 'hyphae')

    Returns:
        bool: True if a PIN was deleted, False if not found
    """
    query = """
    DELETE FROM device_pins
    WHERE device_id = ? AND device_type = ?
    """
    rows_affected = execute_update(query, (device_id, device_type))
    return rows_affected > 0


def get_all_devices_with_pins() -> List[Dict[str, Any]]:
    """
    Get a list of all devices that have stored PINs.

    Returns:
        List[Dict]: List of device_id and device_type pairs
    """
    query = """
    SELECT device_id, device_type, created_at, updated_at
    FROM device_pins
    ORDER BY device_type, device_id
    """
    return execute_query(query, ())


def verify_device_pin(device_id: int, device_type: str, pin: str) -> bool:
    """
    Verify that a provided PIN matches the stored PIN for a device.

    Args:
        device_id (int): ID of the device
        device_type (str): Type of device ('spore' or 'hyphae')
        pin (str): The PIN to verify

    Returns:
        bool: True if the PIN matches, False otherwise
    """
    stored_pin = get_device_pin(device_id, device_type)
    if stored_pin is None:
        return False
    return secrets.compare_digest(stored_pin, pin)


def rotate_encryption_key() -> int:
    """
    Rotate the encryption key and re-encrypt all stored PINs.

    This should be called periodically for security best practices.

    Returns:
        int: Number of PINs re-encrypted
    """
    # Get all current PINs (decrypted with old key)
    pins_data = []
    devices = get_all_devices_with_pins()

    for device in devices:
        pin = get_device_pin(device['device_id'], device['device_type'])
        if pin:
            pins_data.append({
                'device_id': device['device_id'],
                'device_type': device['device_type'],
                'pin': pin
            })

    # Generate new key
    new_key = Fernet.generate_key()
    KEY_FILE.write_bytes(new_key)
    os.chmod(KEY_FILE, 0o600)

    # Re-encrypt all PINs with new key
    for pin_data in pins_data:
        store_device_pin(
            pin_data['device_id'],
            pin_data['device_type'],
            pin_data['pin']
        )

    return len(pins_data)
