#!/usr/bin/env python3
"""
Database Initialization Script for Mycelium Mushroom Farm Management System

This script initializes the unified SQLite database for the Mycelium system.
It can optionally delete an existing database before creating a new one.
"""

import os
import sqlite3
import argparse
from pathlib import Path

# Default database path
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'mycelium.db')
SQL_SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'create_unified_database.sql')

def read_sql_script(script_path):
    """Read SQL script from file."""
    with open(script_path, 'r') as f:
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

def main():
    """Main function to parse arguments and initialize database."""
    parser = argparse.ArgumentParser(description='Initialize Mycelium database')
    parser.add_argument('--db-path', type=str, default=DEFAULT_DB_PATH,
                        help=f'Path to database file (default: {DEFAULT_DB_PATH})')
    parser.add_argument('--force', action='store_true',
                        help='Force deletion of existing database')
    
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
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = cursor.fetchall()
        print("\nTables created:")
        for table in tables:
            print(f"  - {table[0]}")
        
        conn.close()

if __name__ == "__main__":
    main()
