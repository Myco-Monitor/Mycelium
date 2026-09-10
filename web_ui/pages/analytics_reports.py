"""
Reports tab of the Analytics page.

A fixed period summary for a room or a hand-picked device set, in this
order: per-device stats, Compliance (share of samples inside the user's own
alert thresholds), Equipment (relay run-time for the room's Hyphae), Alerts
fired in the period, a Daily summary table with CSV download, then three
insight cards: Control response (how the room's readings react to each
relay), Room comparison (the room against a baseline Sentinel) and Sensor
agreement (Spore pairs and per-device anomalies). The Harvest Analysis
sub-tab is unchanged.

The tab shell and the shared helpers (date picker, chart helpers,
temperature preference) live in web_ui.pages.analytics, which imports this
module lazily. All maths lives in api.services.report_service; the worker
fetch below only gathers rows and calls it.
"""

import bisect
import csv
import io
import itertools
import logging

from datetime import datetime, timedelta

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from nicegui import ui, run

from web_ui.format import pm25_aqi_band, get_timezone_name, fmt_datetime
from web_ui.theme import chart_layout
from web_ui.pages.analytics import (
    SERIES_PALETTE,
    _build_harvest_chart,
    _date_picker,
    _device_colour,
    _relay_colour,
    _temp_pref,
)
from api.services.report_service import (
    AGREEMENT_MAX_PAIRS,
    AGREEMENT_THRESHOLDS,
    ANOMALY_MAX_INTERVALS,
    ANOMALY_Z,
    MAX_SAMPLE_GAP_S,
    METRIC_LABELS,
    NO_RESPONSE_FLOOR,
    RECOVERY_MIN_DATA_MIN,
    RESPONSE_POST_MIN,
    XCORR_DETREND_MIN,
    alert_bounds,
    baseline_candidates,
    compliance_for_panel,
    control_response,
    daily_hours_vs_means,
    daily_rows,
    device_anomalies,
    lag_xcorr,
    mean_frame,
    pair_agreement,
    parse_utc,
    pool_responses,
    readings_frame,
    relay_daily_hours,
    relay_duty,
    relay_events,
    relay_label,
    room_baseline_diff,
    temp_delta_to_pref,
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
    grow_rooms,
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
        "control": {"reason": "not computed"},
        "comparison": {"reason": "not computed"},
        "agreement": {"reason": "not computed"},
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

    # -- Insight cards: every device on a 1-minute grid, then three blocks ----
    # Each block returns {"reason": str} when its inputs do not exist for the
    # selection, and a failure inside one degrades to a reason as well
    frames = {}
    for panel in data["panels"]:
        dev = panel["device"]
        try:
            frames[(dev["source"], dev["device_id"])] = readings_frame(
                panel["readings"]
            )
        except Exception as e:
            logger.warning(f"Failed to grid readings for {dev['label']}: {e}")

    try:
        data["control"] = _control_block(
            room_id,
            hyphae,
            data["equipment"],
            data["panels"],
            frames,
            data["daily"],
            start_ts,
            end_ts,
        )
    except Exception as e:
        logger.warning(f"Failed to build the control response card: {e}")
        data["control"] = {"reason": "could not be computed (see the log)"}

    try:
        data["comparison"] = _comparison_block(
            analytics, room_id, data["panels"], frames, start_ts, end_ts, tz_name
        )
    except Exception as e:
        logger.warning(f"Failed to build the room comparison card: {e}")
        data["comparison"] = {"reason": "could not be computed (see the log)"}

    try:
        data["agreement"] = _agreement_block(data["panels"], frames, tz_name)
    except Exception as e:
        logger.warning(f"Failed to build the sensor agreement card: {e}")
        data["agreement"] = {"reason": "could not be computed (see the log)"}

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


def _control_block(room_id, hyphae, equipment, panels, frames, daily, start_ts, end_ts):
    """Relay events of the room's Hyphae against the Spores they serve.

    Responses are computed for every (Hyphae, room Spore) pair; the card
    decides which un-linked Spores appear under which Hyphae (a Spore linked
    to a Hyphae outside the room counts as un-linked here, as in _hyphae_for).
    """
    if room_id is None:
        return {"reason": "pick a room"}
    if not hyphae:
        return {"reason": "no Hyphae in this room"}
    if not equipment:
        return {"reason": "relay data for the room's Hyphae could not be loaded"}
    spores = [
        {
            "device_id": p["device"]["device_id"],
            "name": p["device"]["name"],
            "linked_hyphae_id": p["device"].get("hyphae_id"),
            "panel_index": i,
        }
        for i, p in enumerate(panels)
        if p["device"]["source"] == "spore" and p["device"].get("room_id") == room_id
    ]
    if not spores:
        return {"reason": "no Spore from this room is selected"}
    spore_frames = [frames.get(("spore", s["device_id"])) for s in spores]
    if not any(f is not None and not f.empty for f in spore_frames):
        return {"reason": "the selected Spores have no readings in the period"}

    hyphae_ids = {e["device_id"] for e in equipment}
    unlinked = [s for s in spores if s["linked_hyphae_id"] not in hyphae_ids]
    out = {
        "reason": None,
        "hyphae": [],
        "spores": spores,
        "unlinked_default": equipment[0]["device_id"],
        "needs_selector": bool(unlinked) and len(equipment) > 1,
    }
    spore_ids = [s["device_id"] for s in spores]
    for eq in equipment:
        hid = eq["device_id"]
        names = {
            r["relay_number"]: r.get("relay_name")
            for r in relay_settings.get_device_relay_settings(hid)
        }
        edges = readings_hyphae.get_relay_edges(hid, start_ts, end_ts, MAX_SAMPLE_GAP_S)
        events = relay_events(edges)
        responses = {}
        for s in spores:
            frame = frames.get(("spore", s["device_id"]))
            if frame is None:
                continue
            responses[s["device_id"]] = {
                n: control_response(evs, frame) for n, evs in events.items() if evs
            }
        active = [r["relay_number"] for r in eq["relays"] if r["on_s"] > 0]
        out["hyphae"].append(
            {
                "device_id": hid,
                "name": eq["name"],
                "relays": [
                    {
                        "relay_number": n,
                        "label": relay_label(n, names.get(n)),
                        "events": len(evs),
                    }
                    for n, evs in sorted(events.items())
                ],
                "responses": responses,
                "scatter": daily_hours_vs_means(
                    eq["daily_hours"], daily, spore_ids, active
                ),
            }
        )
    if not any(h["relays"] for h in out["hyphae"]):
        return {"reason": "no relay samples from the room's Hyphae in the period"}
    return out


def _comparison_block(analytics, room_id, panels, frames, start_ts, end_ts, tz_name):
    """The room's Spore mean against every candidate baseline Sentinel.

    Every candidate is computed here so the card's selector swaps results
    without another fetch. Candidates not among the picks are fetched with
    just CO2 and humidity, and their raw rows are dropped at once.
    """
    if room_id is None:
        return {"reason": "pick a room"}
    room = grow_rooms.get_grow_room(room_id)
    farm_id = room.get("farm_id") if room else None
    picked = [
        p["device"]["device_id"] for p in panels if p["device"]["source"] == "sentinel"
    ]
    candidates = baseline_candidates(
        device_sentinel.get_all_device_sentinel(active_only=True),
        room_id,
        farm_id,
        picked,
    )
    if not candidates:
        return {"reason": "no Sentinel on this farm to use as a baseline"}
    room_frames = [
        frames.get(("spore", p["device"]["device_id"]))
        for p in panels
        if p["device"]["source"] == "spore" and p["device"].get("room_id") == room_id
    ]
    room_frames = [f for f in room_frames if f is not None and not f.empty]
    if not room_frames:
        return {"reason": "no selected Spore from this room has readings in the period"}
    room_mean = mean_frame(room_frames)

    results = {}
    for c in candidates:
        cid = c["device_id"]
        frame = frames.get(("sentinel", cid))
        if frame is None:
            try:
                frame = readings_frame(
                    analytics.get_sentinel_readings_for_period(
                        start_ts, end_ts, device_id=cid
                    ),
                    ("co2", "humidity"),
                )
            except Exception as e:
                logger.warning(
                    f"Failed to load baseline readings for {c['label']}: {e}"
                )
                results[cid] = {"reason": "its readings could not be loaded"}
                continue
        if frame.empty:
            results[cid] = {"reason": "it has no readings in the period"}
            continue
        results[cid] = {
            "heatmaps": room_baseline_diff(room_mean, frame, tz_name),
            "xcorr": lag_xcorr(room_mean["co2"], frame["co2"]),
        }
    return {
        "reason": None,
        "candidates": candidates,
        "default": candidates[0]["device_id"],
        "results": results,
    }


def _agreement_block(panels, frames, tz_name):
    """Pairwise Spore differences per room, and anomalies for every device."""
    by_room = {}
    for i, p in enumerate(panels):
        dev = p["device"]
        frame = frames.get((dev["source"], dev["device_id"]))
        if dev["source"] != "spore" or frame is None or frame.empty:
            continue
        by_room.setdefault(dev.get("room_id"), []).append((i, dev, frame))
    pairs = []
    for members in by_room.values():
        for (ia, a, fa), (ib, b, fb) in itertools.combinations(members, 2):
            pairs.append(
                {
                    "a": a,
                    "b": b,
                    "a_index": ia,
                    "b_index": ib,
                    "room": a.get("room"),
                    "metrics": pair_agreement(fa, fb, tz_name),
                }
            )
    anomalies = []
    for p in panels:
        dev = p["device"]
        frame = frames.get((dev["source"], dev["device_id"]))
        if frame is None or frame.empty:
            continue
        anomalies.append({"device": dev, **device_anomalies(frame, tz_name)})
    if not pairs and not anomalies:
        return {"reason": "no selected device has readings in the period"}
    return {
        "reason": None,
        "pairs": pairs[:AGREEMENT_MAX_PAIRS],
        "pairs_truncated": len(pairs) > AGREEMENT_MAX_PAIRS,
        "pairs_reason": (
            None
            if pairs
            else "fewer than two Spores in the same room have readings in the period"
        ),
        "anomalies": anomalies,
    }


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
            # Numbers first, insight last: stats, compliance, equipment,
            # alerts, the daily table, then control response, room
            # comparison and sensor agreement
            with ui.tab_panel(env_tab):
                _build_device_stats(panels, pref)
                _build_compliance_card(data["compliance"], pref)
                _build_equipment_card(data["equipment"])
                _build_alerts_card(data["alerts"])
                _build_daily_table(data["daily"], pref, data["period"])
                _build_control_card(data["control"], pref, colors)
                _build_comparison_card(data["comparison"], colors)
                _build_agreement_card(data["agreement"], pref, colors)

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


def _not_available(reason: str):
    """One line saying why a card has nothing to show for this selection."""
    ui.label(f"Not available: {reason}").classes("text-muted")


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


# -- Insight cards --------------------------------------------------------------

# (frame column, label, unit or None for the user's temperature unit)
_INSIGHT_METRICS = (
    ("co2", "CO2", "ppm"),
    ("humidity", "Humidity", "%"),
    ("temperature", "Temp", None),
)


def _metric_unit(metric: str, pref: str) -> str:
    """Display unit of an insight metric ('ppm', '%', or the temperature unit)."""
    for key, _label, unit in _INSIGHT_METRICS:
        if key == metric:
            return unit if unit is not None else temp_unit(pref)
    return ""


def _delta_pref(metric: str, value, pref: str):
    """A difference in the display unit (temperature scaled, never offset)."""
    return temp_delta_to_pref(value, pref) if metric == "temperature" else value


def _hover_fmt(metric: str) -> str:
    return ".0f" if metric == "co2" else ".2f"


def _legend_top() -> dict:
    return dict(orientation="h", x=0, xanchor="left", y=1.0, yanchor="bottom")


# ---- Control response ----------------------------------------------------------


def _build_control_card(control, pref, colors):
    """How the room's readings react to each relay: superposed-epoch curves.

    One figure per relay with events: the pooled curve over every served
    Spore drawn bold, each Spore's own curve thin behind it, t=0 marked.
    Then a table of the numbers and a scatter of daily relay hours against
    each Spore's daily means. Un-linked Spores follow the room's only
    Hyphae; with several Hyphae a selector chooses, re-drawing from the
    pre-computed responses.
    """
    unit = temp_unit(pref)
    floors = (
        f"{NO_RESPONSE_FLOOR['co2']:g} ppm / {NO_RESPONSE_FLOOR['humidity']:g}% / "
        f"{temp_delta_to_pref(NO_RESPONSE_FLOOR['temperature'], pref):g} {unit}"
    )
    with _section_card(
        "Control response",
        "Average change in the served Spores' readings around each relay "
        f"switching on, from 10 minutes before to {RESPONSE_POST_MIN} after "
        "(relative to the value at t=0). An event is the first poll seen on, so "
        f"t=0 is late by up to one poll; test pulses and switches after gaps over "
        f"{MAX_SAMPLE_GAP_S // 60} minutes are skipped. Recovery is the time after "
        f"OFF to get halfway back, only when the relay stays off at least "
        f"{RECOVERY_MIN_DATA_MIN} minutes; events that move less than {floors} "
        "count as no response.",
    ):
        if control.get("reason"):
            _not_available(control["reason"])
            return

        hyphae = control["hyphae"]
        spores = control["spores"]
        hyphae_ids = {h["device_id"] for h in hyphae}
        unlinked = [s for s in spores if s["linked_hyphae_id"] not in hyphae_ids]
        sel = None
        if control["needs_selector"]:
            sel = ui.select(
                {h["device_id"]: h["name"] for h in hyphae},
                value=control["unlinked_default"],
                label="Un-linked Spores follow",
            ).classes("w-64")
        elif unlinked:
            ui.label(
                f"{', '.join(s['name'] for s in unlinked)}: not linked to a Hyphae, "
                f"assumed served by {hyphae[0]['name']}"
            ).classes("text-caption text-muted")

        @ui.refreshable
        def body():
            follow = sel.value if sel is not None else control["unlinked_default"]
            for h in hyphae:
                served = [
                    s
                    for s in spores
                    if s["linked_hyphae_id"] == h["device_id"]
                    or (
                        s["linked_hyphae_id"] not in hyphae_ids
                        and follow == h["device_id"]
                    )
                ]
                _control_hyphae_section(h, served, pref, colors)

        if sel is not None:
            sel.on("update:model-value", lambda: body.refresh())
        body()


_RESPONSE_COLUMNS = [
    {"name": "relay", "label": "Relay", "field": "relay", "align": "left"},
    {"name": "spore", "label": "Spore", "field": "spore", "align": "left"},
    {"name": "events", "label": "Events", "field": "events", "align": "right"},
    {"name": "co2", "label": "CO2", "field": "co2", "align": "left"},
    {"name": "humidity", "label": "Humidity", "field": "humidity", "align": "left"},
    {"name": "temperature", "label": "Temp", "field": "temperature", "align": "left"},
]


def _control_hyphae_section(h, served, pref, colors):
    """One Hyphae's relays: a figure per relay with events, the table, the scatter."""
    ui.label(h["name"]).classes("text-subtitle2 text-weight-bold")
    if not served:
        ui.label("No selected Spore is served by this Hyphae").classes(
            "text-caption text-muted"
        )
        return
    if not h["relays"]:
        ui.label("No relay samples in the period").classes("text-caption text-muted")
        return

    table_rows, quiet = [], []
    for relay in h["relays"]:
        n = relay["relay_number"]
        per_spore = [(s, h["responses"].get(s["device_id"], {}).get(n)) for s in served]
        per_spore = [(s, r) for s, r in per_spore if r]
        if relay["events"] == 0 or not per_spore:
            quiet.append(relay["label"])
            continue
        pooled = pool_responses([r for _s, r in per_spore])
        ui.label(
            f"{relay['label']} — {pooled['events_used']} of {relay['events']} events "
            "with readings"
        ).classes("text-caption text-weight-bold")
        ui.plotly(_response_figure(pooled, per_spore, pref, colors)).classes("w-full")
        who = "All served" if len(per_spore) > 1 else per_spore[0][0]["name"]
        table_rows.append(_response_row(relay["label"], who, pooled, pref))
        if len(per_spore) > 1:
            for s, r in per_spore:
                table_rows.append(_response_row(relay["label"], s["name"], r, pref))
    if quiet:
        ui.label("No OFF→ON events in the period: " + ", ".join(quiet)).classes(
            "text-caption text-muted"
        )
    if table_rows:
        for i, row in enumerate(table_rows):
            row["key"] = i
        ui.table(columns=_RESPONSE_COLUMNS, rows=table_rows, row_key="key").classes(
            "w-full"
        ).props("dense flat")

    labels = {r["relay_number"]: r["label"] for r in h["relays"]}
    fig = _hours_scatter_figure(h["scatter"], labels, served, colors)
    if fig is None:
        ui.label(
            "Daily relay hours against daily means: no day has both relay hours "
            "and Spore readings"
        ).classes("text-caption text-muted")
    else:
        ui.label("Daily relay hours against each Spore's daily mean").classes(
            "text-caption text-weight-bold"
        )
        ui.plotly(fig).classes("w-full")


def _response_row(relay_text, who, result, pref):
    """Table row: per metric the delta, time to half of it, recovery, no-response."""
    row = {"relay": relay_text, "spore": who, "events": result["events_used"]}
    for metric, _label, _unit in _INSIGHT_METRICS:
        e = result["metrics"].get(metric) or {}
        delta = _delta_pref(metric, e.get("delta"), pref)
        if delta is None:
            row[metric] = "—"
            continue
        unit = _metric_unit(metric, pref)
        fmt = "{:+.0f}" if metric == "co2" else "{:+.1f}"
        parts = [f"Δ {fmt.format(delta)} {unit}".replace(" %", "%")]
        if e.get("t50_min") is not None:
            parts.append(f"half at {e['t50_min']} min")
        if e.get("recovery_min") is not None:
            parts.append(
                f"recovery {e['recovery_min']:.0f} min ({len(e['recovery_values'])} ev.)"
            )
        else:
            parts.append("recovery n/a")
        parts.append(
            f"{e.get('no_response', 0)} of {e.get('events_with_data', 0)} no response"
        )
        row[metric] = " · ".join(parts)
    return row


def _response_figure(pooled, per_spore, pref, colors):
    """CO2 / humidity / temp response rows: pooled bold, each Spore thin, t=0 dotted."""
    offsets = pooled["offsets"]
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06)
    several = len(per_spore) > 1
    for row, (metric, label, _unit) in enumerate(_INSIGHT_METRICS, start=1):
        unit = _metric_unit(metric, pref)
        if several:
            for s, r in per_spore:
                fig.add_trace(
                    go.Scatter(
                        x=offsets,
                        y=[
                            _delta_pref(metric, v, pref)
                            for v in r["metrics"][metric]["curve"]
                        ],
                        name=s["name"],
                        mode="lines",
                        line=dict(color=_device_colour(s["panel_index"]), width=1),
                        opacity=0.8,
                        legendgroup=f"spore{s['device_id']}",
                        showlegend=(row == 1),
                        hovertemplate="%{y:"
                        + _hover_fmt(metric)
                        + "}<extra>%{fullData.name}</extra>",
                    ),
                    row=row,
                    col=1,
                )
        fig.add_trace(
            go.Scatter(
                x=offsets,
                y=[
                    _delta_pref(metric, v, pref)
                    for v in pooled["metrics"][metric]["curve"]
                ],
                name="All served Spores" if several else per_spore[0][0]["name"],
                mode="lines",
                line=dict(color=colors["primary"], width=3),
                legendgroup="pooled",
                showlegend=(row == 1),
                hovertemplate="%{y:"
                + _hover_fmt(metric)
                + "}<extra>%{fullData.name}</extra>",
            ),
            row=row,
            col=1,
        )
        fig.update_yaxes(title_text=f"{label} Δ ({unit})", row=row, col=1)
    fig.add_vline(x=0, line_dash="dot", line_color=colors["text_secondary"])
    fig.update_xaxes(title_text="Minutes from relay ON", row=3, col=1)
    fig.update_layout(
        **chart_layout(colors),
        margin=dict(l=70, r=20, t=40, b=40),
        height=460,
        hovermode="x unified",
        legend=_legend_top(),
    )
    return fig


_SCATTER_SYMBOLS = ["circle", "diamond", "square", "triangle-up", "cross", "x"]


def _hours_scatter_figure(points, relay_labels, served, colors):
    """Daily relay hours (x) against daily mean CO2 and humidity (y) per Spore.

    Colour = relay, marker = Spore; None when no point applies to the served Spores.
    """
    order = [s["device_id"] for s in served]
    points = [p for p in points if p["device_id"] in order]
    if not points:
        return None
    groups = {}
    for p in points:
        groups.setdefault((p["relay_number"], p["device_id"]), []).append(p)
    fig = make_subplots(
        rows=1,
        cols=2,
        horizontal_spacing=0.1,
        subplot_titles=("Daily mean CO2 (ppm)", "Daily mean humidity (%)"),
    )
    for (n, sid), group in sorted(groups.items()):
        colour = _relay_colour(n, colors)
        symbol = _SCATTER_SYMBOLS[order.index(sid) % len(_SCATTER_SYMBOLS)]
        name = f"{relay_labels.get(n, f'Relay {n}')} · {group[0]['device']}"
        for col, key in ((1, "co2_avg"), (2, "humidity_avg")):
            fig.add_trace(
                go.Scatter(
                    x=[g["hours"] for g in group],
                    y=[g[key] for g in group],
                    mode="markers",
                    marker=dict(color=colour, symbol=symbol, size=9),
                    name=name,
                    text=[g["date"] for g in group],
                    hovertemplate="%{text}<br>%{x:.1f} h on, mean %{y:.1f}<extra>%{fullData.name}</extra>",
                    legendgroup=name,
                    showlegend=(col == 1),
                ),
                row=1,
                col=col,
            )
    for col in (1, 2):
        fig.update_xaxes(title_text="Hours on that day", row=1, col=col)
    fig.update_layout(
        **chart_layout(colors),
        margin=dict(l=60, r=20, t=60, b=40),
        height=380,
        legend=_legend_top(),
    )
    return fig


# ---- Room comparison ------------------------------------------------------------


def _build_comparison_card(comparison, colors):
    """The room's Spore mean against a baseline Sentinel, hour by hour, plus lag.

    The selector lists every candidate (other rooms first, then no room,
    then the selected room); each was computed in the worker, so switching
    only re-draws.
    """
    with _section_card(
        "Room comparison",
        "Selected-room Spore mean minus the baseline Sentinel, per hour of each "
        "day in your time zone (red: room higher, blue: room lower). The lag curve "
        "correlates room CO2 with baseline CO2 at every offset within ±2 hours "
        f"after removing a {XCORR_DETREND_MIN // 60}-hour rolling mean from both, "
        "so the shared daily cycle does not swamp it; a positive peak lag means "
        "the room follows the baseline.",
    ):
        if comparison.get("reason"):
            _not_available(comparison["reason"])
            return

        candidates = comparison["candidates"]
        results = comparison["results"]
        sel = ui.select(
            {
                c["device_id"]: c["label"] + (" (same room)" if c["same_room"] else "")
                for c in candidates
            },
            value=comparison["default"],
            label="Baseline Sentinel",
        ).classes("w-72")

        @ui.refreshable
        def body():
            chosen = next((c for c in candidates if c["device_id"] == sel.value), None)
            res = results.get(sel.value) if chosen else None
            if not res:
                _not_available("pick a baseline Sentinel")
                return
            if res.get("reason"):
                _not_available(res["reason"])
                return
            if chosen["same_room"]:
                ui.label(
                    "This Sentinel is in the selected room, so the map shows the "
                    "gradient inside the room rather than room versus outside."
                ).classes("text-caption text-muted")
            for metric, title in (
                ("co2", "CO2 difference (ppm)"),
                ("humidity", "Humidity difference (%)"),
            ):
                ui.label(title).classes("text-caption text-weight-bold")
                hm = res["heatmaps"].get(metric) or {"reason": "not computed"}
                if hm.get("reason"):
                    _not_available(hm["reason"])
                    continue
                ui.plotly(_heatmap_figure(hm, metric, colors)).classes("w-full")

            ui.label("CO2 lag correlation").classes("text-caption text-weight-bold")
            xc = res["xcorr"]
            if xc.get("reason"):
                _not_available(xc["reason"])
                return
            lag = xc["peak_lag"]
            if lag > 0:
                who = "the room follows the baseline"
            elif lag < 0:
                who = "the baseline follows the room"
            else:
                who = "no lag between room and baseline"
            ui.label(
                f"Peak r = {xc['peak_corr']:.2f} at {abs(lag)} min: {who} "
                f"({xc['n']:,} overlapping minutes)"
            ).classes("text-caption text-muted")
            ui.plotly(_xcorr_figure(xc, colors)).classes("w-full")

        sel.on("update:model-value", lambda: body.refresh())
        body()


def _heatmap_figure(hm, metric, colors):
    """Hour-of-day x date heatmap of a difference, diverging around zero."""
    mid = "#616161" if colors["mode"] == "dark" else "#e0e0e0"
    fig = go.Figure(
        go.Heatmap(
            x=hm["hours"],
            y=hm["dates"],
            z=hm["z"],
            colorscale=[[0.0, "#42a5f5"], [0.5, mid], [1.0, "#ef5350"]],
            zmid=0,
            xgap=1,
            ygap=1,
            hoverongaps=False,
            colorbar=dict(thickness=12, title=dict(text=_metric_unit(metric, "C"))),
            hovertemplate="%{y} %{x}:00 — %{z:"
            + _hover_fmt(metric)
            + "}<extra></extra>",
        )
    )
    fig.update_layout(
        **chart_layout(colors),
        margin=dict(l=90, r=20, t=10, b=40),
        height=max(220, 18 * len(hm["dates"]) + 80),
        xaxis=dict(title="Hour of day", dtick=2),
        yaxis=dict(type="category", autorange="reversed"),
    )
    return fig


def _xcorr_figure(xc, colors):
    """Correlation against lag, the peak lag dotted and zero lag marked."""
    fig = go.Figure(
        go.Scatter(
            x=xc["lags"],
            y=xc["corr"],
            mode="lines",
            line=dict(color=colors["primary"], width=2),
            name="r",
            hovertemplate="lag %{x} min: r = %{y:.2f}<extra></extra>",
        )
    )
    fig.add_vline(x=0, line_width=1, line_color=colors["text_muted"])
    if xc.get("peak_lag") is not None:
        fig.add_vline(
            x=xc["peak_lag"], line_dash="dot", line_color=colors["text_secondary"]
        )
    fig.update_layout(
        **chart_layout(colors),
        margin=dict(l=60, r=20, t=10, b=40),
        height=260,
        showlegend=False,
        xaxis=dict(title="Lag (minutes; positive = room after baseline)"),
        yaxis=dict(title="Correlation", range=[-1, 1]),
    )
    return fig


# ---- Sensor agreement -------------------------------------------------------------


def _build_agreement_card(agreement, pref, colors):
    """Spore pairs in the same room, with a settable band, and per-device anomalies.

    The band inputs only change what is drawn and counted: the rolling
    medians were computed once in the worker, and the share of time outside
    the band comes from their sorted magnitudes.
    """
    unit = temp_unit(pref)
    with _section_card(
        "Sensor agreement",
        "For each pair of Spores in the same room: the rolling 1-hour median of "
        "their difference against a band you can set, and the rolling 24-hour "
        "drift of that difference. Below, the stretches where any selected device "
        f"strays more than {ANOMALY_Z:g} robust standard deviations from its own "
        "hour-of-day pattern over the period.",
    ):
        if agreement.get("reason"):
            _not_available(agreement["reason"])
            return

        with ui.row().classes("items-end gap-3 flex-wrap"):
            inputs = {
                "co2": ui.number(
                    "CO2 band (± ppm)",
                    value=AGREEMENT_THRESHOLDS["co2"],
                    min=0,
                    step=10,
                ),
                "humidity": ui.number(
                    "Humidity band (± %)",
                    value=AGREEMENT_THRESHOLDS["humidity"],
                    min=0,
                    step=0.5,
                ),
                "temperature": ui.number(
                    f"Temp band (± {unit})",
                    value=round(
                        temp_delta_to_pref(AGREEMENT_THRESHOLDS["temperature"], pref), 2
                    ),
                    min=0,
                    step=0.1,
                ),
            }
            for w in inputs.values():
                w.classes("w-40").props("dense debounce=400")

        @ui.refreshable
        def body():
            bands = {}
            for metric, w in inputs.items():
                try:
                    bands[metric] = max(0.0, float(w.value))
                except (TypeError, ValueError):
                    bands[metric] = 0.0
            # Bands are entered in display units; the medians are Celsius
            bands_c = dict(bands)
            if pref == "F":
                bands_c["temperature"] = bands["temperature"] / 1.8

            if agreement["pairs_reason"]:
                ui.label(agreement["pairs_reason"]).classes("text-caption text-muted")
            for pair in agreement["pairs"]:
                ui.label(
                    f"{pair['a']['name']} − {pair['b']['name']} · {pair['room']}"
                ).classes("text-subtitle2 text-weight-bold")
                ui.label(_pair_caption(pair, bands, bands_c, pref)).classes(
                    "text-caption text-muted"
                )
                ui.plotly(_agreement_figure(pair, bands, pref, colors)).classes(
                    "w-full"
                )
            if agreement["pairs_truncated"]:
                ui.label(f"Showing the first {AGREEMENT_MAX_PAIRS} pairs").classes(
                    "text-caption text-muted"
                )
            _anomaly_table(agreement["anomalies"], pref)

        for w in inputs.values():
            w.on("update:model-value", lambda: body.refresh())
        body()


def _pct_outside(sorted_abs, band) -> float:
    """Share (%) of minutes whose |median| exceeds the band."""
    if not sorted_abs:
        return 0.0
    inside = bisect.bisect_right(sorted_abs, band)
    return 100.0 * (1 - inside / len(sorted_abs))


def _pair_caption(pair, bands, bands_c, pref) -> str:
    parts = []
    for metric, label, _unit in _INSIGHT_METRICS:
        res = pair["metrics"].get(metric) or {"reason": "not computed"}
        if res.get("reason"):
            parts.append(f"{label}: {res['reason']}")
            continue
        unit = _metric_unit(metric, pref)
        outside = _pct_outside(res["abs_median_sorted"], bands_c[metric])
        slope = _delta_pref(metric, res["overall_slope_per_day"], pref)
        drift = f"{slope:+.1f} {unit}/day" if slope is not None else "drift n/a"
        parts.append(
            f"{label}: {outside:.0f}% of the time outside ±{bands[metric]:g} {unit}, "
            f"drift {drift}".replace(" %", "%")
        )
    return " · ".join(parts)


def _agreement_figure(pair, bands, pref, colors):
    """Rows per metric: the rolling median with its band (left), the drift (right)."""
    fig = make_subplots(
        rows=3,
        cols=2,
        shared_xaxes=True,
        vertical_spacing=0.07,
        horizontal_spacing=0.08,
        column_titles=["Difference (rolling 1 h median)", "Drift (rolling 24 h slope)"],
    )
    for row, (metric, label, _unit) in enumerate(_INSIGHT_METRICS, start=1):
        unit = _metric_unit(metric, pref)
        res = pair["metrics"].get(metric)
        fig.update_yaxes(title_text=f"{label} ({unit})", row=row, col=1)
        fig.update_yaxes(title_text=f"{unit}/day", row=row, col=2)
        if not res or res.get("reason"):
            continue
        fig.add_trace(
            go.Scatter(
                x=res["t"],
                y=[_delta_pref(metric, v, pref) for v in res["median"]],
                mode="lines",
                line=dict(color=colors["primary"], width=2),
                name=f"{label} median",
                hovertemplate="%{y:"
                + _hover_fmt(metric)
                + "}<extra>%{fullData.name}</extra>",
            ),
            row=row,
            col=1,
        )
        if bands.get(metric, 0) > 0:
            fig.add_hrect(
                y0=-bands[metric],
                y1=bands[metric],
                fillcolor=colors["primary"],
                opacity=0.12,
                line_width=0,
                layer="below",
                row=row,
                col=1,
            )
        fig.add_hline(
            y=0, line_width=1, line_color=colors["text_muted"], row=row, col=1
        )
        fig.add_trace(
            go.Scatter(
                x=res["t"],
                y=[_delta_pref(metric, v, pref) for v in res["slope"]],
                mode="lines",
                line=dict(color=SERIES_PALETTE[3], width=2),
                name=f"{label} drift",
                hovertemplate="%{y:+.1f}/day<extra>%{fullData.name}</extra>",
            ),
            row=row,
            col=2,
        )
        fig.add_hline(
            y=0, line_width=1, line_color=colors["text_muted"], row=row, col=2
        )
    fig.update_layout(
        **chart_layout(colors),
        margin=dict(l=70, r=20, t=40, b=40),
        height=560,
        hovermode="x unified",
        showlegend=False,
    )
    return fig


_ANOMALY_COLUMNS = [
    {"name": "device", "label": "Device", "field": "device", "align": "left"},
    {"name": "metric", "label": "Metric", "field": "metric", "align": "left"},
    {"name": "start", "label": "Start", "field": "start", "align": "left"},
    {"name": "end", "label": "End", "field": "end", "align": "left"},
    {"name": "minutes", "label": "Minutes", "field": "minutes", "align": "right"},
    {"name": "peak_z", "label": "Peak z", "field": "peak_z", "align": "right"},
    {"name": "value", "label": "Value at peak", "field": "value", "align": "right"},
]


def _anomaly_table(anomalies, pref):
    """Flagged intervals of every device, largest |z| first."""
    ui.label("Anomalies").classes("text-subtitle2 text-weight-bold")
    found = []
    for a in anomalies:
        for iv in a["intervals"]:
            found.append((a["device"], iv))
    found.sort(key=lambda item: -abs(item[1]["peak_z"]))

    if not found:
        ui.label(
            f"No stretch beyond |z| = {ANOMALY_Z:g} for any selected device"
        ).classes("text-caption text-muted")
    else:
        rows = []
        for i, (dev, iv) in enumerate(found):
            metric = iv["metric"]
            value = iv["peak_value"]
            if metric == "temperature":
                value = to_pref_temp(value, pref)
            fmt = "{:.0f}" if metric == "co2" else "{:.1f}"
            rows.append(
                {
                    "key": i,
                    "device": dev["name"],
                    "metric": METRIC_LABELS.get(metric, metric),
                    "start": fmt_datetime(iv["start_utc"]),
                    "end": fmt_datetime(iv["end_utc"]),
                    "minutes": iv["minutes"],
                    "peak_z": f"{iv['peak_z']:+.1f}",
                    "value": (
                        f"{fmt.format(value)} {_metric_unit(metric, pref)}".replace(
                            " %", "%"
                        )
                        if value is not None
                        else "—"
                    ),
                }
            )
        ui.table(
            columns=_ANOMALY_COLUMNS, rows=rows, row_key="key", pagination=15
        ).classes("w-full").props("dense flat")

    capped = [a["device"]["name"] for a in anomalies if a.get("truncated")]
    if capped:
        ui.label(
            f"Showing the {ANOMALY_MAX_INTERVALS} largest stretches for "
            + ", ".join(capped)
        ).classes("text-caption text-muted")
    for a in anomalies:
        if a.get("skipped"):
            ui.label(
                f"{a['device']['name']}: "
                + ", ".join(
                    f"{METRIC_LABELS.get(m, m)} {why}"
                    for m, why in a["skipped"].items()
                )
            ).classes("text-caption text-muted")
