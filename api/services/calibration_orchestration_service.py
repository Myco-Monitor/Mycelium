"""
Calibration Orchestration Service for Mycelium

Manages CO2 sensor calibration for Spore devices:
- Schedule calibrations for future execution
- Monitor warmup/cooldown state via GET /api/status
- Trigger calibration via POST /api/calibrate with PIN
- Log calibration events to the database
"""

import logging
from typing import Dict, Any, Optional, List

from storage.tables.device_spore import get_device_spore
from storage.tables.device_pins import get_device_pin


class CalibrationOrchestrationService:
    """Orchestrates CO2 calibration across Spore devices."""

    def __init__(self):
        self.logger = logging.getLogger("api.CalibrationOrchestrationService")

    async def get_calibration_status(self, device_id: int) -> Optional[Dict[str, Any]]:
        """
        Get current calibration status from a Spore device.

        Returns warmup state, std_dev, and remote calibration settings
        from GET /api/status.
        """
        device = get_device_spore(device_id)
        if not device:
            return None

        ip = device.get("hostname")
        if not ip:
            return None

        from api.clients.base_client import _CA_CERT_PATH
        from pathlib import Path
        import ssl
        import aiohttp

        ssl_ctx = ssl.create_default_context()
        ca_path = Path(_CA_CERT_PATH)
        if ca_path.exists():
            ssl_ctx.load_verify_locations(str(ca_path))
        else:
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    f"https://{ip}/api/status",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            self.logger.warning(
                f"Failed to get calibration status from Spore {device_id}: {e}"
            )

        return None

    async def trigger_calibration(
        self,
        device_id: int,
        target_ppm: int = 420,
    ) -> Dict[str, Any]:
        """
        Trigger CO2 calibration on a Spore device.

        Args:
            device_id: Spore device database ID.
            target_ppm: Target CO2 ppm for calibration (default 420 = outdoor ambient).

        Returns:
            Dict with 'success' bool and 'message' str.
        """
        device = get_device_spore(device_id)
        if not device:
            return {"success": False, "message": "Device not found"}

        ip = device.get("hostname")
        if not ip:
            return {"success": False, "message": "Device has no IP address"}

        pin = get_device_pin(device_id, "spore")

        from api.clients.base_client import _CA_CERT_PATH
        from pathlib import Path
        import ssl
        import aiohttp

        ssl_ctx = ssl.create_default_context()
        ca_path = Path(_CA_CERT_PATH)
        if ca_path.exists():
            ssl_ctx.load_verify_locations(str(ca_path))
        else:
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                payload = {"target_ppm": target_ppm}
                if pin:
                    payload["pin"] = pin

                async with session.post(
                    f"https://{ip}/api/calibrate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    body = await resp.text()
                    if resp.status == 200:
                        self._log_calibration(
                            device_id, "remote", target_ppm, "completed"
                        )
                        return {
                            "success": True,
                            "message": f"Calibration triggered at {target_ppm} ppm",
                        }
                    else:
                        self._log_calibration(
                            device_id, "remote", target_ppm, "failed", body
                        )
                        return {
                            "success": False,
                            "message": f"Calibration failed ({resp.status}): {body}",
                        }

        except Exception as e:
            self._log_calibration(device_id, "remote", target_ppm, "failed", str(e))
            return {"success": False, "message": str(e)}

    def get_calibration_history(
        self, device_id: int = None, limit: int = 50
    ) -> List[Dict]:
        """Get calibration history from the database."""
        try:
            from storage.tables.calibration_history import get_calibration_history

            return get_calibration_history(device_id=device_id, limit=limit)
        except Exception:
            return []

    def _log_calibration(
        self,
        device_id: int,
        cal_type: str,
        target_ppm: int,
        status: str,
        notes: str = None,
    ):
        """Log a calibration event to the database."""
        try:
            from storage.tables.calibration_history import create_calibration_event

            create_calibration_event(device_id, cal_type, target_ppm, status, notes)
        except Exception as e:
            self.logger.error(f"Failed to log calibration event: {e}")
