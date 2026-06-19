"""
REST API for Mycelium (FastAPI version)

Provides external REST API endpoints for integration with
third-party tools, automation systems, and custom dashboards.

This is the FastAPI equivalent of rest_api.py (Flask Blueprint),
used by the NiceGUI application.
"""

import hashlib
import secrets
import time
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Depends, Header

from storage.db_utils import execute_query, execute_update, get_timestamp

api_router = APIRouter(prefix="/api/v1")

# Rate limiting storage (in production, use Redis)
rate_limit_store: Dict[str, list] = {}


# --- API Key functions ---


def generate_api_key() -> tuple:
    """Generate a new API key. Returns (key, hashed_key)."""
    key = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(key.encode()).hexdigest()
    return key, hashed


def validate_api_key(key: str) -> Optional[Dict[str, Any]]:
    """Validate an API key and return user info."""
    hashed = hashlib.sha256(key.encode()).hexdigest()

    query = """
    SELECT ak.*, us.user_name as username
    FROM api_keys ak
    JOIN user_settings us ON ak.user_id = us.user_id
    WHERE ak.key_hash = ? AND ak.active = 1
    """
    results = execute_query(query, (hashed,))

    if results:
        update_query = "UPDATE api_keys SET last_used = ? WHERE key_id = ?"
        execute_update(update_query, (get_timestamp(), results[0]["key_id"]))
        return results[0]

    return None


def is_rate_limited(api_key: str, limit: int = 100, window: int = 60) -> bool:
    """Check if API key has exceeded rate limit."""
    now = time.time()
    key = f"rate:{api_key}"

    if key not in rate_limit_store:
        rate_limit_store[key] = []

    rate_limit_store[key] = [t for t in rate_limit_store[key] if now - t < window]

    if len(rate_limit_store[key]) >= limit:
        return True

    rate_limit_store[key].append(now)
    return False


# --- Dependencies ---


async def require_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """FastAPI dependency to require API key authentication."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")

    key_data = validate_api_key(x_api_key)
    if not key_data:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if is_rate_limited(x_api_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    return key_data


# --- Health endpoint (public) ---


@api_router.get("/health")
async def health_check():
    """Get system health status."""
    from storage.tables import device_spore, device_hyphae

    spores = device_spore.get_all_device_spore(active_only=True)
    hyphaes = device_hyphae.get_all_device_hyphae(active_only=True)

    online_spores = sum(1 for d in spores if d.get("is_online"))
    online_hyphaes = sum(1 for d in hyphaes if d.get("is_online"))

    total = len(spores) + len(hyphaes)
    online = online_spores + online_hyphaes

    if total == 0:
        status = "healthy"
    elif (online / total) > 0.9:
        status = "healthy"
    elif (online / total) > 0.5:
        status = "degraded"
    else:
        status = "critical"

    return {
        "status": status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "devices": {
            "spore": {"total": len(spores), "online": online_spores},
            "hyphae": {"total": len(hyphaes), "online": online_hyphaes},
        },
    }


# --- Device endpoints ---


@api_router.get("/devices")
async def list_devices(
    type: Optional[str] = None,
    room_id: Optional[int] = None,
    farm_id: Optional[int] = None,
    api_user=Depends(require_api_key),
):
    """List all devices."""
    from storage.tables import device_spore, device_hyphae

    devices = []

    if type is None or type == "spore":
        if farm_id:
            spores = device_spore.get_devices_by_farm(farm_id)
        elif room_id:
            spores = device_spore.get_all_device_spore(room_id=room_id)
        else:
            spores = device_spore.get_all_device_spore()

        for d in spores:
            d["device_type"] = "spore"
            devices.append(d)

    if type is None or type == "hyphae":
        if farm_id:
            hyphaes = device_hyphae.get_devices_by_farm(farm_id)
        elif room_id:
            hyphaes = device_hyphae.get_all_device_hyphae(room_id=room_id)
        else:
            hyphaes = device_hyphae.get_all_device_hyphae()

        for d in hyphaes:
            d["device_type"] = "hyphae"
            devices.append(d)

    return {"devices": devices, "count": len(devices)}


@api_router.get("/devices/{device_type}/{device_id}")
async def get_device(
    device_type: str, device_id: int, api_user=Depends(require_api_key)
):
    """Get a single device by type and ID."""
    from storage.tables import device_spore, device_hyphae

    if device_type not in ("spore", "hyphae"):
        raise HTTPException(status_code=400, detail="Invalid device type")

    if device_type == "spore":
        device = device_spore.get_device_spore(device_id)
    else:
        device = device_hyphae.get_device_hyphae(device_id)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device["device_type"] = device_type
    return device


# --- Readings endpoints ---


@api_router.get("/readings/{device_type}/{device_id}")
async def get_readings(
    device_type: str,
    device_id: int,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 1000,
    api_user=Depends(require_api_key),
):
    """Get historical readings for a device."""
    from storage.tables import readings_spore, readings_hyphae

    if device_type not in ("spore", "hyphae"):
        raise HTTPException(status_code=400, detail="Invalid device type")

    limit = min(limit, 10000)

    if device_type == "spore":
        readings = readings_spore.get_device_readings(
            device_id, limit=limit, start_ts=start, end_ts=end
        )
    else:
        readings = readings_hyphae.get_device_readings(
            device_id, limit=limit, start_ts=start, end_ts=end
        )

    return {
        "device_id": device_id,
        "device_type": device_type,
        "readings": readings,
        "count": len(readings),
    }


@api_router.get("/readings/{device_type}/{device_id}/latest")
async def get_latest_reading(
    device_type: str, device_id: int, api_user=Depends(require_api_key)
):
    """Get the most recent reading for a device."""
    from storage.tables import readings_spore, readings_hyphae

    if device_type not in ("spore", "hyphae"):
        raise HTTPException(status_code=400, detail="Invalid device type")

    if device_type == "spore":
        reading = readings_spore.get_latest_reading(device_id)
    else:
        reading = readings_hyphae.get_latest_reading(device_id)

    if not reading:
        raise HTTPException(status_code=404, detail="No readings found")

    return reading


# --- Room endpoints ---


@api_router.get("/rooms")
async def list_rooms(farm_id: Optional[int] = None, api_user=Depends(require_api_key)):
    """List all rooms."""
    from storage.tables import grow_rooms

    if farm_id:
        rooms = grow_rooms.get_all_grow_rooms(farm_id=farm_id)
    else:
        rooms = grow_rooms.get_all_grow_rooms()

    return {"rooms": rooms, "count": len(rooms)}


@api_router.get("/rooms/{room_id}")
async def get_room(room_id: int, api_user=Depends(require_api_key)):
    """Get a single room."""
    from storage.tables import grow_rooms, device_spore, device_hyphae

    room = grow_rooms.get_grow_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    spores = device_spore.get_all_device_spore(room_id=room_id)
    hyphaes = device_hyphae.get_all_device_hyphae(room_id=room_id)
    room["spore_count"] = len(spores)
    room["hyphae_count"] = len(hyphaes)

    return room


# --- Farm endpoints ---


@api_router.get("/farms")
async def list_farms(api_user=Depends(require_api_key)):
    """List all farms."""
    from storage.tables import farms

    all_farms = farms.get_all_farms()
    return {"farms": all_farms, "count": len(all_farms)}


@api_router.get("/farms/{farm_id}")
async def get_farm(farm_id: int, api_user=Depends(require_api_key)):
    """Get a single farm with statistics."""
    from storage.tables import farms

    farm = farms.get_farm(farm_id)
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    stats = farms.get_farm_statistics(farm_id)
    farm.update(stats)

    return farm


# --- Alert endpoints ---


@api_router.get("/alerts")
async def list_alerts(
    status: str = "active", days: int = 7, api_user=Depends(require_api_key)
):
    """List alerts."""
    from api.services.alert_service import AlertService

    alert_service = AlertService()

    if status == "active":
        alerts = alert_service.get_active_alerts()
    else:
        alerts = alert_service.get_alert_history(days=days)

    return {"alerts": alerts, "count": len(alerts)}


@api_router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int, request: Request, api_user=Depends(require_api_key)
):
    """Acknowledge an alert."""
    from api.services.alert_service import AlertService

    data = (
        await request.json()
        if request.headers.get("content-type") == "application/json"
        else {}
    )
    notes = data.get("notes")

    alert_service = AlertService()
    success = alert_service.acknowledge_alert(alert_id, api_user["user_id"], notes)

    if success:
        return {"message": "Alert acknowledged"}
    raise HTTPException(status_code=404, detail="Alert not found")


@api_router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int, api_user=Depends(require_api_key)):
    """Resolve an alert."""
    from api.services.alert_service import AlertService

    alert_service = AlertService()
    success = alert_service.resolve_alert(alert_id)

    if success:
        return {"message": "Alert resolved"}
    raise HTTPException(status_code=404, detail="Alert not found")
