"""
Sentinel section of the Devices page.

Sentinel is the grower-environment air-quality monitor (SEN66 PM/VOC/NOx/
CO2/T/RH + BMP581 pressure) that sits outside the grow tents. This module
holds everything Sentinel-specific for the Devices page — list panel, add
dialog, detail tabs — and reuses the generic row/panel helpers from
web_ui.pages.devices, which imports this module lazily to avoid a cycle.

Data model notes: every sensor channel may be None (the firmware reports null
for a channel that is unavailable), so all formatting goes through helpers
that render "N/A" rather than a fake 0.
"""

import asyncio
import logging
from typing import Dict, List, Optional

from nicegui import ui, run

from web_ui.format import fmt_datetime, pm25_aqi_band
from web_ui.pages.devices import (
    _HOST_PATTERN,
    _SPORE_GRID,
    _device_list_header,
    _device_management_panel,
    _expandable_device_row,
    _export_devices_csv,
    _fmt_reading,
    _fmt_temp,
    _fmt_uptime,
    _format_last_seen,
    _get_json,
    _kv,
    _online_badge,
    _open_import_csv_dialog,
    _panel_source_row,
    _placeholder_mac,
    _reading_card,
    _room_options,
    _spore_header_cells,
    _temp_pref,
    discover_mac_address,
)
from storage.tables.device_sentinel import (
    create_device_sentinel,
    get_all_device_sentinel,
    get_device_sentinel_by_hostname,
    set_device_online,
    set_device_room,
    update_device_sentinel,
    update_device_status,
)
from storage.tables.device_spore import normalize_device_host
from storage.tables.readings_sentinel import (
    get_latest_reading as get_latest_sentinel_reading,
)

logger = logging.getLogger(__name__)

# Live JSON key -> readings_sentinel column, so a stored row renders through
# the same code path as a live /api/readings/latest payload.
_DB_COLUMNS = {
    "pm1": "pm1",
    "pm2_5": "pm2_5",
    "pm4": "pm4",
    "pm10": "pm10",
    "co2": "co2",
    "humidity": "humidity",
    "temperature": "temp",
    "voc": "voc",
    "nox": "nox",
    "pressure_hpa": "pressure_hpa",
}


# ---------------------------------------------------------------------------
# Device fetch / register / refresh
# ---------------------------------------------------------------------------


def fetch_sentinel_readings_latest(ip: str) -> Optional[Dict]:
    """Fetch the latest reading from Sentinel /api/readings/latest."""
    return _get_json(ip, "/api/readings/latest")


def fetch_sentinel_diagnostics(ip: str) -> Optional[Dict]:
    """Fetch diagnostics from Sentinel /api/diagnostics (firmware 1.1.0+)."""
    return _get_json(ip, "/api/diagnostics")


def _safe_get_sentinel_devices() -> List[Dict]:
    try:
        return get_all_device_sentinel()
    except Exception:
        return []


def store_complete_sentinel_device_data(ip: str, room_id=None) -> Dict:
    """Probe a Sentinel device, register it in the DB, and return the result.

    One probe of /api/readings/latest is enough: unlike Spore, the device name
    and running firmware version both ride along in that payload. A room is
    optional — a Sentinel usually monitors the grower's air outside the tents.
    """
    # Guard against adding the same device twice (hostname is the stable identity).
    host = normalize_device_host(ip)
    if get_device_sentinel_by_hostname(host):
        return {
            "success": False,
            "errors": [f"A Sentinel with hostname {host} is already in the list."],
        }

    latest = fetch_sentinel_readings_latest(ip) or {}
    device_name = latest.get("device_name") or ip.split(":")[0]
    mac = discover_mac_address(ip) or _placeholder_mac(ip)
    firmware = latest.get("firmware_version") or ""

    try:
        device_id = create_device_sentinel(
            device_name=device_name,
            hostname=ip,
            mac_address=mac,
            room_id=int(room_id) if room_id else None,
            firmware_version=firmware,
            is_online=1 if latest else 0,
        )
        return {
            "success": True,
            "data": {"latest": latest},
            "device_id": device_id,
        }
    except Exception as e:
        return {"success": False, "errors": [str(e)]}


def refresh_sentinel_device_data(device_id, ip: str) -> Dict:
    """Re-poll an existing Sentinel and update its status/info in the DB.

    Counterpart to refresh_spore_device_data(): refreshes online status,
    last-seen time, and any changed name/firmware. Marks offline if unreachable.
    """
    latest = fetch_sentinel_readings_latest(ip)
    if latest is None:
        # Keep last_update meaning "last successful contact" (see set_device_online).
        set_device_online(device_id, 0)
        return {"success": False, "errors": [f"{ip} unreachable."]}

    update_device_status(device_id, 1)
    device_name = latest.get("device_name")
    firmware = latest.get("firmware_version")
    if device_name or firmware:
        update_device_sentinel(
            device_id,
            device_name=device_name or None,
            firmware_version=firmware or None,
        )
    return {"success": True, "errors": []}


# ---------------------------------------------------------------------------
# SENTINEL panel (list of expandable rows)
# ---------------------------------------------------------------------------


def _build_sentinel_panel(colors, selected_device, stat_cards):
    """Build the Sentinel devices tab content (expandable row per device)."""
    open_rows: set = set()
    selected_device["_open_sentinel"] = open_rows

    @ui.refreshable
    def sentinel_table():
        # Rebuilt rows start collapsed, so reset the open-row set here.
        open_rows.clear()

        devices = _safe_get_sentinel_devices()
        if not devices:
            ui.label("No Sentinel devices found. Add a device to get started.").classes(
                "text-muted q-pa-md"
            )
            return

        # Same five summary columns as a Spore row (Name/Hostname/Room/Status/
        # Last Seen), so the shared grid + header-cell renderer apply as-is.
        _device_list_header(
            ["Name", "Hostname", "Room", "Status", "Last Seen"], _SPORE_GRID
        )
        for d in devices:
            _expandable_device_row(
                d,
                _SPORE_GRID,
                _spore_header_cells,
                lambda dev: _render_sentinel_detail(dev, colors, selected_device),
                open_rows,
            )

    with ui.row().classes("w-full items-center gap-2 q-mb-md"):
        ui.button(
            "Add Sentinel",
            icon="add",
            on_click=lambda: _open_add_sentinel_dialog(sentinel_table, stat_cards),
        ).props("color=primary")

        async def refresh_sentinel():
            devices = _safe_get_sentinel_devices()
            if not devices:
                ui.notify("No Sentinel devices to refresh.", type="info")
                return
            # Blocking fetches off the event loop, concurrently — see refresh_spore.
            progress = ui.notification(
                f"Refreshing {len(devices)} Sentinel device(s)…",
                spinner=True,
                timeout=None,
            )
            try:
                results = await asyncio.gather(
                    *(
                        run.io_bound(
                            refresh_sentinel_device_data,
                            d["device_id"],
                            d["hostname"],
                        )
                        for d in devices
                    ),
                    return_exceptions=True,
                )
            finally:
                progress.dismiss()
            success = sum(
                1 for r in results if isinstance(r, dict) and r.get("success")
            )
            errors = len(results) - success
            sentinel_table.refresh()
            stat_cards.refresh()
            if errors == 0:
                ui.notify(f"Refreshed {success} Sentinel device(s).", type="positive")
            else:
                ui.notify(f"Refreshed {success}, failed {errors}.", type="warning")

        ui.button("Refresh All", icon="refresh", on_click=refresh_sentinel).props(
            "outline"
        )
        ui.button(
            "Export CSV",
            icon="download",
            on_click=lambda: _export_devices_csv("sentinel"),
        ).props("outline")
        ui.button(
            "Import CSV",
            icon="upload",
            on_click=lambda: _open_import_csv_dialog(
                "sentinel", sentinel_table, stat_cards
            ),
        ).props("outline")

    sentinel_table()

    # Expose refreshers so the detail panel (e.g. Remove Device) can update the list.
    selected_device["_sentinel_table"] = sentinel_table
    selected_device["_stat_cards"] = stat_cards


def _open_add_sentinel_dialog(table_refresh, stat_cards_refresh):
    """Open the Add Sentinel device dialog."""
    with ui.dialog() as dialog, ui.card().classes("min-w-80"):
        ui.label("Add Sentinel Device").classes("text-h6 q-mb-md")

        ip_input = ui.input(
            label="Hostname",
            placeholder="sentinel-1234.local or 192.168.1.100:8080",
            validation={
                "Invalid hostname": lambda v: (
                    bool(_HOST_PATTERN.match(v)) if v else False
                )
            },
        ).classes("w-full")

        rooms = _room_options()
        room_select = ui.select(
            options=rooms,
            label="Grow Room (optional)",
            with_input=True,
            clearable=True,
        ).classes("w-full")

        ui.label(
            "Enter the device hostname (e.g. sentinel-1234.local). A Sentinel "
            "monitors the grower's air outside the tents, so a room is optional."
        ).classes("text-muted text-caption q-mt-sm")

        with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dialog.close).props("flat")

            def add_sentinel():
                ip = ip_input.value
                if not ip or not _HOST_PATTERN.match(ip):
                    ui.notify("Please enter a valid hostname.", type="negative")
                    return

                try:
                    result = store_complete_sentinel_device_data(
                        ip, room_select.value or None
                    )
                    if result.get("success"):
                        name = (
                            result.get("data", {})
                            .get("latest", {})
                            .get("device_name", ip.split(":")[0])
                        )
                        ui.notify(
                            f'Sentinel device "{name}" added successfully.',
                            type="positive",
                        )
                        dialog.close()
                        table_refresh.refresh()
                        stat_cards_refresh.refresh()
                    else:
                        errors = "; ".join(result.get("errors", ["Unknown error"]))
                        ui.notify(f"Error: {errors}", type="negative")
                except Exception as exc:
                    ui.notify(f"Error adding device: {exc}", type="negative")

            ui.button("Add Device", icon="add", on_click=add_sentinel).props(
                "color=primary"
            )

    dialog.open()


# ---------------------------------------------------------------------------
# SENTINEL detail
# ---------------------------------------------------------------------------


def _render_sentinel_detail(device: Dict, colors: dict, selected_device: Dict = None):
    """Render the full detail panel for a Sentinel device."""
    ui.label(f"{device.get('device_name', 'Sentinel Device')}").classes("text-h5")
    _online_badge(device.get("is_online"))

    with ui.tabs().classes("w-full") as dtabs:
        tab_readings = ui.tab("Readings", icon="air")
        tab_diag = ui.tab("Diagnostics", icon="monitor_heart")
        tab_mgmt = ui.tab("Management", icon="build")

    with ui.tab_panels(dtabs, value=tab_readings).classes("w-full"):
        with ui.tab_panel(tab_readings):
            _sentinel_readings_panel(device, colors)

        with ui.tab_panel(tab_diag):
            _sentinel_diagnostics_panel(device, colors)

        # Management: room assignment, then the shared credential/OTA/remove panel
        with ui.tab_panel(tab_mgmt):
            _sentinel_room_card(device)
            _device_management_panel(device, "sentinel", colors, selected_device)


def _sentinel_db_reading(device: Dict):
    """Build a Sentinel reading view from the database (no device call).

    Returns (reading, as_of) where `reading` uses the same keys as the live
    /api/readings/latest payload, or (None, None) when nothing has been
    polled yet.
    """
    device_id = device.get("device_id")
    if not device_id:
        return None, None
    row = get_latest_sentinel_reading(device_id)
    if not row:
        return None, None

    reading = {key: row.get(column) for key, column in _DB_COLUMNS.items()}
    return reading, _format_last_seen(row.get("reading_ts"))


def _aqi_chip(pm25) -> None:
    """Render the EPA AQI band for a PM2.5 value as a coloured chip.

    A styled ui.label rather than ui.badge: an inline background-color on a
    badge loses to Quasar's `bg-primary !important` (see _online_badge).
    """
    band = pm25_aqi_band(pm25)
    if band is None:
        ui.label("AQI unavailable").classes("text-caption text-muted")
        return
    label, bg, fg = band
    ui.label(label).classes("text-caption text-weight-bold q-px-sm q-py-xs").style(
        f"background-color: {bg}; color: {fg}; border-radius: 12px;"
    )


def _sentinel_readings_panel(device: Dict, colors: dict):
    """Show latest readings for a Sentinel (DB-first, live on demand)."""
    state = {"live": None, "fetched": False}
    accent = colors["primary"]

    @ui.refreshable
    def body():
        live = state["live"]
        if live:
            readings = live
            # /api/readings/latest returns a unix timestamp (0 pre-clock-sync).
            try:
                ts = int(live.get("timestamp", 0))
            except (TypeError, ValueError):
                ts = 0
            as_of = fmt_datetime(ts) if ts > 0 else "device clock not synced"
        else:
            readings, as_of = _sentinel_db_reading(device)

        _panel_source_row(
            state,
            lambda: fetch_sentinel_readings_latest(device.get("hostname", "")),
            body,
            as_of=as_of,
        )

        if live and live.get("error"):
            ui.label(
                "Device reports no data yet — its sensors are still warming up."
            ).classes("text-muted")
            return

        if not readings:
            ui.label(
                "No stored readings yet. Click “Refresh from device” to fetch live."
            ).classes("text-muted")
            return

        # PM2.5 hero with its AQI band
        with ui.card().classes("w-full p-4"):
            with ui.row().classes("items-center gap-4 flex-wrap"):
                ui.icon("air", size="lg").style(f"color: {accent}")
                with ui.column().classes("gap-0"):
                    pm25 = _fmt_reading(readings.get("pm2_5"), 1)
                    ui.label(f"{pm25} µg/m³" if pm25 != "N/A" else "N/A").classes(
                        "text-h4"
                    )
                    ui.label("PM2.5").classes("text-caption text-muted")
                _aqi_chip(readings.get("pm2_5"))

        # Particle size bands (PM4/PM10 are sensor-derived from the PM2.5 count)
        with ui.row().classes("w-full gap-4 flex-wrap"):
            _reading_card(
                "PM1", _fmt_reading(readings.get("pm1"), 1), "µg/m³", "blur_on", accent
            )
            _reading_card(
                "PM4", _fmt_reading(readings.get("pm4"), 1), "µg/m³", "blur_on", accent
            )
            _reading_card(
                "PM10",
                _fmt_reading(readings.get("pm10"), 1),
                "µg/m³",
                "blur_on",
                accent,
            )

        # Gas indices: 100 = typical VOC baseline, 1 = NOx baseline
        with ui.row().classes("w-full gap-4 flex-wrap"):
            _reading_card(
                "VOC Index", _fmt_reading(readings.get("voc"), 0), "", "science", accent
            )
            _reading_card(
                "NOx Index", _fmt_reading(readings.get("nox"), 0), "", "science", accent
            )

        # Climate in the standard metric order: CO2, humidity, temp (then pressure)
        temp_value, temp_unit = _fmt_temp(readings.get("temperature"), _temp_pref())
        with ui.row().classes("w-full gap-4 flex-wrap"):
            _reading_card(
                "CO2", _fmt_reading(readings.get("co2"), 0), "ppm", "co2", accent
            )
            _reading_card(
                "Humidity",
                _fmt_reading(readings.get("humidity"), 1),
                "%",
                "water_drop",
                accent,
            )
            _reading_card("Temperature", temp_value, temp_unit, "thermostat", accent)
            _reading_card(
                "Pressure",
                _fmt_reading(readings.get("pressure_hpa"), 1),
                "hPa",
                "speed",
                accent,
            )

        # Sensor health flags only ride along with a live payload
        if live:
            with ui.row().classes("items-center gap-2 q-mt-sm"):
                sen66_ok = bool(live.get("sen66_ok"))
                bmp_ok = bool(live.get("bmp581_ok"))
                ui.badge(
                    "SEN66 OK" if sen66_ok else "SEN66 fault",
                    color="green" if sen66_ok else "red",
                )
                ui.badge(
                    "BMP581 OK" if bmp_ok else "BMP581 fault",
                    color="green" if bmp_ok else "red",
                )

    body()


def _sentinel_diagnostics_panel(device: Dict, colors: dict):
    """Show Sentinel diagnostics from /api/diagnostics (system, sensors, errors).

    Diagnostics are not persisted, so this panel never fetches automatically.
    It stays blank until the user clicks "Refresh from device".
    """
    state = {"live": None, "fetched": False}

    @ui.refreshable
    def body():
        _panel_source_row(
            state,
            lambda: fetch_sentinel_diagnostics(device.get("hostname", "")),
            body,
            stored=False,
        )
        _sentinel_diagnostics_body(state)

    body()


def _sentinel_diagnostics_body(state: Dict):
    """Render the diagnostics cards once the device has been queried."""
    info = state.get("live")
    if not info:
        if state.get("fetched"):
            ui.label(
                "Could not fetch diagnostics. The device may be offline, or its "
                "firmware predates 1.1.0 (no /api/diagnostics)."
            ).classes("text-muted")
        else:
            ui.label(
                "Diagnostics are read live from the device and are not stored. "
                "Click “Refresh from device” to query it."
            ).classes("text-muted")
        return

    system = info.get("system", {})
    sensors = info.get("sensors", {})
    errors = info.get("errors", {})

    with ui.card().classes("w-full p-4"):
        ui.label("System").classes("text-subtitle1 text-weight-bold q-mb-sm")
        _kv("Uptime", _fmt_uptime(system.get("uptime_sec")))
        _kv("Free Memory", f"{system.get('heap_free_kb', 'N/A')} KB")
        _kv("Min Free Memory", f"{system.get('heap_min_free_kb', 'N/A')} KB")
        _kv("WiFi Signal", f"{system.get('wifi_rssi_dbm', 'N/A')} dBm")

    with ui.card().classes("w-full p-4 q-mt-md"):
        ui.label("Sensors").classes("text-subtitle1 text-weight-bold q-mb-sm")
        _kv("SEN66 (PM/VOC/NOx/CO2/T/RH)", "OK" if sensors.get("sen66_ok") else "Fault")
        _kv("BMP581 (Pressure)", "OK" if sensors.get("bmp581_ok") else "Fault")

    # Entry timestamps are seconds-since-boot; convert to wall-clock using the
    # device's current unix time and uptime (both in this same diagnostics reply).
    try:
        diag_now = int(info.get("timestamp", 0))
    except (TypeError, ValueError):
        diag_now = 0
    try:
        uptime = int(system.get("uptime_sec", 0))
    except (TypeError, ValueError):
        uptime = 0

    def _error_when(entry) -> str:
        try:
            boot_sec = int(entry.get("timestamp_sec", 0))
        except (TypeError, ValueError):
            boot_sec = 0
        if diag_now > 0 and uptime > 0:
            when_unix = diag_now - (uptime - boot_sec)
            if when_unix > 0:
                return fmt_datetime(when_unix)
        return f"+{_fmt_uptime(boot_sec)} (since boot)"

    entries = errors.get("entries", []) if isinstance(errors, dict) else []
    total = errors.get("total_count", len(entries)) if isinstance(errors, dict) else 0
    with ui.card().classes("w-full p-4 q-mt-md"):
        ui.label(f"Error History ({total})").classes(
            "text-subtitle1 text-weight-bold q-mb-sm"
        )
        if not entries:
            ui.label("No errors recorded.").classes("text-muted")
        else:
            for e in entries:
                level = e.get("level", "INFO")
                color = {"ERROR": "red", "WARN": "orange"}.get(level, "grey")
                with ui.row().classes("items-center gap-2"):
                    ui.badge(level, color=color)
                    ui.label(_error_when(e)).classes("text-caption text-muted")
                    ui.label(
                        f"{e.get('component', '?')}: {e.get('message', '')}"
                    ).classes("text-caption")
                    code = e.get("code")
                    if code:
                        ui.label(f"(code {code})").classes("text-caption text-muted")


def _sentinel_room_card(device: Dict):
    """Assign (or clear) the grow room a Sentinel belongs to. Management tab."""
    device_id = device.get("device_id")
    with ui.card().classes("w-full p-4 q-mb-md"):
        ui.label("Room Assignment").classes("text-h6 q-mb-sm")
        ui.label(
            "A Sentinel usually monitors the grower's air outside the tents. "
            "Assign a room only if this unit lives inside one."
        ).classes("text-caption text-muted q-mb-sm")

        room_opts = {0: "— None —", **_room_options()}
        room_select = ui.select(
            options=room_opts,
            value=device.get("room_id") or 0,
            label="Grow Room",
        ).classes("w-full")

        def _save_room():
            room_id = room_select.value or 0
            set_device_room(device_id, room_id if room_id else None)
            if room_id:
                ui.notify(f"Assigned to {room_opts.get(room_id)}", type="positive")
            else:
                ui.notify("Room assignment cleared", type="info")

        ui.button("Save Room", icon="meeting_room", on_click=_save_room).props(
            "outline dense"
        ).classes("q-mt-sm")
