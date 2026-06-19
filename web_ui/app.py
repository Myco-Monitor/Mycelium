"""
Mycelium NiceGUI Application.

Main application setup, middleware, and lifecycle management.
"""

import sys
import logging
from pathlib import Path
from nicegui import app, ui

# Ensure project root is on the path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Note: storage_secret is set via ui.run() in run.py
# Auth is enforced per-page (each page checks app.storage.user)
# NiceGUI middleware cannot access per-client storage,
# so page-level guards are the correct pattern.

logger = logging.getLogger(__name__)

# Singleton polling service instance (started/stopped via lifecycle hooks)
_polling_service = None


# --- Import pages (registers @ui.page routes) ---

import web_ui.auth  # noqa: E402, F401 - login, signup, logout

# Import all page modules (registers @ui.page routes)
import web_ui.pages.dashboard  # noqa: E402, F401
import web_ui.pages.settings  # noqa: E402, F401
import web_ui.pages.farm_overview  # noqa: E402, F401
import web_ui.pages.devices  # noqa: E402, F401
import web_ui.pages.alerts  # noqa: E402, F401
import web_ui.pages.analytics  # noqa: E402, F401
import web_ui.pages.business  # noqa: E402, F401
import web_ui.pages.fleet_management  # noqa: E402, F401
import web_ui.pages.health_dashboard  # noqa: E402, F401
import web_ui.pages.relay_scheduler  # noqa: E402, F401


# --- Root redirect ---


@ui.page("/")
def root_redirect():
    """Redirect root to dashboard or login."""
    user = app.storage.user
    if user.get("user_id"):
        ui.navigate.to("/main")
    else:
        from storage.tables.user_settings import count_users

        if count_users() > 0:
            ui.navigate.to("/login")
        else:
            ui.navigate.to("/signup")


# --- REST API mount ---


def mount_rest_api():
    """Mount the FastAPI REST API router."""
    from api.rest_api_fastapi import api_router

    app.include_router(api_router)


# --- Lifecycle hooks ---


@app.on_startup
async def on_startup():
    """Start background services."""
    global _polling_service
    mount_rest_api()

    from api.services.polling_service import PollingService

    _polling_service = PollingService()
    await _polling_service.start()
    logger.info("Polling service started")


@app.on_shutdown
async def on_shutdown():
    """Stop background services."""
    global _polling_service
    if _polling_service:
        await _polling_service.stop()
        _polling_service = None
        logger.info("Polling service stopped")
