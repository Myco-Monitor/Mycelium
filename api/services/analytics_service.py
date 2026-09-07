"""
Analytics Service for Mycelium

This module provides the readings and harvest queries plus the per-metric
statistics behind the Analytics page.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
import statistics

from storage.db_utils import execute_query


@dataclass
class EnvironmentalStats:
    """Statistics for environmental data over a period.

    Every metric is computed independently and is None when the readings
    carry no value for it (a Sentinel reports null for an unavailable
    channel; a Spore never reports PM2.5).
    """

    co2_mean: Optional[float]
    co2_min: Optional[float]
    co2_max: Optional[float]
    co2_std: Optional[float]
    temp_mean: Optional[float]
    temp_min: Optional[float]
    temp_max: Optional[float]
    temp_std: Optional[float]
    humidity_mean: Optional[float]
    humidity_min: Optional[float]
    humidity_max: Optional[float]
    humidity_std: Optional[float]
    data_points: int
    days: int
    pm25_mean: Optional[float] = None
    pm25_min: Optional[float] = None
    pm25_max: Optional[float] = None


def _end_of_day(end_date: str) -> str:
    """Widen a bare YYYY-MM-DD end bound to include that whole day.

    reading_ts is stored via datetime.isoformat() ("YYYY-MM-DDT..."). The range
    filters compare as strings, and a bare date (or a space-separated suffix)
    sorts BEFORE every 'T'-separated timestamp of that date — silently dropping
    the end day from `<= ?` filters. Full timestamps pass through unchanged.
    """
    if end_date and len(end_date) == 10:
        return end_date + "T23:59:59.999999"
    return end_date


class AnalyticsService:
    """
    Service for the Analytics page's historical environmental and harvest data.

    Provides methods for:
    - Spore and Sentinel readings over a period (per room or per device)
    - Per-metric statistics over a set of readings
    - Harvest records over a period
    """

    def __init__(self):
        self.logger = logging.getLogger("services.AnalyticsService")

    def get_readings_for_period(
        self,
        start_date: str,
        end_date: str,
        room_id: Optional[int] = None,
        device_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get environmental readings for a specified period.

        Args:
            start_date (str): Start date (YYYY-MM-DD or ISO format)
            end_date (str): End date (YYYY-MM-DD or ISO format)
            room_id (int, optional): Filter by room ID
            device_id (int, optional): Filter by specific device

        Returns:
            List[Dict]: List of reading records
        """
        query = """
        SELECT
            'spore' AS source,
            rs.device_id,
            rs.reading_ts as timestamp,
            rs.co2,
            rs.temp as temperature,
            rs.humidity,
            ds.device_name,
            ds.room_id,
            gr.room_name
        FROM readings_spore rs
        JOIN device_spore ds ON rs.device_id = ds.device_id
        LEFT JOIN grow_rooms gr ON ds.room_id = gr.room_id
        WHERE rs.reading_ts >= ? AND rs.reading_ts <= ?
        """
        params = [start_date, _end_of_day(end_date)]

        if room_id is not None:
            query += " AND ds.room_id = ?"
            params.append(room_id)

        if device_id is not None:
            query += " AND rs.device_id = ?"
            params.append(device_id)

        query += " ORDER BY rs.reading_ts ASC"

        return execute_query(query, tuple(params))

    def get_sentinel_readings_for_period(
        self,
        start_date: str,
        end_date: str,
        room_id: Optional[int] = None,
        device_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get Sentinel readings for a specified period.

        Same row shape as get_readings_for_period (source, device_id,
        timestamp, co2, temperature, humidity, device_name, room_id,
        room_name) plus the Sentinel-only channels pm1, pm2_5, pm4, pm10,
        voc, nox and pressure_hpa. Unavailable channels are None.

        Args:
            start_date (str): Start date (YYYY-MM-DD or ISO format)
            end_date (str): End date (YYYY-MM-DD or ISO format)
            room_id (int, optional): Filter by room ID
            device_id (int, optional): Filter by specific device

        Returns:
            List[Dict]: List of reading records
        """
        query = """
        SELECT
            'sentinel' AS source,
            rsn.device_id,
            rsn.reading_ts as timestamp,
            rsn.co2,
            rsn.temp as temperature,
            rsn.humidity,
            rsn.pm1,
            rsn.pm2_5,
            rsn.pm4,
            rsn.pm10,
            rsn.voc,
            rsn.nox,
            rsn.pressure_hpa,
            dsn.device_name,
            dsn.room_id,
            gr.room_name
        FROM readings_sentinel rsn
        JOIN device_sentinel dsn ON rsn.device_id = dsn.device_id
        LEFT JOIN grow_rooms gr ON dsn.room_id = gr.room_id
        WHERE rsn.reading_ts >= ? AND rsn.reading_ts <= ?
        """
        params = [start_date, _end_of_day(end_date)]

        if room_id is not None:
            query += " AND dsn.room_id = ?"
            params.append(room_id)

        if device_id is not None:
            query += " AND rsn.device_id = ?"
            params.append(device_id)

        query += " ORDER BY rsn.reading_ts ASC"

        return execute_query(query, tuple(params))

    def calculate_environmental_stats(
        self, readings: List[Dict[str, Any]]
    ) -> Optional[EnvironmentalStats]:
        """
        Calculate statistics from a list of readings.

        Args:
            readings (List[Dict]): List of reading records

        Returns:
            EnvironmentalStats: Calculated statistics
        """
        if not readings:
            return None

        def _summary(key):
            """(mean, min, max, std) for one metric, or four Nones if absent."""
            values = [r[key] for r in readings if r.get(key) is not None]
            if not values:
                return None, None, None, None
            std = statistics.stdev(values) if len(values) > 1 else 0
            return statistics.mean(values), min(values), max(values), std

        co2 = _summary("co2")
        temp = _summary("temperature")
        humidity = _summary("humidity")
        pm25 = _summary("pm2_5")

        # Calculate days covered
        try:
            timestamps = [r["timestamp"] for r in readings if r.get("timestamp")]
            if timestamps:
                first = datetime.fromisoformat(timestamps[0].replace("Z", "+00:00"))
                last = datetime.fromisoformat(timestamps[-1].replace("Z", "+00:00"))
                days = max(1, (last - first).days)
            else:
                days = 1
        except Exception:
            days = 1

        return EnvironmentalStats(
            co2_mean=co2[0],
            co2_min=co2[1],
            co2_max=co2[2],
            co2_std=co2[3],
            temp_mean=temp[0],
            temp_min=temp[1],
            temp_max=temp[2],
            temp_std=temp[3],
            humidity_mean=humidity[0],
            humidity_min=humidity[1],
            humidity_max=humidity[2],
            humidity_std=humidity[3],
            data_points=len(readings),
            days=days,
            pm25_mean=pm25[0],
            pm25_min=pm25[1],
            pm25_max=pm25[2],
        )

    def get_harvests_for_period(
        self, start_date: str, end_date: str, room_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get harvest records for a period.

        Args:
            start_date (str): Start date
            end_date (str): End date
            room_id (int, optional): Filter by room ID

        Returns:
            List[Dict]: List of harvest records
        """
        query = """
        SELECT
            h.harvest_id,
            h.harvest_ts as harvest_date,
            h.total_wt as yield_weight,
            h.trimmed_wt,
            h.bulk_id
        FROM harvest h
        WHERE h.harvest_ts >= ? AND h.harvest_ts <= ?
        """
        params = [start_date, _end_of_day(end_date)]

        query += " ORDER BY h.harvest_ts ASC"

        return execute_query(query, tuple(params))

    def get_rooms(self) -> List[Dict[str, Any]]:
        """
        Get all grow rooms.

        Returns:
            List[Dict]: List of room records
        """
        query = """
        SELECT room_id, room_name, farm_id
        FROM grow_rooms
        WHERE active = 1
        ORDER BY room_name
        """
        return execute_query(query, ())

    def get_date_range(
        self, room_id: Optional[int] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """Get the date range of available data across Spore and Sentinel readings."""
        queries = [
            (
                "SELECT MIN(rs.reading_ts) as min_date, MAX(rs.reading_ts) as max_date"
                " FROM readings_spore rs"
                " JOIN device_spore ds ON rs.device_id = ds.device_id",
                "ds",
            ),
            (
                "SELECT MIN(rsn.reading_ts) as min_date, MAX(rsn.reading_ts) as max_date"
                " FROM readings_sentinel rsn"
                " JOIN device_sentinel dsn ON rsn.device_id = dsn.device_id",
                "dsn",
            ),
        ]

        mins, maxs = [], []
        for query, alias in queries:
            params = []
            if room_id is not None:
                query += f" WHERE {alias}.room_id = ?"
                params.append(room_id)
            result = execute_query(query, tuple(params))
            if result and result[0]["min_date"]:
                mins.append(result[0]["min_date"])
                maxs.append(result[0]["max_date"])

        if mins:
            return min(mins), max(maxs)
        return None, None
