"""
Tests for the base API client.

This module contains tests for the BaseApiClient class.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp
from aiohttp import ClientResponseError, ClientConnectorError

from api.clients.base_client import BaseApiClient, ApiError, ApiErrorType, RetryableError

class TestBaseApiClient:
    """Tests for the BaseApiClient class."""
    
    @pytest.fixture
    def base_client(self):
        """Create a BaseApiClient instance for testing."""
        return BaseApiClient(
            base_url="http://test.example.com",
            timeout=1,
            max_retries=2,
            retry_delay=0.1
        )
    
    @pytest.mark.asyncio
    async def test_get_success(self, base_client, mock_aiohttp_session):
        """Test successful GET request."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://test.example.com/test",
            status=200,
            json={"key": "value"}
        )
        
        # Make request
        result = await base_client.get("/test")
        
        # Verify result
        assert result == {"key": "value"}
    
    @pytest.mark.asyncio
    async def test_get_with_params(self, base_client, mock_aiohttp_session):
        """Test GET request with query parameters."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://test.example.com/test?param=value",
            status=200,
            json={"key": "value"}
        )
        
        # Make request
        result = await base_client.get("/test", params={"param": "value"})
        
        # Verify result
        assert result == {"key": "value"}
    
    @pytest.mark.asyncio
    async def test_post_success(self, base_client, mock_aiohttp_session):
        """Test successful POST request."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://test.example.com/test",
            status=200,
            json={"key": "value"}
        )
        
        # Make request
        result = await base_client.post("/test", data={"data": "value"})
        
        # Verify result
        assert result == {"key": "value"}
    
    @pytest.mark.asyncio
    async def test_get_text_response(self, base_client, mock_aiohttp_session):
        """Test GET request with text response."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://test.example.com/test",
            status=200,
            text="text response"
        )
        
        # Make request
        result = await base_client.get("/test", response_type="text")
        
        # Verify result
        assert result == "text response"
    
    @pytest.mark.asyncio
    async def test_get_404(self, base_client, mock_aiohttp_session):
        """Test GET request with 404 response."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://test.example.com/test",
            status=404,
            text="Not Found"
        )
        
        # Make request and verify exception
        with pytest.raises(ApiError) as excinfo:
            await base_client.get("/test")
        
        # Verify error details
        error = excinfo.value
        assert error.status_code == 404
        assert error.error_type == ApiErrorType.NOT_FOUND
        assert "Not Found" in error.message
    
    @pytest.mark.asyncio
    async def test_get_500(self, base_client, mock_aiohttp_session):
        """Test GET request with 500 response."""
        # Configure mock response
        mock_aiohttp_session.add_response(
            "http://test.example.com/test",
            status=500,
            text="Internal Server Error"
        )
        
        # Make request and verify exception
        with pytest.raises(ApiError) as excinfo:
            await base_client.get("/test")
        
        # Verify error details
        error = excinfo.value
        assert error.status_code == 500
        assert error.error_type == ApiErrorType.SERVER_ERROR
        assert "Internal Server Error" in error.message
    
    @pytest.mark.asyncio
    async def test_retry_on_server_error(self, base_client, mock_aiohttp_session):
        """Test retry on server error."""
        # Configure mock responses - first fails, second succeeds
        mock_aiohttp_session.add_response(
            "http://test.example.com/test",
            status=500,
            text="Internal Server Error"
        )
        
        # Make request
        with pytest.raises(ApiError) as excinfo:
            await base_client.get("/test")
        
        # Verify error details
        error = excinfo.value
        assert error.status_code == 500
        assert error.error_type == ApiErrorType.SERVER_ERROR
        assert "Internal Server Error" in error.message
        
        # Verify retry count
        assert mock_aiohttp_session.get.call_count == 3  # Initial + 2 retries
    
    @pytest.mark.asyncio
    async def test_retry_success(self, base_client, mock_aiohttp_session):
        """Test successful retry after failure."""
        # Create a counter to track calls
        call_count = 0
        
        # Define a side effect function that fails on first call but succeeds on second
        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            mock_response = AsyncMock()
            if call_count == 1:
                # First call fails
                mock_response.status = 500
                mock_response.text = AsyncMock(return_value="Internal Server Error")
                mock_response.json = AsyncMock(side_effect=ValueError("No JSON"))
            else:
                # Subsequent calls succeed
                mock_response.status = 200
                mock_response.text = AsyncMock(return_value="Success")
                mock_response.json = AsyncMock(return_value={"key": "value"})
            
            return mock_response
        
        # Set the side effect on the mock session
        mock_aiohttp_session.get.side_effect = side_effect
        
        # Make request
        result = await base_client.get("/test")
        
        # Verify result
        assert result == {"key": "value"}
        
        # Verify retry count
        assert call_count == 2  # Initial + 1 retry
    
    @pytest.mark.asyncio
    async def test_connection_error(self, base_client, mock_aiohttp_session):
        """Test handling of connection errors."""
        # Configure mock to raise connection error
        mock_aiohttp_session.get.side_effect = ClientConnectorError(
            connection_key=None,
            os_error=OSError("Connection refused")
        )
        
        # Make request and verify exception
        with pytest.raises(ApiError) as excinfo:
            await base_client.get("/test")
        
        # Verify error details
        error = excinfo.value
        assert error.error_type == ApiErrorType.CONNECTION
        assert "Connection refused" in error.message
        
        # Verify retry count
        assert mock_aiohttp_session.get.call_count == 3  # Initial + 2 retries
    
    @pytest.mark.asyncio
    async def test_timeout_error(self, base_client, mock_aiohttp_session):
        """Test handling of timeout errors."""
        # Configure mock to raise timeout error
        mock_aiohttp_session.get.side_effect = asyncio.TimeoutError()
        
        # Make request and verify exception
        with pytest.raises(ApiError) as excinfo:
            await base_client.get("/test")
        
        # Verify error details
        error = excinfo.value
        assert error.error_type == ApiErrorType.TIMEOUT
        assert "Request timed out" in error.message
        
        # Verify retry count
        assert mock_aiohttp_session.get.call_count == 3  # Initial + 2 retries
    
    @pytest.mark.asyncio
    async def test_request_throttling(self, base_client):
        """Test request throttling."""
        # Configure client with throttling
        base_client.request_limit = 2
        base_client.request_period = 1
        
        # Mock the _make_request method to avoid actual HTTP requests
        base_client._make_request = AsyncMock(return_value={"key": "value"})
        
        # Make multiple requests
        start_time = asyncio.get_event_loop().time()
        await asyncio.gather(
            base_client.get("/test1"),
            base_client.get("/test2"),
            base_client.get("/test3")
        )
        end_time = asyncio.get_event_loop().time()
        
        # Verify that throttling occurred (at least 1 second elapsed)
        assert end_time - start_time >= 1.0
        
        # Verify that all requests were made
        assert base_client._make_request.call_count == 3
