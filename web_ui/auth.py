"""
Authentication pages for Mycelium NiceGUI application.

Provides login and signup page layouts.
"""

from nicegui import ui, app
from web_ui.theme import apply_theme, get_colors, COLOR_THEMES, get_theme, set_theme_color, toggle_theme_mode


def _auth_header():
    """Minimal header for auth pages with theme controls on the right."""
    theme = get_theme()
    with ui.header().classes('items-center justify-between px-4'):
        # Left side: title
        ui.label('Mycelium').classes('text-h6 text-white')

        # Right side: collapsible color picker + dark/light toggle
        with ui.row().classes('items-center gap-1'):
            with ui.button(icon='palette').props('flat color=white'):
                with ui.menu().classes('p-2'):
                    with ui.row().classes('items-center gap-1'):
                        for name, theme_colors in COLOR_THEMES.items():
                            active_class = 'active' if name == theme['color'] else ''
                            border = '3px solid white' if name == theme['color'] else '2px solid #999'
                            ui.element('div').classes(f'mycelium-color-circle {active_class}').style(
                                f'background-color: {theme_colors["primary"]}; border: {border};'
                            ).on('click', _make_color_handler(name))

            mode_icon = 'dark_mode' if theme['mode'] == 'light' else 'light_mode'
            ui.button(icon=mode_icon, on_click=_handle_toggle).props('flat color=white')


def _make_color_handler(color_name: str):
    async def handler():
        set_theme_color(color_name)
        ui.navigate.reload()
    return handler


async def _handle_toggle():
    toggle_theme_mode()
    ui.navigate.reload()


@ui.page('/login')
def login_page():
    """Login page."""
    apply_theme()
    colors = get_colors()
    _auth_header()

    with ui.column().classes('absolute-center items-center'):
        with ui.card().classes('w-96 p-6'):
            ui.label('Login to Mycelium').classes('text-h5 text-center full-width q-mb-md')

            error_label = ui.label('').classes('text-negative q-mb-sm')
            error_label.set_visibility(False)

            username = ui.input('Username', placeholder='Enter your username').classes('full-width q-mb-sm')
            password = ui.input('Password', placeholder='Enter your password', password=True,
                                password_toggle_button=True).classes('full-width q-mb-md')

            async def handle_login():
                if not username.value or not password.value:
                    error_label.text = 'Please enter both username and password.'
                    error_label.set_visibility(True)
                    return

                from storage.tables.user_settings import authenticate_user
                user_data = authenticate_user(username.value, password.value)

                if user_data:
                    app.storage.user['user_id'] = user_data['user_id']
                    app.storage.user['username'] = user_data['user_name']
                    ui.navigate.to('/main')
                else:
                    error_label.text = 'Invalid username or password.'
                    error_label.set_visibility(True)

            ui.button('Login', on_click=handle_login).props('color=primary').classes('full-width q-mb-md')

            # Allow Enter key to submit
            password.on('keydown.enter', handle_login)

            with ui.row().classes('full-width justify-center'):
                ui.label("Don't have an account?").classes('q-mr-xs')
                ui.link('Sign Up', '/signup').style(f'color: {colors["primary"]}')


@ui.page('/signup')
def signup_page():
    """Signup page."""
    apply_theme()
    colors = get_colors()
    _auth_header()

    with ui.column().classes('absolute-center items-center'):
        with ui.card().classes('w-96 p-6'):
            ui.label('Sign Up for Mycelium').classes('text-h5 text-center full-width q-mb-md')

            error_label = ui.label('').classes('text-negative q-mb-sm')
            error_label.set_visibility(False)

            username = ui.input('Username', placeholder='Choose a username').classes('full-width q-mb-sm')
            password = ui.input('Password', placeholder='Create a password', password=True,
                                password_toggle_button=True).classes('full-width q-mb-sm')
            confirm = ui.input('Confirm Password', placeholder='Confirm your password', password=True,
                               password_toggle_button=True).classes('full-width q-mb-md')

            async def handle_signup():
                if not username.value or not password.value or not confirm.value:
                    error_label.text = 'Please fill in all fields.'
                    error_label.set_visibility(True)
                    return

                if len(username.value.strip()) < 3:
                    error_label.text = 'Username must be at least 3 characters.'
                    error_label.set_visibility(True)
                    return

                if len(password.value) < 6:
                    error_label.text = 'Password must be at least 6 characters.'
                    error_label.set_visibility(True)
                    return

                if password.value != confirm.value:
                    error_label.text = 'Passwords do not match.'
                    error_label.set_visibility(True)
                    return

                from storage.tables.user_settings import (
                    create_user_setting, get_user_by_username, count_users
                )

                existing = get_user_by_username(username.value.strip())
                if existing:
                    error_label.text = 'Username already exists.'
                    error_label.set_visibility(True)
                    return

                user_role = 'admin' if count_users() == 0 else 'user'
                create_user_setting(username.value.strip(), password.value, user_role=user_role)
                ui.navigate.to('/login')

            ui.button('Sign Up', on_click=handle_signup).props('color=primary').classes('full-width q-mb-md')

            confirm.on('keydown.enter', handle_signup)

            with ui.row().classes('full-width justify-center'):
                ui.label('Already have an account?').classes('q-mr-xs')
                ui.link('Login', '/login').style(f'color: {colors["primary"]}')


@ui.page('/logout')
def logout_page():
    """Logout page."""
    apply_theme()
    _auth_header()

    with ui.column().classes('absolute-center items-center'):
        with ui.card().classes('w-96 p-6'):
            ui.label('Logout Confirmation').classes('text-h5 text-center full-width q-mb-md')
            ui.label('Are you sure you want to logout?').classes('text-center full-width q-mb-lg')

            with ui.row().classes('full-width justify-center gap-4'):
                async def confirm_logout():
                    app.storage.user.clear()
                    ui.navigate.to('/login')

                ui.button('Yes, Logout', on_click=confirm_logout).props('color=negative')
                ui.button('Cancel', on_click=lambda: ui.navigate.to('/main')).props('color=primary outline')
