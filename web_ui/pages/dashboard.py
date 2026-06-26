"""
Main dashboard page for Mycelium NiceGUI application.

Provides a live, high-level overview of the farm: device online/offline
status, active alerts, per-room environment (CO2 / temp / humidity averaged
from the latest spore readings), and local weather.
"""

from datetime import datetime

from nicegui import ui, app
from web_ui.layout import page_layout
from web_ui.theme import get_colors

# Spores poll ~every 60s. Smooth each sensor over its last few readings to damp
# noise, and treat a sensor whose newest reading is older than the staleness
# window (5 missed polls) as offline — its data is shown as dashes, not a number.
SMOOTH_WINDOW = 5
STALE_AFTER_SECONDS = 300


@ui.page("/main")
@ui.page("/dashboard")
def dashboard_page():
    """Main dashboard with live farm overview."""
    user = app.storage.user
    if not user.get("user_id"):
        ui.navigate.to("/login")
        return

    page_layout("Dashboard")
    colors = get_colors()

    with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
        # Welcome header
        username = user.get("username", "User")
        ui.label(f"Welcome, {username}").classes("text-h4 q-mb-md")

        # Quick stats row (refreshable for live updates)
        dashboard_stats()

        # Per-room environment cards (refreshable)
        room_environment()

        # Auto-refresh stats + room environment every 30 seconds
        def _refresh_live():
            dashboard_stats.refresh()
            room_environment.refresh()

        ui.timer(30.0, _refresh_live)

        # Weather card (only renders if OWM credentials are configured)
        from web_ui.components.weather_card import weather_card

        weather_card(colors)

        # Pressure card (only renders if Hyphae devices exist)
        from web_ui.components.pressure_card import pressure_card

        pressure_card(colors)

        # Navigation cards — CSS grid for equal sizing
        ui.label("Quick Access").classes("text-h5 q-mt-lg q-mb-sm")

        with ui.element("div").style(
            "display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; width: 100%;"
        ):
            _nav_card(
                "Devices",
                "Manage and monitor all connected devices",
                "sensors",
                "/devices",
                colors,
            )
            _nav_card(
                "Farm Overview",
                "View farms, rooms, and device health",
                "agriculture",
                "/farms",
                colors,
            )
            _nav_card(
                "Alerts",
                "Configure alert rules and view history",
                "notifications",
                "/alerts",
                colors,
            )
            _nav_card(
                "Analytics",
                "Analyze historical sensor data",
                "analytics",
                "/analytics",
                colors,
            )
            _nav_card(
                "Business",
                "Track spawn, harvest, and sales",
                "business",
                "/business",
                colors,
            )
            _nav_card(
                "Settings",
                "User preferences and configuration",
                "settings",
                "/settings",
                colors,
            )


@ui.refreshable
def dashboard_stats():
    """Refreshable stat cards — auto-updated via ui.timer."""
    colors = get_colors()
    online, offline = _get_device_status_counts()
    with ui.row().classes("w-full gap-4 flex-wrap"):
        _stat_card("Online Devices", online, "wifi", colors)
        _stat_card("Offline Devices", offline, "wifi_off", colors)
        _stat_card("Active Alerts", _get_alert_count(), "warning", colors)


@ui.refreshable
def room_environment():
    """Per-room environment cards: averaged CO2 / temp / humidity per grow room."""
    colors = get_colors()
    rooms = _get_active_rooms()
    if not rooms:
        return

    ui.label("Room Conditions").classes("text-h5 q-mt-md q-mb-sm")
    temp_pref = _temp_pref()
    with ui.element("div").style(
        "display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; width: 100%;"
    ):
        for room in rooms:
            _room_card(room, temp_pref, colors)


def _room_card(room: dict, temp_pref: str, colors: dict):
    """Render one grow room with its averaged environment readings."""
    avg = _get_room_averages(room["room_id"])
    fresh = avg["fresh_count"] > 0

    with ui.card().classes("p-4").style("height: 100%;"):
        with ui.row().classes("items-center gap-2 q-mb-sm"):
            ui.icon("meeting_room", size="sm").style(f"color: {colors['primary']}")
            ui.label(room.get("room_name", "?")).classes(
                "text-subtitle1 text-weight-bold"
            )

        # When no sensor is reporting fresh data, dash every metric — we don't
        # know the room's state, so don't show a stale average as if it were live.
        if fresh:
            temp_value, temp_unit = _fmt_temp(avg["temp"], temp_pref)
            temp_display = _fmt_unit(temp_value, f"°{temp_unit}")
            co2_display = _fmt_metric(avg["co2"], " ppm", 0)
            humidity_display = _fmt_metric(avg["humidity"], "%", 0)
        else:
            co2_display = temp_display = humidity_display = "—"

        with ui.row().classes("w-full justify-around"):
            _env_stat("co2", "CO₂", co2_display)
            _env_stat("thermostat", "Temp", temp_display)
            _env_stat("water_drop", "Humidity", humidity_display)

        # Freshness / coverage footer
        _room_footer(avg)


def _room_footer(avg: dict):
    """Small muted line describing data age and how many sensors are reporting."""
    total = avg["total_count"]
    fresh_count = avg["fresh_count"]

    if total == 0:
        ui.label("No sensors assigned").classes("text-caption text-muted q-mt-sm")
        return

    if fresh_count == 0:
        ui.label("No recent data — sensors offline").classes(
            "text-caption text-negative q-mt-sm"
        )
        return

    parts = [f"Updated {_humanize_age(avg['age_seconds'])}"]
    if fresh_count < total:
        parts.append(f"{fresh_count}/{total} sensors reporting")
    ui.label(" • ".join(parts)).classes("text-caption text-muted q-mt-sm")


def _env_stat(icon: str, label: str, value: str):
    """Small environment stat cell inside a room card."""
    with ui.column().classes("items-center gap-0"):
        ui.icon(icon, size="xs").classes("text-muted")
        ui.label(value).classes("text-weight-bold")
        ui.label(label).classes("text-caption text-muted")


def _stat_card(label: str, value, icon: str, colors: dict):
    """Create a stat overview card."""
    with ui.card().classes("p-4 flex-1 min-w-48"):
        with ui.row().classes("items-center gap-2"):
            ui.icon(icon, size="sm").style(f"color: {colors['primary']}")
            ui.label(label).classes("text-subtitle2")
        ui.label(str(value)).classes("text-h4 q-mt-sm")


def _nav_card(title: str, description: str, icon: str, href: str, colors: dict):
    """Create a navigation card that fills its grid cell."""
    with (
        ui.card()
        .classes("p-4 cursor-pointer")
        .style("height: 100%;")
        .on("click", lambda href=href: ui.navigate.to(href))
    ):
        with ui.row().classes("items-center gap-3"):
            ui.icon(icon, size="md").style(f"color: {colors['primary']}")
            with ui.column().classes("gap-0"):
                ui.label(title).classes("text-subtitle1 text-weight-bold")
                ui.label(description).classes("text-caption text-muted")


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def _get_device_status_counts() -> tuple:
    """Return (online, offline) counts across all active Spore and Hyphae devices."""
    try:
        from storage.tables.device_spore import get_all_device_spore
        from storage.tables.device_hyphae import get_all_device_hyphae

        devices = list(get_all_device_spore()) + list(get_all_device_hyphae())
        online = sum(1 for d in devices if d.get("is_online"))
        return online, len(devices) - online
    except Exception:
        return 0, 0


def _get_alert_count() -> int:
    """Get count of active alerts."""
    try:
        from storage.tables.alert_history import get_active_alerts

        return len(get_active_alerts())
    except Exception:
        return 0


def _get_active_rooms() -> list:
    """Get all active grow rooms."""
    try:
        from storage.tables.grow_rooms import get_all_grow_rooms

        return get_all_grow_rooms(active_only=True)
    except Exception:
        return []


def _get_room_averages(room_id: int) -> dict:
    """Average CO2 / temp / humidity across the fresh Spores in a room.

    Each Spore is first smoothed over its last ``SMOOTH_WINDOW`` readings to damp
    sensor noise, then the per-Spore values are averaged across the room. A Spore
    whose newest reading is older than ``STALE_AFTER_SECONDS`` is treated as
    offline and excluded entirely (its metrics show as dashes upstream).

    Returns a dict with:
      - ``co2`` / ``temp`` / ``humidity``: room averages, or None if unavailable
      - ``fresh_count``: Spores contributing fresh data
      - ``total_count``: active Spores assigned to the room
      - ``age_seconds``: age of the newest contributing reading, or None
    """
    result = {
        "co2": None,
        "temp": None,
        "humidity": None,
        "fresh_count": 0,
        "total_count": 0,
        "age_seconds": None,
    }
    try:
        from storage.tables.device_spore import get_all_device_spore
        from storage.tables.readings_spore import get_device_readings

        spores = get_all_device_spore(room_id=room_id)
        result["total_count"] = len(spores)

        sums = {"co2": 0.0, "temp": 0.0, "humidity": 0.0}
        counts = {"co2": 0, "temp": 0, "humidity": 0}
        fresh_count = 0
        newest_age = None

        for spore in spores:
            rows = get_device_readings(spore["device_id"], limit=SMOOTH_WINDOW)
            if not rows:
                continue

            # rows are newest-first; gate on the most recent reading's age.
            age = _reading_age_seconds(rows[0].get("reading_ts"))
            if age is None or age > STALE_AFTER_SECONDS:
                continue

            # Smooth each metric over this Spore's recent readings, then fold the
            # per-Spore average into the room totals (equal weight per Spore).
            contributed = False
            for key in ("co2", "temp", "humidity"):
                values = [float(r[key]) for r in rows if r.get(key) is not None]
                if values:
                    sums[key] += sum(values) / len(values)
                    counts[key] += 1
                    contributed = True

            if contributed:
                fresh_count += 1
                if newest_age is None or age < newest_age:
                    newest_age = age

        for key in ("co2", "temp", "humidity"):
            if counts[key]:
                result[key] = sums[key] / counts[key]
        result["fresh_count"] = fresh_count
        result["age_seconds"] = newest_age
    except Exception:
        pass
    return result


def _reading_age_seconds(reading_ts) -> float | None:
    """Age in seconds of an ISO reading timestamp, or None if unparseable."""
    if not reading_ts:
        return None
    try:
        return (datetime.now() - datetime.fromisoformat(reading_ts)).total_seconds()
    except (ValueError, TypeError):
        return None


def _humanize_age(seconds) -> str:
    """Render an age in seconds as a compact 'just now' / 'Nm ago' / 'Nh ago'."""
    if seconds is None:
        return "unknown"
    seconds = int(seconds)
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def _temp_pref() -> str:
    """Return the current user's temperature unit preference ('C' or 'F')."""
    try:
        from storage.tables.user_settings import get_user_setting

        uid = app.storage.user.get("user_id")
        info = get_user_setting(uid) if uid else None
        return (info.get("temp_pref") or "C") if info else "C"
    except Exception:
        return "C"


def _fmt_temp(celsius, pref: str, digits: int = 1):
    """Format a Celsius reading per the user's unit preference. Returns (value, unit)."""
    try:
        c = float(celsius)
    except (TypeError, ValueError):
        return "N/A", pref if pref in ("C", "F") else "C"
    if pref == "F":
        return f"{c * 9 / 5 + 32:.{digits}f}", "F"
    return f"{c:.{digits}f}", "C"


def _fmt_metric(value, suffix: str, digits: int) -> str:
    """Format an averaged metric value with a unit suffix, or '—' if missing."""
    if value is None:
        return "—"
    return f"{value:.{digits}f}{suffix}"


def _fmt_unit(value: str, unit: str) -> str:
    """Join a pre-formatted value with its unit, passing through 'N/A'."""
    if value == "N/A":
        return value
    return f"{value}{unit}"
