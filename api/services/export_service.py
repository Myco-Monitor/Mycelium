"""
Export Service for Mycelium

This module provides data export functionality for analytics,
supporting CSV and Excel formats with multiple sheets.
"""

import csv
import logging
from io import BytesIO, StringIO
from typing import Optional
from datetime import datetime

from api.services.analytics_service import AnalyticsService


class ExportService:
    """Service for exporting analytics and production data."""

    def __init__(self):
        self.logger = logging.getLogger("services.ExportService")
        self.analytics = AnalyticsService()

    def export_readings_csv(
        self, start_date: str, end_date: str, room_id: Optional[int] = None
    ) -> str:
        """
        Export readings to CSV format.

        Args:
            start_date (str): Start date
            end_date (str): End date
            room_id (int, optional): Filter by room ID

        Returns:
            str: CSV content as string
        """
        readings = self.analytics.get_readings_for_period(start_date, end_date, room_id)

        if not readings:
            return ""

        output = StringIO()
        fieldnames = [
            "timestamp",
            "device_name",
            "room_name",
            "co2",
            "temperature",
            "humidity",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(readings)

        return output.getvalue()

    def export_daily_summary_csv(
        self, start_date: str, end_date: str, room_id: Optional[int] = None
    ) -> str:
        """
        Export daily aggregated data to CSV.

        Args:
            start_date (str): Start date
            end_date (str): End date
            room_id (int, optional): Filter by room ID

        Returns:
            str: CSV content as string
        """
        daily_data = self.analytics.get_daily_aggregates(start_date, end_date, room_id)

        if not daily_data:
            return ""

        output = StringIO()
        fieldnames = [
            "date",
            "room_name",
            "avg_co2",
            "min_co2",
            "max_co2",
            "avg_temp",
            "min_temp",
            "max_temp",
            "avg_humidity",
            "min_humidity",
            "max_humidity",
            "reading_count",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(daily_data)

        return output.getvalue()

    def export_harvests_csv(
        self, start_date: str, end_date: str, room_id: Optional[int] = None
    ) -> str:
        """
        Export harvest data to CSV.

        Args:
            start_date (str): Start date
            end_date (str): End date
            room_id (int, optional): Filter by room ID

        Returns:
            str: CSV content as string
        """
        harvests = self.analytics.get_harvests_for_period(start_date, end_date, room_id)

        if not harvests:
            return ""

        output = StringIO()
        fieldnames = [
            "harvest_id",
            "harvest_date",
            "yield_weight",
            "trimmed_wt",
            "bulk_name",
            "room_name",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(harvests)

        return output.getvalue()

    def export_readings_excel(
        self, start_date: str, end_date: str, room_id: Optional[int] = None
    ) -> bytes:
        """
        Export readings to Excel with multiple sheets.

        Args:
            start_date (str): Start date
            end_date (str): End date
            room_id (int, optional): Filter by room ID

        Returns:
            bytes: Excel file content
        """
        try:
            import pandas as pd
        except ImportError:
            self.logger.error("pandas required for Excel export")
            return b""

        import importlib.util

        if importlib.util.find_spec("openpyxl") is None:
            self.logger.error("openpyxl required for Excel export")
            return b""

        output = BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # Raw readings sheet
            readings = self.analytics.get_readings_for_period(
                start_date, end_date, room_id
            )
            if readings:
                df = pd.DataFrame(readings)
                df = df[
                    [
                        "timestamp",
                        "device_name",
                        "room_name",
                        "co2",
                        "temperature",
                        "humidity",
                    ]
                ]
                df.to_excel(writer, sheet_name="Readings", index=False)

            # Daily averages sheet
            daily_data = self.analytics.get_daily_aggregates(
                start_date, end_date, room_id
            )
            if daily_data:
                daily_df = pd.DataFrame(daily_data)
                daily_df.to_excel(writer, sheet_name="Daily Averages", index=False)

            # Statistics sheet
            if readings:
                stats = self.analytics.calculate_environmental_stats(readings)
                if stats:
                    stats_data = [
                        {
                            "Metric": "CO2",
                            "Mean": f"{stats.co2_mean:.1f}",
                            "Std Dev": f"{stats.co2_std:.1f}",
                            "Min": f"{stats.co2_min:.1f}",
                            "Max": f"{stats.co2_max:.1f}",
                        },
                        {
                            "Metric": "Temperature",
                            "Mean": f"{stats.temp_mean:.1f}",
                            "Std Dev": f"{stats.temp_std:.1f}",
                            "Min": f"{stats.temp_min:.1f}",
                            "Max": f"{stats.temp_max:.1f}",
                        },
                        {
                            "Metric": "Humidity",
                            "Mean": f"{stats.humidity_mean:.1f}",
                            "Std Dev": f"{stats.humidity_std:.1f}",
                            "Min": f"{stats.humidity_min:.1f}",
                            "Max": f"{stats.humidity_max:.1f}",
                        },
                    ]
                    stats_df = pd.DataFrame(stats_data)
                    stats_df.to_excel(writer, sheet_name="Statistics", index=False)

            # Harvests sheet
            harvests = self.analytics.get_harvests_for_period(
                start_date, end_date, room_id
            )
            if harvests:
                harvest_df = pd.DataFrame(harvests)
                harvest_df = harvest_df[
                    [
                        "harvest_id",
                        "harvest_date",
                        "yield_weight",
                        "trimmed_wt",
                        "bulk_name",
                        "room_name",
                    ]
                ]
                harvest_df.to_excel(writer, sheet_name="Harvests", index=False)

            # Hourly patterns sheet
            hourly_data = self.analytics.get_hourly_pattern(
                start_date, end_date, room_id
            )
            if hourly_data:
                hourly_df = pd.DataFrame(hourly_data)
                hourly_df.to_excel(writer, sheet_name="Hourly Patterns", index=False)

        output.seek(0)
        return output.read()

    def export_production_report(
        self, start_date: str, end_date: str, room_id: Optional[int] = None
    ) -> bytes:
        """
        Export a comprehensive production report.

        Args:
            start_date (str): Start date
            end_date (str): End date
            room_id (int, optional): Filter by room ID

        Returns:
            bytes: Excel file content with production report
        """
        try:
            import pandas as pd
        except ImportError:
            self.logger.error("pandas required for report export")
            return b""

        output = BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # Summary sheet
            readings = self.analytics.get_readings_for_period(
                start_date, end_date, room_id
            )
            harvests = self.analytics.get_harvests_for_period(
                start_date, end_date, room_id
            )

            summary_data = [
                {
                    "Report Period": f"{start_date} to {end_date}",
                    "Total Readings": len(readings) if readings else 0,
                    "Total Harvests": len(harvests) if harvests else 0,
                    "Total Yield (kg)": sum(
                        h.get("yield_weight", 0) or 0 for h in harvests
                    )
                    if harvests
                    else 0,
                    "Generated": datetime.now().isoformat(),
                }
            ]
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name="Summary", index=False)

            # Environmental stats
            if readings:
                stats = self.analytics.calculate_environmental_stats(readings)
                if stats:
                    env_data = [
                        {
                            "Metric": "CO2 (ppm)",
                            "Average": f"{stats.co2_mean:.0f}",
                            "Range": f"{stats.co2_min:.0f} - {stats.co2_max:.0f}",
                            "Stability (Std Dev)": f"{stats.co2_std:.1f}",
                        },
                        {
                            "Metric": "Temperature (°C)",
                            "Average": f"{stats.temp_mean:.1f}",
                            "Range": f"{stats.temp_min:.1f} - {stats.temp_max:.1f}",
                            "Stability (Std Dev)": f"{stats.temp_std:.1f}",
                        },
                        {
                            "Metric": "Humidity (%)",
                            "Average": f"{stats.humidity_mean:.1f}",
                            "Range": f"{stats.humidity_min:.1f} - {stats.humidity_max:.1f}",
                            "Stability (Std Dev)": f"{stats.humidity_std:.1f}",
                        },
                    ]
                    env_df = pd.DataFrame(env_data)
                    env_df.to_excel(writer, sheet_name="Environmental", index=False)

            # Harvest details
            if harvests:
                harvest_df = pd.DataFrame(harvests)
                harvest_df = harvest_df[
                    [
                        "harvest_date",
                        "yield_weight",
                        "trimmed_wt",
                        "bulk_name",
                        "room_name",
                    ]
                ]
                harvest_df.to_excel(writer, sheet_name="Harvest Details", index=False)

            # Insights
            insights = self.analytics.generate_insights(start_date, end_date, room_id)
            if insights:
                insight_data = [
                    {
                        "Type": i.type.upper(),
                        "Title": i.title,
                        "Message": i.message,
                        "Action": i.action,
                    }
                    for i in insights
                ]
                insight_df = pd.DataFrame(insight_data)
                insight_df.to_excel(writer, sheet_name="Insights", index=False)

        output.seek(0)
        return output.read()

    def get_export_filename(
        self, export_type: str, start_date: str, end_date: str, extension: str = "csv"
    ) -> str:
        """
        Generate a standardized export filename.

        Args:
            export_type (str): Type of export (readings, daily, harvests, report)
            start_date (str): Start date
            end_date (str): End date
            extension (str): File extension

        Returns:
            str: Generated filename
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return (
            f"mycelium_{export_type}_{start_date}_to_{end_date}_{timestamp}.{extension}"
        )
