"""
Tests for the user_settings table module.

This module contains tests for the user_settings table CRUD operations.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.tables.user_settings import (
    create_user_setting, get_user_setting, get_farm_user_settings,
    get_all_user_settings, update_user_setting, delete_user_setting,
    delete_farm_user_settings, hash_password, verify_password,
    get_user_by_username, authenticate_user, count_users
)
from storage.tables.farms import create_farm
from storage.db_utils import get_connection, execute_query, DB_PATH

def clean_test_data():
    """Clean up any test data from previous test runs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete any test user settings that might exist from previous test runs
        cursor.execute("DELETE FROM user_settings WHERE farm_id IN (SELECT farm_id FROM farms WHERE farm_name LIKE 'Test User Settings Farm%')")
        cursor.execute("DELETE FROM farms WHERE farm_name LIKE 'Test User Settings Farm%'")
        # Also delete any user settings not associated with a farm but created during tests
        cursor.execute("DELETE FROM user_settings WHERE owm_zip_code LIKE 'TEST%'")
        # Delete test users by username
        cursor.execute("DELETE FROM user_settings WHERE user_name LIKE 'test_user%'")
        conn.commit()
    finally:
        conn.close()

def test_user_settings_crud():
    """Test CRUD operations for the user_settings table."""
    print("\nTesting user_settings table CRUD operations...")
    
    try:
        # Clean up any existing test data
        clean_test_data()
        
        # Create a test farm first
        print("Creating test farm...")
        farm_id = create_farm(
            farm_name="Test User Settings Farm",
            farm_loc="Test Location",
            farm_desc="Test Description"
        )
        
        # Now run the tests
        
        # Test create_user_setting
        print("Testing create_user_setting...")
        user_id1 = create_user_setting(
            user_name="test_user1",
            user_password="password1",
            owm_api_key="test_api_key_1",
            owm_zip_code="TEST12345",
            timezone_name="America/New_York",
            time_format="12h",
            temp_pref="F",
            reset_pin="1234",
            farm_id=farm_id,
            user_role="admin"
        )
        
        user_id2 = create_user_setting(
            user_name="test_user2",
            user_password="password2",
            owm_zip_code="TEST54321",
            timezone_name="America/Los_Angeles",
            temp_pref="C",
            farm_id=farm_id
        )
        
        user_id3 = create_user_setting(
            user_name="test_user3",
            user_password="password3",
            owm_api_key="test_api_key_3",
            owm_zip_code="TEST67890"
        )
        
        assert user_id1 > 0, f"Expected positive user_id, got {user_id1}"
        assert user_id2 > 0, f"Expected positive user_id, got {user_id2}"
        assert user_id3 > 0, f"Expected positive user_id, got {user_id3}"
        
        # Test get_user_setting
        print("Testing get_user_setting...")
        user1 = get_user_setting(user_id1)
        assert user1 is not None, "Failed to retrieve user1"
        assert user1['user_name'] == "test_user1", f"Expected username 'test_user1', got '{user1['user_name']}'"
        assert user1['user_password'] is not None, "Expected user_password to be set"
        assert user1['user_role'] == "admin", f"Expected role 'admin', got '{user1['user_role']}'"
        assert user1['owm_api_key'] == "test_api_key_1", f"Expected owm_api_key 'test_api_key_1', got '{user1['owm_api_key']}'"
        assert user1['owm_zip_code'] == "TEST12345", f"Expected owm_zip_code 'TEST12345', got '{user1['owm_zip_code']}'"
        assert user1['timezone_name'] == "America/New_York", f"Expected timezone_name 'America/New_York', got '{user1['timezone_name']}'"
        assert user1['time_format'] == "12h", f"Expected time_format '12h', got '{user1['time_format']}'"
        assert user1['temp_pref'] == "F", f"Expected temp_pref 'F', got '{user1['temp_pref']}'"
        assert user1['reset_pin'] == "1234", f"Expected reset_pin '1234', got '{user1['reset_pin']}'"
        assert user1['farm_id'] == farm_id, f"Expected farm_id {farm_id}, got {user1['farm_id']}"
        
        user2 = get_user_setting(user_id2)
        assert user2 is not None, "Failed to retrieve user2"
        assert user2['user_name'] == "test_user2", f"Expected username 'test_user2', got '{user2['user_name']}'"
        assert user2['user_role'] == "user", f"Expected role 'user', got '{user2['user_role']}'"
        assert user2['owm_api_key'] is None, f"Expected owm_api_key None, got '{user2['owm_api_key']}'"
        assert user2['time_format'] is None, f"Expected time_format None, got '{user2['time_format']}'"
        assert user2['reset_pin'] is None, f"Expected reset_pin None, got '{user2['reset_pin']}'"
        
        user3 = get_user_setting(user_id3)
        assert user3 is not None, "Failed to retrieve user3"
        assert user3['user_name'] == "test_user3", f"Expected username 'test_user3', got '{user3['user_name']}'"
        assert user3['farm_id'] is None, f"Expected farm_id None, got {user3['farm_id']}"
        
        # Test get_farm_user_settings
        print("Testing get_farm_user_settings...")
        farm_users = get_farm_user_settings(farm_id)
        assert len(farm_users) == 2, f"Expected 2 user settings for farm, got {len(farm_users)}"
        
        # Test get_all_user_settings
        print("Testing get_all_user_settings...")
        all_users = get_all_user_settings()
        assert len(all_users) >= 3, f"Expected at least 3 user settings, got {len(all_users)}"
        
        # Test update_user_setting
        print("Testing update_user_setting...")
        rows_updated = update_user_setting(
            user_id1,
            user_name="test_user1_updated",
            user_password="new_password",
            owm_zip_code="TEST98765",
            time_format="24h",
            temp_pref="C",
            user_role="user"
        )
        assert rows_updated == 1, f"Expected 1 row updated, got {rows_updated}"
        
        updated_user = get_user_setting(user_id1)
        assert updated_user['user_name'] == "test_user1_updated", f"Expected username 'test_user1_updated', got '{updated_user['user_name']}'"
        assert updated_user['user_role'] == "user", f"Expected role 'user', got '{updated_user['user_role']}'"
        assert updated_user['owm_zip_code'] == "TEST98765", f"Expected owm_zip_code 'TEST98765', got '{updated_user['owm_zip_code']}'"
        assert updated_user['time_format'] == "24h", f"Expected time_format '24h', got '{updated_user['time_format']}'"
        assert updated_user['temp_pref'] == "C", f"Expected temp_pref 'C', got '{updated_user['temp_pref']}'"
        assert updated_user['owm_api_key'] == "test_api_key_1", f"Expected owm_api_key unchanged, got '{updated_user['owm_api_key']}'"
        
        # Verify password was updated by checking the hash
        old_password_hash = hash_password("password1")
        new_password_hash = hash_password("new_password")
        assert updated_user['user_password'] != old_password_hash, "Password hash should have changed"
        assert updated_user['user_password'] == new_password_hash, "Password hash should match the new password"
        
        # Test authentication functions
        print("Testing authentication functions...")
        
        # Test get_user_by_username
        user_by_username = get_user_by_username("test_user2")
        assert user_by_username is not None, "Failed to retrieve user by user_name"
        assert user_by_username['user_id'] == user_id2, f"Expected user_id {user_id2}, got {user_by_username['user_id']}"
        
        # Test authenticate_user with correct password
        authenticated_user = authenticate_user("test_user2", "password2")
        assert authenticated_user is not None, "Failed to authenticate user with correct password"
        assert authenticated_user['user_id'] == user_id2, f"Expected user_id {user_id2}, got {authenticated_user['user_id']}"
        
        # Test authenticate_user with incorrect password
        bad_auth_user = authenticate_user("test_user2", "wrong_password")
        assert bad_auth_user is None, "Should not authenticate user with incorrect password"
        
        # Test count_users
        user_count = count_users()
        assert user_count >= 2, f"Expected at least 2 users, got {user_count}"
        
        # Test hash_password and verify_password
        password = "test_password"
        hashed = hash_password(password)
        assert verify_password(password, hashed), "Password verification should succeed with correct password"
        assert not verify_password("wrong_password", hashed), "Password verification should fail with incorrect password"

        # Test delete_user_setting
        print("Testing delete_user_setting...")
        rows_deleted = delete_user_setting(user_id3)
        assert rows_deleted == 1, f"Expected 1 row deleted, got {rows_deleted}"
        
        deleted_user = get_user_setting(user_id3)
        assert deleted_user is None, f"Expected None for deleted user, got {deleted_user}"
        
        # Test delete_farm_user_settings
        print("Testing delete_farm_user_settings...")
        rows_deleted_farm = delete_farm_user_settings(farm_id)
        assert rows_deleted_farm == 2, f"Expected 2 rows deleted for farm, got {rows_deleted_farm}"
        
        farm_users = get_farm_user_settings(farm_id)
        assert len(farm_users) == 0, f"Expected 0 user settings for farm, got {len(farm_users)}"
        
        print("All user_settings table tests passed!")
        return True
        
    except Exception as e:
        print(f"Error in user_settings table tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up test data
        clean_test_data()

if __name__ == "__main__":
    test_user_settings_crud()
