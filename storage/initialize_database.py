#!/usr/bin/env python3
"""
Database Initialization Script for Mycelium Mushroom Farm Management System

This script initializes the unified SQLite database for the Mycelium system.
It can optionally delete an existing database before creating a new one.
"""

import os
import re
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
    pragma = f"PRAGMA table_info({table})"
    rows = conn.execute(pragma).fetchall()
    return any(r[1] == column for r in rows)


# Columns added to the schema after the initial release. New databases already
# have them (from create_unified_database.sql); this list brings older installs
# up to date on startup, since the project has no migration framework.
_COLUMN_ADDITIONS = [
    ("device_hyphae", "error_group", "INTEGER NOT NULL DEFAULT 0"),
    ("device_hyphae", "error_code", "INTEGER NOT NULL DEFAULT 0"),
    ("device_hyphae", "wifi_rssi", "INTEGER"),
    ("device_hyphae", "uptime_sec", "INTEGER"),
    ("device_spore", "wifi_rssi", "INTEGER"),
    ("device_spore", "heap_free_kb", "INTEGER"),
    ("device_spore", "heap_min_free_kb", "INTEGER"),
    ("device_spore", "uptime_sec", "INTEGER"),
    ("readings_weather", "wind_speed", "REAL"),
    ("readings_weather", "wind_deg", "REAL"),
    ("readings_weather", "sunrise", "TEXT"),
    ("readings_weather", "sunset", "TEXT"),
]


# Tables whose device_type CHECK must admit 'sentinel' (added in v2.8.0).
# Databases created earlier have CHECK(device_type IN ('spore', 'hyphae')) and
# SQLite cannot ALTER a CHECK, so each is rebuilt once from the DDL in
# create_unified_database.sql. Detection inspects sqlite_master, so the rebuild
# is idempotent and a no-op on a fresh database.
_CHECK_REBUILD_TABLES = (
    "firmware_versions",
    "ota_history",
    "device_health_log",
    "device_pins",
)


def _table_sql(conn, table):
    """The CREATE TABLE statement SQLite stored for `table`, or None if absent."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    return row[0] if row else None


def _schema_create_body(script, table):
    """Column/constraint body of `table`'s CREATE TABLE in the schema script.

    The script writes each table's closing `);` alone on its own line, so the
    non-greedy match cannot stop early inside a CHECK(...) clause.
    """
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS {re.escape(table)} \((.*?)\n\);",
        script,
        re.S,
    )
    if not match:
        raise ValueError(f"{table} not found in schema script")
    return match.group(1)


def _rebuild_check_table(conn, script, table):
    """Recreate `table` from the schema script, preserving every row and id.

    Follows the sqlite.org ALTER TABLE procedure: create the new table under a
    temporary name, copy by explicit column list (so AUTOINCREMENT ids and the
    sqlite_sequence counter carry over), drop the old table, rename. Indexes
    are dropped with the old table; the caller's schema pass recreates them.
    Foreign-key enforcement is off in this project (see db_utils) and nothing
    references these tables by FK, so the drop is safe. Table names are the
    trusted constants in _CHECK_REBUILD_TABLES, never user input.
    """
    body = _schema_create_body(script, table)
    new_table = f"{table}__new"

    create_ddl = f"CREATE TABLE {new_table} ({body})"
    conn.execute(create_ddl)

    pragma = f"PRAGMA table_info({table})"
    cols = ", ".join(r[1] for r in conn.execute(pragma).fetchall())
    copy_ddl = f"INSERT INTO {new_table} ({cols}) SELECT {cols} FROM {table}"
    conn.execute(copy_ddl)

    drop_ddl = f"DROP TABLE {table}"
    conn.execute(drop_ddl)
    rename_ddl = f"ALTER TABLE {new_table} RENAME TO {table}"
    conn.execute(rename_ddl)


def apply_migrations(db_path):
    """
    Idempotently bring an existing database up to the current schema.

    Three steps, each a no-op when already applied, so it is safe to run on
    every startup and on a freshly created database:
      1. Rebuild the device_type CHECK tables that predate 'sentinel'.
      2. Re-run the schema script (entirely IF NOT EXISTS) so tables and
         indexes added since the database was created exist.
      3. Add columns that were appended to existing tables.

    Note: user_settings.reset_pin (the retired "Mycelium PIN") is deprecated —
    sensitive actions are confirmed with the account password instead. The
    column is kept for schema stability but is no longer read or written.

    Returns:
        bool: True on success, False if the database could not be opened/altered.
    """
    try:
        conn = sqlite3.connect(db_path)
    except sqlite3.Error as e:
        print(f"Error opening database for migration: {e}")
        return False
    # Autocommit mode: the CHECK rebuild manages its own explicit transaction,
    # and executescript() would otherwise commit whatever was pending anyway.
    conn.isolation_level = None
    try:
        script = read_sql_script(SQL_SCRIPT_PATH)

        pending = []
        for table in _CHECK_REBUILD_TABLES:
            sql = _table_sql(conn, table)
            if sql and "'sentinel'" not in sql:
                pending.append(table)
        if pending:
            conn.execute("BEGIN IMMEDIATE")
            try:
                for table in pending:
                    print(f"Rebuilding device_type CHECK on {table}")
                    _rebuild_check_table(conn, script, table)
                conn.execute("COMMIT")
            except (sqlite3.Error, ValueError):
                conn.execute("ROLLBACK")
                raise

        conn.executescript(script)

        for table, column, decl in _COLUMN_ADDITIONS:
            if not _column_exists(conn, table, column):
                print(f"Adding missing column {table}.{column}")
                ddl = f"ALTER TABLE {table} ADD COLUMN {column} {decl}"
                conn.execute(ddl)
        return True
    except (sqlite3.Error, ValueError) as e:
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
