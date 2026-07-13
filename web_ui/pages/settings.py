"""
Settings page for Mycelium NiceGUI application.

User profile settings only: account info, weather config, preferences,
device PIN, and email notification (SMTP) configuration.

Farm and room management has been moved to the Farm Overview page.
"""

from nicegui import ui, app, run
from web_ui.layout import page_layout, back_to_dashboard
from web_ui.theme import get_colors
from web_ui.format import fmt_datetime, canonical_tz
from web_ui.auth import is_admin
from web_ui.updates import is_managed_appliance
from api.services.hub_update_service import (
    get_current_version,
    check_for_update,
    apply_update,
)
from storage.tables.hub_update_history import (
    record_update_start,
    record_update_result,
    list_updates,
    reconcile_interrupted,
)
from storage.tables.user_settings import (
    get_user_setting,
    update_user_setting,
    get_all_user_settings,
    create_user_setting,
    delete_user_setting,
    get_user_by_username,
    count_admins,
)

# Canonical IANA names (legacy "US/*" aliases need Debian's optional
# tzdata-legacy package; stored legacy values are mapped via canonical_tz).
US_TIMEZONES = {
    "America/New_York": "Eastern (ET)",
    "America/Chicago": "Central (CT)",
    "America/Denver": "Mountain (MT)",
    "America/Phoenix": "Arizona (no DST)",
    "America/Los_Angeles": "Pacific (PT)",
    "America/Anchorage": "Alaska (AKT)",
    "Pacific/Honolulu": "Hawaii (HST)",
}


def _readonly_field(label: str, value: str, hint: str = ""):
    """Render a read-only labelled field with an optional hint."""
    ui.label(label).classes("text-weight-bold")
    ui.input(value=value).props("readonly outlined dense").classes("w-full")
    if hint:
        ui.label(hint).classes("text-muted text-caption")


@ui.refreshable
def user_admin_section(current_uid: int):
    """Admin-only user management: list accounts, add, delete, and change roles.

    Lockout protection: an admin cannot delete their own account, and the last
    remaining admin can neither be deleted nor demoted (the section is only
    rendered for admins, and every action re-checks these rules server-side).
    """
    with ui.card().classes("w-full"):
        ui.label("User Management").classes("text-h5 q-mb-xs")
        ui.label("Add, remove, and set roles for accounts. Admin only.").classes(
            "text-muted text-caption q-mb-md"
        )

        users = get_all_user_settings()
        admin_count = count_admins()

        with ui.element("div").style(
            "display:grid; grid-template-columns: 2fr 1fr auto; "
            "gap:8px 12px; align-items:center; width:100%;"
        ):
            ui.label("Username").classes("text-weight-bold")
            ui.label("Role").classes("text-weight-bold")
            ui.label("")  # actions column header (spacer)

            for u in users:
                uid_u = u["user_id"]
                is_self = uid_u == current_uid
                was_admin = (u.get("user_role") or "user") == "admin"
                last_admin = was_admin and admin_count <= 1

                ui.label(u.get("user_name", ""))

                role_sel = (
                    ui.select(
                        options=["user", "admin"], value=u.get("user_role") or "user"
                    )
                    .props("dense outlined")
                    .classes("w-32")
                )

                def _change_role(
                    e, target_id=uid_u, sel=role_sel, target_was_admin=was_admin
                ):
                    new_role = sel.value
                    if target_was_admin and new_role != "admin" and count_admins() <= 1:
                        ui.notify("Cannot demote the last admin.", type="negative")
                        sel.value = "admin"
                        return
                    update_user_setting(target_id, user_role=new_role)
                    ui.notify("Role updated.", type="positive")
                    user_admin_section.refresh()

                role_sel.on("update:model-value", _change_role)

                def _delete(
                    target_id=uid_u,
                    name=u.get("user_name", ""),
                    self_row=is_self,
                    target_was_admin=was_admin,
                ):
                    if self_row:
                        ui.notify(
                            "You cannot delete your own account.", type="negative"
                        )
                        return
                    if target_was_admin and count_admins() <= 1:
                        ui.notify("Cannot delete the last admin.", type="negative")
                        return
                    delete_user_setting(target_id)
                    ui.notify(f"Deleted '{name}'.", type="positive")
                    user_admin_section.refresh()

                del_btn = ui.button(
                    icon="delete", on_click=lambda _, h=_delete: h()
                ).props("flat dense color=negative")
                if is_self or last_admin:
                    del_btn.disable()  # UX hint; handler still enforces the rule

        ui.separator().classes("q-my-md")

        # ---- Add user ----
        ui.label("Add User").classes("text-weight-bold q-mb-xs")
        new_name = ui.input("Username").props("dense outlined").classes("w-full")
        new_pw = (
            ui.input("Password", password=True, password_toggle_button=True)
            .props("dense outlined")
            .classes("w-full q-mt-sm")
        )
        new_role = (
            ui.select(options=["user", "admin"], value="user", label="Role")
            .props("dense outlined")
            .classes("w-full q-mt-sm")
        )

        def _add_user():
            name = (new_name.value or "").strip()
            pw = new_pw.value or ""
            if len(name) < 3:
                ui.notify("Username must be at least 3 characters.", type="negative")
                return
            if len(pw) < 6:
                ui.notify("Password must be at least 6 characters.", type="negative")
                return
            if get_user_by_username(name):
                ui.notify("Username already exists.", type="negative")
                return
            create_user_setting(name, pw, user_role=new_role.value)
            ui.notify(f"User '{name}' created.", type="positive")
            user_admin_section.refresh()

        ui.button("Add User", icon="person_add", on_click=_add_user).props(
            "color=primary"
        ).classes("q-mt-sm")


def _hub_update_section(uid):
    """Settings card: show the current version, check for the newest release, and
    (admin only) apply it with device-PIN confirmation. Rendered only on a managed
    appliance — the caller gates on is_managed_appliance()."""
    import hmac

    state = {"info": None}

    # Any 'pending' row still here is from an interrupted run (a real update
    # restarts the service and drops this session); tidy them before rendering.
    reconcile_interrupted()

    with ui.card().classes("w-full"):
        ui.label("Hub Updates").classes("text-h5 q-mb-md")
        ui.label(f"Current version: {get_current_version()}").classes("text-body1")

        @ui.refreshable
        def status_line():
            info = state["info"]
            if not info:
                ui.label(
                    "Press “Check for updates” to see if a newer release is available."
                ).classes("text-muted text-caption")
            elif info.get("error"):
                ui.label(f"Could not check for updates: {info['error']}").classes(
                    "text-negative text-caption"
                )
            elif info.get("update_available"):
                ui.label(f"Update available: {info['latest_version']}").classes(
                    "text-positive"
                )
            else:
                ui.label("This hub is on the latest version.").classes(
                    "text-muted text-caption"
                )

        status_line()

        @ui.refreshable
        def history():
            rows = list_updates(limit=5)
            if not rows:
                return
            ui.separator().classes("q-my-sm")
            ui.label("Recent updates").classes("text-subtitle2")
            colors_by_status = {
                "success": "positive",
                "failed": "negative",
                "rolled_back": "warning",
                "pending": "grey",
            }
            with ui.column().classes("w-full gap-1"):
                for r in rows:
                    badge_color = colors_by_status.get(r.get("status"), "grey")
                    when = fmt_datetime(r.get("started_at"), fallback="")
                    target = r.get("to_ref") or r.get("to_version") or "?"
                    with ui.row().classes("items-center gap-2"):
                        ui.badge(r.get("status", ""), color=badge_color)
                        ui.label(f"{target} · {when}").classes("text-caption")
                        if r.get("error_message"):
                            ui.label(r["error_message"]).classes(
                                "text-caption text-muted"
                            )

        history()

        if not is_admin():
            ui.label("Only an admin can apply updates.").classes(
                "text-caption text-muted q-mt-sm"
            )
            return

        async def _run_update(ref):
            # apply_update returns before the deferred restart fires, so we can
            # both record the result and render the "restarting" banner before the
            # websocket drops.
            info = state["info"] or {}
            update_id = record_update_start(
                get_current_version(), info.get("current_ref"), ref, initiated_by=uid
            )
            progress = ui.notification(
                f"Updating to {ref}… do not power off the hub.",
                spinner=True,
                timeout=None,
            )
            try:
                result = await run.io_bound(apply_update, ref)
            finally:
                progress.dismiss()

            outcome = result.get("result")
            if outcome == "success":
                record_update_result(update_id, "success", to_version=result.get("to"))
                ui.notify(
                    f"Update to {ref} applied. The hub is restarting.", type="positive"
                )
                ui.notification(
                    "Finishing update — the hub is restarting. This page will "
                    "reconnect automatically in about 30 seconds.",
                    spinner=True,
                    timeout=None,
                )
                ui.timer(30.0, lambda: ui.navigate.reload(), once=True)
            elif outcome == "rolled_back":
                record_update_result(
                    update_id, "rolled_back", error_message=result.get("reason")
                )
                ui.notify(
                    f"Update failed and was rolled back (now on "
                    f"{result.get('to', 'the previous version')}). "
                    f"{result.get('reason', '')}",
                    type="warning",
                    multi_line=True,
                    close_button="Dismiss",
                    timeout=0,
                )
            else:
                record_update_result(
                    update_id, "failed", error_message=result.get("error")
                )
                ui.notify(
                    f"Update failed: {result.get('error', 'unknown error')}",
                    type="negative",
                    multi_line=True,
                    close_button="Dismiss",
                    timeout=0,
                )
            history.refresh()

        async def _confirm_and_update(ref):
            with ui.dialog() as dlg, ui.card():
                ui.label(f"Confirm update to {ref}").classes("text-h6")
                ui.label(
                    "Enter your device PIN to apply. The hub will restart."
                ).classes("text-caption text-muted")
                pin_in = ui.input("Device PIN").props("type=password").classes("w-full")
                with ui.row().classes("justify-end w-full q-gutter-sm"):
                    ui.button("Cancel", on_click=lambda: dlg.submit(None)).props("flat")
                    ui.button(
                        "Confirm", on_click=lambda: dlg.submit(pin_in.value)
                    ).props("color=primary")
            entered = await dlg
            if entered is None:
                return
            stored = (get_user_setting(uid) or {}).get("reset_pin") or ""
            if not stored:
                ui.notify(
                    "Set a device PIN first (Device Verification PIN section above).",
                    type="negative",
                )
                return
            if not hmac.compare_digest(str(entered).strip(), str(stored)):
                ui.notify("Incorrect PIN", type="negative")
                return
            await _run_update(ref)

        async def _check():
            progress = ui.notification(
                "Checking for updates…", spinner=True, timeout=None
            )
            try:
                info = await run.io_bound(check_for_update)
            finally:
                progress.dismiss()
            state["info"] = info
            status_line.refresh()
            update_btn.set_enabled(bool(info and info.get("update_available")))

        async def _update():
            info = state["info"] or {}
            ref = info.get("latest_ref")
            if not info.get("update_available") or not ref:
                ui.notify(
                    "No update available. Check for updates first.", type="warning"
                )
                return
            await _confirm_and_update(ref)

        with ui.row().classes("q-mt-md q-gutter-sm"):
            ui.button("Check for updates", icon="refresh", on_click=_check).props(
                "outline"
            )
            update_btn = ui.button(
                "Update now", icon="system_update", on_click=_update
            ).props("color=primary")
            update_btn.set_enabled(False)


@ui.page("/settings")
def settings_page():
    """Settings page with user profile and notification configuration."""
    user = app.storage.user
    if not user.get("user_id"):
        ui.navigate.to("/login")
        return

    page_layout("Settings")
    back_to_dashboard()
    colors = get_colors()

    user_info = get_user_setting(user["user_id"]) or {}
    uid = user["user_id"]

    with ui.column().classes("w-full max-w-4xl mx-auto p-4 gap-4"):
        ui.label("Settings").classes("text-h4")
        ui.label("User profile, preferences, and notification configuration").classes(
            "text-muted q-mb-md"
        )

        # ---- Section 1: User Profile ----
        with ui.card().classes("w-full"):
            ui.label("User Profile").classes("text-h5 q-mb-md")

            with ui.column().classes("w-full gap-2"):
                _readonly_field(
                    "User ID",
                    str(user_info.get("user_id", "")),
                    "Internal user identification",
                )
                _readonly_field(
                    "Username",
                    user_info.get("user_name", ""),
                    "Contact administrator to change",
                )
                _readonly_field(
                    "User Role",
                    user_info.get("user_role", ""),
                    "Role for access control",
                )
                _readonly_field(
                    "Account Created",
                    fmt_datetime(user_info.get("created_at"), fallback=""),
                )
                _readonly_field(
                    "Last Updated",
                    fmt_datetime(user_info.get("updated_at"), fallback=""),
                )

        # ---- Section 2: Preferences ----
        with ui.card().classes("w-full"):
            ui.label("Preferences").classes("text-h5 q-mb-md")

            # Timezone
            ui.label("Timezone").classes("text-weight-bold")
            tz_select = ui.select(
                options=US_TIMEZONES,
                value=canonical_tz(user_info.get("timezone_name")),
            ).classes("w-full")

            def _save_tz(e):
                update_user_setting(uid, timezone_name=tz_select.value)
                # Cache in session storage so the new timezone applies
                # immediately across pages (see web_ui/format.get_timezone_name).
                app.storage.user["timezone_name"] = tz_select.value
                ui.notify("Timezone saved", type="positive")

            tz_select.on("update:model-value", _save_tz)

            # Time Format
            ui.label("Time Format").classes("text-weight-bold q-mt-md")
            time_toggle = ui.toggle(
                options={"12": "12-hour (AM/PM)", "24": "24-hour"},
                value=user_info.get("time_format") or "24",
            )

            def _save_time(e):
                update_user_setting(uid, time_format=time_toggle.value)
                # Cache in session storage so the new format applies immediately
                # across pages (see web_ui/format.get_time_format).
                app.storage.user["time_format"] = time_toggle.value
                ui.notify("Time format saved", type="positive")

            time_toggle.on("update:model-value", _save_time)

            # Temperature Preference
            ui.label("Temperature Unit").classes("text-weight-bold q-mt-md")
            temp_toggle = ui.toggle(
                options={"C": "Celsius (\u00b0C)", "F": "Fahrenheit (\u00b0F)"},
                value=user_info.get("temp_pref") or "C",
            )

            def _save_temp(e):
                update_user_setting(uid, temp_pref=temp_toggle.value)
                ui.notify("Temperature unit saved", type="positive")

            temp_toggle.on("update:model-value", _save_temp)

        # ---- Section 3: Weather (OWM) ----
        with ui.card().classes("w-full"):
            ui.label("Weather Integration").classes("text-h5 q-mb-md")
            ui.label(
                "OpenWeatherMap provides local weather data for environmental tracking."
            ).classes("text-muted text-caption q-mb-sm")

            ui.label("API Key").classes("text-weight-bold")
            owm_key = ui.input(
                placeholder="Enter OWM API key",
                password=True,
                password_toggle_button=True,
                value=user_info.get("owm_api_key") or "",
            ).classes("w-full")
            ui.label("Get a free key at openweathermap.org").classes(
                "text-muted text-caption"
            )

            def _save_owm_key(e):
                update_user_setting(uid, owm_api_key=owm_key.value)
                ui.notify("API key saved", type="positive")

            owm_key.on("blur", _save_owm_key)

            ui.label("ZIP Code").classes("text-weight-bold q-mt-md")
            zip_input = (
                ui.input(
                    placeholder="e.g., 12345",
                    value=user_info.get("owm_zip_code") or "",
                )
                .props("maxlength=5")
                .classes("w-full")
            )
            ui.label("5-digit ZIP code for weather location").classes(
                "text-muted text-caption"
            )

            def _save_zip(e):
                val = zip_input.value.strip()
                if val and (len(val) != 5 or not val.isdigit()):
                    ui.notify("ZIP must be exactly 5 digits", type="negative")
                    return
                update_user_setting(uid, owm_zip_code=val)
                ui.notify("ZIP code saved", type="positive")

            zip_input.on("blur", _save_zip)

        # ---- Section 4: Device PIN ----
        with ui.card().classes("w-full"):
            ui.label("Device Verification PIN").classes("text-h5 q-mb-md")
            ui.label(
                "PIN used for authenticated operations on Spore and Hyphae devices."
            ).classes("text-muted text-caption q-mb-sm")

            pin_input = (
                ui.input(
                    placeholder="Enter 4-8 digit PIN",
                    value=user_info.get("reset_pin") or "",
                )
                .props("maxlength=8")
                .classes("w-full")
            )

            pin_confirm = (
                ui.input(
                    placeholder="Confirm PIN",
                )
                .props("maxlength=8")
                .classes("w-full q-mt-sm")
            )

            def _save_pin(e):
                pin = pin_input.value.strip()
                confirm = pin_confirm.value.strip()
                if not pin:
                    return
                if not pin.isdigit() or not (4 <= len(pin) <= 8):
                    ui.notify("PIN must be 4-8 digits", type="negative")
                    return
                if pin != confirm:
                    ui.notify("PINs do not match", type="negative")
                    return
                update_user_setting(uid, reset_pin=pin)
                ui.notify("Device PIN saved", type="positive")

            pin_confirm.on("blur", _save_pin)

        # ---- Section 5: Email Notifications (SMTP) ----
        with ui.card().classes("w-full"):
            ui.label("Email Notifications").classes("text-h5 q-mb-md")
            ui.label(
                "Configure SMTP to receive email alerts for critical events (device offline, threshold breach)."
            ).classes("text-muted text-caption q-mb-xs")
            with ui.row().classes("items-center gap-1 q-mb-sm"):
                ui.icon("warning", size="xs").classes("text-warning")
                ui.label(
                    "Note: Alert emails may initially land in your spam/junk folder. "
                    'Check there after sending a test and mark as "Not Spam" to ensure future delivery.'
                ).classes("text-caption text-warning")

            with ui.expansion("Which settings do I use?", icon="help_outline").classes(
                "w-full q-mb-sm"
            ):
                ui.markdown(
                    "**Direct send (authenticated)** — works for any Gmail / Workspace "
                    "account:\n"
                    "- SMTP Server: `smtp.gmail.com` • Port: `587` • STARTTLS on\n"
                    "- From Address: your full Gmail / Workspace address\n"
                    "- Password: a Google **App Password** (not your login password)\n\n"
                    "**Workspace SMTP relay** — send as your domain, often without a "
                    "password:\n"
                    "- SMTP Server: `smtp-relay.gmail.com` • Port: `587` • STARTTLS on\n"
                    "- From Address: an address on your domain\n"
                    "- Password: leave **blank** if your relay allows by IP/domain "
                    "(register this server's public IP in Admin → Apps → Gmail → "
                    "Routing → SMTP relay service); set an App Password if the relay "
                    "requires SMTP AUTH."
                ).classes("text-caption")

            smtp_server = ui.input(
                label="SMTP Server",
                placeholder="smtp.gmail.com or smtp-relay.gmail.com",
                value=user_info.get("smtp_server") or "",
            ).classes("w-full")

            smtp_port = ui.input(
                label="SMTP Port",
                placeholder="587",
                value=str(user_info.get("smtp_port") or "587"),
            ).classes("w-full")

            smtp_from = ui.input(
                label="From Address",
                placeholder="your@email.com",
                value=user_info.get("smtp_from") or "",
            ).classes("w-full")

            smtp_to = ui.input(
                label="To Address (alerts sent here)",
                placeholder="alerts@email.com",
                value=user_info.get("smtp_to") or "",
            ).classes("w-full")

            smtp_password = ui.input(
                label="App Password (blank for IP-allowlisted relay)",
                placeholder="App Password, or blank for relay",
                password=True,
                password_toggle_button=True,
                value=user_info.get("smtp_password") or "",
            ).classes("w-full")

            smtp_tls = ui.switch(
                "Use STARTTLS", value=bool(user_info.get("smtp_use_tls", True))
            )

            def _save_smtp():
                try:
                    update_user_setting(
                        uid,
                        smtp_server=smtp_server.value.strip(),
                        smtp_port=smtp_port.value.strip(),
                        smtp_from=smtp_from.value.strip(),
                        smtp_to=smtp_to.value.strip(),
                        smtp_password=smtp_password.value,
                        smtp_use_tls="1" if smtp_tls.value else "0",
                    )
                    ui.notify("Email settings saved", type="positive")
                except Exception as e:
                    ui.notify(f"Error saving: {e}", type="negative")

            ui.button("Save Email Settings", icon="save", on_click=_save_smtp).props(
                "color=primary"
            ).classes("q-mt-sm")

            # Test email button
            async def _test_email():
                from api.services.email_service import EmailService

                svc = EmailService()
                # send_alert_email is blocking (smtplib + up to a 10s connect
                # timeout). Run it off the event loop so a slow or failed send
                # doesn't freeze the UI / drop the websocket. Show a spinner
                # notification and dismiss it in finally so it never gets stuck.
                progress = ui.notification(
                    "Sending test email…", spinner=True, timeout=None
                )
                try:
                    ok = await run.io_bound(
                        svc.send_alert_email,
                        subject="Email Configuration Test",
                        body=(
                            "Your Myco-Monitor Mycelium email notifications are configured correctly.\n\n"
                            "You will receive alerts at this address for critical events including:\n"
                            "  - Device offline notifications\n"
                            "  - Environmental threshold breaches (CO2, temperature, humidity)\n"
                            "  - Relay operation failures\n\n"
                            'If this is your first message, please mark it as "Not Spam" to ensure\n'
                            "future alerts are delivered to your inbox."
                        ),
                        alert_type="info",
                        user_id=uid,
                    )
                finally:
                    progress.dismiss()
                if ok:
                    ui.notify("Test email sent successfully", type="positive")
                else:
                    detail = svc.last_error or "Check SMTP settings."
                    ui.notify(
                        f"Failed to send test email:\n{detail}",
                        type="negative",
                        multi_line=True,
                        close_button="Dismiss",
                        timeout=0,
                    )

            ui.button("Send Test Email", icon="email", on_click=_test_email).props(
                "outline"
            ).classes("q-mt-xs")

        # ---- Section: Hub Updates (managed appliance only) ----
        if is_managed_appliance():
            _hub_update_section(uid)

        # ---- Section 6: User Management (admin only) ----
        if is_admin():
            user_admin_section(uid)

        # Auto-save note
        ui.label("Most settings auto-save on change").classes(
            "text-caption text-muted"
        ).style(f"color: {colors['primary']}; font-style: italic")
