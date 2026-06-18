"""
Farm Overview page for Mycelium NiceGUI application.

Full CRUD for farms and rooms. Each farm expands to show its rooms,
and each room shows assigned device counts. Device assignment is
managed from the Devices page.
"""

from nicegui import ui, app
from web_ui.layout import page_layout, back_to_dashboard
from web_ui.theme import get_colors

from storage.tables.farms import (
    get_all_farms, create_farm, update_farm, get_farm,
    deactivate_farm, reactivate_farm, get_farm_statistics,
)
from storage.tables.grow_rooms import (
    get_all_grow_rooms, create_grow_room, update_grow_room,
    deactivate_grow_room, reactivate_grow_room,
)
from storage.tables.device_spore import get_all_device_spore
from storage.tables.device_hyphae import get_all_device_hyphae


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

@ui.page('/farms')
@ui.page('/farm-overview')
def farm_overview_page():
    """Farm overview with full CRUD for farms and rooms."""
    user = app.storage.user
    if not user.get('user_id'):
        ui.navigate.to('/login')
        return

    page_layout('Farm Overview')
    back_to_dashboard()
    colors = get_colors()

    with ui.column().classes('w-full max-w-6xl mx-auto p-4 gap-4'):
        # Header
        with ui.row().classes('w-full items-center justify-between'):
            with ui.column().classes('gap-0'):
                ui.label('Farm Overview').classes('text-h4')
                ui.label('Manage farms, rooms, and view device assignments').classes('text-muted')
            ui.button('Add Farm', icon='add',
                      on_click=lambda: _open_add_farm_dialog(colors)).props('color=primary')

        # Summary stats
        _summary_row(colors)

        # Farm cards (refreshable)
        farm_list(colors)


# ---------------------------------------------------------------------------
# Refreshable farm list
# ---------------------------------------------------------------------------

@ui.refreshable
def farm_list(colors: dict):
    """Render all farm cards with expandable room sections."""
    farms = get_all_farms(active_only=False)

    if not farms:
        with ui.card().classes('w-full p-6 text-center'):
            ui.icon('info', size='md').classes('text-muted')
            ui.label('No farms yet. Click "Add Farm" to get started.').classes('text-muted')
        return

    for farm in farms:
        _farm_card(farm, colors)


# ---------------------------------------------------------------------------
# Summary row
# ---------------------------------------------------------------------------

def _summary_row(colors: dict):
    """Top-level summary stat cards."""
    farms = get_all_farms(active_only=True)
    rooms = get_all_grow_rooms(active_only=True)
    spores = get_all_device_spore()
    hyphaes = get_all_device_hyphae()

    with ui.row().classes('w-full gap-4 flex-wrap'):
        _stat_card('Farms', str(len(farms)), 'agriculture', colors)
        _stat_card('Rooms', str(len(rooms)), 'meeting_room', colors)
        _stat_card('Spores', str(len(spores)), 'sensors', colors)
        _stat_card('Hyphae', str(len(hyphaes)), 'device_hub', colors)


def _stat_card(label, value, icon, colors):
    with ui.card().classes('p-4 flex-1 min-w-40 text-center'):
        ui.icon(icon, size='sm').style(f'color: {colors["primary"]}')
        ui.label(value).classes('text-h4')
        ui.label(label).classes('text-caption text-muted')


# ---------------------------------------------------------------------------
# Farm card
# ---------------------------------------------------------------------------

def _farm_card(farm: dict, colors: dict):
    """Single farm card with stats, edit/deactivate, and expandable room list."""
    fid = farm['farm_id']
    is_active = farm.get('is_active', 1)
    stats = _safe_stats(fid)

    opacity = '' if is_active else 'opacity: 0.55;'

    with ui.card().classes('w-full').style(opacity):
        # Farm header row
        with ui.row().classes('w-full items-center px-4 pt-4 pb-2'):
            ui.icon('agriculture', size='sm').style(f'color: {colors["primary"]}')
            with ui.column().classes('flex-grow gap-0'):
                with ui.row().classes('items-center gap-2'):
                    ui.label(farm.get('farm_name', '?')).classes('text-h6')
                    if not is_active:
                        ui.badge('Inactive', color='grey').props('outline')
                ui.label(farm.get('farm_loc', '') or 'No location').classes('text-caption text-muted')
            # Action buttons
            with ui.row().classes('gap-1'):
                ui.button(icon='edit', on_click=lambda f=farm: _open_edit_farm_dialog(f, colors)).props(
                    'flat dense color=primary size=sm')
                if is_active:
                    ui.button(icon='archive', on_click=lambda f=farm: _confirm_deactivate_farm(f, colors)).props(
                        'flat dense color=negative size=sm').tooltip('Deactivate')
                else:
                    ui.button(icon='unarchive', on_click=lambda f=farm: _reactivate_farm(f)).props(
                        'flat dense color=positive size=sm').tooltip('Reactivate')

        # Stats row
        with ui.row().classes('w-full px-4 pb-2 gap-6'):
            _inline_stat('Rooms', stats.get('room_count', 0))
            _inline_stat('Spores', stats.get('spore_count', 0))
            _inline_stat('Hyphae', stats.get('hyphae_count', 0))
            online = stats.get('online_devices', 0)
            total = stats.get('total_devices', 0)
            _inline_stat('Online', f'{online}/{total}')

        # Health bar
        if total > 0:
            pct = online / total
            with ui.column().classes('w-full px-4 pb-2 gap-0'):
                ui.linear_progress(value=pct, show_value=False).props('color=primary')

        # Expandable rooms section
        with ui.expansion('Rooms', icon='meeting_room').classes('w-full'):
            _room_section(fid, colors)


def _inline_stat(label, value):
    with ui.column().classes('items-center gap-0'):
        ui.label(str(value)).classes('text-weight-bold')
        ui.label(label).classes('text-caption text-muted')


# ---------------------------------------------------------------------------
# Room section (inside farm expansion)
# ---------------------------------------------------------------------------

def _room_section(farm_id: int, colors: dict):
    """List rooms for a farm with add/edit/deactivate."""
    rooms = get_all_grow_rooms(farm_id=farm_id, active_only=False)

    with ui.row().classes('w-full justify-end q-mb-sm'):
        ui.button('Add Room', icon='add',
                  on_click=lambda: _open_add_room_dialog(farm_id, colors)).props('outline size=sm')

    if not rooms:
        ui.label('No rooms in this farm yet.').classes('text-muted text-center')
        return

    for room in rooms:
        _room_row(room, colors)


def _room_row(room: dict, colors: dict):
    """Single room row with device counts and actions."""
    rid = room['room_id']
    is_active = room.get('is_active', 1)

    # Count devices in this room
    spores = [d for d in get_all_device_spore() if d.get('room_id') == rid]
    hyphaes = [d for d in get_all_device_hyphae() if d.get('room_id') == rid]

    opacity = '' if is_active else 'opacity: 0.55;'

    with ui.card().classes('w-full p-3').style(opacity):
        with ui.row().classes('w-full items-center'):
            ui.icon('meeting_room', size='xs').style(f'color: {colors["primary"]}')
            with ui.column().classes('flex-grow gap-0 q-ml-sm'):
                with ui.row().classes('items-center gap-2'):
                    ui.label(room.get('room_name', '?')).classes('text-weight-bold')
                    if not is_active:
                        ui.badge('Inactive', color='grey').props('outline')
                desc = room.get('room_desc') or ''
                if desc:
                    ui.label(desc).classes('text-caption text-muted')

            # Device counts
            with ui.row().classes('gap-3 items-center'):
                with ui.row().classes('items-center gap-1'):
                    ui.icon('sensors', size='xs').classes('text-muted')
                    ui.label(str(len(spores))).classes('text-caption')
                with ui.row().classes('items-center gap-1'):
                    ui.icon('device_hub', size='xs').classes('text-muted')
                    ui.label(str(len(hyphaes))).classes('text-caption')

            # Actions
            with ui.row().classes('gap-1'):
                ui.button(icon='edit',
                          on_click=lambda r=room: _open_edit_room_dialog(r, colors)).props(
                    'flat dense size=sm color=primary')
                if is_active:
                    ui.button(icon='archive',
                              on_click=lambda r=room: _confirm_deactivate_room(r, colors)).props(
                        'flat dense size=sm color=negative').tooltip('Deactivate')
                else:
                    ui.button(icon='unarchive',
                              on_click=lambda r=room: _reactivate_room(r)).props(
                        'flat dense size=sm color=positive').tooltip('Reactivate')


# ---------------------------------------------------------------------------
# Farm dialogs
# ---------------------------------------------------------------------------

def _open_add_farm_dialog(colors: dict):
    with ui.dialog() as dlg, ui.card().classes('p-4 min-w-96'):
        ui.label('Add Farm').classes('text-h6 q-mb-md')
        name = ui.input(label='Farm Name', placeholder='e.g., Main Farm').classes('w-full')
        loc = ui.input(label='Location', placeholder='e.g., 123 Farm Road').classes('w-full')
        desc = ui.textarea(label='Description (optional)').classes('w-full')

        with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
            ui.button('Cancel', on_click=dlg.close).props('outline color=grey')

            def save():
                if not name.value or not name.value.strip():
                    ui.notify('Farm name is required', type='warning')
                    return
                create_farm(name.value.strip(),
                            farm_loc=loc.value.strip() if loc.value else '',
                            farm_desc=desc.value.strip() if desc.value else '')
                ui.notify('Farm created', type='positive')
                dlg.close()
                farm_list.refresh()

            ui.button('Save', icon='save', on_click=save).props('color=primary')
    dlg.open()


def _open_edit_farm_dialog(farm: dict, colors: dict):
    with ui.dialog() as dlg, ui.card().classes('p-4 min-w-96'):
        ui.label('Edit Farm').classes('text-h6 q-mb-md')
        name = ui.input(label='Farm Name', value=farm.get('farm_name', '')).classes('w-full')
        loc = ui.input(label='Location', value=farm.get('farm_loc', '')).classes('w-full')
        desc = ui.textarea(label='Description', value=farm.get('farm_desc', '')).classes('w-full')

        with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
            ui.button('Cancel', on_click=dlg.close).props('outline color=grey')

            def save():
                if not name.value or not name.value.strip():
                    ui.notify('Farm name is required', type='warning')
                    return
                update_farm(farm['farm_id'],
                            farm_name=name.value.strip(),
                            farm_loc=loc.value.strip() if loc.value else '',
                            farm_desc=desc.value.strip() if desc.value else '')
                ui.notify('Farm updated', type='positive')
                dlg.close()
                farm_list.refresh()

            ui.button('Save', icon='save', on_click=save).props('color=primary')
    dlg.open()


def _confirm_deactivate_farm(farm: dict, colors: dict):
    with ui.dialog() as dlg, ui.card().classes('p-4'):
        ui.label(f'Deactivate "{farm.get("farm_name")}"?').classes('text-h6 q-mb-sm')
        ui.label('The farm and its rooms will be hidden but not deleted.').classes('text-muted q-mb-md')
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=dlg.close).props('outline')
            def confirm():
                deactivate_farm(farm['farm_id'])
                ui.notify('Farm deactivated', type='info')
                dlg.close()
                farm_list.refresh()
            ui.button('Deactivate', on_click=confirm).props('color=negative')
    dlg.open()


def _reactivate_farm(farm: dict):
    reactivate_farm(farm['farm_id'])
    ui.notify('Farm reactivated', type='positive')
    farm_list.refresh()


# ---------------------------------------------------------------------------
# Room dialogs
# ---------------------------------------------------------------------------

def _open_add_room_dialog(farm_id: int, colors: dict):
    with ui.dialog() as dlg, ui.card().classes('p-4 min-w-96'):
        ui.label('Add Room').classes('text-h6 q-mb-md')
        name = ui.input(label='Room Name', placeholder='e.g., Fruiting Chamber A').classes('w-full')
        desc = ui.textarea(label='Description (optional)').classes('w-full')

        with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
            ui.button('Cancel', on_click=dlg.close).props('outline color=grey')

            def save():
                if not name.value or not name.value.strip():
                    ui.notify('Room name is required', type='warning')
                    return
                create_grow_room(farm_id, name.value.strip(),
                                 room_desc=desc.value.strip() if desc.value else '')
                ui.notify('Room created', type='positive')
                dlg.close()
                farm_list.refresh()

            ui.button('Save', icon='save', on_click=save).props('color=primary')
    dlg.open()


def _open_edit_room_dialog(room: dict, colors: dict):
    with ui.dialog() as dlg, ui.card().classes('p-4 min-w-96'):
        ui.label('Edit Room').classes('text-h6 q-mb-md')
        name = ui.input(label='Room Name', value=room.get('room_name', '')).classes('w-full')
        desc = ui.textarea(label='Description', value=room.get('room_desc', '')).classes('w-full')

        with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
            ui.button('Cancel', on_click=dlg.close).props('outline color=grey')

            def save():
                if not name.value or not name.value.strip():
                    ui.notify('Room name is required', type='warning')
                    return
                update_grow_room(room['room_id'],
                                 room_name=name.value.strip(),
                                 room_desc=desc.value.strip() if desc.value else '')
                ui.notify('Room updated', type='positive')
                dlg.close()
                farm_list.refresh()

            ui.button('Save', icon='save', on_click=save).props('color=primary')
    dlg.open()


def _confirm_deactivate_room(room: dict, colors: dict):
    with ui.dialog() as dlg, ui.card().classes('p-4'):
        ui.label(f'Deactivate "{room.get("room_name")}"?').classes('text-h6 q-mb-sm')
        ui.label('Devices in this room will remain but become unassigned.').classes('text-muted q-mb-md')
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=dlg.close).props('outline')
            def confirm():
                deactivate_grow_room(room['room_id'])
                ui.notify('Room deactivated', type='info')
                dlg.close()
                farm_list.refresh()
            ui.button('Deactivate', on_click=confirm).props('color=negative')
    dlg.open()


def _reactivate_room(room: dict):
    reactivate_grow_room(room['room_id'])
    ui.notify('Room reactivated', type='positive')
    farm_list.refresh()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_stats(farm_id: int) -> dict:
    try:
        return get_farm_statistics(farm_id)
    except Exception:
        return {
            'room_count': 0, 'spore_count': 0, 'hyphae_count': 0,
            'online_devices': 0, 'total_devices': 0, 'online_pct': 0,
        }
