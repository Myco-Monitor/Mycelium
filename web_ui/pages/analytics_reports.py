"""
Reports tab of the Analytics page.

A fixed period summary for a room or a hand-picked device set: per-device
stats, then the comparison chart, plus the Harvest Analysis sub-tab. The
tab shell and the shared helpers (date picker, chart builders, temperature
preference) live in web_ui.pages.analytics, which imports this module
lazily.
"""

import logging

from datetime import datetime, timedelta

from nicegui import ui, run

from web_ui.format import pm25_aqi_band
from web_ui.pages.analytics import (
    _build_comparison_chart,
    _build_harvest_chart,
    _date_picker,
    _device_colour,
    _temp_pref,
)
from api.services.report_service import temp_unit, to_pref_temp

from storage.tables import device_spore, device_sentinel

logger = logging.getLogger("web_ui.analytics_reports")


# Sentinel values for the Spore / Sentinel selects: every device of that kind
# in the chosen room, or none of that kind.
PICK_ROOM = "__room__"
PICK_NONE = "__none__"


def _labelled_devices(devices, source):
    """Attach the readings source and a 'name · room' label to device rows."""
    out = []
    for d in devices:
        name = d.get("device_name") or f"{source.title()} {d['device_id']}"
        room = d.get("room_name") or "no room"
        out.append(
            {
                "source": source,
                "device_id": d["device_id"],
                "room_id": d.get("room_id"),
                "name": name,
                "room": room,
                "label": f"{name} · {room}",
            }
        )
    return out


def _build_reports_panel(analytics, rooms, state, colors):
    """Construct the Reports tab contents.

    Scope is a room (every Spore and Sentinel assigned to it) and/or specific
    devices: the Spore and Sentinel selects list every device Mycelium knows,
    so a Sentinel in another room can sit alongside the tent's sensors. Each
    selected device is one line per metric row; nothing is blended across
    devices.
    """

    spores, sentinels = [], []
    try:
        spores = _labelled_devices(
            device_spore.get_all_device_spore(active_only=True), "spore"
        )
        sentinels = _labelled_devices(
            device_sentinel.get_all_device_sentinel(active_only=True), "sentinel"
        )
    except Exception as e:
        logger.warning(f"Failed to load device lists: {e}")

    room_options = {r["room_id"]: r["room_name"] for r in rooms}
    default_room = next(iter(room_options), None)

    def _pick_options(devices):
        opts = {PICK_ROOM: "All in room", PICK_NONE: "None"}
        for d in devices:
            opts[d["device_id"]] = d["label"]
        return opts

    # -- Filter bar -----------------------------------------------------------
    with ui.card().classes("w-full p-3"):
        with ui.row().classes("w-full items-end gap-3 flex-wrap"):
            start_input = _date_picker("Start Date", state["start_date"])
            end_input = _date_picker("End Date", state["end_date"])

            room_select = ui.select(
                room_options, value=default_room, label="Room"
            ).classes("w-40")
            spore_select = ui.select(
                _pick_options(spores), value=PICK_ROOM, label="Spore"
            ).classes("w-52")
            sentinel_select = ui.select(
                _pick_options(sentinels), value=PICK_ROOM, label="Sentinel"
            ).classes("w-52")

            # Quick range buttons — fill the date inputs only; nothing loads
            # until Apply
            def _set_quick_range(days):
                end_val = end_input.value or state["end_date"]
                new_start = (
                    datetime.strptime(end_val, "%Y-%m-%d") - timedelta(days=days)
                ).strftime("%Y-%m-%d")
                start_input.set_value(new_start)

            with ui.row().classes("gap-1"):
                for label, days in [("7d", 7), ("30d", 30), ("90d", 90), ("1y", 365)]:
                    ui.button(label, on_click=lambda d=days: _set_quick_range(d)).props(
                        "flat dense size=sm"
                    )

            def _selected_devices():
                """Devices to show: the room's, or the specific picks."""
                room_id = room_select.value
                picks = []
                for select, devices in (
                    (spore_select, spores),
                    (sentinel_select, sentinels),
                ):
                    value = select.value
                    if value == PICK_NONE:
                        continue
                    if value == PICK_ROOM:
                        picks.extend(
                            d
                            for d in devices
                            if room_id is not None and d["room_id"] == room_id
                        )
                    else:
                        picks.extend(d for d in devices if d["device_id"] == value)
                return picks

            # Apply button — queries run in a worker thread so the UI stays
            # responsive; rendering happens back on the event loop
            async def _apply_filters():
                state["start_date"] = start_input.value or state["start_date"]
                state["end_date"] = end_input.value or state["end_date"]
                picks = _selected_devices()
                if not picks:
                    ui.notify(
                        "No devices selected — the room has none assigned; "
                        "pick a specific Spore or Sentinel",
                        type="warning",
                    )
                    return
                n = ui.notification("Loading report…", spinner=True, timeout=None)
                try:
                    data = await run.io_bound(
                        _fetch_report_data,
                        analytics,
                        state["start_date"],
                        state["end_date"],
                        picks,
                    )
                finally:
                    n.dismiss()
                _render_reports(content_container, data, colors)

            ui.button("Apply", icon="refresh", on_click=_apply_filters).props("dense")

    # Report content sits under the filter bar and is rebuilt on every Apply
    content_container = ui.column().classes("w-full gap-4")

    # No initial load — data is only fetched when the user presses Apply
    with content_container:
        ui.label(
            "Choose a date range and a room (or specific devices), then Apply."
        ).classes("text-muted p-4")


def _fetch_report_data(analytics, start, end, devices):
    """Run all report queries. No UI calls — safe for run.io_bound.

    One panel per selected device: its readings and stats. Harvests are
    period-wide and fetched once.
    """
    data = {"panels": [], "harvests": []}

    for dev in devices:
        panel = {"device": dev, "readings": [], "stats": None}
        try:
            if dev["source"] == "sentinel":
                panel["readings"] = analytics.get_sentinel_readings_for_period(
                    start, end, device_id=dev["device_id"]
                )
            else:
                panel["readings"] = analytics.get_readings_for_period(
                    start, end, device_id=dev["device_id"]
                )
        except Exception as e:
            logger.warning(f"Failed to load readings for {dev['label']}: {e}")

        try:
            panel["stats"] = analytics.calculate_environmental_stats(panel["readings"])
        except Exception as e:
            logger.warning(f"Failed to calculate stats for {dev['label']}: {e}")

        data["panels"].append(panel)

    try:
        data["harvests"] = analytics.get_harvests_for_period(start, end)
    except Exception as e:
        logger.warning(f"Failed to load harvests: {e}")

    return data


def _render_reports(container, data, colors):
    """Clear and rebuild the report content area from pre-fetched data."""
    container.clear()

    panels = data["panels"]
    harvests = data["harvests"]
    # Reads app.storage.user, so it stays on the UI side (never in the worker)
    pref = _temp_pref()

    with container:
        # Sub-tabs
        with ui.tabs().classes("w-full") as sub_tabs:
            env_tab = ui.tab("Environmental Trends", icon="thermostat")
            harvest_tab = ui.tab("Harvest Analysis", icon="grass")

        with ui.tab_panels(sub_tabs, value=env_tab).classes("w-full"):
            # -- Environmental Trends -----------------------------------------
            # Per-device stats, then every device on one figure: a row per
            # metric, a colour per device
            with ui.tab_panel(env_tab):
                _build_device_stats(panels, pref)
                with ui.card().classes("w-full p-3 q-mt-md"):
                    ui.plotly(_build_comparison_chart(panels, pref, colors)).classes(
                        "w-full"
                    )

            # -- Harvest Analysis ---------------------------------------------
            with ui.tab_panel(harvest_tab):
                _build_harvest_analysis(harvests, colors)


# -- Report sections ----------------------------------------------------------


def _stat_card(label, value, icon, colors):
    """Render a small stat card (Harvest Analysis)."""
    with ui.card().classes("p-3 flex-1 min-w-40"):
        with ui.row().classes("items-center gap-2"):
            ui.icon(icon, size="sm").style(f"color: {colors['primary']}")
            ui.label(label).classes("text-caption text-muted")
        ui.label(str(value)).classes("text-h5 q-mt-xs")


def _fmt_stat(value, fmt):
    """Format a stat value, or '--' when the metric has no data."""
    return fmt.format(value) if value is not None else "--"


def _fmt_range(lo, hi, fmt):
    """'min – max' caption for a metric, or '--' when it has no data."""
    if lo is None or hi is None:
        return "--"
    return f"{fmt.format(lo)} – {fmt.format(hi)}"


def _aqi_chip(pm25):
    """EPA AQI band chip for a PM2.5 value; renders nothing when unavailable.

    A styled label rather than ui.badge: an inline background-color on a
    badge loses to Quasar's `bg-primary !important` class.
    """
    band = pm25_aqi_band(pm25)
    if band is None:
        return
    text, bg, fg = band
    ui.label(text).classes("text-caption text-weight-bold q-px-sm").style(
        f"background-color: {bg}; color: {fg}; border-radius: 12px;"
    )


def _stat_cell(label, value, caption, pm25=None):
    """One metric cell of the device stats grid: label, bold value, range caption."""
    with ui.column().classes("gap-0"):
        ui.label(label).classes("text-caption text-muted")
        with ui.row().classes("items-center gap-2 no-wrap"):
            ui.label(value).classes("text-weight-bold")
            if pm25 is not None:
                _aqi_chip(pm25)
        ui.label(caption).classes("text-caption text-muted")


def _build_device_stats(panels, temp_pref):
    """Per-device stats grid at the top of the report.

    One row per device: colour dot (matches its lines), name, source badge,
    room, then CO2 / Humidity / Temp (Sentinels also PM2.5 with its EPA
    band) as the average with a min – max caption, and the data-point
    count. Cells are direct grid children so columns line up across devices.
    """
    unit = temp_unit(temp_pref)
    with ui.card().classes("w-full p-3"):
        with (
            ui.element("div")
            .classes("w-full")
            .style(
                "display: grid; "
                "grid-template-columns: 14px minmax(200px, 2fr) repeat(5, minmax(110px, 1fr)); "
                "gap: 8px 16px; align-items: center; overflow-x: auto;"
            )
        ):
            for i, panel in enumerate(panels):
                dev = panel["device"]
                st = panel["stats"]  # None when the device has no readings in range
                is_sentinel = dev["source"] == "sentinel"

                def val(attr):
                    return getattr(st, attr) if st else None

                ui.element("div").style(
                    "width: 12px; height: 12px; border-radius: 50%; "
                    f"background: {_device_colour(i)};"
                )
                with ui.row().classes("items-center gap-2 no-wrap"):
                    ui.label(dev["name"]).classes("text-subtitle2 text-weight-bold")
                    ui.badge("Sentinel" if is_sentinel else "Spore").props("outline")
                    ui.label(dev["room"]).classes("text-caption text-muted")

                _stat_cell(
                    "CO2",
                    _fmt_stat(val("co2_mean"), "{:.0f} ppm"),
                    _fmt_range(val("co2_min"), val("co2_max"), "{:.0f}"),
                )
                _stat_cell(
                    "Humidity",
                    _fmt_stat(val("humidity_mean"), "{:.1f}%"),
                    _fmt_range(val("humidity_min"), val("humidity_max"), "{:.0f}"),
                )
                _stat_cell(
                    "Temp",
                    _fmt_stat(
                        to_pref_temp(val("temp_mean"), temp_pref), "{:.1f} " + unit
                    ),
                    _fmt_range(
                        to_pref_temp(val("temp_min"), temp_pref),
                        to_pref_temp(val("temp_max"), temp_pref),
                        "{:.1f}",
                    ),
                )
                if is_sentinel:
                    _stat_cell(
                        "PM2.5",
                        _fmt_stat(val("pm25_mean"), "{:.1f} µg/m³"),
                        _fmt_range(val("pm25_min"), val("pm25_max"), "{:.1f}"),
                        pm25=val("pm25_mean"),
                    )
                else:
                    ui.element("div")  # keeps the grid columns aligned
                _stat_cell("Points", f"{st.data_points:,}" if st else "0", "")


def _build_harvest_analysis(harvests, colors):
    """Harvest Analysis sub-tab content."""
    total_harvests = len(harvests)
    yields = [h.get("yield_weight", 0) or 0 for h in harvests]
    total_yield = sum(yields)
    avg_yield = total_yield / total_harvests if total_harvests else 0
    best_yield = max(yields) if yields else 0

    with ui.row().classes("w-full gap-3 flex-wrap q-mb-md"):
        _stat_card("Total Harvests", str(total_harvests), "grass", colors)
        _stat_card("Total Yield", f"{total_yield:.0f} g", "scale", colors)
        _stat_card("Avg Yield", f"{avg_yield:.0f} g", "trending_up", colors)
        _stat_card("Best Yield", f"{best_yield:.0f} g", "emoji_events", colors)

    with ui.card().classes("w-full p-3"):
        ui.label("Harvest Yields").classes("text-subtitle1 text-weight-bold q-mb-sm")
        fig = _build_harvest_chart(harvests, colors)
        ui.plotly(fig).classes("w-full").style("height: 400px")
