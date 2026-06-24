"""
Base API Client for Mycelium

This module provides a base API client class with common functionality for all API clients.
Features include:
- Connection pooling
- Request throttling
- Retry logic with exponential backoff
- Error handling and logging
- Timeout handling
"""

import ssl
import time
import socket
import random
import logging
import asyncio
import functools
from pathlib import Path
import aiohttp
from aiohttp.abc import AbstractResolver
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

# Path to MycoMonitor CA root certificate for device HTTPS
_CA_CERT_PATH = Path(__file__).parent.parent.parent / "config" / "ca_root.pem"


def create_device_ssl_context() -> ssl.SSLContext:
    """Create an SSL context that trusts the MycoMonitor CA certificate.

    Use this for any raw aiohttp calls to Spore/Hyphae devices outside BaseApiClient.
    """
    ctx = ssl.create_default_context()
    ca_path = Path(_CA_CERT_PATH)
    if ca_path.exists():
        ctx.load_verify_locations(str(ca_path))
    else:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


# Consecutive transient resolution misses tolerated before a device is marked
# offline. Avahi can briefly fail to resolve a .local name even while the device
# is up, so this grace keeps a momentary mDNS glitch from flapping the device.
RESOLUTION_GRACE = 3


def is_resolution_error(error) -> bool:
    """True if an error looks like a transient name-resolution (mDNS) failure.

    A device that is actually down fails differently (connection refused / timeout
    to a resolved IP), so callers can fast-retry resolution glitches while letting
    genuine failures take the normal exponential-backoff path.
    """
    if error is None:
        return False
    text = str(error).lower()
    return any(
        marker in text
        for marker in (
            "dns server returned",  # systemd-resolved SERVFAIL on .local
            "temporary failure in name",  # EAI_AGAIN
            "name or service not known",  # EAI_NONAME
            "name resolution",
            "getaddrinfo",
        )
    )


class _SystemResolver(AbstractResolver):
    """Resolve names through the OS resolver (glibc getaddrinfo / nss-mdns).

    Under uvloop (used by uvicorn/NiceGUI), aiohttp's default resolver delegates
    to libuv's native getaddrinfo, which fails on mDNS .local names in this app —
    while the sync `requests` path, which uses glibc getaddrinfo, resolves the
    very same names fine. Running socket.getaddrinfo in a thread routes the async
    client through that working glibc/Avahi path so .local resolution succeeds.
    """

    async def resolve(
        self, host: str, port: int = 0, family: int = socket.AF_INET
    ) -> List[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        infos = await loop.run_in_executor(
            None,
            functools.partial(
                socket.getaddrinfo,
                host,
                port,
                family,
                socket.SOCK_STREAM,
            ),
        )
        results: List[Dict[str, Any]] = []
        for fam, _type, proto, _canonname, sockaddr in infos:
            results.append(
                {
                    "hostname": host,
                    "host": sockaddr[0],
                    "port": sockaddr[1],
                    "family": fam,
                    "proto": proto,
                    "flags": socket.AI_NUMERICHOST,
                }
            )
        return results

    async def close(self) -> None:
        pass


# Shared, stateless resolver instance for all device connectors.
SYSTEM_RESOLVER = _SystemResolver()


class ApiErrorType(Enum):
    """Enum for different types of API errors."""

    NETWORK = "network"
    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    RESOURCE_NOT_FOUND = "resource_not_found"
    SERVER_ERROR = "server_error"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


@dataclass
class ApiError(Exception):
    """Custom exception for API errors."""

    message: str
    error_type: ApiErrorType
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    retry_after: Optional[int] = None

    def __str__(self) -> str:
        return f"{self.error_type.value} error ({self.status_code}): {self.message}"


class BaseApiClient:
    """
    Base API client with common functionality for all API clients.

    Attributes:
        base_url (str): Base URL for the API
        timeout (int): Default timeout for requests in seconds
        max_retries (int): Maximum number of retries for failed requests
        retry_delay (int): Initial delay between retries in seconds
        session (aiohttp.ClientSession): HTTP session for making requests
        logger (logging.Logger): Logger for the client
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 10,
        max_retries: int = 3,
        retry_delay: int = 1,
        request_limit: int = 10,
        request_period: int = 1,
        use_tls: bool = False,
        ca_cert_path: Optional[str] = None,
    ):
        """
        Initialize the base API client.

        Args:
            base_url (str): Base URL for the API
            timeout (int): Default timeout for requests in seconds
            max_retries (int): Maximum number of retries for failed requests
            retry_delay (int): Initial delay between retries in seconds
            request_limit (int): Maximum number of requests per period
            request_period (int): Period for request limiting in seconds
            use_tls (bool): Whether to use HTTPS with MycoMonitor CA cert
            ca_cert_path (str, optional): Path to CA certificate file.
                                          Defaults to config/ca_root.pem.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = None
        self.logger = logging.getLogger(f"api.{self.__class__.__name__}")

        # TLS configuration
        self.use_tls = use_tls or self.base_url.startswith("https://")
        self.ca_cert_path = ca_cert_path or str(_CA_CERT_PATH)
        self._ssl_context = None

        # Request throttling
        self.request_limit = request_limit
        self.request_period = request_period
        self.request_times = []

        # Connection status
        self.last_successful_connection = None
        self.connection_failures = 0
        self.is_connected = False

    async def __aenter__(self):
        """Context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.disconnect()

    def _create_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Create an SSL context that trusts the MycoMonitor CA certificate."""
        if not self.use_tls:
            return None

        if self._ssl_context is not None:
            return self._ssl_context

        ca_path = Path(self.ca_cert_path)
        if ca_path.exists():
            ctx = ssl.create_default_context()
            ctx.load_verify_locations(str(ca_path))
            self._ssl_context = ctx
            self.logger.debug(f"SSL context created with CA cert: {ca_path}")
        else:
            # Fall back to no verification if CA cert is missing
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self._ssl_context = ctx
            self.logger.warning(
                f"CA cert not found at {ca_path}, disabling SSL verification"
            )

        return self._ssl_context

    async def connect(self):
        """Create a new HTTP session with optional TLS support."""
        if self.session is None or self.session.closed:
            ssl_ctx = self._create_ssl_context()
            connector = aiohttp.TCPConnector(
                limit=20,
                force_close=False,
                ssl=ssl_ctx,
                # Devices are IPv4-only and resolved via mDNS (.local). Forcing
                # AF_INET avoids the AAAA lookup, which mdns4_minimal can't answer.
                family=socket.AF_INET,
                # Force glibc/Avahi resolution instead of uvloop's native resolver,
                # which fails on .local names under uvicorn. See _SystemResolver.
                resolver=SYSTEM_RESOLVER,
            )
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                connector=connector,
            )
            self.logger.debug(
                f"Created new session for {self.base_url} (TLS={self.use_tls})"
            )
        return self.session

    async def disconnect(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.debug(f"Closed session for {self.base_url}")
            self.session = None

    async def _throttle_requests(self):
        """
        Throttle requests to respect rate limits.

        This method ensures that we don't exceed the request_limit
        within the request_period.
        """
        now = time.time()

        # Remove request times that are outside the current period
        self.request_times = [
            t for t in self.request_times if now - t <= self.request_period
        ]

        # If we've reached the limit, wait until we can make another request
        if len(self.request_times) >= self.request_limit:
            oldest = min(self.request_times)
            sleep_time = self.request_period - (now - oldest)
            if sleep_time > 0:
                self.logger.debug(f"Throttling: waiting {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)

        # Record this request
        self.request_times.append(time.time())

    def _should_retry(self, error: ApiError) -> bool:
        """
        Determine if a request should be retried based on the error.

        Args:
            error (ApiError): The error that occurred

        Returns:
            bool: True if the request should be retried, False otherwise
        """
        # Don't retry authentication or permission errors
        if error.error_type in [ApiErrorType.AUTHENTICATION, ApiErrorType.PERMISSION]:
            return False

        # Don't retry validation errors
        if error.error_type == ApiErrorType.VALIDATION:
            return False

        # Don't retry if resource not found
        if error.error_type == ApiErrorType.RESOURCE_NOT_FOUND:
            return False

        # Retry network and timeout errors
        if error.error_type in [ApiErrorType.NETWORK, ApiErrorType.TIMEOUT]:
            return True

        # Retry server errors
        if error.error_type == ApiErrorType.SERVER_ERROR:
            return True

        # Don't retry unknown errors by default
        return False

    def _get_retry_delay(self, attempt: int) -> float:
        """
        Get the delay before the next retry attempt.

        Args:
            attempt (int): The current attempt number (0-based)

        Returns:
            float: The delay in seconds
        """
        # Exponential backoff with jitter
        delay = self.retry_delay * (2**attempt)
        jitter = delay * 0.2 * (random.random() * 2 - 1)  # ±20% jitter
        return max(0, delay + jitter)

    def _handle_response_error(
        self, response: aiohttp.ClientResponse, body: str
    ) -> ApiError:
        """
        Handle an error response from the API.

        Args:
            response (aiohttp.ClientResponse): The response object
            body (str): The response body

        Returns:
            ApiError: An ApiError instance
        """
        status = response.status

        if status == 401:
            error_type = ApiErrorType.AUTHENTICATION
            message = "Authentication failed"
        elif status == 403:
            error_type = ApiErrorType.PERMISSION
            message = "Permission denied"
        elif status == 404:
            error_type = ApiErrorType.RESOURCE_NOT_FOUND
            message = "Resource not found"
        elif 400 <= status < 500:
            error_type = ApiErrorType.VALIDATION
            message = f"Client error: {body}"
        elif 500 <= status < 600:
            error_type = ApiErrorType.SERVER_ERROR
            message = f"Server error: {body}"
        else:
            error_type = ApiErrorType.UNKNOWN
            message = f"Unknown error: {body}"

        retry_after = None
        if response.headers.get("Retry-After"):
            try:
                retry_after = int(response.headers["Retry-After"])
            except (ValueError, TypeError):
                pass

        return ApiError(
            message=message,
            error_type=error_type,
            status_code=status,
            response_body=body,
            retry_after=retry_after,
        )

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        expected_status: Optional[List[int]] = None,
        parse_json: bool = True,
    ) -> Any:
        """
        Make an HTTP request to the API with retry logic.

        Args:
            method (str): HTTP method (GET, POST, etc.)
            endpoint (str): API endpoint (will be appended to base_url)
            params (Dict[str, Any], optional): Query parameters
            data (Any, optional): Request body data
            json_data (Dict[str, Any], optional): JSON request body
            headers (Dict[str, str], optional): Request headers
            timeout (int, optional): Request timeout in seconds
            expected_status (List[int], optional): Expected HTTP status codes
            parse_json (bool): Whether to parse the response as JSON

        Returns:
            Any: The response data

        Raises:
            ApiError: If the request fails
        """
        if expected_status is None:
            expected_status = [200]

        if timeout is None:
            timeout = self.timeout

        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"

        url = f"{self.base_url}{endpoint}"

        # Ensure we have a session
        if self.session is None or self.session.closed:
            await self.connect()

        # Apply request throttling
        await self._throttle_requests()

        # Set up timeout for this specific request
        request_timeout = aiohttp.ClientTimeout(total=timeout)

        attempt = 0
        last_error = None

        while attempt <= self.max_retries:
            try:
                self.logger.debug(
                    f"{method} {url} (Attempt {attempt + 1}/{self.max_retries + 1})"
                )

                async with self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    json=json_data,
                    headers=headers,
                    timeout=request_timeout,
                ) as response:
                    # Read the response body
                    body_text = await response.text()

                    # Check if the status code is expected
                    if response.status in expected_status:
                        # Update connection status
                        self.last_successful_connection = time.time()
                        self.connection_failures = 0
                        self.is_connected = True

                        # Parse and return the response
                        if parse_json and body_text:
                            try:
                                return await response.json()
                            except ValueError:
                                # If JSON parsing fails, return the raw text
                                return body_text
                        return body_text
                    else:
                        # Handle error response
                        error = self._handle_response_error(response, body_text)
                        last_error = error

                        # Check if we should retry
                        if not self._should_retry(error) or attempt >= self.max_retries:
                            raise error

            except asyncio.TimeoutError:
                last_error = ApiError(
                    message=f"Request timed out after {timeout}s",
                    error_type=ApiErrorType.TIMEOUT,
                )

            except aiohttp.ClientError as e:
                last_error = ApiError(
                    message=f"Network error: {str(e)}", error_type=ApiErrorType.NETWORK
                )

            except ApiError as e:
                last_error = e

            # Update connection status on failure
            self.connection_failures += 1
            if self.connection_failures >= 3:
                self.is_connected = False

            # If we get here, the request failed and we should retry
            attempt += 1

            if attempt <= self.max_retries:
                # Calculate delay before next retry
                delay = self._get_retry_delay(attempt - 1)

                # If we have a Retry-After header, use that instead
                if last_error and last_error.retry_after:
                    delay = last_error.retry_after

                self.logger.debug(f"Retrying in {delay:.2f}s")
                await asyncio.sleep(delay)

        # If we get here, we've exhausted our retries
        if last_error:
            raise last_error
        else:
            raise ApiError(
                message="Request failed after multiple retries",
                error_type=ApiErrorType.UNKNOWN,
            )

    async def get(self, endpoint: str, **kwargs) -> Any:
        """
        Make a GET request to the API.

        Args:
            endpoint (str): API endpoint
            **kwargs: Additional arguments to pass to _make_request

        Returns:
            Any: The response data
        """
        return await self._make_request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs) -> Any:
        """
        Make a POST request to the API.

        Args:
            endpoint (str): API endpoint
            **kwargs: Additional arguments to pass to _make_request

        Returns:
            Any: The response data
        """
        return await self._make_request("POST", endpoint, **kwargs)

    async def put(self, endpoint: str, **kwargs) -> Any:
        """
        Make a PUT request to the API.

        Args:
            endpoint (str): API endpoint
            **kwargs: Additional arguments to pass to _make_request

        Returns:
            Any: The response data
        """
        return await self._make_request("PUT", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> Any:
        """
        Make a DELETE request to the API.

        Args:
            endpoint (str): API endpoint
            **kwargs: Additional arguments to pass to _make_request

        Returns:
            Any: The response data
        """
        return await self._make_request("DELETE", endpoint, **kwargs)

    async def check_connection(self) -> bool:
        """
        Check if the API is reachable.

        Returns:
            bool: True if the API is reachable, False otherwise
        """
        try:
            # This should be implemented by subclasses to use an appropriate endpoint
            raise NotImplementedError("Subclasses must implement check_connection()")
        except ApiError:
            return False

    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get the current connection status.

        Returns:
            Dict[str, Any]: Connection status information
        """
        return {
            "is_connected": self.is_connected,
            "last_successful_connection": self.last_successful_connection,
            "connection_failures": self.connection_failures,
        }
