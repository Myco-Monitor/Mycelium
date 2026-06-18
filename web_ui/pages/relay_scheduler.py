"""
Relay Visual Scheduler page for Mycelium NiceGUI application.

Timeline/calendar view for relay schedules across all Hyphae devices.
Shows a 24-hour Gantt-style view of relay group on/off periods.
"""

import plotly.graph_objects as go

from nicegui import ui, app
from web_ui.layout import page_layout, back_to_dashboard
from web_ui.theme import get_colors


@ui.page('/relay-scheduler')
def relay_scheduler_page():
    """Relay visual scheduler with Gantt-style timeline."""
    user = app.storage.user
    if not user.get('user_id'):
        ui.navigate.to('/login')
        return

    page_layout('Relay Scheduler')
    back_to_dashboard()
    colors = get_colors()

    with ui.column().classes('w-full max-w-6xl mx-auto p-4 gap-4'):
        ui.label('Relay Schedule Overview').classes('text-h4')
        ui.label('24-hour timeline of relay group schedules across all Hyphae devices').classes('text-muted')

        # Device selector
        from storage.tables.device_hyphae import get_all_device_hyphae
        hyphae_devices = get_all_device_hyphae()

        if not hyphae_devices:
            with ui.card().classes('w-full p-6 text-center'):
                ui.icon('info', size='md').classes('text-muted')
                ui.label('No Hyphae devices registered. Add devices in the Devices page.').classes('text-muted')
            return

        device_options = {d['device_id']: d.get('device_name', f"Hyphae-{d['device_id']}") for d in hyphae_devices}
        selected_device = ui.select(
            options=device_options,
            label='Select Hyphae Device',
            value=hyphae_devices[0]['device_id'],
        ).classes('w-64')

        # Schedule timeline (refreshable)
        @ui.refreshable
        def schedule_timeline():
            device_id = selected_device.value
            if not device_id:
                ui.label('Select a device to view its schedule').classes('text-muted')
                return

            from storage.tables.schedule_settings import get_device_schedule_settings
            schedules = get_device_schedule_settings(int(device_id))

            if not schedules:
                with ui.card().classes('w-full p-6 text-center'):
                    ui.label('No schedule settings configured for this device.').classes('text-muted')
                    ui.label('Configure schedules in the Devices page.').classes('text-caption text-muted')
                return

            # Build Gantt chart
            fig = _build_schedule_gantt(schedules, device_options.get(device_id, ''), colors)
            ui.plotly(fig).classes('w-full')

            # Schedule details table
            with ui.card().classes('w-full p-4 q-mt-md'):
                ui.label('Schedule Details').classes('text-h6 q-mb-sm')
                columns = [
                    {'name': 'group', 'label': 'Group', 'field': 'group_num', 'align': 'center'},
                    {'name': 'on', 'label': 'On Time', 'field': 'on_time', 'align': 'center'},
                    {'name': 'off', 'label': 'Off Time', 'field': 'off_time', 'align': 'center'},
                    {'name': 'duration', 'label': 'Duration', 'field': 'duration', 'align': 'center'},
                ]
                rows = []
                for s in schedules:
                    on_time = s.get('on_time', '00:00') or '00:00'
                    off_time = s.get('off_time', '00:00') or '00:00'
                    duration = _calc_duration(on_time, off_time)
                    rows.append({
                        'group_num': f"Group {s.get('group_num', '?')}",
                        'on_time': on_time,
                        'off_time': off_time,
                        'duration': duration,
                    })
                ui.table(columns=columns, rows=rows, row_key='group_num').classes('w-full')

        selected_device.on('update:model-value', lambda: schedule_timeline.refresh())
        schedule_timeline()


def _build_schedule_gantt(schedules: list, device_name: str, colors: dict) -> go.Figure:
    """Build a Gantt-style horizontal bar chart for relay schedules."""
    fig = go.Figure()

    group_colors = [
        '#a500a5', '#d32f2f', '#f57c00', '#fbc02d',
        '#388e3c', '#1976d2', '#303f9f',
    ]

    for schedule in schedules:
        group_num = schedule.get('group_num', 0)
        on_time = schedule.get('on_time', '00:00') or '00:00'
        off_time = schedule.get('off_time', '00:00') or '00:00'

        on_hour, on_min = _parse_time(on_time)
        off_hour, off_min = _parse_time(off_time)

        on_decimal = on_hour + on_min / 60
        off_decimal = off_hour + off_min / 60

        color = group_colors[group_num % len(group_colors)]
        label = f"Group {group_num}"

        if off_decimal > on_decimal:
            # Normal case: on before off
            fig.add_trace(go.Bar(
                y=[label],
                x=[off_decimal - on_decimal],
                base=[on_decimal],
                orientation='h',
                name=label,
                marker_color=color,
                text=f"{on_time} - {off_time}",
                textposition='inside',
                hoverinfo='text',
            ))
        elif off_decimal < on_decimal:
            # Wraps midnight: two bars
            fig.add_trace(go.Bar(
                y=[label],
                x=[24 - on_decimal],
                base=[on_decimal],
                orientation='h',
                name=f"{label} (evening)",
                marker_color=color,
                text=f"{on_time} - 24:00",
                textposition='inside',
                showlegend=False,
                hoverinfo='text',
            ))
            fig.add_trace(go.Bar(
                y=[label],
                x=[off_decimal],
                base=[0],
                orientation='h',
                name=f"{label} (morning)",
                marker_color=color,
                text=f"00:00 - {off_time}",
                textposition='inside',
                showlegend=False,
                hoverinfo='text',
            ))

    fig.update_layout(
        title=f"Relay Schedule — {device_name}",
        xaxis=dict(
            title='Hour of Day',
            range=[0, 24],
            tickmode='linear',
            dtick=2,
            ticktext=[f"{h:02d}:00" for h in range(0, 25, 2)],
            tickvals=list(range(0, 25, 2)),
        ),
        yaxis=dict(title='', autorange='reversed'),
        barmode='overlay',
        showlegend=False,
        height=max(200, len(schedules) * 60 + 100),
        margin=dict(l=80, r=20, t=40, b=40),
    )

    return fig


def _parse_time(time_str: str):
    """Parse HH:MM string to (hour, minute) tuple."""
    try:
        parts = time_str.split(':')
        return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return 0, 0


def _calc_duration(on_time: str, off_time: str) -> str:
    """Calculate duration between on and off time as a readable string."""
    on_h, on_m = _parse_time(on_time)
    off_h, off_m = _parse_time(off_time)

    on_minutes = on_h * 60 + on_m
    off_minutes = off_h * 60 + off_m

    if off_minutes >= on_minutes:
        total = off_minutes - on_minutes
    else:
        total = (24 * 60 - on_minutes) + off_minutes

    hours = total // 60
    mins = total % 60
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"
