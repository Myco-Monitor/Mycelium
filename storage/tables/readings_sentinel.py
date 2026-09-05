"""
Readings Sentinel Table Module for Mycelium

This module provides functions for interacting with the readings_sentinel table
in the Mycelium database.

Every channel is nullable: the Sentinel firmware reports null for a channel
that is unavailable (sensor warming up or faulted), and that is stored as-is
rather than as a fake 0. Units: PM in ug/m3, VOC/NOx are Sensirion indices
(1-500), CO2 in ppm, temp in Celsius, humidity in %RH, pressure in hPa.
"""

from typing import Dict, List, Optional, Tuple, Any

from storage.db_utils import execute_query, execute_insert, execute_update

# Column order used by create_reading; kept in one place so the service layer
# and the analytics registry agree on the channel names.
CHANNELS = (
    "pm1",
    "pm2_5",
    "pm4",
    "pm10",
    "co2",
    "humidity",
    "temp",
    "voc",
    "nox",
    "pressure_hpa",
)


def create_reading(
    device_id: int,
    reading_ts: str,
    pm1: Optional[float] = None,
    pm2_5: Optional[float] = None,
    pm4: Optional[float] = None,
    pm10: Optional[float] = None,
    co2: Optional[float] = None,
    humidity: Optional[float] = None,
    temp: Optional[float] = None,
    voc: Optional[float] = None,
    nox: Optional[float] = None,
    pressure_hpa: Optional[float] = None,
) -> Tuple[int, str]:
    """
    Create a new Sentinel reading record.

    Args:
        device_id (int): ID of the Sentinel device
        reading_ts (str): Timestamp of the reading (naive UTC ISO)
        pm1, pm2_5, pm4, pm10 (float, optional): Particulate matter in ug/m3
        co2 (float, optional): CO2 in ppm
        humidity (float, optional): Relative humidity in %
        temp (float, optional): Temperature in Celsius
        voc, nox (float, optional): Sensirion gas indices (1-500)
        pressure_hpa (float, optional): Barometric pressure in hPa

    Returns:
        Tuple[int, str]: Tuple of device_id and reading_ts of the newly created reading
    """
    query = """
    INSERT INTO readings_sentinel (device_id, reading_ts, pm1, pm2_5, pm4, pm10,
                                   co2, humidity, temp, voc, nox, pressure_hpa)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    execute_insert(
        query,
        (
            device_id,
            reading_ts,
            pm1,
            pm2_5,
            pm4,
            pm10,
            co2,
            humidity,
            temp,
            voc,
            nox,
            pressure_hpa,
        ),
    )
    return (device_id, reading_ts)


def get_device_readings(
    device_id: int,
    limit: int = 100,
    start_ts: Optional[str] = None,
    end_ts: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get readings for a specific Sentinel device with optional time range filtering.

    Args:
        device_id (int): ID of the Sentinel device
        limit (int, optional): Maximum number of readings to return
        start_ts (str, optional): Start timestamp for filtering
        end_ts (str, optional): End timestamp for filtering

    Returns:
        List[Dict[str, Any]]: List of reading records, newest first
    """
    query = "SELECT * FROM readings_sentinel WHERE device_id = ?"
    params = [device_id]

    if start_ts:
        query += " AND reading_ts >= ?"
        params.append(start_ts)

    if end_ts:
        query += " AND reading_ts <= ?"
        params.append(end_ts)

    query += " ORDER BY reading_ts DESC LIMIT ?"
    params.append(limit)

    return execute_query(query, tuple(params))


def delete_device_readings(
    device_id: int, start_ts: Optional[str] = None, end_ts: Optional[str] = None
) -> int:
    """
    Delete readings for a specific Sentinel device with optional time range filtering.

    Args:
        device_id (int): ID of the Sentinel device
        start_ts (str, optional): Start timestamp for filtering
        end_ts (str, optional): End timestamp for filtering

    Returns:
        int: Number of rows affected
    """
    query = "DELETE FROM readings_sentinel WHERE device_id = ?"
    params = [device_id]

    if start_ts:
        query += " AND reading_ts >= ?"
        params.append(start_ts)

    if end_ts:
        query += " AND reading_ts <= ?"
        params.append(end_ts)

    return execute_update(query, tuple(params))


def get_latest_reading(device_id: int) -> Optional[Dict[str, Any]]:
    """
    Get the most recent reading for a Sentinel device.

    Args:
        device_id (int): ID of the Sentinel device

    Returns:
        Optional[Dict[str, Any]]: Latest reading data or None if no readings exist
    """
    query = """
    SELECT * FROM readings_sentinel
    WHERE device_id = ?
    ORDER BY reading_ts DESC
    LIMIT 1
    """
    results = execute_query(query, (device_id,))
    return results[0] if results else None
