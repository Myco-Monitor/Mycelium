"""
Polling Service for Mycelium

This module provides services for polling devices for data, including:
- Configurable polling intervals
- Error handling and recovery
- Device status tracking
- Automatic retry with exponential backoff
"""

import asyncio
import logging
import random
from typing import Dict, Any
from datetime import datetime, timedelta

from api.services.spore_service import SporeDataService
from api.services.hyphae_service import HyphaeDataService
from api.services.weather_service import WeatherDataService
from api.services.pressure_service import PressureDataService
from api.services.pressure_distribution_service import PressureDistributionService
from api.services.alert_service import AlertService
from api.services.notification_service import NotificationService
from api.clients.base_client import is_resolution_error, RESOLUTION_GRACE
from storage.tables.device_spore import (
    get_all_device_spore,
    update_device_status as update_spore_status,
)
from storage.tables.device_hyphae import (
    get_all_device_hyphae,
    update_device_status as update_hyphae_status,
)


class PollingService:
    """
    Service for polling devices for data.

    This service is responsible for:
    - Periodically polling devices for data
    - Handling errors and retrying failed requests
    - Tracking device status
    - Configuring polling intervals
    """

    def __init__(self):
        """Initialize the polling service."""
        self.logger = logging.getLogger("api.PollingService")

        # Initialize services
        self.spore_service = SporeDataService()
        self.hyphae_service = HyphaeDataService()
        self.weather_service = WeatherDataService()
        self.pressure_service = PressureDataService()
        self.pressure_distribution = PressureDistributionService()
        self.alert_service = AlertService()
        self.notification_service = NotificationService()

        # Polling configuration - load from app_config.json
        import json
        from pathlib import Path

        config_path = Path(__file__).parent.parent.parent / "config" / "app_config.json"
        try:
            with open(config_path) as f:
                config = json.load(f)
            self.polling_config = config.get(
                "polling",
                {
                    "spore": {
                        "interval": 60,
                        "jitter": 5,
                        "backoff_factor": 2,
                        "max_backoff": 3600,
                        "enabled": True,
                    },
                    "hyphae": {
                        "interval": 60,
                        "jitter": 5,
                        "backoff_factor": 2,
                        "max_backoff": 3600,
                        "enabled": True,
                    },
                    "weather": {
                        "interval": 1800,
                        "jitter": 60,
                        "backoff_factor": 2,
                        "max_backoff": 14400,
                        "enabled": True,
                    },
                    "pressure": {
                        "interval": 300,
                        "jitter": 30,
                        "backoff_factor": 2,
                        "max_backoff": 3600,
                        "enabled": True,
                    },
                    "alerts": {"interval": 60, "jitter": 5, "enabled": True},
                },
            )
        except Exception as e:
            print(f"Warning: Could not load polling config from app_config.json: {e}")
            self.polling_config = {
                "spore": {
                    "interval": 60,
                    "jitter": 5,
                    "backoff_factor": 2,
                    "max_backoff": 3600,
                    "enabled": True,
                },
                "hyphae": {
                    "interval": 60,
                    "jitter": 5,
                    "backoff_factor": 2,
                    "max_backoff": 3600,
                    "enabled": True,
                },
                "weather": {
                    "interval": 1800,
                    "jitter": 60,
                    "backoff_factor": 2,
                    "max_backoff": 14400,
                    "enabled": True,
                },
                "pressure": {
                    "interval": 300,
                    "jitter": 30,
                    "backoff_factor": 2,
                    "max_backoff": 3600,
                    "enabled": True,
                },
                "alerts": {"interval": 60, "jitter": 5, "enabled": True},
            }

        # Device status tracking
        self.device_status = {
            "spore": {},  # device_id -> {"online": bool, "last_success": datetime, "failures": int, "next_poll": datetime}
            "hyphae": {},
            "weather": {},
            "pressure": {},
        }

        # Tasks
        self.polling_tasks = {}
        self.running = False

    async def start(self):
        """Start the polling service."""
        if self.running:
            self.logger.warning("Polling service is already running")
            return

        self.running = True
        self.logger.info("Starting polling service")

        # Start polling tasks
        if self.polling_config["spore"]["enabled"]:
            self.polling_tasks["spore"] = asyncio.create_task(
                self._poll_spore_devices()
            )

        if self.polling_config["hyphae"]["enabled"]:
            self.polling_tasks["hyphae"] = asyncio.create_task(
                self._poll_hyphae_devices()
            )

        if self.polling_config["weather"]["enabled"]:
            self.polling_tasks["weather"] = asyncio.create_task(self._poll_weather())

        if self.polling_config["pressure"]["enabled"]:
            self.polling_tasks["pressure"] = asyncio.create_task(
                self._poll_pressure_devices()
            )

        if self.polling_config.get("alerts", {}).get("enabled", True):
            self.polling_tasks["alerts"] = asyncio.create_task(self._check_alerts())

    async def stop(self):
        """Stop the polling service."""
        if not self.running:
            self.logger.warning("Polling service is not running")
            return

        self.running = False
        self.logger.info("Stopping polling service")

        # Cancel all polling tasks
        for task_name, task in self.polling_tasks.items():
            if not task.done():
                task.cancel()

        # Wait for tasks to complete
        for task_name, task in self.polling_tasks.items():
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.polling_tasks = {}

    def configure_polling(self, device_type: str, config: Dict[str, Any]):
        """
        Configure polling for a device type.

        Args:
            device_type (str): Type of device ("spore", "hyphae", "weather")
            config (Dict[str, Any]): Polling configuration
        """
        if device_type not in self.polling_config:
            self.logger.error(f"Unknown device type: {device_type}")
            return

        # Update the configuration
        for key, value in config.items():
            if key in self.polling_config[device_type]:
                self.polling_config[device_type][key] = value

        self.logger.info(
            f"Updated polling configuration for {device_type}: {self.polling_config[device_type]}"
        )

    async def _poll_spore_devices(self):
        """Poll all Spore devices for data."""
        self.logger.info("Starting Spore device polling")

        while self.running:
            try:
                # Get all Spore devices
                devices = get_all_device_spore()

                # Poll each device
                for device in devices:
                    device_id = device["device_id"]

                    # Check if we should poll this device
                    if not self._should_poll_device("spore", device_id):
                        continue

                    # Poll the device
                    try:
                        self.logger.debug(f"Polling Spore device {device_id}")

                        # Initialize the client if needed
                        if device_id not in self.spore_service.clients:
                            await self.spore_service.initialize_client(device_id)

                        # Get the latest reading (raises on failure)
                        await self.spore_service.get_latest_reading(device_id)

                        # Update device status
                        self._update_device_status("spore", device_id, True)

                        self.logger.debug(
                            f"Successfully polled Spore device {device_id}"
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Error polling Spore device {device_id}: {e}"
                        )

                        # Update device status (error drives transient-vs-real handling)
                        self._update_device_status("spore", device_id, False, e)

                # Sleep until the next polling interval
                await asyncio.sleep(self._get_polling_interval("spore"))
            except Exception as e:
                self.logger.error(f"Error in Spore polling loop: {e}")

                # Sleep for a short time before retrying
                await asyncio.sleep(5)

    async def _poll_hyphae_devices(self):
        """Poll all Hyphae devices for data."""
        self.logger.info("Starting Hyphae device polling")

        while self.running:
            try:
                # Get all Hyphae devices
                devices = get_all_device_hyphae()

                # Poll each device
                for device in devices:
                    device_id = device["device_id"]

                    # Check if we should poll this device
                    if not self._should_poll_device("hyphae", device_id):
                        continue

                    # Poll the device
                    try:
                        self.logger.debug(f"Polling Hyphae device {device_id}")

                        # Initialize the client if needed
                        if device_id not in self.hyphae_service.clients:
                            await self.hyphae_service.initialize_client(device_id)

                        # Get the latest reading (raises on failure)
                        await self.hyphae_service.get_latest_reading(device_id)

                        # Update device status
                        self._update_device_status("hyphae", device_id, True)

                        self.logger.debug(
                            f"Successfully polled Hyphae device {device_id}"
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Error polling Hyphae device {device_id}: {e}"
                        )

                        # Update device status (error drives transient-vs-real handling)
                        self._update_device_status("hyphae", device_id, False, e)

                # Sleep until the next polling interval
                await asyncio.sleep(self._get_polling_interval("hyphae"))
            except Exception as e:
                self.logger.error(f"Error in Hyphae polling loop: {e}")

                # Sleep for a short time before retrying
                await asyncio.sleep(5)

    async def _poll_weather(self):
        """Poll weather data."""
        self.logger.info("Starting weather polling")

        while self.running:
            try:
                # Get all weather locations
                locations = self._get_weather_locations()

                # Poll each location
                for location_id, location in locations.items():
                    # Check if we should poll this location
                    if not self._should_poll_device("weather", location_id):
                        continue

                    # Poll the location
                    try:
                        self.logger.debug(f"Polling weather for location {location_id}")

                        # Initialize the client if needed
                        if location_id not in self.weather_service.clients:
                            self.weather_service.initialize_client(
                                location_id=location_id,
                                api_key=location["api_key"],
                                location=location["location"],
                                units=location.get("units", "metric"),
                            )

                        # Get the current weather
                        weather = await self.weather_service.get_current_weather(
                            location_id
                        )

                        # Update device status
                        self._update_device_status("weather", location_id, True)

                        self.logger.debug(
                            f"Successfully polled weather for location {location_id}"
                        )

                        # Relay ambient pressure to opted-in Spores that have no
                        # local Hyphae barometer (weather-as-pressure-source feature).
                        farm_id = location.get("farm_id")
                        if weather and farm_id is not None:
                            await (
                                self.pressure_distribution.distribute_weather_pressure(
                                    farm_id,
                                    weather.get("pressure"),
                                    weather.get("pressure_grnd"),
                                )
                            )
                    except Exception as e:
                        self.logger.error(
                            f"Error polling weather for location {location_id}: {e}"
                        )

                        # Update device status
                        self._update_device_status("weather", location_id, False)

                # Sleep until the next polling interval
                await asyncio.sleep(self._get_polling_interval("weather"))
            except Exception as e:
                self.logger.error(f"Error in weather polling loop: {e}")

                # Sleep for a short time before retrying
                await asyncio.sleep(5)

    async def _poll_pressure_devices(self):
        """Poll all Hyphae devices for BMP581 pressure data."""
        self.logger.info("Starting pressure device polling")

        while self.running:
            try:
                # Get all Hyphae devices (pressure comes from Hyphae)
                devices = get_all_device_hyphae()

                # Poll each device for pressure
                for device in devices:
                    device_id = device["device_id"]

                    # Check if we should poll this device
                    if not self._should_poll_device("pressure", device_id):
                        continue

                    # Poll the device for pressure
                    try:
                        self.logger.debug(
                            f"Polling pressure from Hyphae device {device_id}"
                        )

                        # Fetch and store pressure reading
                        reading = await self.pressure_service.fetch_and_store_pressure(
                            device_id
                        )

                        if reading:
                            self._update_device_status("pressure", device_id, True)
                            self.logger.debug(
                                f"Successfully polled pressure from device {device_id}: "
                                f"{reading.get('pressure_hpa', 'N/A')} hPa"
                            )
                            # Distribute pressure to associated Spore devices
                            pressure_hpa = reading.get("pressure_hpa")
                            if pressure_hpa:
                                await self.pressure_distribution.distribute_pressure(
                                    device_id, pressure_hpa
                                )
                        else:
                            self._update_device_status("pressure", device_id, False)

                    except Exception as e:
                        self.logger.error(
                            f"Error polling pressure from device {device_id}: {e}"
                        )
                        self._update_device_status("pressure", device_id, False)

                # Sleep until the next polling interval
                await asyncio.sleep(self._get_polling_interval("pressure"))
            except Exception as e:
                self.logger.error(f"Error in pressure polling loop: {e}")

                # Sleep for a short time before retrying
                await asyncio.sleep(5)

    def _get_weather_locations(self) -> Dict[str, Dict[str, Any]]:
        """
        Get weather locations from user settings.

        Reads OWM API keys and ZIP codes configured by users in the settings page.

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of weather locations by location ID
        """
        from storage.tables.user_settings import get_all_user_settings

        locations = {}
        for user in get_all_user_settings():
            api_key = (user.get("owm_api_key") or "").strip()
            zip_code = (user.get("owm_zip_code") or "").strip()
            if api_key and zip_code:
                location_id = f"user_{user['user_id']}"
                locations[location_id] = {
                    "api_key": api_key,
                    "location": {"zip": f"{zip_code},us"},
                    "units": "metric",
                    "farm_id": user.get("farm_id"),
                }
        return locations

    def _should_poll_device(self, device_type: str, device_id: str) -> bool:
        """
        Check if a device should be polled.

        Args:
            device_type (str): Type of device
            device_id (str): ID of the device

        Returns:
            bool: True if the device should be polled, False otherwise
        """
        # Check if polling is enabled for this device type
        if not self.polling_config[device_type]["enabled"]:
            return False

        # Check if the device is in the status dictionary
        if device_id not in self.device_status[device_type]:
            # First time polling this device
            self.device_status[device_type][device_id] = {
                "online": False,
                "last_success": None,
                "failures": 0,
                "next_poll": datetime.now(),
            }
            return True

        # Check if it's time to poll this device
        status = self.device_status[device_type][device_id]
        return datetime.now() >= status["next_poll"]

    def _update_device_status(
        self, device_type: str, device_id: str, success: bool, error=None
    ):
        """
        Update the status of a device.

        Args:
            device_type (str): Type of device
            device_id (str): ID of the device
            success (bool): Whether the polling was successful
            error (Exception, optional): The failure cause, used to tell a
                transient mDNS resolution miss from a genuine outage.
        """
        # Initialize the status dictionary if needed
        if device_id not in self.device_status[device_type]:
            self.device_status[device_type][device_id] = {
                "online": False,
                "last_success": None,
                "failures": 0,
                "resolution_misses": 0,
                "next_poll": datetime.now(),
            }

        status = self.device_status[device_type][device_id]
        interval = self.polling_config[device_type]["interval"]
        jitter = self.polling_config[device_type]["jitter"]

        def _schedule(seconds):
            status["next_poll"] = datetime.now() + timedelta(seconds=max(1.0, seconds))

        def _write_db(online: bool):
            if device_type == "spore":
                update_spore_status(device_id, 1 if online else 0)
            elif device_type == "hyphae":
                update_hyphae_status(device_id, 1 if online else 0)

        if success:
            status["online"] = True
            status["last_success"] = datetime.now()
            status["failures"] = 0
            status["resolution_misses"] = 0
            _schedule(interval + random.uniform(-jitter, jitter))
            _write_db(True)

        elif is_resolution_error(error):
            # Transient mDNS glitch — Avahi briefly failed to resolve the .local
            # name, the device itself is probably fine. Retry at the normal cadence
            # (no exponential backoff) and keep the device's current status through
            # a short grace window so one missed lookup doesn't bench it.
            status["resolution_misses"] = status.get("resolution_misses", 0) + 1
            _schedule(interval + random.uniform(-jitter, jitter))
            if status["resolution_misses"] >= RESOLUTION_GRACE:
                status["online"] = False
                _write_db(False)
            # else: within grace — leave online state and DB untouched

        else:
            # Genuine failure (resolved host, refused/timeout/HTTP error). Mark
            # offline and back off exponentially.
            status["online"] = False
            status["failures"] += 1
            status["resolution_misses"] = 0
            backoff_factor = self.polling_config[device_type]["backoff_factor"]
            max_backoff = self.polling_config[device_type]["max_backoff"]
            backoff = min(
                interval * (backoff_factor ** status["failures"]),
                max_backoff,
            )
            _schedule(backoff + random.uniform(-jitter, jitter))
            _write_db(False)

        self.logger.debug(
            f"Updated status for {device_type} device {device_id}: "
            f"online={status['online']}, failures={status['failures']}, "
            f"resolution_misses={status['resolution_misses']}, "
            f"next_poll={status['next_poll'].isoformat()}"
        )

    def _get_polling_interval(self, device_type: str) -> float:
        """
        Get the polling interval for a device type.

        Args:
            device_type (str): Type of device

        Returns:
            float: Polling interval in seconds
        """
        interval = self.polling_config[device_type]["interval"]
        jitter = self.polling_config[device_type]["jitter"]

        # Add some jitter to prevent all devices from being polled at the same time
        return interval + random.uniform(-jitter, jitter)

    async def _check_alerts(self):
        """Periodically check alert rules and trigger notifications."""
        self.logger.info("Starting alert checking")

        while self.running:
            try:
                # Check all alert rules
                triggers = self.alert_service.check_all_rules()

                # Send notifications for triggered alerts
                for trigger in triggers:
                    try:
                        # Get the full rule configuration
                        rule = self.alert_service.get_rule(trigger.rule_id)
                        if not rule:
                            continue

                        # Build device info
                        device_info = {
                            "device_id": trigger.device_id,
                            "device_type": trigger.device_type,
                            "device_name": trigger.device_name,
                        }

                        # Get alert ID from the most recent alert for this trigger
                        from storage.tables import alert_history

                        recent_alerts = (
                            alert_history.get_alerts_for_device(
                                trigger.device_id, trigger.device_type, days=1
                            )
                            if trigger.device_id
                            else []
                        )

                        alert_id = recent_alerts[0]["alert_id"] if recent_alerts else 0

                        # Send notification
                        self.notification_service.send_alert_notification(
                            alert_id=alert_id,
                            rule=rule,
                            device=device_info,
                            message=trigger.message,
                        )

                        self.logger.info(
                            f"Alert triggered and notification sent: {trigger.message}"
                        )

                    except Exception as e:
                        self.logger.error(f"Error sending notification for alert: {e}")

                # Sleep until next check
                interval = self.polling_config.get("alerts", {}).get("interval", 60)
                jitter = self.polling_config.get("alerts", {}).get("jitter", 5)
                await asyncio.sleep(interval + random.uniform(-jitter, jitter))

            except Exception as e:
                self.logger.error(f"Error in alert checking loop: {e}")
                await asyncio.sleep(5)
