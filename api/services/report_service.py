"""
Report maths for the Analytics Reports tab.

Pure functions over rows already fetched from storage: no database access,
no UI, no app.storage, so everything here is safe inside nicegui.run.io_bound
and can be exercised offline against any rows. The page passes the user's
time zone and temperature unit in explicitly. The insight cards (control
response, room comparison, sensor agreement) use numpy and pandas; the rest
is stdlib.

Compliance uses only the user's own alert rules (threshold_high /
threshold_low). Mycelium stores no generic CO2 / humidity / temperature
targets — they are species-specific — so a metric without a rule reports
"no rule" rather than a made-up band.
"""

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

logger = logging.getLogger("services.ReportService")

# Samples further apart than this mean the device was offline: the gap counts
# as neither ON nor OFF for relays, and ends an excursion run for compliance.
MAX_SAMPLE_GAP_S = 300

# -- Insight card parameters --------------------------------------------------
# Readings are put on a 1-minute grid (readings_frame); holes up to this many
# minutes (normal poll jitter) are forward-filled, offline gaps are not.
FRAME_FIELDS = ("co2", "humidity", "temperature")
FRAME_FFILL_LIMIT = 2

# Control response: minutes before / after a relay ON event in each epoch, and
# how far after OFF to look for the metric to recover halfway (needs at least
# RECOVERY_MIN_DATA_MIN minutes of data before the next ON).
RESPONSE_PRE_MIN = 10
RESPONSE_POST_MIN = 30
RECOVERY_MAX_MIN = 120
RECOVERY_MIN_DATA_MIN = 30
# An event whose own response stays under this is counted as "no response".
# Judgment values near sensor noise; shown in the card caption.
NO_RESPONSE_FLOOR = {"co2": 25.0, "humidity": 1.0, "temperature": 0.2}

# Room comparison: lag search range and the minimum overlap for a correlation
# at any lag; both series are high-passed with a centred rolling mean first,
# else the shared diurnal cycle flattens the ±2 h correlation curve.
XCORR_MAX_LAG_MIN = 120
XCORR_MIN_PAIRS = 120
XCORR_DETREND_MIN = 180
HEATMAP_MIN_OVERLAP_MIN = 60

# Sensor agreement: rolling-median window for the pairwise difference, the
# window of the rolling drift slope, the plot resolution, the default band
# (Celsius for temperature) and a cap on pairs drawn.
AGREEMENT_WINDOW_MIN = 60
AGREEMENT_SLOPE_WINDOW_MIN = 1440
AGREEMENT_PLOT_STEP = "15min"
AGREEMENT_THRESHOLDS = {"co2": 100.0, "humidity": 3.0, "temperature": 0.5}
AGREEMENT_MAX_PAIRS = 15

# Anomalies: |z| above this against an hour-of-day median baseline, needing at
# least a day of samples; runs closer than the merge gap join, runs shorter
# than the minimum are noise, and the table is capped.
ANOMALY_Z = 3.0
ANOMALY_MIN_SAMPLES = 1440
ANOMALY_MERGE_GAP_MIN = 2
ANOMALY_MIN_RUN_MIN = 3
ANOMALY_MAX_INTERVALS = 50

# Rule metric -> key in the AnalyticsService reading rows. Mirrors
# alert_service._METRIC_FIELDS but targets the service row shape
# (`temperature`), not the raw table column (`temp`). A metric missing for a
# source means that device type does not measure it.
METRIC_FIELDS = {
    "spore": {"co2": "co2", "humidity": "humidity", "temperature": "temperature"},
    "sentinel": {
        "co2": "co2",
        "humidity": "humidity",
        "temperature": "temperature",
        "pm2_5": "pm2_5",
        "voc": "voc",
        "nox": "nox",
    },
}

# Display order: the standard CO2, humidity, temperature trio first
METRIC_LABELS = {
    "co2": "CO2",
    "humidity": "Humidity",
    "temperature": "Temp",
    "pm2_5": "PM2.5",
    "voc": "VOC",
    "nox": "NOx",
}


# -- Temperature preference ---------------------------------------------------


def temp_unit(pref: str) -> str:
    """Display unit string for a temperature preference ('C' or 'F')."""
    return "°F" if pref == "F" else "°C"


def to_pref_temp(celsius, pref: str) -> Optional[float]:
    """Convert a stored Celsius value to the preferred unit, or None."""
    if celsius is None:
        return None
    try:
        c = float(celsius)
    except (TypeError, ValueError):
        return None
    return c * 9 / 5 + 32 if pref == "F" else c


def temp_delta_to_pref(delta_c, pref: str) -> Optional[float]:
    """Convert a Celsius difference (delta, band, slope) to the preferred unit.

    Unlike to_pref_temp there is no +32: a change of 1 °C is a change of 1.8 °F.
    """
    if delta_c is None:
        return None
    try:
        d = float(delta_c)
    except (TypeError, ValueError):
        return None
    return d * 9 / 5 if pref == "F" else d


# -- Timestamps ---------------------------------------------------------------


def parse_utc(value) -> Optional[datetime]:
    """Stored naive-UTC timestamp ('T' or space separated) -> aware UTC datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _zone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or "UTC")
    except Exception:
        logger.warning(f"Unknown time zone {tz_name!r}; reporting in UTC")
        return ZoneInfo("UTC")


def utc_bounds(start_date: str, end_date: str, tz_name: str) -> Tuple[str, str]:
    """Naive-UTC ISO bounds covering the whole local days start..end inclusive.

    reading_ts is naive UTC written by datetime.isoformat(), and the readings
    queries compare it as a string, so both bounds keep the 'T' separator.
    The end bound is the last microsecond before local midnight after
    end_date, so a report covers full days in the user's own time zone.
    """
    zone = _zone(tz_name)
    start_local = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=zone)
    end_local = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).replace(
        tzinfo=zone
    )
    start = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end = end_local.astimezone(timezone.utc).replace(tzinfo=None) - timedelta(
        microseconds=1
    )
    return start.isoformat(), end.isoformat()


def alert_bounds(start_ts: str, end_ts: str) -> Tuple[str, str]:
    """Rewrite 'T' bounds for alert_history, whose timestamps use a space.

    alert_history.triggered_at is written by SQLite CURRENT_TIMESTAMP as
    'YYYY-MM-DD HH:MM:SS'. A 'T' string or a bare date sorts wrongly against
    that, so the bounds are space-separated and truncated to seconds.
    """
    return start_ts.replace("T", " ")[:19], end_ts.replace("T", " ")[:19]


# -- Compliance against the user's alert rules --------------------------------


def rule_bands(rules: List[Dict], device: Dict) -> Dict[str, Dict[str, Any]]:
    """Threshold bands that apply to one device, keyed by metric.

    A rule applies when it is enabled, is a threshold rule, names a metric
    the device measures, and its device_type / device_id / room_id filters
    are each unset or match the device — the same AND filters the alert
    engine uses (AlertService._get_devices_for_rule). Every applicable rule
    fires on its own, so a sample is compliant only when it violates none:
    the band is the tightest high and the tightest low across them. The
    duration comes from the rule that supplied the tighter side (the smaller
    of the two when both sides are set).
    """
    fields = METRIC_FIELDS.get(device["source"], {})
    bands: Dict[str, Dict[str, Any]] = {}
    for rule in rules:
        if not rule.get("enabled", 1):
            continue
        rtype = rule.get("rule_type")
        if rtype not in ("threshold_high", "threshold_low"):
            continue
        metric = rule.get("metric")
        if metric not in fields or rule.get("threshold_value") is None:
            continue
        if rule.get("device_type") and rule["device_type"] != device["source"]:
            continue
        if rule.get("device_id") and rule["device_id"] != device["device_id"]:
            continue
        if rule.get("room_id") and rule["room_id"] != device.get("room_id"):
            continue

        band = bands.setdefault(
            metric,
            {
                "low": None,
                "high": None,
                "duration_min": 0,
                "rule_names": [],
                "_durations": {},
            },
        )
        value = float(rule["threshold_value"])
        duration = int(rule.get("threshold_duration_minutes") or 0)
        if rtype == "threshold_high" and (band["high"] is None or value < band["high"]):
            band["high"] = value
            band["_durations"]["high"] = duration
        elif rtype == "threshold_low" and (band["low"] is None or value > band["low"]):
            band["low"] = value
            band["_durations"]["low"] = duration
        band["rule_names"].append(
            rule.get("rule_name") or f"rule {rule.get('rule_id')}"
        )

    for band in bands.values():
        durations = band.pop("_durations").values()
        band["duration_min"] = min(durations) if durations else 0
    return bands


def compliance_for_panel(
    readings: List[Dict], device: Dict, rules: List[Dict]
) -> List[Dict[str, Any]]:
    """Per-metric share of samples inside the device's threshold bands.

    One entry per metric the device measures, in METRIC_LABELS order. A
    metric with no applicable rule gets has_rule=False and no numbers.
    Thresholds are compared raw (Celsius for temperature), as the alert
    engine does; the page converts band labels for display.

    An excursion is a run of consecutive out-of-band samples. A gap wider
    than MAX_SAMPLE_GAP_S ends the run at its last sample, and a run shorter
    than the rule's duration is not counted — that persistence is what the
    rule asks for, so single bad polls stay out of the tally.
    """
    fields = METRIC_FIELDS.get(device["source"], {})
    bands = rule_bands(rules, device)
    out = []
    for metric, label in METRIC_LABELS.items():
        if metric not in fields:
            continue
        entry = {
            "metric": metric,
            "label": label,
            "has_rule": metric in bands,
            "low": None,
            "high": None,
            "duration_min": 0,
            "rule_names": [],
            "samples": 0,
            "in_band": 0,
            "pct_in_band": None,
            "excursions": 0,
            "longest_s": 0.0,
        }
        if metric in bands:
            band = bands[metric]
            entry.update(
                low=band["low"],
                high=band["high"],
                duration_min=band["duration_min"],
                rule_names=band["rule_names"],
            )
            _score_band(entry, readings, fields[metric], band)
        out.append(entry)
    return out


def _score_band(entry: Dict, readings: List[Dict], key: str, band: Dict):
    """Fill entry's sample / in-band / excursion counts for one metric."""
    low, high = band["low"], band["high"]
    min_run_s = band["duration_min"] * 60
    samples = in_band = excursions = 0
    longest = 0.0
    run_start = None  # first out-of-band sample of the open run
    run_last = None  # latest out-of-band sample of the open run
    prev_ts = None

    def close_run(end_ts):
        nonlocal excursions, longest, run_start, run_last
        if run_start is not None and end_ts is not None:
            duration = (end_ts - run_start).total_seconds()
            if duration >= min_run_s:
                excursions += 1
                longest = max(longest, duration)
        run_start = run_last = None

    for r in readings:
        value = r.get(key)
        if value is None:
            continue
        try:
            v = float(value)
        except (TypeError, ValueError):
            continue
        ts = parse_utc(r.get("timestamp"))
        if ts is None:
            continue
        # The device was away: whatever run was open ended at its last sample
        if prev_ts is not None and (ts - prev_ts).total_seconds() > MAX_SAMPLE_GAP_S:
            close_run(run_last)
        prev_ts = ts
        samples += 1
        out = (high is not None and v > high) or (low is not None and v < low)
        if out:
            if run_start is None:
                run_start = ts
            run_last = ts
        else:
            in_band += 1
            close_run(ts)
    close_run(run_last)

    entry.update(
        samples=samples,
        in_band=in_band,
        excursions=excursions,
        longest_s=longest,
        pct_in_band=(100.0 * in_band / samples) if samples else None,
    )


# -- Relay run-time -----------------------------------------------------------


def relay_label(relay_number: int, name: Optional[str]) -> str:
    """'Relay n', plus ' · name' when the Hyphae has a custom relay name."""
    label = f"Relay {relay_number}"
    clean = (name or "").strip()
    if clean and clean != label:
        label += f" · {clean}"
    return label


def relay_duty(hourly: List[Dict], names: Dict[int, str]) -> List[Dict[str, Any]]:
    """Per-relay ON time over the period, from hourly duty buckets.

    `hourly` rows come from readings_hyphae.get_relay_hourly_duty:
    {relay_number, hour_utc, samples, covered_s, on_s}. covered_s is the time
    between consecutive samples no further apart than the gap cap, so
    offline stretches count as neither ON nor OFF and pct_on is ON time over
    covered time (None when nothing was covered).
    """
    totals: Dict[int, Dict[str, float]] = {}
    for row in hourly:
        n = row["relay_number"]
        t = totals.setdefault(n, {"on_s": 0.0, "covered_s": 0.0, "samples": 0})
        t["on_s"] += row.get("on_s") or 0.0
        t["covered_s"] += row.get("covered_s") or 0.0
        t["samples"] += row.get("samples") or 0

    out = []
    for n in sorted(totals):
        t = totals[n]
        out.append(
            {
                "relay_number": n,
                "label": relay_label(n, names.get(n)),
                "on_s": t["on_s"],
                "covered_s": t["covered_s"],
                "pct_on": (t["on_s"] / t["covered_s"]) if t["covered_s"] else None,
                "samples": int(t["samples"]),
            }
        )
    return out


def relay_daily_hours(hourly: List[Dict], tz_name: str) -> Dict[str, Dict[int, float]]:
    """{local date: {relay_number: hours ON}} from hourly duty buckets.

    Each UTC hour bucket is attributed to the local day it starts in.
    """
    zone = _zone(tz_name)
    days: Dict[str, Dict[int, float]] = {}
    for row in hourly:
        try:
            hour = datetime.strptime(row["hour_utc"], "%Y-%m-%dT%H").replace(
                tzinfo=timezone.utc
            )
        except (KeyError, TypeError, ValueError):
            continue
        day = hour.astimezone(zone).date().isoformat()
        per_relay = days.setdefault(day, {})
        n = row["relay_number"]
        per_relay[n] = per_relay.get(n, 0.0) + (row.get("on_s") or 0.0) / 3600.0
    return days


# -- Daily summary ------------------------------------------------------------

# (column prefix, key in the service reading rows)
_DAILY_METRICS = (
    ("co2", "co2"),
    ("humidity", "humidity"),
    ("temp", "temperature"),
    ("pm25", "pm2_5"),
)


def daily_rows(
    readings: List[Dict], device: Dict, tz_name: str, temp_pref: str
) -> List[Dict[str, Any]]:
    """One row per local day: min / avg / max of each metric the device measures.

    Keys: date, device, source, device_id, room, samples, then
    {co2, humidity, temp, pm25}_{min, avg, max}. Temperature is in the
    preferred unit; pm25 is only filled for Sentinels. Values are unrounded
    floats (None where a metric had no readings that day).
    """
    zone = _zone(tz_name)
    is_sentinel = device["source"] == "sentinel"
    acc: Dict[str, Dict[str, Any]] = {}

    for r in readings:
        ts = parse_utc(r.get("timestamp"))
        if ts is None:
            continue
        day = ts.astimezone(zone).date().isoformat()
        a = acc.setdefault(day, {"samples": 0})
        a["samples"] += 1
        for prefix, key in _DAILY_METRICS:
            if prefix == "pm25" and not is_sentinel:
                continue
            value = r.get(key)
            if value is None:
                continue
            try:
                v = float(value)
            except (TypeError, ValueError):
                continue
            m = a.get(prefix)
            if m is None:
                a[prefix] = [v, v, v, 1]  # min, sum, max, count
            else:
                if v < m[0]:
                    m[0] = v
                m[1] += v
                if v > m[2]:
                    m[2] = v
                m[3] += 1

    rows = []
    for day in sorted(acc):
        a = acc[day]
        row = {
            "date": day,
            "device": device["name"],
            "source": device["source"],
            "device_id": device["device_id"],
            "room": device.get("room"),
            "samples": a["samples"],
        }
        for prefix, _key in _DAILY_METRICS:
            m = a.get(prefix)
            lo, avg, hi = (m[0], m[1] / m[3], m[2]) if m else (None, None, None)
            if prefix == "temp":
                lo, avg, hi = (to_pref_temp(x, temp_pref) for x in (lo, avg, hi))
            row[f"{prefix}_min"] = lo
            row[f"{prefix}_avg"] = avg
            row[f"{prefix}_max"] = hi
        rows.append(row)
    return rows


# -- 1-minute frames ----------------------------------------------------------


def _empty_frame(fields) -> pd.DataFrame:
    return pd.DataFrame(
        columns=list(fields), index=pd.DatetimeIndex([], tz="UTC"), dtype="float64"
    )


def _to_list(values) -> List[Optional[float]]:
    """Float list with NaN as None, so the UI and JSON never see numpy."""
    return [None if np.isnan(v) else float(v) for v in np.asarray(values, dtype=float)]


def _utc_iso(ts) -> str:
    """Timestamp -> naive-UTC ISO string in the stored format."""
    return pd.Timestamp(ts).tz_convert("UTC").tz_localize(None).isoformat()


def readings_frame(
    readings: List[Dict], fields=FRAME_FIELDS, ts_key: str = "timestamp"
) -> pd.DataFrame:
    """Service reading rows -> float frame on a regular 1-minute UTC grid.

    One column per field (NaN where the row lacks it), the mean of the samples
    in each minute, and holes up to FRAME_FFILL_LIMIT minutes forward-filled so
    normal poll jitter leaves no gaps while an offline stretch stays NaN. The
    index is tz-aware UTC and runs from the first to the last sample. Rows with
    an unparseable timestamp are dropped; an empty input gives an empty frame
    with the same columns.
    """
    cols = list(fields)
    if not readings:
        return _empty_frame(cols)
    df = pd.DataFrame(readings, columns=[ts_key, *cols])
    ts = pd.to_datetime(df[ts_key], format="ISO8601", utc=True, errors="coerce")
    values = df[cols].apply(pd.to_numeric, errors="coerce").astype("float64")
    values.index = pd.DatetimeIndex(ts)
    values = values[values.index.notna()].sort_index()
    if values.empty:
        return _empty_frame(cols)
    return values.resample("1min").mean().ffill(limit=FRAME_FFILL_LIMIT)


def mean_frame(frames: List[pd.DataFrame]) -> pd.DataFrame:
    """Minute-by-minute mean across devices, ignoring the ones missing a minute."""
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return _empty_frame(FRAME_FIELDS)
    if len(frames) == 1:
        return frames[0]
    return pd.concat(frames).groupby(level=0).mean().sort_index()


# -- Relay events from state edges --------------------------------------------


def relay_events(
    edges: List[Dict], max_gap_s: float = MAX_SAMPLE_GAP_S
) -> Dict[int, List[Dict[str, Any]]]:
    """OFF->ON events per relay from readings_hyphae.get_relay_edges rows.

    An event starts at the first sample seen ON after a sample seen OFF no
    more than max_gap_s earlier (a switch across an offline gap has no usable
    time). off_ts is the first sample seen OFF afterwards when that sample is
    equally reliable, else None; next_on_ts is the relay's following event.
    Every relay with samples gets a key, even with no events.
    """
    out: Dict[int, List[Dict[str, Any]]] = {}
    open_event: Dict[int, Optional[Dict[str, Any]]] = {}
    for row in edges:
        n = row["relay_number"]
        events = out.setdefault(n, [])
        state = row.get("relay_state")
        gap = row.get("gap_s")
        reliable = (
            row.get("prev_state") is not None and gap is not None and gap <= max_gap_s
        )
        current = open_event.get(n)
        if current is not None:
            # Whatever this row is, the open ON run ends here: its end is only
            # known when this is a reliable OFF sample
            if state == 0 and reliable:
                current["off_ts"] = row["reading_ts"]
            open_event[n] = None
        if state == 1 and row.get("prev_state") == 0 and reliable:
            event = {"on_ts": row["reading_ts"], "off_ts": None, "next_on_ts": None}
            if events:
                events[-1]["next_on_ts"] = event["on_ts"]
            events.append(event)
            open_event[n] = event
    return out


def relay_on_intervals(
    edges: List[Dict], max_gap_s: float = MAX_SAMPLE_GAP_S
) -> Dict[int, List[Tuple[str, str]]]:
    """(start, end) stretches each relay was ON, from get_relay_edges rows.

    A run that was ON when the device went away ends at the last sample
    before the gap; a run still ON at the last sample ends there.
    """
    out: Dict[int, List[Tuple[str, str]]] = {}
    start_by_relay: Dict[int, Optional[str]] = {}

    def close(n, start, end):
        if start is not None and end is not None and end > start:
            out[n].append((start, end))
        start_by_relay[n] = None

    for row in edges:
        n = row["relay_number"]
        out.setdefault(n, [])
        ts = row["reading_ts"]
        gap = row.get("gap_s")
        start = start_by_relay.get(n)
        if start is not None and gap is not None and gap > max_gap_s:
            close(n, start, row.get("prev_ts") or ts)
            start = None
        if row.get("relay_state") == 1 and start is None:
            start_by_relay[n] = ts
            start = ts
        elif row.get("relay_state") == 0 and start is not None:
            close(n, start, ts)
            start = None
        if row.get("is_last") and start is not None:
            close(n, start, ts)
    return out


# -- Control response (superposed epochs) --------------------------------------


def _grid_positions(idx: pd.DatetimeIndex, stamps: List[str]) -> np.ndarray:
    """Row index in a 1-minute grid for each stamp, -1 when the minute is absent."""
    pos = np.full(len(stamps), -1, dtype=int)
    if len(stamps) == 0 or len(idx) == 0:
        return pos
    t = pd.to_datetime(stamps, format="ISO8601", utc=True, errors="coerce").floor("min")
    ok = ~pd.isna(t)
    if not ok.any():
        return pos
    found = np.asarray(idx.searchsorted(t[ok]))
    inside = found < len(idx)
    if inside.any():
        inside[inside] = idx.asi8[found[inside]] == t[ok].asi8[inside]
    found[~inside] = -1
    pos[np.flatnonzero(ok)] = found
    return pos


def _curve_stats(
    curve: np.ndarray, pre_min: int
) -> Tuple[Optional[float], Optional[int]]:
    """(delta, minutes to half of it) from a response curve; None when flat."""
    post = curve[pre_min + 1 :]
    if post.size == 0 or np.isnan(post).all():
        return None, None
    hi, lo = float(np.nanmax(post)), float(np.nanmin(post))
    delta = hi if abs(hi) >= abs(lo) else lo
    if delta == 0:
        return 0.0, None
    sign = np.sign(delta)
    hit = np.flatnonzero((np.sign(post) == sign) & (np.abs(post) >= 0.5 * abs(delta)))
    return delta, (int(hit[0]) + 1) if hit.size else None


def _event_deltas(residuals: np.ndarray) -> np.ndarray:
    """Per-event extreme of the post-event residuals (rows with data only)."""
    hi = np.nanmax(residuals, axis=1)
    lo = np.nanmin(residuals, axis=1)
    return np.where(np.abs(hi) >= np.abs(lo), hi, lo)


def _recovery_minutes(
    values: np.ndarray, pos_on: int, pos_off: int, limit: int
) -> Optional[int]:
    """Minutes after OFF until the metric is back halfway to its value at ON."""
    if pos_on < 0 or pos_off < 0 or pos_off <= pos_on or limit < RECOVERY_MIN_DATA_MIN:
        return None
    v_on, v_off = values[pos_on], values[pos_off]
    if np.isnan(v_on) or np.isnan(v_off) or v_on == v_off:
        return None
    window = values[pos_off : pos_off + limit + 1]
    if int((~np.isnan(window)).sum()) < RECOVERY_MIN_DATA_MIN:
        return None
    target = v_off - 0.5 * (v_off - v_on)
    back = window <= target if v_off > v_on else window >= target
    back[0] = False
    hit = np.flatnonzero(back)
    return int(hit[0]) if hit.size else None


def control_response(
    events: List[Dict],
    frame: pd.DataFrame,
    metrics=FRAME_FIELDS,
    pre_min: int = RESPONSE_PRE_MIN,
    post_min: int = RESPONSE_POST_MIN,
    recovery_max_min: int = RECOVERY_MAX_MIN,
) -> Dict[str, Any]:
    """Superposed-epoch response of one device's readings to one relay's events.

    Each event contributes the frame's values from -pre_min to +post_min
    minutes around its ON minute, relative to the value at t=0; epochs are
    averaged minute by minute (NaN-aware) into a curve per metric. Per metric:
    curve, its running sum and count (so pool_responses can merge devices
    exactly), delta (the curve's largest excursion after t=0), t50_min
    (minutes to half of it), recovery_min (median minutes after OFF to get
    halfway back, over the events where that is computable), the recovery
    values themselves, the number of events with post-event data and how many
    of those stayed under NO_RESPONSE_FLOOR. Event times are poll stamps, so
    t=0 is late by up to one poll interval.
    """
    offsets = list(range(-pre_min, post_min + 1))
    width = len(offsets)
    out: Dict[str, Any] = {
        "offsets": offsets,
        "events_total": len(events),
        "events_used": 0,
        "metrics": {
            m: {
                "curve": [None] * width,
                "sum": [0.0] * width,
                "count": [0] * width,
                "delta": None,
                "t50_min": None,
                "recovery_min": None,
                "recovery_values": [],
                "no_response": 0,
                "events_with_data": 0,
            }
            for m in metrics
        },
    }
    if not events or frame is None or frame.empty:
        return out

    idx = frame.index
    values = frame.reindex(columns=list(metrics)).to_numpy(dtype=float)
    n_rows = len(idx)
    pos_on = _grid_positions(idx, [e.get("on_ts") for e in events])
    inside = pos_on >= 0
    if not inside.any():
        return out
    events_in = [e for e, ok in zip(events, inside) if ok]
    pos = pos_on[inside]

    rows = pos[:, None] + np.asarray(offsets)[None, :]
    valid = (rows >= 0) & (rows < n_rows)
    epochs = np.full((len(pos), width, values.shape[1]), np.nan)
    epochs[valid] = values[rows[valid]]
    base = epochs[:, pre_min, :]
    residual = epochs - base[:, None, :]
    out["events_used"] = int((~np.isnan(base).all(axis=1)).sum())

    count = (~np.isnan(residual)).sum(axis=0)
    total = np.nansum(residual, axis=0)
    curve = np.divide(total, count, out=np.full_like(total, np.nan), where=count > 0)

    pos_off = _grid_positions(idx, [e.get("off_ts") or "" for e in events_in])
    pos_next = _grid_positions(idx, [e.get("next_on_ts") or "" for e in events_in])

    for j, m in enumerate(metrics):
        entry = out["metrics"][m]
        entry["curve"] = _to_list(curve[:, j])
        entry["sum"] = [float(v) for v in total[:, j]]
        entry["count"] = [int(v) for v in count[:, j]]
        entry["delta"], entry["t50_min"] = _curve_stats(curve[:, j], pre_min)

        post = residual[:, pre_min + 1 :, j]
        with_data = (~np.isnan(post)).sum(axis=1) >= post_min / 2
        entry["events_with_data"] = int(with_data.sum())
        if with_data.any():
            deltas = _event_deltas(post[with_data])
            entry["no_response"] = int(
                (np.abs(deltas) < NO_RESPONSE_FLOOR.get(m, 0.0)).sum()
            )

        recovered = []
        for k, event in enumerate(events_in):
            if not event.get("off_ts") or pos_off[k] < 0:
                continue
            limit = recovery_max_min
            if event.get("next_on_ts"):
                if pos_next[k] < 0:
                    continue
                limit = min(limit, int(pos_next[k] - pos_off[k]))
            minutes = _recovery_minutes(
                values[:, j], int(pos[k]), int(pos_off[k]), limit
            )
            if minutes is not None:
                recovered.append(minutes)
        entry["recovery_values"] = recovered
        if recovered:
            entry["recovery_min"] = float(np.median(recovered))
    return out


def pool_responses(results: List[Dict]) -> Dict[str, Any]:
    """Merge control_response results of several devices for the same relay.

    The pooled curve is the exact mean over every epoch of every device
    (sums and counts add), so it equals one run over the combined epochs.
    """
    results = [r for r in results if r and r.get("offsets")]
    if not results:
        return {"offsets": [], "events_total": 0, "events_used": 0, "metrics": {}}
    offsets = results[0]["offsets"]
    pre_min = -offsets[0]
    out: Dict[str, Any] = {
        "offsets": offsets,
        "events_total": max(r["events_total"] for r in results),
        "events_used": max(r["events_used"] for r in results),
        "metrics": {},
    }
    for m in results[0]["metrics"]:
        parts = [r["metrics"][m] for r in results if m in r["metrics"]]
        total = np.sum([np.asarray(p["sum"], dtype=float) for p in parts], axis=0)
        count = np.sum([np.asarray(p["count"], dtype=float) for p in parts], axis=0)
        curve = np.divide(
            total, count, out=np.full_like(total, np.nan), where=count > 0
        )
        delta, t50 = _curve_stats(curve, pre_min)
        recovered = [v for p in parts for v in p.get("recovery_values", [])]
        out["metrics"][m] = {
            "curve": _to_list(curve),
            "sum": [float(v) for v in total],
            "count": [int(v) for v in count],
            "delta": delta,
            "t50_min": t50,
            "recovery_min": float(np.median(recovered)) if recovered else None,
            "recovery_values": recovered,
            "no_response": sum(p["no_response"] for p in parts),
            "events_with_data": sum(p["events_with_data"] for p in parts),
        }
    return out


def daily_hours_vs_means(
    daily_hours: Dict[str, Dict[int, float]],
    daily: List[Dict],
    device_ids: List[int],
    relay_numbers: List[int],
) -> List[Dict[str, Any]]:
    """Scatter points: a Spore's daily mean CO2 / humidity against relay hours.

    daily_hours is relay_daily_hours output for the serving Hyphae; daily is
    daily_rows output (any devices; only the Spores in device_ids count). One
    point per (date, device, relay) where both sides have that date.
    """
    wanted = set(device_ids)
    points = []
    for row in daily:
        if row.get("source") != "spore" or row.get("device_id") not in wanted:
            continue
        hours = daily_hours.get(row["date"], {})
        for n in relay_numbers:
            if n not in hours:
                continue
            points.append(
                {
                    "date": row["date"],
                    "relay_number": n,
                    "device_id": row["device_id"],
                    "device": row["device"],
                    "hours": hours[n],
                    "co2_avg": row.get("co2_avg"),
                    "humidity_avg": row.get("humidity_avg"),
                }
            )
    return points


# -- Room comparison against a baseline Sentinel ------------------------------


def baseline_candidates(
    sentinels: List[Dict], room_id, farm_id, picked_ids=()
) -> List[Dict[str, Any]]:
    """Sentinels that can serve as the baseline for a room, best default first.

    Kept: Sentinels on the room's farm, Sentinels with no room (they belong
    to no farm in the schema, so they are offered rather than dropped), and
    any explicitly picked ones. Order: other rooms on the farm, then no room,
    then the selected room itself (an in-room baseline only shows the
    gradient inside the room).
    """
    picked = set(picked_ids or ())
    other, roomless, same = [], [], []
    for s in sentinels:
        sid = s["device_id"]
        s_room = s.get("room_id")
        on_farm = farm_id is not None and s.get("farm_id") == farm_id
        if not (on_farm or s_room is None or sid in picked):
            continue
        name = s.get("device_name") or f"Sentinel {sid}"
        entry = {
            "device_id": sid,
            "label": f"{name} · {s.get('room_name') or 'no room'}",
            "room_id": s_room,
            "same_room": room_id is not None and s_room == room_id,
        }
        if s_room is None:
            roomless.append(entry)
        elif entry["same_room"]:
            same.append(entry)
        else:
            other.append(entry)
    for group in (other, roomless, same):
        group.sort(key=lambda e: e["label"])
    return other + roomless + same


def room_baseline_diff(
    room: pd.DataFrame,
    baseline: pd.DataFrame,
    tz_name: str,
    metrics=("co2", "humidity"),
) -> Dict[str, Dict[str, Any]]:
    """Hourly (room - baseline) as a local date x hour-of-day matrix per metric.

    {metric: {dates, hours, z, n}} with z[date][hour] None where either side
    has no data that hour, or {metric: {"reason": ...}} when the two overlap
    for fewer than HEATMAP_MIN_OVERLAP_MIN minutes.
    """
    zone = _zone(tz_name)
    out: Dict[str, Dict[str, Any]] = {}
    for m in metrics:
        if m not in room.columns or m not in baseline.columns:
            out[m] = {"reason": "not measured by both sides"}
            continue
        diff = (room[m] - baseline[m]).dropna()
        n = int(len(diff))
        if n < HEATMAP_MIN_OVERLAP_MIN:
            out[m] = {"reason": f"only {n} overlapping minutes of data"}
            continue
        hourly = diff.tz_convert(zone).resample("h").mean().dropna()
        table = (
            hourly.groupby([hourly.index.date, hourly.index.hour])
            .mean()
            .unstack()
            .reindex(columns=range(24))
        )
        out[m] = {
            "dates": [d.isoformat() for d in table.index],
            "hours": list(range(24)),
            "z": [_to_list(row) for row in table.to_numpy(dtype=float)],
            "n": n,
        }
    return out


def lag_xcorr(
    x: pd.Series,
    y: pd.Series,
    max_lag: int = XCORR_MAX_LAG_MIN,
    min_pairs: int = XCORR_MIN_PAIRS,
    detrend_min: int = XCORR_DETREND_MIN,
) -> Dict[str, Any]:
    """Correlation of x(t) with y(t - lag) for lags in +-max_lag minutes.

    A positive peak lag means x follows y. Both series are high-passed by
    subtracting a centred detrend_min rolling mean first (0 disables). corr
    holds None at lags with fewer than min_pairs overlapping minutes; the
    peak is the largest correlation.
    """
    lags = list(range(-max_lag, max_lag + 1))
    out: Dict[str, Any] = {
        "lags": lags,
        "corr": [None] * len(lags),
        "peak_lag": None,
        "peak_corr": None,
        "n": 0,
        "reason": None,
    }
    if x is None or y is None or x.empty or y.empty:
        out["reason"] = "no data on one side"
        return out
    x, y = x.align(y, join="inner")
    n = int((x.notna() & y.notna()).sum())
    out["n"] = n
    if n < min_pairs:
        out["reason"] = f"only {n} overlapping minutes of CO2 data"
        return out
    if detrend_min:
        window = f"{int(detrend_min)}min"
        periods = max(1, int(detrend_min) // 2)
        x = x - x.rolling(window, center=True, min_periods=periods).mean()
        y = y - y.rolling(window, center=True, min_periods=periods).mean()
    a = x.to_numpy(dtype=float)
    b = y.to_numpy(dtype=float)
    size = len(a)
    corr: List[Optional[float]] = []
    for lag in lags:
        if lag >= 0:
            p, q = a[lag:], b[: size - lag]
        else:
            p, q = a[: size + lag], b[-lag:]
        mask = ~(np.isnan(p) | np.isnan(q))
        if int(mask.sum()) < min_pairs:
            corr.append(None)
            continue
        p = p[mask] - p[mask].mean()
        q = q[mask] - q[mask].mean()
        den = math.sqrt(float(p @ p) * float(q @ q))
        corr.append(float(p @ q) / den if den > 0 else None)
    out["corr"] = corr
    scored = [(c, lag) for c, lag in zip(corr, lags) if c is not None]
    if not scored:
        out["reason"] = "too little overlap at every lag"
        return out
    out["peak_corr"], out["peak_lag"] = max(scored)
    return out


# -- Sensor agreement -----------------------------------------------------------


def pair_agreement(
    frame_a: pd.DataFrame,
    frame_b: pd.DataFrame,
    tz_name: str,
    metrics=FRAME_FIELDS,
    window_min: int = AGREEMENT_WINDOW_MIN,
    slope_window_min: int = AGREEMENT_SLOPE_WINDOW_MIN,
    plot_step: str = AGREEMENT_PLOT_STEP,
) -> Dict[str, Dict[str, Any]]:
    """Rolling median and drift of (a - b) per metric.

    Per metric: t (naive local datetimes at plot_step), median (rolling
    window_min-minute median of the difference), slope (rolling least-squares
    slope over slope_window_min, units per day), overall_slope_per_day, and
    abs_median_sorted (every minute's |median|, sorted, so a caller can count
    the share of time outside any band without recomputing). Temperature
    stays in Celsius. {"reason": ...} when the two overlap too little.
    """
    zone = _zone(tz_name)
    out: Dict[str, Dict[str, Any]] = {}
    for m in metrics:
        if m not in frame_a.columns or m not in frame_b.columns:
            out[m] = {"reason": "not measured by both"}
            continue
        diff = frame_a[m] - frame_b[m]
        n = int(diff.notna().sum())
        if n < window_min:
            out[m] = {"reason": f"only {n} overlapping minutes of data"}
            continue
        diff = diff.loc[diff.first_valid_index() : diff.last_valid_index()]
        median = diff.rolling(
            f"{window_min}min", center=True, min_periods=max(1, window_min // 2)
        ).median()

        # Rolling slope from rolling means of t, d, t*d and t*t over the same
        # non-NaN minutes: cov(t, d) / var(t), in days
        t = pd.Series(
            (diff.index - diff.index[0]) / pd.Timedelta(days=1), index=diff.index
        )
        t = t.where(diff.notna())
        parts = pd.DataFrame({"t": t, "d": diff, "td": t * diff, "tt": t * t})
        roll = parts.rolling(
            f"{slope_window_min}min",
            center=True,
            min_periods=max(2, slope_window_min // 4),
        ).mean()
        var_t = roll["tt"] - roll["t"] ** 2
        slope = (roll["td"] - roll["t"] * roll["d"]) / var_t.where(var_t > 1e-12)

        mask = diff.notna().to_numpy()
        overall = None
        if int(mask.sum()) >= 2:
            overall = float(
                np.polyfit(
                    t.to_numpy(dtype=float)[mask], diff.to_numpy(dtype=float)[mask], 1
                )[0]
            )

        plot = (
            pd.DataFrame({"median": median, "slope": slope}).resample(plot_step).mean()
        )
        out[m] = {
            "t": plot.index.tz_convert(zone).tz_localize(None).to_pydatetime().tolist(),
            "median": _to_list(plot["median"].to_numpy()),
            "slope": _to_list(plot["slope"].to_numpy()),
            "overall_slope_per_day": overall,
            "abs_median_sorted": np.sort(median.dropna().abs().to_numpy()).tolist(),
            "n": n,
        }
    return out


def device_anomalies(
    frame: pd.DataFrame,
    tz_name: str,
    metrics=FRAME_FIELDS,
    z_thresh: float = ANOMALY_Z,
    min_samples: int = ANOMALY_MIN_SAMPLES,
    merge_gap_min: int = ANOMALY_MERGE_GAP_MIN,
    min_run_min: int = ANOMALY_MIN_RUN_MIN,
    max_intervals: int = ANOMALY_MAX_INTERVALS,
) -> Dict[str, Any]:
    """Minutes that stray from a device's own hour-of-day pattern.

    Per metric the baseline is the median at each local hour of day over the
    period; the residual is scaled by a robust sigma (1.4826 x MAD, so the
    spikes being hunted do not inflate it) and minutes with |z| above
    z_thresh are grouped into intervals (gaps up to merge_gap_min join, runs
    shorter than min_run_min are dropped). Intervals carry naive-UTC bounds,
    the span in minutes, the peak z and the raw value there (Celsius for
    temperature); sorted by |peak z|, capped at max_intervals. skipped names
    the metrics that could not be scored and why.
    """
    out: Dict[str, Any] = {
        "intervals": [],
        "sigma": {},
        "skipped": {},
        "truncated": False,
    }
    if frame is None or frame.empty:
        out["skipped"] = {m: "no readings" for m in metrics}
        return out
    local = frame.tz_convert(_zone(tz_name))
    intervals = []
    for m in metrics:
        if m not in local.columns:
            out["skipped"][m] = "not measured"
            continue
        series = local[m]
        if int(series.notna().sum()) < min_samples:
            out["skipped"][m] = f"fewer than {min_samples // 60} h of samples"
            continue
        residual = series - series.groupby(series.index.hour).transform("median")
        mad = (residual - residual.median()).abs().median()
        sigma = 1.4826 * float(mad) if pd.notna(mad) else 0.0
        if not sigma > 0:
            out["skipped"][m] = "no variation to score against"
            continue
        out["sigma"][m] = sigma
        z = (residual / sigma).to_numpy(dtype=float)
        flagged = np.flatnonzero(np.abs(z) > z_thresh)
        if flagged.size == 0:
            continue
        breaks = np.flatnonzero(np.diff(flagged) > merge_gap_min + 1) + 1
        for run in np.split(flagged, breaks):
            span = int(run[-1] - run[0] + 1)
            if span < min_run_min:
                continue
            k = int(run[np.argmax(np.abs(z[run]))])
            intervals.append(
                {
                    "metric": m,
                    "start_utc": _utc_iso(local.index[int(run[0])]),
                    "end_utc": _utc_iso(local.index[int(run[-1])]),
                    "minutes": span,
                    "peak_z": float(z[k]),
                    "peak_value": float(series.iloc[k]),
                }
            )
    intervals.sort(key=lambda i: -abs(i["peak_z"]))
    out["truncated"] = len(intervals) > max_intervals
    out["intervals"] = intervals[:max_intervals]
    return out
