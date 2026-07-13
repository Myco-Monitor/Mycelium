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
from nicegui import ui, app

from web_ui.layout import page_layout, back_to_dashboard
from web_ui.theme import get_colors

from storage.tables import (
    readings_spore,
    readings_hyphae,
    readings_pressure,
    readings_weather,
    device_spore,
    device_hyphae,
)

logger = logging.getLogger("web_ui.analytics")


# -- Readings source registry -------------------------------------------------
# One entry per readings table, mapping it to its storage module, the device
# list it is keyed to, and the numeric columns worth graphing. Both the Graph
# Builder and Records panels drive off this so there is a single code path
# instead of four near-duplicates.
#
# Call convention: get_device_readings / delete_device_readings take the device
# id as the FIRST POSITIONAL arg in every module (spore/weather/hyphae name it
# device_id, pressure names it hyphae_id), so always pass it positionally. For
# readings_hyphae, relay_number is keyword-defaulted None, so the same call
# shape works without special-casing. The timestamp column is `reading_ts` in
# all four tables, returned ORDER BY reading_ts DESC.

READINGS_SOURCES = {
    "readings_spore": {
        "label": "Spore Sensor Readings",
        "module": readings_spore,
        "device_fn": lambda: device_spore.get_all_device_spore(active_only=True),
        "metrics": {"co2": "CO2 (ppm)", "temp": "Temp", "humidity": "Humidity (%)"},
        "has_relay": False,
    },
    "readings_weather": {
        "label": "Weather Readings",
        "module": readings_weather,
        "device_fn": lambda: device_spore.get_all_device_spore(active_only=True),
        "metrics": {
            "current_temp": "Temp",
            "feels_like": "Feels Like",
            "humidity": "Humidity (%)",
            "ambient_pressure": "Pressure (hPa)",
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


def _build_env_trends_chart(readings, colors, temp_pref="C"):
    """Build a plotly time-series chart for environmental trends."""
    if not readings:
        return _empty_figure("No environmental data for selected period")

    temp_unit = _temp_unit(temp_pref)
    timestamps = [r.get("timestamp", "") for r in readings]
    co2 = [r.get("co2") for r in readings]
    temp = [_to_pref_temp(r.get("temperature"), temp_pref) for r in readings]
    humidity = [r.get("humidity") for r in readings]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=timestamps, y=co2, name="CO2 (ppm)", yaxis="y", line=dict(color="#ef5350")
        )
    )
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=temp,
            name=f"Temp ({temp_unit})",
            yaxis="y2",
            line=dict(color="#42a5f5"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=humidity,
            name="Humidity (%)",
            yaxis="y3",
            line=dict(color="#66bb6a"),
        )
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=60, r=60, t=30, b=40),
        legend=dict(orientation="h", y=1.12),
        xaxis=dict(title="Time"),
        yaxis=dict(title="CO2 (ppm)", side="left"),
        yaxis2=dict(
            title=f"Temp ({temp_unit})", side="right", overlaying="y", showgrid=False
        ),
        yaxis3=dict(
            title="Humidity (%)",
            side="right",
            overlaying="y",
            anchor="free",
            position=0.95,
            showgrid=False,
        ),
    )
    return fig


def _build_harvest_chart(harvests, colors):
    """Build a plotly bar chart for harvest data."""
    if not harvests:
        return _empty_figure("No harvest data for selected period")

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
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=60, r=20, t=30, b=40),
        xaxis=dict(title="Harvest Date"),
        yaxis=dict(title="Yield (g)"),
    )
    return fig


def _build_hourly_chart(hourly_data, field, title, color, value_transform=None):
    """Build a plotly chart for hourly pattern data.

    value_transform, if given, maps each raw value (e.g. Celsius -> the user's
    preferred temperature unit) before plotting.
    """
    if not hourly_data:
        return _empty_figure(f"No hourly {title.lower()} data")

    hours = [h.get("hour", 0) for h in hourly_data]
    values = [h.get(field, 0) or 0 for h in hourly_data]
    if value_transform:
        values = [value_transform(v) for v in values]
    hour_labels = [f"{h:02d}:00" for h in hours]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=hour_labels,
            y=values,
            name=title,
            mode="lines+markers",
            fill="tozeroy",
            line=dict(color=color),
            fillcolor=color.replace(")", ", 0.15)").replace("rgb", "rgba")
            if color.startswith("rgb")
            else color,
        )
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=50, r=20, t=30, b=40),
        xaxis=dict(title="Hour of Day"),
        yaxis=dict(title=title),
        showlegend=False,
    )
    return fig


def _empty_figure(message: str):
    """Create an empty plotly figure with a centered message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=16, color="grey"),
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
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

    # Shared filter state
    state = {
        "start_date": default_start,
        "end_date": default_end,
        "room_id": None,
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


def _build_dashboard_panel(analytics, rooms, state, colors):
    """Construct the dashboard tab contents."""

    # Containers that get refreshed when filters change
    content_container = ui.column().classes("w-full gap-4")

    # -- Filter bar -----------------------------------------------------------
    with ui.card().classes("w-full p-3"):
        with ui.row().classes("w-full items-end gap-3 flex-wrap"):
            # Start date
            with ui.input("Start Date", value=state["start_date"]).classes(
                "w-40"
            ) as start_input:
                with ui.menu().props("no-parent-event") as start_menu:
                    with ui.date().bind_value(start_input):
                        pass
                with start_input.add_slot("append"):
                    ui.icon("edit_calendar").on("click", start_menu.open).classes(
                        "cursor-pointer"
                    )

            # End date
            with ui.input("End Date", value=state["end_date"]).classes(
                "w-40"
            ) as end_input:
                with ui.menu().props("no-parent-event") as end_menu:
                    with ui.date().bind_value(end_input):
                        pass
                with end_input.add_slot("append"):
                    ui.icon("edit_calendar").on("click", end_menu.open).classes(
                        "cursor-pointer"
                    )

            # Room selector
            room_options = {None: "All Rooms"}
            for r in rooms:
                room_options[r["room_id"]] = r["room_name"]
            room_select = ui.select(room_options, value=None, label="Room").classes(
                "w-40"
            )

            # Quick range buttons
            def _set_quick_range(days):
                end_val = state["end_date"]
                new_start = (
                    datetime.strptime(end_val, "%Y-%m-%d") - timedelta(days=days)
                ).strftime("%Y-%m-%d")
                start_input.set_value(new_start)
                _apply_filters()

            with ui.row().classes("gap-1"):
                for label, days in [("7d", 7), ("30d", 30), ("90d", 90), ("1y", 365)]:
                    ui.button(label, on_click=lambda d=days: _set_quick_range(d)).props(
                        "flat dense size=sm"
                    )

            # Apply button
            def _apply_filters():
                state["start_date"] = start_input.value or state["start_date"]
                state["end_date"] = end_input.value or state["end_date"]
                state["room_id"] = room_select.value
                _refresh_dashboard(analytics, state, colors, content_container)

            ui.button("Apply", icon="refresh", on_click=_apply_filters).props("dense")

            # Export CSV
            def _export_csv():
                try:
                    readings = analytics.get_readings_for_period(
                        state["start_date"], state["end_date"], state["room_id"]
                    )
                    if not readings:
                        ui.notify("No data to export", type="warning")
                        return
                    output = io.StringIO()
                    writer = csv.DictWriter(output, fieldnames=readings[0].keys())
                    writer.writeheader()
                    writer.writerows(readings)
                    ui.download(
                        output.getvalue().encode(),
                        f"analytics_{state['start_date']}_{state['end_date']}.csv",
                    )
                except Exception as e:
                    ui.notify(f"Export failed: {e}", type="negative")

            ui.button("Export CSV", icon="download", on_click=_export_csv).props(
                "dense outline"
            )

    # Initial load
    _refresh_dashboard(analytics, state, colors, content_container)


def _refresh_dashboard(analytics, state, colors, container):
    """Clear and rebuild the dashboard content area."""
    container.clear()

    start = state["start_date"]
    end = state["end_date"]
    room_id = state["room_id"]

    # Fetch data
    readings = []
    harvests = []
    hourly = []
    stats = None
    insights = []

    try:
        readings = analytics.get_readings_for_period(start, end, room_id)
    except Exception as e:
        logger.warning(f"Failed to load readings: {e}")

    try:
        stats = analytics.calculate_environmental_stats(readings)
    except Exception as e:
        logger.warning(f"Failed to calculate stats: {e}")

    try:
        harvests = analytics.get_harvests_for_period(start, end, room_id)
    except Exception as e:
        logger.warning(f"Failed to load harvests: {e}")

    try:
        hourly = analytics.get_hourly_pattern(start, end, room_id)
    except Exception as e:
        logger.warning(f"Failed to load hourly data: {e}")

    try:
        insights = analytics.generate_insights(start, end, room_id)
    except Exception as e:
        logger.warning(f"Failed to generate insights: {e}")

    with container:
        # Sub-tabs
        with ui.tabs().classes("w-full") as sub_tabs:
            env_tab = ui.tab("Environmental Trends", icon="thermostat")
            harvest_tab = ui.tab("Harvest Analysis", icon="grass")
            pattern_tab = ui.tab("Daily Patterns", icon="schedule")
            insight_tab = ui.tab("Insights", icon="lightbulb")

        with ui.tab_panels(sub_tabs, value=env_tab).classes("w-full"):
            # -- Environmental Trends -----------------------------------------
            with ui.tab_panel(env_tab):
                _build_env_trends(stats, readings, colors)

            # -- Harvest Analysis ---------------------------------------------
            with ui.tab_panel(harvest_tab):
                _build_harvest_analysis(harvests, colors)

            # -- Daily Patterns -----------------------------------------------
            with ui.tab_panel(pattern_tab):
                _build_daily_patterns(hourly, colors)

            # -- Insights -----------------------------------------------------
            with ui.tab_panel(insight_tab):
                _build_insights(insights, colors)


# -- Dashboard sub-sections ---------------------------------------------------


def _stat_card(label, value, icon, colors):
    """Render a small stat card."""
    with ui.card().classes("p-3 flex-1 min-w-48"):
        with ui.row().classes("items-center gap-2"):
            ui.icon(icon, size="sm").style(f"color: {colors['primary']}")
            ui.label(label).classes("text-caption text-muted")
        ui.label(str(value)).classes("text-h5 q-mt-xs")


def _build_env_trends(stats, readings, colors):
    """Environmental Trends sub-tab content."""
    pref = _temp_pref()
    unit = _temp_unit(pref)
    with ui.row().classes("w-full gap-3 flex-wrap q-mb-md"):
        if stats:
            avg_temp = _to_pref_temp(stats.temp_mean, pref)
            temp_text = f"{avg_temp:.1f} {unit}" if avg_temp is not None else "--"
            _stat_card("Avg CO2", f"{stats.co2_mean:.0f} ppm", "co2", colors)
            _stat_card("Avg Temp", temp_text, "thermostat", colors)
            _stat_card(
                "Avg Humidity", f"{stats.humidity_mean:.1f}%", "water_drop", colors
            )
            _stat_card("Data Points", f"{stats.data_points:,}", "data_usage", colors)
        else:
            _stat_card("Avg CO2", "--", "co2", colors)
            _stat_card("Avg Temp", "--", "thermostat", colors)
            _stat_card("Avg Humidity", "--", "water_drop", colors)
            _stat_card("Data Points", "0", "data_usage", colors)

    with ui.card().classes("w-full p-3"):
        ui.label("Environmental Trends").classes(
            "text-subtitle1 text-weight-bold q-mb-sm"
        )
        fig = _build_env_trends_chart(readings, colors, pref)
        ui.plotly(fig).classes("w-full").style("height: 400px")


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


def _build_daily_patterns(hourly, colors):
    """Daily Patterns sub-tab content."""
    with ui.row().classes("w-full gap-3 flex-wrap"):
        with ui.card().classes("flex-1 min-w-72 p-3"):
            ui.label("CO2 Hourly Pattern").classes(
                "text-subtitle1 text-weight-bold q-mb-sm"
            )
            fig = _build_hourly_chart(hourly, "avg_co2", "CO2 (ppm)", "#ef5350")
            ui.plotly(fig).classes("w-full").style("height: 300px")

        with ui.card().classes("flex-1 min-w-72 p-3"):
            ui.label("Temperature Hourly Pattern").classes(
                "text-subtitle1 text-weight-bold q-mb-sm"
            )
            pref = _temp_pref()
            fig = _build_hourly_chart(
                hourly,
                "avg_temp",
                f"Temp ({_temp_unit(pref)})",
                "#42a5f5",
                value_transform=(lambda c: _to_pref_temp(c, pref)),
            )
            ui.plotly(fig).classes("w-full").style("height: 300px")

        with ui.card().classes("flex-1 min-w-72 p-3"):
            ui.label("Humidity Hourly Pattern").classes(
                "text-subtitle1 text-weight-bold q-mb-sm"
            )
            fig = _build_hourly_chart(hourly, "avg_humidity", "Humidity (%)", "#66bb6a")
            ui.plotly(fig).classes("w-full").style("height: 300px")


def _build_insights(insights, colors):
    """Insights sub-tab content."""
    if not insights:
        with ui.card().classes("w-full p-4"):
            ui.label("No insights available for the selected period.").classes(
                "text-muted"
            )
            ui.label(
                "Try expanding the date range or checking that devices are reporting data."
            ).classes("text-caption text-muted q-mt-sm")
        return

    insight_icons = {
        "success": ("check_circle", "positive"),
        "warning": ("warning", "warning"),
        "info": ("info", "info"),
        "danger": ("error", "negative"),
    }

    for insight in insights:
        icon, badge_type = insight_icons.get(insight.type, ("info", "info"))
        with ui.card().classes("w-full p-4 q-mb-sm"):
            with ui.row().classes("items-start gap-3"):
                ui.icon(icon, size="sm").props(f"color={badge_type}")
                with ui.column().classes("gap-1 flex-1"):
                    ui.label(insight.title).classes("text-subtitle1 text-weight-bold")
                    ui.label(insight.message).classes("text-body2")
                    with ui.row().classes("items-center gap-2 q-mt-xs"):
                        ui.badge(insight.metric.upper()).props(
                            f"color={badge_type} outline"
                        )
                        ui.label(insight.action).classes("text-caption text-muted")


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
    """{device_id: device_name} options for a source's device list."""
    options = {}
    try:
        for d in source["device_fn"]():
            options[d["device_id"]] = d.get("device_name") or f"Device {d['device_id']}"
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
        return _empty_figure("No data for selected filters")

    x = [r.get("reading_ts", "") for r in rows]
    palette = ["#ef5350", "#42a5f5", "#66bb6a", "#ffa726", "#ab47bc", "#26c6da"]

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
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
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
        return _empty_figure("No data for selected filters")
    palette = ["#ef5350", "#42a5f5", "#66bb6a", "#ffa726", "#ab47bc", "#26c6da"]
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
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
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
