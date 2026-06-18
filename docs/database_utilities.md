# Mycelium Database Utilities Documentation

## Overview

This document provides detailed information about the database utilities implemented for the Mycelium Mushroom Farm Management System. These utilities handle database initialization, migrations, backup/restore operations, and maintenance tasks.

## Database Initialization

### Initialize Database Script

The primary database initialization utility is `initialize_database.py`, located in the `storage` directory. This script creates a new SQLite database with all tables defined in the schema.

**Usage:**
```bash
python storage/initialize_database.py [--db-path PATH] [--force]
```

**Parameters:**
- `--db-path`: Optional path to the database file (default: `data/mycelium.db`)
- `--force`: If specified, deletes any existing database before creating a new one

**Functionality:**
1. Checks if the database already exists
2. If `--force` is specified, removes any existing database
3. Creates the database directory if it doesn't exist
4. Reads the SQL schema from `storage/create_unified_database.sql`
5. Executes the SQL script to create all tables, indexes, and constraints
6. Reports success status and basic database information

**Example:**
```bash
# Create a new database (fails if one already exists)
python storage/initialize_database.py

# Force creation of a new database, overwriting any existing one
python storage/initialize_database.py --force

# Create a database at a custom location
python storage/initialize_database.py --db-path /path/to/custom/database.db
```

### SQL Schema Script

The `create_unified_database.sql` script contains all SQL statements to create the database schema. This script:

1. Creates all tables with appropriate columns and constraints
2. Defines primary and foreign keys
3. Creates indexes for optimized queries
4. Sets default values and check constraints

## Database Connection Utilities

The `db_utils.py` module provides utilities for connecting to and interacting with the database.

### Key Functions

#### get_connection

```python
def get_connection(db_path=None):
    """
    Get a connection to the SQLite database.
    
    Args:
        db_path (str, optional): Path to the database file. Defaults to None,
                                which uses the default database path.
    
    Returns:
        sqlite3.Connection: A connection to the database
    """
```

This function:
- Creates a connection to the SQLite database
- Sets pragmas for foreign key enforcement
- Returns a connection object for database operations

#### execute_query

```python
def execute_query(query, params=None, db_path=None):
    """
    Execute a query and return the results.
    
    Args:
        query (str): SQL query to execute
        params (tuple, optional): Parameters for the query. Defaults to None.
        db_path (str, optional): Path to the database file. Defaults to None.
    
    Returns:
        list: Query results as a list of tuples
    """
```

This function:
- Establishes a database connection
- Executes the provided SQL query with parameters
- Returns the query results
- Handles connection cleanup

#### execute_transaction

```python
def execute_transaction(queries, db_path=None):
    """
    Execute multiple queries as a single transaction.
    
    Args:
        queries (list): List of (query, params) tuples
        db_path (str, optional): Path to the database file. Defaults to None.
    
    Returns:
        bool: True if successful, False otherwise
    """
```

This function:
- Establishes a database connection
- Begins a transaction
- Executes all queries in sequence
- Commits if all succeed, rolls back if any fail
- Returns success status

## Database Migration System

The migration system allows for schema evolution over time while preserving data.

### Migration Structure

Migrations are stored in the `storage/migrations` directory with sequential version numbers:

```
storage/migrations/
  ├── 001_initial_schema.sql
  ├── 002_add_user_settings.sql
  ├── 003_extend_device_tables.sql
  └── ...
```

### Migration Tracking

The `schema_versions` table tracks applied migrations:

```sql
CREATE TABLE IF NOT EXISTS schema_versions (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);
```

### Migration Process

The migration utility:

1. Determines the current schema version from the database
2. Identifies unapplied migrations
3. Applies each migration in sequence within a transaction
4. Updates the schema version after each successful migration
5. Reports on migration status

## Backup and Restore Utilities

### Database Backup

The backup utility creates timestamped backups of the database:

```python
def backup_database(db_path=None, backup_dir=None):
    """
    Create a backup of the database.
    
    Args:
        db_path (str, optional): Path to the database file. Defaults to None.
        backup_dir (str, optional): Directory to store backups. Defaults to None.
    
    Returns:
        str: Path to the backup file if successful, None otherwise
    """
```

**Features:**
- Creates timestamped backup files (e.g., `mycelium_backup_20250718_102345.db`)
- Verifies backup integrity
- Maintains a configurable number of backup files
- Supports both manual and scheduled backups

### Database Restore

The restore utility restores the database from a backup:

```python
def restore_database(backup_path, target_path=None):
    """
    Restore the database from a backup.
    
    Args:
        backup_path (str): Path to the backup file
        target_path (str, optional): Path to restore to. Defaults to None.
    
    Returns:
        bool: True if successful, False otherwise
    """
```

**Features:**
- Verifies backup file integrity before restoring
- Creates a backup of the current database before restoring
- Supports restoring to a different location
- Reports detailed status of the restore operation

## Database Maintenance Utilities

### Integrity Check

The integrity check utility verifies database integrity:

```python
def check_database_integrity(db_path=None):
    """
    Check the integrity of the SQLite database.
    
    Args:
        db_path (str, optional): Path to the database file. Defaults to None.
    
    Returns:
        bool: True if integrity check passes, False otherwise
    """
```

This function:
- Runs the SQLite `PRAGMA integrity_check` command
- Verifies foreign key constraints with `PRAGMA foreign_key_check`
- Reports any integrity issues found

### Database Optimization

The optimization utility improves database performance:

```python
def optimize_database(db_path=None):
    """
    Optimize the SQLite database.
    
    Args:
        db_path (str, optional): Path to the database file. Defaults to None.
    
    Returns:
        bool: True if optimization succeeds, False otherwise
    """
```

This function:
- Runs the SQLite `VACUUM` command to reclaim unused space
- Rebuilds indexes for better performance
- Updates database statistics
- Reports on space saved and performance improvements

### Database Monitoring

The monitoring utility tracks database metrics:

```python
def get_database_stats(db_path=None):
    """
    Get statistics about the database.
    
    Args:
        db_path (str, optional): Path to the database file. Defaults to None.
    
    Returns:
        dict: Dictionary of database statistics
    """
```

This function returns statistics including:
- Database file size
- Number of tables and indexes
- Row counts for each table
- Index usage statistics
- Last modification times

## Data Validation Utilities

### Schema Validation

The schema validation utility verifies that the database schema matches the expected structure:

```python
def validate_schema(db_path=None):
    """
    Validate that the database schema matches the expected structure.
    
    Args:
        db_path (str, optional): Path to the database file. Defaults to None.
    
    Returns:
        dict: Validation results with any discrepancies
    """
```

This function:
- Compares the actual database schema with the expected schema
- Reports any missing tables, columns, indexes, or constraints
- Identifies any unexpected schema elements

### Data Validation

The data validation utility checks data integrity beyond schema constraints:

```python
def validate_data(db_path=None):
    """
    Validate data integrity beyond schema constraints.
    
    Args:
        db_path (str, optional): Path to the database file. Defaults to None.
    
    Returns:
        dict: Validation results with any issues found
    """
```

This function checks for:
- Orphaned records (valid foreign keys to inactive records)
- Logical inconsistencies (e.g., end dates before start dates)
- Data range violations (values outside expected ranges)
- Duplicate records where uniqueness is expected

## Test Data Generation

The test data generation utility creates sample data for testing:

```python
def generate_test_data(db_path=None, scale='small'):
    """
    Generate test data for the database.
    
    Args:
        db_path (str, optional): Path to the database file. Defaults to None.
        scale (str, optional): Scale of test data ('small', 'medium', 'large'). 
                              Defaults to 'small'.
    
    Returns:
        bool: True if successful, False otherwise
    """
```

This function:
- Creates realistic test data for all tables
- Maintains proper relationships between entities
- Scales data volume based on the specified scale
- Includes both current and historical data

## Usage Examples

### Basic Database Setup

```python
# Import database utilities
from storage.db_utils import get_connection, execute_query

# Initialize a new database
import subprocess
subprocess.run(["python", "storage/initialize_database.py", "--force"])

# Connect to the database
conn = get_connection()

# Execute a simple query
farms = execute_query("SELECT * FROM farms")
print(f"Found {len(farms)} farms")
```

### Backup and Restore

```python
# Import backup utilities
from storage.backup_utils import backup_database, restore_database

# Create a backup
backup_path = backup_database()
print(f"Database backed up to {backup_path}")

# Restore from backup
success = restore_database(backup_path)
if success:
    print("Database restored successfully")
else:
    print("Database restore failed")
```

### Database Maintenance

```python
# Import maintenance utilities
from storage.maintenance_utils import check_database_integrity, optimize_database

# Check database integrity
integrity_ok = check_database_integrity()
if integrity_ok:
    print("Database integrity check passed")
else:
    print("Database integrity check failed")

# Optimize the database
optimize_database()
print("Database optimized")
```

## Best Practices

1. **Always use parameterized queries** to prevent SQL injection
2. **Use transactions** for operations that modify multiple tables
3. **Validate data** before inserting or updating
4. **Create regular backups**, especially before schema migrations
5. **Run integrity checks** periodically to catch issues early
6. **Monitor database size** and performance metrics
7. **Use the provided utilities** rather than direct SQL when possible
