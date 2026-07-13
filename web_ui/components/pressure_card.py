"""
BMP581 pressure card component for the Mycelium dashboard.

Displays the latest barometric pressure reading from each Hyphae device.
Auto-refreshes every 5 minutes (aligned with the pressure polling interval).
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from nicegui import ui

from storage.tables.device_hyphae import get_all_device_hyphae
from storage.tables.readings_pressure import get_latest_pressure
from web_ui.format import fmt_time, to_user_dt

logger = logging.getLogger(__name__)

REFRESH_INTERVAL = 300  # 5 minutes, matches pressure polling default
# A reading older than this means the Hyphae isn't reporting, so we dash the
# value instead of showing a frozen number — same treatment the room-condition
# cards give stale sensors. Pressure publishes every ~REFRESH_INTERVAL and each
# successful poll stores a fresh row (dedup only collapses readings <60s apart),
# so age is a reliable liveness signal. Allow a couple of missed polls first.
STALE_AFTER_SECONDS = 900  # 3 missed pressure polls


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

        # Only when no device has ever reported — a fresh install waiting for
        # its first pressure poll. Devices that have data (fresh or stale) are
        # rendered per-row below.
        if not any(r["has_data"] for r in readings):
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
                    # Stale or never-reported: dash the value rather than show a
                    # number we can't vouch for as current.
                    if r["stale"]:
                        ui.label("—").classes("text-h6")
                        ui.icon("cloud_off", size="xs").style("color: #9e9e9e")
                    else:
                        ui.label(f"{r['pressure_hpa']} hPa").classes("text-h6")
                        healthy_icon = "check_circle" if r["healthy"] else "error"
                        healthy_color = "#388e3c" if r["healthy"] else "#d32f2f"
                        ui.icon(healthy_icon, size="xs").style(
                            f"color: {healthy_color}"
                        )

                if not r["has_data"]:
                    ui.label("No recent data — device offline").classes(
                        "text-caption text-negative"
                    )
                elif r["stale"]:
                    ui.label(f"Stale — last seen {r['timestamp']}").classes(
                        "text-caption text-negative"
                    )
                else:
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
    """Latest pressure reading per Hyphae device, with a staleness flag.

    Every device is included so an offline/never-reported Hyphae still shows a
    dashed row rather than silently vanishing. ``stale`` is True when the device
    has no reading or its newest reading is older than ``STALE_AFTER_SECONDS``.
    """
    readings = []
    for device in devices:
        device_id = device["device_id"]
        latest = get_latest_pressure(device_id)

        ts = ""
        age = None
        if latest:
            try:
                # reading_ts is naive UTC; age math in UTC, display in user tz
                dt = datetime.fromisoformat(latest["reading_ts"])
                local = to_user_dt(dt)
                ts = f"{fmt_time(dt)} {local.strftime('%b %d')}"
                age = (
                    datetime.now(timezone.utc).replace(tzinfo=None) - dt
                ).total_seconds()
            except (ValueError, TypeError):
                ts = str(latest.get("reading_ts", ""))

        stale = age is None or age > STALE_AFTER_SECONDS

        readings.append(
            {
                "device_name": device.get("device_name", f"Hyphae #{device_id}"),
                "pressure_hpa": latest["pressure_hpa"] if latest else None,
                "source": latest.get("source", "BMP581") if latest else "BMP581",
                "healthy": bool(latest.get("healthy", 0)) if latest else False,
                "timestamp": ts,
                "has_data": latest is not None,
                "stale": stale,
            }
        )
    return readings
