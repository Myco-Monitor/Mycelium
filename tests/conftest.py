"""
Pytest configuration for Mycelium tests.

This module provides fixtures and configuration for pytest.
"""

import os
import sys
import pytest
import asyncio
import logging
from typing import Dict, Any, Generator, AsyncGenerator

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def mock_aiohttp_session(monkeypatch):
    """
    Mock aiohttp.ClientSession for testing HTTP clients.
    
    This fixture provides a mock ClientSession that can be configured
    to return predefined responses for specific requests.
    """
    from unittest.mock import AsyncMock, MagicMock
    
    # Create mock response and session
    mock_response = AsyncMock()
    mock_session = AsyncMock()
    
    # Store responses for different URLs
    responses = {}
    
    # Configure the mock session to return appropriate responses
    async def mock_get(url, **kwargs):
        nonlocal responses
        if url in responses:
            response_data = responses[url]
            mock_response.status = response_data.get("status", 200)
            mock_response.text = AsyncMock(return_value=response_data.get("text", ""))
            mock_response.json = AsyncMock(return_value=response_data.get("json", {}))
            return mock_response
        else:
            mock_response.status = 404
            mock_response.text = AsyncMock(return_value="Not Found")
            mock_response.json = AsyncMock(side_effect=ValueError("No JSON"))
            return mock_response
            
    async def mock_post(url, **kwargs):
        nonlocal responses
        if url in responses:
            response_data = responses[url]
            mock_response.status = response_data.get("status", 200)
            mock_response.text = AsyncMock(return_value=response_data.get("text", ""))
            mock_response.json = AsyncMock(return_value=response_data.get("json", {}))
            return mock_response
        else:
            mock_response.status = 404
            mock_response.text = AsyncMock(return_value="Not Found")
            mock_response.json = AsyncMock(side_effect=ValueError("No JSON"))
            return mock_response
    
    # Set up the mock methods
    mock_session.get = mock_get
    mock_session.post = mock_post
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    # Create a function to add responses
    def add_response(url, status=200, text="", json=None):
        responses[url] = {
            "status": status,
            "text": text,
            "json": json or {}
        }
    
    # Add the add_response function to the mock session
    mock_session.add_response = add_response
    
    # Patch aiohttp.ClientSession
    import aiohttp
    monkeypatch.setattr(aiohttp, "ClientSession", MagicMock(return_value=mock_session))
    
    yield mock_session

@pytest.fixture
def mock_sqlite_connection(monkeypatch):
    """
    Mock SQLite connection for testing database operations.
    
    This fixture provides a mock connection that can be configured
    to return predefined results for specific queries.
    """
    from unittest.mock import MagicMock
    
    # Create mock connection and cursor
    mock_cursor = MagicMock()
    mock_connection = MagicMock()
    
    # Store results for different queries
    query_results = {}
    
    # Configure the mock cursor to return appropriate results
    def mock_execute(query, params=None):
        nonlocal query_results
        query_key = (query, str(params) if params else None)
        if query_key in query_results:
            mock_cursor.fetchall.return_value = query_results[query_key].get("fetchall", [])
            mock_cursor.fetchone.return_value = query_results[query_key].get("fetchone", None)
            mock_cursor.lastrowid = query_results[query_key].get("lastrowid", None)
            return mock_cursor
        else:
            mock_cursor.fetchall.return_value = []
            mock_cursor.fetchone.return_value = None
            mock_cursor.lastrowid = None
            return mock_cursor
    
    # Set up the mock methods
    mock_cursor.execute = mock_execute
    mock_connection.cursor.return_value = mock_cursor
    mock_connection.commit = MagicMock()
    
    # Create a function to add query results
    def add_query_result(query, params=None, fetchall=None, fetchone=None, lastrowid=None):
        query_key = (query, str(params) if params else None)
        query_results[query_key] = {
            "fetchall": fetchall or [],
            "fetchone": fetchone,
            "lastrowid": lastrowid
        }
    
    # Add the add_query_result function to the mock connection
    mock_connection.add_query_result = add_query_result
    
    # Patch sqlite3.connect
    import sqlite3
    monkeypatch.setattr(sqlite3, "connect", MagicMock(return_value=mock_connection))
    
    yield mock_connection
