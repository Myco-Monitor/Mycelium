"""
Device Authentication Handler for Mycelium

This module provides PIN-based authentication with Spore and Hyphae devices.
The devices use a challenge-response mechanism with SHA-256 hashing.
"""

import hashlib
import aiohttp
from typing import Optional, Dict
from dataclasses import dataclass

from api.clients.base_client import create_device_ssl_context


@dataclass
class AuthResult:
    """Result of an authentication attempt."""
    success: bool
    challenge: Optional[str] = None
    response: Optional[str] = None
    error: Optional[str] = None


class DeviceAuthHandler:
    """
    Handles PIN-based authentication with Spore and Hyphae devices.

    The authentication flow:
    1. Request a challenge from the device (/auth-challenge)
    2. Compute SHA-256 hash of PIN + challenge
    3. Include the challenge and response in request headers

    Attributes:
        device_ip (str): IP address of the device
        pin (str): 5-digit PIN for the device
        timeout (float): Timeout for requests in seconds
    """

    def __init__(self, device_ip: str, pin: str, timeout: float = 5.0):
        """
        Initialize the authentication handler.

        Args:
            device_ip (str): IP address of the device
            pin (str): 5-digit PIN for the device
            timeout (float): Timeout for requests in seconds
        """
        self.device_ip = device_ip
        self.pin = pin
        self.timeout = timeout
        self._cached_challenge: Optional[str] = None

    async def get_challenge(self) -> Optional[str]:
        """
        Get an authentication challenge from the device.

        Returns:
            Optional[str]: The challenge string, or None if failed
        """
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            ssl_ctx = create_device_ssl_context()
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.get(f"https://{self.device_ip}/auth-challenge") as response:
                    if response.status == 200:
                        data = await response.json()
                        self._cached_challenge = data.get('challenge')
                        return self._cached_challenge
        except aiohttp.ClientError:
            pass
        except Exception:
            pass
        return None

    def compute_response(self, challenge: str) -> str:
        """
        Compute the SHA-256 hash of PIN + challenge.

        Args:
            challenge (str): The challenge from the device

        Returns:
            str: The hex-encoded SHA-256 hash
        """
        combined = f"{self.pin}{challenge}"
        return hashlib.sha256(combined.encode()).hexdigest()

    async def get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for an API request.

        Returns:
            Dict[str, str]: Headers containing X-Auth-Challenge and X-Auth-Response

        Raises:
            AuthenticationError: If unable to get challenge from device
        """
        challenge = await self.get_challenge()
        if not challenge:
            raise AuthenticationError("Failed to get auth challenge from device")

        response = self.compute_response(challenge)
        return {
            "X-Auth-Challenge": challenge,
            "X-Auth-Response": response
        }

    async def authenticate(self) -> AuthResult:
        """
        Perform a full authentication check.

        Returns:
            AuthResult: The result of the authentication attempt
        """
        challenge = await self.get_challenge()
        if not challenge:
            return AuthResult(
                success=False,
                error="Failed to get challenge from device"
            )

        response = self.compute_response(challenge)
        return AuthResult(
            success=True,
            challenge=challenge,
            response=response
        )

    async def make_authenticated_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        data: Optional[str] = None
    ) -> Dict:
        """
        Make an authenticated request to the device.

        Args:
            method (str): HTTP method (GET, POST, etc.)
            endpoint (str): API endpoint (e.g., /api/calibrate)
            json_data (Dict, optional): JSON body for the request
            data (str, optional): Raw data for the request

        Returns:
            Dict: Response with 'success', 'status', and 'data' or 'error'
        """
        try:
            headers = await self.get_auth_headers()
        except AuthenticationError as e:
            return {"success": False, "error": str(e)}

        url = f"https://{self.device_ip}{endpoint}"
        timeout = aiohttp.ClientTimeout(total=self.timeout)

        try:
            ssl_ctx = create_device_ssl_context()
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                kwargs = {"headers": headers}
                if json_data is not None:
                    kwargs["json"] = json_data
                elif data is not None:
                    kwargs["data"] = data

                async with session.request(method, url, **kwargs) as response:
                    status = response.status
                    try:
                        response_data = await response.json()
                    except Exception:
                        response_data = await response.text()

                    if status == 200:
                        return {
                            "success": True,
                            "status": status,
                            "data": response_data
                        }
                    elif status == 401:
                        return {
                            "success": False,
                            "status": status,
                            "error": "Authentication failed - incorrect PIN"
                        }
                    elif status == 403:
                        return {
                            "success": False,
                            "status": status,
                            "error": "Operation not permitted"
                        }
                    else:
                        return {
                            "success": False,
                            "status": status,
                            "error": f"Request failed with status {status}",
                            "data": response_data
                        }

        except aiohttp.ClientError as e:
            return {"success": False, "error": f"Network error: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {str(e)}"}


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass
