"""
Device Health Service for Mycelium

This module provides services for monitoring device health, including:
- Health check execution
- Response time tracking
- Uptime calculation
- Health status management
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

import aiohttp

from api.clients.base_client import create_device_ssl_context
from storage.tables.device_spore import get_all_device_spore, update_device_status as update_spore_status
from storage.tables.device_hyphae import get_all_device_hyphae, update_device_status as update_hyphae_status
from storage.tables.device_health import (
    log_health_check,
    get_health_history,
    get_recent_status,
    calculate_uptime,
    calculate_avg_response_time,
    get_device_health_metrics,
    cleanup_old_records,
    get_all_devices_health_summary
)


class HealthService:
    """
    Service for monitoring device health.

    This service is responsible for:
    - Performing health checks on devices
    - Logging health check results
    - Tracking response times
    - Calculating uptime metrics
    """

    def __init__(self, timeout: float = 5.0):
        """
        Initialize the health service.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.logger = logging.getLogger("api.HealthService")
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None or self._session.closed:
            ssl_ctx = create_device_ssl_context()
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                connector=connector
            )
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def check_device_health(
        self,
        device_id: int,
        device_type: str,
        ip_address: str
    ) -> Dict[str, Any]:
        """
        Perform a health check on a single device.

        Args:
            device_id: Device ID
            device_type: 'spore' or 'hyphae'
            ip_address: Device IP address

        Returns:
            Dictionary with health check results
        """
        result = {
            "device_id": device_id,
            "device_type": device_type,
            "ip_address": ip_address,
            "is_online": False,
            "response_time_ms": None,
            "error_message": None,
            "http_status_code": None,
            "check_time": datetime.now().isoformat()
        }

        # Determine the health check endpoint
        endpoint = "/api/info" if device_type == "spore" else "/api/status"
        url = f"https://{ip_address}{endpoint}"

        try:
            session = await self._get_session()
            start_time = time.monotonic()

            async with session.get(url) as response:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)

                result["response_time_ms"] = elapsed_ms
                result["http_status_code"] = response.status

                if response.status == 200:
                    result["is_online"] = True
                else:
                    result["error_message"] = f"HTTP {response.status}"

        except asyncio.TimeoutError:
            result["error_message"] = "Connection timeout"
        except aiohttp.ClientConnectorError as e:
            result["error_message"] = f"Connection failed: {str(e)}"
        except Exception as e:
            result["error_message"] = f"Error: {str(e)}"
            self.logger.error(f"Health check error for {device_type} {device_id}: {e}")

        # Log the health check result
        try:
            log_health_check(
                device_id=device_id,
                device_type=device_type,
                is_online=result["is_online"],
                response_time_ms=result["response_time_ms"],
                error_message=result["error_message"],
                http_status_code=result["http_status_code"]
            )
        except Exception as e:
            self.logger.error(f"Failed to log health check: {e}")

        # Update device online status
        try:
            if device_type == "spore":
                update_spore_status(device_id, 1 if result["is_online"] else 0)
            else:
                update_hyphae_status(device_id, 1 if result["is_online"] else 0)
        except Exception as e:
            self.logger.error(f"Failed to update device status: {e}")

        return result

    async def check_all_devices(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Perform health checks on all devices.

        Returns:
            Dictionary with 'spore' and 'hyphae' lists of health check results
        """
        results = {
            "spore": [],
            "hyphae": []
        }

        # Get all active devices
        spore_devices = get_all_device_spore()
        hyphae_devices = get_all_device_hyphae()

        # Create health check tasks
        tasks = []

        for device in spore_devices:
            if device.get("active", 1):
                tasks.append(
                    self.check_device_health(
                        device_id=device["device_id"],
                        device_type="spore",
                        ip_address=device["ip_address"]
                    )
                )

        for device in hyphae_devices:
            if device.get("active", 1):
                tasks.append(
                    self.check_device_health(
                        device_id=device["device_id"],
                        device_type="hyphae",
                        ip_address=device["ip_address"]
                    )
                )

        # Run all health checks concurrently
        if tasks:
            check_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in check_results:
                if isinstance(result, Exception):
                    self.logger.error(f"Health check task failed: {result}")
                    continue

                if result["device_type"] == "spore":
                    results["spore"].append(result)
                else:
                    results["hyphae"].append(result)

        self.logger.info(
            f"Health check complete: {len(results['spore'])} spore, "
            f"{len(results['hyphae'])} hyphae devices checked"
        )

        return results

    def get_device_metrics(
        self,
        device_id: int,
        device_type: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive health metrics for a device.

        Args:
            device_id: Device ID
            device_type: 'spore' or 'hyphae'

        Returns:
            Dictionary with health metrics
        """
        return get_device_health_metrics(device_id, device_type)

    def get_recent_device_status(
        self,
        device_id: int,
        device_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recent health check for a device.

        Args:
            device_id: Device ID
            device_type: 'spore' or 'hyphae'

        Returns:
            Most recent health check record or None
        """
        return get_recent_status(device_id, device_type)

    def get_device_uptime(
        self,
        device_id: int,
        device_type: str,
        hours: int = 24
    ) -> float:
        """
        Get uptime percentage for a device.

        Args:
            device_id: Device ID
            device_type: 'spore' or 'hyphae'
            hours: Number of hours to calculate over

        Returns:
            Uptime percentage (0.0 to 100.0)
        """
        return calculate_uptime(device_id, device_type, hours)

    def get_device_avg_response_time(
        self,
        device_id: int,
        device_type: str,
        hours: int = 24
    ) -> Optional[float]:
        """
        Get average response time for a device.

        Args:
            device_id: Device ID
            device_type: 'spore' or 'hyphae'
            hours: Number of hours to calculate over

        Returns:
            Average response time in milliseconds, or None if no data
        """
        return calculate_avg_response_time(device_id, device_type, hours)

    def get_all_devices_summary(self) -> List[Dict[str, Any]]:
        """
        Get health summary for all devices.

        Returns:
            List of device health summaries
        """
        return get_all_devices_health_summary()

    def cleanup_old_health_records(self, days: int = 7) -> int:
        """
        Remove old health records.

        Args:
            days: Number of days to keep

        Returns:
            Number of records deleted
        """
        deleted = cleanup_old_records(days)
        self.logger.info(f"Cleaned up {deleted} old health records")
        return deleted

    def get_fleet_health_overview(self) -> Dict[str, Any]:
        """
        Get an overview of fleet health status.

        Returns:
            Dictionary with fleet health overview
        """
        spore_devices = get_all_device_spore()
        hyphae_devices = get_all_device_hyphae()

        spore_online = 0
        spore_offline = 0
        hyphae_online = 0
        hyphae_offline = 0

        for device in spore_devices:
            if not device.get("active", 1):
                continue
            status = get_recent_status(device["device_id"], "spore")
            if status and status.get("is_online"):
                spore_online += 1
            else:
                spore_offline += 1

        for device in hyphae_devices:
            if not device.get("active", 1):
                continue
            status = get_recent_status(device["device_id"], "hyphae")
            if status and status.get("is_online"):
                hyphae_online += 1
            else:
                hyphae_offline += 1

        total_devices = spore_online + spore_offline + hyphae_online + hyphae_offline
        total_online = spore_online + hyphae_online

        return {
            "total_devices": total_devices,
            "total_online": total_online,
            "total_offline": total_devices - total_online,
            "fleet_health_percent": (total_online / total_devices * 100) if total_devices > 0 else 0,
            "spore": {
                "total": spore_online + spore_offline,
                "online": spore_online,
                "offline": spore_offline
            },
            "hyphae": {
                "total": hyphae_online + hyphae_offline,
                "online": hyphae_online,
                "offline": hyphae_offline
            }
        }
