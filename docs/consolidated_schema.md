# Consolidated Mycelium Database Schema

This schema integrates the core monitoring functionality with business operations for a complete mushroom farm management system. It incorporates the many-to-many relationship between sales and harvests and ensures all tables are properly related.

## Core System Tables

### farms
| Column       | Type      | Description                        | Constraints      |
|-------------|-----------|------------------------------------|------------------|
| farm_id     | INTEGER   | Unique identifier for the farm     | PK, AUTOINCREMENT|
| farm_name   | TEXT      | Farm name                          | NOT NULL         |
| farm_loc    | TEXT      | Physical location/address          | -                |
| farm_desc   | TEXT      | Description of the farm            | -                |
| active      | INTEGER   | Active status (1=active, 0=deleted)| DEFAULT 1        |
| deactivation_reason | TEXT | Reason for deactivation if inactive | -              |
| created_at  | TEXT      | Creation timestamp                 | DEFAULT CURRENT_TIMESTAMP |
| updated_at  | TEXT      | Last update timestamp              | DEFAULT CURRENT_TIMESTAMP |

### grow_rooms
| Column       | Type      | Description                        | Constraints      |
|-------------|-----------|------------------------------------|------------------|
| room_id     | INTEGER   | Unique identifier for the grow room| PK, AUTOINCREMENT|
| farm_id     | INTEGER   | Reference to farm                  | FK, NOT NULL     |
| room_name   | TEXT      | Room name                          | NOT NULL         |
| room_desc   | TEXT      | Description of the grow room       | -                |
| active      | INTEGER   | Active status (1=active, 0=deleted)| DEFAULT 1        |
| deactivation_reason | TEXT | Reason for deactivation if inactive | -              |
| created_at  | TEXT      | Creation timestamp                 | DEFAULT CURRENT_TIMESTAMP |
| updated_at  | TEXT      | Last update timestamp              | DEFAULT CURRENT_TIMESTAMP |

### device_spore
| Column           | Type      | Description                        | Constraints      |
|-----------------|-----------|------------------------------------|------------------|
| device_id       | INTEGER   | Unique identifier for Spore device | PK, AUTOINCREMENT|
| device_name     | TEXT      | Device name                        | NOT NULL         |
| room_id         | INTEGER   | Reference to grow room             | FK, NOT NULL     |
| hyphae_id       | INTEGER   | Linked Hyphae device ID            | FK               |
| ip_address      | TEXT      | IP address                         | NOT NULL         |
| mac_address     | TEXT      | Device MAC address                 | UNIQUE, NOT NULL |
| hyphae_present  | INTEGER   | Whether Hyphae is present (0/1)    | DEFAULT 0        |
| firmware_version| TEXT      | Firmware version                   | -                |
| is_online       | INTEGER   | Online status (0/1)                | DEFAULT 0        |
| last_update     | TEXT      | Last communication timestamp       | -                |
| active          | INTEGER   | Active status (1=active, 0=deleted)| DEFAULT 1        |
| deactivation_reason | TEXT | Reason for deactivation if inactive | -              |
| created_at      | TEXT      | Creation timestamp                 | DEFAULT CURRENT_TIMESTAMP |

### device_hyphae
| Column           | Type      | Description                        | Constraints      |
|-----------------|-----------|------------------------------------|------------------|
| device_id       | INTEGER   | Unique identifier for Hyphae device| PK, AUTOINCREMENT|
| device_name     | TEXT      | Device name                        | NOT NULL         |
| room_id         | INTEGER   | Reference to grow room             | FK, NOT NULL     |
| ip_address      | TEXT      | IP address                         | NOT NULL         |
| mac_address     | TEXT      | MAC address                        | UNIQUE, NOT NULL |
| mode_enabled    | INTEGER   | 0=Offline, 1=Testing, 2=Running    | NOT NULL, DEFAULT 0 |
| mode_operation  | INTEGER   | 0=Schedule, 1=Dynamic              | NOT NULL, DEFAULT 0 |
| firmware_version| TEXT      | Firmware version                   | -                |
| is_online       | INTEGER   | Online status (0/1)                | DEFAULT 0        |
| last_update     | TEXT      | Last communication timestamp       | -                |
| active          | INTEGER   | Active status (1=active, 0=deleted)| DEFAULT 1        |
| deactivation_reason | TEXT | Reason for deactivation if inactive | -              |
| created_at  | TEXT      | Creation timestamp                 | DEFAULT CURRENT_TIMESTAMP |
| updated_at  | TEXT      | Last update timestamp              | DEFAULT CURRENT_TIMESTAMP |

## Time-Series Data Tables

### readings_weather
| Column           | Type      | Description                        | Constraints      |
|-----------------|-----------|------------------------------------|------------------|
| device_id       | INTEGER   | Reference to device                | PK, FK           |
| reading_ts      | TEXT      | Reading timestamp                  | PK               |
| current_temp    | REAL      | Current temperature                | -                |
| feels_like      | REAL      | "Feels like" temperature           | -                |
| humidity        | REAL      | Humidity percentage                | -                |
| ambient_pressure| REAL      | Ambient pressure (mbar)            | -                |

### readings_spore
| Column           | Type      | Description                        | Constraints      |
|-----------------|-----------|------------------------------------|------------------|
| device_id       | INTEGER   | Reference to Spore device          | PK, FK           |
| reading_ts      | TEXT      | Reading timestamp                  | PK               |
| co2             | REAL      | CO2 reading (ppm)                  | -                |
| humidity        | REAL      | Humidity reading (%)               | -                |
| temp            | REAL      | Temperature reading                | -                |
| spore_ts        | TEXT      | Original device timestamp          | -                |

### readings_hyphae
| Column        | Type      | Description                        | Constraints      |
|---------------|-----------|------------------------------------|------------------|
| device_id     | INTEGER   | Reference to Hyphae device         | PK, FK           |
| reading_ts    | TEXT      | Reading timestamp                  | PK               |
| relay_number  | INTEGER   | Relay number (1-6)                 | PK               |
| relay_state   | INTEGER   | Relay state (1=ON, 0=OFF)          | NOT NULL         |
| cooldown      | INTEGER   | Cooldown time remaining (seconds)  | -                |
| testing       | INTEGER   | Testing mode flag (0/1)            | DEFAULT 0        |
| hyphae_ts     | TEXT      | Original device timestamp          | -                |

## Configuration Tables

### relay_settings
| Column          | Type      | Description                        | Constraints      |
|----------------|-----------|------------------------------------|------------------|
| device_id      | INTEGER   | Reference to Hyphae device         | PK, FK           |
| relay_number   | INTEGER   | Relay number (1-6)                 | PK               |
| relay_name     | TEXT      | Relay name                         | -                |
| group_num      | INTEGER   | Group number (1-6)                 | NOT NULL         |
| created_at     | TEXT      | Creation timestamp                 | DEFAULT CURRENT_TIMESTAMP |
| updated_at     | TEXT      | Last update timestamp              | DEFAULT CURRENT_TIMESTAMP |

### schedule_settings
| Column            | Type      | Description                        | Constraints      |
|------------------|-----------|------------------------------------|------------------|
| device_id        | INTEGER   | Reference to Hyphae device         | PK, FK           |
| group_num        | INTEGER   | Group number (1-6)                 | PK               |
| on_time          | TEXT      | Schedule ON time (HH:MM)           | -                |
| off_time         | TEXT      | Schedule OFF time (HH:MM)          | -                |
| created_at       | TEXT      | Creation timestamp                 | DEFAULT CURRENT_TIMESTAMP |
| updated_at       | TEXT      | Last update timestamp              | DEFAULT CURRENT_TIMESTAMP |

### dynamic_settings
| Column         | Type      | Description                        | Constraints      |
|---------------|-----------|------------------------------------|------------------|
| device_id     | INTEGER   | Reference to Hyphae device         | PK, FK           |
| group_num     | INTEGER   | Group number (1-3)                 | PK               |
| parameter     | TEXT      | 'temperature', 'humidity', 'co2'   | PK               |
| low_threshold | REAL      | Low threshold value                | NOT NULL         |
| high_threshold| REAL      | High threshold value               | NOT NULL         |
| behavior      | INTEGER   | Behavior (0 or 1)                  | NOT NULL         |
| created_at    | TEXT      | Creation timestamp                 | DEFAULT CURRENT_TIMESTAMP |
| updated_at    | TEXT      | Last update timestamp              | DEFAULT CURRENT_TIMESTAMP |

### user_settings
| Column        | Type      | Description                        | Constraints      |
|---------------|-----------|------------------------------------|------------------|
| user_id       | INTEGER   | Primary key                        | PK, AUTOINCREMENT|
| owm_api_key   | TEXT      | OpenWeatherMap API key             | -                |
| owm_zip_code  | TEXT      | ZIP code for weather               | -                |
| timezone_name | TEXT      | Timezone name (ET,PT,CT,MT)        | -                |
| time_format   | TEXT      | Time format (12 or 24)             | -                |
| temp_pref     | TEXT      | Temperature preference (C or F)    | -                |
| reset_pin     | TEXT      | Reset PIN (hashed)                 | -                |
| farm_id       | INTEGER   | Reference to farms.farm_id         | FK               |
| created_at    | TEXT      | Creation timestamp                 | DEFAULT CURRENT_TIMESTAMP |
| updated_at    | TEXT      | Last update timestamp              | DEFAULT CURRENT_TIMESTAMP |

## Business Operations Tables

### product_categories
| Column        | Type      | Description                        | Constraints      |
|---------------|-----------|------------------------------------|------------------|
| item_id       | INTEGER   | Unique identifier for product type | PK, AUTOINCREMENT|
| category_name | TEXT      | Name of the product category       | NOT NULL, UNIQUE |
| category_type | TEXT      | Type classification (mushroom, substrate, equipment, etc.) | -    |
| category_desc | TEXT      | Description of the product category| -                |
| active        | INTEGER   | Active status (1=active, 0=deleted)| DEFAULT 1        |
| created_at    | TEXT      | Creation timestamp                 | DEFAULT CURRENT_TIMESTAMP |
| updated_at    | TEXT      | Last update timestamp              | DEFAULT CURRENT_TIMESTAMP |

### cost_of_goods
| Column        | Type      | Description                        | Constraints      |
|---------------|-----------|------------------------------------|------------------|
| item_id       | INTEGER   | Reference to product category      | FK, NOT NULL     |
| item_name     | TEXT      | Name of the good/item              | -                |
| item_cost     | REAL      | Purchase cost for batch/unit       | CHECK(item_cost >= 0) |
| item_count    | INTEGER   | Number of units purchased          | CHECK(item_count > 0) |
| weight_lbs    | REAL      | Weight per unit/batch (lbs)        | CHECK(weight_lbs >= 0) |
| item_used     | INTEGER   | Number of units used from batch    | DEFAULT 0, CHECK(item_used >= 0) |
| used_weight   | REAL      | Total weight used from batch       | DEFAULT 0.0, CHECK(used_weight >= 0) |
| unit_id       | INTEGER   | Unique identifier for batch/unit   | PK, AUTOINCREMENT |
| purchase_ts   | TEXT      | Timestamp of purchase              | -                |
| created_at    | TEXT      | Creation timestamp                 | DEFAULT CURRENT_TIMESTAMP |
| updated_at    | TEXT      | Last update timestamp              | DEFAULT CURRENT_TIMESTAMP |

### spawn
| Column        | Type      | Description                        | Constraints      |
|---------------|-----------|------------------------------------|------------------|
| spawn_id      | INTEGER   | Unique identifier for spawn batch  | PK, AUTOINCREMENT|
| unit_id       | INTEGER   | Reference to spawn type            | FK               |
| total_wt      | REAL      | Total dry weight for spawn batch   | CHECK(total_wt > 0) |
| bag_id        | INTEGER   | Bag used for spawn                 | FK               |
| bag_wt        | REAL      | Wet weight per spawn bag           | CHECK(bag_wt > 0) |
| bag_count     | INTEGER   | Number of bags used for spawn      | CHECK(bag_count >= 0) |
| prep_notes    | TEXT      | Preparation notes                  | -                |
| start_ts      | TEXT      | Spawn creation timestamp           | -                |
| inoculated_ts | TEXT      | Inoculation timestamp              | -                |
| finished_ts   | TEXT      | Finished timestamp                 | -                |

### bulk
| Column        | Type      | Description                        | Constraints      |
|---------------|-----------|------------------------------------|------------------|
| bulk_id       | INTEGER   | Unique identifier for bulk batch   | PK, AUTOINCREMENT|
| spawn_id      | INTEGER   | Reference to spawn batch           | FK               |
| unit_id       | INTEGER   | Reference to substrate blend       | FK               |
| total_wt      | REAL      | Total dry weight for bulk batch    | CHECK(total_wt > 0) |
| bag_id        | INTEGER   | Bag used for bulk                  | FK               |
| bag_wt        | REAL      | Wet weight per bulk bag            | CHECK(bag_wt > 0) |
| bag_count     | INTEGER   | Number of bags used for bulk       | CHECK(bag_count >= 0) |
| prep_notes    | TEXT      | Preparation notes                  | -                |
| start_ts      | TEXT      | Bulk creation timestamp            | -                |
| colonized_ts  | TEXT      | Colonization start timestamp       | -                |
| finished_ts   | TEXT      | Colonization finished timestamp    | -                |

### harvest
| Column        | Type      | Description                        | Constraints      |
|---------------|-----------|------------------------------------|------------------|
| harvest_id    | INTEGER   | Unique identifier for harvest      | PK, AUTOINCREMENT|
| harvest_ts    | TEXT      | Harvest timestamp                  | NOT NULL         |
| bulk_id       | INTEGER   | Reference to bulk batch            | FK               |
| total_wt      | REAL      | Total harvested weight             | CHECK(total_wt > 0) |
| trimmed_wt    | REAL      | Net trimmed weight                 | CHECK(trimmed_wt >= 0) |
| unit_id       | INTEGER   | Packaging material or batch used   | FK               |
| weight_used   | REAL      | Weight of mushrooms used           | DEFAULT 0.0, CHECK(weight_used >= 0) |

### sales_transaction
| Column        | Type      | Description                        | Constraints      |
|---------------|-----------|------------------------------------|------------------|
| sale_id       | INTEGER   | Sale transaction identifier        | PK, AUTOINCREMENT|
| customer_id   | INTEGER   | Reference to customer (optional)   | FK               |
| sale_ts       | TEXT      | Sale timestamp                     | NOT NULL         |
| total_amount  | REAL      | Total sale amount                  | DEFAULT 0.0      |
| notes         | TEXT      | Additional notes about sale        | -                |
| created_at    | TEXT      | Record creation timestamp          | DEFAULT CURRENT_TIMESTAMP |
| active        | INTEGER   | Active status (1=active, 0=deleted)| DEFAULT 1        |

### sales_detail
| Column        | Type      | Description                        | Constraints      |
|---------------|-----------|------------------------------------|------------------|
| detail_id     | INTEGER   | Detail entry identifier            | PK, AUTOINCREMENT|
| sale_id       | INTEGER   | Reference to sales transaction     | FK, NOT NULL     |
| harvest_id    | INTEGER   | Reference to harvest               | FK, NOT NULL     |
| unit_id       | INTEGER   | Packaging material or batch used   | FK               |
| weight_used   | REAL      | Weight debited from harvest        | NOT NULL, CHECK(weight_used > 0) |
| price         | REAL      | Price per pound                    | NOT NULL, CHECK(price >= 0) |
| line_total    | REAL      | Total for this line item           | NOT NULL, CHECK(line_total >= 0) |
| notes         | TEXT      | Notes for this line item           | -                |
| created_at    | TEXT      | Record creation timestamp          | DEFAULT CURRENT_TIMESTAMP |

### employees
| Column        | Type      | Description                        | Constraints      |
|---------------|-----------|------------------------------------|------------------|
| emp_id        | INTEGER   | Unique identifier for employee     | PK, AUTOINCREMENT|
| farm_id       | INTEGER   | Reference to farm                  | FK               |
| emp_name      | TEXT      | Employee name                      | NOT NULL         |
| emp_role      | TEXT      | Employee role/position             | -                |
| emp_rate      | REAL      | Hourly pay rate                    | -                |
| emp_contact   | TEXT      | Contact information                | -                |
| emp_start     | TEXT      | Employment start date              | -                |
| active        | INTEGER   | Active status (0/1)               | DEFAULT 1        |
| deactivation_reason | TEXT | Reason for deactivation if inactive | -              |
| created_at    | TEXT      | Record creation timestamp          | DEFAULT CURRENT_TIMESTAMP |
| updated_at    | TEXT      | Record update timestamp            | DEFAULT CURRENT_TIMESTAMP |

### labour
| Column        | Type      | Description                        | Constraints      |
|---------------|-----------|------------------------------------|------------------|
| labour_id     | INTEGER   | Unique identifier for labor entry  | PK, AUTOINCREMENT|
| emp_id        | INTEGER   | Reference to employee              | FK, NOT NULL     |
| task_type     | TEXT      | Type of work (e.g., Harvesting)    | NOT NULL         |
| work_date     | TEXT      | Date of work performed             | NOT NULL         |
| hours_worked  | REAL      | Number of hours worked that day    | NOT NULL, CHECK(hours_worked > 0) |
| notes         | TEXT      | Additional notes about work        | -                |
| created_at    | TEXT      | Record creation timestamp          | DEFAULT CURRENT_TIMESTAMP |

### customers
| Column        | Type      | Description                        | Constraints      |
|---------------|-----------|------------------------------------|------------------|
| customer_id   | INTEGER   | Unique identifier for customer     | PK, AUTOINCREMENT|
| farm_id       | INTEGER   | Reference to farm                  | FK               |
| customer_name | TEXT      | Customer name                      | NOT NULL         |
| customer_info | TEXT      | Customer contact details           | -                |
| customer_type | TEXT      | Customer type (retail/wholesale)   | -                |
| notes         | TEXT      | Additional notes about customer    | -                |
| active        | INTEGER   | Active status (1=active, 0=deleted)| DEFAULT 1        |
| deactivation_reason | TEXT | Reason for deactivation if inactive | -              |
| created_at    | TEXT      | Record creation timestamp          | DEFAULT CURRENT_TIMESTAMP |
| updated_at    | TEXT      | Record update timestamp            | DEFAULT CURRENT_TIMESTAMP |

### loss_of_goods
| Column        | Type      | Description                        | Constraints      |
|---------------|-----------|------------------------------------|------------------|
| loss_id       | INTEGER   | Unique identifier for loss entry   | PK, AUTOINCREMENT|
| farm_id       | INTEGER   | Reference to farm                  | FK               |
| item_type     | TEXT      | Type of item lost                  | NOT NULL         |
| source_id     | INTEGER   | ID of source (spawn_id, bulk_id, etc.) | FK           |
| source_type | TEXT | What is the source? ('spawn', 'bulk', 'harvest', etc.) | NOT NULL |
| loss_date     | TEXT      | Date of loss                       | NOT NULL         |
| quantity      | REAL      | Quantity lost                      | NOT NULL, CHECK(quantity > 0) |
| reason        | TEXT      | Reason for loss                    | -                |
| notes         | TEXT      | Additional notes                   | -                |
| created_at    | TEXT      | Record creation timestamp          | DEFAULT CURRENT_TIMESTAMP |

### utilities
| Column       | Type    | Description                        | Constraints                                   |
|--------------|---------|------------------------------------|-----------------------------------------------|
| unit_id      | INTEGER | Unique identifier for utility bill | PK, AUTOINCREMENT                             |
| util_name    | TEXT    | Name of the bill/company           | NOT NULL                                      |
| util_cost    | REAL    | Cost of the bill/company           | NOT NULL, CHECK(util_cost >= 0)               |
| util_recd    | TEXT    | Date the bill was received         | NOT NULL                                      |
| util_dued    | TEXT    | Due date of the bill               | NOT NULL                                      |
| util_paid    | TEXT    | Date the bill was paid             |                                                |
| util_note    | TEXT    | Notes about the bill               |                                                |
| farm_id      | INTEGER | Unique Farm ID                     | NOT NULL, FK (farms.farm_id)                  |
| room_id      | INTEGER | Unique Room ID                     | FK (rooms.room_id)                            |
| created_at   | TEXT    | Creation timestamp                 | DEFAULT CURRENT_TIMESTAMP                     |
| updated_at   | TEXT    | Last update timestamp              | DEFAULT CURRENT_TIMESTAMP                     |

## Foreign Key Constraints

```sql
-- Core tables relationships
ALTER TABLE grow_rooms ADD CONSTRAINT fk_grow_rooms_farm FOREIGN KEY (farm_id) REFERENCES farms(farm_id);
ALTER TABLE device_spore ADD CONSTRAINT fk_device_spore_room FOREIGN KEY (room_id) REFERENCES grow_rooms(room_id);
ALTER TABLE device_spore ADD CONSTRAINT fk_device_spore_hyphae FOREIGN KEY (hyphae_device_id) REFERENCES device_hyphae(device_id);
ALTER TABLE device_hyphae ADD CONSTRAINT fk_device_hyphae_room FOREIGN KEY (room_id) REFERENCES grow_rooms(room_id);

-- Time-series tables relationships
ALTER TABLE readings_spore ADD CONSTRAINT fk_readings_spore_device FOREIGN KEY (device_id) REFERENCES device_spore(device_id);
ALTER TABLE readings_hyphae ADD CONSTRAINT fk_readings_hyphae_device FOREIGN KEY (device_id) REFERENCES device_hyphae(device_id);
ALTER TABLE readings_weather ADD CONSTRAINT fk_readings_weather_device FOREIGN KEY (device_id) REFERENCES device_spore(device_id);

-- Configuration tables relationships
ALTER TABLE relay_settings ADD CONSTRAINT fk_relay_settings_device FOREIGN KEY (device_id) REFERENCES device_hyphae(device_id);
ALTER TABLE schedule_settings ADD CONSTRAINT fk_schedule_settings_device FOREIGN KEY (device_id) REFERENCES device_hyphae(device_id);
ALTER TABLE dynamic_settings ADD CONSTRAINT fk_dynamic_settings_device FOREIGN KEY (device_id) REFERENCES device_hyphae(device_id);
ALTER TABLE user_settings ADD CONSTRAINT fk_user_settings_farm FOREIGN KEY (farm_id) REFERENCES farms(farm_id);

-- Business operations relationships
ALTER TABLE cost_of_goods ADD CONSTRAINT fk_cost_of_goods_item FOREIGN KEY (item_id) REFERENCES product_categories(item_id);
ALTER TABLE spawn ADD CONSTRAINT fk_spawn_unit FOREIGN KEY (unit_id) REFERENCES cost_of_goods(unit_id);
ALTER TABLE spawn ADD CONSTRAINT fk_spawn_bag FOREIGN KEY (bag_id) REFERENCES cost_of_goods(unit_id);
ALTER TABLE bulk ADD CONSTRAINT fk_bulk_spawn FOREIGN KEY (spawn_id) REFERENCES spawn(spawn_id);
ALTER TABLE bulk ADD CONSTRAINT fk_bulk_unit FOREIGN KEY (unit_id) REFERENCES cost_of_goods(unit_id);
ALTER TABLE bulk ADD CONSTRAINT fk_bulk_bag FOREIGN KEY (bag_id) REFERENCES cost_of_goods(unit_id);
ALTER TABLE harvest ADD CONSTRAINT fk_harvest_bulk FOREIGN KEY (bulk_id) REFERENCES bulk(bulk_id);
ALTER TABLE harvest ADD CONSTRAINT fk_harvest_unit FOREIGN KEY (unit_id) REFERENCES cost_of_goods(unit_id);
ALTER TABLE sales_transaction ADD CONSTRAINT fk_sales_transaction_customer FOREIGN KEY (customer_id) REFERENCES customers(customer_id);
ALTER TABLE sales_detail ADD CONSTRAINT fk_sales_detail_transaction FOREIGN KEY (sale_id) REFERENCES sales_transaction(sale_id);
ALTER TABLE sales_detail ADD CONSTRAINT fk_sales_detail_harvest FOREIGN KEY (harvest_id) REFERENCES harvest(harvest_id);
ALTER TABLE sales_detail ADD CONSTRAINT fk_sales_detail_unit FOREIGN KEY (unit_id) REFERENCES cost_of_goods(unit_id);
ALTER TABLE customers ADD CONSTRAINT fk_customers_farm FOREIGN KEY (farm_id) REFERENCES farms(farm_id);
ALTER TABLE employees ADD CONSTRAINT fk_employees_farm FOREIGN KEY (farm_id) REFERENCES farms(farm_id);
ALTER TABLE labour ADD CONSTRAINT fk_labour_employee FOREIGN KEY (employee_id) REFERENCES employees(employee_id);
ALTER TABLE loss_of_goods ADD CONSTRAINT fk_loss_farm FOREIGN KEY (farm_id) REFERENCES farms(farm_id);
```

## Indexes

```sql
-- Core table indexes
CREATE INDEX idx_grow_rooms_farm_id ON grow_rooms(farm_id);
CREATE INDEX idx_device_spore_room_id ON device_spore(room_id);
CREATE INDEX idx_device_spore_hyphae_id ON device_spore(hyphae_device_id);
CREATE INDEX idx_device_hyphae_room_id ON device_hyphae(room_id);

-- Time-series data indexes
CREATE INDEX idx_readings_spore_timestamp ON readings_spore(timestamp);
CREATE INDEX idx_readings_spore_device_time ON readings_spore(device_id, timestamp DESC);
CREATE INDEX idx_readings_hyphae_timestamp ON readings_hyphae(timestamp);
CREATE INDEX idx_readings_hyphae_device_time ON readings_hyphae(device_id, timestamp DESC);
CREATE INDEX idx_readings_weather_timestamp ON readings_weather(timestamp);
CREATE INDEX idx_readings_weather_device_time ON readings_weather(device_id, timestamp DESC);

-- Business data indexes
CREATE INDEX idx_product_categories_name ON product_categories(category_name);
CREATE INDEX idx_product_categories_type ON product_categories(category_type);
CREATE INDEX idx_cost_of_goods_item_id ON cost_of_goods(item_id);
CREATE INDEX idx_cost_of_goods_purchase ON cost_of_goods(purchase_ts);
CREATE INDEX idx_spawn_timestamps ON spawn(start_ts, finished_ts);
CREATE INDEX idx_bulk_timestamps ON bulk(start_ts, finished_ts);
CREATE INDEX idx_harvest_ts ON harvest(harvest_ts);
CREATE INDEX idx_sales_transaction_ts ON sales_transaction(sale_ts);
CREATE INDEX idx_sales_detail_sale_id ON sales_detail(sale_id);
CREATE INDEX idx_sales_detail_harvest_id ON sales_detail(harvest_id);
```

## Notes

1. All timestamp fields are stored as TEXT in ISO format (YYYY-MM-DD HH:MM:SS)
2. Boolean values are stored as INTEGER (0/1) for SQLite compatibility
3. The sales relationship uses a sales_transaction and sales_detail structure to enable many-to-many sales-to-harvest mapping. Each sales_detail row is uniquely identified by detail_id.
4. Foreign key constraints are explicitly defined to maintain data integrity
5. Indexes are created for frequently queried columns and join operations
6. Default values are provided for common fields to simplify data entry
7. Application logic must filter for active=1 when querying tables with soft delete capability
8. Application logic must update the updated_at timestamp whenever a record is modified (do NOT use SQLite triggers for this as they can cause infinite recursion)
9. The source_type field in loss_of_goods clarifies which table the source_id references
