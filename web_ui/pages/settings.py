"""
Settings page for Mycelium NiceGUI application.

User profile settings only: account info, weather config, preferences,
device PIN, and email notification (SMTP) configuration.

Farm and room management has been moved to the Farm Overview page.
"""

from nicegui import ui, app
from web_ui.layout import page_layout, back_to_dashboard
from web_ui.theme import get_colors
from storage.tables.user_settings import get_user_setting, update_user_setting

US_TIMEZONES = [
    'US/Eastern',
    'US/Central',
    'US/Mountain',
    'US/Pacific',
    'US/Alaska',
    'US/Hawaii',
]


def _readonly_field(label: str, value: str, hint: str = ''):
    """Render a read-only labelled field with an optional hint."""
    ui.label(label).classes('text-weight-bold')
    ui.input(value=value).props('readonly outlined dense').classes('w-full')
    if hint:
        ui.label(hint).classes('text-muted text-caption')


@ui.page('/settings')
def settings_page():
    """Settings page with user profile and notification configuration."""
    user = app.storage.user
    if not user.get('user_id'):
        ui.navigate.to('/login')
        return

    page_layout('Settings')
    back_to_dashboard()
    colors = get_colors()

    user_info = get_user_setting(user['user_id']) or {}
    uid = user['user_id']

    with ui.column().classes('w-full max-w-4xl mx-auto p-4 gap-4'):
        ui.label('Settings').classes('text-h4')
        ui.label('User profile, preferences, and notification configuration').classes('text-muted q-mb-md')

        # ---- Section 1: User Profile ----
        with ui.card().classes('w-full'):
            ui.label('User Profile').classes('text-h5 q-mb-md')

            with ui.column().classes('w-full gap-2'):
                _readonly_field('User ID', str(user_info.get('user_id', '')), 'Internal user identification')
                _readonly_field('Username', user_info.get('user_name', ''), 'Contact administrator to change')
                _readonly_field('User Role', user_info.get('user_role', ''), 'Role for access control')
                _readonly_field('Account Created', str(user_info.get('created_at', '')))
                _readonly_field('Last Updated', str(user_info.get('updated_at', '')))

        # ---- Section 2: Preferences ----
        with ui.card().classes('w-full'):
            ui.label('Preferences').classes('text-h5 q-mb-md')

            # Timezone
            ui.label('Timezone').classes('text-weight-bold')
            tz_select = ui.select(
                options=US_TIMEZONES,
                value=user_info.get('timezone_name') or 'US/Eastern',
            ).classes('w-full')

            def _save_tz(e):
                update_user_setting(uid, timezone_name=tz_select.value)
                ui.notify('Timezone saved', type='positive')
            tz_select.on('update:model-value', _save_tz)

            # Time Format
            ui.label('Time Format').classes('text-weight-bold q-mt-md')
            time_toggle = ui.toggle(
                options={'12': '12-hour (AM/PM)', '24': '24-hour'},
                value=user_info.get('time_format') or '12',
            )

            def _save_time(e):
                update_user_setting(uid, time_format=time_toggle.value)
                ui.notify('Time format saved', type='positive')
            time_toggle.on('update:model-value', _save_time)

            # Temperature Preference
            ui.label('Temperature Unit').classes('text-weight-bold q-mt-md')
            temp_toggle = ui.toggle(
                options={'C': 'Celsius (\u00b0C)', 'F': 'Fahrenheit (\u00b0F)'},
                value=user_info.get('temp_pref') or 'C',
            )

            def _save_temp(e):
                update_user_setting(uid, temp_pref=temp_toggle.value)
                ui.notify('Temperature unit saved', type='positive')
            temp_toggle.on('update:model-value', _save_temp)

        # ---- Section 3: Weather (OWM) ----
        with ui.card().classes('w-full'):
            ui.label('Weather Integration').classes('text-h5 q-mb-md')
            ui.label('OpenWeatherMap provides local weather data for environmental tracking.').classes('text-muted text-caption q-mb-sm')

            ui.label('API Key').classes('text-weight-bold')
            owm_key = ui.input(
                placeholder='Enter OWM API key',
                password=True, password_toggle_button=True,
                value=user_info.get('owm_api_key') or '',
            ).classes('w-full')
            ui.label('Get a free key at openweathermap.org').classes('text-muted text-caption')

            def _save_owm_key(e):
                update_user_setting(uid, owm_api_key=owm_key.value)
                ui.notify('API key saved', type='positive')
            owm_key.on('blur', _save_owm_key)

            ui.label('ZIP Code').classes('text-weight-bold q-mt-md')
            zip_input = ui.input(
                placeholder='e.g., 12345',
                value=user_info.get('owm_zip_code') or '',
            ).props('maxlength=5').classes('w-full')
            ui.label('5-digit ZIP code for weather location').classes('text-muted text-caption')

            def _save_zip(e):
                val = zip_input.value.strip()
                if val and (len(val) != 5 or not val.isdigit()):
                    ui.notify('ZIP must be exactly 5 digits', type='negative')
                    return
                update_user_setting(uid, owm_zip_code=val)
                ui.notify('ZIP code saved', type='positive')
            zip_input.on('blur', _save_zip)

        # ---- Section 4: Device PIN ----
        with ui.card().classes('w-full'):
            ui.label('Device Verification PIN').classes('text-h5 q-mb-md')
            ui.label('PIN used for authenticated operations on Spore and Hyphae devices.').classes('text-muted text-caption q-mb-sm')

            pin_input = ui.input(
                placeholder='Enter 4-8 digit PIN',
                value=user_info.get('reset_pin') or '',
            ).props('maxlength=8').classes('w-full')

            pin_confirm = ui.input(
                placeholder='Confirm PIN',
            ).props('maxlength=8').classes('w-full q-mt-sm')

            def _save_pin(e):
                pin = pin_input.value.strip()
                confirm = pin_confirm.value.strip()
                if not pin:
                    return
                if not pin.isdigit() or not (4 <= len(pin) <= 8):
                    ui.notify('PIN must be 4-8 digits', type='negative')
                    return
                if pin != confirm:
                    ui.notify('PINs do not match', type='negative')
                    return
                update_user_setting(uid, reset_pin=pin)
                ui.notify('Device PIN saved', type='positive')
            pin_confirm.on('blur', _save_pin)

        # ---- Section 5: Email Notifications (SMTP) ----
        with ui.card().classes('w-full'):
            ui.label('Email Notifications').classes('text-h5 q-mb-md')
            ui.label('Configure SMTP to receive email alerts for critical events (device offline, threshold breach).').classes('text-muted text-caption q-mb-xs')
            with ui.row().classes('items-center gap-1 q-mb-sm'):
                ui.icon('warning', size='xs').classes('text-warning')
                ui.label(
                    'Note: Alert emails may initially land in your spam/junk folder. '
                    'Check there after sending a test and mark as "Not Spam" to ensure future delivery.'
                ).classes('text-caption text-warning')

            smtp_server = ui.input(
                label='SMTP Server', placeholder='e.g., smtp.gmail.com',
                value=user_info.get('smtp_server') or '',
            ).classes('w-full')

            smtp_port = ui.input(
                label='SMTP Port', placeholder='587',
                value=str(user_info.get('smtp_port') or '587'),
            ).classes('w-full')

            smtp_from = ui.input(
                label='From Address', placeholder='your@email.com',
                value=user_info.get('smtp_from') or '',
            ).classes('w-full')

            smtp_to = ui.input(
                label='To Address (alerts sent here)', placeholder='alerts@email.com',
                value=user_info.get('smtp_to') or '',
            ).classes('w-full')

            smtp_password = ui.input(
                label='SMTP Password / App Password',
                placeholder='Enter password',
                password=True, password_toggle_button=True,
                value=user_info.get('smtp_password') or '',
            ).classes('w-full')

            smtp_tls = ui.switch('Use STARTTLS', value=bool(user_info.get('smtp_use_tls', True)))

            def _save_smtp():
                try:
                    update_user_setting(
                        uid,
                        smtp_server=smtp_server.value.strip(),
                        smtp_port=smtp_port.value.strip(),
                        smtp_from=smtp_from.value.strip(),
                        smtp_to=smtp_to.value.strip(),
                        smtp_password=smtp_password.value,
                        smtp_use_tls='1' if smtp_tls.value else '0',
                    )
                    ui.notify('Email settings saved', type='positive')
                except Exception as e:
                    ui.notify(f'Error saving: {e}', type='negative')

            ui.button('Save Email Settings', icon='save', on_click=_save_smtp).props('color=primary').classes('q-mt-sm')

            # Test email button
            async def _test_email():
                from api.services.email_service import EmailService
                svc = EmailService()
                ok = svc.send_alert_email(
                    subject='Email Configuration Test',
                    body=(
                        'Your Myco-Monitor Mycelium email notifications are configured correctly.\n\n'
                        'You will receive alerts at this address for critical events including:\n'
                        '  - Device offline notifications\n'
                        '  - Environmental threshold breaches (CO2, temperature, humidity)\n'
                        '  - Relay operation failures\n\n'
                        'If this is your first message, please mark it as "Not Spam" to ensure\n'
                        'future alerts are delivered to your inbox.'
                    ),
                    alert_type='info',
                    user_id=uid,
                )
                if ok:
                    ui.notify('Test email sent successfully', type='positive')
                else:
                    ui.notify('Failed to send test email. Check SMTP settings.', type='negative')

            ui.button('Send Test Email', icon='email', on_click=_test_email).props('outline').classes('q-mt-xs')

        # Auto-save note
        ui.label('Most settings auto-save on change').classes('text-caption text-muted').style(f'color: {colors["primary"]}; font-style: italic')
