# Mycelium Component - CLAUDE.md

This file provides component-specific guidance for the Mycelium data processing engine and web interface.

## Component Overview

Mycelium is the central data processing, device control, and visualization platform for the MycoMonitor ecosystem. It communicates with Spore (sensor) and Hyphae (controller) devices over HTTPS, stores data in SQLite, and provides a reactive web dashboard.

## Technology Stack

- **Web Framework**: NiceGUI (FastAPI + Vue.js/Quasar + WebSocket)
- **REST API**: FastAPI with API key auth and rate limiting
- **Database**: SQLite with WAL mode, parameterized queries
- **Data Processing**: Pandas for analytics
- **Device Communication**: aiohttp with HTTPS (CSP CA cert), mDNS discovery (zeroconf)
- **Charting**: Plotly via `ui.plotly()`
- **Email**: Python smtplib (stdlib) for SMTP alert notifications
- **Testing**: pytest with mock device servers

## Directory Structure

```
Mycelium/
├── api/
│   ├── clients/                # HTTP clients for Spore/Hyphae devices
│   │   ├── base_client.py      # aiohttp base with HTTPS/retry/throttle
│   │   ├── spore_client.py     # Spore device API client
│   │   ├── hyphae_client.py    # Hyphae device API client
│   │   ├── weather_client.py   # OpenWeatherMap client
│   │   └── pressure_client.py  # Pressure data client
│   ├── services/               # Business logic services
│   │   ├── discovery_service.py         # mDNS + CIDR device discovery
│   │   ├── polling_service.py           # Background data collection
│   │   ├── ota_service.py               # Two-phase OTA upload orchestration
│   │   ├── email_service.py             # SMTP email notifications
│   │   ├── pressure_distribution_service.py  # Push pressure to Spores
│   │   ├── calibration_orchestration_service.py
│   │   ├── reconnection_service.py      # Pull cached data after offline
│   │   ├── alert_service.py             # Threshold evaluation
│   │   ├── weather_service.py           # OWM weather integration
│   │   ├── health_service.py            # Device health monitoring
│   │   └── ...
│   └── rest_api_fastapi.py     # FastAPI REST API router
├── web_ui/                     # NiceGUI web application
│   ├── app.py                  # App entry, middleware, lifecycle, page imports
│   ├── theme.py                # 8-color theme + dark/light mode
│   ├── layout.py               # Shared header, nav drawer, back button
│   ├── auth.py                 # Login, signup, logout pages
│   ├── pages/                  # Application pages (@ui.page routes)
│   │   ├── dashboard.py        # Main dashboard + weather + pressure cards
│   │   ├── devices.py          # Device management + centralized control
│   │   ├── farm_overview.py    # Farm/room CRUD
│   │   ├── alerts.py           # Alert rules + history
│   │   ├── analytics.py        # Notebook-style analysis
│   │   ├── business.py         # Business operations
│   │   ├── fleet_management.py # Firmware upload + batch OTA
│   │   ├── health_dashboard.py # Device health overview
│   │   ├── relay_scheduler.py  # Visual relay schedule editor
│   │   └── settings.py         # User profile, prefs, SMTP config
│   └── components/             # Reusable NiceGUI components
│       ├── weather_card.py     # OWM weather card with auto-refresh
│       └── pressure_card.py    # BMP581 pressure card with auto-refresh
├── storage/
│   ├── tables/                 # 30+ database table modules
│   ├── migrations/             # Additive schema migrations
│   ├── create_unified_database.sql
│   ├── initialize_database.py
│   └── db_utils.py             # SQLite utilities
├── config/
│   ├── app_config.json         # App config (port 8051, TLS, discovery)
│   └── ca_root.pem             # MycoMonitor CA root certificate
├── data/                       # SQLite DB, firmware binaries, exports
├── tests/                      # pytest tests
├── run.py                      # Entry point
├── setup.py                    # Setup script
└── requirements.txt            # Dependencies
```

## Running the Application

```bash
# Activate environment first
source activate_mycelium.sh
# OR: conda activate mycelium

# NiceGUI application (default, port 8051)
python run.py

# Development mode with hot reload
python run.py --dev

# Custom host/port
python run.py --host 0.0.0.0 --port 8080

# Sentinel mode (simulated devices)
python run.py --sentinel --dev
```

## Architecture

### Data Flow
1. **Discovery**: mDNS (`zeroconf`) discovers `spore-NNNN.local` / `hyphae-NNNN.local`, CIDR scan as fallback
2. **Collection**: API clients poll devices over HTTPS (CA cert from CSP), polling_service manages intervals
3. **Storage**: SQLite with WAL mode, 30+ table modules for readings, devices, alerts, business data
4. **Processing**: Background services handle pressure distribution, reconnection, alert evaluation
5. **Visualization**: NiceGUI pages render with WebSocket live updates via `ui.timer()` and `@ui.refreshable`
6. **Notifications**: Email alerts via SMTP for critical events, in-app toasts for all events

### Key Patterns

**NiceGUI page pattern:**
```python
from nicegui import ui, app
from web_ui.layout import page_layout, back_to_dashboard
from web_ui.theme import get_colors

@ui.page('/my-page')
def my_page():
    user = app.storage.user
    if not user.get('user_id'):
        ui.navigate.to('/login')
        return
    page_layout('My Page')
    back_to_dashboard()
    colors = get_colors()
    # ... page content ...
```

**Theme system:**
- 8 color themes (purple default) aligned to Spore/Hyphae device UIs
- Dark mode: backgrounds `#333`/`#4d4d4d`, Light mode: `#c2c2c2`/`#a8a8a8`
- Theme stored in `app.storage.user`, applied via `apply_theme()` which sets Quasar colors + CSS

**Auth pattern:**
- Session via `app.storage.user` (contains `user_id`, `username`)
- Each page checks `user.get('user_id')` — no middleware (NiceGUI limitation)
- Login/signup in `web_ui/auth.py`

**PIN management:**
- Two-tier: per-device PIN in `device_pins` table, fallback to user's default PIN in `user_settings`
- `device_pins.py` uses Fernet encryption with key in `data/.pin_key`
- OTA service resolves PIN via `_resolve_pin(device_id, device_type, user_id)`

### Package naming
The NiceGUI UI package is `web_ui/` (not `ui/`) because `ui` conflicts with `from nicegui import ui`.

## Configuration

`config/app_config.json`:
```json
{
  "app": { "name": "Mycelium Farm Monitor", "version": "2.0.0", "port": 8051 },
  "tls": { "ca_cert_path": "config/ca_root.pem", "verify_ssl": true },
  "discovery": { "mdns_enabled": true, "cidr_fallback": true, "scan_port": 443 },
  "devices": { "polling_interval_seconds": 30, "timeout_seconds": 10 }
}
```

## Device Communication

### Spore API (HTTPS, port 443)
- `GET /api/readings/latest` — Latest EMA-filtered reading
- `GET /api/diagnostics` — System info (uptime, heap, RSSI, errors)
- `GET /api/status` — Calibration state
- `GET /api/ota/status` — OTA progress
- `POST /api/ambient-pressure` — Set ambient pressure
- `POST /api/calibrate` — Remote CO2 calibration (PIN required)
- `POST /api/ota/start-upload` + `/api/ota/upload-stream` — Two-phase OTA (PIN required)

### Hyphae API (HTTPS, port 443)
- `GET /api/system/info` — System info + relay states
- `GET /api/relay/config|groups|state|thresholds|schedule` — Relay data
- `POST /api/relay/test|config|groups/set|thresholds|schedule|mode` — Relay control (PIN required)
- `POST /api/ota/start-upload` + `/api/ota/upload-stream` — Two-phase OTA (PIN required)

## Development Guidelines

- Follow PEP 8, use type hints
- Use parameterized SQL queries (never string interpolation)
- NiceGUI pages go in `web_ui/pages/`, register imports in `web_ui/app.py`
- Reusable widgets go in `web_ui/components/`
- New DB tables go in `storage/tables/`, add migration in `storage/migrations/`
- Backend services go in `api/services/`
- KISS and YAGNI — see project root CLAUDE.md

## Background Services

The `PollingService` starts automatically on app startup and manages:
- **Spore polling** (60s) — sensor readings from all registered Spore devices
- **Hyphae polling** (60s) — relay state, system info from Hyphae devices
- **Pressure polling** (5min) — BMP581 barometric pressure from Hyphae, distributed to associated Spores for CO2 calibration
- **Weather polling** (30min) — OpenWeatherMap data (optional, requires API key in Settings)
- **Alert checking** (60s) — evaluates alert rules and triggers notifications

Intervals and backoff settings are configured in `config/app_config.json` under the `polling` key.
