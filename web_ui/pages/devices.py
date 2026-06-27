"""
Devices page for Mycelium NiceGUI application.

Comprehensive device management for Spore and Hyphae devices.
Provides device tables, add dialogs, and detail panels with readings,
configuration, relay state, schedule, and dynamic control views.
"""

import re
import asyncio
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, List

import requests

from nicegui import ui, app, run
from web_ui.layout import page_layout, back_to_dashboard
from web_ui.theme import get_colors, STATUS_COLORS
from web_ui.format import fmt_datetime

from storage.tables.device_spore import (
    get_all_device_spore,
    link_spore_to_hyphae,
    unlink_spore_from_hyphae,
    update_spore_weather_pressure,
    delete_device_spore,
)
from storage.tables.device_hyphae import (
    get_all_device_hyphae,
    update_device_hyphae,
    delete_device_hyphae,
)
from storage.tables.grow_rooms import get_all_grow_rooms
from storage.tables.relay_settings import get_device_relay_settings
from storage.tables.device_pins import store_device_pin, has_stored_pin
from storage.tables.readings_spore import get_latest_reading as get_latest_spore_reading
from storage.tables.readings_hyphae import get_latest_relay_states
from storage.tables.readings_pressure import get_latest_pressure

logger = logging.getLogger(__name__)

_SCHEME = "https"
# Kept short: these device fetches are synchronous (requests) and run on the UI
# event loop, so a slow/unreachable device must not stall it for long.
_TIMEOUT = 5
_CA_CERT = str(Path(__file__).parent.parent.parent / "config" / "ca_root.pem")


def _device_url(ip: str, path: str) -> str:
    """Build a device URL. Supports an optional ip:port (e.g. for local simulators)."""
    return f"{_SCHEME}://{ip}{path}"


def _get_json(ip: str, path: str) -> Optional[Dict]:
    """GET a JSON endpoint from a device. Returns None on any error."""
    try:
        verify = _CA_CERT if Path(_CA_CERT).exists() else False
        r = requests.get(_device_url(ip, path), timeout=_TIMEOUT, verify=verify)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.debug(f"GET {path} from {ip} failed: {e}")
    return None


def _get_text(ip: str, path: str) -> Optional[str]:
    """GET an HTML/text endpoint from a device. Returns None on any error."""
    try:
        verify = _CA_CERT if Path(_CA_CERT).exists() else False
        r = requests.get(_device_url(ip, path), timeout=_TIMEOUT, verify=verify)
        if r.status_code == 200:
            return r.text
    except Exception as e:
        logger.debug(f"GET {path} from {ip} failed: {e}")
    return None


# The Hyphae firmware serves relay schedule + dynamic thresholds only as POST
# (the JSON GET endpoints return 400). The current values are, however, rendered
# into the device's own HTML config pages as <input> values, so we read those
# pages and parse the inputs back out. If a future firmware adds a JSON GET, swap
# these two helpers to use _get_json instead.
def _input_value(html_text: str, input_id: str) -> Optional[str]:
    """Return the value="..." of the <input id="input_id"> in a device page."""
    m = re.search(rf'id="{re.escape(input_id)}"[^>]*\bvalue="([^"]*)"', html_text)
    return m.group(1) if m else None


def _checkbox_checked(html_text: str, input_id: str) -> bool:
    """Return True if the checkbox <input id="input_id"> carries `checked`."""
    m = re.search(rf'id="{re.escape(input_id)}"([^>]*)>', html_text)
    return bool(m and "checked" in m.group(1))


def _parse_hyphae_schedule_html(html_text: Optional[str]) -> Optional[Dict]:
    """Parse the relay schedule (on/off duty-cycle minutes per group 1-6)."""
    if not html_text:
        return None
    groups = []
    for g in range(1, 7):
        on = _input_value(html_text, f"g{g}_on")
        off = _input_value(html_text, f"g{g}_off")
        if on is None and off is None:
            continue
        groups.append({"group": g, "on_min": on, "off_min": off})
    return {"groups": groups} if groups else None


_ENABLED_MODE_TO_INT = {"off": 0, "testing": 1, "running": 2}
_OPERATION_MODE_TO_INT = {"schedule": 0, "dynamic": 1}


def _config_mode_value(html_text: str, label: str) -> Optional[str]:
    """Return the value text shown next to a config-page label (e.g. 'Testing')."""
    m = re.search(rf"{re.escape(label)}</span><span[^>]*>([^<]+)</span>", html_text)
    return m.group(1).strip() if m else None


def _parse_hyphae_config_modes(html_text: Optional[str]) -> Optional[Dict]:
    """Parse the Enabled Mode + Operation Mode from the /hyphae-config page.

    Returns ints matching the DB columns: enabled_mode 0=Off/1=Testing/2=Running,
    operation_mode 0=Schedule/1=Dynamic. Either may be None if not found.
    """
    if not html_text:
        return None
    enabled = _config_mode_value(html_text, "Enabled Mode")
    operation = _config_mode_value(html_text, "Operation Mode")
    e = _ENABLED_MODE_TO_INT.get((enabled or "").lower())
    o = _OPERATION_MODE_TO_INT.get((operation or "").lower())
    if e is None and o is None:
        return None
    return {"enabled_mode": e, "operation_mode": o}


def _parse_hyphae_dynamic_html(html_text: Optional[str]) -> Optional[Dict]:
    """Parse dynamic-control thresholds (CO2/Humidity/Temp low+high + behavior)."""
    if not html_text:
        return None
    params = [("CO₂", "co2", 1), ("Humidity", "hum", 2), ("Temperature", "temp", 3)]
    controls = []
    for label, key, group in params:
        low = _input_value(html_text, f"{key}_low")
        high = _input_value(html_text, f"{key}_high")
        if low is None and high is None:
            continue
        controls.append(
            {
                "param": label,
                "group": group,
                "low": low,
                "high": high,
                # Checked = "Activate HIGH"; unchecked = "Activate LOW".
                "activate_high": _checkbox_checked(html_text, f"g{group}_behavior"),
            }
        )
    return {
        "controls": controls,
        "temp_pref": _input_value(html_text, "temp_pref"),
    }


def discover_mac_address(hostname: str) -> Optional[str]:
    """Discover MAC address via ARP / ip-neigh."""
    # Try ARP
    try:
        result = subprocess.run(
            ["arp", "-n", hostname], capture_output=True, text=True, timeout=5
        )
        match = re.search(r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}", result.stdout)
        if match:
            return match.group(0)
    except Exception:
        pass
    # Try ip neigh
    try:
        result = subprocess.run(
            ["ip", "neigh", "show"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split("\n"):
            if hostname in line:
                match = re.search(r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}", line)
                if match:
                    return match.group(0)
    except Exception:
        pass
    return None


def _placeholder_mac(ip: str) -> str:
    """Stable, unique MAC placeholder for devices that don't report a MAC.

    The Spore/Hyphae API doesn't expose a MAC and ARP can't resolve an mDNS
    name, so derive a per-host label. Using the (unique) hostname keeps the
    UNIQUE constraint on mac_address satisfied so multiple devices can be added.
    """
    label = ip.split(":")[0].replace(".local", "")
    return f"unknown-{label}"


def fetch_spore_readings_latest(ip: str) -> Optional[Dict]:
    """Fetch latest readings from Spore /api/readings/latest."""
    return _get_json(ip, "/api/readings/latest")


def fetch_spore_info(ip: str) -> Optional[Dict]:
    """Fetch diagnostics from Spore /api/diagnostics."""
    return _get_json(ip, "/api/diagnostics")


def fetch_spore_config(ip: str) -> Optional[Dict]:
    """Fetch Spore configuration from /spore-config (HTML) or /api/status."""
    # Prefer JSON status endpoint
    data = _get_json(ip, "/api/status")
    if data:
        return data
    return None


def fetch_hyphae_config(ip: str) -> Optional[Dict]:
    """Fetch Hyphae configuration from /api/system/info."""
    return _get_json(ip, "/api/system/info")


def fetch_hyphae_relay_config(ip: str) -> Optional[Dict]:
    """Fetch relay configuration from Hyphae /api/relay/config."""
    return _get_json(ip, "/api/relay/config")


def fetch_hyphae_config_modes(ip: str) -> Optional[Dict]:
    """Fetch the device's Enabled/Operation mode by parsing the /hyphae-config page.

    Neither mode is exposed as JSON, so we read the config page (which shows both
    unconditionally) and map the labels back to the DB's integer codes.
    """
    return _parse_hyphae_config_modes(_get_text(ip, "/hyphae-config"))


def fetch_hyphae_relay_state(ip: str) -> Optional[List]:
    """Fetch relay states from Hyphae /api/relay/state."""
    return _get_json(ip, "/api/relay/state")


def fetch_hyphae_relay_schedule(ip: str) -> Optional[Dict]:
    """Fetch relay schedule by parsing the device's config page.

    The /api/relay/schedule JSON endpoint is POST-only (GET returns 400), so the
    current on/off duty-cycle minutes are read from the /hyphae-relay-sched page.
    """
    return _parse_hyphae_schedule_html(_get_text(ip, "/hyphae-relay-sched"))


def fetch_hyphae_relay_dynamic(ip: str) -> Optional[Dict]:
    """Fetch dynamic-control thresholds by parsing the device's config page.

    The /api/relay/thresholds JSON endpoint is POST-only (GET returns 400), so the
    current thresholds are read from the /hyphae-relay-dynam page.
    """
    return _parse_hyphae_dynamic_html(_get_text(ip, "/hyphae-relay-dynam"))


def store_complete_spore_device_data(ip: str, room_id) -> Dict:
    """Fetch data from a Spore device, register it in the DB, and return result."""
    from storage.tables.device_spore import (
        create_device_spore,
        get_device_spore_by_hostname,
        normalize_device_host,
    )

    errors = []

    # Guard against adding the same device twice (hostname is the stable identity).
    host = normalize_device_host(ip)
    if get_device_spore_by_hostname(host):
        return {
            "success": False,
            "errors": [f"A Spore with hostname {host} is already in the list."],
        }

    info = fetch_spore_info(ip) or {}
    config = fetch_spore_config(ip) or {}
    readings = fetch_spore_readings_latest(ip)

    device_name = (
        config.get("device_name")
        or info.get("device_name")
        or ip.split(":")[0]  # fall back to the hostname (e.g. spore-1234.local)
    )
    mac = info.get("mac_address") or discover_mac_address(ip) or _placeholder_mac(ip)
    firmware = info.get("firmware_version") or config.get("firmware_version", "")

    try:
        device_id = create_device_spore(
            room_id=int(room_id),
            device_name=device_name,
            hostname=ip,
            mac_address=mac,
            firmware_version=firmware,
            is_online=1 if info else 0,
        )
        return {
            "success": True,
            "data": {"config": config, "info": info, "readings": readings},
            "device_id": device_id,
        }
    except Exception as e:
        errors.append(str(e))
        return {"success": False, "errors": errors}


def store_complete_hyphae_device_data(ip: str, room_id, pin=None) -> Dict:
    """Fetch data from a Hyphae device, register it in the DB, and return result."""
    from storage.tables.device_hyphae import (
        create_device_hyphae,
        get_device_hyphae_by_hostname,
    )
    from storage.tables.device_spore import normalize_device_host

    errors = []

    # Guard against adding the same device twice (hostname is the stable identity).
    host = normalize_device_host(ip)
    if get_device_hyphae_by_hostname(host):
        return {
            "success": False,
            "errors": [f"A Hyphae with hostname {host} is already in the list."],
        }

    info = fetch_hyphae_config(ip) or {}
    relay = fetch_hyphae_relay_config(ip)

    device_name = info.get("device_name") or ip.split(":")[0]  # fall back to hostname
    mac = info.get("mac_address") or discover_mac_address(ip) or _placeholder_mac(ip)
    firmware = info.get("firmware_version", "")

    try:
        device_id = create_device_hyphae(
            room_id=int(room_id),
            device_name=device_name,
            hostname=ip,
            mac_address=mac,
            firmware_version=firmware,
            is_online=1 if info else 0,
        )
        if pin:
            store_device_pin(device_id, "hyphae", pin)
        return {
            "success": True,
            "data": {"config": info, "relay_config": relay or {}},
            "device_id": device_id,
        }
    except Exception as e:
        errors.append(str(e))
        return {"success": False, "errors": errors}


def refresh_spore_device_data(device_id, ip: str) -> Dict:
    """Re-poll an existing Spore device and update its status/info in the DB.

    Unlike store_complete_spore_device_data() (the *add* path), this updates a
    device that already exists: it contacts the device, refreshes online status,
    last-seen time, and any changed name/firmware. Marks offline if unreachable.
    """
    from storage.tables.device_spore import (
        set_device_online,
        update_device_spore,
        update_device_status,
    )

    info = fetch_spore_info(ip)
    config = fetch_spore_config(ip) or {}
    reachable = info is not None

    if not reachable:
        # Keep last_update meaning "last successful contact" (see set_device_online).
        set_device_online(device_id, 0)
        return {"success": False, "errors": [f"{ip} unreachable."]}

    # Online: bump is_online + last_update, then sync any changed metadata.
    update_device_status(device_id, 1)
    device_name = config.get("device_name") or info.get("device_name")
    firmware = info.get("firmware_version") or config.get("firmware_version")
    if device_name or firmware:
        update_device_spore(
            device_id,
            device_name=device_name or None,
            firmware_version=firmware or None,
        )
    return {"success": True, "errors": []}


def refresh_hyphae_device_data(device_id, ip: str) -> Dict:
    """Re-poll an existing Hyphae device and update its status/info in the DB.

    Counterpart to refresh_spore_device_data() for Hyphae controllers.
    """
    from storage.tables.device_hyphae import (
        set_device_online,
        update_device_hyphae,
        update_device_status,
    )

    info = fetch_hyphae_config(ip)
    reachable = info is not None

    if not reachable:
        set_device_online(device_id, 0)
        return {"success": False, "errors": [f"{ip} unreachable."]}

    update_device_status(device_id, 1)
    device_name = info.get("device_name")
    firmware = info.get("firmware_version")
    if device_name or firmware:
        update_device_hyphae(
            device_id,
            device_name=device_name or None,
            firmware_version=firmware or None,
        )
    return {"success": True, "errors": []}


# Hostname validation pattern. Accepts an mDNS hostname (spore-1234.local),
# a bare IP, or either with an optional :port (e.g. localhost:8001 for a
# local simulator such as RoboSims).
_HOST_PATTERN = re.compile(r"^[A-Za-z0-9.\-]+(?::\d{1,5})?$")


def _room_options() -> List[Dict]:
    """Get grow rooms as select options."""
    try:
        rooms = get_all_grow_rooms()
        return {r["room_id"]: r["room_name"] for r in rooms}
    except Exception:
        return {}


def _format_last_seen(value) -> str:
    """Format a timestamp or datetime string for display (honors 12/24h pref)."""
    if not value:
        return "Never"
    return fmt_datetime(value, fallback="Never")


def _online_badge(is_online) -> None:
    """Render an online/offline badge inline.

    Uses Quasar's fixed green/red palette rather than an inline color so the
    status stays unambiguous whatever accent the user picks for the theme. (An
    inline background-color loses to Quasar's `bg-primary !important` class, which
    is why the badge previously took on the theme color.)
    """
    online = bool(is_online)
    ui.badge(
        "Online" if online else "Offline",
        color="green" if online else "red",
    )


# ---------------------------------------------------------------------------
# Page entry point
# ---------------------------------------------------------------------------


@ui.page("/devices")
def devices_page():
    """Main devices management page."""
    user = app.storage.user
    if not user.get("user_id"):
        ui.navigate.to("/login")
        return

    page_layout("Devices")
    back_to_dashboard()
    colors = get_colors()

    # Shared state for device detail
    selected_device = {"type": None, "data": None}

    with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-4"):
        # --- Header with discover button ---
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Devices").classes("text-h4")
            discover_btn = ui.button("Discover Devices", icon="wifi_find").props(
                "outline"
            )

        # --- Stat cards ---
        stat_cards_container = ui.row().classes("w-full gap-4 flex-wrap")

        @ui.refreshable
        def stat_cards():
            stat_cards_container.clear()
            with stat_cards_container:
                spore_devices = _safe_get_spore_devices()
                hyphae_devices = _safe_get_hyphae_devices()
                spore_online = sum(1 for d in spore_devices if d.get("is_online"))
                hyphae_online = sum(1 for d in hyphae_devices if d.get("is_online"))
                total_offline = (
                    len(spore_devices)
                    + len(hyphae_devices)
                    - spore_online
                    - hyphae_online
                )

                _stat_card(
                    "Spore Online",
                    str(spore_online),
                    "sensors",
                    STATUS_COLORS["online"],
                    colors,
                )
                _stat_card(
                    "Hyphae Online",
                    str(hyphae_online),
                    "device_hub",
                    STATUS_COLORS["online"],
                    colors,
                )
                _stat_card(
                    "Devices Offline",
                    str(total_offline),
                    "warning",
                    STATUS_COLORS["offline"],
                    colors,
                )

        stat_cards()

        # --- Tabs (Spore / Hyphae). Each device row expands inline to reveal its
        #     detail tabs, so there is no separate "Device Detail" tab. ---
        with ui.tabs().classes("w-full") as tabs:
            spore_tab = ui.tab("Spore Devices", icon="sensors")
            hyphae_tab = ui.tab("Hyphae Devices", icon="device_hub")

        with ui.tab_panels(tabs, value=spore_tab).classes("w-full"):
            # =============================================================
            # SPORE TAB
            # =============================================================
            with ui.tab_panel(spore_tab):
                _build_spore_panel(colors, selected_device, stat_cards)

            # =============================================================
            # HYPHAE TAB
            # =============================================================
            with ui.tab_panel(hyphae_tab):
                _build_hyphae_panel(colors, selected_device, stat_cards)

        # Wire discovery button now that stat_cards is defined
        discover_btn.on(
            "click",
            lambda: _run_mdns_discovery(colors, stat_cards, selected_device),
        )

        # Periodically re-read device status from the DB so the tables + stat cards
        # reflect what polling has recorded, without a manual page reload. Online
        # status lives in the is_online flag (single source of truth); the poller
        # keeps it current, this just surfaces it.
        def _auto_refresh_status():
            # Always keep the stat cards current. Only rebuild a device list when
            # none of its rows are expanded, so a periodic refresh never collapses
            # a detail panel the user is actively viewing.
            sc = selected_device.get("_stat_cards")
            if sc is not None:
                try:
                    sc.refresh()
                except Exception:
                    pass
            for table_key, open_key in (
                ("_spore_table", "_open_spore"),
                ("_hyphae_table", "_open_hyphae"),
            ):
                ref = selected_device.get(table_key)
                if ref is not None and not selected_device.get(open_key):
                    try:
                        ref.refresh()
                    except Exception:
                        pass

        ui.timer(20.0, _auto_refresh_status)


# ---------------------------------------------------------------------------
# Stat card helper
# ---------------------------------------------------------------------------


def _stat_card(label: str, value: str, icon: str, accent: str, colors: dict):
    with ui.card().classes("p-4 flex-1 min-w-48"):
        with ui.row().classes("items-center gap-2"):
            ui.icon(icon, size="sm").style(f"color: {accent}")
            ui.label(label).classes("text-subtitle2")
        ui.label(value).classes("text-h4 q-mt-sm")


# ---------------------------------------------------------------------------
# Safe data fetchers
# ---------------------------------------------------------------------------


def _safe_get_spore_devices() -> List[Dict]:
    try:
        return get_all_device_spore()
    except Exception:
        return []


def _safe_get_hyphae_devices() -> List[Dict]:
    try:
        return get_all_device_hyphae()
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Expandable device rows (replace the old table + separate Device Detail tab)
# ---------------------------------------------------------------------------

# CSS grid column templates shared by each list's header bar and its rows so the
# columns line up. The leading expand chevron sits outside the grid.
_SPORE_GRID = "grid-template-columns: 1.6fr 1.8fr 1.2fr 0.9fr 1.4fr;"
_HYPHAE_GRID = "grid-template-columns: 1.5fr 1.6fr 1.1fr 1fr 0.9fr 1.3fr;"


def _row_grid(template: str):
    """A grid element holding one row of aligned device columns."""
    return ui.element("div").style(
        f"display: grid; {template} align-items: center; gap: 0.75rem; "
        "flex: 1 1 0; min-width: 0;"
    )


def _device_list_header(labels: List[str], template: str):
    """Column-label bar shown above an expandable device list."""
    with ui.row().classes("w-full items-center gap-2 px-3 q-mt-sm no-wrap"):
        ui.element("div").style("width: 1.5rem; flex: 0 0 auto;")  # chevron spacer
        with _row_grid(template):
            for lbl in labels:
                ui.label(lbl).classes("text-caption text-weight-bold text-muted")


def _expandable_device_row(device, template, header_cells, detail_render, open_rows):
    """Render one device as a click-to-expand row.

    The header shows the device's summary columns with a leading chevron (in
    place of the old selection checkbox). Expanding lazily renders the full
    detail — the same tabbed view that used to live in the Device Detail tab.
    `open_rows` tracks which device_ids are expanded so the auto-refresh timer
    can avoid rebuilding (and collapsing) a list the user is viewing.
    """
    device_id = device.get("device_id")
    state = {"rendered": False}

    with ui.card().classes("w-full p-0"):
        header = ui.row().classes(
            "w-full items-center gap-2 px-3 py-2 cursor-pointer no-wrap"
        )
        with header:
            chevron = ui.icon("chevron_right", size="sm").classes("text-muted")
            with _row_grid(template):
                header_cells(device)
        body = ui.column().classes("w-full px-3 pb-3 gap-3")
        body.set_visibility(False)

    def _toggle():
        if device_id in open_rows:
            open_rows.discard(device_id)
            chevron.props("name=chevron_right")
            body.set_visibility(False)
            return
        open_rows.add(device_id)
        chevron.props("name=expand_more")
        body.set_visibility(True)
        if not state["rendered"]:
            with body:
                detail_render(device)
            state["rendered"] = True

    header.on("click", _toggle)


def _spore_header_cells(device: Dict):
    """Summary columns for a Spore row (order must match _SPORE_GRID)."""
    ui.label(device.get("device_name") or "—").classes("text-weight-medium ellipsis")
    ui.label(device.get("hostname") or "—").classes("text-caption ellipsis")
    ui.label(device.get("room_name") or "Unassigned").classes("text-caption ellipsis")
    _online_badge(device.get("is_online"))
    ui.label(_format_last_seen(device.get("last_update"))).classes(
        "text-caption ellipsis"
    )


def _hyphae_header_cells(device: Dict):
    """Summary columns for a Hyphae row (order must match _HYPHAE_GRID)."""
    mode_map = {0: "Offline", 1: "Testing", 2: "Running"}
    ui.label(device.get("device_name") or "—").classes("text-weight-medium ellipsis")
    ui.label(device.get("hostname") or "—").classes("text-caption ellipsis")
    ui.label(device.get("room_name") or "Unassigned").classes("text-caption ellipsis")
    mode_text = mode_map.get(device.get("mode_enabled", 0), "Unknown")
    mode_color = (
        "green"
        if mode_text == "Running"
        else "orange"
        if mode_text == "Testing"
        else "grey"
    )
    ui.badge(mode_text, color=mode_color)
    _online_badge(device.get("is_online"))
    ui.label(_format_last_seen(device.get("last_update"))).classes(
        "text-caption ellipsis"
    )


# ---------------------------------------------------------------------------
# SPORE panel
# ---------------------------------------------------------------------------


def _build_spore_panel(colors, selected_device, stat_cards):
    """Build the Spore devices tab content (expandable row per device)."""
    open_rows: set = set()
    selected_device["_open_spore"] = open_rows

    @ui.refreshable
    def spore_table():
        # Rebuilt rows start collapsed, so reset the open-row set here. The
        # auto-refresh timer relies on this to know nothing is expanded.
        open_rows.clear()

        devices = _safe_get_spore_devices()
        if not devices:
            ui.label("No Spore devices found. Add a device to get started.").classes(
                "text-muted q-pa-md"
            )
            return

        _device_list_header(
            ["Name", "Hostname", "Room", "Status", "Last Seen"], _SPORE_GRID
        )
        for d in devices:
            _expandable_device_row(
                d,
                _SPORE_GRID,
                _spore_header_cells,
                lambda dev: _render_spore_detail(dev, colors, selected_device),
                open_rows,
            )

    # Buttons row
    with ui.row().classes("w-full items-center gap-2 q-mb-md"):
        ui.button(
            "Add Spore",
            icon="add",
            on_click=lambda: _open_add_spore_dialog(spore_table, stat_cards),
        ).props("color=primary")

        async def refresh_spore():
            devices = _safe_get_spore_devices()
            if not devices:
                ui.notify("No Spore devices to refresh.", type="info")
                return
            # Each device fetch is blocking (requests, up to ~5s per call, and an
            # unreachable device burns the full timeout). Run them off the event
            # loop and concurrently so the websocket heartbeat keeps flowing
            # (otherwise the UI shows "connection lost") and N devices don't add up.
            progress = ui.notification(
                f"Refreshing {len(devices)} Spore device(s)…",
                spinner=True,
                timeout=None,
            )
            try:
                results = await asyncio.gather(
                    *(
                        run.io_bound(
                            refresh_spore_device_data, d["device_id"], d["hostname"]
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
            spore_table.refresh()
            stat_cards.refresh()
            if errors == 0:
                ui.notify(f"Refreshed {success} Spore device(s).", type="positive")
            else:
                ui.notify(f"Refreshed {success}, failed {errors}.", type="warning")

        ui.button("Refresh All", icon="refresh", on_click=refresh_spore).props(
            "outline"
        )
        ui.button(
            "Export CSV", icon="download", on_click=lambda: _export_devices_csv("spore")
        ).props("outline")
        ui.button(
            "Import CSV",
            icon="upload",
            on_click=lambda: _open_import_csv_dialog("spore", spore_table, stat_cards),
        ).props("outline")

    spore_table()

    # Expose refreshers so the detail panel (e.g. Remove Device) can update the list.
    selected_device["_spore_table"] = spore_table
    selected_device["_stat_cards"] = stat_cards


# ---------------------------------------------------------------------------
# HYPHAE panel
# ---------------------------------------------------------------------------


def _build_hyphae_panel(colors, selected_device, stat_cards):
    """Build the Hyphae devices tab content (expandable row per device)."""
    open_rows: set = set()
    selected_device["_open_hyphae"] = open_rows

    @ui.refreshable
    def hyphae_table():
        # Rebuilt rows start collapsed, so reset the open-row set here.
        open_rows.clear()

        devices = _safe_get_hyphae_devices()
        if not devices:
            ui.label("No Hyphae devices found. Add a device to get started.").classes(
                "text-muted q-pa-md"
            )
            return

        _device_list_header(
            ["Name", "Hostname", "Room", "Mode", "Status", "Last Seen"], _HYPHAE_GRID
        )
        for d in devices:
            _expandable_device_row(
                d,
                _HYPHAE_GRID,
                _hyphae_header_cells,
                lambda dev: _render_hyphae_detail(dev, colors, selected_device),
                open_rows,
            )

    with ui.row().classes("w-full items-center gap-2 q-mb-md"):
        ui.button(
            "Add Hyphae",
            icon="add",
            on_click=lambda: _open_add_hyphae_dialog(hyphae_table, stat_cards),
        ).props("color=primary")

        async def refresh_hyphae():
            devices = _safe_get_hyphae_devices()
            if not devices:
                ui.notify("No Hyphae devices to refresh.", type="info")
                return
            # Blocking fetches off the event loop, concurrently — see refresh_spore.
            progress = ui.notification(
                f"Refreshing {len(devices)} Hyphae device(s)…",
                spinner=True,
                timeout=None,
            )
            try:
                results = await asyncio.gather(
                    *(
                        run.io_bound(
                            refresh_hyphae_device_data, d["device_id"], d["hostname"]
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
            hyphae_table.refresh()
            stat_cards.refresh()
            if errors == 0:
                ui.notify(f"Refreshed {success} Hyphae device(s).", type="positive")
            else:
                ui.notify(f"Refreshed {success}, failed {errors}.", type="warning")

        ui.button("Refresh All", icon="refresh", on_click=refresh_hyphae).props(
            "outline"
        )
        ui.button(
            "Export CSV",
            icon="download",
            on_click=lambda: _export_devices_csv("hyphae"),
        ).props("outline")
        ui.button(
            "Import CSV",
            icon="upload",
            on_click=lambda: _open_import_csv_dialog(
                "hyphae", hyphae_table, stat_cards
            ),
        ).props("outline")

    hyphae_table()

    # Expose refreshers so the detail panel (e.g. Remove Device) can update the list.
    selected_device["_hyphae_table"] = hyphae_table
    selected_device["_stat_cards"] = stat_cards


# ---------------------------------------------------------------------------
# Add device dialogs
# ---------------------------------------------------------------------------


def _open_add_spore_dialog(spore_table_refresh, stat_cards_refresh):
    """Open the Add Spore device dialog."""
    with ui.dialog() as dialog, ui.card().classes("min-w-80"):
        ui.label("Add Spore Device").classes("text-h6 q-mb-md")

        ip_input = ui.input(
            label="Hostname",
            placeholder="spore-1234.local or 192.168.1.100:8080",
            validation={
                "Invalid hostname": lambda v: (
                    bool(_HOST_PATTERN.match(v)) if v else False
                )
            },
        ).classes("w-full")

        rooms = _room_options()
        room_select = ui.select(
            options=rooms,
            label="Grow Room",
            with_input=True,
        ).classes("w-full")

        ui.label(
            "Enter the device hostname (e.g. spore-1234.local) and assign it to a room."
        ).classes("text-muted text-caption q-mt-sm")

        with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dialog.close).props("flat")

            def add_spore():
                ip = ip_input.value
                room_id = room_select.value
                if not ip or not _HOST_PATTERN.match(ip):
                    ui.notify("Please enter a valid hostname.", type="negative")
                    return
                if not room_id:
                    ui.notify("Please select a grow room.", type="negative")
                    return

                try:
                    result = store_complete_spore_device_data(ip, room_id)
                    if result.get("success"):
                        name = (
                            result.get("data", {})
                            .get("config", {})
                            .get("device_name", f"Spore-{ip.split('.')[-1]}")
                        )
                        ui.notify(
                            f'Spore device "{name}" added successfully.',
                            type="positive",
                        )
                        dialog.close()
                        spore_table_refresh.refresh()
                        stat_cards_refresh.refresh()
                    else:
                        errors = "; ".join(result.get("errors", ["Unknown error"]))
                        ui.notify(f"Error: {errors}", type="negative")
                except Exception as exc:
                    ui.notify(f"Error adding device: {exc}", type="negative")

            ui.button("Add Device", icon="add", on_click=add_spore).props(
                "color=primary"
            )

    dialog.open()


def _open_add_hyphae_dialog(hyphae_table_refresh, stat_cards_refresh):
    """Open the Add Hyphae device dialog."""
    with ui.dialog() as dialog, ui.card().classes("min-w-80"):
        ui.label("Add Hyphae Device").classes("text-h6 q-mb-md")

        ip_input = ui.input(
            label="Hostname",
            placeholder="spore-1234.local or 192.168.1.100:8080",
            validation={
                "Invalid hostname": lambda v: (
                    bool(_HOST_PATTERN.match(v)) if v else False
                )
            },
        ).classes("w-full")

        pin_input = ui.input(
            label="Device PIN",
            placeholder="5-digit PIN",
            password=True,
            password_toggle_button=True,
        ).classes("w-full")

        rooms = _room_options()
        room_select = ui.select(
            options=rooms,
            label="Grow Room",
            with_input=True,
        ).classes("w-full")

        ui.label("Enter the device IP, PIN, and assign it to a room.").classes(
            "text-muted text-caption q-mt-sm"
        )

        with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dialog.close).props("flat")

            def add_hyphae():
                ip = ip_input.value
                pin = pin_input.value
                room_id = room_select.value
                if not ip or not _HOST_PATTERN.match(ip):
                    ui.notify("Please enter a valid hostname.", type="negative")
                    return
                if not room_id:
                    ui.notify("Please select a grow room.", type="negative")
                    return

                try:
                    result = store_complete_hyphae_device_data(ip, room_id, pin)
                    if result.get("success"):
                        name = (
                            result.get("data", {})
                            .get("config", {})
                            .get("device_name", f"Hyphae-{ip.split('.')[-1]}")
                        )
                        relay_count = len(
                            result.get("data", {})
                            .get("relay_config", {})
                            .get("relays", [])
                        )
                        ui.notify(
                            f'Hyphae device "{name}" added with {relay_count} relays.',
                            type="positive",
                        )
                        dialog.close()
                        hyphae_table_refresh.refresh()
                        stat_cards_refresh.refresh()
                    else:
                        errors = "; ".join(result.get("errors", ["Unknown error"]))
                        ui.notify(f"Error: {errors}", type="negative")
                except Exception as exc:
                    ui.notify(f"Error adding device: {exc}", type="negative")

            ui.button("Add Device", icon="add", on_click=add_hyphae).props(
                "color=primary"
            )

    dialog.open()


# ---------------------------------------------------------------------------
# Detail-panel data source helper (DB-first, live on demand)
# ---------------------------------------------------------------------------


def _panel_status_line(state: Dict, *, as_of=None, stored=True):
    """Render a panel's data-source badge/as-of without a refresh button.

    Used by the Hyphae detail panels that are refreshed together by the single
    "Refresh from device" button at the top of the Hyphae detail view.
    """
    with ui.row().classes("w-full items-center gap-2 q-mb-sm"):
        if state.get("fetched"):
            if state.get("live"):
                ui.badge("Live from device", color="green")
            else:
                ui.badge("Device unreachable", color="red")
                if stored and as_of:
                    ui.label(f"showing stored data from {as_of}").classes(
                        "text-caption text-muted"
                    )
        elif stored:
            ui.badge("Stored", color="blue")
            ui.label(f"as of {as_of}" if as_of else "from database").classes(
                "text-caption text-muted"
            )
        else:
            ui.badge("Not stored", color="grey")
            ui.label("fetched from device on demand").classes("text-caption text-muted")


def _panel_source_row(state: Dict, fetch_fn, body, *, as_of=None, stored=True):
    """Render the data-source line + an on-demand "Refresh from device" button.

    Detail panels read from the database by default so simply viewing a device
    costs no network traffic. This row tells the user where the shown data came
    from (stored vs. just-fetched-live) and lets them pull a fresh copy on
    demand. The live fetch runs off the event loop so a slow/unreachable device
    can't freeze the UI.

    Args:
        state: Per-panel dict holding {"live", "fetched"}; `body.refresh()` re-reads it.
        fetch_fn: Zero-arg callable that performs the blocking device fetch.
        body: The @ui.refreshable that renders the panel body.
        as_of: Human-readable timestamp of the stored data (DB-first panels).
        stored: False for panels with no persisted copy (diagnostics, Hyphae
            config) — those are live-only and shown blank until refreshed.
    """
    with ui.row().classes("w-full items-center gap-2 q-mb-sm"):
        if state.get("fetched"):
            if state.get("live"):
                ui.badge("Live from device", color="green")
            else:
                ui.badge("Device unreachable", color="red")
                if stored and as_of:
                    ui.label(f"showing stored data from {as_of}").classes(
                        "text-caption text-muted"
                    )
        elif stored:
            ui.badge("Stored", color="blue")
            ui.label(f"as of {as_of}" if as_of else "from database").classes(
                "text-caption text-muted"
            )
        else:
            ui.badge("Not stored", color="grey")
            ui.label("fetched from device on demand").classes("text-caption text-muted")

        ui.space()

        async def _do_refresh():
            n = ui.notification("Fetching from device…", spinner=True, timeout=None)
            try:
                state["live"] = await run.io_bound(fetch_fn)
            finally:
                n.dismiss()
            state["fetched"] = True
            body.refresh()
            if state["live"]:
                ui.notify("Updated from device.", type="positive")
            else:
                ui.notify("Device unreachable.", type="warning")

        ui.button(
            "Refresh from device", icon="cloud_download", on_click=_do_refresh
        ).props("outline dense")


# ---------------------------------------------------------------------------
# SPORE detail
# ---------------------------------------------------------------------------


def _render_spore_detail(device: Dict, colors: dict, selected_device: Dict = None):
    """Render the full detail panel for a Spore device."""
    ui.label(f"{device.get('device_name', 'Spore Device')}").classes("text-h5")
    _online_badge(device.get("is_online"))

    with ui.tabs().classes("w-full") as dtabs:
        tab_readings = ui.tab("Readings", icon="thermostat")
        tab_diag = ui.tab("Diagnostics", icon="monitor_heart")
        tab_mgmt = ui.tab("Management", icon="build")

    with ui.tab_panels(dtabs, value=tab_readings).classes("w-full"):
        # --- Readings ---
        with ui.tab_panel(tab_readings):
            _spore_readings_panel(device, colors)

        # --- Diagnostics ---
        with ui.tab_panel(tab_diag):
            _spore_diagnostics_panel(device, colors)

        # --- Management (settings, PIN, OTA, remove) ---
        with ui.tab_panel(tab_mgmt):
            _device_management_panel(device, "spore", colors, selected_device)


def _spore_db_reading(device: Dict):
    """Build a Spore reading view from the database (no device call).

    Temp/humidity/CO2 come from readings_spore (filled by the ~60s poller).
    Spore has no pressure sensor, so pressure is the linked Hyphae's latest
    stored pressure when one is associated. Returns (reading, as_of) where
    `reading` uses the same keys as the live /api/readings/latest payload, or
    (None, None) when nothing has been polled yet.
    """
    device_id = device.get("device_id")
    if not device_id:
        return None, None
    row = get_latest_spore_reading(device_id)
    if not row:
        return None, None

    pressure = None
    hyphae_id = device.get("hyphae_id")
    if hyphae_id:
        p = get_latest_pressure(hyphae_id)
        if p:
            pressure = p.get("pressure_hpa")

    reading = {
        "temperature": row.get("temp"),
        "humidity": row.get("humidity"),
        "co2": row.get("co2"),
        "pressure": pressure,
    }
    return reading, _format_last_seen(row.get("reading_ts"))


def _spore_readings_panel(device: Dict, colors: dict):
    """Show latest sensor readings for a Spore device (DB-first, live on demand)."""
    state = {"live": None, "fetched": False}

    @ui.refreshable
    def body():
        if state["live"]:
            readings = state["live"]
            # /api/readings/latest returns a unix timestamp (0 pre-clock-sync).
            try:
                ts = int(readings.get("timestamp", 0))
            except (TypeError, ValueError):
                ts = 0
            as_of = fmt_datetime(ts) if ts > 0 else "device clock not synced"
        else:
            readings, as_of = _spore_db_reading(device)

        _panel_source_row(
            state,
            lambda: fetch_spore_readings_latest(device.get("hostname", "")),
            body,
            as_of=as_of,
        )

        if not readings:
            ui.label(
                "No stored readings yet. Click “Refresh from device” to fetch live."
            ).classes("text-muted")
            return

        temp_value, temp_unit = _fmt_temp(readings.get("temperature"), _temp_pref())

        with ui.row().classes("w-full gap-4 flex-wrap"):
            _reading_card(
                "Temperature",
                temp_value,
                temp_unit,
                "thermostat",
                colors["primary"],
            )
            _reading_card(
                "Humidity",
                _fmt_reading(readings.get("humidity"), 1),
                "%",
                "water_drop",
                colors["primary"],
            )
            _reading_card(
                "CO2",
                _fmt_reading(readings.get("co2"), 0),
                "ppm",
                "co2",
                colors["primary"],
            )
            _reading_card(
                "Pressure",
                _fmt_reading(readings.get("pressure"), 0),
                "hPa",
                "speed",
                colors["primary"],
            )

    body()


def _reading_card(label: str, value, unit: str, icon: str, accent: str):
    """Small card showing a single sensor reading."""
    with ui.card().classes("p-4 flex-1 min-w-40 text-center"):
        ui.icon(icon, size="md").style(f"color: {accent}")
        display = f"{value} {unit}" if value != "N/A" else "N/A"
        ui.label(display).classes("text-h5 q-mt-xs")
        ui.label(label).classes("text-caption text-muted")


def _fmt_reading(value, digits: int = 1) -> str:
    """Format a numeric sensor reading, or 'N/A' if missing/non-numeric."""
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "N/A"


def _fmt_uptime(seconds) -> str:
    """Format an uptime given in seconds as 'Hh Mm Ss'."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "N/A"
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}h {minutes}m {secs}s"


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


def _spore_hyphae_association_card(device: Dict):
    """Associate a Spore with a Hyphae controller. Shown in the Management tab."""
    with ui.card().classes("w-full p-4 q-mb-md"):
        ui.label("Hyphae Association").classes("text-h6 q-mb-sm")

        hyphae_devices = _safe_get_hyphae_devices()
        hyphae_opts = {0: "— None —"}
        for h in hyphae_devices:
            hyphae_opts[h["device_id"]] = h.get(
                "device_name", f"Hyphae #{h['device_id']}"
            )

        current_hyphae = device.get("hyphae_id") or 0
        spore_id = device.get("device_id")

        assoc_select = ui.select(
            options=hyphae_opts,
            value=current_hyphae,
            label="Associated Hyphae Controller",
        ).classes("w-full")

        def _save_association():
            new_hyphae_id = assoc_select.value
            if new_hyphae_id and new_hyphae_id != 0:
                link_spore_to_hyphae(spore_id, new_hyphae_id)
                hname = hyphae_opts.get(new_hyphae_id, f"#{new_hyphae_id}")
                ui.notify(f"Linked to {hname}", type="positive")
            else:
                unlink_spore_from_hyphae(spore_id)
                ui.notify("Hyphae association removed", type="info")

        ui.button("Save Association", icon="link", on_click=_save_association).props(
            "outline dense"
        ).classes("q-mt-sm")


def _spore_pressure_source_card(device: Dict):
    """Choose the ambient-pressure source for a Spore. Shown in the Management tab.

    Lets Mycelium relay OpenWeatherMap pressure to Spores that have no Hyphae
    supplying local barometric pressure.
    """
    spore_id = device.get("device_id")
    has_hyphae = bool(device.get("hyphae_id"))
    with ui.card().classes("w-full p-4 q-mb-md"):
        ui.label("Ambient Pressure Source").classes("text-h6 q-mb-sm")

        if has_hyphae:
            ui.label(
                "Pressure is supplied by the linked Hyphae controller. "
                "Unlink the Hyphae above to use weather data instead."
            ).classes("text-muted")

        weather_switch = ui.switch(
            "Send OpenWeatherMap pressure to this Spore",
            value=bool(device.get("weather_pressure_enabled")),
        )
        if has_hyphae:
            weather_switch.props("disable")

        altitude_input = (
            ui.number(
                label="Device altitude (meters)",
                value=device.get("altitude_m"),
                min=-500,
                max=9000,
                step=1,
            )
            .classes("w-full")
            .tooltip(
                "Used to approximate local pressure from sea-level pressure when "
                "OpenWeatherMap does not report ground-level pressure. Leave blank "
                "to only relay pressure when the weather service provides grnd_level."
            )
        )

        def _save_weather_pressure():
            altitude = altitude_input.value
            update_spore_weather_pressure(
                spore_id,
                1 if weather_switch.value else 0,
                float(altitude) if altitude is not None else None,
            )
            ui.notify("Pressure source settings saved", type="positive")

        ui.button(
            "Save Pressure Source", icon="cloud", on_click=_save_weather_pressure
        ).props("outline dense").classes("q-mt-sm")


def _spore_diagnostics_panel(device: Dict, colors: dict):
    """Show Spore diagnostics from /api/diagnostics (system, sensors, errors).

    Diagnostics are not persisted (by design — no diagnostics table), so this
    panel never fetches automatically. It stays blank until the user clicks
    "Refresh from device", keeping page views off the network.
    """
    state = {"live": None, "fetched": False}

    @ui.refreshable
    def body():
        _panel_source_row(
            state,
            lambda: fetch_spore_info(device.get("hostname", "")),
            body,
            stored=False,
        )
        _spore_diagnostics_body(device, state)

    body()


def _spore_diagnostics_body(device: Dict, state: Dict):
    """Render the diagnostics cards once the device has been queried."""
    info = state.get("live")
    if not info:
        if state.get("fetched"):
            ui.label("Could not fetch diagnostics. Device may be offline.").classes(
                "text-muted"
            )
        else:
            ui.label(
                "Diagnostics are read live from the device and are not stored. "
                "Click “Refresh from device” to query it."
            ).classes("text-muted")
        return

    system = info.get("system", {})
    sensors = info.get("sensors", {})
    errors = info.get("errors", {})

    # --- System ---
    with ui.card().classes("w-full p-4"):
        ui.label("System").classes("text-subtitle1 text-weight-bold q-mb-sm")
        _kv("Uptime", _fmt_uptime(system.get("uptime_sec")))
        _kv("Free Memory", f"{system.get('heap_free_kb', 'N/A')} KB")
        _kv("Min Free Memory", f"{system.get('heap_min_free_kb', 'N/A')} KB")
        _kv("WiFi Signal", f"{system.get('wifi_rssi_dbm', 'N/A')} dBm")

    # --- Sensors ---
    with ui.card().classes("w-full p-4 q-mt-md"):
        ui.label("Sensors").classes("text-subtitle1 text-weight-bold q-mb-sm")
        s_temp, s_unit = _fmt_temp(sensors.get("temperature"), _temp_pref())
        _kv("Data Valid", "Yes" if sensors.get("valid") else "No")
        _kv("CO2", f"{_fmt_reading(sensors.get('co2'), 0)} ppm")
        _kv("Temperature", f"{s_temp} {s_unit}")
        _kv("Humidity", f"{_fmt_reading(sensors.get('humidity'), 1)} %")

    # --- Error history ---
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


# ---------------------------------------------------------------------------
# HYPHAE detail
# ---------------------------------------------------------------------------


def _render_hyphae_detail(device: Dict, colors: dict, selected_device: Dict = None):
    """Render the full detail panel for a Hyphae device."""
    mode_map = {0: "Offline", 1: "Testing", 2: "Running"}
    op_map = {0: "Schedule", 1: "Dynamic"}

    # Each data panel registers (state, fetch_fn, body) here so the single
    # "Refresh from device" button can pull every page in one pass. The values
    # below (system info, relay config, schedule, thresholds) rarely change once
    # set, so they share this button; Relay State keeps its own (it changes
    # often) and is refreshed by this button too.
    panels: List = []

    def register(state, fetch_fn, body):
        panels.append((state, fetch_fn, body))

    async def _refresh_all():
        if not panels:
            return
        note = ui.notification("Fetching from device…", spinner=True, timeout=None)
        ok = 0
        try:
            # Fetch sequentially (not concurrently) to stay gentle on the device.
            for state, fetch_fn, body in panels:
                try:
                    state["live"] = await run.io_bound(fetch_fn)
                except Exception:
                    state["live"] = None
                state["fetched"] = True
                if state["live"]:
                    ok += 1
                body.refresh()
        finally:
            note.dismiss()
        if ok == len(panels):
            ui.notify(f"Updated {ok} page(s) from device.", type="positive")
        elif ok:
            ui.notify(
                f"Updated {ok}/{len(panels)} page(s); some were unreachable.",
                type="warning",
            )
        else:
            ui.notify("Device unreachable.", type="warning")

    ui.label(f"{device.get('device_name', 'Hyphae Device')}").classes("text-h5")

    # Status + mode badges. mode_enabled/mode_operation live on the DB row, which
    # starts at its default until a refresh reads the device's real modes.
    mode_state = {"live": None, "fetched": False}

    @ui.refreshable
    def mode_badges():
        _online_badge(device.get("is_online"))
        mode_text = mode_map.get(device.get("mode_enabled", 0), "Unknown")
        mode_color = (
            "green"
            if mode_text == "Running"
            else "orange"
            if mode_text == "Testing"
            else "grey"
        )
        ui.badge(mode_text, color=mode_color)
        op_text = op_map.get(device.get("mode_operation", 0), "Unknown")
        ui.badge(op_text, color="blue")

    def _fetch_modes():
        # Enabled/Operation mode aren't exposed as JSON, so read them from the
        # /hyphae-config page, reflect them on the in-memory row, and persist so
        # the badges stay correct on the next open (not just after a refresh).
        data = fetch_hyphae_config_modes(device.get("hostname", ""))
        if not data:
            return None
        updates = {}
        if data.get("enabled_mode") is not None:
            updates["mode_enabled"] = data["enabled_mode"]
        if data.get("operation_mode") is not None:
            updates["mode_operation"] = data["operation_mode"]
        if updates:
            device.update(updates)
            try:
                update_device_hyphae(device["device_id"], **updates)
            except Exception:
                pass
        return data

    register(mode_state, _fetch_modes, mode_badges)

    with ui.row().classes("w-full gap-2 items-center"):
        mode_badges()
        ui.space()
        ui.button(
            "Refresh from device", icon="cloud_download", on_click=_refresh_all
        ).props("outline dense")

    with ui.tabs().classes("w-full") as dtabs:
        tab_sys = ui.tab("System Info", icon="info")
        tab_relay = ui.tab("Relay Config", icon="electrical_services")
        tab_state = ui.tab("Relay State", icon="toggle_on")
        tab_sched = ui.tab("Schedule", icon="schedule")
        tab_dyn = ui.tab("Dynamic", icon="tune")
        tab_mgmt = ui.tab("Management", icon="build")

    with ui.tab_panels(dtabs, value=tab_sys).classes("w-full"):
        with ui.tab_panel(tab_sys):
            _hyphae_system_panel(device, colors, register)

        with ui.tab_panel(tab_relay):
            _hyphae_relay_config_panel(device, colors, register)

        with ui.tab_panel(tab_state):
            _hyphae_relay_state_panel(device, colors, register)

        with ui.tab_panel(tab_sched):
            _hyphae_schedule_panel(device, colors, register)

        with ui.tab_panel(tab_dyn):
            _hyphae_dynamic_panel(device, colors, register)

        with ui.tab_panel(tab_mgmt):
            _device_management_panel(device, "hyphae", colors, selected_device)


def _hyphae_system_panel(device: Dict, colors: dict, register):
    """Show Hyphae system information.

    Core device metadata (name/host/MAC/room/firmware) comes from the database,
    so it always renders without a network call. The live "Status" section
    (uptime, WiFi signal) is read from /api/system/info via the shared "Refresh
    from device" button at the top of the detail view.
    """
    # --- Device info (always from DB) ---
    with ui.card().classes("w-full p-4"):
        ui.label("Device Information").classes(
            "text-subtitle1 text-weight-bold q-mb-sm"
        )
        _kv("Device Name", device.get("device_name", "Unknown"))
        _kv("Hostname", device.get("hostname", "Unknown"))
        _kv("MAC Address", device.get("mac_address", "Unknown"))
        _kv("Room", device.get("room_name", "Unassigned"))
        _kv("Firmware", device.get("firmware_version", "Unknown"))

    # --- Live status (fetched by the shared Refresh button) ---
    state = {"live": None, "fetched": False}

    def fetch_fn():
        return fetch_hyphae_config(device.get("hostname", ""))

    @ui.refreshable
    def body():
        _panel_status_line(state, stored=False)
        config = state.get("live")
        if not config:
            if state.get("fetched"):
                ui.label("Could not fetch live status from device.").classes(
                    "text-muted"
                )
            else:
                ui.label(
                    "Live status is read from the device on demand. "
                    "Use “Refresh from device” above to query it."
                ).classes("text-muted")
            return

        # /api/system/info reports the device's live connection health.
        with ui.card().classes("w-full p-4"):
            ui.label("Live Status").classes("text-subtitle1 text-weight-bold q-mb-sm")
            _kv("Uptime", str(config.get("uptime", "N/A")))
            rssi = config.get("rssi")
            _kv("WiFi Signal", f"{rssi} dBm" if rssi is not None else "N/A")
            quality = config.get("signal_quality")
            _kv("Signal Quality", f"{quality}%" if quality is not None else "N/A")

    with ui.column().classes("w-full q-mt-md"):
        body()
    register(state, fetch_fn, body)


def _hyphae_relay_config_panel(device: Dict, colors: dict, register):
    """Show relay configuration (6 relays, 7 groups) — DB-first, live on demand."""
    device_id = device.get("device_id")
    state = {"live": None, "fetched": False}

    def fetch_fn():
        return fetch_hyphae_relay_config(device.get("hostname", ""))

    def _db_relays():
        rows = get_device_relay_settings(device_id) if device_id else None
        if not rows:
            return []
        return [
            {
                "id": str(r.get("relay_number", "")),
                "name": r.get("relay_name", f"Relay {r.get('relay_number', '?')}"),
                "group": r.get("group_num", 0),
                "relay_number": r.get("relay_number", 0),
                "enabled": r.get("group_num", 0) != 0,
            }
            for r in rows
        ]

    def _live_relays(live: Dict) -> list:
        # Firmware /api/relay/config items are {relay, name, group}; normalize to
        # the same shape _db_relays() produces so the render below is uniform.
        return [
            {
                "id": str(r.get("relay", "")),
                "name": r.get("name", f"Relay {r.get('relay', '?')}"),
                "group": r.get("group", 0),
                "relay_number": r.get("relay", 0),
                "enabled": r.get("group", 0) != 0,
            }
            for r in live.get("relays", [])
        ]

    @ui.refreshable
    def body():
        relays = _live_relays(state["live"]) if state["live"] else _db_relays()

        _panel_status_line(state)

        if not relays:
            ui.label("No relay configuration available.").classes("text-muted")
            return

        ui.label(f"{len(relays)} relays configured").classes(
            "text-caption text-muted q-mb-md"
        )

        with ui.row().classes("w-full gap-4 flex-wrap"):
            for relay in relays:
                with ui.card().classes("p-4 min-w-48 flex-1"):
                    enabled = relay.get("enabled", False)
                    ui.label(
                        f"Relay {relay.get('id', '?')}: {relay.get('name', 'Unnamed')}"
                    ).classes("text-subtitle2 text-weight-bold")
                    _kv("Group", str(relay.get("group", "N/A")))
                    if relay.get("group_description"):
                        _kv("Description", relay["group_description"])
                    ui.badge(
                        "Enabled" if enabled else "Disabled",
                        color="green" if enabled else "grey",
                    )

    body()
    register(state, fetch_fn, body)


def _hyphae_relay_state_view(device: Dict, live: Optional[Dict]) -> Dict:
    """Normalize relay state from either the live payload or the database.

    Returns a uniform dict: per-relay {is_on, name}, on/off/total counts, the
    system/operation mode strings, and an `as_of` time. The DB path reads the
    latest stored state from readings_hyphae (filled by the poller), relay names
    from relay_settings, and the modes from the device row — so it needs no
    device call.
    """
    mode_map = {0: "Offline", 1: "Testing", 2: "Running"}
    op_map = {0: "Schedule", 1: "Dynamic"}

    # Relay names always come from stored relay_settings so the live state (which
    # carries no names) still labels each relay.
    device_id = device.get("device_id")
    names = {}
    if device_id:
        for s in get_device_relay_settings(device_id) or []:
            names[s.get("relay_number")] = s.get("relay_name")

    relays: Dict[int, Dict] = {}
    as_of = None

    if live:
        # Firmware /api/relay/state returns a `states` array of 6 booleans.
        for i, is_on in enumerate(live.get("states", []), start=1):
            relays[i] = {
                "is_on": bool(is_on),
                "name": names.get(i) or f"Relay {i}",
            }
    else:
        for row in get_latest_relay_states(device_id) if device_id else []:
            n = row.get("relay_number")
            relays[n] = {
                "is_on": bool(row.get("relay_state")),
                "name": names.get(n) or f"Relay {n}",
                "ts": row.get("reading_ts"),
            }
        ts_values = [r["ts"] for r in relays.values() if r.get("ts")]
        if ts_values:
            as_of = _format_last_seen(max(ts_values))

    # Modes always come from the device row (the live payload's mode field
    # semantics differ); the row is kept current on refresh.
    system_mode = mode_map.get(device.get("mode_enabled", 0), "")
    operation_mode = op_map.get(device.get("mode_operation", 0), "")

    on = sum(1 for r in relays.values() if r["is_on"])
    total = len(relays)
    return {
        "relays": relays,
        "total": total,
        "on": on,
        "off": total - on,
        "system_mode": system_mode,
        "operation_mode": operation_mode,
        "as_of": as_of,
    }


def _hyphae_relay_state_panel(device: Dict, colors: dict, register):
    """Show current relay states (ON/OFF) for all 6 relays — DB-first.

    Relay state changes often, so this panel keeps its own refresh button in
    addition to being updated by the shared "Refresh from device" button.
    """
    state = {"live": None, "fetched": False}

    def fetch_fn():
        return fetch_hyphae_relay_state(device.get("hostname", ""))

    @ui.refreshable
    def body():
        view = _hyphae_relay_state_view(device, state["live"])
        relays = view["relays"]

        _panel_source_row(state, fetch_fn, body, as_of=view["as_of"])

        if not relays:
            ui.label(
                "No relay state recorded yet. Click “Refresh from device” to fetch live."
            ).classes("text-muted")
            return

        with ui.row().classes("w-full gap-4 flex-wrap q-mb-md"):
            _mini_stat("Total", str(view["total"]), colors["primary"])
            _mini_stat("ON", str(view["on"]), STATUS_COLORS["online"])
            _mini_stat("OFF", str(view["off"]), STATUS_COLORS["offline"])

        if view["system_mode"]:
            ui.label(f"System Mode: {view['system_mode']}").classes(
                "text-caption text-muted"
            )
        if view["operation_mode"]:
            ui.label(f"Operation Mode: {view['operation_mode']}").classes(
                "text-caption text-muted"
            )

        with ui.row().classes("w-full gap-4 flex-wrap"):
            for i in range(1, 7):
                relay = relays.get(i)
                is_on = relay["is_on"] if relay else False
                relay_name = relay["name"] if relay else f"Relay {i}"

                with ui.card().classes("p-4 min-w-36 flex-1 text-center"):
                    color = (
                        STATUS_COLORS["online"] if is_on else STATUS_COLORS["offline"]
                    )
                    ui.icon("toggle_on" if is_on else "toggle_off", size="lg").style(
                        f"color: {color}"
                    )
                    ui.label(relay_name).classes("text-subtitle2 q-mt-xs")
                    ui.badge(
                        "ON" if is_on else "OFF",
                        color="green" if is_on else "red",
                    ).classes("q-mt-xs")

    body()
    register(state, fetch_fn, body)


def _hyphae_schedule_panel(device: Dict, colors: dict, register):
    """Show relay schedule (on/off duty-cycle minutes per group) — live on demand.

    Read by parsing the device's /hyphae-relay-sched config page, since the JSON
    API is POST-only. Fetched by the shared "Refresh from device" button.
    """
    state = {"live": None, "fetched": False}

    def fetch_fn():
        return fetch_hyphae_relay_schedule(device.get("hostname", ""))

    @ui.refreshable
    def body():
        _panel_status_line(state, stored=False)

        data = state.get("live")
        if not data:
            if state.get("fetched"):
                ui.label("Could not read the schedule from the device.").classes(
                    "text-muted"
                )
            else:
                ui.label(
                    "Relay schedule is read from the device on demand. "
                    "Use “Refresh from device” above to query it."
                ).classes("text-muted")
            return

        groups = data.get("groups", [])
        ui.label(
            f"{len(groups)} relay group cycle(s) — on/off duration per group"
        ).classes("text-caption text-muted q-mb-md")

        with ui.row().classes("w-full gap-4 flex-wrap"):
            for g in groups:
                with ui.card().classes("p-4 min-w-48 flex-1"):
                    ui.label(f"Group {g['group']}").classes(
                        "text-subtitle2 text-weight-bold"
                    )
                    _kv("On", f"{g['on_min']} min")
                    _kv("Off", f"{g['off_min']} min")

    body()
    register(state, fetch_fn, body)


def _hyphae_dynamic_panel(device: Dict, colors: dict, register):
    """Show dynamic-control thresholds (CO2/Humidity/Temp) — live on demand.

    Read by parsing the device's /hyphae-relay-dynam config page, since the JSON
    API is POST-only. Fetched by the shared "Refresh from device" button.
    """
    state = {"live": None, "fetched": False}

    def fetch_fn():
        return fetch_hyphae_relay_dynamic(device.get("hostname", ""))

    @ui.refreshable
    def body():
        _panel_status_line(state, stored=False)

        data = state.get("live")
        if not data:
            if state.get("fetched"):
                ui.label("Could not read thresholds from the device.").classes(
                    "text-muted"
                )
            else:
                ui.label(
                    "Dynamic-control thresholds are read from the device on demand. "
                    "Use “Refresh from device” above to query it."
                ).classes("text-muted")
            return

        controls = data.get("controls", [])
        if not controls:
            ui.label("No dynamic control configuration available.").classes(
                "text-muted"
            )
            return

        with ui.row().classes("w-full gap-4 flex-wrap"):
            for c in controls:
                with ui.card().classes("p-4 min-w-56 flex-1"):
                    ui.label(f"{c['param']} (Group {c['group']})").classes(
                        "text-subtitle2 text-weight-bold"
                    )
                    _kv("Low Threshold", str(c.get("low", "N/A")))
                    _kv("High Threshold", str(c.get("high", "N/A")))
                    high = c.get("activate_high")
                    ui.badge(
                        "Activate HIGH" if high else "Activate LOW",
                        color="green" if high else "blue",
                    )

    body()
    register(state, fetch_fn, body)


# ---------------------------------------------------------------------------
# Device Management panel (PIN + OTA) — shared by Spore and Hyphae
# ---------------------------------------------------------------------------


def _device_management_panel(
    device: Dict, device_type: str, colors: dict, selected_device: Dict = None
):
    """PIN management, OTA firmware update, and device removal for a single device."""
    device_id = device.get("device_id")
    user_id = app.storage.user.get("user_id")

    from api.services.ota_service import OtaService

    ota_svc = OtaService()

    # --- Spore-specific settings (moved here from the old Configuration tab) ---
    if device_type == "spore":
        _spore_hyphae_association_card(device)
        _spore_pressure_source_card(device)

    # --- PIN Section ---
    with ui.card().classes("w-full p-4 q-mb-md"):
        ui.label("Device PIN").classes("text-h6 q-mb-sm")

        pin_status = ota_svc.get_pin_status(device_id, device_type, user_id)
        status_map = {
            "device": ("Per-device PIN stored", "positive"),
            "default": ("Using default PIN from Settings", "info"),
            "missing": ("No PIN configured", "negative"),
        }
        status_text, status_type = status_map.get(pin_status, ("Unknown", "grey"))

        with ui.row().classes("items-center gap-2 q-mb-md"):
            ui.icon("vpn_key", size="sm").style(f"color: {colors['primary']}")
            ui.label(f"Status: {status_text}").classes("text-caption")

        ui.label(
            "Set a 5-digit PIN specific to this device (overrides default):"
        ).classes("text-caption text-muted q-mb-xs")

        with ui.row().classes("items-end gap-2"):
            pin_input = (
                ui.input(
                    label="Device PIN",
                    placeholder="5-digit PIN",
                )
                .props("maxlength=5 type=password")
                .classes("w-40")
            )

            def save_pin():
                val = pin_input.value.strip() if pin_input.value else ""
                if not val or len(val) != 5 or not val.isdigit():
                    ui.notify("PIN must be exactly 5 digits", type="warning")
                    return
                store_device_pin(device_id, device_type, val)
                ui.notify("Device PIN saved", type="positive")
                pin_input.value = ""

            ui.button("Save PIN", icon="save", on_click=save_pin).props(
                "color=primary size=sm"
            )

            if has_stored_pin(device_id, device_type):
                from storage.tables.device_pins import delete_device_pin

                def clear_pin():
                    delete_device_pin(device_id, device_type)
                    ui.notify(
                        "Device PIN cleared — will fall back to default", type="info"
                    )

                ui.button("Clear", icon="delete", on_click=clear_pin).props(
                    "outline color=negative size=sm"
                )

    # --- Firmware Update (OTA) ---
    _device_ota_card(device, device_type, user_id, ota_svc)

    # --- Remove Device Section ---
    with ui.card().classes("w-full p-4 q-mb-md").style("border: 1px solid #c10015"):
        ui.label("Remove Device").classes("text-h6 text-negative q-mb-sm")
        ui.label(
            "Remove this device from Mycelium. Recorded readings are kept, but the "
            "device disappears from the list. You can re-add it afterward."
        ).classes("text-caption text-muted q-mb-sm")

        def _do_remove():
            try:
                if device_type == "spore":
                    delete_device_spore(device_id)
                else:
                    delete_device_hyphae(device_id)
            except Exception as exc:
                ui.notify(f"Remove failed: {exc}", type="negative")
                return

            ui.notify(f"Removed {device.get('device_name', 'device')}", type="positive")
            confirm_dialog.close()

            # Refresh the device lists/stat cards so the removed row disappears.
            # Rebuilding the list resets its open-row set, collapsing this panel.
            if selected_device is not None:
                for key in ("_spore_table", "_hyphae_table", "_stat_cards"):
                    ref = selected_device.get(key)
                    if ref is not None:
                        try:
                            ref.refresh()
                        except Exception:
                            pass

        with ui.dialog() as confirm_dialog, ui.card():
            ui.label(
                f"Remove '{device.get('device_name', 'this device')}' from Mycelium?"
            ).classes("text-body1")
            with ui.row().classes("justify-end gap-2 w-full"):
                ui.button("Cancel", on_click=confirm_dialog.close).props("flat")
                ui.button("Remove", color="negative", on_click=_do_remove)

        ui.button(
            "Remove Device", icon="delete_forever", on_click=confirm_dialog.open
        ).props("color=negative outline")


def _device_ota_card(device: Dict, device_type: str, user_id, ota_svc):
    """Firmware Update (OTA) card for the device management panel."""
    device_id = device.get("device_id")
    with ui.card().classes("w-full p-4 q-mb-md"):
        ui.label("Firmware Update (OTA)").classes("text-h6 q-mb-sm")

        # Check PIN availability
        pin = ota_svc.resolve_pin(device_id, device_type, user_id)
        if not pin:
            ui.label(
                "A device PIN is required for OTA updates. Set one above or configure a default in Settings."
            ).classes("text-negative q-mb-md")

        # Firmware selector
        from storage.tables.firmware_versions import get_all_firmware_versions

        available_fw = get_all_firmware_versions(device_type=device_type)

        if not available_fw:
            ui.label(
                f"No {device_type} firmware uploaded. Go to Fleet Management to upload firmware."
            ).classes("text-muted")
            ui.button(
                "Go to Fleet",
                icon="inventory",
                on_click=lambda: ui.navigate.to("/fleet"),
            ).props("outline size=sm").classes("q-mt-sm")
            return

        fw_options = {
            fw[
                "version_id"
            ]: f"v{fw['version']} — {fw.get('file_size', 0) // 1024}KB ({fw.get('uploaded_at', '')[:10]})"
            for fw in available_fw
        }
        fw_select = ui.select(
            options=fw_options,
            label="Select firmware version",
        ).classes("w-full q-mb-md")

        progress_label = ui.label("").classes("text-caption text-muted")
        progress_bar = ui.linear_progress(value=0, show_value=False).classes("w-full")
        progress_bar.set_visibility(False)

        async def start_ota():
            if not fw_select.value:
                ui.notify("Select a firmware version", type="warning")
                return
            if not pin:
                ui.notify(
                    "No PIN available. Set a device PIN or default PIN first.",
                    type="negative",
                )
                return

            fw = next(
                (f for f in available_fw if f["version_id"] == fw_select.value), None
            )
            if not fw:
                ui.notify("Firmware not found", type="negative")
                return

            firmware_path = fw["file_path"]

            progress_bar.set_visibility(True)
            progress_label.text = "Starting OTA upload..."

            def on_progress(pct, msg):
                progress_bar.value = pct / 100.0
                progress_label.text = msg

            result = await ota_svc.upload_firmware(
                device_id,
                device_type,
                firmware_path,
                user_id=user_id,
                on_progress=on_progress,
            )

            if result.get("success"):
                progress_bar.value = 1.0
                progress_label.text = "OTA complete! Device is rebooting."
                ui.notify("Firmware uploaded successfully", type="positive")
            else:
                progress_label.text = (
                    f"OTA failed: {result.get('error', 'Unknown error')}"
                )
                ui.notify(f"OTA failed: {result.get('error')}", type="negative")

        ui.button("Upload Firmware", icon="system_update", on_click=start_ota).props(
            "color=primary"
        )

        # OTA history for this device
        from storage.tables.ota_history import get_ota_history

        history = get_ota_history(device_id=device_id, device_type=device_type, limit=5)
        if history:
            ui.separator().classes("q-my-md")
            ui.label("Recent OTA History").classes("text-subtitle2 q-mb-xs")
            for h in history:
                status_color = "green" if h.get("status") == "success" else "red"
                with ui.row().classes("items-center gap-2"):
                    ui.badge(h.get("status", "?"), color=status_color)
                    ui.label(h.get("firmware_name", "")).classes("text-caption")
                    ui.label(fmt_datetime(h.get("started_at"), fallback="")).classes(
                        "text-caption text-muted"
                    )
                    if h.get("error_message"):
                        ui.label(h["error_message"]).classes(
                            "text-caption text-negative"
                        )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _kv(key: str, value: str):
    """Render a key-value pair on a single row."""
    with ui.row().classes("items-baseline gap-2"):
        ui.label(f"{key}:").classes("text-weight-bold text-caption")
        ui.label(value).classes("text-caption")


def _mini_stat(label: str, value: str, accent: str):
    """Small stat badge used in summary rows."""
    with ui.card().classes("p-3 min-w-24 text-center"):
        ui.label(value).classes("text-h5").style(f"color: {accent}")
        ui.label(label).classes("text-caption text-muted")


async def _run_mdns_discovery(colors: dict, stat_cards=None, selected_device=None):
    """Run mDNS discovery and display results in a dialog."""
    rooms = _room_options()

    with ui.dialog() as dlg, ui.card().classes("p-4 min-w-96"):
        ui.label("Device Discovery").classes("text-h6 q-mb-sm")
        status_label = ui.label("Scanning network via mDNS...").classes("text-muted")
        results_container = ui.column().classes("w-full q-mt-sm")
        ui.button("Close", on_click=dlg.close).props("outline").classes("q-mt-md")
    dlg.open()

    # Check for existing devices to detect duplicates
    existing_ips = set()
    for d in _safe_get_spore_devices():
        existing_ips.add(d.get("hostname"))
    for d in _safe_get_hyphae_devices():
        existing_ips.add(d.get("hostname"))

    try:
        from api.services.discovery_service import DeviceDiscoveryService

        svc = DeviceDiscoveryService()
        discovered = await svc.discover_mdns(timeout=5.0)

        if discovered:
            status_label.text = f"Found {len(discovered)} device(s) via mDNS"
            with results_container:
                for hostname, info in discovered.items():
                    ip = info.get("hostname", "")
                    device_type = info.get("device_type", "").lower()
                    already_added = ip in existing_ips

                    with ui.card().classes("w-full p-3 q-mb-xs"):
                        with ui.row().classes("items-center justify-between w-full"):
                            with ui.column().classes("gap-0"):
                                ui.label(info.get("device_name", hostname)).classes(
                                    "text-weight-bold"
                                )
                                ui.label(f"{device_type} — {ip}").classes(
                                    "text-caption text-muted"
                                )
                                if info.get("hostname"):
                                    ui.label(info["hostname"]).classes(
                                        "text-caption text-muted"
                                    )

                            if already_added:
                                ui.badge("Already Added").props("color=grey")
                            elif device_type in ("spore", "hyphae") and rooms:
                                room_select = ui.select(
                                    options=rooms,
                                    label="Room",
                                    with_input=True,
                                ).classes("min-w-32")

                                def _make_add_handler(dev_ip, dev_type, room_sel):
                                    def handler():
                                        room_id = room_sel.value
                                        if not room_id:
                                            ui.notify(
                                                "Select a room first.", type="warning"
                                            )
                                            return
                                        if dev_type == "spore":
                                            result = store_complete_spore_device_data(
                                                dev_ip, room_id
                                            )
                                        else:
                                            result = store_complete_hyphae_device_data(
                                                dev_ip, room_id
                                            )
                                        if result.get("success"):
                                            existing_ips.add(dev_ip)
                                            ui.notify(
                                                f"{dev_type.title()} at {dev_ip} added.",
                                                type="positive",
                                            )
                                            if stat_cards:
                                                stat_cards.refresh()
                                            # Refresh the device table so the new
                                            # device shows up in the list immediately.
                                            if selected_device is not None:
                                                tbl = selected_device.get(
                                                    "_spore_table"
                                                    if dev_type == "spore"
                                                    else "_hyphae_table"
                                                )
                                                if tbl is not None:
                                                    try:
                                                        tbl.refresh()
                                                    except Exception:
                                                        pass
                                        else:
                                            errors = "; ".join(
                                                result.get("errors", ["Unknown error"])
                                            )
                                            ui.notify(
                                                f"Error: {errors}", type="negative"
                                            )

                                    return handler

                                ui.button(
                                    "Add",
                                    icon="add",
                                    on_click=_make_add_handler(
                                        ip, device_type, room_select
                                    ),
                                ).props("dense color=primary")
                            else:
                                ui.badge(device_type.upper() or "?").props(
                                    "color=primary"
                                )
        else:
            status_label.text = (
                "No devices found via mDNS. Devices may not be advertising _https._tcp."
            )
    except ImportError:
        status_label.text = "zeroconf not installed. Run: pip install zeroconf"
    except Exception as e:
        status_label.text = f"Discovery error: {e}"


# ---------------------------------------------------------------------------
# CSV export / import
# ---------------------------------------------------------------------------


def _export_devices_csv(device_type: str):
    """Export devices to CSV and trigger download."""
    import csv
    import io

    devices = (
        _safe_get_spore_devices()
        if device_type == "spore"
        else _safe_get_hyphae_devices()
    )
    if not devices:
        ui.notify(f"No {device_type} devices to export.", type="info")
        return

    output = io.StringIO()
    fields = [
        "device_name",
        "hostname",
        "mac_address",
        "room_name",
        "firmware_version",
        "is_online",
    ]
    if device_type == "spore":
        fields.append("hyphae_id")

    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for d in devices:
        writer.writerow(d)

    ui.download(output.getvalue().encode(), f"mycelium_{device_type}_devices.csv")


def _open_import_csv_dialog(device_type: str, table_refresh, stat_cards_refresh):
    """Open a dialog for importing devices from a CSV file."""
    import csv
    import io

    rooms = _room_options()

    with ui.dialog() as dialog, ui.card().classes("min-w-[500px] p-4"):
        ui.label(f"Import {device_type.title()} Devices from CSV").classes(
            "text-h6 q-mb-sm"
        )

        ui.label(
            "CSV must have columns: device_name, hostname. "
            "Optional: mac_address, room_id."
        ).classes("text-caption text-muted q-mb-md")

        # Template download
        def _download_template():
            if device_type == "spore":
                header = "device_name,hostname,mac_address,room_id\nMy-Spore,192.168.1.100,,1\n"
            else:
                header = "device_name,hostname,mac_address,room_id,pin\nMy-Hyphae,192.168.1.200,,1,12345\n"
            ui.download(header.encode(), f"{device_type}_template.csv")

        ui.button(
            "Download Template", icon="description", on_click=_download_template
        ).props("outline dense")

        room_select = ui.select(
            options=rooms,
            label="Default Room (for rows without room_id)",
            with_input=True,
        ).classes("w-full q-mt-md")

        upload_area = (
            ui.upload(
                label="Drop CSV file here or click to browse",
                auto_upload=True,
                max_files=1,
            )
            .classes("w-full q-mt-sm")
            .props("accept=.csv")
        )

        status_label = ui.label("").classes("text-muted q-mt-sm")

        uploaded_rows = []

        def on_upload(e):
            uploaded_rows.clear()
            try:
                content = e.content.read().decode("utf-8")
                reader = csv.DictReader(io.StringIO(content))
                for row in reader:
                    uploaded_rows.append(dict(row))
                status_label.text = f"Parsed {len(uploaded_rows)} row(s) from CSV"
            except Exception as exc:
                status_label.text = f"Error parsing CSV: {exc}"

        upload_area.on("upload", on_upload)

        with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dialog.close).props("flat")

            def _do_import():
                if not uploaded_rows:
                    ui.notify("No CSV data loaded.", type="warning")
                    return
                default_room = room_select.value
                if not default_room:
                    ui.notify("Select a default room.", type="warning")
                    return

                success, errors = 0, 0
                for row in uploaded_rows:
                    ip = (row.get("hostname") or "").strip()
                    if not ip:
                        errors += 1
                        continue
                    row_room = row.get("room_id") or default_room
                    try:
                        if device_type == "spore":
                            result = store_complete_spore_device_data(ip, row_room)
                        else:
                            pin = row.get("pin", "")
                            result = store_complete_hyphae_device_data(
                                ip, row_room, pin or None
                            )
                        if result.get("success"):
                            success += 1
                        else:
                            errors += 1
                    except Exception:
                        errors += 1

                table_refresh.refresh()
                stat_cards_refresh.refresh()
                dialog.close()
                if errors == 0:
                    ui.notify(f"Imported {success} device(s).", type="positive")
                else:
                    ui.notify(f"Imported {success}, failed {errors}.", type="warning")

            ui.button("Import", icon="upload", on_click=_do_import).props(
                "color=primary"
            )

    dialog.open()
