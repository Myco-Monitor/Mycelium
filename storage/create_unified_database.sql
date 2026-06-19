-- Unified Database Creation Script for Mycelium Mushroom Farm Management System
-- This script creates all tables defined in the consolidated schema in a single database

-- Core Tables

-- Create farms table
CREATE TABLE IF NOT EXISTS farms (
    farm_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_name TEXT NOT NULL,
    farm_loc TEXT,
    farm_desc TEXT,
    active INTEGER DEFAULT 1,
    deactivation_reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_farms_name ON farms(farm_name);
CREATE INDEX IF NOT EXISTS idx_farms_active ON farms(active);

-- Create grow_rooms table
CREATE TABLE IF NOT EXISTS grow_rooms (
    room_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    room_name TEXT NOT NULL,
    room_desc TEXT,
    active INTEGER DEFAULT 1,
    deactivation_reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farm_id) REFERENCES farms(farm_id)
);

CREATE INDEX IF NOT EXISTS idx_grow_rooms_farm_id ON grow_rooms(farm_id);
CREATE INDEX IF NOT EXISTS idx_grow_rooms_active ON grow_rooms(active);

-- Create device_hyphae table
CREATE TABLE IF NOT EXISTS device_hyphae (
    device_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_name TEXT NOT NULL,
    room_id INTEGER NOT NULL,
    hostname TEXT NOT NULL,
    mac_address TEXT UNIQUE NOT NULL,
    mode_enabled INTEGER NOT NULL DEFAULT 0,
    mode_operation INTEGER NOT NULL DEFAULT 0,
    firmware_version TEXT,
    is_online INTEGER DEFAULT 0,
    last_update TEXT,
    active INTEGER DEFAULT 1,
    deactivation_reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (room_id) REFERENCES grow_rooms(room_id)
);

CREATE INDEX IF NOT EXISTS idx_device_hyphae_room_id ON device_hyphae(room_id);
CREATE INDEX IF NOT EXISTS idx_device_hyphae_active ON device_hyphae(active);

-- Create device_spore table
CREATE TABLE IF NOT EXISTS device_spore (
    device_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_name TEXT NOT NULL,
    room_id INTEGER NOT NULL,
    hyphae_id INTEGER,
    hostname TEXT NOT NULL,
    mac_address TEXT UNIQUE NOT NULL,
    hyphae_present INTEGER DEFAULT 0,
    firmware_version TEXT,
    is_online INTEGER DEFAULT 0,
    -- When 1 (and no Hyphae is linked), Mycelium pushes OpenWeatherMap-derived
    -- ambient pressure to this Spore for CO2 compensation. altitude_m (meters)
    -- lets Mycelium approximate local station pressure from sea-level pressure
    -- when OWM does not supply grnd_level.
    weather_pressure_enabled INTEGER DEFAULT 0,
    altitude_m REAL,
    last_update TEXT,
    active INTEGER DEFAULT 1,
    deactivation_reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (room_id) REFERENCES grow_rooms(room_id),
    FOREIGN KEY (hyphae_id) REFERENCES device_hyphae(device_id)
);

CREATE INDEX IF NOT EXISTS idx_device_spore_room_id ON device_spore(room_id);
CREATE INDEX IF NOT EXISTS idx_device_spore_hyphae_id ON device_spore(hyphae_id);

-- Time-series Data Tables

-- Create readings_spore table
CREATE TABLE IF NOT EXISTS readings_spore (
    device_id INTEGER NOT NULL,
    reading_ts TEXT NOT NULL,
    co2 REAL,
    humidity REAL,
    temp REAL,
    spore_ts TEXT,
    PRIMARY KEY (device_id, reading_ts),
    FOREIGN KEY (device_id) REFERENCES device_spore(device_id)
);

CREATE INDEX IF NOT EXISTS idx_readings_spore_device_id ON readings_spore(device_id);
CREATE INDEX IF NOT EXISTS idx_readings_spore_timestamp ON readings_spore(reading_ts);
CREATE INDEX IF NOT EXISTS idx_readings_spore_device_time ON readings_spore(device_id, reading_ts DESC);

-- Create readings_hyphae table
CREATE TABLE IF NOT EXISTS readings_hyphae (
    device_id INTEGER NOT NULL,
    reading_ts TEXT NOT NULL,
    relay_number INTEGER NOT NULL,
    relay_state INTEGER NOT NULL,
    cooldown INTEGER,
    testing INTEGER DEFAULT 0,
    hyphae_ts TEXT,
    PRIMARY KEY (device_id, reading_ts, relay_number),
    FOREIGN KEY (device_id) REFERENCES device_hyphae(device_id)
);

CREATE INDEX IF NOT EXISTS idx_readings_hyphae_device_id ON readings_hyphae(device_id);
CREATE INDEX IF NOT EXISTS idx_readings_hyphae_timestamp ON readings_hyphae(reading_ts);
CREATE INDEX IF NOT EXISTS idx_readings_hyphae_device_time ON readings_hyphae(device_id, reading_ts DESC);

-- Create readings_weather table
CREATE TABLE IF NOT EXISTS readings_weather (
    device_id INTEGER NOT NULL,
    reading_ts TEXT NOT NULL,
    current_temp REAL,
    feels_like REAL,
    humidity REAL,
    ambient_pressure REAL,
    PRIMARY KEY (device_id, reading_ts),
    FOREIGN KEY (device_id) REFERENCES device_spore(device_id)
);

CREATE INDEX IF NOT EXISTS idx_readings_weather_timestamp ON readings_weather(reading_ts);
CREATE INDEX IF NOT EXISTS idx_readings_weather_device_time ON readings_weather(device_id, reading_ts DESC);

-- Create readings_pressure table (BMP581 pressure from Hyphae devices)
CREATE TABLE IF NOT EXISTS readings_pressure (
    hyphae_id INTEGER NOT NULL,
    reading_ts TEXT NOT NULL,
    pressure_hpa INTEGER NOT NULL,
    source TEXT DEFAULT 'BMP581',
    healthy INTEGER DEFAULT 1,
    PRIMARY KEY (hyphae_id, reading_ts),
    FOREIGN KEY (hyphae_id) REFERENCES device_hyphae(device_id)
);

CREATE INDEX IF NOT EXISTS idx_readings_pressure_hyphae_id ON readings_pressure(hyphae_id);
CREATE INDEX IF NOT EXISTS idx_readings_pressure_timestamp ON readings_pressure(reading_ts);
CREATE INDEX IF NOT EXISTS idx_readings_pressure_device_time ON readings_pressure(hyphae_id, reading_ts DESC);

-- Fleet Management Tables

-- Firmware version inventory
CREATE TABLE IF NOT EXISTS firmware_versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_type TEXT NOT NULL CHECK(device_type IN ('spore', 'hyphae')),
    version TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    release_notes TEXT,
    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fw_device_type ON firmware_versions(device_type);
CREATE INDEX IF NOT EXISTS idx_fw_uploaded ON firmware_versions(uploaded_at);

-- OTA update event log
CREATE TABLE IF NOT EXISTS ota_history (
    ota_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    device_type TEXT NOT NULL CHECK(device_type IN ('spore', 'hyphae')),
    firmware_name TEXT,
    status TEXT NOT NULL CHECK(status IN ('pending', 'uploading', 'success', 'failed')),
    error_message TEXT,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_ota_device ON ota_history(device_id, device_type);
CREATE INDEX IF NOT EXISTS idx_ota_status ON ota_history(status);
CREATE INDEX IF NOT EXISTS idx_ota_started ON ota_history(started_at);

-- Calibration event log
CREATE TABLE IF NOT EXISTS calibration_history (
    cal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    cal_type TEXT NOT NULL CHECK(cal_type IN ('remote', 'manual')),
    target_ppm INTEGER,
    status TEXT NOT NULL CHECK(status IN ('scheduled', 'in_progress', 'completed', 'failed')),
    scheduled_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_cal_device ON calibration_history(device_id);
CREATE INDEX IF NOT EXISTS idx_cal_status ON calibration_history(status);
CREATE INDEX IF NOT EXISTS idx_cal_started ON calibration_history(started_at);

-- Configuration Tables

-- Create relay_settings table
CREATE TABLE IF NOT EXISTS relay_settings (
    device_id INTEGER NOT NULL,
    relay_number INTEGER NOT NULL,
    relay_name TEXT,
    group_num INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (device_id, relay_number),
    FOREIGN KEY (device_id) REFERENCES device_hyphae(device_id)
);

-- Create schedule_settings table
CREATE TABLE IF NOT EXISTS schedule_settings (
    device_id INTEGER,
    group_num INTEGER,
    on_time TEXT,
    off_time TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (device_id, group_num),
    FOREIGN KEY (device_id) REFERENCES device_hyphae(device_id)
);

CREATE INDEX IF NOT EXISTS idx_schedule_settings_device_id ON schedule_settings(device_id);

-- Create dynamic_settings table
CREATE TABLE IF NOT EXISTS dynamic_settings (
    device_id INTEGER NOT NULL,
    group_num INTEGER NOT NULL,
    parameter TEXT NOT NULL,
    low_threshold REAL NOT NULL,
    high_threshold REAL NOT NULL,
    behavior INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (device_id, group_num, parameter),
    FOREIGN KEY (device_id) REFERENCES device_hyphae(device_id)
);

CREATE INDEX IF NOT EXISTS idx_dynamic_settings_device_id ON dynamic_settings(device_id);

-- Create user_settings table
CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT NOT NULL UNIQUE,
    user_password TEXT NOT NULL,
    user_role TEXT,
    owm_api_key TEXT,
    owm_zip_code TEXT,
    timezone_name TEXT,
    time_format TEXT,
    temp_pref TEXT,
    reset_pin TEXT,
    farm_id INTEGER,
    smtp_server TEXT DEFAULT '',
    smtp_port TEXT DEFAULT '587',
    smtp_from TEXT DEFAULT '',
    smtp_to TEXT DEFAULT '',
    smtp_password TEXT DEFAULT '',
    smtp_use_tls TEXT DEFAULT '1',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farm_id) REFERENCES farms(farm_id)
);

-- Business Tables

-- Create product_categories table
CREATE TABLE IF NOT EXISTS product_categories (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT NOT NULL UNIQUE,
    category_type TEXT,
    category_desc TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Create cost_of_goods table
CREATE TABLE IF NOT EXISTS cost_of_goods (
    item_id INTEGER NOT NULL,
    item_name TEXT,
    item_cost REAL CHECK(item_cost >= 0),
    item_count INTEGER CHECK(item_count > 0),
    weight_lbs REAL CHECK(weight_lbs >= 0),
    item_used INTEGER DEFAULT 0 CHECK(item_used >= 0),
    used_weight REAL DEFAULT 0.0 CHECK(used_weight >= 0),
    unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_ts TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES product_categories(item_id)
);

CREATE INDEX IF NOT EXISTS idx_product_categories_name ON product_categories(category_name);
CREATE INDEX IF NOT EXISTS idx_product_categories_type ON product_categories(category_type);
CREATE INDEX IF NOT EXISTS idx_cost_of_goods_item_id ON cost_of_goods(item_id);
CREATE INDEX IF NOT EXISTS idx_cost_of_goods_purchase_date ON cost_of_goods(purchase_ts);

-- Create spawn table
CREATE TABLE IF NOT EXISTS spawn (
    spawn_id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER,
    total_wt REAL CHECK(total_wt > 0),
    bag_id INTEGER,
    bag_wt REAL CHECK(bag_wt > 0),
    bag_count INTEGER CHECK(bag_count >= 0),
    prep_notes TEXT,
    start_ts TEXT,
    inoculated_ts TEXT,
    finished_ts TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unit_id) REFERENCES cost_of_goods(unit_id),
    FOREIGN KEY (bag_id) REFERENCES cost_of_goods(unit_id)
);

CREATE INDEX IF NOT EXISTS idx_spawn_unit_id ON spawn(unit_id);
CREATE INDEX IF NOT EXISTS idx_spawn_bag_id ON spawn(bag_id);
CREATE INDEX IF NOT EXISTS idx_spawn_timestamps ON spawn(start_ts, finished_ts);

-- Create bulk table
CREATE TABLE IF NOT EXISTS bulk (
    bulk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    spawn_id INTEGER,
    unit_id INTEGER,
    total_wt REAL CHECK(total_wt > 0),
    bag_id INTEGER,
    bag_wt REAL CHECK(bag_wt > 0),
    bag_count INTEGER CHECK(bag_count >= 0),
    prep_notes TEXT,
    start_ts TEXT,
    colonized_ts TEXT,
    finished_ts TEXT,
    FOREIGN KEY (spawn_id) REFERENCES spawn(spawn_id),
    FOREIGN KEY (unit_id) REFERENCES cost_of_goods(unit_id),
    FOREIGN KEY (bag_id) REFERENCES cost_of_goods(unit_id)
);

CREATE INDEX IF NOT EXISTS idx_bulk_spawn_id ON bulk(spawn_id);
CREATE INDEX IF NOT EXISTS idx_bulk_unit_id ON bulk(unit_id);
CREATE INDEX IF NOT EXISTS idx_bulk_bag_id ON bulk(bag_id);
CREATE INDEX IF NOT EXISTS idx_bulk_timestamps ON bulk(start_ts, colonized_ts, finished_ts);

-- Create harvest table
CREATE TABLE IF NOT EXISTS harvest (
    harvest_id INTEGER PRIMARY KEY AUTOINCREMENT,
    harvest_ts TEXT NOT NULL,
    bulk_id INTEGER,
    total_wt REAL CHECK(total_wt > 0),
    trimmed_wt REAL CHECK(trimmed_wt >= 0),
    unit_id INTEGER,
    weight_used REAL DEFAULT 0.0 CHECK(weight_used >= 0),
    FOREIGN KEY (bulk_id) REFERENCES bulk(bulk_id),
    FOREIGN KEY (unit_id) REFERENCES cost_of_goods(unit_id)
);

CREATE INDEX IF NOT EXISTS idx_harvest_bulk_id ON harvest(bulk_id);
CREATE INDEX IF NOT EXISTS idx_harvest_unit_id ON harvest(unit_id);
CREATE INDEX IF NOT EXISTS idx_harvest_ts ON harvest(harvest_ts);

-- Create customers table
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER,
    customer_name TEXT NOT NULL,
    customer_info TEXT,
    customer_type TEXT,
    notes TEXT,
    active INTEGER DEFAULT 1,
    deactivation_reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farm_id) REFERENCES farms(farm_id)
);

CREATE INDEX IF NOT EXISTS idx_customers_farm_id ON customers(farm_id);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(customer_name);
CREATE INDEX IF NOT EXISTS idx_customers_type ON customers(customer_type);
CREATE INDEX IF NOT EXISTS idx_customers_active ON customers(active);

-- Create sales_transaction table
CREATE TABLE IF NOT EXISTS sales_transaction (
    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    sale_ts TEXT NOT NULL,
    total_amount REAL DEFAULT 0.0,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    active INTEGER DEFAULT 1,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE INDEX IF NOT EXISTS idx_sales_transaction_customer_id ON sales_transaction(customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_transaction_ts ON sales_transaction(sale_ts);

-- Create sales_detail table
CREATE TABLE IF NOT EXISTS sales_detail (
    detail_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    harvest_id INTEGER NOT NULL,
    unit_id INTEGER,
    weight_used REAL NOT NULL CHECK(weight_used > 0),
    price REAL NOT NULL CHECK(price >= 0),
    line_total REAL NOT NULL CHECK(line_total >= 0),
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sale_id) REFERENCES sales_transaction(sale_id),
    FOREIGN KEY (harvest_id) REFERENCES harvest(harvest_id),
    FOREIGN KEY (unit_id) REFERENCES cost_of_goods(unit_id)
);

CREATE INDEX IF NOT EXISTS idx_sales_detail_sale_id ON sales_detail(sale_id);
CREATE INDEX IF NOT EXISTS idx_sales_detail_harvest_id ON sales_detail(harvest_id);

-- Create employees table
CREATE TABLE IF NOT EXISTS employees (
    emp_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER,
    emp_name TEXT NOT NULL,
    emp_role TEXT,
    emp_rate REAL,
    emp_contact TEXT,
    emp_start TEXT,
    active INTEGER DEFAULT 1,
    deactivation_reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farm_id) REFERENCES farms(farm_id)
);

CREATE INDEX IF NOT EXISTS idx_employees_farm_id ON employees(farm_id);
CREATE INDEX IF NOT EXISTS idx_employees_active ON employees(active);

-- Create labour table
CREATE TABLE IF NOT EXISTS labour (
    labour_id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_id INTEGER NOT NULL,
    task_type TEXT NOT NULL,
    work_date TEXT NOT NULL,
    hours_worked REAL NOT NULL CHECK(hours_worked > 0),
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (emp_id) REFERENCES employees(emp_id)
);

CREATE INDEX IF NOT EXISTS idx_labour_emp_id ON labour(emp_id);
CREATE INDEX IF NOT EXISTS idx_labour_date_performed ON labour(work_date);

-- Create loss_of_goods table
CREATE TABLE IF NOT EXISTS loss_of_goods (
    loss_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER,
    item_type TEXT NOT NULL,
    source_id INTEGER,
    source_type TEXT NOT NULL,
    loss_date TEXT NOT NULL,
    quantity REAL NOT NULL CHECK(quantity > 0),
    reason TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farm_id) REFERENCES farms(farm_id)
);

CREATE INDEX IF NOT EXISTS idx_loss_of_goods_farm_id ON loss_of_goods(farm_id);
CREATE INDEX IF NOT EXISTS idx_loss_of_goods_loss_date ON loss_of_goods(loss_date);

-- Create utilities table
CREATE TABLE IF NOT EXISTS utilities (
    unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    util_name TEXT NOT NULL,
    util_cost REAL NOT NULL CHECK(util_cost >= 0),
    util_recd TEXT NOT NULL,
    util_dued TEXT NOT NULL,
    util_paid TEXT,
    util_note TEXT,
    farm_id INTEGER NOT NULL,
    room_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farm_id) REFERENCES farms(farm_id),
    FOREIGN KEY (room_id) REFERENCES grow_rooms(room_id)
);

CREATE INDEX IF NOT EXISTS idx_utilities_farm_id ON utilities(farm_id);
CREATE INDEX IF NOT EXISTS idx_utilities_room_id ON utilities(room_id);
CREATE INDEX IF NOT EXISTS idx_utilities_dued ON utilities(util_dued);

-- Device Health Monitoring

-- Create device_health_log table for tracking device health over time
CREATE TABLE IF NOT EXISTS device_health_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    device_type TEXT NOT NULL CHECK(device_type IN ('spore', 'hyphae')),
    check_time TEXT DEFAULT CURRENT_TIMESTAMP,
    is_online INTEGER NOT NULL,
    response_time_ms INTEGER,
    error_message TEXT,
    http_status_code INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_health_device ON device_health_log(device_id, device_type);
CREATE INDEX IF NOT EXISTS idx_health_time ON device_health_log(check_time);
CREATE INDEX IF NOT EXISTS idx_health_online ON device_health_log(is_online);

-- Device PIN Storage (for authenticated device control)
-- PINs are stored encrypted using Fernet symmetric encryption

CREATE TABLE IF NOT EXISTS device_pins (
    device_id INTEGER NOT NULL,
    device_type TEXT NOT NULL CHECK(device_type IN ('spore', 'hyphae')),
    encrypted_pin TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (device_id, device_type)
);

CREATE INDEX IF NOT EXISTS idx_device_pins_device ON device_pins(device_id, device_type);

-- Alerting System Tables

-- Create alert_rules table for configurable alert conditions
CREATE TABLE IF NOT EXISTS alert_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT NOT NULL,
    rule_type TEXT NOT NULL CHECK(rule_type IN ('offline', 'threshold_high', 'threshold_low', 'error', 'degraded')),
    device_type TEXT,
    device_id INTEGER,
    room_id INTEGER,
    metric TEXT,
    threshold_value REAL,
    threshold_duration_minutes INTEGER DEFAULT 5,
    notification_method TEXT DEFAULT 'ui',
    notification_target TEXT,
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled);
CREATE INDEX IF NOT EXISTS idx_alert_rules_type ON alert_rules(rule_type);

-- Create alert_history table for tracking triggered alerts
CREATE TABLE IF NOT EXISTS alert_history (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER NOT NULL,
    device_id INTEGER,
    device_type TEXT,
    triggered_at TEXT DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT,
    alert_message TEXT NOT NULL,
    alert_value REAL,
    acknowledged INTEGER DEFAULT 0,
    acknowledged_by INTEGER,
    acknowledged_at TEXT,
    notes TEXT,
    FOREIGN KEY (rule_id) REFERENCES alert_rules(rule_id)
);

CREATE INDEX IF NOT EXISTS idx_alert_history_triggered ON alert_history(triggered_at);
CREATE INDEX IF NOT EXISTS idx_alert_history_resolved ON alert_history(resolved_at);
CREATE INDEX IF NOT EXISTS idx_alert_history_ack ON alert_history(acknowledged);
CREATE INDEX IF NOT EXISTS idx_alert_history_rule ON alert_history(rule_id);

-- Create notification_settings table for user notification preferences
CREATE TABLE IF NOT EXISTS notification_settings (
    setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    email_enabled INTEGER DEFAULT 0,
    email_address TEXT,
    smtp_server TEXT,
    smtp_port INTEGER DEFAULT 587,
    smtp_username TEXT,
    smtp_password_encrypted TEXT,
    smtp_use_tls INTEGER DEFAULT 1,
    quiet_hours_enabled INTEGER DEFAULT 0,
    quiet_hours_start TEXT,
    quiet_hours_end TEXT,
    min_alert_interval_minutes INTEGER DEFAULT 15,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_settings(user_id)
);

CREATE INDEX IF NOT EXISTS idx_notification_settings_user ON notification_settings(user_id);

-- Create notification_log table for tracking notification delivery
CREATE TABLE IF NOT EXISTS notification_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id INTEGER NOT NULL,
    notification_method TEXT NOT NULL,
    recipient TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (alert_id) REFERENCES alert_history(alert_id)
);

CREATE INDEX IF NOT EXISTS idx_notification_log_alert ON notification_log(alert_id);
CREATE INDEX IF NOT EXISTS idx_notification_log_status ON notification_log(status);

-- REST API Tables

-- Create api_keys table for API authentication
CREATE TABLE IF NOT EXISTS api_keys (
    key_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    key_name TEXT NOT NULL,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_used TEXT,
    FOREIGN KEY (user_id) REFERENCES user_settings(user_id)
);

CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);

-- Create webhooks table for event subscriptions
CREATE TABLE IF NOT EXISTS webhooks (
    webhook_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    events TEXT NOT NULL,
    secret TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_settings(user_id)
);

CREATE INDEX IF NOT EXISTS idx_webhooks_user ON webhooks(user_id);

-- Create webhook_deliveries table for logging webhook attempts
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
    webhook_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    status_code INTEGER,
    success INTEGER,
    error TEXT,
    delivered_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (webhook_id) REFERENCES webhooks(webhook_id)
);

CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook ON webhook_deliveries(webhook_id);
