#!/usr/bin/env python3
"""
Database Initialization Script for Mycelium Mushroom Farm Management System

This script initializes the unified SQLite database for the Mycelium system.
It can optionally delete an existing database before creating a new one.
"""

import os
import sqlite3
import argparse

# Default database path
DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "mycelium.db"
)
SQL_SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "create_unified_database.sql"
)


def read_sql_script(script_path):
    """Read SQL script from file."""
    with open(script_path, "r") as f:
        return f.read()


def initialize_database(db_path, force=False):
    """
    Initialize the database with all tables.

    Args:
        db_path (str): Path to the database file
        force (bool): If True, delete existing database before creating a new one

    Returns:
        bool: True if successful, False otherwise
    """
    # Ensure the directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Check if database exists
    db_exists = os.path.exists(db_path)

    if db_exists:
        if force:
            print(f"Removing existing database at {db_path}")
            try:
                os.remove(db_path)
                print("Existing database removed successfully")
            except Exception as e:
                print(f"Error removing database: {e}")
                return False
        else:
            print(f"Database already exists at {db_path}")
            print("Use --force to delete and recreate it")
            return False

    # Create new database
    print(f"Creating new database at {db_path}")
    try:
        # Read SQL script
        sql_script = read_sql_script(SQL_SCRIPT_PATH)

        # Connect to database and execute script
        conn = sqlite3.connect(db_path)
        conn.executescript(sql_script)
        conn.commit()
        conn.close()

        print("Database initialized successfully")
        return True
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False


def _column_exists(conn, table, column):
    """True if `column` is present on `table`.

    The table name is interpolated because SQLite cannot bind identifiers in
    PRAGMA/DDL; it is never user input — only the trusted constants in
    _COLUMN_ADDITIONS reach here.
    """
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


# Columns added to the schema after the initial release. New databases already
# have them (from create_unified_database.sql); this list brings older installs
# up to date on startup, since the project has no migration framework.
_COLUMN_ADDITIONS = [
    ("device_hyphae", "error_group", "INTEGER NOT NULL DEFAULT 0"),
    ("device_hyphae", "error_code", "INTEGER NOT NULL DEFAULT 0"),
]


def apply_migrations(db_path):
    """
    Idempotently bring an existing database up to the current schema.

    Only adds columns that are missing, so it is safe to run on every startup
    and on a freshly created database (where it is a no-op).

    Returns:
        bool: True on success, False if the database could not be opened/altered.
    """
    try:
        conn = sqlite3.connect(db_path)
    except sqlite3.Error as e:
        print(f"Error opening database for migration: {e}")
        return False
    try:
        for table, column, decl in _COLUMN_ADDITIONS:
            if not _column_exists(conn, table, column):
                print(f"Adding missing column {table}.{column}")
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error applying migrations: {e}")
        return False
    finally:
        conn.close()


def main():
    """Main function to parse arguments and initialize database."""
    parser = argparse.ArgumentParser(description="Initialize Mycelium database")
    parser.add_argument(
        "--db-path",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to database file (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--force", action="store_true", help="Force deletion of existing database"
    )

    args = parser.parse_args()

    # Initialize database
    success = initialize_database(args.db_path, args.force)

    # Print database info if successful
    if success:
        db_size = os.path.getsize(args.db_path) / 1024  # Size in KB
        print(f"Database size: {db_size:.2f} KB")

        # Connect and get table count
        conn = sqlite3.connect(args.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table';")
        table_count = cursor.fetchone()[0]
        print(f"Number of tables created: {table_count}")

        # List all tables
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        tables = cursor.fetchall()
        print("\nTables created:")
        for table in tables:
            print(f"  - {table[0]}")

        conn.close()


if __name__ == "__main__":
    main()
