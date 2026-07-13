"""
Database utility functions for Mycelium.

This module provides helper functions for connecting to the database
and performing common operations.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

# Database path - use absolute path resolution to ensure correct location
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DB_PATH = str(PROJECT_ROOT / "data" / "mycelium.db")


def get_connection() -> sqlite3.Connection:
    """
    Get a connection to the SQLite database.

    Returns:
        sqlite3.Connection: A connection to the database.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dict-like objects
    conn.execute("PRAGMA journal_mode=WAL")  # Enable WAL for concurrent access
    return conn


def execute_query(query: str, params: Tuple = ()) -> List[Dict]:
    """
    Execute a SELECT query and return the results.

    Args:
        query (str): The SQL query to execute.
        params (tuple): Parameters for the query.

    Returns:
        List[Dict]: A list of dictionaries representing the query results.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]
        return results
    finally:
        conn.close()


def execute_update(query: str, params: Tuple = ()) -> int:
    """
    Execute an UPDATE, INSERT, or DELETE query.

    Args:
        query (str): The SQL query to execute.
        params (tuple): Parameters for the query.

    Returns:
        int: The number of rows affected.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def execute_insert(query: str, params: Tuple = ()) -> int:
    """
    Execute an INSERT query and return the last inserted row ID.

    Args:
        query (str): The SQL query to execute.
        params (tuple): Parameters for the query.

    Returns:
        int: The ID of the last inserted row.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_timestamp() -> str:
    """
    Get the current UTC timestamp in ISO format.

    All persisted timestamps are naive UTC; the web UI converts to the
    user's configured timezone at display time (web_ui/format.py).

    Returns:
        str: Current UTC timestamp in ISO format (YYYY-MM-DD HH:MM:SS).
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def utc_now_iso() -> str:
    """Current UTC time as a naive datetime.isoformat() string.

    Use for reading_ts-style columns (they carry sub-second precision and a
    'T' separator, unlike get_timestamp()).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
