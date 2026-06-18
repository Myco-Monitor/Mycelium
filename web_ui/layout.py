"""
Shared layout components for Mycelium NiceGUI application.

Provides the page wrapper with header, navigation drawer, and theme controls.
"""

from nicegui import ui, app
from web_ui.theme import (
    COLOR_THEMES, get_theme, set_theme_color, toggle_theme_mode, apply_theme, get_colors
)


def page_layout(title: str = 'Mycelium'):
    """
    Create the shared page layout with header, nav drawer, and theme controls.

    Usage:
        @ui.page('/dashboard')
        def dashboard_page():
            page_layout('Dashboard')
            # ... page content here ...
    """
    apply_theme()
    theme = get_theme()
    colors = get_colors()

    # Navigation drawer (created before header so toggle lambda can capture it)
    drawer = ui.left_drawer(value=False).classes('p-4')
    with drawer:
        ui.label('Navigation').classes('text-h6 q-mb-md')
        _nav_item('Dashboard', '/main', 'dashboard')
        _nav_item('Devices', '/devices', 'sensors')
        _nav_item('Farm Overview', '/farms', 'agriculture')
        _nav_item('Alerts', '/alerts', 'notifications')
        _nav_item('Analytics', '/analytics', 'analytics')
        _nav_item('Business', '/business', 'business')
        _nav_item('Fleet', '/fleet', 'system_update')
        _nav_item('Health', '/health', 'monitor_heart')
        _nav_item('Schedules', '/relay-scheduler', 'calendar_today')
        _nav_item('Settings', '/settings', 'settings')

        ui.separator().classes('q-my-md')

        _nav_item('Logout', '/logout', 'logout')

    # Header
    with ui.header().classes('items-center justify-between px-4'):
        # Left side: menu + title
        with ui.row().classes('items-center gap-2'):
            ui.button(icon='menu', on_click=lambda: drawer.toggle()).props('flat color=white')
            ui.label('Mycelium').classes('text-h6 text-white')

        # Right side: collapsible color picker + dark/light toggle
        with ui.row().classes('items-center gap-1'):
            # Color theme popup (expand/collapse on button press)
            with ui.button(icon='palette').props('flat color=white'):
                with ui.menu().classes('p-2'):
                    with ui.row().classes('items-center gap-1'):
                        for name, theme_colors in COLOR_THEMES.items():
                            active_class = 'active' if name == theme['color'] else ''
                            border = '3px solid white' if name == theme['color'] else '2px solid #999'
                            ui.element('div').classes(f'mycelium-color-circle {active_class}').style(
                                f'background-color: {theme_colors["primary"]}; border: {border};'
                            ).on('click', _make_color_handler(name))

            # Dark/light toggle
            mode_icon = 'dark_mode' if theme['mode'] == 'light' else 'light_mode'
            ui.button(icon=mode_icon, on_click=_handle_toggle_mode).props('flat color=white')


def _nav_item(label: str, href: str, icon: str):
    """Create a navigation menu item."""
    with ui.element('a').classes('no-underline'):
        ui.button(label, icon=icon, on_click=lambda: ui.navigate.to(href)).props(
            'flat align=left'
        ).classes('full-width q-mb-xs')


def _make_color_handler(color_name: str):
    """Create a click handler for a color theme circle."""
    async def handler():
        set_theme_color(color_name)
        ui.navigate.reload()
    return handler


async def _handle_toggle_mode():
    """Handle light/dark mode toggle."""
    toggle_theme_mode()
    ui.navigate.reload()


def back_to_dashboard():
    """Render a back-to-dashboard button. Call at the top of page content."""
    ui.button('Dashboard', icon='arrow_back',
              on_click=lambda: ui.navigate.to('/main')).props('flat color=primary').classes('q-mb-sm')
