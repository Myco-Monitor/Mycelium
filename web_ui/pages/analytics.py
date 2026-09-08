"""
Analytics page for Mycelium NiceGUI application.

Three tabs, each answering a different question:
- Reports: how did the period go — a fixed summary for a room or device set
  (web_ui.pages.analytics_reports, imported lazily since it reuses the
  helpers below)
- Explore: what exactly happened — free-form charts of raw readings from any
  readings table, one source at a time
- Data: take the rows with you — preview, download CSV, and (admin) delete
  raw readings
No code execution.
"""

import csv
import io
import logging
from datetime import datetime, timedelta

import plotly.graph_objects as go
from nicegui import ui, app

from web_ui.layout import page_layout, back_to_dashboard
from web_ui.theme import get_colors, chart_layout
from web_ui.format import to_user_dt
from api.services.report_service import (
    MAX_SAMPLE_GAP_S,
    relay_label,
    relay_on_intervals,
)

from storage.tables import (
    readings_spore,
    readings_hyphae,
    readings_pressure,
    readings_weather,
    readings_sentinel,
    device_spore,
    device_hyphae,
    device_sentinel,
    relay_settings,
)

logger = logging.getLogger("web_ui.analytics")


# -- Readings source registry -------------------------------------------------
# One entry per readings table, mapping it to its storage module, the device
# list it is keyed to, and the numeric columns worth graphing. Both the Explore
# and Data panels drive off this so there is a single code path instead of
# five near-duplicates.
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

# Explicit large cap for Explore/Data queries — get_device_readings defaults
# to limit=100, which would silently truncate a real range.
READINGS_QUERY_LIMIT = 100_000

# Cap on rows rendered into the preview table (the true total still drives the
# count label, CSV download, and delete).
PREVIEW_ROW_CAP = 500

# Series colours: one per device in the Reports cards (selection order), one
# per metric or relay in the Explore / relay charts. Material 400 hues,
# readable on the dark template.
SERIES_PALETTE = ["#ef5350", "#42a5f5", "#66bb6a", "#ffa726", "#ab47bc", "#26c6da"]


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


# -- Chart builders -----------------------------------------------------------


def _chart_ts(value):
    """Convert a stored (naive UTC) timestamp to a naive user-local datetime.

    Plotly renders naive datetimes as-is, so charts show the user's timezone.
    """
    dt = to_user_dt(value)
    return dt.replace(tzinfo=None) if dt else value


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
    """Analytics page with Reports, Explore, and Data tabs."""
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

    # Reports filter state (the dates survive an Apply so the pickers keep them)
    state = {
        "start_date": default_start,
        "end_date": default_end,
    }

    # Lazy: analytics_reports reuses this module's helpers, so importing it at
    # module level would be circular.
    from web_ui.pages.analytics_reports import _build_reports_panel

    # ---- Main tabs ----------------------------------------------------------

    with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-4"):
        ui.label("Analytics").classes("text-h4")

        with ui.tabs().classes("w-full") as main_tabs:
            reports_tab = ui.tab("Reports", icon="summarize")
            explore_tab = ui.tab("Explore", icon="show_chart")
            data_tab = ui.tab("Data", icon="table_rows")

        # Each tab opens with one line saying what it is for, so the three
        # stay distinct: a fixed period summary, free-form charts, raw rows
        with ui.tab_panels(main_tabs, value=reports_tab).classes("w-full"):
            with ui.tab_panel(reports_tab):
                _tab_caption(
                    "How did the period go — a fixed summary for a room or "
                    "a set of devices"
                )
                _build_reports_panel(analytics, rooms, state, colors)

            with ui.tab_panel(explore_tab):
                _tab_caption(
                    "What exactly happened — free-form charts of raw readings, "
                    "one source at a time"
                )
                _build_explore_panel(colors)

            with ui.tab_panel(data_tab):
                _tab_caption(
                    "Take the rows with you — preview, download CSV, and delete "
                    "raw readings from any table"
                )
                _build_data_panel(colors)


def _tab_caption(text: str):
    """One-line purpose statement under a tab header."""
    ui.label(text).classes("text-caption text-muted")


# -- Shared filter-bar helpers (all three tabs) --------------------------------


def _date_picker(label: str, value: str):
    """Build a date input with a calendar popup; returns the ui.input."""
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


def _spore_relay_bands(device_id, start, end):
    """Relay ON stretches of the Hyphae serving a Spore, for shading its chart.

    None when the Spore has no linked Hyphae (or the lookup fails); else one
    entry per relay that was ever on in the range: {relay_number, label,
    intervals: [(start, end)]} with naive user-local datetimes, ready for
    the chart. Test pulses are excluded and an ON run ends at the last
    sample before an offline gap.
    """
    try:
        dev = device_spore.get_device_spore(device_id)
        hyphae_id = dev.get("hyphae_id") if dev else None
        if not hyphae_id:
            return None
        names = {
            r["relay_number"]: r.get("relay_name")
            for r in relay_settings.get_device_relay_settings(hyphae_id)
        }
        edges = readings_hyphae.get_relay_edges(
            hyphae_id, start or "", _normalize_end_ts(end) or "9999", MAX_SAMPLE_GAP_S
        )
    except Exception as e:
        logger.warning(f"Failed to load relay bands for device {device_id}: {e}")
        return None
    bands = []
    for n, intervals in sorted(relay_on_intervals(edges).items()):
        if intervals:
            bands.append(
                {
                    "relay_number": n,
                    "label": relay_label(n, names.get(n)),
                    "intervals": [(_chart_ts(s), _chart_ts(e)) for s, e in intervals],
                }
            )
    return bands


# -- Explore panel ------------------------------------------------------------


def _build_metric_chart(rows, metric_specs, chart_type, colors, relay_bands=None):
    """Generic multi-metric, multi-axis chart over readings rows.

    metric_specs: list of (field, label) in selection order. Metrics with
    differing unit labels are placed on separate y-axes (up to 3). `rows`
    must already be chronological. relay_bands (see _spore_relay_bands)
    draws each relay's ON stretches as translucent bands behind the lines,
    one legend entry per relay that toggles all of its bands.
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
    # Band colours continue past the metric colours so none matches a line
    for i, band in enumerate(relay_bands or []):
        colour = palette[(len(metric_specs) + i) % len(palette)]
        for k, (x0, x1) in enumerate(band["intervals"]):
            fig.add_vrect(
                x0=x0,
                x1=x1,
                fillcolor=colour,
                opacity=0.15,
                line_width=0,
                layer="below",
                name=band["label"],
                legendgroup=f"relay{band['relay_number']}",
                showlegend=(k == 0),
            )
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


def _build_explore_panel(colors):
    """Free-form chart builder over the readings tables (no code)."""
    default_source = "readings_spore"
    src = READINGS_SOURCES[default_source]

    today = datetime.now().strftime("%Y-%m-%d")
    default_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

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

    # Chart sits under the filter bar and is rebuilt on every Generate
    chart_container = ui.column().classes("w-full gap-2")

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
            # Spore readings get the serving Hyphae's relay ON stretches
            # shaded behind them (no-op for un-linked Spores)
            bands = None
            if source_select.value == "readings_spore":
                bands = _spore_relay_bands(
                    device_id, start_input.value, end_input.value
                )
            fig = _build_metric_chart(
                rows, metric_specs, chart_type, colors, relay_bands=bands
            )
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


# -- Data panel ---------------------------------------------------------------


def _build_data_panel(colors):
    """Preview, download, and (admin-only) delete raw readings rows."""
    from web_ui.auth import is_admin

    default_source = "readings_spore"
    src = READINGS_SOURCES[default_source]

    today = datetime.now().strftime("%Y-%m-%d")
    default_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    # Row count from the last Preview; Delete refuses to run without one so the
    # confirmation can quote exactly what it is about to remove.
    sel = {"total": 0}

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
            # Download runs the same query itself — no Preview needed first
            ui.button(
                "Download CSV", icon="download", on_click=lambda: _download()
            ).props("dense outline")

    # Preview table sits under the filter bar and is rebuilt on every Preview
    preview_container = ui.column().classes("w-full gap-2")

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
        """Fetch matching rows across all target devices (chronological per device).

        Returns (rows, capped) where capped lists the device ids that hit
        READINGS_QUERY_LIMIT, so callers can warn that only their newest rows
        were fetched.
        """
        rows, capped = [], []
        for dev_id in _target_ids(source):
            try:
                got, truncated = _query_readings(
                    source,
                    dev_id,
                    start_input.value,
                    end_input.value,
                    relay=relay_select.value if source["has_relay"] else None,
                )
                rows.extend(got)
                if truncated:
                    capped.append(dev_id)
            except Exception as e:
                logger.warning(f"Failed to query device {dev_id}: {e}")
        return rows, capped

    def _cap_warning(capped):
        return (
            f"{len(capped)} device(s) hit the {READINGS_QUERY_LIMIT:,}-row cap, so "
            "only their newest rows are included — narrow the date range"
        )

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
        rows, capped = _collect_rows(source)
        sel["total"] = len(rows)

        with preview_container:
            with ui.row().classes("w-full items-center gap-3"):
                ui.label(f"{len(rows):,} rows match").classes("text-subtitle2")
                if is_admin():
                    ui.button(
                        "Delete",
                        icon="delete_forever",
                        on_click=lambda: _confirm_delete(),
                    ).props("dense color=negative outline")
            if capped:
                ui.label(_cap_warning(capped)).classes("text-caption text-warning")

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
        """Query the current filters and download every matching row as CSV."""
        source = READINGS_SOURCES[source_select.value]
        rows, capped = _collect_rows(source)
        if not rows:
            ui.notify("No rows for the selected filters", type="warning")
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
        ui.notify(f"Downloaded {len(rows):,} rows", type="positive")
        if capped:
            ui.notify(_cap_warning(capped), type="warning")

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
