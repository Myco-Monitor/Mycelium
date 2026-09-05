"""
Device Health Dashboard page for Mycelium NiceGUI application.

Unified view of all device health metrics: RSSI, heap, uptime,
firmware version, response time, last error, and online status.
"""

from nicegui import ui, app
from web_ui.layout import page_layout, back_to_dashboard
from web_ui.theme import get_colors, STATUS_COLORS
from web_ui.format import fmt_datetime


@ui.page("/health")
@ui.page("/health-dashboard")
def health_dashboard_page():
    """Device health dashboard with live metrics and history."""
    user = app.storage.user
    if not user.get("user_id"):
        ui.navigate.to("/login")
        return

    page_layout("Health Dashboard")
    back_to_dashboard()
    colors = get_colors()

    with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.column().classes("gap-0"):
                ui.label("Device Health Dashboard").classes("text-h4")
                ui.label("Real-time health monitoring for all devices").classes(
                    "text-muted"
                )
            ui.button(
                "Refresh",
                icon="refresh",
                on_click=lambda: (_health_summary.refresh(), health_grid.refresh()),
            ).props("outline")

        # Summary stats
        _health_summary(colors)

        # Device health grid
        health_grid()

        # Auto-refresh every 60 seconds
        ui.timer(60.0, lambda: (_health_summary.refresh(), health_grid.refresh()))


@ui.refreshable
def _health_summary(colors: dict):
    """Summary cards for overall fleet health."""
    from storage.tables.device_spore import get_all_device_spore
    from storage.tables.device_hyphae import get_all_device_hyphae
    from storage.tables.device_sentinel import get_all_device_sentinel

    all_devices = (
        [(d, "spore") for d in get_all_device_spore()]
        + [(d, "hyphae") for d in get_all_device_hyphae()]
        + [(d, "sentinel") for d in get_all_device_sentinel()]
    )

    total = len(all_devices)
    online = sum(1 for d, _ in all_devices if d.get("is_online"))
    offline = total - online

    with ui.row().classes("w-full gap-4 flex-wrap"):
        _stat_card("Total Devices", str(total), "devices", colors)
        _stat_card(
            "Online", str(online), "check_circle", colors, color=STATUS_COLORS["online"]
        )
        _stat_card(
            "Offline",
            str(offline),
            "error",
            colors,
            color=STATUS_COLORS["offline"]
            if offline > 0
            else colors.get("text_muted", "#999"),
        )
        health_pct = f"{(online / total * 100):.0f}%" if total > 0 else "N/A"
        _stat_card("Fleet Health", health_pct, "monitor_heart", colors)


def _stat_card(label: str, value: str, icon: str, colors: dict, color: str = None):
    """Small stat card."""
    with ui.card().classes("p-4 flex-1 min-w-40 text-center"):
        ui.icon(icon, size="sm").style(f"color: {color or colors['primary']}")
        ui.label(value).classes("text-h4 q-mt-xs")
        ui.label(label).classes("text-caption text-muted")


@ui.refreshable
def health_grid():
    """Grid of device health cards."""
    from storage.tables.device_spore import get_all_device_spore
    from storage.tables.device_hyphae import get_all_device_hyphae
    from storage.tables.device_sentinel import get_all_device_sentinel
    from storage.tables.device_health import (
        get_all_devices_health_summary,
        get_device_health_metrics,
    )

    colors = get_colors()

    all_devices = (
        [(d, "spore") for d in get_all_device_spore()]
        + [(d, "hyphae") for d in get_all_device_hyphae()]
        + [(d, "sentinel") for d in get_all_device_sentinel()]
    )

    if not all_devices:
        ui.label("No devices registered").classes("text-muted text-center q-pa-lg")
        return

    # Get health summary data
    health_data = {}
    try:
        for h in get_all_devices_health_summary():
            health_data[f"{h['device_type']}:{h['device_id']}"] = h
    except Exception:
        pass

    # Get detailed metrics per device (24h uptime + response time)
    metrics_data = {}
    for device, dtype in all_devices:
        device_id = device["device_id"]
        try:
            metrics_data[f"{dtype}:{device_id}"] = get_device_health_metrics(
                device_id, dtype
            )
        except Exception:
            pass

    with ui.element("div").style(
        "display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; width: 100%;"
    ):
        for device, dtype in all_devices:
            _device_health_card(device, dtype, health_data, metrics_data, colors)


def _device_health_card(
    device: dict, dtype: str, health_data: dict, metrics_data: dict, colors: dict
):
    """Render a single device health card with detailed metrics."""
    device_id = device["device_id"]
    name = device.get("device_name", f"{dtype}-{device_id}")
    ip = device.get("hostname", "N/A")
    firmware = device.get("firmware_version", "Unknown")
    is_online = device.get("is_online", False)

    key = f"{dtype}:{device_id}"
    health = health_data.get(key, {})
    metrics = metrics_data.get(key, {})

    # Extract metrics with fallback chain
    uptime_24h = metrics.get("uptime_24h", 0)
    uptime_7d = metrics.get("uptime_7d", 0)
    avg_response = metrics.get("avg_response_24h")
    if avg_response is None:
        avg_response = health.get("last_response_ms")
    last_check = health.get("last_check")
    check_count = metrics.get("check_count_24h", 0)
    rssi = device.get("wifi_rssi")

    status_color = STATUS_COLORS["online"] if is_online else STATUS_COLORS["offline"]
    status_text = "Online" if is_online else "Offline"

    with ui.card().classes("p-4"):
        # Header: name + status badge
        with ui.row().classes("w-full items-center justify-between q-mb-sm"):
            with ui.row().classes("items-center gap-2"):
                icon = {
                    "spore": "sensors",
                    "hyphae": "device_hub",
                    "sentinel": "air",
                }.get(dtype, "devices")
                ui.icon(icon, size="xs").style(f"color: {colors['primary']}")
                ui.label(name).classes("text-subtitle1 text-weight-bold")
            ui.badge(status_text).style(
                f"background-color: {status_color}; color: white"
            )

        # Basic info
        _info_row("IP", ip)
        _info_row("Type", dtype.capitalize())
        _info_row("Firmware", firmware)

        # RSSI with signal quality
        if rssi is not None:
            rssi_label = f"{rssi} dBm"
            if rssi > -50:
                rssi_label += " (Excellent)"
            elif rssi > -70:
                rssi_label += " (Good)"
            elif rssi > -80:
                rssi_label += " (Fair)"
            else:
                rssi_label += " (Weak)"
            _info_row("RSSI", rssi_label)

        # Diagnostics snapshot (spore-only heap; hidden when not yet polled)
        heap_free_kb = device.get("heap_free_kb")
        if heap_free_kb is not None:
            heap_label = f"{heap_free_kb} KB"
            heap_min_free_kb = device.get("heap_min_free_kb")
            if heap_min_free_kb is not None:
                heap_label += f" (min {heap_min_free_kb} KB)"
            _info_row("Heap Free", heap_label)

        uptime_sec = device.get("uptime_sec")
        if uptime_sec is not None:
            _info_row("Device Uptime", _fmt_uptime(uptime_sec))

        ui.separator().classes("q-my-xs")

        # Uptime metrics
        _info_row("Uptime (24h)", f"{uptime_24h:.1f}%" if uptime_24h else "No data")
        if uptime_7d:
            _info_row("Uptime (7d)", f"{uptime_7d:.1f}%")

        # Uptime progress bar (24h)
        bar_value = uptime_24h / 100 if uptime_24h else 0
        bar_color = (
            "green" if bar_value > 0.9 else "orange" if bar_value > 0.5 else "red"
        )
        ui.linear_progress(value=bar_value, show_value=False).props(
            f"color={bar_color}"
        ).classes("w-full q-mt-xs")

        # Response time
        if avg_response is not None:
            rt_label = f"{avg_response:.0f} ms"
            if avg_response > 5000:
                rt_label += " (Slow)"
            elif avg_response > 2000:
                rt_label += " (Fair)"
            _info_row("Avg Response", rt_label)

        # Check count
        if check_count:
            _info_row("Checks (24h)", str(check_count))

        # Last check
        if last_check:
            _info_row("Last Check", fmt_datetime(last_check, fallback="—"))


def _fmt_uptime(uptime_sec: int) -> str:
    """Format device uptime seconds as 'Xd Yh Zm'."""
    days, rem = divmod(int(uptime_sec), 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _info_row(label: str, value: str):
    """Render a label: value row."""
    with ui.row().classes("w-full justify-between"):
        ui.label(label).classes("text-caption text-muted")
        ui.label(value).classes("text-caption")
