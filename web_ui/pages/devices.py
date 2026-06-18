"""
Devices page for Mycelium NiceGUI application.

Comprehensive device management for Spore and Hyphae devices.
Provides device tables, add dialogs, and detail panels with readings,
configuration, relay state, schedule, and dynamic control views.
"""

import re
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

import requests

from nicegui import ui, app
from web_ui.layout import page_layout, back_to_dashboard
from web_ui.theme import get_colors, STATUS_COLORS

from storage.tables.device_spore import (
    get_all_device_spore, delete_device_spore,
    link_spore_to_hyphae, unlink_spore_from_hyphae,
)
from storage.tables.device_hyphae import (
    get_all_device_hyphae, delete_device_hyphae
)
from storage.tables.grow_rooms import get_all_grow_rooms
from storage.tables.relay_settings import get_device_relay_settings
from storage.tables.schedule_settings import get_device_schedule_settings
from storage.tables.dynamic_settings import get_device_dynamic_settings
from storage.tables.device_pins import store_device_pin, get_device_pin, has_stored_pin

logger = logging.getLogger(__name__)

_SCHEME = 'https'
_TIMEOUT = 10
_CA_CERT = str(Path(__file__).parent.parent.parent / 'config' / 'ca_root.pem')


def _device_url(ip: str, path: str) -> str:
    """Build a device URL. Supports ip:port for Sentinel mode."""
    return f'{_SCHEME}://{ip}{path}'


def _get_json(ip: str, path: str) -> Optional[Dict]:
    """GET a JSON endpoint from a device. Returns None on any error."""
    try:
        verify = _CA_CERT if Path(_CA_CERT).exists() else False
        r = requests.get(_device_url(ip, path), timeout=_TIMEOUT, verify=verify)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.debug(f'GET {path} from {ip} failed: {e}')
    return None


def discover_mac_address(ip_address: str) -> Optional[str]:
    """Discover MAC address via ARP / ip-neigh."""
    # Try ARP
    try:
        result = subprocess.run(['arp', '-n', ip_address],
                                capture_output=True, text=True, timeout=5)
        match = re.search(r'([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}', result.stdout)
        if match:
            return match.group(0)
    except Exception:
        pass
    # Try ip neigh
    try:
        result = subprocess.run(['ip', 'neigh', 'show'],
                                capture_output=True, text=True, timeout=5)
        for line in result.stdout.split('\n'):
            if ip_address in line:
                match = re.search(r'([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}', line)
                if match:
                    return match.group(0)
    except Exception:
        pass
    return None


def fetch_spore_readings_latest(ip: str) -> Optional[Dict]:
    """Fetch latest readings from Spore /api/readings/latest."""
    return _get_json(ip, '/api/readings/latest')


def fetch_spore_info(ip: str) -> Optional[Dict]:
    """Fetch diagnostics from Spore /api/diagnostics."""
    return _get_json(ip, '/api/diagnostics')


def fetch_spore_config(ip: str) -> Optional[Dict]:
    """Fetch Spore configuration from /spore-config (HTML) or /api/status."""
    # Prefer JSON status endpoint
    data = _get_json(ip, '/api/status')
    if data:
        return data
    return None


def fetch_hyphae_config(ip: str) -> Optional[Dict]:
    """Fetch Hyphae configuration from /api/system/info."""
    return _get_json(ip, '/api/system/info')


def fetch_hyphae_relay_config(ip: str) -> Optional[Dict]:
    """Fetch relay configuration from Hyphae /api/relay/config."""
    return _get_json(ip, '/api/relay/config')


def fetch_hyphae_relay_state(ip: str) -> Optional[List]:
    """Fetch relay states from Hyphae /api/relay/state."""
    return _get_json(ip, '/api/relay/state')


def fetch_hyphae_relay_schedule(ip: str) -> Optional[Dict]:
    """Fetch relay schedule from Hyphae /api/relay/schedule."""
    return _get_json(ip, '/api/relay/schedule')


def fetch_hyphae_relay_dynamic(ip: str) -> Optional[Dict]:
    """Fetch relay thresholds from Hyphae /api/relay/thresholds."""
    return _get_json(ip, '/api/relay/thresholds')


def store_complete_spore_device_data(ip: str, room_id) -> Dict:
    """Fetch data from a Spore device, register it in the DB, and return result."""
    from storage.tables.device_spore import create_device_spore

    errors = []
    info = fetch_spore_info(ip) or {}
    config = fetch_spore_config(ip) or {}
    readings = fetch_spore_readings_latest(ip)

    device_name = config.get('device_name') or info.get('device_name') or f'Spore-{ip.split(".")[-1]}'
    mac = info.get('mac_address') or discover_mac_address(ip) or 'unknown'
    firmware = info.get('firmware_version') or config.get('firmware_version', '')

    try:
        device_id = create_device_spore(
            room_id=int(room_id),
            device_name=device_name,
            ip_address=ip,
            mac_address=mac,
            firmware_version=firmware,
            is_online=1 if info else 0,
        )
        return {
            'success': True,
            'data': {'config': config, 'info': info, 'readings': readings},
            'device_id': device_id,
        }
    except Exception as e:
        errors.append(str(e))
        return {'success': False, 'errors': errors}


def store_complete_hyphae_device_data(ip: str, room_id, pin=None) -> Dict:
    """Fetch data from a Hyphae device, register it in the DB, and return result."""
    from storage.tables.device_hyphae import create_device_hyphae

    errors = []
    info = fetch_hyphae_config(ip) or {}
    relay = fetch_hyphae_relay_config(ip)

    device_name = info.get('device_name') or f'Hyphae-{ip.split(".")[-1]}'
    mac = info.get('mac_address') or discover_mac_address(ip) or 'unknown'
    firmware = info.get('firmware_version', '')

    try:
        device_id = create_device_hyphae(
            room_id=int(room_id),
            device_name=device_name,
            ip_address=ip,
            mac_address=mac,
            firmware_version=firmware,
            is_online=1 if info else 0,
        )
        if pin:
            store_device_pin(device_id, 'hyphae', pin)
        return {
            'success': True,
            'data': {'config': info, 'relay_config': relay or {}},
            'device_id': device_id,
        }
    except Exception as e:
        errors.append(str(e))
        return {'success': False, 'errors': errors}


def refresh_spore_device_data(device_id, ip: str) -> Optional[Dict]:
    """Refresh data for an existing Spore device."""
    return store_complete_spore_device_data(ip, None)


def refresh_hyphae_device_data(device_id, ip: str) -> Optional[Dict]:
    """Refresh data for an existing Hyphae device."""
    return store_complete_hyphae_device_data(ip, None)


# IP address validation pattern (supports optional port for Sentinel mode)
_IP_PATTERN = re.compile(
    r'^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}'
    r'(?:25[0-5]|2[0-4]\d|[01]?\d\d?)(?::\d{1,5})?$'
)


def _room_options() -> List[Dict]:
    """Get grow rooms as select options."""
    try:
        rooms = get_all_grow_rooms()
        return {r['room_id']: r['room_name'] for r in rooms}
    except Exception:
        return {}


def _format_last_seen(value) -> str:
    """Format a timestamp or datetime string for display."""
    if not value:
        return 'Never'
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')
        return str(value)
    except Exception:
        return str(value)


def _online_badge(is_online) -> None:
    """Render an online/offline badge inline."""
    online = bool(is_online)
    color = STATUS_COLORS['online'] if online else STATUS_COLORS['offline']
    text = 'Online' if online else 'Offline'
    ui.badge(text).style(f'background-color: {color}; color: white;')


# ---------------------------------------------------------------------------
# Page entry point
# ---------------------------------------------------------------------------

@ui.page('/devices')
def devices_page():
    """Main devices management page."""
    user = app.storage.user
    if not user.get('user_id'):
        ui.navigate.to('/login')
        return

    page_layout('Devices')
    back_to_dashboard()
    colors = get_colors()

    # Shared state for device detail
    selected_device = {'type': None, 'data': None}

    with ui.column().classes('w-full max-w-7xl mx-auto p-4 gap-4'):
        # --- Header with discover button ---
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Devices').classes('text-h4')
            discover_btn = ui.button('Discover Devices', icon='wifi_find').props('outline')

        # --- Stat cards ---
        stat_cards_container = ui.row().classes('w-full gap-4 flex-wrap')

        @ui.refreshable
        def stat_cards():
            stat_cards_container.clear()
            with stat_cards_container:
                spore_devices = _safe_get_spore_devices()
                hyphae_devices = _safe_get_hyphae_devices()
                spore_online = sum(1 for d in spore_devices if d.get('is_online'))
                hyphae_online = sum(1 for d in hyphae_devices if d.get('is_online'))
                total_offline = (len(spore_devices) + len(hyphae_devices)
                                 - spore_online - hyphae_online)

                _stat_card('Spore Online', str(spore_online), 'sensors',
                           STATUS_COLORS['online'], colors)
                _stat_card('Hyphae Online', str(hyphae_online), 'device_hub',
                           STATUS_COLORS['online'], colors)
                _stat_card('Devices Offline', str(total_offline), 'warning',
                           STATUS_COLORS['offline'], colors)

        stat_cards()

        # --- Tabs ---
        with ui.tabs().classes('w-full') as tabs:
            spore_tab = ui.tab('Spore Devices', icon='sensors')
            hyphae_tab = ui.tab('Hyphae Devices', icon='device_hub')
            detail_tab = ui.tab('Device Detail', icon='info')

        with ui.tab_panels(tabs, value=spore_tab).classes('w-full'):
            # =============================================================
            # SPORE TAB
            # =============================================================
            with ui.tab_panel(spore_tab):
                _build_spore_panel(colors, selected_device, tabs, detail_tab,
                                   stat_cards)

            # =============================================================
            # HYPHAE TAB
            # =============================================================
            with ui.tab_panel(hyphae_tab):
                _build_hyphae_panel(colors, selected_device, tabs, detail_tab,
                                    stat_cards)

            # =============================================================
            # DEVICE DETAIL TAB
            # =============================================================
            with ui.tab_panel(detail_tab):
                detail_container = ui.column().classes('w-full gap-4')

                @ui.refreshable
                def device_detail():
                    detail_container.clear()
                    with detail_container:
                        if selected_device['type'] is None:
                            ui.label('Select a device from the Spore or Hyphae table to view details.').classes('text-muted')
                            return
                        if selected_device['type'] == 'spore':
                            _render_spore_detail(selected_device['data'], colors)
                        else:
                            _render_hyphae_detail(selected_device['data'], colors)

                device_detail()

                # Store refreshable reference so table clicks can trigger it
                selected_device['_refresh_detail'] = device_detail

        # Wire discovery button now that stat_cards is defined
        discover_btn.on('click', lambda: _run_mdns_discovery(colors, stat_cards))


# ---------------------------------------------------------------------------
# Stat card helper
# ---------------------------------------------------------------------------

def _stat_card(label: str, value: str, icon: str, accent: str, colors: dict):
    with ui.card().classes('p-4 flex-1 min-w-48'):
        with ui.row().classes('items-center gap-2'):
            ui.icon(icon, size='sm').style(f'color: {accent}')
            ui.label(label).classes('text-subtitle2')
        ui.label(value).classes('text-h4 q-mt-sm')


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
# SPORE panel
# ---------------------------------------------------------------------------

def _build_spore_panel(colors, selected_device, tabs, detail_tab, stat_cards):
    """Build the Spore devices tab content."""

    @ui.refreshable
    def spore_table():
        devices = _safe_get_spore_devices()
        if not devices:
            ui.label('No Spore devices found. Add a device to get started.').classes('text-muted q-pa-md')
            return

        columns = [
            {'name': 'device_name', 'label': 'Name', 'field': 'device_name', 'align': 'left', 'sortable': True},
            {'name': 'ip_address', 'label': 'IP Address', 'field': 'ip_address', 'align': 'left'},
            {'name': 'room_name', 'label': 'Room', 'field': 'room_name', 'align': 'left'},
            {'name': 'mac_address', 'label': 'MAC', 'field': 'mac_address', 'align': 'left'},
            {'name': 'firmware_version', 'label': 'Firmware', 'field': 'firmware_version', 'align': 'left'},
            {'name': 'is_online', 'label': 'Status', 'field': 'is_online', 'align': 'center'},
            {'name': 'last_update', 'label': 'Last Seen', 'field': 'last_update', 'align': 'left'},
        ]

        rows = []
        for d in devices:
            rows.append({
                'device_id': d.get('device_id'),
                'device_name': d.get('device_name', ''),
                'ip_address': d.get('ip_address', ''),
                'room_name': d.get('room_name', ''),
                'mac_address': d.get('mac_address', ''),
                'firmware_version': d.get('firmware_version', ''),
                'is_online': 'Online' if d.get('is_online') else 'Offline',
                'last_update': _format_last_seen(d.get('last_update')),
                '_raw': d,
            })

        table = ui.table(
            columns=columns,
            rows=rows,
            row_key='device_id',
            selection='single',
        ).classes('w-full')

        # Status column styling
        table.add_slot('body-cell-is_online', r'''
            <q-td :props="props">
                <q-badge :color="props.row.is_online === 'Online' ? 'green' : 'red'">
                    {{ props.row.is_online }}
                </q-badge>
            </q-td>
        ''')

        def on_select(e):
            rows_selected = table.selected
            if rows_selected:
                row = rows_selected[0]
                device_id = row.get('device_id')
                raw = next((d for d in devices if d.get('device_id') == device_id), row)
                selected_device['type'] = 'spore'
                selected_device['data'] = raw
                if '_refresh_detail' in selected_device:
                    selected_device['_refresh_detail'].refresh()
                tabs.set_value(detail_tab)

        table.on('selection', on_select)

    # Buttons row
    with ui.row().classes('w-full items-center gap-2 q-mb-md'):
        ui.button('Add Spore', icon='add', on_click=lambda: _open_add_spore_dialog(
            spore_table, stat_cards
        )).props('color=primary')

        def refresh_spore():
            devices = _safe_get_spore_devices()
            if not devices:
                ui.notify('No Spore devices to refresh.', type='info')
                return
            success, errors = 0, 0
            for d in devices:
                try:
                    result = refresh_spore_device_data(d['device_id'], d['ip_address'])
                    if result.get('success'):
                        success += 1
                    else:
                        errors += 1
                except Exception:
                    errors += 1
            spore_table.refresh()
            stat_cards.refresh()
            if errors == 0:
                ui.notify(f'Refreshed {success} Spore device(s).', type='positive')
            else:
                ui.notify(f'Refreshed {success}, failed {errors}.', type='warning')

        ui.button('Refresh All', icon='refresh', on_click=refresh_spore).props('outline')
        ui.button('Export CSV', icon='download',
                  on_click=lambda: _export_devices_csv('spore')).props('outline')
        ui.button('Import CSV', icon='upload',
                  on_click=lambda: _open_import_csv_dialog('spore', spore_table, stat_cards)
                  ).props('outline')

    spore_table()


# ---------------------------------------------------------------------------
# HYPHAE panel
# ---------------------------------------------------------------------------

def _build_hyphae_panel(colors, selected_device, tabs, detail_tab, stat_cards):
    """Build the Hyphae devices tab content."""

    @ui.refreshable
    def hyphae_table():
        devices = _safe_get_hyphae_devices()
        if not devices:
            ui.label('No Hyphae devices found. Add a device to get started.').classes('text-muted q-pa-md')
            return

        mode_enabled_map = {0: 'Offline', 1: 'Testing', 2: 'Running'}
        mode_operation_map = {0: 'Schedule', 1: 'Dynamic'}

        columns = [
            {'name': 'device_name', 'label': 'Name', 'field': 'device_name', 'align': 'left', 'sortable': True},
            {'name': 'ip_address', 'label': 'IP Address', 'field': 'ip_address', 'align': 'left'},
            {'name': 'room_name', 'label': 'Room', 'field': 'room_name', 'align': 'left'},
            {'name': 'mac_address', 'label': 'MAC', 'field': 'mac_address', 'align': 'left'},
            {'name': 'firmware_version', 'label': 'Firmware', 'field': 'firmware_version', 'align': 'left'},
            {'name': 'mode_enabled', 'label': 'Mode', 'field': 'mode_enabled', 'align': 'center'},
            {'name': 'mode_operation', 'label': 'Operation', 'field': 'mode_operation', 'align': 'center'},
            {'name': 'is_online', 'label': 'Status', 'field': 'is_online', 'align': 'center'},
            {'name': 'last_update', 'label': 'Last Seen', 'field': 'last_update', 'align': 'left'},
        ]

        rows = []
        for d in devices:
            rows.append({
                'device_id': d.get('device_id'),
                'device_name': d.get('device_name', ''),
                'ip_address': d.get('ip_address', ''),
                'room_name': d.get('room_name', ''),
                'mac_address': d.get('mac_address', ''),
                'firmware_version': d.get('firmware_version', ''),
                'mode_enabled': mode_enabled_map.get(d.get('mode_enabled', 0), 'Unknown'),
                'mode_operation': mode_operation_map.get(d.get('mode_operation', 0), 'Unknown'),
                'is_online': 'Online' if d.get('is_online') else 'Offline',
                'last_update': _format_last_seen(d.get('last_update')),
                '_raw': d,
            })

        table = ui.table(
            columns=columns,
            rows=rows,
            row_key='device_id',
            selection='single',
        ).classes('w-full')

        table.add_slot('body-cell-is_online', r'''
            <q-td :props="props">
                <q-badge :color="props.row.is_online === 'Online' ? 'green' : 'red'">
                    {{ props.row.is_online }}
                </q-badge>
            </q-td>
        ''')

        table.add_slot('body-cell-mode_enabled', r'''
            <q-td :props="props">
                <q-badge :color="props.row.mode_enabled === 'Running' ? 'green' : props.row.mode_enabled === 'Testing' ? 'orange' : 'grey'">
                    {{ props.row.mode_enabled }}
                </q-badge>
            </q-td>
        ''')

        def on_select(e):
            rows_selected = table.selected
            if rows_selected:
                row = rows_selected[0]
                device_id = row.get('device_id')
                raw = next((d for d in devices if d.get('device_id') == device_id), row)
                selected_device['type'] = 'hyphae'
                selected_device['data'] = raw
                if '_refresh_detail' in selected_device:
                    selected_device['_refresh_detail'].refresh()
                tabs.set_value(detail_tab)

        table.on('selection', on_select)

    with ui.row().classes('w-full items-center gap-2 q-mb-md'):
        ui.button('Add Hyphae', icon='add', on_click=lambda: _open_add_hyphae_dialog(
            hyphae_table, stat_cards
        )).props('color=primary')

        def refresh_hyphae():
            devices = _safe_get_hyphae_devices()
            if not devices:
                ui.notify('No Hyphae devices to refresh.', type='info')
                return
            success, errors = 0, 0
            for d in devices:
                try:
                    result = refresh_hyphae_device_data(d['device_id'], d['ip_address'])
                    if result.get('success'):
                        success += 1
                    else:
                        errors += 1
                except Exception:
                    errors += 1
            hyphae_table.refresh()
            stat_cards.refresh()
            if errors == 0:
                ui.notify(f'Refreshed {success} Hyphae device(s).', type='positive')
            else:
                ui.notify(f'Refreshed {success}, failed {errors}.', type='warning')

        ui.button('Refresh All', icon='refresh', on_click=refresh_hyphae).props('outline')
        ui.button('Export CSV', icon='download',
                  on_click=lambda: _export_devices_csv('hyphae')).props('outline')
        ui.button('Import CSV', icon='upload',
                  on_click=lambda: _open_import_csv_dialog('hyphae', hyphae_table, stat_cards)
                  ).props('outline')

    hyphae_table()


# ---------------------------------------------------------------------------
# Add device dialogs
# ---------------------------------------------------------------------------

def _open_add_spore_dialog(spore_table_refresh, stat_cards_refresh):
    """Open the Add Spore device dialog."""
    with ui.dialog() as dialog, ui.card().classes('min-w-80'):
        ui.label('Add Spore Device').classes('text-h6 q-mb-md')

        ip_input = ui.input(
            label='IP Address',
            placeholder='192.168.1.100 or 192.168.1.100:8080',
            validation={'Invalid IP': lambda v: bool(_IP_PATTERN.match(v)) if v else False},
        ).classes('w-full')

        rooms = _room_options()
        room_select = ui.select(
            options=rooms,
            label='Grow Room',
            with_input=True,
        ).classes('w-full')

        ui.label('Enter the device IP address and assign it to a room.').classes('text-muted text-caption q-mt-sm')

        with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
            ui.button('Cancel', on_click=dialog.close).props('flat')

            def add_spore():
                ip = ip_input.value
                room_id = room_select.value
                if not ip or not _IP_PATTERN.match(ip):
                    ui.notify('Please enter a valid IP address.', type='negative')
                    return
                if not room_id:
                    ui.notify('Please select a grow room.', type='negative')
                    return

                try:
                    result = store_complete_spore_device_data(ip, room_id)
                    if result.get('success'):
                        name = result.get('data', {}).get('config', {}).get(
                            'device_name', f'Spore-{ip.split(".")[-1]}')
                        ui.notify(f'Spore device "{name}" added successfully.', type='positive')
                        dialog.close()
                        spore_table_refresh.refresh()
                        stat_cards_refresh.refresh()
                    else:
                        errors = '; '.join(result.get('errors', ['Unknown error']))
                        ui.notify(f'Error: {errors}', type='negative')
                except Exception as exc:
                    ui.notify(f'Error adding device: {exc}', type='negative')

            ui.button('Add Device', icon='add', on_click=add_spore).props('color=primary')

    dialog.open()


def _open_add_hyphae_dialog(hyphae_table_refresh, stat_cards_refresh):
    """Open the Add Hyphae device dialog."""
    with ui.dialog() as dialog, ui.card().classes('min-w-80'):
        ui.label('Add Hyphae Device').classes('text-h6 q-mb-md')

        ip_input = ui.input(
            label='IP Address',
            placeholder='192.168.1.100 or 192.168.1.100:8080',
            validation={'Invalid IP': lambda v: bool(_IP_PATTERN.match(v)) if v else False},
        ).classes('w-full')

        pin_input = ui.input(
            label='Device PIN',
            placeholder='5-digit PIN',
            password=True,
            password_toggle_button=True,
        ).classes('w-full')

        rooms = _room_options()
        room_select = ui.select(
            options=rooms,
            label='Grow Room',
            with_input=True,
        ).classes('w-full')

        ui.label('Enter the device IP, PIN, and assign it to a room.').classes('text-muted text-caption q-mt-sm')

        with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
            ui.button('Cancel', on_click=dialog.close).props('flat')

            def add_hyphae():
                ip = ip_input.value
                pin = pin_input.value
                room_id = room_select.value
                if not ip or not _IP_PATTERN.match(ip):
                    ui.notify('Please enter a valid IP address.', type='negative')
                    return
                if not room_id:
                    ui.notify('Please select a grow room.', type='negative')
                    return

                try:
                    result = store_complete_hyphae_device_data(ip, room_id, pin)
                    if result.get('success'):
                        name = result.get('data', {}).get('config', {}).get(
                            'device_name', f'Hyphae-{ip.split(".")[-1]}')
                        relay_count = len(result.get('data', {}).get('relay_config', {}).get('relays', []))
                        ui.notify(
                            f'Hyphae device "{name}" added with {relay_count} relays.',
                            type='positive',
                        )
                        dialog.close()
                        hyphae_table_refresh.refresh()
                        stat_cards_refresh.refresh()
                    else:
                        errors = '; '.join(result.get('errors', ['Unknown error']))
                        ui.notify(f'Error: {errors}', type='negative')
                except Exception as exc:
                    ui.notify(f'Error adding device: {exc}', type='negative')

            ui.button('Add Device', icon='add', on_click=add_hyphae).props('color=primary')

    dialog.open()


# ---------------------------------------------------------------------------
# SPORE detail
# ---------------------------------------------------------------------------

def _render_spore_detail(device: Dict, colors: dict):
    """Render the full detail panel for a Spore device."""
    ui.label(f'{device.get("device_name", "Spore Device")}').classes('text-h5')
    _online_badge(device.get('is_online'))

    with ui.tabs().classes('w-full') as dtabs:
        tab_readings = ui.tab('Readings', icon='thermostat')
        tab_config = ui.tab('Configuration', icon='settings')
        tab_diag = ui.tab('Diagnostics', icon='monitor_heart')
        tab_mgmt = ui.tab('Management', icon='build')

    with ui.tab_panels(dtabs, value=tab_readings).classes('w-full'):
        # --- Readings ---
        with ui.tab_panel(tab_readings):
            _spore_readings_panel(device, colors)

        # --- Configuration ---
        with ui.tab_panel(tab_config):
            _spore_config_panel(device, colors)

        # --- Diagnostics ---
        with ui.tab_panel(tab_diag):
            _spore_diagnostics_panel(device, colors)

        # --- Management (PIN + OTA) ---
        with ui.tab_panel(tab_mgmt):
            _device_management_panel(device, 'spore', colors)


def _spore_readings_panel(device: Dict, colors: dict):
    """Show latest sensor readings for a Spore device."""
    ip = device.get('ip_address', '')
    readings = fetch_spore_readings_latest(ip) if ip else None

    if not readings:
        ui.label('Could not fetch sensor readings. Device may be offline.').classes('text-muted')
        return

    timestamp = readings.get('datetime', 'Unknown')
    ui.label(f'Last reading: {timestamp}').classes('text-caption text-muted q-mb-md')

    with ui.row().classes('w-full gap-4 flex-wrap'):
        _reading_card('Temperature', readings.get('temperature', 'N/A'), 'C',
                      'thermostat', colors['primary'])
        _reading_card('Humidity', readings.get('humidity', 'N/A'), '%',
                      'water_drop', colors['primary'])
        _reading_card('CO2', readings.get('co2_ppm', 'N/A'), 'ppm',
                      'co2', colors['primary'])


def _reading_card(label: str, value, unit: str, icon: str, accent: str):
    """Small card showing a single sensor reading."""
    with ui.card().classes('p-4 flex-1 min-w-40 text-center'):
        ui.icon(icon, size='md').style(f'color: {accent}')
        display = f'{value} {unit}' if value != 'N/A' else 'N/A'
        ui.label(display).classes('text-h5 q-mt-xs')
        ui.label(label).classes('text-caption text-muted')


def _spore_config_panel(device: Dict, colors: dict):
    """Show Spore device configuration."""
    ip = device.get('ip_address', '')
    config = fetch_spore_config(ip) if ip else None

    with ui.card().classes('w-full p-4'):
        ui.label('Device Information').classes('text-subtitle1 text-weight-bold q-mb-sm')
        _kv('Device Name', device.get('device_name', 'Unknown'))
        _kv('IP Address', device.get('ip_address', 'Unknown'))
        _kv('MAC Address', device.get('mac_address', 'Unknown'))
        _kv('Room', device.get('room_name', 'Unassigned'))
        _kv('Firmware', device.get('firmware_version', 'Unknown'))

    # Hyphae association card
    with ui.card().classes('w-full p-4 q-mt-md'):
        ui.label('Hyphae Association').classes('text-subtitle1 text-weight-bold q-mb-sm')

        hyphae_devices = _safe_get_hyphae_devices()
        hyphae_opts = {0: '— None —'}
        for h in hyphae_devices:
            hyphae_opts[h['device_id']] = h.get('device_name', f"Hyphae #{h['device_id']}")

        current_hyphae = device.get('hyphae_id') or 0
        spore_id = device.get('device_id')

        assoc_select = ui.select(
            options=hyphae_opts,
            value=current_hyphae,
            label='Associated Hyphae Controller',
        ).classes('w-full')

        def _save_association():
            new_hyphae_id = assoc_select.value
            if new_hyphae_id and new_hyphae_id != 0:
                link_spore_to_hyphae(spore_id, new_hyphae_id)
                hname = hyphae_opts.get(new_hyphae_id, f'#{new_hyphae_id}')
                ui.notify(f'Linked to {hname}', type='positive')
            else:
                unlink_spore_from_hyphae(spore_id)
                ui.notify('Hyphae association removed', type='info')

        ui.button('Save Association', icon='link', on_click=_save_association).props(
            'outline dense'
        ).classes('q-mt-sm')

    if config:
        with ui.card().classes('w-full p-4 q-mt-md'):
            ui.label('Sensor Configuration').classes('text-subtitle1 text-weight-bold q-mb-sm')
            _kv('Measurement Interval', config.get('measurement_interval_text', 'N/A'))
            _kv('Temperature Offset', config.get('temperature_offset_text', 'N/A'))
            _kv('Altitude Compensation', config.get('altitude_compensation_text', 'N/A'))
            _kv('Temperature Display', config.get('temperature_display_text', 'N/A'))
            _kv('Auto Calibration', config.get('auto_calibration_text', 'N/A'))
            _kv('Forced Recalibration', config.get('forced_recalibration_text', 'N/A'))
    else:
        ui.label('Could not fetch live configuration from device.').classes('text-muted q-mt-md')


def _spore_diagnostics_panel(device: Dict, colors: dict):
    """Show Spore device diagnostics (memory, WiFi signal, etc.)."""
    ip = device.get('ip_address', '')
    info = fetch_spore_info(ip) if ip else None

    if not info:
        ui.label('Could not fetch diagnostics. Device may be offline.').classes('text-muted')
        return

    with ui.card().classes('w-full p-4'):
        ui.label('System Diagnostics').classes('text-subtitle1 text-weight-bold q-mb-sm')

        if 'wifi_signal_strength_text' in info:
            _kv('WiFi Signal', info['wifi_signal_strength_text'])

        if 'memory_usage_percentage' in info:
            _kv('Memory Usage', f'{info["memory_usage_percentage"]}%')
            with ui.linear_progress(value=info['memory_usage_percentage'] / 100).classes('q-mt-xs'):
                pass

        if 'total_memory_text' in info:
            _kv('Total Memory', info['total_memory_text'])
        if 'free_memory_text' in info:
            _kv('Free Memory', info['free_memory_text'])

        # Show any additional info keys
        skip_keys = {
            'wifi_signal_strength_text', 'wifi_signal_strength_dbm',
            'memory_usage_percentage', 'total_memory_text', 'free_memory_text',
            'total_memory_kb', 'used_memory_kb', 'free_memory_kb',
            'used_memory_text', 'parse_error',
        }
        for key, value in info.items():
            if key not in skip_keys and isinstance(value, (str, int, float)):
                display_key = key.replace('_', ' ').title()
                _kv(display_key, str(value))


# ---------------------------------------------------------------------------
# HYPHAE detail
# ---------------------------------------------------------------------------

def _render_hyphae_detail(device: Dict, colors: dict):
    """Render the full detail panel for a Hyphae device."""
    mode_map = {0: 'Offline', 1: 'Testing', 2: 'Running'}
    op_map = {0: 'Schedule', 1: 'Dynamic'}

    ui.label(f'{device.get("device_name", "Hyphae Device")}').classes('text-h5')
    with ui.row().classes('gap-2 items-center'):
        _online_badge(device.get('is_online'))
        mode_text = mode_map.get(device.get('mode_enabled', 0), 'Unknown')
        mode_color = 'green' if mode_text == 'Running' else 'orange' if mode_text == 'Testing' else 'grey'
        ui.badge(mode_text, color=mode_color)
        op_text = op_map.get(device.get('mode_operation', 0), 'Unknown')
        ui.badge(op_text, color='blue')

    with ui.tabs().classes('w-full') as dtabs:
        tab_sys = ui.tab('System Info', icon='info')
        tab_relay = ui.tab('Relay Config', icon='electrical_services')
        tab_state = ui.tab('Relay State', icon='toggle_on')
        tab_sched = ui.tab('Schedule', icon='schedule')
        tab_dyn = ui.tab('Dynamic', icon='tune')
        tab_mgmt = ui.tab('Management', icon='build')

    with ui.tab_panels(dtabs, value=tab_sys).classes('w-full'):
        with ui.tab_panel(tab_sys):
            _hyphae_system_panel(device, colors)

        with ui.tab_panel(tab_relay):
            _hyphae_relay_config_panel(device, colors)

        with ui.tab_panel(tab_state):
            _hyphae_relay_state_panel(device, colors)

        with ui.tab_panel(tab_sched):
            _hyphae_schedule_panel(device, colors)

        with ui.tab_panel(tab_dyn):
            _hyphae_dynamic_panel(device, colors)

        with ui.tab_panel(tab_mgmt):
            _device_management_panel(device, 'hyphae', colors)


def _hyphae_system_panel(device: Dict, colors: dict):
    """Show Hyphae system information."""
    ip = device.get('ip_address', '')
    config = fetch_hyphae_config(ip) if ip else None

    with ui.card().classes('w-full p-4'):
        ui.label('Device Information').classes('text-subtitle1 text-weight-bold q-mb-sm')
        _kv('Device Name', device.get('device_name', 'Unknown'))
        _kv('IP Address', device.get('ip_address', 'Unknown'))
        _kv('MAC Address', device.get('mac_address', 'Unknown'))
        _kv('Room', device.get('room_name', 'Unassigned'))
        _kv('Firmware', device.get('firmware_version', 'Unknown'))

    if config:
        with ui.card().classes('w-full p-4 q-mt-md'):
            ui.label('Configuration').classes('text-subtitle1 text-weight-bold q-mb-sm')
            _kv('OWM API Key', config.get('owm_api_key', 'N/A'))
            _kv('ZIP Code', config.get('zip_code', 'N/A'))
            _kv('Timezone', config.get('timezone', 'N/A'))
            _kv('Time Format', config.get('time_format', 'N/A'))
            _kv('Temperature Unit', config.get('temperature_unit', 'N/A'))
            _kv('Spore Average', str(config.get('spore_average', 'N/A')))
            _kv('Spore Read Frequency', config.get('spore_freq_text', 'N/A'))
            _kv('OWM Cache Size', str(config.get('owm_cache_size', 'N/A')))
            _kv('OWM Read Frequency', config.get('owm_freq_text', 'N/A'))

            connected = config.get('connected_spore_devices', [])
            if connected:
                _kv('Connected Spores', ', '.join(connected))
    else:
        ui.label('Could not fetch live configuration from device.').classes('text-muted q-mt-md')


def _hyphae_relay_config_panel(device: Dict, colors: dict):
    """Show relay configuration (6 relays, 7 groups)."""
    ip = device.get('ip_address', '')
    device_id = device.get('device_id')

    # Try live data first, fall back to database
    relay_config = fetch_hyphae_relay_config(ip) if ip else None
    relays = relay_config.get('relays', []) if relay_config else []

    if not relays and device_id:
        db_relays = get_device_relay_settings(device_id)
        if db_relays:
            relays = [
                {
                    'id': str(r.get('relay_number', '')),
                    'name': r.get('relay_name', f'Relay {r.get("relay_number", "?")}'),
                    'group': r.get('group_num', 0),
                    'relay_number': r.get('relay_number', 0),
                    'enabled': r.get('group_num', 0) != 0,
                }
                for r in db_relays
            ]

    if not relays:
        ui.label('No relay configuration available.').classes('text-muted')
        return

    ui.label(f'{len(relays)} relays configured').classes('text-caption text-muted q-mb-md')

    with ui.row().classes('w-full gap-4 flex-wrap'):
        for relay in relays:
            with ui.card().classes('p-4 min-w-48 flex-1'):
                enabled = relay.get('enabled', False)
                status_color = STATUS_COLORS['online'] if enabled else STATUS_COLORS['offline']
                ui.label(f'Relay {relay.get("id", "?")}: {relay.get("name", "Unnamed")}').classes(
                    'text-subtitle2 text-weight-bold')
                _kv('Group', str(relay.get('group', 'N/A')))
                if relay.get('group_description'):
                    _kv('Description', relay['group_description'])
                ui.badge(
                    'Enabled' if enabled else 'Disabled',
                    color='green' if enabled else 'grey',
                )


def _hyphae_relay_state_panel(device: Dict, colors: dict):
    """Show current relay states (ON/OFF) for all 6 relays."""
    ip = device.get('ip_address', '')
    state_data = fetch_hyphae_relay_state(ip) if ip else None
    relays = state_data.get('relays', []) if state_data else []

    if state_data:
        with ui.row().classes('w-full gap-4 flex-wrap q-mb-md'):
            _mini_stat('Total', str(state_data.get('total_relays', 0)), colors['primary'])
            _mini_stat('ON', str(state_data.get('relays_on', 0)), STATUS_COLORS['online'])
            _mini_stat('OFF', str(state_data.get('relays_off', 0)), STATUS_COLORS['offline'])

        if state_data.get('system_mode'):
            ui.label(f'System Mode: {state_data["system_mode"]}').classes('text-caption text-muted')
        if state_data.get('operation_mode'):
            ui.label(f'Operation Mode: {state_data["operation_mode"]}').classes('text-caption text-muted')

    with ui.row().classes('w-full gap-4 flex-wrap'):
        for i in range(1, 7):
            relay = next((r for r in relays if int(r.get('id', 0)) == i), None)
            is_on = relay.get('is_on', False) if relay else False
            relay_name = relay.get('name', f'Relay {i}') if relay else f'Relay {i}'

            with ui.card().classes('p-4 min-w-36 flex-1 text-center'):
                color = STATUS_COLORS['online'] if is_on else STATUS_COLORS['offline']
                ui.icon('toggle_on' if is_on else 'toggle_off', size='lg').style(f'color: {color}')
                ui.label(relay_name).classes('text-subtitle2 q-mt-xs')
                ui.badge(
                    'ON' if is_on else 'OFF',
                    color='green' if is_on else 'red',
                ).classes('q-mt-xs')

    if not relays and not state_data:
        ui.label('Could not fetch relay state. Device may be offline.').classes('text-muted')


def _hyphae_schedule_panel(device: Dict, colors: dict):
    """Show relay schedule settings (on/off times per group)."""
    ip = device.get('ip_address', '')
    device_id = device.get('device_id')

    # Try live data first
    schedule_data = fetch_hyphae_relay_schedule(ip) if ip else None
    groups = schedule_data.get('groups', []) if schedule_data else []

    # Fall back to database
    if not groups and device_id:
        db_schedules = get_device_schedule_settings(device_id)
        if db_schedules:
            groups = [
                {
                    'group_id': s.get('group_num', 0),
                    'group_name': f'Group {s.get("group_num", "?")}',
                    'on_time': s.get('on_time', 'N/A'),
                    'off_time': s.get('off_time', 'N/A'),
                }
                for s in db_schedules
            ]

    if not groups:
        ui.label('No schedule configuration available.').classes('text-muted')
        return

    ui.label(f'{len(groups)} group schedule(s)').classes('text-caption text-muted q-mb-md')

    with ui.row().classes('w-full gap-4 flex-wrap'):
        for group in groups:
            with ui.card().classes('p-4 min-w-48 flex-1'):
                ui.label(f'Group {group.get("group_id", "?")}: {group.get("group_name", "")}').classes(
                    'text-subtitle2 text-weight-bold')
                _kv('On Time', str(group.get('on_time', 'N/A')))
                _kv('Off Time', str(group.get('off_time', 'N/A')))


def _hyphae_dynamic_panel(device: Dict, colors: dict):
    """Show dynamic control settings (CO2/humidity/temp thresholds for groups 1-3)."""
    ip = device.get('ip_address', '')
    device_id = device.get('device_id')

    # Try live data first
    dynamic_data = fetch_hyphae_relay_dynamic(ip) if ip else None
    controls = dynamic_data.get('controls', []) if dynamic_data else []

    # Fall back to database
    if not controls and device_id:
        db_dynamics = get_device_dynamic_settings(device_id)
        if db_dynamics:
            controls = [
                {
                    'relay_id': f'Group {d.get("group_num", "?")}',
                    'relay_name': d.get('parameter', 'Unknown').title(),
                    'sensor_type': d.get('parameter', 'Unknown').title(),
                    'low_threshold': str(d.get('low_threshold', 0)),
                    'high_threshold': str(d.get('high_threshold', 0)),
                    'is_activate_high': d.get('behavior', 0) == 1,
                    'behavior': 'ACTIVATE HIGH' if d.get('behavior', 0) == 1 else 'ACTIVATE LOW',
                    'activate': True,
                }
                for d in db_dynamics
            ]

    if not controls:
        ui.label('No dynamic control configuration available.').classes('text-muted')
        return

    # Summary
    total = len(controls)
    active = len([c for c in controls if c.get('activate')])
    sensor_types = list({c.get('sensor_type', 'Unknown') for c in controls})

    with ui.row().classes('w-full gap-4 flex-wrap q-mb-md'):
        _mini_stat('Controls', str(total), colors['primary'])
        _mini_stat('Active', str(active), STATUS_COLORS['online'])
        _mini_stat('Sensor Types', str(len(sensor_types)), colors['primary'])

    if sensor_types:
        ui.label(f'Types: {", ".join(sensor_types)}').classes('text-caption text-muted q-mb-md')

    with ui.row().classes('w-full gap-4 flex-wrap'):
        for control in controls:
            is_active = control.get('activate', False)
            with ui.card().classes('p-4 min-w-56 flex-1'):
                ui.label(f'{control.get("relay_id", "")}: {control.get("relay_name", "")}').classes(
                    'text-subtitle2 text-weight-bold')
                _kv('Low Threshold', str(control.get('low_threshold', 'N/A')))
                _kv('High Threshold', str(control.get('high_threshold', 'N/A')))

                behavior_color = 'green' if control.get('is_activate_high') else 'blue'
                ui.badge(control.get('behavior', 'N/A'), color=behavior_color)

                if control.get('behavior_description'):
                    ui.label(control['behavior_description']).classes(
                        'text-caption text-muted q-mt-xs').style('font-style: italic')

                ui.badge(
                    'Active' if is_active else 'Inactive',
                    color='green' if is_active else 'grey',
                ).classes('q-mt-xs')


# ---------------------------------------------------------------------------
# Device Management panel (PIN + OTA) — shared by Spore and Hyphae
# ---------------------------------------------------------------------------

def _device_management_panel(device: Dict, device_type: str, colors: dict):
    """PIN management and OTA firmware update for a single device."""
    device_id = device.get('device_id')
    user_id = app.storage.user.get('user_id')

    from api.services.ota_service import OtaService
    ota_svc = OtaService()

    # --- PIN Section ---
    with ui.card().classes('w-full p-4 q-mb-md'):
        ui.label('Device PIN').classes('text-h6 q-mb-sm')

        pin_status = ota_svc.get_pin_status(device_id, device_type, user_id)
        status_map = {
            'device': ('Per-device PIN stored', 'positive'),
            'default': ('Using default PIN from Settings', 'info'),
            'missing': ('No PIN configured', 'negative'),
        }
        status_text, status_type = status_map.get(pin_status, ('Unknown', 'grey'))

        with ui.row().classes('items-center gap-2 q-mb-md'):
            ui.icon('vpn_key', size='sm').style(f'color: {colors["primary"]}')
            ui.label(f'Status: {status_text}').classes('text-caption')

        ui.label('Set a 5-digit PIN specific to this device (overrides default):').classes('text-caption text-muted q-mb-xs')

        with ui.row().classes('items-end gap-2'):
            pin_input = ui.input(
                label='Device PIN', placeholder='5-digit PIN',
            ).props('maxlength=5 type=password').classes('w-40')

            def save_pin():
                val = pin_input.value.strip() if pin_input.value else ''
                if not val or len(val) != 5 or not val.isdigit():
                    ui.notify('PIN must be exactly 5 digits', type='warning')
                    return
                store_device_pin(device_id, device_type, val)
                ui.notify('Device PIN saved', type='positive')
                pin_input.value = ''

            ui.button('Save PIN', icon='save', on_click=save_pin).props('color=primary size=sm')

            if has_stored_pin(device_id, device_type):
                from storage.tables.device_pins import delete_device_pin

                def clear_pin():
                    delete_device_pin(device_id, device_type)
                    ui.notify('Device PIN cleared — will fall back to default', type='info')

                ui.button('Clear', icon='delete', on_click=clear_pin).props('outline color=negative size=sm')

    # --- OTA Section ---
    with ui.card().classes('w-full p-4'):
        ui.label('Firmware Update (OTA)').classes('text-h6 q-mb-sm')

        # Check PIN availability
        pin = ota_svc.resolve_pin(device_id, device_type, user_id)
        if not pin:
            ui.label('A device PIN is required for OTA updates. Set one above or configure a default in Settings.').classes(
                'text-negative q-mb-md')

        # Firmware selector
        from storage.tables.firmware_versions import get_all_firmware_versions
        available_fw = get_all_firmware_versions(device_type=device_type)

        if not available_fw:
            ui.label(f'No {device_type} firmware uploaded. Go to Fleet Management to upload firmware.').classes('text-muted')
            ui.button('Go to Fleet', icon='inventory',
                      on_click=lambda: ui.navigate.to('/fleet')).props('outline size=sm').classes('q-mt-sm')
            return

        fw_options = {
            fw['version_id']: f"v{fw['version']} — {fw.get('file_size', 0) // 1024}KB ({fw.get('uploaded_at', '')[:10]})"
            for fw in available_fw
        }
        fw_select = ui.select(
            options=fw_options,
            label='Select firmware version',
        ).classes('w-full q-mb-md')

        progress_label = ui.label('').classes('text-caption text-muted')
        progress_bar = ui.linear_progress(value=0, show_value=False).classes('w-full')
        progress_bar.set_visibility(False)

        async def start_ota():
            if not fw_select.value:
                ui.notify('Select a firmware version', type='warning')
                return
            if not pin:
                ui.notify('No PIN available. Set a device PIN or default PIN first.', type='negative')
                return

            fw = next((f for f in available_fw if f['version_id'] == fw_select.value), None)
            if not fw:
                ui.notify('Firmware not found', type='negative')
                return

            firmware_path = fw['file_path']

            progress_bar.set_visibility(True)
            progress_label.text = 'Starting OTA upload...'

            def on_progress(pct, msg):
                progress_bar.value = pct / 100.0
                progress_label.text = msg

            result = await ota_svc.upload_firmware(
                device_id, device_type, firmware_path,
                user_id=user_id,
                on_progress=on_progress,
            )

            if result.get('success'):
                progress_bar.value = 1.0
                progress_label.text = 'OTA complete! Device is rebooting.'
                ui.notify('Firmware uploaded successfully', type='positive')
            else:
                progress_label.text = f'OTA failed: {result.get("error", "Unknown error")}'
                ui.notify(f'OTA failed: {result.get("error")}', type='negative')

        ui.button('Upload Firmware', icon='system_update',
                  on_click=start_ota).props('color=primary')

        # OTA history for this device
        from storage.tables.ota_history import get_ota_history
        history = get_ota_history(device_id=device_id, device_type=device_type, limit=5)
        if history:
            ui.separator().classes('q-my-md')
            ui.label('Recent OTA History').classes('text-subtitle2 q-mb-xs')
            for h in history:
                status_color = 'green' if h.get('status') == 'success' else 'red'
                with ui.row().classes('items-center gap-2'):
                    ui.badge(h.get('status', '?'), color=status_color)
                    ui.label(h.get('firmware_name', '')).classes('text-caption')
                    ui.label(h.get('started_at', '')[:16]).classes('text-caption text-muted')
                    if h.get('error_message'):
                        ui.label(h['error_message']).classes('text-caption text-negative')


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _kv(key: str, value: str):
    """Render a key-value pair on a single row."""
    with ui.row().classes('items-baseline gap-2'):
        ui.label(f'{key}:').classes('text-weight-bold text-caption')
        ui.label(value).classes('text-caption')


def _mini_stat(label: str, value: str, accent: str):
    """Small stat badge used in summary rows."""
    with ui.card().classes('p-3 min-w-24 text-center'):
        ui.label(value).classes('text-h5').style(f'color: {accent}')
        ui.label(label).classes('text-caption text-muted')


async def _run_mdns_discovery(colors: dict, stat_cards=None):
    """Run mDNS + CIDR discovery and display results in a dialog."""
    rooms = _room_options()

    with ui.dialog() as dlg, ui.card().classes('p-4 min-w-96'):
        ui.label('Device Discovery').classes('text-h6 q-mb-sm')
        status_label = ui.label('Scanning network via mDNS...').classes('text-muted')
        results_container = ui.column().classes('w-full q-mt-sm')
        ui.button('Close', on_click=dlg.close).props('outline').classes('q-mt-md')
    dlg.open()

    # Check for existing devices to detect duplicates
    existing_ips = set()
    for d in _safe_get_spore_devices():
        existing_ips.add(d.get('ip_address'))
    for d in _safe_get_hyphae_devices():
        existing_ips.add(d.get('ip_address'))

    try:
        from api.services.discovery_service import DeviceDiscoveryService
        svc = DeviceDiscoveryService()
        discovered = await svc.discover_mdns(timeout=5.0)

        if discovered:
            status_label.text = f'Found {len(discovered)} device(s) via mDNS'
            with results_container:
                for hostname, info in discovered.items():
                    ip = info.get('ip_address', '')
                    device_type = info.get('device_type', '').lower()
                    already_added = ip in existing_ips

                    with ui.card().classes('w-full p-3 q-mb-xs'):
                        with ui.row().classes('items-center justify-between w-full'):
                            with ui.column().classes('gap-0'):
                                ui.label(info.get('device_name', hostname)).classes('text-weight-bold')
                                ui.label(f'{device_type} — {ip}').classes('text-caption text-muted')
                                if info.get('hostname'):
                                    ui.label(info['hostname']).classes('text-caption text-muted')

                            if already_added:
                                ui.badge('Already Added').props('color=grey')
                            elif device_type in ('spore', 'hyphae') and rooms:
                                room_select = ui.select(
                                    options=rooms, label='Room', with_input=True,
                                ).classes('min-w-32')

                                def _make_add_handler(dev_ip, dev_type, room_sel):
                                    def handler():
                                        room_id = room_sel.value
                                        if not room_id:
                                            ui.notify('Select a room first.', type='warning')
                                            return
                                        if dev_type == 'spore':
                                            result = store_complete_spore_device_data(dev_ip, room_id)
                                        else:
                                            result = store_complete_hyphae_device_data(dev_ip, room_id)
                                        if result.get('success'):
                                            existing_ips.add(dev_ip)
                                            ui.notify(f'{dev_type.title()} at {dev_ip} added.', type='positive')
                                            if stat_cards:
                                                stat_cards.refresh()
                                        else:
                                            errors = '; '.join(result.get('errors', ['Unknown error']))
                                            ui.notify(f'Error: {errors}', type='negative')
                                    return handler

                                ui.button('Add', icon='add',
                                          on_click=_make_add_handler(ip, device_type, room_select)
                                          ).props('dense color=primary')
                            else:
                                ui.badge(device_type.upper() or '?').props('color=primary')
        else:
            status_label.text = 'No devices found via mDNS. Devices may not be advertising _https._tcp.'
    except ImportError:
        status_label.text = 'zeroconf not installed. Run: pip install zeroconf'
    except Exception as e:
        status_label.text = f'Discovery error: {e}'


# ---------------------------------------------------------------------------
# CSV export / import
# ---------------------------------------------------------------------------

def _export_devices_csv(device_type: str):
    """Export devices to CSV and trigger download."""
    import csv
    import io

    devices = _safe_get_spore_devices() if device_type == 'spore' else _safe_get_hyphae_devices()
    if not devices:
        ui.notify(f'No {device_type} devices to export.', type='info')
        return

    output = io.StringIO()
    fields = ['device_name', 'ip_address', 'mac_address', 'room_name',
              'firmware_version', 'is_online']
    if device_type == 'spore':
        fields.append('hyphae_id')

    writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    for d in devices:
        writer.writerow(d)

    ui.download(output.getvalue().encode(), f'mycelium_{device_type}_devices.csv')


def _open_import_csv_dialog(device_type: str, table_refresh, stat_cards_refresh):
    """Open a dialog for importing devices from a CSV file."""
    import csv
    import io
    import base64

    rooms = _room_options()

    with ui.dialog() as dialog, ui.card().classes('min-w-[500px] p-4'):
        ui.label(f'Import {device_type.title()} Devices from CSV').classes('text-h6 q-mb-sm')

        ui.label(
            'CSV must have columns: device_name, ip_address. '
            'Optional: mac_address, room_id.'
        ).classes('text-caption text-muted q-mb-md')

        # Template download
        def _download_template():
            if device_type == 'spore':
                header = 'device_name,ip_address,mac_address,room_id\nMy-Spore,192.168.1.100,,1\n'
            else:
                header = 'device_name,ip_address,mac_address,room_id,pin\nMy-Hyphae,192.168.1.200,,1,12345\n'
            ui.download(header.encode(), f'{device_type}_template.csv')

        ui.button('Download Template', icon='description',
                  on_click=_download_template).props('outline dense')

        room_select = ui.select(
            options=rooms, label='Default Room (for rows without room_id)', with_input=True,
        ).classes('w-full q-mt-md')

        upload_area = ui.upload(
            label='Drop CSV file here or click to browse',
            auto_upload=True,
            max_files=1,
        ).classes('w-full q-mt-sm').props('accept=.csv')

        status_label = ui.label('').classes('text-muted q-mt-sm')

        uploaded_rows = []

        def on_upload(e):
            uploaded_rows.clear()
            try:
                content = e.content.read().decode('utf-8')
                reader = csv.DictReader(io.StringIO(content))
                for row in reader:
                    uploaded_rows.append(dict(row))
                status_label.text = f'Parsed {len(uploaded_rows)} row(s) from CSV'
            except Exception as exc:
                status_label.text = f'Error parsing CSV: {exc}'

        upload_area.on('upload', on_upload)

        with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
            ui.button('Cancel', on_click=dialog.close).props('flat')

            def _do_import():
                if not uploaded_rows:
                    ui.notify('No CSV data loaded.', type='warning')
                    return
                default_room = room_select.value
                if not default_room:
                    ui.notify('Select a default room.', type='warning')
                    return

                success, errors = 0, 0
                for row in uploaded_rows:
                    ip = (row.get('ip_address') or '').strip()
                    if not ip:
                        errors += 1
                        continue
                    row_room = row.get('room_id') or default_room
                    try:
                        if device_type == 'spore':
                            result = store_complete_spore_device_data(ip, row_room)
                        else:
                            pin = row.get('pin', '')
                            result = store_complete_hyphae_device_data(ip, row_room, pin or None)
                        if result.get('success'):
                            success += 1
                        else:
                            errors += 1
                    except Exception:
                        errors += 1

                table_refresh.refresh()
                stat_cards_refresh.refresh()
                dialog.close()
                if errors == 0:
                    ui.notify(f'Imported {success} device(s).', type='positive')
                else:
                    ui.notify(f'Imported {success}, failed {errors}.', type='warning')

            ui.button('Import', icon='upload', on_click=_do_import).props('color=primary')

    dialog.open()
