# Mycelium

**Mycelium** is the central monitoring, control, and data platform for the **Myco-Monitor** ecosystem — a modular system for precision environmental monitoring in mushroom cultivation.

Mycelium runs locally on a desktop, laptop, or Raspberry Pi 4. It discovers and communicates with network-connected **Spore** (sensor) and **Hyphae** (controller) devices over HTTPS, stores data in SQLite, and provides a reactive web dashboard built on NiceGUI.

---

## Features

### Environmental Monitoring
- HTTPS communication with CSP-provisioned device certificates
- mDNS device discovery (`spore-NNNN.local`, `hyphae-NNNN.local`) with CIDR fallback
- Real-time sensor data via WebSocket-driven UI updates
- Timestamped logging of all readings in SQLite
- Plotly-based visualization of CO2, temperature, humidity, and pressure
- Configurable polling intervals and device management
- OpenWeatherMap integration for local weather tracking on the dashboard

### Centralized Device Control
- All Spore and Hyphae operations from one interface
- Relay configuration, testing, scheduling, and dynamic threshold control
- Remote CO2 calibration orchestration
- Ambient pressure distribution from Hyphae BMP581 to all associated Spores
- Per-device PIN vault with encrypted storage

### OTA Firmware Management
- Upload firmware binaries to a local inventory
- Push firmware to individual devices or batch update across the fleet
- Two-phase OTA protocol with progress tracking
- OTA history log with version tracking per device

### Multi-Farm Management
- Multiple farms with individual grow rooms
- Farm overview dashboard with device health statistics
- Room-level device organization and associations

### Alerting & Notifications
- Configurable alert thresholds for environmental parameters
- Alert history with acknowledgment and resolution tracking
- Email notifications via SMTP for critical events (device offline, threshold breach)
- In-app toast notifications

### Analytics
- Interactive notebook-style code cells for ad-hoc analysis
- Pre-built analytics dashboard with time-series charts
- Data export capabilities

### REST API
- FastAPI-based REST API at `/api/v1/`
- API key authentication with rate limiting
- Device, reading, room, farm, and alert endpoints
- Webhook registration for event-driven integrations

### Business Management
- Production tracking (spawn batches, substrates, harvests)
- Inventory management (costs, suppliers, stock levels)
- Sales and customer relationship management
- Employee and labour tracking
- Financial reporting and business intelligence
- All data stays local — no cloud required

---

## Project Structure

```plaintext
Mycelium/
├── api/
│   ├── clients/            # HTTP clients for device communication (HTTPS + mDNS)
│   ├── services/           # Business logic, OTA, discovery, weather, email, etc.
│   ├── rest_api_fastapi.py # FastAPI REST API router
│   └── rest_api.py         # Legacy Flask REST API (kept during migration)
├── web_ui/                 # NiceGUI web application
│   ├── app.py              # App entry point, middleware, lifecycle
│   ├── theme.py            # 8-color theme system + dark/light mode
│   ├── layout.py           # Shared header, nav drawer, back button
│   ├── auth.py             # Login, signup, logout pages
│   ├── pages/              # All application pages
│   │   ├── dashboard.py    # Main dashboard with stats + weather
│   │   ├── devices.py      # Device management + control
│   │   ├── farm_overview.py # Farm and room management
│   │   ├── alerts.py       # Alert rules and history
│   │   ├── analytics.py    # Notebook-style analytics
│   │   ├── business.py     # Business operations dashboard
│   │   ├── fleet_management.py # Firmware upload + OTA management
│   │   ├── health_dashboard.py # Device health overview
│   │   ├── relay_scheduler.py  # Visual relay schedule editor
│   │   └── settings.py     # User profile, preferences, SMTP config
│   └── components/         # Reusable UI components (weather card, etc.)
├── storage/
│   ├── tables/             # Database table operations (30+ modules)
│   ├── migrations/         # Schema migration scripts
│   ├── create_unified_database.sql
│   └── db_utils.py         # SQLite utilities (WAL mode, parameterized queries)
├── config/
│   ├── app_config.json     # Application configuration
│   └── ca_root.pem         # Myco-Monitor CA root certificate
├── data/                   # SQLite DB, firmware binaries, exports
├── run.py                  # Application entry point
├── setup.py                # Setup and installation script
└── requirements.txt        # Python dependencies
```

---

## Quick Start

### Prerequisites
- Python 3.9 or later
- pip for managing dependencies
- Local network access to Spore and Hyphae devices (optional)

### Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/myco-monitor.git
   cd myco-monitor/Mycelium
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the setup script:**
   ```bash
   # Basic setup with sample data
   python setup.py --sample-data

   # Reset database (WARNING: deletes existing data)
   python setup.py --reset-db --sample-data
   ```

4. **Start the application:**
   ```bash
   # NiceGUI application (default, port 8051)
   python run.py

   # Development mode with hot reload
   python run.py --dev

   # Custom host/port
   python run.py --host 0.0.0.0 --port 8080
   ```

5. **Open your browser to:**
   ```
   http://localhost:8051
   ```

---

## Command Line Options

```
python run.py [OPTIONS]

Options:
  --host HOST     Host to bind to (default: 127.0.0.1)
  --port PORT     Port to bind to (default: 8051)
  --debug         Enable debug mode
  --dev           Development mode (hot reload, verbose logging)
```

---

## Pages

| Page | Route | Description |
|------|-------|-------------|
| Dashboard | `/main` | Live farm overview, device stats, weather card |
| Devices | `/devices` | Device management, control, mDNS discovery |
| Farm Overview | `/farms` | Farm and room CRUD, health statistics |
| Alerts | `/alerts` | Alert rules, history, acknowledge/resolve |
| Analytics | `/analytics` | Notebook-style data analysis with Plotly |
| Business | `/business` | Production, sales, inventory, financials |
| Fleet | `/fleet` | Firmware upload, batch OTA, version tracking |
| Health | `/health` | Device health metrics (RSSI, heap, uptime) |
| Schedules | `/relay-scheduler` | Visual relay schedule editor |
| Settings | `/settings` | User profile, preferences, weather API, SMTP email |

---

## Configuration

Application settings are in `config/app_config.json`:

```json
{
  "app": { "name": "Mycelium Farm Monitor", "version": "2.0.0", "port": 8051 },
  "tls": { "ca_cert_path": "config/ca_root.pem", "verify_ssl": true },
  "discovery": { "mdns_enabled": true, "cidr_fallback": true, "scan_port": 443 },
  "devices": { "polling_interval_seconds": 30, "timeout_seconds": 10 }
}
```

---

## Security

- HTTPS-only device communication using CSP-provisioned certificates
- Per-device PIN vault with Fernet encryption
- API key authentication with SHA-256 hashing for REST API
- Rate limiting on API endpoints
- All data stays local — no cloud dependency

---

## Contributing

Contributions are welcome! If you'd like to help improve Mycelium:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Push to the branch and open a Pull Request

Please keep changes focused and follow the existing code style. See `CLAUDE.md` for architecture details and development patterns.

For bug reports and feature requests, open an issue on GitHub.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## About Myco-Monitor

Myco-Monitor is a modular monitoring and control system for small to mid-sized mushroom farms. Components include:

- **Spore**: ESP32-S3 environmental sensor node (CO2, temperature, humidity)
- **Hyphae**: ESP32-S3 controller (6-relay control, pressure sensing, speaker alerts)
- **Mycelium**: Python data aggregation, control, and analysis platform (open source)

Hardware and support available at [Myco-Monitor](https://myco-monitor.com).

*Precise Control, Maximum Yields*
