"""
Alerts page for Mycelium NiceGUI application.

Provides alert management with active alerts, alert history, and rule configuration.
"""

from datetime import datetime
from typing import Optional

from nicegui import ui, app
from web_ui.layout import page_layout, back_to_dashboard
from web_ui.theme import get_colors

from api.services.alert_service import AlertService
from storage.tables import device_spore, device_hyphae, grow_rooms


# Alert type display mappings
ALERT_TYPE_LABELS = {
    'offline': 'Device Offline',
    'threshold_high': 'High Threshold',
    'threshold_low': 'Low Threshold',
    'degraded': 'Performance Degraded',
    'error': 'Device Error',
}

ALERT_ICON_MAP = {
    'offline': 'wifi_off',
    'threshold_high': 'thermostat',
    'threshold_low': 'ac_unit',
    'error': 'error',
    'degraded': 'speed',
}

ALERT_COLOR_MAP = {
    'offline': '#e74c3c',
    'threshold_high': '#f39c12',
    'threshold_low': '#3498db',
    'error': '#e74c3c',
    'degraded': '#f39c12',
}


def format_time_ago(timestamp_str: Optional[str]) -> str:
    """Format a timestamp string as a relative time description."""
    if not timestamp_str:
        return "Unknown"
    try:
        ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.now()
        if ts.tzinfo:
            now = now.replace(tzinfo=ts.tzinfo)
        diff = now - ts
        seconds = diff.total_seconds()
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m ago"
        elif seconds < 86400:
            return f"{int(seconds // 3600)}h ago"
        else:
            return f"{int(seconds // 86400)}d ago"
    except (ValueError, TypeError):
        return timestamp_str[:16] if timestamp_str else "Unknown"


def _get_device_options() -> dict:
    """Build device dropdown options from spore and hyphae tables."""
    options = {'': 'All Devices'}
    try:
        for d in device_spore.get_all_device_spore(active_only=True):
            key = f"spore:{d['device_id']}"
            options[key] = f"[Spore] {d.get('device_name', d.get('device_id'))}"
    except Exception:
        pass
    try:
        for d in device_hyphae.get_all_device_hyphae(active_only=True):
            key = f"hyphae:{d['device_id']}"
            options[key] = f"[Hyphae] {d.get('device_name', d.get('device_id'))}"
    except Exception:
        pass
    return options


def _get_room_options() -> dict:
    """Build room dropdown options."""
    options = {'': 'All Rooms'}
    try:
        for r in grow_rooms.get_all_grow_rooms(active_only=True):
            options[str(r['room_id'])] = r['room_name']
    except Exception:
        pass
    return options


@ui.page('/alerts')
def alerts_page():
    """Alert management page with active alerts, history, and rule configuration."""
    user = app.storage.user
    if not user.get('user_id'):
        ui.navigate.to('/login')
        return

    page_layout('Alerts')
    back_to_dashboard()
    colors = get_colors()
    alert_service = AlertService()

    with ui.column().classes('w-full max-w-6xl mx-auto p-4 gap-4'):
        # Page header
        with ui.row().classes('items-center gap-2'):
            ui.icon('notifications', size='md').style(f'color: {colors["primary"]}')
            ui.label('Alert Management').classes('text-h4')

        # Summary cards row
        _render_summary_cards(alert_service, colors)

        # Tabs
        with ui.tabs().classes('w-full') as tabs:
            ui.tab('active', label='Active Alerts', icon='warning')
            ui.tab('history', label='Alert History', icon='history')
            ui.tab('rules', label='Alert Rules', icon='rule')

        with ui.tab_panels(tabs, value='active').classes('w-full'):
            with ui.tab_panel('active'):
                active_alerts_list(alert_service, user, colors)

            with ui.tab_panel('history'):
                alert_history_list(alert_service, colors)

            with ui.tab_panel('rules'):
                alert_rules_list(alert_service, colors)


def _render_summary_cards(alert_service: AlertService, colors: dict):
    """Render the four summary statistic cards."""
    try:
        counts = alert_service.get_alert_counts()
    except Exception:
        counts = {}

    active_count = counts.get('active', 0)
    unack_count = counts.get('unacknowledged', 0)
    total_24h = counts.get('total_24h', 0)

    try:
        rules_count = len(alert_service.get_all_rules())
    except Exception:
        rules_count = 0

    with ui.row().classes('w-full gap-4 flex-wrap'):
        # Active Alerts
        border_style = 'border-left: 4px solid #e74c3c' if active_count > 0 else ''
        with ui.card().classes('p-4 flex-1 min-w-48 text-center').style(border_style):
            ui.label('Active Alerts').classes('text-subtitle2 text-muted')
            ui.label(str(active_count)).classes('text-h3').style(
                'color: #e74c3c' if active_count > 0 else ''
            )

        # Unacknowledged
        border_style = 'border-left: 4px solid #f39c12' if unack_count > 0 else ''
        with ui.card().classes('p-4 flex-1 min-w-48 text-center').style(border_style):
            ui.label('Unacknowledged').classes('text-subtitle2 text-muted')
            ui.label(str(unack_count)).classes('text-h3').style(
                'color: #f39c12' if unack_count > 0 else ''
            )

        # Last 24h
        with ui.card().classes('p-4 flex-1 min-w-48 text-center'):
            ui.label('Last 24h').classes('text-subtitle2 text-muted')
            ui.label(str(total_24h)).classes('text-h3')

        # Alert Rules
        with ui.card().classes('p-4 flex-1 min-w-48 text-center'):
            ui.label('Alert Rules').classes('text-subtitle2 text-muted')
            ui.label(str(rules_count)).classes('text-h3')


def _render_alert_card(alert: dict, alert_service: AlertService,
                       user: dict, colors: dict, refresh_fn):
    """Render a single alert card with action buttons."""
    rule_type = alert.get('rule_type', 'unknown')
    icon = ALERT_ICON_MAP.get(rule_type, 'notifications')
    icon_color = ALERT_COLOR_MAP.get(rule_type, colors['primary'])

    is_acknowledged = alert.get('acknowledged', 0)
    is_resolved = alert.get('resolved_at') is not None

    with ui.card().classes('w-full p-3'):
        with ui.row().classes('w-full items-start justify-between'):
            # Left: alert info
            with ui.column().classes('flex-1 gap-1'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon(icon).style(f'color: {icon_color}; font-size: 1.3rem')
                    ui.label(alert.get('rule_name', 'Alert')).classes('text-weight-bold')
                    if is_resolved:
                        ui.badge('Resolved', color='green').props('outline')
                    elif is_acknowledged:
                        ui.badge('Acknowledged', color='orange').props('outline')
                    else:
                        ui.badge('Active', color='red').props('outline')

                ui.label(alert.get('alert_message', '')).classes('text-body2')

                with ui.row().classes('items-center gap-1'):
                    ui.icon('schedule', size='xs').classes('text-muted')
                    ui.label(format_time_ago(alert.get('triggered_at', ''))).classes(
                        'text-caption text-muted'
                    )

            # Right: action buttons
            alert_id = alert.get('alert_id')
            with ui.row().classes('gap-1'):
                ui.button(icon='visibility', on_click=lambda a=alert: _show_alert_detail(a)).props(
                    'flat dense size=sm'
                ).tooltip('View Details')

                ack_btn = ui.button(
                    icon='check',
                    on_click=lambda aid=alert_id: _acknowledge_alert(
                        aid, alert_service, user, refresh_fn
                    ),
                ).props('flat dense size=sm color=orange')
                ack_btn.tooltip('Acknowledge')
                if is_acknowledged or is_resolved:
                    ack_btn.disable()

                resolve_btn = ui.button(
                    icon='done_all',
                    on_click=lambda aid=alert_id: _resolve_alert(
                        aid, alert_service, refresh_fn
                    ),
                ).props('flat dense size=sm color=green')
                resolve_btn.tooltip('Resolve')
                if is_resolved:
                    resolve_btn.disable()


def _show_alert_detail(alert: dict):
    """Show alert detail in a dialog."""
    with ui.dialog() as dialog, ui.card().classes('min-w-96 p-4'):
        ui.label('Alert Details').classes('text-h6 q-mb-md')
        ui.separator()

        with ui.column().classes('gap-2 q-mt-md'):
            with ui.row().classes('gap-2'):
                ui.label('Rule:').classes('text-weight-bold')
                ui.label(alert.get('rule_name', 'N/A'))

            with ui.row().classes('gap-2'):
                ui.label('Type:').classes('text-weight-bold')
                ui.label(ALERT_TYPE_LABELS.get(
                    alert.get('rule_type', ''), alert.get('rule_type', 'N/A')
                ))

            with ui.row().classes('gap-2'):
                ui.label('Message:').classes('text-weight-bold')
                ui.label(alert.get('alert_message', 'N/A'))

            with ui.row().classes('gap-2'):
                ui.label('Triggered:').classes('text-weight-bold')
                ui.label(alert.get('triggered_at', 'N/A'))

            if alert.get('acknowledged'):
                with ui.row().classes('gap-2'):
                    ui.label('Acknowledged:').classes('text-weight-bold')
                    ui.label(alert.get('acknowledged_at', 'Yes'))

            if alert.get('resolved_at'):
                with ui.row().classes('gap-2'):
                    ui.label('Resolved:').classes('text-weight-bold')
                    ui.label(alert.get('resolved_at', 'N/A'))

            if alert.get('device_name'):
                with ui.row().classes('gap-2'):
                    ui.label('Device:').classes('text-weight-bold')
                    ui.label(alert['device_name'])

        ui.separator()
        with ui.row().classes('w-full justify-end q-mt-sm'):
            ui.button('Close', on_click=dialog.close).props('flat')

    dialog.open()


def _acknowledge_alert(alert_id: int, alert_service: AlertService,
                       user: dict, refresh_fn):
    """Acknowledge an alert and refresh the list."""
    try:
        alert_service.acknowledge_alert(alert_id, user_id=user.get('user_id', 1))
        ui.notify('Alert acknowledged', type='positive')
        refresh_fn()
    except Exception as e:
        ui.notify(f'Failed to acknowledge alert: {e}', type='negative')


def _resolve_alert(alert_id: int, alert_service: AlertService, refresh_fn):
    """Resolve an alert and refresh the list."""
    try:
        alert_service.resolve_alert(alert_id)
        ui.notify('Alert resolved', type='positive')
        refresh_fn()
    except Exception as e:
        ui.notify(f'Failed to resolve alert: {e}', type='negative')


@ui.refreshable
def active_alerts_list(alert_service: AlertService, user: dict, colors: dict):
    """Render the list of active alerts."""
    try:
        alerts = alert_service.get_active_alerts()
    except Exception:
        alerts = []

    if not alerts:
        with ui.card().classes('w-full p-6 text-center'):
            ui.icon('check_circle', size='xl').style('color: #2ecc71')
            ui.label('No active alerts').classes('text-h6 q-mt-sm')
            ui.label('All systems operating normally.').classes('text-muted')
        return

    # Bulk acknowledge button
    unack = [a for a in alerts if not a.get('acknowledged')]
    if len(unack) > 1:
        def _ack_all():
            uid = user.get('user_id', 1)
            for a in unack:
                try:
                    alert_service.acknowledge_alert(a['alert_id'], user_id=uid)
                except Exception:
                    pass
            ui.notify(f'Acknowledged {len(unack)} alert(s)', type='positive')
            active_alerts_list.refresh()

        ui.button(f'Acknowledge All ({len(unack)})', icon='done_all',
                  on_click=_ack_all).props('outline color=orange').classes('q-mb-sm')

    for alert in alerts:
        _render_alert_card(alert, alert_service, user, colors, active_alerts_list.refresh)


@ui.refreshable
def alert_history_list(alert_service: AlertService, colors: dict):
    """Render the alert history for the last 7 days."""
    try:
        alerts = alert_service.get_alert_history(days=7)
    except Exception:
        alerts = []

    if not alerts:
        with ui.card().classes('w-full p-6 text-center'):
            ui.icon('info', size='xl').style(f'color: {colors["primary"]}')
            ui.label('No alerts in the last 7 days').classes('text-h6 q-mt-sm')
        return

    user = app.storage.user
    for alert in alerts:
        _render_alert_card(alert, alert_service, user, colors, alert_history_list.refresh)


@ui.refreshable
def alert_rules_list(alert_service: AlertService, colors: dict):
    """Render the list of alert rules with management controls."""
    ui.button('Add Alert Rule', icon='add', on_click=lambda: _open_add_rule_dialog(
        alert_service, colors
    )).props('color=primary').classes('q-mb-md')

    try:
        rules = alert_service.get_all_rules()
    except Exception:
        rules = []

    if not rules:
        with ui.card().classes('w-full p-6 text-center'):
            ui.icon('info', size='xl').style(f'color: {colors["primary"]}')
            ui.label('No alert rules configured').classes('text-h6 q-mt-sm')
            ui.label('Click "Add Alert Rule" to create one.').classes('text-muted')
        return

    for rule in rules:
        _render_rule_card(rule, alert_service, colors)


def _render_rule_card(rule: dict, alert_service: AlertService, colors: dict):
    """Render a single rule card with toggle and delete actions."""
    rule_type = rule.get('rule_type', 'unknown')
    enabled = rule.get('enabled', 1)

    # Build description
    description_parts = []
    if rule.get('device_type'):
        description_parts.append(f"Device type: {rule['device_type']}")
    if rule.get('metric'):
        threshold = rule.get('threshold_value', 0)
        op = '>' if rule_type == 'threshold_high' else '<'
        description_parts.append(f"{rule['metric']} {op} {threshold}")
    if rule.get('threshold_duration_minutes'):
        description_parts.append(f"Duration: {rule['threshold_duration_minutes']}min")

    with ui.card().classes('w-full p-3'):
        with ui.row().classes('w-full items-center justify-between'):
            # Left: rule info
            with ui.column().classes('flex-1 gap-1'):
                with ui.row().classes('items-center gap-2'):
                    ui.label(rule.get('rule_name', 'Rule')).classes('text-weight-bold')
                    ui.badge(
                        ALERT_TYPE_LABELS.get(rule_type, rule_type),
                        color='primary',
                    )
                    ui.badge(
                        'Enabled' if enabled else 'Disabled',
                        color='green' if enabled else 'grey',
                    ).props('outline' if not enabled else '')

                ui.label(
                    ' | '.join(description_parts) if description_parts else 'All devices'
                ).classes('text-caption text-muted')

            # Right: action buttons
            rule_id = rule.get('rule_id')
            with ui.row().classes('gap-1'):
                ui.button(
                    icon='edit',
                    on_click=lambda r=rule: _open_edit_rule_dialog(r, alert_service, colors),
                ).props('flat dense size=sm').tooltip('Edit Rule')

                ui.button(
                    icon='power_settings_new',
                    on_click=lambda rid=rule_id, en=enabled: _toggle_rule(
                        rid, en, alert_service
                    ),
                ).props(
                    f'flat dense size=sm color={"green" if enabled else "grey"}'
                ).tooltip('Toggle Enable/Disable')

                ui.button(
                    icon='delete',
                    on_click=lambda rid=rule_id: _delete_rule(rid, alert_service),
                ).props('flat dense size=sm color=red').tooltip('Delete Rule')


def _toggle_rule(rule_id: int, current_enabled, alert_service: AlertService):
    """Toggle a rule's enabled state and refresh the list."""
    try:
        alert_service.toggle_rule(rule_id, not current_enabled)
        state = 'enabled' if not current_enabled else 'disabled'
        ui.notify(f'Rule {state}', type='positive')
        alert_rules_list.refresh()
    except Exception as e:
        ui.notify(f'Failed to toggle rule: {e}', type='negative')


def _delete_rule(rule_id: int, alert_service: AlertService):
    """Delete a rule and refresh the list."""
    try:
        alert_service.delete_rule(rule_id)
        ui.notify('Rule deleted', type='warning')
        alert_rules_list.refresh()
    except Exception as e:
        ui.notify(f'Failed to delete rule: {e}', type='negative')


def _open_add_rule_dialog(alert_service: AlertService, colors: dict):
    """Open the dialog for creating a new alert rule."""
    device_opts = _get_device_options()
    room_opts = _get_room_options()

    with ui.dialog() as dialog, ui.card().classes('min-w-[600px] p-4'):
        ui.label('Create Alert Rule').classes('text-h6 q-mb-md')
        ui.separator()

        with ui.column().classes('w-full gap-3 q-mt-md'):
            rule_name = ui.input(
                label='Rule Name',
                placeholder='e.g., High CO2 Alert',
            ).classes('w-full')

            rule_type = ui.select(
                label='Alert Type',
                options={
                    'offline': 'Device Offline',
                    'threshold_high': 'High Threshold',
                    'threshold_low': 'Low Threshold',
                    'degraded': 'Performance Degraded',
                },
                value='offline',
            ).classes('w-full')

            device_type_select = ui.select(
                label='Device Type',
                options={
                    '': 'All Device Types',
                    'spore': 'Spore (Sensors)',
                    'hyphae': 'Hyphae (Controllers)',
                },
                value='',
            ).classes('w-full')

            device_select = ui.select(
                label='Specific Device',
                options=device_opts,
                value='',
            ).classes('w-full')

            room_select = ui.select(
                label='Room',
                options=room_opts,
                value='',
            ).classes('w-full')

            # Threshold settings - visible only for threshold types
            with ui.column().classes('w-full gap-3').bind_visibility_from(
                rule_type, 'value',
                backward=lambda v: v in ('threshold_high', 'threshold_low'),
            ):
                metric_select = ui.select(
                    label='Metric',
                    options={
                        'co2': 'CO2 (ppm)',
                        'temperature': 'Temperature',
                        'humidity': 'Humidity (%)',
                    },
                    value='co2',
                ).classes('w-full')

                threshold_input = ui.number(
                    label='Threshold Value',
                    placeholder='e.g., 2000',
                ).classes('w-full')

            duration_input = ui.number(
                label='Duration (minutes)',
                value=5,
                min=1,
            ).classes('w-full')

            notification_select = ui.select(
                label='Notification Method',
                options={
                    'ui': 'Dashboard Only',
                    'email': 'Email',
                    'webhook': 'Webhook',
                },
                value='ui',
            ).classes('w-full')

            # Notification target - visible for email/webhook
            with ui.column().classes('w-full').bind_visibility_from(
                notification_select, 'value',
                backward=lambda v: v in ('email', 'webhook'),
            ):
                notification_target = ui.input(
                    label='Notification Target',
                    placeholder='Email address or webhook URL',
                ).classes('w-full')

        ui.separator()

        with ui.row().classes('w-full justify-end gap-2 q-mt-sm'):
            ui.button('Cancel', on_click=dialog.close).props('flat')
            ui.button('Create Rule', on_click=lambda: _save_rule(
                dialog, alert_service,
                rule_name.value,
                rule_type.value,
                device_type_select.value,
                device_select.value,
                room_select.value,
                metric_select.value,
                threshold_input.value,
                duration_input.value,
                notification_select.value,
                notification_target.value,
            )).props('color=primary')

    dialog.open()


def _save_rule(dialog, alert_service: AlertService,
               name: str, rule_type: str, device_type: str,
               device_select: str, room_id: str,
               metric: str, threshold, duration,
               notification: str, notification_target: str):
    """Validate and save a new alert rule."""
    if not name or not name.strip():
        ui.notify('Rule name is required', type='negative')
        return

    # Parse device selection
    parsed_device_type = device_type if device_type else None
    device_id = None
    if device_select and ':' in str(device_select):
        dtype, did = str(device_select).split(':', 1)
        parsed_device_type = dtype
        try:
            device_id = int(did)
        except ValueError:
            pass

    try:
        alert_service.create_rule(
            rule_name=name.strip(),
            rule_type=rule_type,
            device_type=parsed_device_type,
            device_id=device_id,
            room_id=int(room_id) if room_id else None,
            metric=metric if rule_type in ('threshold_high', 'threshold_low') else None,
            threshold_value=float(threshold) if threshold else None,
            threshold_duration_minutes=int(duration) if duration else 5,
            notification_method=notification,
            notification_target=notification_target if notification_target else None,
        )
        ui.notify('Rule created successfully', type='positive')
        dialog.close()
        alert_rules_list.refresh()
    except Exception as e:
        ui.notify(f'Failed to create rule: {e}', type='negative')


def _open_edit_rule_dialog(rule: dict, alert_service: AlertService, colors: dict):
    """Open a dialog for editing an existing alert rule."""
    rule_id = rule.get('rule_id')

    with ui.dialog() as dialog, ui.card().classes('min-w-[600px] p-4'):
        ui.label('Edit Alert Rule').classes('text-h6 q-mb-md')
        ui.separator()

        with ui.column().classes('w-full gap-3 q-mt-md'):
            rule_name = ui.input(
                label='Rule Name',
                value=rule.get('rule_name', ''),
            ).classes('w-full')

            current_type = rule.get('rule_type', 'offline')
            rule_type = ui.select(
                label='Alert Type',
                options={
                    'offline': 'Device Offline',
                    'threshold_high': 'High Threshold',
                    'threshold_low': 'Low Threshold',
                    'degraded': 'Performance Degraded',
                },
                value=current_type,
            ).classes('w-full')

            # Threshold settings
            with ui.column().classes('w-full gap-3').bind_visibility_from(
                rule_type, 'value',
                backward=lambda v: v in ('threshold_high', 'threshold_low'),
            ):
                metric_select = ui.select(
                    label='Metric',
                    options={
                        'co2': 'CO2 (ppm)',
                        'temperature': 'Temperature',
                        'humidity': 'Humidity (%)',
                    },
                    value=rule.get('metric', 'co2'),
                ).classes('w-full')

                threshold_input = ui.number(
                    label='Threshold Value',
                    value=rule.get('threshold_value'),
                ).classes('w-full')

            duration_input = ui.number(
                label='Duration (minutes)',
                value=rule.get('threshold_duration_minutes', 5),
                min=1,
            ).classes('w-full')

            notification_select = ui.select(
                label='Notification Method',
                options={
                    'ui': 'Dashboard Only',
                    'email': 'Email',
                    'webhook': 'Webhook',
                },
                value=rule.get('notification_method', 'ui'),
            ).classes('w-full')

            with ui.column().classes('w-full').bind_visibility_from(
                notification_select, 'value',
                backward=lambda v: v in ('email', 'webhook'),
            ):
                notification_target = ui.input(
                    label='Notification Target',
                    value=rule.get('notification_target', ''),
                    placeholder='Email address or webhook URL',
                ).classes('w-full')

        ui.separator()

        with ui.row().classes('w-full justify-end gap-2 q-mt-sm'):
            ui.button('Cancel', on_click=dialog.close).props('flat')

            def _save_edit():
                if not rule_name.value or not rule_name.value.strip():
                    ui.notify('Rule name is required', type='negative')
                    return
                try:
                    kwargs = {
                        'rule_name': rule_name.value.strip(),
                        'rule_type': rule_type.value,
                        'threshold_duration_minutes': int(duration_input.value) if duration_input.value else 5,
                        'notification_method': notification_select.value,
                        'notification_target': notification_target.value if notification_target.value else None,
                    }
                    if rule_type.value in ('threshold_high', 'threshold_low'):
                        kwargs['metric'] = metric_select.value
                        kwargs['threshold_value'] = float(threshold_input.value) if threshold_input.value else None
                    alert_service.update_rule(rule_id, **kwargs)
                    ui.notify('Rule updated', type='positive')
                    dialog.close()
                    alert_rules_list.refresh()
                except Exception as e:
                    ui.notify(f'Failed to update rule: {e}', type='negative')

            ui.button('Save Changes', on_click=_save_edit).props('color=primary')

    dialog.open()
