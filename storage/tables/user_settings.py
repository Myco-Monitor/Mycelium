"""
User Settings Table Module for Mycelium

This module provides functions for interacting with the user_settings table
in the Mycelium database. It includes authentication-related fields and functions.
"""

from typing import Dict, List, Optional, Any
import hashlib

from storage.db_utils import (
    execute_query,
    execute_insert,
    execute_update,
    get_timestamp,
)


def create_user_setting(
    user_name: str,
    user_password: str,
    owm_api_key: Optional[str] = None,
    owm_zip_code: Optional[str] = None,
    timezone_name: Optional[str] = None,
    time_format: Optional[str] = None,
    temp_pref: Optional[str] = None,
    reset_pin: Optional[str] = None,
    farm_id: Optional[int] = None,
    user_role: str = "user",
) -> int:
    """
    Create a new user setting record with authentication information.

    Args:
        user_name (str): Username for authentication
        user_password (str): Password (will be hashed with salt before storage)
        owm_api_key (str, optional): OpenWeatherMap API key
        owm_zip_code (str, optional): OpenWeatherMap zip code
        timezone_name (str, optional): User's timezone name
        time_format (str, optional): User's preferred time format
        temp_pref (str, optional): User's temperature preference (e.g., 'C' or 'F')
        reset_pin (str, optional): PIN for resetting settings
        farm_id (int, optional): Associated farm ID
        user_role (str, optional): User role ('user' or 'admin')

    Returns:
        int: ID of the newly created user setting
    """
    # Hash the password with salt
    user_password_hash = hash_password(user_password)

    query = """
    INSERT INTO user_settings (user_name, user_password, owm_api_key, owm_zip_code, timezone_name, 
                              time_format, temp_pref, reset_pin, farm_id, user_role)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    return execute_insert(
        query,
        (
            user_name,
            user_password_hash,
            owm_api_key,
            owm_zip_code,
            timezone_name,
            time_format,
            temp_pref,
            reset_pin,
            farm_id,
            user_role,
        ),
    )


def get_user_setting(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific user setting by user_id.

    Args:
        user_id (int): ID of the user setting

    Returns:
        Optional[Dict[str, Any]]: User setting data or None if not found
    """
    query = "SELECT * FROM user_settings WHERE user_id = ?"
    results = execute_query(query, (user_id,))
    return results[0] if results else None


def get_farm_user_settings(farm_id: int) -> List[Dict[str, Any]]:
    """
    Get all user settings for a specific farm.

    Args:
        farm_id (int): ID of the farm

    Returns:
        List[Dict[str, Any]]: List of user setting records
    """
    query = "SELECT * FROM user_settings WHERE farm_id = ?"
    return execute_query(query, (farm_id,))


def get_all_user_settings() -> List[Dict[str, Any]]:
    """
    Get all user settings.

    Returns:
        List[Dict[str, Any]]: List of all user setting records
    """
    query = "SELECT * FROM user_settings"
    return execute_query(query, ())


def update_user_setting(
    user_id: int,
    user_name: Optional[str] = None,
    user_password: Optional[str] = None,
    owm_api_key: Optional[str] = None,
    owm_zip_code: Optional[str] = None,
    timezone_name: Optional[str] = None,
    time_format: Optional[str] = None,
    temp_pref: Optional[str] = None,
    reset_pin: Optional[str] = None,
    farm_id: Optional[int] = None,
    user_role: Optional[str] = None,
    smtp_server: Optional[str] = None,
    smtp_port: Optional[str] = None,
    smtp_from: Optional[str] = None,
    smtp_to: Optional[str] = None,
    smtp_password: Optional[str] = None,
    smtp_use_tls: Optional[str] = None,
) -> int:
    """
    Update a user setting record.

    Args:
        user_id (int): ID of the user setting to update
        user_name (str, optional): New username
        user_password (str, optional): New password (will be hashed with salt)
        owm_api_key (str, optional): New OpenWeatherMap API key
        owm_zip_code (str, optional): New OpenWeatherMap zip code
        timezone_name (str, optional): New timezone name
        time_format (str, optional): New time format
        temp_pref (str, optional): New temperature preference
        reset_pin (str, optional): New reset PIN
        farm_id (int, optional): New associated farm ID
        user_role (str, optional): New user role ('user' or 'admin')

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    # Build the SET clause dynamically based on provided parameters
    set_clause = []
    params = []

    if user_name is not None:
        set_clause.append("user_name = ?")
        params.append(user_name)

    if user_password is not None:
        # Hash the password before storing
        password_hash = hash_password(user_password)
        set_clause.append("user_password = ?")
        params.append(password_hash)

    if owm_api_key is not None:
        set_clause.append("owm_api_key = ?")
        params.append(owm_api_key)

    if owm_zip_code is not None:
        set_clause.append("owm_zip_code = ?")
        params.append(owm_zip_code)

    if timezone_name is not None:
        set_clause.append("timezone_name = ?")
        params.append(timezone_name)

    if time_format is not None:
        set_clause.append("time_format = ?")
        params.append(time_format)

    if temp_pref is not None:
        set_clause.append("temp_pref = ?")
        params.append(temp_pref)

    if reset_pin is not None:
        set_clause.append("reset_pin = ?")
        params.append(reset_pin)

    if farm_id is not None:
        set_clause.append("farm_id = ?")
        params.append(farm_id)

    if user_role is not None:
        set_clause.append("user_role = ?")
        params.append(user_role)

    if smtp_server is not None:
        set_clause.append("smtp_server = ?")
        params.append(smtp_server)

    if smtp_port is not None:
        set_clause.append("smtp_port = ?")
        params.append(smtp_port)

    if smtp_from is not None:
        set_clause.append("smtp_from = ?")
        params.append(smtp_from)

    if smtp_to is not None:
        set_clause.append("smtp_to = ?")
        params.append(smtp_to)

    if smtp_password is not None:
        set_clause.append("smtp_password = ?")
        params.append(smtp_password)

    if smtp_use_tls is not None:
        set_clause.append("smtp_use_tls = ?")
        params.append(smtp_use_tls)

    if not set_clause:
        return 0  # Nothing to update

    # Add updated_at timestamp
    set_clause.append("updated_at = ?")
    params.append(get_timestamp())

    # Add user_id to params
    params.append(user_id)

    query = f"""
    UPDATE user_settings
    SET {", ".join(set_clause)}
    WHERE user_id = ?
    """

    return execute_update(query, tuple(params))


def delete_user_setting(user_id: int) -> int:
    """
    Delete a user setting record.

    Args:
        user_id (int): ID of the user setting to delete

    Returns:
        int: Number of rows affected (should be 1 if successful)
    """
    query = "DELETE FROM user_settings WHERE user_id = ?"
    return execute_update(query, (user_id,))


def delete_farm_user_settings(farm_id: int) -> int:
    """
    Delete all user settings for a specific farm.

    Args:
        farm_id (int): ID of the farm

    Returns:
        int: Number of rows affected
    """
    query = "DELETE FROM user_settings WHERE farm_id = ?"
    return execute_update(query, (farm_id,))


def hash_password(password: str) -> str:
    """
    Hash a password with a salt.

    Args:
        password (str): Password to hash

    Returns:
        str: Hashed password
    """
    # Use fixed salt for all passwords
    salt = "MycoMonitor2025"

    # Combine password and salt
    salted_password = password + salt

    # Create SHA-256 hash
    hash_obj = hashlib.sha256(salted_password.encode())

    # Return hexadecimal digest
    return hash_obj.hexdigest()


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify a password against a stored hash.

    Args:
        password (str): Password to verify
        stored_hash (str): Stored hash to compare against

    Returns:
        bool: True if password matches, False otherwise
    """
    # Hash the provided password
    password_hash = hash_password(password)

    # Compare with stored hash
    return password_hash == stored_hash


def get_user_by_username(user_name: str) -> Optional[Dict[str, Any]]:
    """
    Get a user setting by username.

    Args:
        user_name (str): Username to look up

    Returns:
        Optional[Dict[str, Any]]: User setting data or None if not found
    """
    query = "SELECT * FROM user_settings WHERE user_name = ?"
    results = execute_query(query, (user_name,))
    return results[0] if results else None


def authenticate_user(user_name: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate a user with username and password.

    Args:
        user_name (str): Username to authenticate
        password (str): Password to verify

    Returns:
        Optional[Dict[str, Any]]: User data if authentication successful, None otherwise
    """
    user = get_user_by_username(user_name)

    if user and verify_password(password, user["user_password"]):
        return user

    return None


def count_users() -> int:
    """
    Count the number of users in the user_settings table.

    Returns:
        int: Number of users
    """
    query = "SELECT COUNT(*) FROM user_settings"
    results = execute_query(query, ())
    return results[0]["COUNT(*)"] if results else 0
