"""
Report maths for the Analytics Reports tab.

Pure functions over rows already fetched from storage: no database access,
no UI, no app.storage, so everything here is safe inside nicegui.run.io_bound
and can be exercised offline against any rows. The page passes the user's
time zone and temperature unit in explicitly.

Compliance uses only the user's own alert rules (threshold_high /
threshold_low). Mycelium stores no generic CO2 / humidity / temperature
targets — they are species-specific — so a metric without a rule reports
"no rule" rather than a made-up band.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger("services.ReportService")

# Samples further apart than this mean the device was offline: the gap counts
# as neither ON nor OFF for relays, and ends an excursion run for compliance.
MAX_SAMPLE_GAP_S = 300

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
