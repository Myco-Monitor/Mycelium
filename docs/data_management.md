# Mycelium Data Management Documentation

## Overview

This document provides detailed information about data management practices for the Mycelium Mushroom Farm Management System. It covers data validation, retention policies, time-series data handling, and export capabilities.

## Data Validation

### Input Validation

All data entering the system undergoes validation to ensure integrity and consistency:

#### Core Entity Validation

1. **Farm Data**
   - Farm names must be unique and non-empty
   - Location data is validated for format consistency
   - Active status must be 0 or 1

2. **Grow Room Data**
   - Room names must be unique within a farm
   - Farm ID must reference an existing active farm
   - Room descriptions have a maximum length

3. **Device Data**
   - Device names must be unique within a room
   - IP addresses are validated for correct format
   - MAC addresses are validated for correct format and uniqueness
   - Room ID must reference an existing active room

#### Time-Series Data Validation

1. **Sensor Readings**
   - Timestamps must be in ISO format (YYYY-MM-DD HH:MM:SS)
   - Sensor values must be within physically possible ranges:
     - Temperature: -50°C to 100°C
     - Humidity: 0% to 100%
     - CO2: 0 to 10000 ppm
     - Pressure: 800 to 1200 mbar
   - Device ID must reference an existing device

2. **Relay State Changes**
   - Relay numbers must be between 1 and 6
   - Relay states must be 0 or 1
   - Cooldown values must be non-negative integers

#### Business Data Validation

1. **Cost of Goods**
   - Item costs must be non-negative
   - Item counts must be positive
   - Weights must be non-negative

2. **Production Data**
   - Weights must be positive
   - Timestamps must be in chronological order
   - References must point to existing records

3. **Sales Data**
   - Prices must be non-negative
   - Weights must be positive
   - Line totals must match price × weight

### Validation Implementation

Validation is implemented at multiple levels:

1. **Database Constraints**
   - CHECK constraints enforce basic value ranges
   - FOREIGN KEY constraints enforce referential integrity
   - UNIQUE constraints prevent duplicates

2. **Application-Level Validation**
   - Each table module in `storage/tables/` implements validation functions
   - Validation occurs before any database operation
   - Custom validation errors provide detailed information

3. **API-Level Validation**
   - API endpoints validate input data before processing
   - Structured error responses indicate validation failures

Example validation function:

```python
def validate_spore_reading(device_id, reading_ts, co2, humidity, temp):
    """
    Validate a Spore device reading.
    
    Args:
        device_id (int): Device ID
        reading_ts (str): Reading timestamp
        co2 (float): CO2 reading in ppm
        humidity (float): Humidity reading in %
        temp (float): Temperature reading in °C
        
    Returns:
        tuple: (is_valid, error_message)
    """
    # Check device exists
    device = get_device_by_id(device_id)
    if not device:
        return False, f"Device with ID {device_id} does not exist"
    
    # Check device is active
    if not device['active']:
        return False, f"Device with ID {device_id} is inactive"
    
    # Validate timestamp format
    try:
        datetime.fromisoformat(reading_ts.replace('Z', '+00:00'))
    except ValueError:
        return False, f"Invalid timestamp format: {reading_ts}"
    
    # Validate CO2 range
    if co2 is not None and (co2 < 0 or co2 > 10000):
        return False, f"CO2 value {co2} outside valid range (0-10000 ppm)"
    
    # Validate humidity range
    if humidity is not None and (humidity < 0 or humidity > 100):
        return False, f"Humidity value {humidity} outside valid range (0-100%)"
    
    # Validate temperature range
    if temp is not None and (temp < -50 or temp > 100):
        return False, f"Temperature value {temp} outside valid range (-50°C to 100°C)"
    
    return True, ""
```

## Data Retention Policies

### Time-Series Data Retention

The system implements tiered data retention for time-series data:

1. **Raw Data Retention**
   - Recent data (0-30 days): Full resolution
   - Medium-term data (31-90 days): 5-minute resolution
   - Long-term data (91-365 days): Hourly resolution
   - Historical data (>365 days): Daily aggregates

2. **Aggregation Methods**
   - Temperature: min, max, average
   - Humidity: min, max, average
   - CO2: min, max, average
   - Relay states: on-time percentage, cycle count

3. **Implementation**
   - Scheduled jobs perform data aggregation
   - Original data is archived before aggregation
   - Aggregation preserves critical min/max values

### Business Data Retention

Business data has different retention requirements:

1. **Transactional Data**
   - All production and sales records are retained indefinitely
   - Soft deletion is used to hide obsolete records
   - Full audit trail is maintained

2. **Reference Data**
   - Customer and supplier information is retained indefinitely
   - Inactive entities are marked with active=0
   - Historical pricing information is preserved

### Data Pruning

The system includes utilities for data pruning:

```python
def prune_time_series_data(older_than_days=365, resolution='daily'):
    """
    Prune time-series data older than the specified threshold.
    
    Args:
        older_than_days (int): Age threshold in days
        resolution (str): Target resolution ('raw', '5min', 'hourly', 'daily')
        
    Returns:
        int: Number of records pruned
    """
```

This function:
- Identifies data eligible for pruning
- Creates aggregated records if they don't exist
- Removes the original high-resolution data
- Returns the count of pruned records

## Time-Series Data Management

### Storage Optimization

Time-series data is optimized for efficient storage and retrieval:

1. **Table Structure**
   - Composite primary keys (device_id, reading_ts)
   - Minimal column set for frequent readings
   - Optimized data types for storage efficiency

2. **Indexing Strategy**
   - Composite indexes for device+time queries
   - Time-based indexes for range queries
   - Covering indexes for common query patterns

3. **Query Optimization**
   - Prepared statements for all queries
   - Date range limiting for all time-series queries
   - Result limiting to prevent excessive memory usage

### Data Aggregation

The system provides functions for data aggregation:

```python
def aggregate_readings(device_id, start_ts, end_ts, resolution='hourly'):
    """
    Aggregate readings for a device over a time period.
    
    Args:
        device_id (int): Device ID
        start_ts (str): Start timestamp
        end_ts (str): End timestamp
        resolution (str): Aggregation resolution ('5min', 'hourly', 'daily')
        
    Returns:
        list: Aggregated readings
    """
```

This function:
- Groups readings by the specified time resolution
- Calculates aggregate statistics (min, max, avg)
- Returns the aggregated data series

### Time-Based Partitioning

For high-volume deployments, time-based partitioning is implemented:

1. **Partitioning Strategy**
   - Monthly partitions for recent data
   - Quarterly partitions for older data
   - Yearly partitions for historical data

2. **Implementation**
   - Views provide a unified interface across partitions
   - Queries are automatically directed to appropriate partitions
   - New partitions are created automatically

## Data Export Capabilities

### Export Formats

The system supports exporting data in multiple formats:

1. **CSV Export**
   - Simple tabular format for spreadsheet compatibility
   - Configurable field delimiters and quoting
   - UTF-8 encoding with BOM for Excel compatibility

2. **JSON Export**
   - Hierarchical data representation
   - Includes metadata and schema information
   - Supports both compact and pretty-printed formats

3. **Excel Export**
   - Direct Excel file generation
   - Multiple worksheets for related data
   - Formatting and formulas for analysis

### Export Functions

The system provides functions for data export:

```python
def export_data(table_name, query_params=None, format='csv', file_path=None):
    """
    Export data from a table.
    
    Args:
        table_name (str): Name of the table to export
        query_params (dict): Query parameters to filter data
        format (str): Export format ('csv', 'json', 'excel')
        file_path (str): Path to save the exported file
        
    Returns:
        str: Path to the exported file
    """
```

This function:
- Retrieves data based on query parameters
- Formats the data in the requested format
- Saves the data to the specified file path
- Returns the path to the exported file

### Scheduled Exports

The system supports scheduled exports:

1. **Export Configuration**
   - Export content (tables, query parameters)
   - Export format and destination
   - Schedule (daily, weekly, monthly)

2. **Delivery Methods**
   - Local file system
   - Email attachment
   - FTP/SFTP upload

## Data Import Capabilities

### Import Formats

The system supports importing data from multiple sources:

1. **CSV Import**
   - Configurable field mapping
   - Validation before import
   - Error reporting for invalid records

2. **JSON Import**
   - Schema validation
   - Support for nested structures
   - Batch processing for large imports

3. **Direct Device Import**
   - API integration with devices
   - Real-time data ingestion
   - Validation and error handling

### Import Functions

The system provides functions for data import:

```python
def import_data(source_path, table_name, mapping=None, validate=True):
    """
    Import data into a table.
    
    Args:
        source_path (str): Path to the source file
        table_name (str): Name of the target table
        mapping (dict): Field mapping configuration
        validate (bool): Whether to validate data before import
        
    Returns:
        dict: Import results with counts and errors
    """
```

This function:
- Reads data from the source file
- Maps fields according to the provided mapping
- Validates data if requested
- Imports valid records and tracks errors
- Returns detailed import results

## Data Integrity Maintenance

### Consistency Checks

The system includes utilities for checking data consistency:

```python
def check_data_consistency():
    """
    Check data consistency across related tables.
    
    Returns:
        dict: Consistency check results
    """
```

This function checks for:
- Orphaned records
- Inconsistent timestamps across related records
- Mismatched totals in parent/child relationships
- Logical inconsistencies in business data

### Data Repair

The system includes utilities for repairing data issues:

```python
def repair_data_issues(issues):
    """
    Repair identified data issues.
    
    Args:
        issues (dict): Issues identified by consistency check
        
    Returns:
        dict: Repair results
    """
```

This function:
- Applies appropriate fixes for each issue type
- Logs all changes made
- Verifies that issues are resolved
- Returns detailed repair results

## Best Practices

1. **Data Validation**
   - Always validate data at the application level
   - Use database constraints as a secondary defense
   - Provide clear error messages for validation failures

2. **Time-Series Data**
   - Query with time range limits
   - Use appropriate aggregation for historical analysis
   - Consider data volume in query design

3. **Data Retention**
   - Configure retention policies based on business needs
   - Schedule regular aggregation jobs
   - Archive data before deletion

4. **Data Export/Import**
   - Validate data before import
   - Include metadata in exports
   - Use transactions for imports

5. **Performance Optimization**
   - Index columns used in WHERE clauses
   - Use prepared statements
   - Limit result sets for large queries
