"""
Main dashboard page for Mycelium NiceGUI application.

Provides a live, high-level overview of the farm: device online/offline
status, active alerts, per-tent environment (each Hyphae and its linked
Spores: averaged CO2 / temp / humidity, barometric pressure, and per-Spore
snapshots), and local weather.
"""

from datetime import datetime, timezone

from nicegui import ui, app
from web_ui.layout import page_layout
from web_ui.theme import get_colors

# Spores poll ~every 60s. Smooth each sensor over its last few readings to damp
# noise, and treat a sensor whose newest reading is older than the staleness
# window (5 missed polls) as offline — its data is shown as dashes, not a number.
SMOOTH_WINDOW = 5
STALE_AFTER_SECONDS = 300

# A pressure reading older than this means the Hyphae isn't reporting, so we
# dash the value instead of showing a frozen number. Pressure publishes every
# ~5 minutes and each successful poll stores a fresh row (dedup only collapses
# readings <60s apart), so age is a reliable liveness signal. Allow a couple
# of missed polls first.
PRESSURE_STALE_AFTER_SECONDS = 900  # 3 missed pressure polls


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

        # Per-tent environment cards (refreshable)
        tent_environment()

        # Auto-refresh stats + tent environment every 30 seconds
        def _refresh_live():
            dashboard_stats.refresh()
            tent_environment.refresh()

        ui.timer(30.0, _refresh_live)

        # Weather card (only renders if OWM credentials are configured)
        from web_ui.components.weather_card import weather_card

        weather_card(colors)

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
def tent_environment():
    """Per-tent cards: each Hyphae with its linked Spores (plus per-room cards
    of unlinked Spores), showing averages, pressure, and per-Spore snapshots."""
    colors = get_colors()
    tents = _get_tent_data()
    if not tents:
        return

    ui.label("Grow Tent Conditions").classes("text-h5 q-mt-md q-mb-sm")
    temp_pref = _temp_pref()
    for tent in tents:
        _tent_card(tent, temp_pref, colors)


def _tent_card(tent: dict, temp_pref: str, colors: dict):
    """Render one grow tent as a full-width card with three columns."""
    with ui.card().classes("w-full p-4"):
        with ui.row().classes("items-center gap-2 q-mb-sm"):
            ui.icon(tent["icon"], size="sm").style(f"color: {colors['primary']}")
            ui.label(tent["title"]).classes("text-subtitle1 text-weight-bold")
            ui.label(tent["room_caption"]).classes("text-caption text-muted")

        with ui.element("div").style(
            "display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; width: 100%;"
        ):
            _tent_averages_col(tent, temp_pref)
            _tent_pressure_col(tent)
            _tent_snapshot_col(tent, temp_pref)


def _tent_averages_col(tent: dict, temp_pref: str):
    """Averaged CO2 / temp / humidity across the tent's fresh Spores."""
    avg = tent["avg"]
    with ui.column().classes("gap-1 min-w-0"):
        ui.label("Averages").classes("text-caption text-muted")

        # When no sensor is reporting fresh data, dash every metric — we don't
        # know the tent's state, so don't show a stale average as if it were live.
        if avg["fresh_count"] > 0:
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
        total = avg["total_count"]
        fresh_count = avg["fresh_count"]
        if total == 0:
            ui.label("No sensors linked").classes("text-caption text-muted q-mt-sm")
        elif fresh_count == 0:
            ui.label("No recent data — sensors offline").classes(
                "text-caption text-negative q-mt-sm"
            )
        else:
            parts = [f"Updated {_humanize_age(avg['age_seconds'])}"]
            if fresh_count < total:
                parts.append(f"{fresh_count}/{total} sensors reporting")
            ui.label(" • ".join(parts)).classes("text-caption text-muted q-mt-sm")


def _tent_pressure_col(tent: dict):
    """Latest barometric pressure from the tent's Hyphae, with staleness states."""
    pressure = tent["pressure"]
    with ui.column().classes("gap-1 min-w-0"):
        ui.label("Pressure").classes("text-caption text-muted")

        if pressure is None:
            ui.label("—").classes("text-h6")
            ui.label("No Hyphae linked").classes("text-caption text-muted")
            return

        with ui.row().classes("items-center gap-2"):
            # Stale or never-reported: dash the value rather than show a
            # number we can't vouch for as current.
            if pressure["stale"]:
                ui.label("—").classes("text-h6")
                ui.icon("cloud_off", size="xs").style("color: #9e9e9e")
            else:
                ui.label(f"{pressure['pressure_hpa']} hPa").classes("text-h6")
                healthy_icon = "check_circle" if pressure["healthy"] else "error"
                healthy_color = "#388e3c" if pressure["healthy"] else "#d32f2f"
                ui.icon(healthy_icon, size="xs").style(f"color: {healthy_color}")

        if not pressure["has_data"]:
            ui.label("No recent data — device offline").classes(
                "text-caption text-negative"
            )
        elif pressure["stale"]:
            ui.label(f"Stale — last seen {pressure['timestamp']}").classes(
                "text-caption text-negative"
            )
        else:
            ui.label(
                f"Source: {pressure['source']}  |  {pressure['timestamp']}"
            ).classes("text-caption text-muted")


def _tent_snapshot_col(tent: dict, temp_pref: str):
    """Latest reading per Spore in the tent, as of the last refresh."""
    spores = tent["avg"]["spores"]
    with ui.column().classes("gap-1 min-w-0"):
        ui.label("Sensors").classes("text-caption text-muted")

        if not spores:
            ui.label("No sensors linked").classes("text-caption text-muted")
            return

        for spore in spores:
            with ui.column().classes("gap-0 q-mb-xs"):
                ui.label(spore["name"]).classes("text-caption text-weight-bold")
                if not spore["has_data"]:
                    ui.label("—").classes("text-body2")
                    ui.label("no data").classes("text-caption text-muted")
                    continue

                if spore["temp"] is None:
                    temp_display = "—"
                else:
                    temp_value, temp_unit = _fmt_temp(spore["temp"], temp_pref)
                    temp_display = _fmt_unit(temp_value, f"°{temp_unit}")
                line = " · ".join(
                    (
                        temp_display,
                        _fmt_metric(spore["humidity"], "%", 0),
                        _fmt_metric(spore["co2"], " ppm", 0),
                    )
                )
                ui.label(line).classes("text-body2")

                # The snapshot stays visible when stale — the age label below
                # says how old it is, going red once the Spore stops reporting.
                stale = (
                    spore["age_seconds"] is None
                    or spore["age_seconds"] > STALE_AFTER_SECONDS
                )
                ui.label(_humanize_age(spore["age_seconds"])).classes(
                    "text-caption text-negative" if stale else "text-caption text-muted"
                )


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


def _get_tent_data() -> list:
    """Build one tent group per Hyphae, plus per-room groups of unlinked Spores.

    Each tent dict carries everything its card renders:
      - ``title`` / ``room_caption`` / ``icon``: card header
      - ``avg``: output of ``_summarize_spores`` (averages + per-Spore snapshots)
      - ``pressure``: output of ``_get_hyphae_pressure``, or None when the group
        has no Hyphae (unlinked Spores)
    """
    tents = []
    try:
        from storage.tables.device_hyphae import get_all_device_hyphae
        from storage.tables.device_spore import (
            get_spores_by_hyphae,
            get_unlinked_spores,
        )

        # One tent per Hyphae controller (already sorted by device_name).
        for hyphae in get_all_device_hyphae():
            spores = get_spores_by_hyphae(hyphae["device_id"])
            tents.append(
                {
                    "title": hyphae.get("device_name")
                    or f"Hyphae #{hyphae['device_id']}",
                    "room_caption": hyphae.get("room_name") or "No room",
                    "icon": "camping",
                    "avg": _summarize_spores(spores),
                    "pressure": _get_hyphae_pressure(hyphae),
                }
            )

        # Spores with no Hyphae still get a card, grouped by their grow room.
        rooms = {}
        for spore in get_unlinked_spores():
            rooms.setdefault(spore.get("room_id"), []).append(spore)

        unlinked = []
        for spores in rooms.values():
            unlinked.append(
                {
                    "title": spores[0].get("room_name") or "Unassigned room",
                    "room_caption": "Unlinked sensors",
                    "icon": "meeting_room",
                    "avg": _summarize_spores(spores),
                    "pressure": None,
                }
            )
        unlinked.sort(key=lambda t: t["title"])
        tents.extend(unlinked)
    except Exception:
        return []
    return tents


def _summarize_spores(spores: list) -> dict:
    """Average CO2 / temp / humidity across a tent's fresh Spores.

    Each Spore is first smoothed over its last ``SMOOTH_WINDOW`` readings to damp
    sensor noise, then the per-Spore values are averaged across the tent. A Spore
    whose newest reading is older than ``STALE_AFTER_SECONDS`` is treated as
    offline and excluded from the averages (its metrics show as dashes upstream).
    Every Spore's newest reading is also captured as its snapshot for the card's
    sensor column — same query, no extra reads.

    Returns a dict with:
      - ``co2`` / ``temp`` / ``humidity``: tent averages, or None if unavailable
      - ``fresh_count``: Spores contributing fresh data
      - ``total_count``: Spores in the tent
      - ``age_seconds``: age of the newest contributing reading, or None
      - ``spores``: per-Spore snapshots
        [{name, co2, temp, humidity, age_seconds, has_data}]
    """
    result = {
        "co2": None,
        "temp": None,
        "humidity": None,
        "fresh_count": 0,
        "total_count": len(spores),
        "age_seconds": None,
        "spores": [],
    }
    try:
        from storage.tables.readings_spore import get_device_readings

        sums = {"co2": 0.0, "temp": 0.0, "humidity": 0.0}
        counts = {"co2": 0, "temp": 0, "humidity": 0}
        fresh_count = 0
        newest_age = None

        for spore in spores:
            name = spore.get("device_name") or f"Spore #{spore['device_id']}"
            rows = get_device_readings(spore["device_id"], limit=SMOOTH_WINDOW)
            if not rows:
                result["spores"].append(
                    {
                        "name": name,
                        "co2": None,
                        "temp": None,
                        "humidity": None,
                        "age_seconds": None,
                        "has_data": False,
                    }
                )
                continue

            # rows are newest-first; row 0 doubles as the Spore's snapshot.
            age = _reading_age_seconds(rows[0].get("reading_ts"))
            result["spores"].append(
                {
                    "name": name,
                    "co2": rows[0].get("co2"),
                    "temp": rows[0].get("temp"),
                    "humidity": rows[0].get("humidity"),
                    "age_seconds": age,
                    "has_data": True,
                }
            )
            if age is None or age > STALE_AFTER_SECONDS:
                continue

            # Smooth each metric over this Spore's recent readings, then fold the
            # per-Spore average into the tent totals (equal weight per Spore).
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


def _get_hyphae_pressure(hyphae: dict) -> dict:
    """Latest pressure reading for one Hyphae, with a staleness flag.

    ``stale`` is True when the device has no reading or its newest reading is
    older than ``PRESSURE_STALE_AFTER_SECONDS``.
    """
    latest = None
    ts = ""
    age = None
    try:
        from storage.tables.readings_pressure import get_latest_pressure
        from web_ui.format import fmt_time, to_user_dt

        latest = get_latest_pressure(hyphae["device_id"])
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
    except Exception:
        latest = None

    return {
        "pressure_hpa": latest["pressure_hpa"] if latest else None,
        "source": latest.get("source", "BMP581") if latest else "BMP581",
        "healthy": bool(latest.get("healthy", 0)) if latest else False,
        "timestamp": ts,
        "has_data": latest is not None,
        "stale": age is None or age > PRESSURE_STALE_AFTER_SECONDS,
    }


def _reading_age_seconds(reading_ts) -> float | None:
    """Age in seconds of an ISO reading timestamp, or None if unparseable."""
    if not reading_ts:
        return None
    try:
        # reading_ts is naive UTC; compare against naive UTC now
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return (now - datetime.fromisoformat(reading_ts)).total_seconds()
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
