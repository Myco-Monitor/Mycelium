"""
Reports tab of the Analytics page.

A fixed period summary for a room or a hand-picked device set, in this
order: per-device stats, Compliance (share of samples inside the user's own
alert thresholds), Equipment (relay run-time for the room's Hyphae), Alerts
fired in the period, a Daily summary table with CSV download, then the
comparison chart. The Harvest Analysis sub-tab is unchanged.

The tab shell and the shared helpers (date picker, chart builders,
temperature preference) live in web_ui.pages.analytics, which imports this
module lazily. All maths lives in api.services.report_service; the worker
fetch below only gathers rows and calls it.
"""

import csv
import io
import logging

from datetime import datetime, timedelta

from nicegui import ui, run

from web_ui.format import pm25_aqi_band, get_timezone_name, fmt_datetime
from web_ui.pages.analytics import (
    _build_comparison_chart,
    _build_harvest_chart,
    _date_picker,
    _device_colour,
    _temp_pref,
)
from api.services.report_service import (
    MAX_SAMPLE_GAP_S,
    METRIC_LABELS,
    alert_bounds,
    compliance_for_panel,
    daily_rows,
    parse_utc,
    relay_daily_hours,
    relay_duty,
    temp_unit,
    to_pref_temp,
    utc_bounds,
)

from storage.tables import (
    alert_history,
    alert_rules,
    device_hyphae,
    device_sentinel,
    device_spore,
    readings_hyphae,
    relay_settings,
)

logger = logging.getLogger("web_ui.analytics_reports")


# Sentinel values for the Spore / Sentinel selects: every device of that kind
# in the chosen room, or none of that kind.
PICK_ROOM = "__room__"
PICK_NONE = "__none__"

# Alerts listed in the Alerts card before it falls back to a count caption
ALERT_ROW_CAP = 200


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
                "hyphae_id": d.get("hyphae_id"),
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
    devices. The room also scopes the Equipment card (its Hyphae) and
    room-wide alert rules.
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
            # responsive; rendering happens back on the event loop. The user's
            # time zone and temperature unit are read here, on the UI side,
            # and handed to the worker (app.storage.user is not readable there).
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
                        room_select.value,
                        get_timezone_name(),
                        _temp_pref(),
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


# -- Worker-side fetch --------------------------------------------------------


def _fetch_report_data(
    analytics, start_date, end_date, devices, room_id, tz_name, temp_pref
):
    """Run every report query and computation. No UI calls — safe for run.io_bound.

    `devices` are the labelled picks; `room_id` scopes the Equipment card
    (the room's Hyphae) and room-wide alert rules. The period covers whole
    days in the user's time zone. Each block guards itself so one failing
    query leaves the rest of the report intact.
    """
    start_ts, end_ts = utc_bounds(start_date, end_date, tz_name)
    data = {
        "period": {"start": start_date, "end": end_date},
        "panels": [],
        "compliance": [],
        "equipment": [],
        "alerts": [],
        "daily": [],
        "harvests": [],
    }

    # -- Readings, stats and compliance: one panel per device -----------------
    rules = []
    try:
        rules = alert_rules.get_all_rules(enabled_only=True)
    except Exception as e:
        logger.warning(f"Failed to load alert rules: {e}")

    for dev in devices:
        panel = {"device": dev, "readings": [], "stats": None}
        try:
            if dev["source"] == "sentinel":
                panel["readings"] = analytics.get_sentinel_readings_for_period(
                    start_ts, end_ts, device_id=dev["device_id"]
                )
            else:
                panel["readings"] = analytics.get_readings_for_period(
                    start_ts, end_ts, device_id=dev["device_id"]
                )
        except Exception as e:
            logger.warning(f"Failed to load readings for {dev['label']}: {e}")

        try:
            panel["stats"] = analytics.calculate_environmental_stats(panel["readings"])
        except Exception as e:
            logger.warning(f"Failed to calculate stats for {dev['label']}: {e}")

        data["panels"].append(panel)

        try:
            data["compliance"].append(
                {
                    "device": dev,
                    "metrics": compliance_for_panel(panel["readings"], dev, rules),
                }
            )
        except Exception as e:
            logger.warning(f"Failed to score compliance for {dev['label']}: {e}")

    # -- Equipment: relay run-time of the room's Hyphae ----------------------
    hyphae = []
    if room_id is not None:
        try:
            hyphae = device_hyphae.get_all_device_hyphae(
                room_id=room_id, active_only=True
            )
        except Exception as e:
            logger.warning(f"Failed to load Hyphae for room {room_id}: {e}")
    hyphae.sort(key=lambda h: h.get("device_name") or "")

    for h in hyphae:
        name = h.get("device_name") or f"Hyphae {h['device_id']}"
        try:
            names = {
                r["relay_number"]: r.get("relay_name")
                for r in relay_settings.get_device_relay_settings(h["device_id"])
            }
            hourly = readings_hyphae.get_relay_hourly_duty(
                h["device_id"], start_ts, end_ts, MAX_SAMPLE_GAP_S
            )
            data["equipment"].append(
                {
                    "device_id": h["device_id"],
                    "name": name,
                    "relays": relay_duty(hourly, names),
                    "daily_hours": relay_daily_hours(hourly, tz_name),
                }
            )
        except Exception as e:
            logger.warning(f"Failed to compute relay duty for {name}: {e}")

    # -- Alerts triggered in the period ---------------------------------------
    # Kept when they belong to a selected sensor or a room Hyphae, or come
    # from a rule scoped to the room
    try:
        names = {(d["source"], d["device_id"]): d["name"] for d in devices}
        names.update({("hyphae", e["device_id"]): e["name"] for e in data["equipment"]})
        for alert in alert_history.get_alerts_between(*alert_bounds(start_ts, end_ts)):
            key = (alert.get("device_type"), alert.get("device_id"))
            in_room_rule = room_id is not None and alert.get("rule_room_id") == room_id
            if key not in names and not in_room_rule:
                continue
            fallback = (
                f"{alert.get('device_type') or 'device'} #{alert.get('device_id')}"
                if alert.get("device_id") is not None
                else "—"
            )
            alert["device_name"] = names.get(key, fallback)
            data["alerts"].append(alert)
        data["alerts"].reverse()  # newest first
    except Exception as e:
        logger.warning(f"Failed to load alerts for the period: {e}")

    # -- Daily table: one row per device per local day ------------------------
    # Spores get an hours column per relay that was ever on, taken from the
    # Hyphae that serves them; Sentinels sit outside the tents and get none
    for panel in data["panels"]:
        dev = panel["device"]
        try:
            rows = daily_rows(panel["readings"], dev, tz_name, temp_pref)
        except Exception as e:
            logger.warning(f"Failed to bucket daily rows for {dev['label']}: {e}")
            continue
        serving = _hyphae_for(dev, data["equipment"])
        if serving:
            active = [r for r in serving["relays"] if r["on_s"] > 0]
            for row in rows:
                hours = serving["daily_hours"].get(row["date"], {})
                for relay in active:
                    row[f"{relay['label']} (h)"] = hours.get(relay["relay_number"], 0.0)
        data["daily"].extend(rows)
    data["daily"].sort(key=lambda r: (r["date"], r["device"]))

    # -- Harvests: period-wide, unchanged --------------------------------------
    try:
        data["harvests"] = analytics.get_harvests_for_period(start_date, end_date)
    except Exception as e:
        logger.warning(f"Failed to load harvests: {e}")

    return data


def _hyphae_for(dev, equipment):
    """The Hyphae whose relays serve a Spore.

    Its linked Hyphae when that one is in the room, else the room's first
    Hyphae by name (a tent normally has one). Sentinels get none.
    """
    if dev["source"] != "spore" or not equipment:
        return None
    for h in equipment:
        if dev.get("hyphae_id") and h["device_id"] == dev["hyphae_id"]:
            return h
    return equipment[0]


# -- Rendering ----------------------------------------------------------------


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
            # Numbers first, the chart last: stats, compliance, equipment,
            # alerts, the daily table, then every device on one figure
            with ui.tab_panel(env_tab):
                _build_device_stats(panels, pref)
                _build_compliance_card(data["compliance"], pref)
                _build_equipment_card(data["equipment"])
                _build_alerts_card(data["alerts"])
                _build_daily_table(data["daily"], pref, data["period"])
                with _section_card("Trends"):
                    ui.plotly(_build_comparison_chart(panels, pref, colors)).classes(
                        "w-full"
                    )

            # -- Harvest Analysis ---------------------------------------------
            with ui.tab_panel(harvest_tab):
                _build_harvest_analysis(harvests, colors)


def _section_card(title: str, caption: str = "", badge=None):
    """A report section: full-width card with a bold title and muted caption.

    Returns the card so callers add their content with `with`.
    """
    card = ui.card().classes("w-full p-3")
    with card:
        with ui.row().classes("items-center gap-2"):
            ui.label(title).classes("text-subtitle1 text-weight-bold")
            if badge is not None:
                ui.badge(str(badge)).props("outline")
        if caption:
            ui.label(caption).classes("text-caption text-muted")
    return card


def _fmt_duration(seconds) -> str:
    """'45s', '8m', '1h 12m', '2d 3h' for a length of time in seconds."""
    s = int(round(seconds or 0))
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m"
    h, m = divmod(m, 60)
    if h < 24:
        return f"{h}h {m}m"
    d, h = divmod(h, 24)
    return f"{d}d {h}h"


# Unit suffix for a band label, per rule metric (temperature is converted)
_BAND_UNITS = {"co2": " ppm", "humidity": "%", "pm2_5": " µg/m³", "voc": "", "nox": ""}


def _band_text(entry, pref) -> str:
    """'≤ 590 ppm', '≥ 85%', '64.4–78.8 °F' — the band a metric is judged against."""
    lo, hi = entry["low"], entry["high"]
    if entry["metric"] == "temperature":
        lo, hi = to_pref_temp(lo, pref), to_pref_temp(hi, pref)
        unit = " " + temp_unit(pref)
    else:
        unit = _BAND_UNITS.get(entry["metric"], "")
    if lo is not None and hi is not None:
        return f"{lo:g}–{hi:g}{unit}"
    if hi is not None:
        return f"≤ {hi:g}{unit}"
    return f"≥ {lo:g}{unit}"


def _build_compliance_card(entries, pref):
    """Share of samples inside the user's own thresholds, per device and metric.

    A metric with no applicable rule says so; when no rule applies to any
    selected device the card points at the Alerts page instead of a grid.
    Bands come only from alert rules — there are no built-in targets.
    """
    with _section_card(
        "Compliance",
        "Share of samples inside your alert thresholds. Excursions shorter than "
        "a rule's duration are not counted.",
    ):
        if not any(m["has_rule"] for e in entries for m in e["metrics"]):
            with ui.row().classes("items-center gap-1"):
                ui.label(
                    "No threshold rules apply to the selected devices — add one on the"
                ).classes("text-muted")
                ui.link("Alerts page", "/alerts")
            return

        metrics = [
            m
            for m in METRIC_LABELS
            if any(x["metric"] == m for e in entries for x in e["metrics"])
        ]
        with (
            ui.element("div")
            .classes("w-full")
            .style(
                "display: grid; "
                f"grid-template-columns: minmax(200px, 2fr) repeat({len(metrics)}, "
                "minmax(170px, 1fr)); gap: 8px 16px; align-items: center; "
                "overflow-x: auto;"
            )
        ):
            for entry in entries:
                dev = entry["device"]
                by_metric = {x["metric"]: x for x in entry["metrics"]}
                with ui.row().classes("items-center gap-2 no-wrap"):
                    ui.label(dev["name"]).classes("text-subtitle2 text-weight-bold")
                    ui.badge(dev["source"].title()).props("outline")
                for metric in metrics:
                    x = by_metric.get(metric)
                    if x is None:
                        ui.element("div")  # the device does not measure it
                    elif not x["has_rule"]:
                        with ui.column().classes("gap-0"):
                            ui.label(METRIC_LABELS[metric]).classes(
                                "text-caption text-muted"
                            )
                            ui.label("no threshold rule").classes(
                                "text-caption text-muted"
                            )
                    elif x["pct_in_band"] is None:
                        _stat_cell(x["label"], "--", "no samples")
                    else:
                        n = x["excursions"]
                        caption = (
                            f"{n} excursion{'' if n == 1 else 's'}"
                            + (
                                f" · longest {_fmt_duration(x['longest_s'])}"
                                if n
                                else ""
                            )
                            + f" · {_band_text(x, pref)}"
                        )
                        _stat_cell(
                            x["label"], f"{x['pct_in_band']:.1f}% in band", caption
                        )


def _build_equipment_card(equipment):
    """Hours and share of time each relay of the room's Hyphae was on."""
    with _section_card(
        "Equipment",
        "Relay run-time for the room's Hyphae. Test pulses are excluded, and "
        f"gaps over {MAX_SAMPLE_GAP_S // 60} minutes (device offline) count as "
        "neither on nor off.",
    ):
        if not equipment:
            ui.label("No Hyphae in this room").classes("text-muted")
            return
        for h in equipment:
            ui.label(h["name"]).classes("text-subtitle2 text-weight-bold")
            if not h["relays"]:
                ui.label("No relay samples in the period").classes(
                    "text-caption text-muted"
                )
                continue
            with (
                ui.element("div")
                .classes("w-full")
                .style(
                    "display: grid; grid-template-columns: repeat(auto-fill, "
                    "minmax(180px, 1fr)); gap: 8px 16px;"
                )
            ):
                for relay in h["relays"]:
                    if relay["covered_s"]:
                        value = f"{relay['on_s'] / 3600:.1f} h on"
                        caption = (
                            f"{relay['pct_on'] * 100:.0f}% of "
                            f"{relay['covered_s'] / 3600:.0f} h"
                        )
                    else:
                        value, caption = "--", "no samples"
                    _stat_cell(relay["label"], value, caption)


def _build_alerts_card(alerts):
    """Alerts triggered in the period, newest first."""
    with _section_card("Alerts", badge=len(alerts)):
        if not alerts:
            ui.label("No alerts in the period").classes("text-muted")
            return

        def resolved_text(a):
            if not a.get("resolved_at"):
                return "open"
            t0, t1 = parse_utc(a.get("triggered_at")), parse_utc(a["resolved_at"])
            if t0 is None or t1 is None:
                return "resolved"
            return "after " + _fmt_duration((t1 - t0).total_seconds())

        columns = [
            {"name": "when", "label": "When", "field": "when", "align": "left"},
            {"name": "rule", "label": "Rule", "field": "rule", "align": "left"},
            {"name": "device", "label": "Device", "field": "device", "align": "left"},
            {"name": "value", "label": "Value", "field": "value", "align": "right"},
            {
                "name": "resolved",
                "label": "Resolved",
                "field": "resolved",
                "align": "left",
            },
        ]
        rows = [
            {
                "alert_id": a.get("alert_id"),
                "when": fmt_datetime(a.get("triggered_at")),
                "rule": a.get("rule_name") or "—",
                "device": a.get("device_name") or "—",
                "value": (
                    f"{a['alert_value']:.1f}"
                    if a.get("alert_value") is not None
                    else "—"
                ),
                "resolved": resolved_text(a),
            }
            for a in alerts[:ALERT_ROW_CAP]
        ]
        if len(alerts) > ALERT_ROW_CAP:
            ui.label(f"Showing the newest {ALERT_ROW_CAP} of {len(alerts)}").classes(
                "text-caption text-muted"
            )
        ui.table(columns=columns, rows=rows, row_key="alert_id").classes(
            "w-full"
        ).props("dense flat")


# Daily table metric groups: (row key prefix, column label, display format)
_DAILY_GROUPS = (
    ("co2", "CO2", "{:.0f}"),
    ("humidity", "Humidity", "{:.1f}"),
    ("temp", "Temp", "{:.1f}"),
    ("pm25", "PM2.5", "{:.1f}"),
)


def _build_daily_table(rows, pref, period):
    """One row per device per local day, with a CSV download of the same rows."""
    unit = temp_unit(pref)
    with _section_card(
        "Daily summary",
        "One row per device per day in your time zone: min / average / max of "
        f"each metric (CO2 in ppm, humidity in %, temperature in {unit}, PM2.5 "
        "in µg/m³) and hours each active relay was on.",
    ):
        if not rows:
            ui.label("No readings in the period").classes("text-muted")
            return

        ui.button(
            "Download table CSV",
            icon="download",
            on_click=lambda: _download_daily(rows, period),
        ).props("dense outline")

        has_pm = any(r.get("pm25_avg") is not None for r in rows)
        relay_keys = []  # union of relay-hour columns, first seen first
        for r in rows:
            for k in r:
                if k.endswith(" (h)") and k not in relay_keys:
                    relay_keys.append(k)

        columns = [
            {"name": "date", "label": "Date", "field": "date", "align": "left"},
            {"name": "device", "label": "Device", "field": "device", "align": "left"},
            {
                "name": "samples",
                "label": "Samples",
                "field": "samples",
                "align": "right",
            },
        ]
        for prefix, label, _fmt in _DAILY_GROUPS:
            if prefix == "pm25" and not has_pm:
                continue
            for stat in ("min", "avg", "max"):
                key = f"{prefix}_{stat}"
                columns.append(
                    {
                        "name": key,
                        "label": f"{label} {stat}",
                        "field": key,
                        "align": "right",
                    }
                )
        for k in relay_keys:
            columns.append({"name": k, "label": k, "field": k, "align": "right"})

        def cell(value, fmt):
            return fmt.format(value) if value is not None else "—"

        display = []
        for r in rows:
            d = {
                "key": f"{r['date']}|{r['source']}:{r['device_id']}",
                "date": r["date"],
                "device": r["device"],
                "samples": f"{r['samples']:,}",
            }
            for prefix, _label, fmt in _DAILY_GROUPS:
                for stat in ("min", "avg", "max"):
                    key = f"{prefix}_{stat}"
                    d[key] = cell(r.get(key), fmt)
            for k in relay_keys:
                d[k] = cell(r.get(k), "{:.2f}")
            display.append(d)

        ui.table(columns=columns, rows=display, row_key="key", pagination=31).classes(
            "w-full"
        ).props("dense flat")


def _download_daily(rows, period):
    """CSV of the daily rows exactly as computed (floats rounded to 2 places)."""
    if not rows:
        ui.notify("No daily rows to download", type="warning")
        return
    fieldnames = []
    for r in rows:
        for k in r:
            if k not in fieldnames:
                fieldnames.append(k)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, restval="")
    writer.writeheader()
    for r in rows:
        writer.writerow(
            {k: round(v, 2) if isinstance(v, float) else v for k, v in r.items()}
        )
    ui.download(
        output.getvalue().encode(),
        f"report_daily_{period['start']}_{period['end']}.csv",
    )


# -- Device stats and harvest (pre-existing sections) -------------------------


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
    """One metric cell of a stats grid: label, bold value, caption."""
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
