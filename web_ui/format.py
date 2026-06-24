"""User-preference-aware date/time formatting for the web UI.

Honors the user's `time_format` setting ('12' or '24') so every page renders
clock times consistently, mirroring how temperature units are handled. Inputs may
be a datetime, a unix timestamp (int/float), or an ISO string ("YYYY-MM-DD HH:MM:SS").
"""

from datetime import datetime

from nicegui import app


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


def _to_datetime(value):
    """Coerce a datetime / unix timestamp / ISO string to a datetime, or None."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
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


def fmt_time(value, seconds: bool = False, fallback: str = "—") -> str:
    """Format the time-of-day portion per the user's 12/24h preference."""
    dt = _to_datetime(value)
    if dt is None:
        return str(value) if value else fallback
    if get_time_format() == "12":
        out = dt.strftime("%I:%M:%S %p" if seconds else "%I:%M %p")
        return out[1:] if out.startswith("0") else out  # 08:30 PM -> 8:30 PM
    return dt.strftime("%H:%M:%S" if seconds else "%H:%M")


def fmt_datetime(value, seconds: bool = False, fallback: str = "—") -> str:
    """Format a full date + time per the user's 12/24h preference."""
    dt = _to_datetime(value)
    if dt is None:
        return str(value) if value else fallback
    return f"{dt.strftime('%Y-%m-%d')} {fmt_time(dt, seconds=seconds)}"
