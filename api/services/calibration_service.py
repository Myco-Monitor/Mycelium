"""
Calibration Service for Mycelium

This module provides services for managing Spore sensor calibration,
including triggering calibration and updating ambient pressure.
"""

import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass

from api.clients.auth_handler import DeviceAuthHandler
from api.clients.base_client import create_device_ssl_context


@dataclass
class CalibrationStatus:
    """Current calibration status of a Spore device."""
    warmup_state: str
    co2_std_dev: Optional[float] = None
    allow_remote_calibration: bool = False
    last_calibration_timestamp: Optional[str] = None
    calibration_cooldown_remaining: int = 0
    can_calibrate: bool = False


@dataclass
class CalibrationResult:
    """Result of a calibration attempt."""
    success: bool
    accepted: bool = False
    warmup_seconds: int = 0
    previous_reading: Optional[int] = None
    error: Optional[str] = None


class CalibrationService:
    """
    Service for managing Spore sensor calibration.

    Provides methods to:
    - Check calibration status
    - Trigger CO2 sensor calibration
    - Update ambient pressure for CO2 compensation
    - Clear diagnostic logs
    """

    def __init__(self, timeout: float = 10.0):
        """
        Initialize the calibration service.

        Args:
            timeout (float): Timeout for device requests in seconds
        """
        self.timeout = timeout
        self.logger = logging.getLogger("services.CalibrationService")

    async def get_calibration_status(self, spore_ip: str) -> Optional[CalibrationStatus]:
        """
        Get the current calibration status from a Spore device.

        Args:
            spore_ip (str): IP address of the Spore device

        Returns:
            Optional[CalibrationStatus]: Calibration status or None if failed
        """
        import aiohttp

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            ssl_ctx = create_device_ssl_context()
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.get(f"https://{spore_ip}/api/status") as response:
                    if response.status == 200:
                        data = await response.json()

                        warmup_state = data.get("warmup_state", "unknown")
                        allow_remote = data.get("allow_remote_calibration", False)
                        cooldown = data.get("calibration_cooldown_remaining", 0)

                        # Determine if calibration is possible
                        can_calibrate = (
                            allow_remote and
                            warmup_state == "ready" and
                            cooldown == 0
                        )

                        return CalibrationStatus(
                            warmup_state=warmup_state,
                            co2_std_dev=data.get("co2_std_dev"),
                            allow_remote_calibration=allow_remote,
                            last_calibration_timestamp=data.get("last_calibration_timestamp"),
                            calibration_cooldown_remaining=cooldown,
                            can_calibrate=can_calibrate
                        )
        except Exception as e:
            self.logger.error(f"Error getting calibration status from {spore_ip}: {e}")

        return None

    async def trigger_calibration(
        self,
        spore_ip: str,
        pin: str,
        target_ppm: int = 420
    ) -> CalibrationResult:
        """
        Trigger CO2 sensor calibration on a Spore device.

        Args:
            spore_ip (str): IP address of the Spore device
            pin (str): Device PIN for authentication
            target_ppm (int): Reference CO2 level (typically 420 ppm for outdoor air)

        Returns:
            CalibrationResult: Result of the calibration attempt
        """
        # Validate target PPM
        if not 350 <= target_ppm <= 500:
            return CalibrationResult(
                success=False,
                error="Target PPM must be between 350 and 500"
            )

        # Check if calibration is allowed first
        status = await self.get_calibration_status(spore_ip)
        if status:
            if not status.allow_remote_calibration:
                return CalibrationResult(
                    success=False,
                    error="Remote calibration is disabled on this device"
                )
            if status.warmup_state != "ready":
                return CalibrationResult(
                    success=False,
                    error=f"Sensor not ready (warmup state: {status.warmup_state})"
                )
            if status.calibration_cooldown_remaining > 0:
                return CalibrationResult(
                    success=False,
                    error=f"Calibration on cooldown ({status.calibration_cooldown_remaining}s remaining)"
                )

        auth = DeviceAuthHandler(spore_ip, pin, timeout=self.timeout)
        payload = {"target_ppm": target_ppm}

        result = await auth.make_authenticated_request(
            "POST",
            "/api/calibrate",
            json_data=payload
        )

        if result.get("success"):
            data = result.get("data", {})
            self.logger.info(f"Calibration triggered on {spore_ip} with target {target_ppm} ppm")
            return CalibrationResult(
                success=True,
                accepted=data.get("accepted", True),
                warmup_seconds=data.get("warmup_seconds", 120),
                previous_reading=data.get("previous_reading")
            )
        else:
            self.logger.warning(f"Calibration failed on {spore_ip}: {result.get('error')}")
            return CalibrationResult(
                success=False,
                error=result.get("error", "Unknown error")
            )

    async def update_ambient_pressure(
        self,
        spore_ip: str,
        pin: str,
        pressure_hpa: int
    ) -> Dict[str, Any]:
        """
        Update the ambient pressure on a Spore device for CO2 compensation.

        The SCD41 CO2 sensor uses ambient pressure to compensate for altitude.
        Accurate pressure values improve CO2 reading accuracy.

        Args:
            spore_ip (str): IP address of the Spore device
            pin (str): Device PIN for authentication
            pressure_hpa (int): Ambient pressure in hectopascals (300-1100)

        Returns:
            Dict: Result with 'success' and optional 'error'
        """
        # Validate pressure range
        if not 300 <= pressure_hpa <= 1100:
            return {
                "success": False,
                "error": "Pressure must be between 300 and 1100 hPa"
            }

        auth = DeviceAuthHandler(spore_ip, pin, timeout=self.timeout)

        # Spore expects plain text body for pressure
        result = await auth.make_authenticated_request(
            "POST",
            "/api/ambient-pressure",
            data=str(pressure_hpa)
        )

        if result.get("success"):
            self.logger.info(f"Ambient pressure updated to {pressure_hpa} hPa on {spore_ip}")
        else:
            self.logger.warning(f"Failed to update pressure on {spore_ip}: {result.get('error')}")

        return result

    async def clear_diagnostics(
        self,
        spore_ip: str,
        pin: str
    ) -> Dict[str, Any]:
        """
        Clear the diagnostic/error log on a Spore device.

        Args:
            spore_ip (str): IP address of the Spore device
            pin (str): Device PIN for authentication

        Returns:
            Dict: Result with 'success' and optional 'error'
        """
        auth = DeviceAuthHandler(spore_ip, pin, timeout=self.timeout)

        result = await auth.make_authenticated_request(
            "POST",
            "/api/diagnostics/clear"
        )

        if result.get("success"):
            self.logger.info(f"Diagnostics cleared on {spore_ip}")
        else:
            self.logger.warning(f"Failed to clear diagnostics on {spore_ip}: {result.get('error')}")

        return result

    async def get_sensor_info(self, spore_ip: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed sensor information from a Spore device.

        Args:
            spore_ip (str): IP address of the Spore device

        Returns:
            Optional[Dict]: Sensor information or None if failed
        """
        import aiohttp

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            ssl_ctx = create_device_ssl_context()
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.get(f"https://{spore_ip}/api/status") as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "device_name": data.get("device_name"),
                            "firmware_version": data.get("firmware_version"),
                            "mac_address": data.get("mac_address"),
                            "warmup_state": data.get("warmup_state"),
                            "co2_std_dev": data.get("co2_std_dev"),
                            "measurement_interval": data.get("measurement_interval"),
                            "temp_preference": data.get("temp_preference"),
                            "default_pressure": data.get("default_pressure"),
                            "allow_remote_calibration": data.get("allow_remote_calibration"),
                            "calibration_cooldown_period": data.get("calibration_cooldown_period"),
                            "last_calibration_timestamp": data.get("last_calibration_timestamp"),
                        }
        except Exception as e:
            self.logger.error(f"Error getting sensor info from {spore_ip}: {e}")

        return None
