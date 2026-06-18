"""
OTA Firmware Update Service for Mycelium

Orchestrates two-phase OTA uploads to Spore and Hyphae devices:
1. POST /api/ota/start-upload with PIN → returns upload token
2. POST /api/ota/upload-stream with token + firmware binary
3. Poll GET /api/ota/status for progress

Also manages firmware version inventory and OTA history.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional

import aiohttp

from storage.tables.device_spore import get_device_spore
from storage.tables.device_hyphae import get_device_hyphae
from storage.tables.device_pins import get_device_pin, has_stored_pin


class OtaService:
    """Service for managing OTA firmware updates to devices."""

    def __init__(self):
        self.logger = logging.getLogger("api.OtaService")
        self.firmware_dir = Path(__file__).parent.parent.parent / 'data' / 'firmware'
        self.firmware_dir.mkdir(parents=True, exist_ok=True)

    def _get_device_url(self, device_id: int, device_type: str) -> Optional[str]:
        """Get the base URL for a device."""
        if device_type == 'spore':
            device = get_device_spore(device_id)
        else:
            device = get_device_hyphae(device_id)

        if not device:
            return None

        ip = device.get('ip_address')
        if not ip:
            return None

        return f"https://{ip}"

    def resolve_pin(self, device_id: int, device_type: str, user_id: int = None) -> Optional[str]:
        """
        Two-tier PIN lookup:
        1. Per-device PIN from device_pins table (highest priority)
        2. Default PIN from user_settings (fallback)
        Returns None if no PIN is available.
        """
        # Tier 1: per-device PIN
        if has_stored_pin(device_id, device_type):
            pin = get_device_pin(device_id, device_type)
            if pin:
                return pin

        # Tier 2: user's default PIN from settings
        if user_id:
            try:
                from storage.tables.user_settings import get_user_setting
                user_info = get_user_setting(user_id)
                if user_info and user_info.get('reset_pin'):
                    return user_info['reset_pin']
            except Exception:
                pass

        return None

    def get_pin_status(self, device_id: int, device_type: str, user_id: int = None) -> str:
        """
        Return the PIN status for a device:
        'device' — per-device PIN stored
        'default' — using user's default PIN
        'missing' — no PIN available
        """
        if has_stored_pin(device_id, device_type):
            return 'device'
        if user_id:
            try:
                from storage.tables.user_settings import get_user_setting
                user_info = get_user_setting(user_id)
                if user_info and user_info.get('reset_pin'):
                    return 'default'
            except Exception:
                pass
        return 'missing'

    async def upload_firmware(
        self,
        device_id: int,
        device_type: str,
        firmware_path: str,
        user_id: int = None,
        on_progress: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Upload firmware to a device via the two-phase OTA protocol.

        Args:
            device_id: Database ID of the device.
            device_type: 'spore' or 'hyphae'.
            firmware_path: Path to the firmware .bin file.
            user_id: User ID for default PIN fallback.
            on_progress: Optional callback(percent, message).

        Returns:
            Dict with 'success' bool, 'message' str, and optional 'error'.
        """
        base_url = self._get_device_url(device_id, device_type)
        if not base_url:
            return {'success': False, 'error': 'Device not found or has no IP'}

        pin = self.resolve_pin(device_id, device_type, user_id)
        firmware = Path(firmware_path)
        if not firmware.exists():
            return {'success': False, 'error': f'Firmware file not found: {firmware_path}'}

        file_size = firmware.stat().st_size
        self.logger.info(f"Starting OTA upload to {device_type} {device_id}: {firmware.name} ({file_size} bytes)")

        # Create SSL context for device communication
        from api.clients.base_client import _CA_CERT_PATH
        import ssl
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
                # Phase 1: Start upload
                if on_progress:
                    on_progress(0, 'Starting upload...')

                start_data = {'pin': pin} if pin else {}
                async with session.post(
                    f"{base_url}/api/ota/start-upload",
                    json=start_data,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        return {'success': False, 'error': f'Start upload failed ({resp.status}): {body}'}
                    result = await resp.json()
                    token = result.get('token') or result.get('upload_token')
                    if not token:
                        return {'success': False, 'error': 'No upload token returned'}

                # Phase 2: Stream firmware
                if on_progress:
                    on_progress(10, 'Uploading firmware...')

                with open(firmware, 'rb') as f:
                    async with session.post(
                        f"{base_url}/api/ota/upload-stream",
                        data=f,
                        headers={
                            'X-OTA-Token': token,
                            'Content-Type': 'application/octet-stream',
                            'Content-Length': str(file_size),
                        },
                        timeout=aiohttp.ClientTimeout(total=120),
                    ) as resp:
                        if resp.status != 200:
                            body = await resp.text()
                            return {'success': False, 'error': f'Upload failed ({resp.status}): {body}'}

                if on_progress:
                    on_progress(90, 'Firmware uploaded, device rebooting...')

                # Log to OTA history
                self._log_ota_event(device_id, device_type, firmware.name, 'success')

                return {'success': True, 'message': f'Firmware uploaded successfully to {device_type} {device_id}'}

        except asyncio.TimeoutError:
            self._log_ota_event(device_id, device_type, firmware.name, 'failed', 'Upload timed out')
            return {'success': False, 'error': 'Upload timed out'}
        except Exception as e:
            self._log_ota_event(device_id, device_type, firmware.name, 'failed', str(e))
            return {'success': False, 'error': str(e)}

    async def get_device_ota_status(self, device_id: int, device_type: str) -> Optional[Dict]:
        """Poll a device's OTA status endpoint."""
        base_url = self._get_device_url(device_id, device_type)
        if not base_url:
            return None

        from api.clients.base_client import _CA_CERT_PATH
        import ssl
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
                    f"{base_url}/api/ota/status",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception:
            pass
        return None

    def _log_ota_event(self, device_id: int, device_type: str, firmware_name: str, status: str, error: str = None):
        """Log an OTA event to the database."""
        try:
            from storage.tables.ota_history import create_ota_event
            create_ota_event(device_id, device_type, firmware_name, status, error)
        except Exception as e:
            self.logger.error(f"Failed to log OTA event: {e}")
