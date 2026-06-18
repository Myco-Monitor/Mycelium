"""
Migration 001: Add fleet management tables.

Adds firmware_versions, ota_history, and calibration_history tables.
These are additive only — no existing tables are modified or dropped.

Usage:
    python -m storage.migrations.001_add_fleet_tables
"""

import sqlite3
import sys
from pathlib import Path

NEW_TABLES_SQL = """
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
"""


def migrate(db_path: str = None):
    """Run migration to add fleet management tables."""
    if db_path is None:
        db_path = str(Path(__file__).parent.parent.parent / 'data' / 'mycelium.db')

    print(f"Running migration 001_add_fleet_tables on {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(NEW_TABLES_SQL)
        conn.commit()
        print("Migration 001 completed successfully:")
        print("  + firmware_versions table")
        print("  + ota_history table")
        print("  + calibration_history table")
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    db = sys.argv[1] if len(sys.argv) > 1 else None
    migrate(db)
