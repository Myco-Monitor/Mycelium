"""
Fleet Management page for Mycelium NiceGUI application.

Provides firmware inventory management, OTA upload orchestration,
device firmware version tracking, and OTA history.
"""

import hashlib
from pathlib import Path

from nicegui import ui, app
from web_ui.layout import page_layout, back_to_dashboard
from web_ui.theme import get_colors

FIRMWARE_DIR = Path(__file__).parent.parent.parent / "data" / "firmware"
FIRMWARE_DIR.mkdir(parents=True, exist_ok=True)


@ui.page("/fleet")
@ui.page("/fleet-management")
def fleet_management_page():
    """Fleet management page with firmware inventory, OTA upload, and history."""
    user = app.storage.user
    if not user.get("user_id"):
        ui.navigate.to("/login")
        return

    page_layout("Fleet Management")
    back_to_dashboard()
    colors = get_colors()

    with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
        ui.label("Fleet Management").classes("text-h4")
        ui.label(
            "Firmware inventory, OTA updates, and device version tracking"
        ).classes("text-muted")

        # Tabs
        with ui.tabs().classes("w-full") as tabs:
            firmware_tab = ui.tab("Firmware Inventory", icon="inventory")
            batch_tab = ui.tab("Batch OTA", icon="system_update")
            versions_tab = ui.tab("Device Versions", icon="devices")
            ota_tab = ui.tab("OTA History", icon="history")

        with ui.tab_panels(tabs, value=firmware_tab).classes("w-full"):
            # Firmware Inventory Tab
            with ui.tab_panel(firmware_tab):
                _firmware_inventory_section(colors)

            # Batch OTA Tab
            with ui.tab_panel(batch_tab):
                _batch_ota_section(colors)

            # Device Versions Tab
            with ui.tab_panel(versions_tab):
                _device_versions_section(colors)

            # OTA History Tab
            with ui.tab_panel(ota_tab):
                _ota_history_section(colors)


@ui.refreshable
def _firmware_inventory_section(colors: dict):
    """Firmware inventory with upload and listing."""
    from storage.tables.firmware_versions import get_all_firmware_versions

    # Upload section
    with ui.card().classes("w-full p-4 q-mb-md"):
        ui.label("Upload Firmware").classes("text-h6 q-mb-sm")

        with ui.row().classes("w-full items-end gap-4"):
            device_type = ui.select(
                options=["spore", "hyphae"],
                label="Device Type",
                value="spore",
            ).classes("w-32")
            version_input = ui.input(
                label="Version", placeholder="e.g., 1.2.0"
            ).classes("w-32")
            notes_input = ui.input(
                label="Release Notes", placeholder="Optional"
            ).classes("flex-1")

        upload_ref = {"file": None}

        async def handle_upload(e):
            upload_ref["file"] = e
            ui.notify(f"File selected: {e.name}", type="info")

        ui.upload(
            label="Select firmware .bin file",
            on_upload=handle_upload,
            auto_upload=True,
        ).props("accept=.bin").classes("w-full q-mt-sm")

        async def save_firmware():
            if not upload_ref["file"] or not version_input.value:
                ui.notify("Select a file and enter a version", type="warning")
                return

            e = upload_ref["file"]
            content = e.content.read()
            file_hash = hashlib.sha256(content).hexdigest()
            filename = f"{device_type.value}_{version_input.value}.bin"
            file_path = FIRMWARE_DIR / filename

            with open(file_path, "wb") as f:
                f.write(content)

            from storage.tables.firmware_versions import create_firmware_version

            create_firmware_version(
                device_type=device_type.value,
                version=version_input.value,
                file_path=str(file_path),
                file_hash=file_hash,
                file_size=len(content),
                release_notes=notes_input.value or None,
            )
            ui.notify(f"Firmware {version_input.value} uploaded", type="positive")
            version_input.value = ""
            notes_input.value = ""
            upload_ref["file"] = None
            _firmware_inventory_section.refresh()

        ui.button("Save Firmware", icon="save", on_click=save_firmware).props(
            "color=primary"
        ).classes("q-mt-sm")

    # Firmware list
    firmware_list = get_all_firmware_versions()
    if not firmware_list:
        ui.label("No firmware uploaded yet").classes("text-muted text-center q-pa-lg")
        return

    columns = [
        {"name": "type", "label": "Type", "field": "device_type", "align": "left"},
        {"name": "version", "label": "Version", "field": "version", "align": "left"},
        {"name": "size", "label": "Size", "field": "size_display", "align": "left"},
        {"name": "hash", "label": "SHA256", "field": "hash_short", "align": "left"},
        {"name": "notes", "label": "Notes", "field": "release_notes", "align": "left"},
        {
            "name": "uploaded",
            "label": "Uploaded",
            "field": "uploaded_at",
            "align": "left",
        },
    ]
    rows = []
    for fw in firmware_list:
        size_kb = (fw.get("file_size", 0) or 0) / 1024
        rows.append(
            {
                **fw,
                "size_display": f"{size_kb:.0f} KB",
                "hash_short": (fw.get("file_hash", "") or "")[:12] + "...",
            }
        )

    ui.table(columns=columns, rows=rows, row_key="version_id").classes("w-full")


@ui.refreshable
def _batch_ota_section(colors: dict):
    """Batch OTA: select firmware, select devices, push to all."""
    from storage.tables.device_spore import get_all_device_spore
    from storage.tables.device_hyphae import get_all_device_hyphae
    from storage.tables.firmware_versions import get_all_firmware_versions
    from api.services.ota_service import OtaService

    user_id = app.storage.user.get("user_id")
    ota_svc = OtaService()

    # Step 1: Select device type and firmware
    with ui.card().classes("w-full p-4 q-mb-md"):
        ui.label("Step 1: Select Firmware").classes("text-h6 q-mb-sm")

        with ui.row().classes("w-full items-end gap-4"):
            dtype = ui.select(
                options=["spore", "hyphae"],
                label="Device Type",
                value="spore",
            ).classes("w-40")

            # Build firmware options dynamically
            all_fw = get_all_firmware_versions()
            fw_by_type = {}
            for fw in all_fw:
                fw_by_type.setdefault(fw["device_type"], []).append(fw)

            def _fw_options():
                fws = fw_by_type.get(dtype.value, [])
                return {
                    fw[
                        "version_id"
                    ]: f"v{fw['version']} ({fw.get('file_size', 0) // 1024}KB)"
                    for fw in fws
                }

            fw_select = ui.select(
                options=_fw_options(),
                label="Firmware Version",
            ).classes("flex-1")

            def _on_type_change(e):
                fw_select.options = _fw_options()
                fw_select.value = None

            dtype.on("update:model-value", _on_type_change)

    # Step 2: Select devices
    with ui.card().classes("w-full p-4 q-mb-md"):
        ui.label("Step 2: Select Devices").classes("text-h6 q-mb-sm")
        ui.label(
            "Devices with PIN status. Only devices with a PIN (device or default) can receive OTA."
        ).classes("text-caption text-muted q-mb-md")

        device_table_container = ui.column().classes("w-full")

        @ui.refreshable
        def device_checklist():
            dt = dtype.value
            if dt == "spore":
                devices = get_all_device_spore()
            else:
                devices = get_all_device_hyphae()

            if not devices:
                ui.label("No devices found").classes("text-muted")
                return

            columns = [
                {"name": "name", "label": "Device", "field": "name", "align": "left"},
                {"name": "ip", "label": "IP", "field": "ip", "align": "left"},
                {
                    "name": "firmware",
                    "label": "Current FW",
                    "field": "firmware",
                    "align": "left",
                },
                {
                    "name": "pin_status",
                    "label": "PIN",
                    "field": "pin_status",
                    "align": "center",
                },
                {
                    "name": "online",
                    "label": "Online",
                    "field": "online",
                    "align": "center",
                },
            ]

            rows = []
            for d in devices:
                did = d["device_id"]
                ps = ota_svc.get_pin_status(did, dt, user_id)
                ps_label = {
                    "device": "Device PIN",
                    "default": "Default",
                    "missing": "MISSING",
                }[ps]
                rows.append(
                    {
                        "device_id": did,
                        "name": d.get("device_name", ""),
                        "ip": d.get("hostname", ""),
                        "firmware": d.get("firmware_version", "Unknown"),
                        "pin_status": ps_label,
                        "online": "Yes" if d.get("is_online") else "No",
                    }
                )

            with device_table_container:
                device_table_container.clear()
                table = ui.table(
                    columns=columns,
                    rows=rows,
                    row_key="device_id",
                    selection="multiple",
                ).classes("w-full")

                # Color code PIN status
                table.add_slot(
                    "body-cell-pin_status",
                    r"""
                    <q-td :props="props">
                        <q-badge :color="props.row.pin_status === 'MISSING' ? 'red' : props.row.pin_status === 'Device PIN' ? 'green' : 'blue'">
                            {{ props.row.pin_status }}
                        </q-badge>
                    </q-td>
                """,
                )

                table.add_slot(
                    "body-cell-online",
                    r"""
                    <q-td :props="props">
                        <q-badge :color="props.row.online === 'Yes' ? 'green' : 'red'">
                            {{ props.row.online }}
                        </q-badge>
                    </q-td>
                """,
                )

                # Store table ref for batch OTA
                _batch_state["table"] = table
                _batch_state["device_type"] = dt

        device_checklist()
        dtype.on("update:model-value", lambda e: device_checklist.refresh())

    # Step 3: Execute batch OTA
    with ui.card().classes("w-full p-4"):
        ui.label("Step 3: Push Firmware").classes("text-h6 q-mb-sm")

        batch_log = ui.column().classes("w-full")
        batch_progress = ui.linear_progress(value=0, show_value=False).classes(
            "w-full q-mb-sm"
        )
        batch_progress.set_visibility(False)

        async def run_batch_ota():
            table = _batch_state.get("table")
            if not table or not table.selected:
                ui.notify("Select at least one device", type="warning")
                return
            if not fw_select.value:
                ui.notify("Select a firmware version", type="warning")
                return

            fw = next((f for f in all_fw if f["version_id"] == fw_select.value), None)
            if not fw:
                ui.notify("Firmware not found", type="negative")
                return

            selected = table.selected
            dt = _batch_state["device_type"]
            total = len(selected)

            batch_progress.set_visibility(True)
            batch_log.clear()

            with batch_log:
                ui.label(
                    f"Updating {total} device(s) with v{fw['version']}..."
                ).classes("text-weight-bold")

            for i, row in enumerate(selected):
                did = row["device_id"]
                dname = row.get("name", f"#{did}")
                pin = ota_svc.resolve_pin(did, dt, user_id)

                batch_progress.value = i / total

                if not pin:
                    with batch_log:
                        with ui.row().classes("items-center gap-2"):
                            ui.badge("SKIP", color="orange")
                            ui.label(f"{dname} — no PIN available").classes(
                                "text-caption"
                            )
                    continue

                with batch_log:
                    ui.label(f"{dname} — uploading...").classes("text-caption")

                result = await ota_svc.upload_firmware(
                    did,
                    dt,
                    fw["file_path"],
                    user_id=user_id,
                )

                with batch_log:
                    if result.get("success"):
                        with ui.row().classes("items-center gap-2"):
                            ui.badge("OK", color="green")
                            ui.label(f"{dname} — success").classes("text-caption")
                    else:
                        with ui.row().classes("items-center gap-2"):
                            ui.badge("FAIL", color="red")
                            ui.label(f"{dname} — {result.get('error', '?')}").classes(
                                "text-caption"
                            )

            batch_progress.value = 1.0
            with batch_log:
                ui.label("Batch OTA complete.").classes("text-weight-bold q-mt-sm")
            _ota_history_section.refresh()

        ui.button(
            "Start Batch OTA", icon="rocket_launch", on_click=run_batch_ota
        ).props("color=primary")


# Shared state for batch OTA table reference
_batch_state: dict = {}


@ui.refreshable
def _device_versions_section(colors: dict):
    """Show current firmware version per device with PIN status."""
    from storage.tables.device_spore import get_all_device_spore
    from storage.tables.device_hyphae import get_all_device_hyphae
    from api.services.ota_service import OtaService

    user_id = app.storage.user.get("user_id")
    ota_svc = OtaService()

    spores = get_all_device_spore()
    hyphae = get_all_device_hyphae()

    columns = [
        {"name": "type", "label": "Type", "field": "type", "align": "left"},
        {"name": "name", "label": "Device", "field": "name", "align": "left"},
        {"name": "ip", "label": "IP", "field": "ip", "align": "left"},
        {"name": "firmware", "label": "Firmware", "field": "firmware", "align": "left"},
        {"name": "pin", "label": "PIN", "field": "pin_status", "align": "center"},
        {"name": "online", "label": "Online", "field": "online", "align": "center"},
    ]

    rows = []
    for d in spores:
        ps = ota_svc.get_pin_status(d["device_id"], "spore", user_id)
        rows.append(
            {
                "id": f"spore-{d['device_id']}",
                "type": "Spore",
                "name": d.get("device_name", ""),
                "ip": d.get("hostname", ""),
                "firmware": d.get("firmware_version", "Unknown"),
                "pin_status": {
                    "device": "Device",
                    "default": "Default",
                    "missing": "MISSING",
                }[ps],
                "online": "Yes" if d.get("is_online") else "No",
            }
        )
    for d in hyphae:
        ps = ota_svc.get_pin_status(d["device_id"], "hyphae", user_id)
        rows.append(
            {
                "id": f"hyphae-{d['device_id']}",
                "type": "Hyphae",
                "name": d.get("device_name", ""),
                "ip": d.get("hostname", ""),
                "firmware": d.get("firmware_version", "Unknown"),
                "pin_status": {
                    "device": "Device",
                    "default": "Default",
                    "missing": "MISSING",
                }[ps],
                "online": "Yes" if d.get("is_online") else "No",
            }
        )

    if not rows:
        ui.label("No devices registered").classes("text-muted text-center q-pa-lg")
        return

    table = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")

    # Color code PIN status
    table.add_slot(
        "body-cell-pin",
        r"""
        <q-td :props="props">
            <q-badge :color="props.row.pin_status === 'MISSING' ? 'red' : props.row.pin_status === 'Device' ? 'green' : 'blue'">
                {{ props.row.pin_status }}
            </q-badge>
        </q-td>
    """,
    )


@ui.refreshable
def _ota_history_section(colors: dict):
    """Show OTA update history."""
    from storage.tables.ota_history import get_ota_history

    history = get_ota_history(limit=100)
    if not history:
        ui.label("No OTA events recorded").classes("text-muted text-center q-pa-lg")
        return

    columns = [
        {"name": "device", "label": "Device", "field": "device_label", "align": "left"},
        {
            "name": "firmware",
            "label": "Firmware",
            "field": "firmware_name",
            "align": "left",
        },
        {"name": "status", "label": "Status", "field": "status", "align": "center"},
        {"name": "error", "label": "Error", "field": "error_message", "align": "left"},
        {"name": "started", "label": "Started", "field": "started_at", "align": "left"},
    ]
    rows = []
    for h in history:
        rows.append(
            {
                **h,
                "device_label": f"{h.get('device_type', '')} #{h.get('device_id', '')}",
            }
        )

    ui.table(columns=columns, rows=rows, row_key="ota_id").classes("w-full")
