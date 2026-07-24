"""
Alert Service for Mycelium

This module provides alert checking, triggering, and management functionality.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from storage.tables import alert_rules, alert_history
from storage.tables import device_spore, device_hyphae
from storage.tables import readings_spore


logger = logging.getLogger("services.AlertService")


# Hyphae latched-error reason codes (err_code reported on /api/relay/state).
# Mirrors RelayErrorCode in the firmware.
_HYPHAE_ERROR_REASONS = {
    1: "CO2 uncontrollable after exhausting drift corrections — check the exhaust fan.",
    2: "Could not auto-correct CO2 drift: no calibration PIN set for a Spore.",
    3: "Humidity never reached target — check the humidifier.",
    4: "Temperature never reached target — check the heater.",
}


def _hyphae_error_groups(error_group: int) -> str:
    """Human list of culprit groups from the err_grp bitmask (bit0=CO2, 1=Hum, 2=Temp)."""
    names = []
    if error_group & 0x01:
        names.append("CO2")
    if error_group & 0x02:
        names.append("Humidity")
    if error_group & 0x04:
        names.append("Temperature")
    return ", ".join(names) if names else "unknown"


@dataclass
class AlertTrigger:
    """Represents a triggered alert."""

    rule_id: int
    rule_name: str
    rule_type: str
    device_id: Optional[int]
    device_type: Optional[str]
    device_name: Optional[str]
    message: str
    value: Optional[float] = None


class AlertService:
    """Service for checking and managing alerts."""

    def __init__(self):
        self.logger = logging.getLogger("services.AlertService")

    def check_all_rules(self) -> List[AlertTrigger]:
        """
        Check all enabled alert rules.

        Returns:
            List of triggered alerts
        """
        rules = alert_rules.get_all_rules(enabled_only=True)
        triggered = []

        for rule in rules:
            try:
                triggers = self._check_rule(rule)
                triggered.extend(triggers)
            except Exception as e:
                self.logger.error(f"Error checking rule {rule.get('rule_id')}: {e}")

        return triggered

    def _check_rule(self, rule: Dict[str, Any]) -> List[AlertTrigger]:
        """
        Check a single alert rule.

        Args:
            rule: Rule configuration

        Returns:
            List of triggered alerts
        """
        rule_type = rule.get("rule_type")

        if rule_type == "offline":
            return self._check_offline_rule(rule)
        elif rule_type in ("threshold_high", "threshold_low"):
            return self._check_threshold_rule(rule)
        elif rule_type == "degraded":
            return self._check_degraded_rule(rule)
        elif rule_type == "error":
            return self._check_error_rule(rule)

        return []

    def _check_offline_rule(self, rule: Dict[str, Any]) -> List[AlertTrigger]:
        """Check for offline devices."""
        triggers = []
        duration_minutes = rule.get("threshold_duration_minutes", 5)
        # Naive UTC to match persisted timestamps
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            minutes=duration_minutes
        )
        cutoff_str = cutoff.isoformat()

        devices = self._get_devices_for_rule(rule)

        for device in devices:
            last_update = device.get("last_update")
            is_online = device.get("is_online", 0)

            # Check if device is offline or hasn't updated recently
            if not is_online or (last_update and last_update < cutoff_str):
                # Check for duplicate
                if not alert_history.has_active_alert(
                    rule["rule_id"], device["device_id"]
                ):
                    # Create alert
                    message = f"{device['device_name']} offline for {duration_minutes}+ minutes"
                    alert_history.create_alert(
                        rule_id=rule["rule_id"],
                        device_id=device["device_id"],
                        device_type=device["device_type"],
                        alert_message=message,
                    )

                    triggers.append(
                        AlertTrigger(
                            rule_id=rule["rule_id"],
                            rule_name=rule["rule_name"],
                            rule_type="offline",
                            device_id=device["device_id"],
                            device_type=device["device_type"],
                            device_name=device["device_name"],
                            message=message,
                        )
                    )

                    self.logger.info(f"Alert triggered: {message}")

        return triggers

    def _check_threshold_rule(self, rule: Dict[str, Any]) -> List[AlertTrigger]:
        """Check sensor threshold rules."""
        triggers = []
        metric = rule.get("metric")
        threshold = rule.get("threshold_value")
        is_high = rule["rule_type"] == "threshold_high"

        if not metric or threshold is None:
            return triggers

        # Only applies to Spore devices (they have sensor data)
        devices = self._get_devices_for_rule(rule)
        spore_devices = [d for d in devices if d.get("device_type") == "spore"]

        for device in spore_devices:
            reading = self._get_latest_reading(device["device_id"], metric)
            if reading is None:
                continue

            triggered = (reading > threshold) if is_high else (reading < threshold)

            if triggered:
                if not alert_history.has_active_alert(
                    rule["rule_id"], device["device_id"]
                ):
                    direction = "above" if is_high else "below"
                    message = f"{metric.upper()} {direction} threshold on {device['device_name']}: {reading:.1f} (limit: {threshold})"

                    alert_history.create_alert(
                        rule_id=rule["rule_id"],
                        device_id=device["device_id"],
                        device_type="spore",
                        alert_message=message,
                        alert_value=reading,
                    )

                    triggers.append(
                        AlertTrigger(
                            rule_id=rule["rule_id"],
                            rule_name=rule["rule_name"],
                            rule_type=rule["rule_type"],
                            device_id=device["device_id"],
                            device_type="spore",
                            device_name=device["device_name"],
                            message=message,
                            value=reading,
                        )
                    )

                    self.logger.info(f"Alert triggered: {message}")
            else:
                # Auto-resolve if condition cleared
                alert_history.auto_resolve_for_rule_device(
                    rule["rule_id"], device["device_id"]
                )

        return triggers

    def _check_degraded_rule(self, rule: Dict[str, Any]) -> List[AlertTrigger]:
        """Check for degraded device performance."""
        triggers = []
        devices = self._get_devices_for_rule(rule)

        # Check response times from health log
        from storage.tables.device_health import get_device_health_metrics

        for device in devices:
            metrics = get_device_health_metrics(
                device["device_id"], device["device_type"]
            )
            avg_response = metrics.get("avg_response_24h")

            # Consider degraded if average response time > 2000ms
            if avg_response and avg_response > 2000:
                if not alert_history.has_active_alert(
                    rule["rule_id"], device["device_id"]
                ):
                    message = f"{device['device_name']} performance degraded (avg response: {avg_response:.0f}ms)"

                    alert_history.create_alert(
                        rule_id=rule["rule_id"],
                        device_id=device["device_id"],
                        device_type=device["device_type"],
                        alert_message=message,
                        alert_value=avg_response,
                    )

                    triggers.append(
                        AlertTrigger(
                            rule_id=rule["rule_id"],
                            rule_name=rule["rule_name"],
                            rule_type="degraded",
                            device_id=device["device_id"],
                            device_type=device["device_type"],
                            device_name=device["device_name"],
                            message=message,
                            value=avg_response,
                        )
                    )

                    self.logger.info(f"Alert triggered: {message}")

        return triggers

    def _check_error_rule(self, rule: Dict[str, Any]) -> List[AlertTrigger]:
        """Raise an alert when a Hyphae controller has latched into error mode
        (relay control halted by the max-on-time safety). Only Hyphae devices
        carry this state; the reason comes from the mode/error fields the poller
        stored from /api/relay/state."""
        triggers = []
        devices = self._get_devices_for_rule(rule)
        hyphae_devices = [d for d in devices if d.get("device_type") == "hyphae"]

        for device in hyphae_devices:
            if device.get("mode_enabled") == 3:
                if not alert_history.has_active_alert(
                    rule["rule_id"], device["device_id"]
                ):
                    groups = _hyphae_error_groups(device.get("error_group", 0) or 0)
                    reason = _HYPHAE_ERROR_REASONS.get(
                        device.get("error_code", 0) or 0,
                        "Relay control halted by the max-on-time safety.",
                    )
                    message = (
                        f"{device['device_name']} halted relay control "
                        f"({groups}): {reason}"
                    )
                    alert_history.create_alert(
                        rule_id=rule["rule_id"],
                        device_id=device["device_id"],
                        device_type="hyphae",
                        alert_message=message,
                    )
                    triggers.append(
                        AlertTrigger(
                            rule_id=rule["rule_id"],
                            rule_name=rule["rule_name"],
                            rule_type="error",
                            device_id=device["device_id"],
                            device_type="hyphae",
                            device_name=device["device_name"],
                            message=message,
                        )
                    )
                    self.logger.info(f"Alert triggered: {message}")
            else:
                # Recovered (operator set the mode back to 0/1/2) — clear it.
                alert_history.auto_resolve_for_rule_device(
                    rule["rule_id"], device["device_id"]
                )

        return triggers

    def _get_devices_for_rule(self, rule: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get devices that match rule criteria.

        Args:
            rule: Rule configuration

        Returns:
            List of matching devices
        """
        devices = []

        # Get target device type(s)
        rule_device_type = rule.get("device_type")
        rule_device_id = rule.get("device_id")
        rule_room_id = rule.get("room_id")

        # Get Spore devices
        if rule_device_type is None or rule_device_type == "spore":
            spore_devices = device_spore.get_all_devices(active_only=True)
            for d in spore_devices:
                # Apply filters
                if rule_device_id and d["device_id"] != rule_device_id:
                    continue
                if rule_room_id and d.get("room_id") != rule_room_id:
                    continue
                d["device_type"] = "spore"
                devices.append(d)

        # Get Hyphae devices
        if rule_device_type is None or rule_device_type == "hyphae":
            hyphae_devices = device_hyphae.get_all_devices(active_only=True)
            for d in hyphae_devices:
                # Apply filters
                if rule_device_id and d["device_id"] != rule_device_id:
                    continue
                if rule_room_id and d.get("room_id") != rule_room_id:
                    continue
                d["device_type"] = "hyphae"
                devices.append(d)

        return devices

    def _get_latest_reading(self, device_id: int, metric: str) -> Optional[float]:
        """
        Get latest sensor reading for a metric.

        Args:
            device_id: Spore device ID
            metric: 'co2', 'temperature', or 'humidity'

        Returns:
            Latest value or None
        """
        latest = readings_spore.get_latest_reading(device_id)
        if not latest:
            return None

        metric_map = {"co2": "co2", "temperature": "temp", "humidity": "humidity"}

        field = metric_map.get(metric)
        if field:
            return latest.get(field)

        return None

    # Alert management methods

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active (unresolved) alerts."""
        return alert_history.get_active_alerts()

    def get_unacknowledged_alerts(self) -> List[Dict[str, Any]]:
        """Get all unacknowledged alerts."""
        return alert_history.get_unacknowledged_alerts()

    def get_alert_history(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get alert history for the past N days."""
        return alert_history.get_alert_history(days=days)

    def acknowledge_alert(
        self, alert_id: int, user_id: int, notes: Optional[str] = None
    ) -> bool:
        """Acknowledge an alert."""
        return alert_history.acknowledge_alert(alert_id, user_id, notes)

    def resolve_alert(self, alert_id: int) -> bool:
        """Resolve an alert."""
        return alert_history.resolve_alert(alert_id)

    def get_alert_counts(self) -> Dict[str, int]:
        """Get alert count summary."""
        return alert_history.get_alert_counts()

    # Rule management methods

    def get_all_rules(self) -> List[Dict[str, Any]]:
        """Get all alert rules."""
        return alert_rules.get_all_rules(enabled_only=False)

    def get_rule(self, rule_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific rule."""
        return alert_rules.get_rule(rule_id)

    def create_rule(
        self,
        rule_name: str,
        rule_type: str,
        device_type: Optional[str] = None,
        device_id: Optional[int] = None,
        room_id: Optional[int] = None,
        metric: Optional[str] = None,
        threshold_value: Optional[float] = None,
        threshold_duration_minutes: int = 5,
        notification_method: str = "ui",
        notification_target: Optional[str] = None,
    ) -> int:
        """Create a new alert rule."""
        return alert_rules.create_rule(
            rule_name=rule_name,
            rule_type=rule_type,
            device_type=device_type,
            device_id=device_id,
            room_id=room_id,
            metric=metric,
            threshold_value=threshold_value,
            threshold_duration_minutes=threshold_duration_minutes,
            notification_method=notification_method,
            notification_target=notification_target,
        )

    def update_rule(self, rule_id: int, **kwargs) -> bool:
        """Update an alert rule."""
        return alert_rules.update_rule(rule_id, **kwargs)

    def delete_rule(self, rule_id: int) -> bool:
        """Delete an alert rule."""
        return alert_rules.delete_rule(rule_id)

    def toggle_rule(self, rule_id: int, enabled: bool) -> bool:
        """Enable or disable a rule."""
        return alert_rules.toggle_rule(rule_id, enabled)
