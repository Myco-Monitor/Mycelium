# Mycelium Database Schema Documentation

## Overview

This document provides detailed information about the database schema design for the Mycelium Mushroom Farm Management System. The database is implemented in SQLite and follows a structured approach to manage both monitoring data and business operations.

## Schema Design Philosophy

The Mycelium database schema is designed with the following principles:

1. **Separation of Concerns**: Clear separation between device monitoring, configuration, and business operations
2. **Efficient Time-Series Storage**: Optimized structure for high-frequency sensor data
3. **Referential Integrity**: Proper relationships between tables with foreign key constraints
4. **Extensibility**: Flexible design to accommodate future requirements
5. **Performance**: Strategic indexing for common query patterns

## Entity-Relationship Overview

The database consists of the following major entity groups:

1. **Core System Entities**: Farms, grow rooms, and devices
2. **Time-Series Data**: Sensor readings from devices
3. **Configuration Settings**: Device and system configuration
4. **Business Operations**: Production tracking and sales management

### Core Relationships

- A farm contains multiple grow rooms
- Each grow room contains multiple devices (Spore and Hyphae)
- Spore devices can be linked to Hyphae devices
- All sensor readings are associated with specific devices
- Business operations (spawn, bulk, harvest) follow a linear production flow
- Sales transactions can reference multiple harvests

## Table Descriptions

### Core System Tables

#### farms
The top-level entity representing a physical farm location.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| farm_id | INTEGER | Primary key | PK, AUTOINCREMENT |
| farm_name | TEXT | Farm name | NOT NULL |
| farm_loc | TEXT | Physical location | - |
| farm_desc | TEXT | Description | - |
| active | INTEGER | Active status (1=active, 0=deleted) | DEFAULT 1 |
| deactivation_reason | TEXT | Reason if inactive | - |
| created_at | TEXT | Creation timestamp | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TEXT | Last update timestamp | DEFAULT CURRENT_TIMESTAMP |

**Indexes**:
- `idx_farms_name`: For quick lookup by name
- `idx_farms_active`: For filtering active records

#### grow_rooms
Represents growing areas within a farm.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| room_id | INTEGER | Primary key | PK, AUTOINCREMENT |
| farm_id | INTEGER | Reference to farm | FK, NOT NULL |
| room_name | TEXT | Room name | NOT NULL |
| room_desc | TEXT | Description | - |
| active | INTEGER | Active status | DEFAULT 1 |
| deactivation_reason | TEXT | Reason if inactive | - |
| created_at | TEXT | Creation timestamp | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TEXT | Last update timestamp | DEFAULT CURRENT_TIMESTAMP |

**Indexes**:
- `idx_grow_rooms_farm_id`: For joining with farms
- `idx_grow_rooms_active`: For filtering active records

#### device_spore
Represents Spore monitoring devices.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| device_id | INTEGER | Primary key | PK, AUTOINCREMENT |
| device_name | TEXT | Device name | NOT NULL |
| room_id | INTEGER | Reference to grow room | FK, NOT NULL |
| hyphae_id | INTEGER | Linked Hyphae device | FK |
| ip_address | TEXT | IP address | NOT NULL |
| mac_address | TEXT | MAC address | UNIQUE, NOT NULL |
| hyphae_present | INTEGER | Hyphae presence flag | DEFAULT 0 |
| firmware_version | TEXT | Firmware version | - |
| is_online | INTEGER | Online status | DEFAULT 0 |
| last_update | TEXT | Last communication | - |
| active | INTEGER | Active status | DEFAULT 1 |
| deactivation_reason | TEXT | Reason if inactive | - |
| created_at | TEXT | Creation timestamp | DEFAULT CURRENT_TIMESTAMP |

**Indexes**:
- `idx_device_spore_room_id`: For joining with grow_rooms
- `idx_device_spore_hyphae_id`: For joining with device_hyphae

#### device_hyphae
Represents Hyphae control devices.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| device_id | INTEGER | Primary key | PK, AUTOINCREMENT |
| device_name | TEXT | Device name | NOT NULL |
| room_id | INTEGER | Reference to grow room | FK, NOT NULL |
| ip_address | TEXT | IP address | NOT NULL |
| mac_address | TEXT | MAC address | UNIQUE, NOT NULL |
| mode_enabled | INTEGER | Operation mode | NOT NULL, DEFAULT 0 |
| mode_operation | INTEGER | Schedule/Dynamic mode | NOT NULL, DEFAULT 0 |
| firmware_version | TEXT | Firmware version | - |
| is_online | INTEGER | Online status | DEFAULT 0 |
| last_update | TEXT | Last communication | - |
| active | INTEGER | Active status | DEFAULT 1 |
| deactivation_reason | TEXT | Reason if inactive | - |
| created_at | TEXT | Creation timestamp | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TEXT | Last update timestamp | DEFAULT CURRENT_TIMESTAMP |

**Indexes**:
- `idx_device_hyphae_room_id`: For joining with grow_rooms
- `idx_device_hyphae_active`: For filtering active records

### Time-Series Data Tables

#### readings_spore
Stores sensor readings from Spore devices.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| device_id | INTEGER | Reference to device | PK, FK |
| reading_ts | TEXT | Reading timestamp | PK |
| co2 | REAL | CO2 reading (ppm) | - |
| humidity | REAL | Humidity reading (%) | - |
| temp | REAL | Temperature reading | - |
| spore_ts | TEXT | Original device timestamp | - |

**Indexes**:
- `idx_readings_spore_device_id`: For filtering by device
- `idx_readings_spore_timestamp`: For time-based queries
- `idx_readings_spore_device_time`: Composite index for device+time queries

#### readings_hyphae
Stores relay state changes from Hyphae devices.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| device_id | INTEGER | Reference to device | PK, FK |
| reading_ts | TEXT | Reading timestamp | PK |
| relay_number | INTEGER | Relay number (1-6) | PK |
| relay_state | INTEGER | Relay state (1=ON, 0=OFF) | NOT NULL |
| cooldown | INTEGER | Cooldown time remaining | - |
| testing | INTEGER | Testing mode flag | DEFAULT 0 |
| hyphae_ts | TEXT | Original device timestamp | - |

**Indexes**:
- `idx_readings_hyphae_device_id`: For filtering by device
- `idx_readings_hyphae_timestamp`: For time-based queries
- `idx_readings_hyphae_device_time`: Composite index for device+time queries

#### readings_weather
Stores external weather data.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| device_id | INTEGER | Reference to device | PK, FK |
| reading_ts | TEXT | Reading timestamp | PK |
| current_temp | REAL | Current temperature | - |
| feels_like | REAL | "Feels like" temperature | - |
| humidity | REAL | Humidity percentage | - |
| ambient_pressure | REAL | Ambient pressure (mbar) | - |

**Indexes**:
- `idx_readings_weather_timestamp`: For time-based queries
- `idx_readings_weather_device_time`: Composite index for device+time queries

### Configuration Tables

#### relay_settings
Configures Hyphae relay settings.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| device_id | INTEGER | Reference to Hyphae device | PK, FK |
| relay_number | INTEGER | Relay number (1-6) | PK |
| relay_name | TEXT | Relay name | - |
| group_num | INTEGER | Group number (1-6) | NOT NULL |
| created_at | TEXT | Creation timestamp | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TEXT | Last update timestamp | DEFAULT CURRENT_TIMESTAMP |

#### schedule_settings
Configures scheduled operation times.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| device_id | INTEGER | Reference to Hyphae device | PK, FK |
| group_num | INTEGER | Group number (1-6) | PK |
| on_time | TEXT | Schedule ON time (HH:MM) | - |
| off_time | TEXT | Schedule OFF time (HH:MM) | - |
| created_at | TEXT | Creation timestamp | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TEXT | Last update timestamp | DEFAULT CURRENT_TIMESTAMP |

**Indexes**:
- `idx_schedule_settings_device_id`: For filtering by device

#### dynamic_settings
Configures dynamic operation thresholds.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| device_id | INTEGER | Reference to Hyphae device | PK, FK |
| group_num | INTEGER | Group number (1-3) | PK |
| parameter | TEXT | 'temperature', 'humidity', 'co2' | PK |
| low_threshold | REAL | Low threshold value | NOT NULL |
| high_threshold | REAL | High threshold value | NOT NULL |
| behavior | INTEGER | Behavior (0 or 1) | NOT NULL |
| created_at | TEXT | Creation timestamp | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TEXT | Last update timestamp | DEFAULT CURRENT_TIMESTAMP |

**Indexes**:
- `idx_dynamic_settings_device_id`: For filtering by device

#### user_settings
Stores user preferences and settings.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| user_id | INTEGER | Primary key | PK, AUTOINCREMENT |
| owm_api_key | TEXT | OpenWeatherMap API key | - |
| owm_zip_code | TEXT | ZIP code for weather | - |
| timezone_name | TEXT | Timezone name | - |
| time_format | TEXT | Time format (12 or 24) | - |
| temp_pref | TEXT | Temperature preference (C or F) | - |
| reset_pin | TEXT | Reset PIN (hashed) | - |
| farm_id | INTEGER | Reference to farms | FK |
| created_at | TEXT | Creation timestamp | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TEXT | Last update timestamp | DEFAULT CURRENT_TIMESTAMP |

### Business Operations Tables

#### cost_of_goods
Tracks inventory and supplies.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| item_name | TEXT | Name of the good/item | - |
| item_cost | REAL | Purchase cost | CHECK(item_cost >= 0) |
| item_count | INTEGER | Number of units purchased | CHECK(item_count > 0) |
| weight_lbs | REAL | Weight per unit/batch | CHECK(weight_lbs >= 0) |
| item_used | INTEGER | Number of units used | DEFAULT 0, CHECK(item_used >= 0) |
| used_weight | REAL | Total weight used | DEFAULT 0.0, CHECK(used_weight >= 0) |
| unit_id | INTEGER | Primary key | PK, AUTOINCREMENT |
| purchase_ts | TEXT | Purchase timestamp | - |
| created_at | TEXT | Creation timestamp | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TEXT | Last update timestamp | DEFAULT CURRENT_TIMESTAMP |

**Indexes**:
- `idx_cost_of_goods_purchase_date`: For time-based queries

#### spawn
Tracks spawn production.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| spawn_id | INTEGER | Primary key | PK, AUTOINCREMENT |
| unit_id | INTEGER | Reference to spawn type | FK |
| total_wt | REAL | Total dry weight | CHECK(total_wt > 0) |
| bag_id | INTEGER | Bag used for spawn | FK |
| bag_wt | REAL | Wet weight per bag | CHECK(bag_wt > 0) |
| bag_count | INTEGER | Number of bags used | CHECK(bag_count >= 0) |
| prep_notes | TEXT | Preparation notes | - |
| start_ts | TEXT | Start timestamp | - |
| inoculated_ts | TEXT | Inoculation timestamp | - |
| finished_ts | TEXT | Finished timestamp | - |
| created_at | TEXT | Creation timestamp | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TEXT | Last update timestamp | DEFAULT CURRENT_TIMESTAMP |

**Indexes**:
- `idx_spawn_unit_id`: For joining with cost_of_goods
- `idx_spawn_bag_id`: For joining with cost_of_goods
- `idx_spawn_timestamps`: For time-based queries

#### bulk
Tracks bulk substrate production.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| bulk_id | INTEGER | Primary key | PK, AUTOINCREMENT |
| spawn_id | INTEGER | Reference to spawn batch | FK |
| unit_id | INTEGER | Reference to substrate blend | FK |
| total_wt | REAL | Total dry weight | CHECK(total_wt > 0) |
| bag_id | INTEGER | Bag used for bulk | FK |
| bag_wt | REAL | Wet weight per bag | CHECK(bag_wt > 0) |
| bag_count | INTEGER | Number of bags used | CHECK(bag_count >= 0) |
| prep_notes | TEXT | Preparation notes | - |
| start_ts | TEXT | Start timestamp | - |
| colonized_ts | TEXT | Colonization start timestamp | - |
| finished_ts | TEXT | Finished timestamp | - |

**Indexes**:
- `idx_bulk_spawn_id`: For joining with spawn
- `idx_bulk_unit_id`: For joining with cost_of_goods
- `idx_bulk_bag_id`: For joining with cost_of_goods
- `idx_bulk_timestamps`: For time-based queries

#### harvest
Tracks mushroom harvests.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| harvest_id | INTEGER | Primary key | PK, AUTOINCREMENT |
| harvest_ts | TEXT | Harvest timestamp | NOT NULL |
| bulk_id | INTEGER | Reference to bulk batch | FK |
| total_wt | REAL | Total harvested weight | CHECK(total_wt > 0) |
| trimmed_wt | REAL | Net trimmed weight | CHECK(trimmed_wt >= 0) |
| unit_id | INTEGER | Packaging material | FK |
| weight_used | REAL | Weight of mushrooms used | DEFAULT 0.0, CHECK(weight_used >= 0) |

**Indexes**:
- `idx_harvest_bulk_id`: For joining with bulk
- `idx_harvest_unit_id`: For joining with cost_of_goods
- `idx_harvest_ts`: For time-based queries

#### customers
Tracks customer information.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| customer_id | INTEGER | Primary key | PK, AUTOINCREMENT |
| farm_id | INTEGER | Reference to farm | FK |
| customer_name | TEXT | Customer name | NOT NULL |
| customer_info | TEXT | Contact details | - |
| customer_type | TEXT | Customer type | - |
| notes | TEXT | Additional notes | - |
| active | INTEGER | Active status | DEFAULT 1 |
| deactivation_reason | TEXT | Reason if inactive | - |
| created_at | TEXT | Creation timestamp | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TEXT | Last update timestamp | DEFAULT CURRENT_TIMESTAMP |

**Indexes**:
- `idx_customers_farm_id`: For joining with farms
- `idx_customers_name`: For searching by name
- `idx_customers_type`: For filtering by type
- `idx_customers_active`: For filtering active records

#### sales_transaction
Tracks sales transactions.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| sale_id | INTEGER | Primary key | PK, AUTOINCREMENT |
| customer_id | INTEGER | Reference to customer | FK |
| sale_ts | TEXT | Sale timestamp | NOT NULL |
| total_amount | REAL | Total sale amount | DEFAULT 0.0 |
| notes | TEXT | Additional notes | - |
| created_at | TEXT | Creation timestamp | DEFAULT CURRENT_TIMESTAMP |
| active | INTEGER | Active status | DEFAULT 1 |

**Indexes**:
- `idx_sales_transaction_customer_id`: For joining with customers
- `idx_sales_transaction_ts`: For time-based queries

#### sales_detail
Tracks individual line items in sales.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| detail_id | INTEGER | Primary key | PK, AUTOINCREMENT |
| sale_id | INTEGER | Reference to transaction | FK, NOT NULL |
| harvest_id | INTEGER | Reference to harvest | FK, NOT NULL |
| unit_id | INTEGER | Packaging material | FK |
| weight_used | REAL | Weight sold | NOT NULL, CHECK(weight_used > 0) |
| price | REAL | Price per pound | NOT NULL, CHECK(price >= 0) |
| line_total | REAL | Total for line item | NOT NULL, CHECK(line_total >= 0) |
| notes | TEXT | Notes for line item | - |
| created_at | TEXT | Creation timestamp | DEFAULT CURRENT_TIMESTAMP |

**Indexes**:
- `idx_sales_detail_sale_id`: For joining with sales_transaction
- `idx_sales_detail_harvest_id`: For joining with harvest

#### employees
Tracks employee information.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| emp_id | INTEGER | Primary key | PK, AUTOINCREMENT |
| farm_id | INTEGER | Reference to farm | FK |
| emp_name | TEXT | Employee name | NOT NULL |
| emp_role | TEXT | Employee role | - |
| emp_rate | REAL | Hourly pay rate | - |
| emp_contact | TEXT | Contact information | - |
| emp_start | TEXT | Employment start date | - |
| active | INTEGER | Active status | DEFAULT 1 |
| deactivation_reason | TEXT | Reason if inactive | - |
| created_at | TEXT | Creation timestamp | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TEXT | Last update timestamp | DEFAULT CURRENT_TIMESTAMP |

**Indexes**:
- `idx_employees_farm_id`: For joining with farms
- `idx_employees_active`: For filtering active records

#### labour
Tracks employee work hours.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| labour_id | INTEGER | Primary key | PK, AUTOINCREMENT |
| emp_id | INTEGER | Reference to employee | FK, NOT NULL |
| task_type | TEXT | Type of work | NOT NULL |
| work_date | TEXT | Date of work | NOT NULL |
| hours_worked | REAL | Hours worked | NOT NULL, CHECK(hours_worked > 0) |
| notes | TEXT | Additional notes | - |
| created_at | TEXT | Creation timestamp | DEFAULT CURRENT_TIMESTAMP |

**Indexes**:
- `idx_labour_emp_id`: For joining with employees
- `idx_labour_date_performed`: For time-based queries

#### loss_of_goods
Tracks inventory losses.

| Column | Type | Description | Constraints |
|--------|------|-------------|------------|
| loss_id | INTEGER | Primary key | PK, AUTOINCREMENT |
| farm_id | INTEGER | Reference to farm | FK |
| item_type | TEXT | Type of item lost | NOT NULL |
| source_id | INTEGER | ID of source | FK |
| source_type | TEXT | Source table reference | NOT NULL |
| loss_date | TEXT | Date of loss | NOT NULL |
| quantity | REAL | Quantity lost | NOT NULL, CHECK(quantity > 0) |
| reason | TEXT | Reason for loss | - |
| notes | TEXT | Additional notes | - |
| created_at | TEXT | Creation timestamp | DEFAULT CURRENT_TIMESTAMP |

**Indexes**:
- `idx_loss_of_goods_farm_id`: For joining with farms
- `idx_loss_of_goods_loss_date`: For time-based queries

## Indexing Strategy

The database uses a comprehensive indexing strategy to optimize common query patterns:

1. **Foreign Key Indexes**: All foreign key columns are indexed to optimize joins
2. **Time-Series Indexes**: Composite indexes on device_id and timestamp for efficient time-series queries
3. **Filtering Indexes**: Indexes on commonly filtered columns like 'active' status
4. **Search Indexes**: Indexes on columns frequently used in search operations

## Data Types and Constraints

1. **Data Types**:
   - INTEGER: For IDs and boolean flags (0/1)
   - REAL: For floating-point values
   - TEXT: For strings and timestamps (ISO format: YYYY-MM-DD HH:MM:SS)

2. **Constraints**:
   - Primary Keys: Defined for all tables
   - Foreign Keys: Enforce referential integrity
   - CHECK constraints: Validate data ranges and values
   - NOT NULL: Enforce required fields
   - DEFAULT values: Provide sensible defaults

## Soft Delete Pattern

Many tables implement a soft delete pattern using an 'active' column:
- active = 1: Record is active and should be included in normal queries
- active = 0: Record is logically deleted but retained for historical purposes
- deactivation_reason: Documents why a record was deactivated

Application code should filter for active=1 in most queries unless specifically retrieving historical data.

## Time-Series Data Management

Time-series data is stored efficiently with:
- Composite primary keys (device_id, reading_ts)
- Composite indexes for efficient time-range queries
- Original device timestamps preserved alongside system timestamps

## Schema Evolution

The schema is designed to evolve over time:
- Tables include created_at/updated_at timestamps for tracking changes
- Foreign key constraints are explicitly defined for integrity
- The schema allows for future extensions without breaking existing functionality
