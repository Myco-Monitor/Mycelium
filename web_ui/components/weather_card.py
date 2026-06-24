"""
OpenWeatherMap weather card component for the Mycelium dashboard.

Displays current weather conditions with smart polling:
- Initial fetch on page load
- Uses the OWM `dt` field to calculate when the next 10-min update will occur
- Aligns subsequent polls to OWM's 10-minute update cadence
- Stays well within free tier limits (~144 calls/day)
"""

import time
import logging
import requests
from typing import Optional, Dict

from nicegui import ui, app

from web_ui.format import fmt_time

logger = logging.getLogger(__name__)

OWM_UPDATE_INTERVAL = 600  # OWM updates every 10 minutes
OWM_API_URL = "https://api.openweathermap.org/data/2.5/weather"


def _get_owm_credentials(user_id: int) -> Optional[Dict[str, str]]:
    """Load OWM API key and ZIP from user settings. Returns None if not configured."""
    try:
        from storage.tables.user_settings import get_user_setting

        info = get_user_setting(user_id)
        if not info:
            return None
        api_key = info.get("owm_api_key", "").strip()
        zip_code = info.get("owm_zip_code", "").strip()
        if api_key and zip_code:
            return {"api_key": api_key, "zip": zip_code}
    except Exception:
        pass
    return None


def _fetch_weather(
    api_key: str, zip_code: str, units: str = "metric"
) -> Optional[Dict]:
    """
    Fetch current weather from OWM. Returns the raw JSON response.
    The `dt` field is the Unix timestamp of when OWM last calculated the data.
    """
    try:
        r = requests.get(
            OWM_API_URL,
            params={
                "appid": api_key,
                "zip": f"{zip_code},us",
                "units": units,
            },
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
        logger.warning(f"OWM returned {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logger.warning(f"OWM fetch failed: {e}")
    return None


def _seconds_until_next_update(dt_unix: int) -> float:
    """
    Calculate seconds until OWM's next 10-minute data update.

    OWM updates data roughly every 10 minutes, aligned to the `dt` timestamp.
    We add a 30-second buffer so the new data is actually available.
    """
    now = time.time()
    elapsed_since_dt = now - dt_unix
    next_update_in = OWM_UPDATE_INTERVAL - (elapsed_since_dt % OWM_UPDATE_INTERVAL)
    # Add 30s buffer — OWM needs a moment after the interval to publish
    return max(next_update_in + 30, 10)


def _spore_altitudes() -> list:
    """Distinct altitudes (m) configured on weather-pressure-enabled Spores, sorted.

    The card is location-level but altitude is per-Spore, so show one adjusted
    figure per distinct altitude (usually one; more if Spores differ).
    """
    try:
        from storage.tables.device_spore import get_all_device_spore

        alts = {
            s.get("altitude_m")
            for s in get_all_device_spore()
            if s.get("weather_pressure_enabled") and s.get("altitude_m") is not None
        }
        return sorted(alts)
    except Exception:
        return []


def _pressure_cell(main: Dict, altitudes: list):
    """Render the Pressure stat: ground-level by default, the altitude-adjusted
    station pressure per configured altitude, and sea-level in a tooltip."""
    from api.services.pressure_distribution_service import (
        sea_level_to_station_pressure,
    )

    sea = main.get("pressure")
    grnd = main.get("grnd_level")
    primary = grnd if grnd is not None else sea

    with ui.column().classes("items-center gap-0"):
        ui.icon("speed", size="xs").classes("text-muted")
        ui.label(f"{primary} hPa" if primary is not None else "—").classes(
            "text-weight-bold text-caption"
        )
        if sea is not None:
            for alt in altitudes:
                adjusted = round(sea_level_to_station_pressure(sea, alt))
                ui.label(f"{adjusted} hPa @ {alt:.0f} m").classes(
                    "text-caption text-muted"
                )
        label = "Pressure (ground)" if grnd is not None else "Pressure"
        cell_label = ui.label(label).classes("text-caption text-muted")
        if sea is not None:
            cell_label.tooltip(f"Sea-level: {sea} hPa")


def weather_card(colors: dict):
    """
    Render the OWM weather card on the dashboard.
    Only renders if the user has OWM credentials configured.
    Sets up a smart timer aligned to OWM's 10-minute update cadence.
    """
    user_id = app.storage.user.get("user_id")
    if not user_id:
        return

    creds = _get_owm_credentials(user_id)
    if not creds:
        return  # No credentials — don't render anything

    # Get user's temp preference
    try:
        from storage.tables.user_settings import get_user_setting

        info = get_user_setting(user_id)
        temp_pref = info.get("temp_pref", "C") if info else "C"
    except Exception:
        temp_pref = "C"

    units = "metric" if temp_pref == "C" else "imperial"
    temp_unit = "\u00b0C" if temp_pref == "C" else "\u00b0F"
    speed_unit = "m/s" if temp_pref == "C" else "mph"

    # Timer state — stored in a mutable dict so the timer callback can update it
    timer_state = {"next_poll": 0}

    @ui.refreshable
    def weather_content():
        data = _fetch_weather(creds["api_key"], creds["zip"], units)
        if not data:
            ui.label(
                "Unable to fetch weather data. Check your API key and ZIP code in Settings."
            ).classes("text-muted")
            # Retry in 60 seconds
            timer_state["next_poll"] = 60
            return

        # Parse response
        main = data.get("main", {})
        weather = data.get("weather", [{}])[0]
        wind = data.get("wind", {})
        sys_data = data.get("sys", {})
        dt_unix = data.get("dt", 0)
        city = data.get("name", "Unknown")

        temp = main.get("temp", 0)
        feels_like = main.get("feels_like", 0)
        humidity = main.get("humidity", 0)
        wind_speed = wind.get("speed", 0)
        wind_deg = wind.get("deg", 0)
        description = weather.get("description", "").capitalize()
        icon_code = weather.get("icon", "01d")

        # Sunrise/sunset (honor 12/24h preference)
        sunrise = fmt_time(sys_data.get("sunrise"))
        sunset = fmt_time(sys_data.get("sunset"))

        # Data timestamp
        data_time = fmt_time(dt_unix)

        # Calculate next poll interval
        if dt_unix:
            timer_state["next_poll"] = _seconds_until_next_update(dt_unix)
        else:
            timer_state["next_poll"] = OWM_UPDATE_INTERVAL

        # Wind direction arrow
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        wind_dir = directions[round(wind_deg / 45) % 8]

        # Render — centered top section
        with ui.row().classes("w-full items-center justify-center gap-4"):
            ui.image(f"https://openweathermap.org/img/wn/{icon_code}@2x.png").classes(
                "w-16 h-16"
            )

            with ui.column().classes("gap-0 items-center"):
                ui.label(city).classes("text-subtitle1 text-weight-bold")
                ui.label(f"{temp:.0f}{temp_unit}").classes("text-h4")
                ui.label(f"Feels like {feels_like:.0f}{temp_unit}").classes(
                    "text-caption text-muted"
                )
                ui.label(description).classes("text-caption")
                ui.label(f"Data as of {data_time} \u2022 Updates every 10 min").classes(
                    "text-caption text-muted"
                )

        ui.separator().classes("q-my-sm")

        # Detail stats — horizontal row
        altitudes = _spore_altitudes()
        with ui.row().classes("w-full justify-around flex-wrap gap-2"):
            _weather_stat("water_drop", "Humidity", f"{humidity}%")
            _pressure_cell(main, altitudes)
            _weather_stat("air", "Wind", f"{wind_speed} {speed_unit} {wind_dir}")
            _weather_stat("wb_sunny", "Sunrise", sunrise)
            _weather_stat("nights_stay", "Sunset", sunset)

    # Render the card with header + refreshable content
    with ui.card().classes("w-full p-4"):
        with ui.row().classes("w-full items-center gap-2 q-mb-sm"):
            ui.icon("cloud", size="sm").style(f"color: {colors['primary']}")
            ui.label("Local Weather").classes("text-h6")

        weather_content()

    # Smart timer — first poll aligns to OWM's cadence, then every 10 min
    def _poll_weather():
        weather_content.refresh()

    # Initial refresh is already done above. Set timer for next update.
    # We use a 10-second initial timer that then self-adjusts.
    poll_timer = ui.timer(OWM_UPDATE_INTERVAL, _poll_weather, active=False)

    def _start_aligned_timer():
        """After first fetch, align timer to OWM's update cadence."""
        interval = timer_state.get("next_poll", OWM_UPDATE_INTERVAL)
        logger.info(f"OWM: next poll in {interval:.0f}s")
        poll_timer.interval = interval
        poll_timer.activate()

    # Kick off the aligned timer after a brief delay (let first render complete)
    ui.timer(2.0, _start_aligned_timer, once=True)


def _weather_stat(icon: str, label: str, value: str):
    """Render a small weather stat cell."""
    with ui.column().classes("items-center gap-0"):
        ui.icon(icon, size="xs").classes("text-muted")
        ui.label(value).classes("text-weight-bold text-caption")
        ui.label(label).classes("text-caption text-muted")
