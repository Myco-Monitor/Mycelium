"""User-preference-aware date/time formatting for the web UI.

Honors the user's `timezone_name` and `time_format` ('12' or '24') settings so
every page renders clock times consistently, mirroring how temperature units
are handled. Inputs may be a datetime, a unix timestamp (int/float), or an ISO
string ("YYYY-MM-DD HH:MM:SS").

All persisted timestamps are naive UTC (see storage.db_utils.get_timestamp);
naive inputs are therefore interpreted as UTC and converted to the user's
timezone for display.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from nicegui import app

# Older settings stored legacy tzdata aliases; Debian trixie ships those only
# in the optional tzdata-legacy package, so map them to canonical IANA names.
LEGACY_TZ_ALIASES = {
    "US/Eastern": "America/New_York",
    "US/Central": "America/Chicago",
    "US/Mountain": "America/Denver",
    "US/Pacific": "America/Los_Angeles",
    "US/Alaska": "America/Anchorage",
    "US/Hawaii": "Pacific/Honolulu",
    "US/Arizona": "America/Phoenix",
}

DEFAULT_TIMEZONE = "America/New_York"


def canonical_tz(name) -> str:
    """Map a stored timezone name to its canonical IANA form."""
    return LEGACY_TZ_ALIASES.get(name, name) if name else DEFAULT_TIMEZONE


def get_time_format() -> str:
    """Return the user's time format preference: '12' or '24' (default '24').

    Cached in per-session storage to avoid a DB read on every formatted value
    (these helpers are called in tight loops — table rows, error lists, etc.).
    """
    try:
        cached = app.storage.user.get("time_format")
        if cached in ("12", "24"):
            return cached

        from storage.tables.user_settings import get_user_setting

        uid = app.storage.user.get("user_id")
        info = get_user_setting(uid) if uid else None
        pref = info.get("time_format") if info else None
        pref = pref if pref in ("12", "24") else "24"
        try:
            app.storage.user["time_format"] = pref
        except Exception:
            pass
        return pref
    except Exception:
        return "24"


def get_timezone_name() -> str:
    """Return the user's timezone preference as a canonical IANA name.

    Cached in per-session storage like get_time_format().
    """
    try:
        cached = app.storage.user.get("timezone_name")
        if cached:
            return canonical_tz(cached)

        from storage.tables.user_settings import get_user_setting

        uid = app.storage.user.get("user_id")
        info = get_user_setting(uid) if uid else None
        pref = canonical_tz(info.get("timezone_name") if info else None)
        try:
            app.storage.user["timezone_name"] = pref
        except Exception:
            pass
        return pref
    except Exception:
        return DEFAULT_TIMEZONE


def _user_zone():
    """ZoneInfo for the user's timezone, or None if tzdata can't resolve it."""
    try:
        return ZoneInfo(get_timezone_name())
    except Exception:
        return None


def _to_datetime(value):
    """Coerce a datetime / unix timestamp / ISO string to a datetime, or None."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    if isinstance(value, str):
        s = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(s[:19], fmt)
                except ValueError:
                    continue
    return None


def to_user_dt(value):
    """Coerce a timestamp to an aware datetime in the user's timezone.

    Naive inputs are interpreted as UTC (the storage convention). Returns None
    if the value can't be parsed.
    """
    dt = _to_datetime(value)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    zone = _user_zone()
    return dt.astimezone(zone) if zone else dt


def fmt_time(value, seconds: bool = False, fallback: str = "—") -> str:
    """Format the time-of-day portion per the user's timezone + 12/24h prefs."""
    dt = to_user_dt(value)
    if dt is None:
        return str(value) if value else fallback
    if get_time_format() == "12":
        out = dt.strftime("%I:%M:%S %p" if seconds else "%I:%M %p")
        return out[1:] if out.startswith("0") else out  # 08:30 PM -> 8:30 PM
    return dt.strftime("%H:%M:%S" if seconds else "%H:%M")


def fmt_datetime(value, seconds: bool = False, fallback: str = "—") -> str:
    """Format a full date + time per the user's timezone + 12/24h prefs."""
    dt = to_user_dt(value)
    if dt is None:
        return str(value) if value else fallback
    return f"{dt.strftime('%Y-%m-%d')} {fmt_time(dt, seconds=seconds)}"
