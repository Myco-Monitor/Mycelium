"""
Main dashboard page for Mycelium NiceGUI application.

Provides a live overview of the farm with device counts, recent readings,
and quick navigation to key features.
"""

from nicegui import ui, app
from web_ui.layout import page_layout
from web_ui.theme import get_colors


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

        # Auto-refresh stats every 30 seconds via WebSocket
        ui.timer(30.0, lambda: dashboard_stats.refresh())

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
    with ui.row().classes("w-full gap-4 flex-wrap"):
        _stat_card("Spore Devices", _get_device_count("spore"), "sensors", colors)
        _stat_card("Hyphae Devices", _get_device_count("hyphae"), "device_hub", colors)
        _stat_card("Grow Rooms", _get_room_count(), "meeting_room", colors)
        _stat_card("Active Alerts", _get_alert_count(), "warning", colors)


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


def _get_device_count(device_type: str) -> int:
    """Get count of devices by type."""
    try:
        if device_type == "spore":
            from storage.tables.device_spore import get_all_device_spore

            return len(get_all_device_spore())
        else:
            from storage.tables.device_hyphae import get_all_device_hyphae

            return len(get_all_device_hyphae())
    except Exception:
        return 0


def _get_room_count() -> int:
    """Get count of grow rooms."""
    try:
        from storage.tables.grow_rooms import get_all_grow_rooms

        return len(get_all_grow_rooms())
    except Exception:
        return 0


def _get_alert_count() -> int:
    """Get count of active alerts."""
    try:
        from storage.tables.alert_history import get_active_alerts

        return len(get_active_alerts())
    except Exception:
        return 0
