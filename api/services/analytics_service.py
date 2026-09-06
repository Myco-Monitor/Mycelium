"""
Analytics Service for Mycelium

This module provides data aggregation and analysis functions for historical
environmental data, harvest correlations, and production insights.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
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
    pm25_max: Optional[float] = None


# EPA 2024 PM2.5 24-hour breakpoints (ug/m3): the top of the "Good" band and
# the top of "Moderate". Kept in step with PM25_AQI_BANDS in web_ui.format,
# which owns the full band table for display.
PM25_GOOD_MAX = 9.0
PM25_MODERATE_MAX = 35.4


@dataclass
class Insight:
    """An automated insight from data analysis."""

    type: str  # 'success', 'warning', 'info', 'danger'
    title: str
    message: str
    metric: str
    action: str


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
    Service for analyzing historical environmental and production data.

    Provides methods for:
    - Environmental trend analysis
    - Harvest correlation analysis
    - Grow cycle comparison
    - Automated insight generation
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

    def get_daily_aggregates(
        self, start_date: str, end_date: str, room_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get daily aggregated readings for a period.

        Args:
            start_date (str): Start date
            end_date (str): End date
            room_id (int, optional): Filter by room ID

        Returns:
            List[Dict]: List of daily aggregate records
        """
        query = """
        SELECT
            DATE(rs.reading_ts) as date,
            ds.room_id,
            gr.room_name,
            AVG(rs.co2) as avg_co2,
            MIN(rs.co2) as min_co2,
            MAX(rs.co2) as max_co2,
            AVG(rs.temp) as avg_temp,
            MIN(rs.temp) as min_temp,
            MAX(rs.temp) as max_temp,
            AVG(rs.humidity) as avg_humidity,
            MIN(rs.humidity) as min_humidity,
            MAX(rs.humidity) as max_humidity,
            COUNT(*) as reading_count
        FROM readings_spore rs
        JOIN device_spore ds ON rs.device_id = ds.device_id
        LEFT JOIN grow_rooms gr ON ds.room_id = gr.room_id
        WHERE rs.reading_ts >= ? AND rs.reading_ts <= ?
        """
        params = [start_date, _end_of_day(end_date)]

        if room_id is not None:
            query += " AND ds.room_id = ?"
            params.append(room_id)

        query += " GROUP BY DATE(rs.reading_ts), ds.room_id ORDER BY date ASC"

        return execute_query(query, tuple(params))

    def get_hourly_pattern(
        self, start_date: str, end_date: str, room_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get hourly aggregated patterns (average by hour of day).

        Args:
            start_date (str): Start date
            end_date (str): End date
            room_id (int, optional): Filter by room ID

        Returns:
            List[Dict]: List of hourly pattern records
        """
        query = """
        SELECT
            CAST(strftime('%H', rs.reading_ts) AS INTEGER) as hour,
            AVG(rs.co2) as avg_co2,
            AVG(rs.temp) as avg_temp,
            AVG(rs.humidity) as avg_humidity,
            COUNT(*) as reading_count
        FROM readings_spore rs
        JOIN device_spore ds ON rs.device_id = ds.device_id
        WHERE rs.reading_ts >= ? AND rs.reading_ts <= ?
        """
        params = [start_date, _end_of_day(end_date)]

        if room_id is not None:
            query += " AND ds.room_id = ?"
            params.append(room_id)

        query += " GROUP BY hour ORDER BY hour ASC"

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

    def calculate_harvest_correlations(
        self, start_date: str, end_date: str, room_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate correlations between environmental conditions and harvest yields.

        Args:
            start_date (str): Start date
            end_date (str): End date
            room_id (int, optional): Filter by room ID

        Returns:
            Dict: Correlation analysis results
        """
        harvests = self.get_harvests_for_period(start_date, end_date, room_id)

        if len(harvests) < 3:
            return {"error": "Need at least 3 harvests for correlation analysis"}

        results = {
            "harvest_count": len(harvests),
            "total_yield": sum(h.get("yield_weight", 0) or 0 for h in harvests),
            "avg_yield": 0,
            "correlations": {},
        }

        yields = []
        co2_avgs = []
        temp_avgs = []
        humidity_avgs = []

        # For each harvest, get environmental data from the preceding 30 days
        for harvest in harvests:
            if not harvest.get("yield_weight"):
                continue

            harvest_date = harvest.get("harvest_date", "")
            if not harvest_date:
                continue

            try:
                harvest_dt = datetime.fromisoformat(harvest_date.replace("Z", "+00:00"))
                start_dt = harvest_dt - timedelta(days=30)

                # Get environmental readings for the grow period
                env_data = self.get_readings_for_period(
                    start_dt.isoformat(),
                    harvest_dt.isoformat(),
                    room_id=harvest.get("room_id"),
                )

                if env_data:
                    co2_vals = [r["co2"] for r in env_data if r.get("co2")]
                    temp_vals = [
                        r["temperature"] for r in env_data if r.get("temperature")
                    ]
                    humidity_vals = [
                        r["humidity"] for r in env_data if r.get("humidity")
                    ]

                    if co2_vals and temp_vals and humidity_vals:
                        yields.append(harvest["yield_weight"])
                        co2_avgs.append(statistics.mean(co2_vals))
                        temp_avgs.append(statistics.mean(temp_vals))
                        humidity_avgs.append(statistics.mean(humidity_vals))
            except Exception as e:
                self.logger.warning(
                    f"Error processing harvest {harvest.get('harvest_id')}: {e}"
                )
                continue

        if len(yields) >= 3:
            results["avg_yield"] = statistics.mean(yields)

            # Calculate correlations using Pearson correlation coefficient
            results["correlations"]["co2"] = self._calculate_correlation(
                co2_avgs, yields
            )
            results["correlations"]["temperature"] = self._calculate_correlation(
                temp_avgs, yields
            )
            results["correlations"]["humidity"] = self._calculate_correlation(
                humidity_avgs, yields
            )

            # Find optimal ranges from top performers
            top_indices = sorted(
                range(len(yields)), key=lambda i: yields[i], reverse=True
            )[: max(1, len(yields) // 5)]

            if top_indices:
                results["optimal_ranges"] = {
                    "co2": (
                        min(co2_avgs[i] for i in top_indices),
                        max(co2_avgs[i] for i in top_indices),
                    ),
                    "temperature": (
                        min(temp_avgs[i] for i in top_indices),
                        max(temp_avgs[i] for i in top_indices),
                    ),
                    "humidity": (
                        min(humidity_avgs[i] for i in top_indices),
                        max(humidity_avgs[i] for i in top_indices),
                    ),
                }

        return results

    def _calculate_correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient between two lists."""
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        n = len(x)
        mean_x = sum(x) / n
        mean_y = sum(y) / n

        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denominator_x = sum((x[i] - mean_x) ** 2 for i in range(n))
        denominator_y = sum((y[i] - mean_y) ** 2 for i in range(n))

        if denominator_x == 0 or denominator_y == 0:
            return 0.0

        return numerator / ((denominator_x * denominator_y) ** 0.5)

    def generate_insights(
        self,
        start_date: str,
        end_date: str,
        room_id: Optional[int] = None,
        readings: Optional[List[Dict[str, Any]]] = None,
        stats: Optional[EnvironmentalStats] = None,
        harvests: Optional[List[Dict[str, Any]]] = None,
        source: str = "spore",
    ) -> List[Insight]:
        """
        Generate automated insights from historical data.

        Args:
            start_date (str): Start date
            end_date (str): End date
            room_id (int, optional): Filter by room ID
            readings (list, optional): Pre-fetched readings for the period;
                fetched here when None so the caller can avoid a second
                full-range query
            stats (EnvironmentalStats, optional): Pre-computed stats; computed
                from readings when None
            harvests (list, optional): Pre-fetched harvests; fetched here
                when None. Pass an empty list to skip harvest insights (the
                Analytics page adds them once via harvest_insights instead of
                once per device).
            source (str): 'spore' applies the grow-room rules (CO2 band,
                temperature stability, humidity); 'sentinel' applies the
                grower-space air-quality rules (PM2.5)

        Returns:
            List[Insight]: List of generated insights
        """
        insights = []

        # Get environmental data
        if readings is None:
            if source == "sentinel":
                readings = self.get_sentinel_readings_for_period(
                    start_date, end_date, room_id
                )
            else:
                readings = self.get_readings_for_period(start_date, end_date, room_id)
        if not readings:
            return insights

        if stats is None:
            stats = self.calculate_environmental_stats(readings)
        if not stats:
            return insights

        if source == "sentinel":
            insights.extend(self._sentinel_insights(readings, stats))
        else:
            insights.extend(self._spore_insights(readings, stats))

        # Data coverage (both sources poll on a roughly per-minute cadence,
        # so anything under one point an hour means a device was offline)
        if stats.data_points < stats.days * 24:
            coverage = (
                (stats.data_points / (stats.days * 24)) * 100 if stats.days > 0 else 0
            )
            if coverage < 50:
                insights.append(
                    Insight(
                        type="info",
                        title="Data Coverage Gap",
                        message=f"Only {coverage:.0f}% data coverage for the period. Some devices may be offline.",
                        metric="data",
                        action="Check device connectivity and polling intervals",
                    )
                )

        if harvests is None:
            harvests = self.get_harvests_for_period(start_date, end_date, room_id)
        insights.extend(self.harvest_insights(harvests))

        return insights

    def _sentinel_insights(
        self, readings: List[Dict[str, Any]], stats: EnvironmentalStats
    ) -> List[Insight]:
        """Grower-space air-quality rules for one Sentinel's readings."""
        insights = []
        if stats.pm25_mean is None:
            return insights

        if stats.pm25_mean <= PM25_GOOD_MAX:
            insights.append(
                Insight(
                    type="success",
                    title="Good Air Quality",
                    message=f"PM2.5 averaged {stats.pm25_mean:.1f} µg/m³, inside the EPA 'Good' band.",
                    metric="pm2.5",
                    action="No action needed",
                )
            )
        elif stats.pm25_mean <= PM25_MODERATE_MAX:
            insights.append(
                Insight(
                    type="info",
                    title="Moderate Air Quality",
                    message=f"PM2.5 averaged {stats.pm25_mean:.1f} µg/m³, in the EPA 'Moderate' band.",
                    metric="pm2.5",
                    action="Check filtration and spore load around the grow space",
                )
            )
        else:
            insights.append(
                Insight(
                    type="warning",
                    title="Poor Air Quality",
                    message=f"PM2.5 averaged {stats.pm25_mean:.1f} µg/m³, above the EPA 'Moderate' band.",
                    metric="pm2.5",
                    action="Improve filtration and ventilation; wear a respirator when handling",
                )
            )

        pm_values = [r["pm2_5"] for r in readings if r.get("pm2_5") is not None]
        high_count = sum(1 for v in pm_values if v > PM25_MODERATE_MAX)
        high_pct = (high_count / len(pm_values)) * 100 if pm_values else 0
        if high_pct > 10 and stats.pm25_mean <= PM25_MODERATE_MAX:
            insights.append(
                Insight(
                    type="warning",
                    title="Particulate Spikes",
                    message=f"PM2.5 exceeded {PM25_MODERATE_MAX} µg/m³ about {high_pct:.0f}% of the time (peak {stats.pm25_max:.0f} µg/m³).",
                    metric="pm2.5",
                    action="Match the spikes against tent openings, harvests and substrate work",
                )
            )

        return insights

    def _spore_insights(
        self, readings: List[Dict[str, Any]], stats: EnvironmentalStats
    ) -> List[Insight]:
        """Grow-room rules for one Spore's (or a room's) readings."""
        insights = []

        # Insight 1: CO2 levels analysis
        if stats.co2_mean is None:
            pass
        elif stats.co2_mean < 800:
            insights.append(
                Insight(
                    type="warning",
                    title="Low CO2 Levels",
                    message=f"Average CO2 is {stats.co2_mean:.0f} ppm. Consider increasing CO2 supplementation for optimal growth.",
                    metric="co2",
                    action="Increase CO2 supplementation or improve air circulation",
                )
            )
        elif stats.co2_mean > 2000:
            insights.append(
                Insight(
                    type="warning",
                    title="High CO2 Levels",
                    message=f"Average CO2 is {stats.co2_mean:.0f} ppm. This may indicate insufficient air exchange.",
                    metric="co2",
                    action="Increase fresh air exchange frequency",
                )
            )
        elif 1000 <= stats.co2_mean <= 1500:
            insights.append(
                Insight(
                    type="success",
                    title="Optimal CO2 Range",
                    message=f"CO2 averaging {stats.co2_mean:.0f} ppm is in the ideal range for mushroom growth.",
                    metric="co2",
                    action="Maintain current CO2 management",
                )
            )

        # Insight 2: Temperature stability
        if stats.temp_std is None:
            pass
        elif stats.temp_std > 3:
            insights.append(
                Insight(
                    type="warning",
                    title="Temperature Fluctuations",
                    message=f"Temperature varies by ±{stats.temp_std:.1f}°. Stable temperatures improve yields.",
                    metric="temperature",
                    action="Check HVAC system and insulation",
                )
            )
        elif stats.temp_std < 1:
            insights.append(
                Insight(
                    type="success",
                    title="Excellent Temperature Stability",
                    message=f"Temperature is very stable with only ±{stats.temp_std:.1f}° variation.",
                    metric="temperature",
                    action="Continue current temperature management",
                )
            )

        # Insight 3: Humidity patterns
        low_humidity_count = sum(
            1 for r in readings if r.get("humidity") and r["humidity"] < 60
        )
        low_humidity_pct = (low_humidity_count / len(readings)) * 100 if readings else 0

        if low_humidity_pct > 20:
            insights.append(
                Insight(
                    type="warning",
                    title="Low Humidity Periods",
                    message=f"Humidity drops below 60% about {low_humidity_pct:.0f}% of the time.",
                    metric="humidity",
                    action="Consider adding humidification during dry periods",
                )
            )

        high_humidity_count = sum(
            1 for r in readings if r.get("humidity") and r["humidity"] > 95
        )
        high_humidity_pct = (
            (high_humidity_count / len(readings)) * 100 if readings else 0
        )

        if high_humidity_pct > 30:
            insights.append(
                Insight(
                    type="info",
                    title="High Humidity Levels",
                    message=f"Humidity exceeds 95% about {high_humidity_pct:.0f}% of the time.",
                    metric="humidity",
                    action="Monitor for condensation and potential contamination",
                )
            )

        return insights

    def harvest_insights(self, harvests: List[Dict[str, Any]]) -> List[Insight]:
        """Yield-trend insight over a period's harvests (needs at least 3)."""
        insights = []
        if harvests and len(harvests) >= 3:
            yields = [h["yield_weight"] for h in harvests if h.get("yield_weight")]
            if len(yields) >= 3:
                # Sort by date and compare recent vs earlier
                recent_yields = yields[-3:]
                earlier_yields = yields[:3]

                recent_avg = statistics.mean(recent_yields)
                earlier_avg = statistics.mean(earlier_yields)

                if recent_avg > earlier_avg * 1.1:
                    improvement = ((recent_avg / earlier_avg) - 1) * 100
                    insights.append(
                        Insight(
                            type="success",
                            title="Improving Yields",
                            message=f"Recent harvests average {improvement:.0f}% higher than earlier ones.",
                            metric="yield",
                            action="Continue current practices",
                        )
                    )
                elif recent_avg < earlier_avg * 0.9:
                    decline = (1 - (recent_avg / earlier_avg)) * 100
                    insights.append(
                        Insight(
                            type="warning",
                            title="Declining Yields",
                            message=f"Recent harvests average {decline:.0f}% lower than earlier ones.",
                            metric="yield",
                            action="Review environmental conditions and substrate quality",
                        )
                    )

        return insights

    def get_reading_count(self, room_id: Optional[int] = None) -> int:
        """Get total reading count, optionally filtered by room."""
        query = """
        SELECT COUNT(*) as count
        FROM readings_spore rs
        JOIN device_spore ds ON rs.device_id = ds.device_id
        """
        params = []

        if room_id is not None:
            query += " WHERE ds.room_id = ?"
            params.append(room_id)

        result = execute_query(query, tuple(params))
        return result[0]["count"] if result else 0

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
