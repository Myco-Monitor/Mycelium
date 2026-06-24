"""
BMP581 pressure card component for the Mycelium dashboard.

Displays the latest barometric pressure reading from each Hyphae device.
Auto-refreshes every 5 minutes (aligned with the pressure polling interval).
"""

import logging
from datetime import datetime
from typing import List, Dict, Any

from nicegui import ui

from storage.tables.device_hyphae import get_all_device_hyphae
from storage.tables.readings_pressure import get_latest_pressure
from web_ui.format import fmt_time

logger = logging.getLogger(__name__)

REFRESH_INTERVAL = 300  # 5 minutes, matches pressure polling default


def pressure_card(colors: dict):
    """
    Render the BMP581 pressure card on the dashboard.
    Only renders if at least one Hyphae device exists.
    """
    devices = get_all_device_hyphae()
    if not devices:
        return

    @ui.refreshable
    def pressure_content():
        readings = _get_pressure_readings(devices)

        if not readings:
            ui.label(
                "No pressure data yet. Waiting for Hyphae devices to report."
            ).classes("text-caption text-muted")
            return

        for r in readings:
            with ui.row().classes("w-full items-center justify-between gap-2"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("speed", size="xs").style(f"color: {colors['primary']}")
                    ui.label(r["device_name"]).classes("text-weight-bold")

                with ui.row().classes("items-center gap-4"):
                    ui.label(f"{r['pressure_hpa']} hPa").classes("text-h6")
                    healthy_icon = "check_circle" if r["healthy"] else "error"
                    healthy_color = "#388e3c" if r["healthy"] else "#d32f2f"
                    ui.icon(healthy_icon, size="xs").style(f"color: {healthy_color}")

                ui.label(f"Source: {r['source']}  |  {r['timestamp']}").classes(
                    "text-caption text-muted"
                )

            if r != readings[-1]:
                ui.separator().classes("q-my-xs")

    with ui.card().classes("w-full p-4"):
        with ui.row().classes("w-full items-center gap-2 q-mb-sm"):
            ui.icon("thermostat", size="sm").style(f"color: {colors['primary']}")
            ui.label("Grow Room Pressure").classes("text-h6")

        pressure_content()

    ui.timer(REFRESH_INTERVAL, lambda: pressure_content.refresh())


def _get_pressure_readings(devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Get the latest pressure reading for each Hyphae device."""
    readings = []
    for device in devices:
        device_id = device["device_id"]
        latest = get_latest_pressure(device_id)
        if latest:
            try:
                dt = datetime.fromisoformat(latest["reading_ts"])
                ts = f"{fmt_time(dt)} {dt.strftime('%b %d')}"
            except (ValueError, TypeError):
                ts = str(latest.get("reading_ts", ""))

            readings.append(
                {
                    "device_name": device.get("device_name", f"Hyphae #{device_id}"),
                    "pressure_hpa": latest["pressure_hpa"],
                    "source": latest.get("source", "BMP581"),
                    "healthy": bool(latest.get("healthy", 0)),
                    "timestamp": ts,
                }
            )
    return readings
