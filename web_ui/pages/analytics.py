"""
Analytics page for Mycelium NiceGUI application.

Three tabs: Dashboard (pre-built charts), Graph Builder (curated ad-hoc
charts over the readings tables), and Records (preview / download / delete
raw readings). No code execution.
"""

import csv
import io
import logging
from datetime import datetime, timedelta

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from nicegui import ui, app, run

from web_ui.layout import page_layout, back_to_dashboard
from web_ui.theme import get_colors, chart_layout
from web_ui.format import to_user_dt, pm25_aqi_band

from storage.tables import (
    readings_spore,
    readings_hyphae,
    readings_pressure,
    readings_weather,
    readings_sentinel,
    device_spore,
    device_hyphae,
    device_sentinel,
)

logger = logging.getLogger("web_ui.analytics")


# -- Readings source registry -------------------------------------------------
# One entry per readings table, mapping it to its storage module, the device
# list it is keyed to, and the numeric columns worth graphing. Both the Graph
# Builder and Records panels drive off this so there is a single code path
# instead of five near-duplicates.
#
# Call convention: get_device_readings / delete_device_readings take the device
# id as the FIRST POSITIONAL arg in every module (spore/weather/hyphae/sentinel
# name it device_id, pressure names it hyphae_id), so always pass it
# positionally. For readings_hyphae, relay_number is keyword-defaulted None, so
# the same call shape works without special-casing. The timestamp column is
# `reading_ts` in all five tables, returned ORDER BY reading_ts DESC.

READINGS_SOURCES = {
    "readings_spore": {
        "label": "Spore Sensor Readings",
        "module": readings_spore,
        "device_fn": lambda: device_spore.get_all_device_spore(active_only=True),
        # Standard metric order: CO2, humidity, temp
        "metrics": {"co2": "CO2 (ppm)", "humidity": "Humidity (%)", "temp": "Temp"},
        "has_relay": False,
    },
    "readings_sentinel": {
        "label": "Sentinel Air Quality Readings",
        "module": readings_sentinel,
        "device_fn": lambda: device_sentinel.get_all_device_sentinel(active_only=True),
        # PM first (the hero metrics), then the standard CO2 / humidity / temp
        # trio, then the remaining channels. Nulls (unavailable channels) are
        # stored as-is and simply leave gaps in a series.
        "metrics": {
            "pm2_5": "PM2.5 (µg/m³)",
            "pm1": "PM1 (µg/m³)",
            "pm4": "PM4 (µg/m³)",
            "pm10": "PM10 (µg/m³)",
            "voc": "VOC Index",
            "nox": "NOx Index",
            "co2": "CO2 (ppm)",
            "humidity": "Humidity (%)",
            "temp": "Temp",
            "pressure_hpa": "Pressure (hPa)",
        },
        "has_relay": False,
    },
    "readings_weather": {
        "label": "Weather Readings",
        "module": readings_weather,
        "device_fn": lambda: device_spore.get_all_device_spore(active_only=True),
        # Humidity before temp per the standard metric order (no CO2 here)
        "metrics": {
            "humidity": "Humidity (%)",
            "current_temp": "Temp",
            "feels_like": "Feels Like",
            "ambient_pressure": "Pressure (hPa)",
            "wind_speed": "Wind (m/s)",
            "wind_deg": "Wind Dir (°)",
        },
        "has_relay": False,
    },
    "readings_pressure": {
        "label": "Pressure Readings",
        "module": readings_pressure,
        "device_fn": lambda: device_hyphae.get_all_device_hyphae(active_only=True),
        "metrics": {"pressure_hpa": "Pressure (hPa)"},
        "has_relay": False,
    },
    "readings_hyphae": {
        "label": "Relay / Actuation Readings",
        "module": readings_hyphae,
        "device_fn": lambda: device_hyphae.get_all_device_hyphae(active_only=True),
        "metrics": {"relay_state": "Relay State", "cooldown": "Cooldown"},
        "has_relay": True,
    },
}

# Explicit large cap for graph/records queries — get_device_readings defaults
# to limit=100, which would silently truncate a real range.
READINGS_QUERY_LIMIT = 100_000

# Cap on rows rendered into the preview table (the true total still drives the
# count label, CSV download, and delete).
PREVIEW_ROW_CAP = 500

# Series colours for the Dashboard comparison chart (one per device) and the
# Graph Builder / relay charts (one per metric or relay). Material 400 hues,
# readable on the dark template.
SERIES_PALETTE = ["#ef5350", "#42a5f5", "#66bb6a", "#ffa726", "#ab47bc", "#26c6da"]

# Comparison-chart rows as (readings-row field, axis title). Base rows always
# appear (the temp title gets the user's unit); Sentinel rows only when a
# Sentinel is among the selected devices.
BASE_ROWS = [
    ("co2", "CO2 (ppm)"),
    ("humidity", "Humidity (%)"),
    ("temperature", "Temp"),
]
SENTINEL_ROWS = [("pm2_5", "PM2.5 (µg/m³)"), ("voc", "VOC Index"), ("nox", "NOx Index")]
CHART_ROW_PX = 160  # figure height per metric row
CHART_BASE_PX = 80  # plus legend and margins


def _device_colour(index: int) -> str:
    """Colour of the device at `index` in selection order; dot and lines agree."""
    return SERIES_PALETTE[index % len(SERIES_PALETTE)]


def _normalize_end_ts(end_date: str) -> str:
    """Widen a YYYY-MM-DD end bound to include the whole day.

    reading_ts is a full datetime.isoformat() timestamp ("YYYY-MM-DDT...") and
    the table queries filter `reading_ts <= end_ts` as strings, so the suffix
    must be 'T'-separated: a bare date — or a space-separated suffix, which
    sorts before 'T' — would exclude every reading on the end date itself.
    Applied identically in preview, download, and delete so the previewed
    count equals the deleted count.
    """
    if end_date and len(end_date) == 10:
        return end_date + "T23:59:59.999999"
    return end_date


# -- Temperature unit preference ---------------------------------------------


def _temp_pref() -> str:
    """Current user's temperature unit preference ('C' or 'F'). Defaults to 'C'."""
    try:
        from storage.tables.user_settings import get_user_setting

        uid = app.storage.user.get("user_id")
        info = get_user_setting(uid) if uid else None
        return (info.get("temp_pref") or "C") if info else "C"
    except Exception:
        return "C"


def _temp_unit(pref: str) -> str:
    """Display unit string for a preference."""
    return "°F" if pref == "F" else "°C"


def _to_pref_temp(celsius, pref: str):
    """Convert a stored Celsius value to the preferred unit (float), or None."""
    if celsius is None:
        return None
    try:
        c = float(celsius)
    except (TypeError, ValueError):
        return None
    return c * 9 / 5 + 32 if pref == "F" else c


# -- Chart builders -----------------------------------------------------------


def _chart_ts(value):
    """Convert a stored (naive UTC) timestamp to a naive user-local datetime.

    Plotly renders naive datetimes as-is, so charts show the user's timezone.
    """
    dt = to_user_dt(value)
    return dt.replace(tzinfo=None) if dt else value


def _build_comparison_chart(panels, temp_pref, colors):
    """One figure, one row per metric, one line per device in its colour.

    Rows share the time axis, so a zoom on any row applies to all. The base
    rows (CO2, humidity, temp) always appear; the Sentinel rows (PM2.5, VOC,
    NOx) only when a Sentinel is among the panels, and Spores add no trace
    there. A device with no readings keeps its legend entry; an empty trace
    draws nothing.
    """
    if not any(p["readings"] for p in panels):
        return _empty_figure("No environmental data for selected period", colors)

    unit = _temp_unit(temp_pref)
    rows = [
        (field, f"{label} ({unit})" if field == "temperature" else label)
        for field, label in BASE_ROWS
    ]
    if any(p["device"]["source"] == "sentinel" for p in panels):
        rows += SENTINEL_ROWS
    sentinel_fields = {field for field, _label in SENTINEL_ROWS}

    fig = make_subplots(
        rows=len(rows), cols=1, shared_xaxes=True, vertical_spacing=0.04
    )
    for i, panel in enumerate(panels):
        dev = panel["device"]
        readings = panel["readings"]
        x = [_chart_ts(r.get("timestamp", "")) for r in readings]
        colour = _device_colour(i)
        # Spore and Sentinel ids come from different tables and can collide,
        # so the legend group (one click hides the device on every row)
        # carries the source too
        group = f"{dev['source']}:{dev['device_id']}"
        first = True
        for row, (field, _label) in enumerate(rows, start=1):
            if field in sentinel_fields and dev["source"] != "sentinel":
                continue
            y = [r.get(field) for r in readings]
            if field == "temperature":
                y = [_to_pref_temp(v, temp_pref) for v in y]
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    name=dev["name"],
                    mode="lines",
                    line=dict(color=colour),
                    legendgroup=group,
                    showlegend=first,
                ),
                row=row,
                col=1,
            )
            first = False

    for row, (_field, label) in enumerate(rows, start=1):
        fig.update_yaxes(title_text=label, row=row, col=1)
    fig.update_xaxes(title_text="Time", row=len(rows), col=1)
    fig.update_layout(
        **chart_layout(colors),
        margin=dict(l=70, r=20, t=40, b=40),
        # Height lives in the layout, not CSS, so it follows the row count
        height=CHART_BASE_PX + CHART_ROW_PX * len(rows),
        hovermode="x unified",
        legend=dict(orientation="h", x=0, xanchor="left", y=1.0, yanchor="bottom"),
    )
    return fig


def _build_harvest_chart(harvests, colors):
    """Build a plotly bar chart for harvest data."""
    if not harvests:
        return _empty_figure("No harvest data for selected period", colors)

    dates = [h.get("harvest_date", "")[:10] for h in harvests]
    yields = [h.get("yield_weight", 0) or 0 for h in harvests]
    labels = [f"Batch {h.get('bulk_id', '?')}" for h in harvests]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=dates,
            y=yields,
            name="Yield (g)",
            text=labels,
            textposition="outside",
            marker_color=colors["primary"],
        )
    )
    fig.update_layout(
        **chart_layout(colors),
        margin=dict(l=60, r=20, t=30, b=40),
        xaxis=dict(title="Harvest Date"),
        yaxis=dict(title="Yield (g)"),
    )
    return fig


def _empty_figure(message: str, colors):
    """Create an empty plotly figure with a centered message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=16, color=colors["text_secondary"]),
    )
    fig.update_layout(
        **chart_layout(colors),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=20, r=20, t=20, b=20),
    )
    return fig


# -- Page routes --------------------------------------------------------------


@ui.page("/analytics")
@ui.page("/analytics-dashboard")
def analytics_page():
    """Analytics page with Dashboard, Graph Builder, and Records tabs."""
    user = app.storage.user
    if not user.get("user_id"):
        ui.navigate.to("/login")
        return

    page_layout("Analytics")
    back_to_dashboard()
    colors = get_colors()

    # Service and data defaults
    from api.services.analytics_service import AnalyticsService

    analytics = AnalyticsService()

    rooms = []
    try:
        rooms = analytics.get_rooms()
    except Exception:
        pass

    min_date, max_date = None, None
    try:
        min_date, max_date = analytics.get_date_range()
    except Exception:
        pass

    today = datetime.now().strftime("%Y-%m-%d")
    default_end = max_date[:10] if max_date else today
    default_start = (
        datetime.strptime(default_end, "%Y-%m-%d") - timedelta(days=30)
    ).strftime("%Y-%m-%d")

    # Shared filter state; `panels` holds the last Apply's per-device results
    # so Export CSV writes exactly what is on screen
    state = {
        "start_date": default_start,
        "end_date": default_end,
        "panels": [],
    }

    # ---- Main tabs ----------------------------------------------------------

    with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-4"):
        ui.label("Analytics").classes("text-h4")

        with ui.tabs().classes("w-full") as main_tabs:
            dashboard_tab = ui.tab("Dashboard", icon="bar_chart")
            graph_tab = ui.tab("Graph Builder", icon="show_chart")
            records_tab = ui.tab("Records", icon="table_rows")

        with ui.tab_panels(main_tabs, value=dashboard_tab).classes("w-full"):
            # ==============================================================
            # DASHBOARD TAB
            # ==============================================================
            with ui.tab_panel(dashboard_tab):
                _build_dashboard_panel(analytics, rooms, state, colors)

            # ==============================================================
            # GRAPH BUILDER TAB
            # ==============================================================
            with ui.tab_panel(graph_tab):
                _build_graph_builder_panel(colors)

            # ==============================================================
            # RECORDS TAB
            # ==============================================================
            with ui.tab_panel(records_tab):
                _build_records_panel(colors)


# -- Dashboard panel ----------------------------------------------------------


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


def _build_dashboard_panel(analytics, rooms, state, colors):
    """Construct the dashboard tab contents.

    Scope is a room (every Spore and Sentinel assigned to it) and/or specific
    devices: the Spore and Sentinel selects list every device Mycelium knows,
    so a Sentinel in another room can sit alongside the tent's sensors. Each
    selected device is one line per metric row; nothing is blended across
    devices.
    """

    # Containers that get refreshed when filters change
    content_container = ui.column().classes("w-full gap-4")

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
                n = ui.notification("Loading analytics…", spinner=True, timeout=None)
                try:
                    data = await run.io_bound(
                        _fetch_dashboard_data,
                        analytics,
                        state["start_date"],
                        state["end_date"],
                        picks,
                    )
                finally:
                    n.dismiss()
                state["panels"] = data["panels"]
                _render_dashboard(content_container, data, colors)

            ui.button("Apply", icon="refresh", on_click=_apply_filters).props("dense")

            # Export CSV — the rows behind the panels currently on screen.
            # Spore and Sentinel rows share the common columns; the Sentinel
            # air-quality columns are blank on Spore rows.
            def _export_csv():
                rows = [r for p in state["panels"] for r in p["readings"]]
                if not rows:
                    ui.notify("No data to export — press Apply first", type="warning")
                    return
                try:
                    fieldnames = []
                    for r in rows:
                        for key in r.keys():
                            if key not in fieldnames:
                                fieldnames.append(key)
                    output = io.StringIO()
                    writer = csv.DictWriter(output, fieldnames=fieldnames, restval="")
                    writer.writeheader()
                    writer.writerows(rows)
                    ui.download(
                        output.getvalue().encode(),
                        f"analytics_{state['start_date']}_{state['end_date']}.csv",
                    )
                except Exception as e:
                    ui.notify(f"Export failed: {e}", type="negative")

            ui.button("Export CSV", icon="download", on_click=_export_csv).props(
                "dense outline"
            )

    # No initial load — data is only fetched when the user presses Apply
    with content_container:
        ui.label(
            "Choose a date range and a room (or specific devices), then Apply."
        ).classes("text-muted p-4")


def _fetch_dashboard_data(analytics, start, end, devices):
    """Run all dashboard queries. No UI calls — safe for run.io_bound.

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


def _render_dashboard(container, data, colors):
    """Clear and rebuild the dashboard content area from pre-fetched data."""
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


# -- Dashboard sub-sections ---------------------------------------------------


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
    """Per-device stats grid above the comparison chart.

    One row per device: colour dot (matches its lines), name, source badge,
    room, then CO2 / Humidity / Temp (Sentinels also PM2.5 with its EPA
    band) as the average with a min – max caption, and the data-point
    count. Cells are direct grid children so columns line up across devices.
    """
    unit = _temp_unit(temp_pref)
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
                        _to_pref_temp(val("temp_mean"), temp_pref), "{:.1f} " + unit
                    ),
                    _fmt_range(
                        _to_pref_temp(val("temp_min"), temp_pref),
                        _to_pref_temp(val("temp_max"), temp_pref),
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


# -- Shared filter-bar helpers (Graph Builder + Records) ----------------------


def _date_picker(label: str, value: str):
    """Build a date input with a calendar popup; returns the ui.input.

    Mirrors the Dashboard filter-bar date pickers.
    """
    with ui.input(label, value=value).classes("w-40") as date_input:
        with ui.menu().props("no-parent-event") as menu:
            with ui.date().bind_value(date_input):
                pass
        with date_input.add_slot("append"):
            ui.icon("edit_calendar").on("click", menu.open).classes("cursor-pointer")
    return date_input


def _device_options(source: dict) -> dict:
    """{device_id: 'name · room'} options for a source's device list."""
    options = {}
    try:
        for d in source["device_fn"]():
            name = d.get("device_name") or f"Device {d['device_id']}"
            room = d.get("room_name") or "no room"
            options[d["device_id"]] = f"{name} · {room}"
    except Exception as e:
        logger.warning(f"Failed to load device list: {e}")
    return options


def _relay_options(module, device_id) -> dict:
    """{relay_number: label} for a hyphae device, plus an 'All relays' entry."""
    options = {None: "All relays"}
    try:
        rows = module.get_device_readings(device_id, limit=READINGS_QUERY_LIMIT)
        for n in sorted(
            {r["relay_number"] for r in rows if r.get("relay_number") is not None}
        ):
            options[n] = f"Relay {n}"
    except Exception as e:
        logger.warning(f"Failed to load relay list: {e}")
    return options


def _query_readings(source: dict, device_id, start, end, relay=None):
    """Fetch readings for one device over a date range, chronological order.

    Returns (rows, truncated) where truncated flags a possible limit hit.
    """
    module = source["module"]
    end_ts = _normalize_end_ts(end)
    kwargs = {"limit": READINGS_QUERY_LIMIT, "start_ts": start, "end_ts": end_ts}
    if source["has_relay"] and relay is not None:
        kwargs["relay_number"] = relay
    rows = module.get_device_readings(device_id, **kwargs)
    truncated = len(rows) >= READINGS_QUERY_LIMIT
    # Tables return newest-first; reverse to chronological for plotting/preview.
    rows = list(reversed(rows))
    return rows, truncated


# -- Graph Builder panel ------------------------------------------------------


def _build_metric_chart(rows, metric_specs, chart_type, colors):
    """Generic multi-metric, multi-axis chart over readings rows.

    metric_specs: list of (field, label) in selection order. Metrics with
    differing unit labels are placed on separate y-axes (up to 3), mirroring
    the Dashboard env-trends chart. `rows` must already be chronological.
    """
    if not rows or not metric_specs:
        return _empty_figure("No data for selected filters", colors)

    x = [_chart_ts(r.get("reading_ts", "")) for r in rows]
    palette = SERIES_PALETTE

    # Assign each distinct unit label to an axis (y, y2, y3). Group by the
    # label text so like-united metrics share a scale.
    axis_for_label = {}
    axis_names = ["y", "y2", "y3"]
    over_axis_limit = False

    fig = go.Figure()
    for i, (field, label) in enumerate(metric_specs):
        if label not in axis_for_label:
            if len(axis_for_label) < len(axis_names):
                axis_for_label[label] = axis_names[len(axis_for_label)]
            else:
                over_axis_limit = True
                continue
        yaxis = axis_for_label[label]
        color = palette[i % len(palette)]
        y = [r.get(field) for r in rows]

        if chart_type == "bar":
            fig.add_trace(go.Bar(x=x, y=y, name=label, yaxis=yaxis, marker_color=color))
        elif chart_type == "stepped":
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    name=label,
                    yaxis=yaxis,
                    mode="lines",
                    line=dict(color=color, shape="hv"),
                )
            )
        elif chart_type == "area":
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    name=label,
                    yaxis=yaxis,
                    mode="lines",
                    fill="tozeroy",
                    line=dict(color=color),
                )
            )
        else:  # line
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    name=label,
                    yaxis=yaxis,
                    mode="lines",
                    line=dict(color=color),
                )
            )

    # Build axis layout from the labels we actually assigned.
    label_by_axis = {v: k for k, v in axis_for_label.items()}
    layout = dict(
        **chart_layout(colors),
        margin=dict(l=60, r=60, t=30, b=40),
        legend=dict(orientation="h", y=1.12),
        xaxis=dict(title="Time"),
        yaxis=dict(title=label_by_axis.get("y", "")),
    )
    if "y2" in label_by_axis:
        layout["yaxis2"] = dict(
            title=label_by_axis["y2"], side="right", overlaying="y", showgrid=False
        )
    if "y3" in label_by_axis:
        layout["yaxis3"] = dict(
            title=label_by_axis["y3"],
            side="right",
            overlaying="y",
            anchor="free",
            position=0.95,
            showgrid=False,
        )
    fig.update_layout(**layout)
    fig._over_axis_limit = over_axis_limit  # read by caller for a warning
    return fig


def _build_graph_builder_panel(colors):
    """Curated ad-hoc chart builder over the readings tables (no code)."""
    default_source = "readings_spore"
    src = READINGS_SOURCES[default_source]

    today = datetime.now().strftime("%Y-%m-%d")
    default_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    chart_container = ui.column().classes("w-full gap-2")

    with ui.card().classes("w-full p-3"):
        with ui.row().classes("w-full items-end gap-3 flex-wrap"):
            source_select = ui.select(
                {k: v["label"] for k, v in READINGS_SOURCES.items()},
                value=default_source,
                label="Data Source",
            ).classes("w-52")

            device_select = ui.select(_device_options(src), label="Device").classes(
                "w-52"
            )

            metrics_select = (
                ui.select(src["metrics"], multiple=True, label="Metrics")
                .classes("w-64")
                .props("use-chips")
            )

            relay_select = ui.select(
                {None: "All relays"}, value=None, label="Relay"
            ).classes("w-40")
            relay_select.set_visibility(src["has_relay"])

            start_input = _date_picker("Start Date", default_start)
            end_input = _date_picker("End Date", today)

            with ui.row().classes("gap-1"):
                for lbl, days in [("7d", 7), ("30d", 30), ("90d", 90), ("1y", 365)]:

                    def _quick(d=days):
                        new_start = (
                            datetime.strptime(end_input.value or today, "%Y-%m-%d")
                            - timedelta(days=d)
                        ).strftime("%Y-%m-%d")
                        start_input.set_value(new_start)

                    ui.button(lbl, on_click=_quick).props("flat dense size=sm")

            chart_type_select = ui.select(
                ["line", "area", "bar"], value="line", label="Chart Type"
            ).classes("w-36")

            def _on_source_change():
                new_src = READINGS_SOURCES[source_select.value]
                device_select.options = _device_options(new_src)
                device_select.value = None
                device_select.update()
                metrics_select.options = new_src["metrics"]
                metrics_select.value = []
                metrics_select.update()
                relay_select.set_visibility(new_src["has_relay"])
                relay_select.options = {None: "All relays"}
                relay_select.value = None
                relay_select.update()
                # Relay data is a 0/1 step series; force stepped and lock it.
                if new_src["has_relay"]:
                    chart_type_select.value = "stepped"
                    chart_type_select.options = ["stepped"]
                else:
                    chart_type_select.options = ["line", "area", "bar"]
                    if chart_type_select.value == "stepped":
                        chart_type_select.value = "line"
                chart_type_select.update()

            source_select.on("update:model-value", lambda _: _on_source_change())

            def _on_device_change():
                new_src = READINGS_SOURCES[source_select.value]
                if new_src["has_relay"] and device_select.value is not None:
                    relay_select.options = _relay_options(
                        new_src["module"], device_select.value
                    )
                    relay_select.value = None
                    relay_select.update()

            device_select.on("update:model-value", lambda _: _on_device_change())

            ui.button(
                "Generate", icon="show_chart", on_click=lambda: _generate()
            ).props("dense")

    def _generate():
        chart_container.clear()
        source = READINGS_SOURCES[source_select.value]
        device_id = device_select.value
        selected = list(metrics_select.value or [])
        if device_id is None:
            ui.notify("Pick a device", type="warning")
            return
        if not selected:
            ui.notify("Pick at least one metric", type="warning")
            return
        try:
            rows, truncated = _query_readings(
                source,
                device_id,
                start_input.value,
                end_input.value,
                relay=relay_select.value if source["has_relay"] else None,
            )
        except Exception as e:
            ui.notify(f"Query failed: {e}", type="negative")
            return

        if truncated:
            ui.notify(
                f"Showing newest {READINGS_QUERY_LIMIT:,} points; range may be truncated",
                type="warning",
            )

        chart_type = chart_type_select.value or "line"
        # Relay data with no single relay chosen: one stepped trace per relay.
        if source["has_relay"] and relay_select.value is None:
            fig = _build_relay_chart(rows, colors)
        else:
            metric_specs = [(f, source["metrics"][f]) for f in selected]
            fig = _build_metric_chart(rows, metric_specs, chart_type, colors)
            if getattr(fig, "_over_axis_limit", False):
                ui.notify(
                    "More than 3 distinct units selected; extra metrics were dropped",
                    type="warning",
                )

        with chart_container:
            ui.plotly(fig).classes("w-full").style("height: 420px")
            ui.label(f"{len(rows):,} data points").classes("text-caption text-muted")

    with chart_container:
        ui.label("Choose a source, device, and metrics, then Generate.").classes(
            "text-muted p-4"
        )


def _build_relay_chart(rows, colors):
    """Stepped 0/1 chart with one trace per relay_number."""
    if not rows:
        return _empty_figure("No data for selected filters", colors)
    palette = SERIES_PALETTE
    by_relay = {}
    for r in rows:
        by_relay.setdefault(r.get("relay_number"), []).append(r)
    fig = go.Figure()
    for i, (relay, rrows) in enumerate(
        sorted(by_relay.items(), key=lambda kv: (kv[0] is None, kv[0]))
    ):
        fig.add_trace(
            go.Scatter(
                x=[r.get("reading_ts", "") for r in rrows],
                y=[r.get("relay_state") for r in rrows],
                name=f"Relay {relay}",
                mode="lines",
                line=dict(color=palette[i % len(palette)], shape="hv"),
            )
        )
    fig.update_layout(
        **chart_layout(colors),
        margin=dict(l=60, r=20, t=30, b=40),
        legend=dict(orientation="h", y=1.12),
        xaxis=dict(title="Time"),
        yaxis=dict(title="Relay State", tickvals=[0, 1], range=[-0.1, 1.1]),
    )
    return fig


# -- Records panel ------------------------------------------------------------


def _build_records_panel(colors):
    """Preview, download, and (admin-only) delete raw readings rows."""
    from web_ui.auth import is_admin

    default_source = "readings_spore"
    src = READINGS_SOURCES[default_source]

    today = datetime.now().strftime("%Y-%m-%d")
    default_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    # Selection shared by Preview / Download / Delete so they act on the same set.
    sel = {"rows": [], "total": 0}

    preview_container = ui.column().classes("w-full gap-2")

    with ui.card().classes("w-full p-3"):
        with ui.row().classes("w-full items-end gap-3 flex-wrap"):
            source_select = ui.select(
                {k: v["label"] for k, v in READINGS_SOURCES.items()},
                value=default_source,
                label="Data Source",
            ).classes("w-52")

            device_options = {"__all__": "All devices"}
            device_options.update(_device_options(src))
            device_select = ui.select(
                device_options, value="__all__", label="Device"
            ).classes("w-52")

            relay_select = ui.select(
                {None: "All relays"}, value=None, label="Relay"
            ).classes("w-40")
            relay_select.set_visibility(src["has_relay"])

            start_input = _date_picker("Start Date", default_start)
            end_input = _date_picker("End Date", today)

            def _on_source_change():
                new_src = READINGS_SOURCES[source_select.value]
                opts = {"__all__": "All devices"}
                opts.update(_device_options(new_src))
                device_select.options = opts
                device_select.value = "__all__"
                device_select.update()
                relay_select.set_visibility(new_src["has_relay"])
                relay_select.options = {None: "All relays"}
                relay_select.value = None
                relay_select.update()

            source_select.on("update:model-value", lambda _: _on_source_change())

            ui.button("Preview", icon="search", on_click=lambda: _preview()).props(
                "dense"
            )

    def _target_ids(source):
        """Device ids to act on: the selected one, or all for this source."""
        if device_select.value == "__all__":
            try:
                return [d["device_id"] for d in source["device_fn"]()]
            except Exception as e:
                logger.warning(f"Failed to list devices: {e}")
                return []
        return [device_select.value]

    def _collect_rows(source):
        """Fetch matching rows across all target devices (chronological)."""
        rows = []
        for dev_id in _target_ids(source):
            try:
                got, _ = _query_readings(
                    source,
                    dev_id,
                    start_input.value,
                    end_input.value,
                    relay=relay_select.value if source["has_relay"] else None,
                )
                rows.extend(got)
            except Exception as e:
                logger.warning(f"Failed to query device {dev_id}: {e}")
        return rows

    def _scope_label(source):
        if device_select.value == "__all__":
            return "all devices"
        name = (
            source_select.value and device_select.options.get(device_select.value)
        ) or "device"
        return f"'{name}'"

    def _preview():
        preview_container.clear()
        source = READINGS_SOURCES[source_select.value]
        rows = _collect_rows(source)
        sel["rows"] = rows
        sel["total"] = len(rows)

        with preview_container:
            with ui.row().classes("w-full items-center gap-3"):
                ui.label(f"{len(rows):,} rows match").classes("text-subtitle2")
                ui.button(
                    "Download CSV", icon="download", on_click=lambda: _download()
                ).props("dense outline")
                if is_admin():
                    ui.button(
                        "Delete",
                        icon="delete_forever",
                        on_click=lambda: _confirm_delete(),
                    ).props("dense color=negative outline")

            if not rows:
                ui.label("No rows for the selected filters.").classes("text-muted")
                return

            columns = [
                {"name": c, "label": c, "field": c, "align": "left"}
                for c in rows[0].keys()
            ]
            display_rows = rows[:PREVIEW_ROW_CAP]
            if len(rows) > PREVIEW_ROW_CAP:
                ui.label(
                    f"Showing first {PREVIEW_ROW_CAP:,} of {len(rows):,} rows "
                    f"(download / delete act on all {len(rows):,})."
                ).classes("text-caption text-muted")
            ui.table(columns=columns, rows=display_rows, row_key="reading_ts").classes(
                "w-full"
            ).props("dense")

    def _download():
        rows = sel["rows"]
        if not rows:
            ui.notify("No data to export", type="warning")
            return
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        scope = "all" if device_select.value == "__all__" else device_select.value
        ui.download(
            output.getvalue().encode(),
            f"{source_select.value}_{scope}_{start_input.value}_{end_input.value}.csv",
        )

    def _confirm_delete():
        if not is_admin():
            ui.notify("Only an admin can delete records.", type="negative")
            return
        source = READINGS_SOURCES[source_select.value]
        count = sel["total"]
        if count == 0:
            ui.notify("Nothing to delete — run Preview first.", type="warning")
            return

        with ui.dialog() as dlg, ui.card():
            ui.label(
                f"Permanently delete {count:,} rows from {source['label']} "
                f"for {_scope_label(source)} between {start_input.value} and "
                f"{end_input.value}?"
            ).classes("text-body1")
            ui.label("This cannot be undone.").classes("text-caption text-negative")
            with ui.row().classes("justify-end gap-2 w-full"):
                ui.button(
                    "Download CSV first", icon="download", on_click=_download
                ).props("flat")
                ui.button("Cancel", on_click=dlg.close).props("flat")
                ui.button("Delete", color="negative", on_click=lambda: _do_delete(dlg))

        dlg.open()

    def _do_delete(dlg):
        dlg.close()
        if not is_admin():
            ui.notify("Only an admin can delete records.", type="negative")
            return
        source = READINGS_SOURCES[source_select.value]
        module = source["module"]
        end_ts = _normalize_end_ts(end_input.value)
        deleted = 0
        for dev_id in _target_ids(source):
            try:
                kwargs = {"start_ts": start_input.value, "end_ts": end_ts}
                if source["has_relay"] and relay_select.value is not None:
                    kwargs["relay_number"] = relay_select.value
                deleted += module.delete_device_readings(dev_id, **kwargs)
            except Exception as e:
                logger.warning(f"Failed to delete for device {dev_id}: {e}")
        ui.notify(f"Deleted {deleted:,} rows", type="positive")
        _preview()

    with preview_container:
        ui.label("Choose a source, device, and date range, then Preview.").classes(
            "text-muted p-4"
        )
