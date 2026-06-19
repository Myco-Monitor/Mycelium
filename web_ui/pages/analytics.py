"""
Analytics page for Mycelium NiceGUI application.

Merges the dashboard analytics (pre-built charts) and notebook interface
(interactive code cells) into a single tabbed page.
"""

import csv
import io
import logging
from datetime import datetime, timedelta

import plotly.graph_objects as go
from nicegui import ui, app

from web_ui.layout import page_layout, back_to_dashboard
from web_ui.theme import get_colors

logger = logging.getLogger("web_ui.analytics")


# -- Notebook state ----------------------------------------------------------


def _default_cells():
    """Return the default notebook cells list."""
    return [{"id": 1, "code": "# Start here\n", "output": ""}]


def _get_cells():
    """Get notebook cells from user storage."""
    stored = app.storage.user.get("notebook_cells")
    if stored:
        return stored
    cells = _default_cells()
    app.storage.user["notebook_cells"] = cells
    return cells


def _save_cells(cells):
    """Persist notebook cells to user storage."""
    app.storage.user["notebook_cells"] = cells


def _next_cell_id(cells):
    """Return the next available cell ID."""
    return max(c["id"] for c in cells) + 1 if cells else 1


def execute_code_cell(code: str) -> str:
    """
    Placeholder code execution.

    Returns the code as-is. A real implementation would run the code
    against the database and return formatted results.
    """
    if not code.strip():
        return "(empty cell)"
    return code


# -- Chart builders -----------------------------------------------------------


def _build_env_trends_chart(readings, colors):
    """Build a plotly time-series chart for environmental trends."""
    if not readings:
        return _empty_figure("No environmental data for selected period")

    timestamps = [r.get("timestamp", "") for r in readings]
    co2 = [r.get("co2") for r in readings]
    temp = [r.get("temperature") for r in readings]
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
            name="Temp (C)",
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
        yaxis2=dict(title="Temp (C)", side="right", overlaying="y", showgrid=False),
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


def _build_hourly_chart(hourly_data, field, title, color):
    """Build a plotly chart for hourly pattern data."""
    if not hourly_data:
        return _empty_figure(f"No hourly {title.lower()} data")

    hours = [h.get("hour", 0) for h in hourly_data]
    values = [h.get(field, 0) or 0 for h in hourly_data]
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
    """Combined analytics page with Dashboard and Notebook tabs."""
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
            notebook_tab = ui.tab("Notebook", icon="code")

        with ui.tab_panels(main_tabs, value=dashboard_tab).classes("w-full"):
            # ==============================================================
            # DASHBOARD TAB
            # ==============================================================
            with ui.tab_panel(dashboard_tab):
                _build_dashboard_panel(analytics, rooms, state, colors)

            # ==============================================================
            # NOTEBOOK TAB
            # ==============================================================
            with ui.tab_panel(notebook_tab):
                _build_notebook_panel(colors)


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
    with ui.row().classes("w-full gap-3 flex-wrap q-mb-md"):
        if stats:
            _stat_card("Avg CO2", f"{stats.co2_mean:.0f} ppm", "co2", colors)
            _stat_card("Avg Temp", f"{stats.temp_mean:.1f} C", "thermostat", colors)
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
        fig = _build_env_trends_chart(readings, colors)
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
            fig = _build_hourly_chart(hourly, "avg_temp", "Temp (C)", "#42a5f5")
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


# -- Notebook panel -----------------------------------------------------------


def _build_notebook_panel(colors):
    """Construct the notebook tab contents."""
    cells = _get_cells()

    @ui.refreshable
    def notebook_cells():
        for idx, cell in enumerate(cells):
            _render_cell(cell, idx, cells, notebook_cells)

    # Toolbar
    with ui.card().classes("w-full p-3"):
        with ui.row().classes("gap-2 flex-wrap"):

            def _run_all():
                for cell in cells:
                    cell["output"] = execute_code_cell(cell["code"])
                _save_cells(cells)
                notebook_cells.refresh()

            ui.button("Run All Cells", icon="play_arrow", on_click=_run_all).props(
                "dense"
            )

            def _add_cell():
                cells.append({"id": _next_cell_id(cells), "code": "", "output": ""})
                _save_cells(cells)
                notebook_cells.refresh()

            ui.button("Add Cell", icon="add", on_click=_add_cell).props("dense outline")

            def _save_nb():
                _save_cells(cells)
                ui.notify("Notebook saved", type="positive")

            ui.button("Save Notebook", icon="save", on_click=_save_nb).props(
                "dense outline"
            )

            def _clear_all():
                cells.clear()
                cells.extend(_default_cells())
                _save_cells(cells)
                notebook_cells.refresh()

            ui.button("Clear All", icon="delete_sweep", on_click=_clear_all).props(
                "dense outline color=negative"
            )

    # Cells area
    notebook_cells()

    # Quick reference card
    with ui.card().classes("w-full p-4 q-mt-md"):
        ui.label("Database Quick Reference").classes(
            "text-subtitle1 text-weight-bold q-mb-sm"
        )
        ui.label(
            "Common functions and key tables for querying the Mycelium database."
        ).classes("text-caption text-muted q-mb-md")

        with ui.row().classes("w-full gap-4 flex-wrap"):
            with ui.column().classes("flex-1 min-w-64"):
                ui.label("Key Tables").classes(
                    "text-subtitle2 text-weight-bold q-mb-xs"
                )
                _ref_items(
                    [
                        (
                            "readings_spore",
                            "Sensor readings (co2, temp, humidity, reading_ts)",
                        ),
                        (
                            "device_spore",
                            "Spore devices (device_id, device_name, room_id)",
                        ),
                        (
                            "device_hyphae",
                            "Hyphae controllers (device_id, device_name)",
                        ),
                        ("grow_rooms", "Grow rooms (room_id, room_name, farm_id)"),
                        (
                            "harvest",
                            "Harvest records (harvest_id, harvest_ts, total_wt)",
                        ),
                        ("bulk", "Bulk substrates (bulk_id, bulk_name, room_id)"),
                    ]
                )

            with ui.column().classes("flex-1 min-w-64"):
                ui.label("Common Queries").classes(
                    "text-subtitle2 text-weight-bold q-mb-xs"
                )
                _ref_code_items(
                    [
                        'SELECT AVG(co2), AVG(temp) FROM readings_spore WHERE reading_ts >= date("now", "-7 days")',
                        "SELECT room_name, COUNT(*) FROM grow_rooms gr JOIN device_spore ds ON gr.room_id = ds.room_id GROUP BY room_name",
                        "SELECT DATE(harvest_ts) as day, SUM(total_wt) FROM harvest GROUP BY day ORDER BY day DESC LIMIT 10",
                    ]
                )

            with ui.column().classes("flex-1 min-w-64"):
                ui.label("Service Functions").classes(
                    "text-subtitle2 text-weight-bold q-mb-xs"
                )
                _ref_items(
                    [
                        (
                            "analytics.get_readings_for_period(start, end, room_id)",
                            "Fetch readings",
                        ),
                        (
                            "analytics.calculate_environmental_stats(readings)",
                            "Compute stats",
                        ),
                        (
                            "analytics.get_harvests_for_period(start, end, room_id)",
                            "Fetch harvests",
                        ),
                        (
                            "analytics.get_hourly_pattern(start, end, room_id)",
                            "Hourly averages",
                        ),
                        (
                            "analytics.generate_insights(start, end, room_id)",
                            "Auto insights",
                        ),
                    ]
                )


def _render_cell(cell, idx, cells, refresh_fn):
    """Render a single notebook cell."""
    with ui.card().classes("w-full q-mb-sm"):
        with ui.row().classes("items-center justify-between p-2"):
            ui.label(f"Cell {idx + 1}").classes(
                "text-caption text-weight-bold text-muted"
            )
            with ui.row().classes("gap-1"):

                def _run_cell(c=cell):
                    c["output"] = execute_code_cell(c["code"])
                    _save_cells(cells)
                    refresh_fn.refresh()

                ui.button(icon="play_arrow", on_click=_run_cell).props(
                    "flat dense size=sm color=positive"
                )

                def _delete_cell(c=cell):
                    cells.remove(c)
                    if not cells:
                        cells.extend(_default_cells())
                    _save_cells(cells)
                    refresh_fn.refresh()

                ui.button(icon="delete", on_click=_delete_cell).props(
                    "flat dense size=sm color=negative"
                )

        # Code input
        ui.textarea(
            value=cell["code"],
            on_change=lambda e, c=cell: c.update(code=e.value),
        ).classes("w-full").props('outlined dense input-style="font-family: monospace"')

        # Output area
        if cell.get("output"):
            with (
                ui.card()
                .classes("w-full q-mt-xs p-2")
                .style(
                    "background-color: rgba(0,0,0,0.15); border-left: 3px solid grey;"
                )
            ):
                ui.label("Output:").classes("text-caption text-muted")
                ui.html(
                    f'<pre style="white-space: pre-wrap; margin: 0; font-family: monospace;">'
                    f"{cell['output']}</pre>"
                )


def _ref_items(items):
    """Render a list of reference items (name + description)."""
    for name, desc in items:
        with ui.row().classes("items-start gap-2 q-mb-xs"):
            ui.label(name).classes("text-caption text-weight-bold").style(
                "font-family: monospace"
            )
            ui.label(desc).classes("text-caption text-muted")


def _ref_code_items(items):
    """Render a list of code snippet reference items."""
    for code in items:
        ui.html(
            f'<pre style="white-space: pre-wrap; margin: 0 0 8px 0; font-family: monospace; '
            f'font-size: 0.8em; padding: 6px; background: rgba(0,0,0,0.1); border-radius: 4px;">'
            f"{code}</pre>"
        )
