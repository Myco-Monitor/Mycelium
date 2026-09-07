# Mycelium

**Mycelium** is the central monitoring, control, and data platform for the **Myco-Monitor** ecosystem — a modular system for precision environmental monitoring in mushroom cultivation.

Mycelium runs locally on a desktop, laptop, or Raspberry Pi. It discovers and polls network-connected **Spore** (sensor), **Hyphae** (controller) and **Sentinel** (grower-air quality) devices over HTTPS, stores every reading in SQLite, and serves a reactive web dashboard built on NiceGUI. All data stays on your network — there is no cloud dependency.

---

## Features

### Live Dashboard
- Device online/offline counts and active alerts at a glance
- One card per grow tent: the Hyphae controller plus its linked Spores, with averaged CO2 / humidity / temperature, barometric pressure from the Hyphae BMP581, and a per-Spore snapshot
- **Grower Environment**: one card per Sentinel air-quality monitor (PM1 / PM2.5 / PM4 / PM10, VOC and NOx indices, CO2, humidity, temperature, pressure) with the EPA AQI band for PM2.5
- Local weather card from OpenWeatherMap (optional, needs an API key)
- Environment metrics always render in the order CO2, humidity, temperature so values line up across every page

### Device Management
- mDNS discovery of `spore-NNNN.local`, `hyphae-NNNN.local` and `sentinel-NNNN.local`, or add a device by typing its hostname
- Every device carries a name of your choosing (it defaults to the mDNS name); rename it any time from its Management tab and the dashboard, reports and alerts follow. A refresh never overwrites it.
- Devices are addressed by mDNS hostname, never raw IP — the device TLS certificates are issued for the hostname
- **Spore**: live readings, diagnostics (uptime, heap, RSSI, error log), remote CO2 calibration, and a per-Spore pressure source — the linked Hyphae's BMP581, or weather-derived station pressure (altitude-corrected) for Spores with no Hyphae
- **Hyphae**: system info, relay configuration, live relay state, on/off schedules, dynamic threshold control
- **Sentinel**: readings, diagnostics and management; a Sentinel sits outside the tents, so its room is optional
- **Management tab** on every device: device credential, OTA firmware update, remove
- Per-device credentials (an 8–64 character device password on firmware 3.6.0+, or a legacy 4–8 digit PIN) stored encrypted; the Mycelium account password is never sent to a device

### Background Polling
- A polling service starts with the app and collects Spore, Hyphae and Sentinel readings, Hyphae pressure, weather, and alert evaluations on independent intervals with jitter and exponential backoff
- Every poll is logged to a device health history, with periodic diagnostics snapshots (heap, RSSI, uptime)
- Firmware version is recorded whenever a device comes back online
- Readings are permanent — nothing is auto-pruned; use date ranges in the UI to narrow what you look at

### Analytics
- **Reports** — how did the period go: pick a room, Spore or Sentinel set and a date range (whole days in your time zone) and get a fixed summary: per-device averages and extremes; **Compliance**, the share of samples inside *your own* alert thresholds with excursion counts and the longest excursion (a metric with no rule says so, there are no built-in targets); **Equipment**, hours and percent on for each relay of the room's Hyphae, excluding test pulses and offline gaps; **Alerts** triggered in the period; a **Daily summary** table of min / average / max per device per day with relay hours and a CSV download; then the trend chart, one row per metric (CO2, humidity, temperature, plus PM2.5 / VOC / NOx when a Sentinel is selected) and a line per device. Harvest Analysis charts yields from the harvest table.
- **Explore** — what exactly happened: free-form charts over any readings table (Spore, Sentinel, weather, Hyphae relay, pressure): pick a device, metrics and a chart type; up to three y-axes for mixed units. No code execution.
- **Data** — take the rows with you: preview and download raw readings as CSV; administrators can delete rows
- All charts follow the light/dark theme, including hover boxes

### Alerts
- Rule types: device offline, threshold high, threshold low, device error, degraded
- Threshold metrics: CO2, temperature, humidity (Spore and Sentinel) and PM2.5, VOC index, NOx index (Sentinel), with a persistence duration
- Hyphae relay error codes are surfaced with plain-language explanations (CO2 uncontrollable, missing calibration credential, humidity target not reached)
- Active alerts, history, acknowledge and resolve; notification by email (SMTP) or webhook, plus in-app toasts — see [docs/email_setup.md](docs/email_setup.md) (Gmail needs an App Password)

### Fleet & OTA
- Upload firmware binaries to a local inventory
- Batch OTA in three steps: pick firmware, pick devices, push — with progress tracking
- Two-phase OTA protocol (start-upload token, then streamed upload) for Spore, Hyphae and Sentinel
- Device Versions and OTA History tabs

### Health Dashboard
- RSSI, heap, uptime, firmware version, response time, last error and online status for every device, fed by the poll-by-poll health log

### Farms, Rooms & Schedules
- Full CRUD for farms and grow rooms; each room shows its assigned devices
- Relay schedule timeline: a 24-hour Gantt view per Hyphae (schedules are edited on the Devices page)

### Accounts & Settings
- The first account created at `/signup` becomes the administrator; further accounts are created by an admin under Settings → User Management (admins can also reset passwords)
- Account passwords are PBKDF2-hashed with a per-user salt; self-service password change
- Preferences: time zone, 12/24-hour clock, °C/°F
- Weather Integration (OpenWeatherMap key) and Email Notifications (SMTP)
- 8 colour themes with light and dark mode, matching the Spore/Hyphae device UIs
- **Hub Updates** (managed hub appliance only): check GitHub release tags and apply an update after re-entering the account password; hidden when Mycelium runs on a laptop

### REST API
- FastAPI router at `/api/v1/` with `X-API-Key` header authentication (keys stored as SHA-256 hashes) and per-key rate limiting
- Endpoints: `health`, `devices`, `devices/{type}/{id}`, `readings/{type}/{id}` and `/latest`, `rooms`, `farms`, `alerts`, `alerts/{id}/acknowledge`, `alerts/{id}/resolve`
- There is no UI for issuing API keys yet; a key must be inserted into the `api_keys` table by hand

### Business (scaffold)
- The Business page is a KPI/navigation dashboard; most management sections are placeholders
- The schema for production (spawn, bulk, harvest), sales, cost and loss of goods, employees and labour exists, but the data-entry pages are not built yet — see [docs/business_page.md](docs/business_page.md) for the design

---

## Project Structure

```plaintext
Mycelium/
├── api/
│   ├── clients/                # aiohttp HTTPS clients: spore, hyphae, sentinel, pressure, weather
│   ├── services/               # polling, discovery, alerts, OTA, calibration, pressure
│   │                           # distribution, weather, email/webhook notifications, hub update
│   └── rest_api_fastapi.py     # /api/v1 REST router
├── web_ui/                     # NiceGUI web application
│   ├── app.py                  # App entry, page imports, REST router, polling lifecycle
│   ├── auth.py                 # Login, signup, logout
│   ├── layout.py               # Shared header, nav drawer, back button
│   ├── theme.py                # 8 colour themes, light/dark mode, shared chart layout
│   ├── format.py               # Timestamp / unit formatting, AQI helper
│   ├── updates.py              # Managed-appliance detection for Hub Updates
│   ├── components/             # Reusable widgets (weather card)
│   └── pages/
│       ├── dashboard.py        # Live farm overview
│       ├── devices.py          # Spore / Hyphae / Sentinel management and control
│       ├── devices_sentinel.py # Sentinel panels (used by devices.py)
│       ├── farm_overview.py    # Farms and rooms
│       ├── alerts.py           # Alert rules, active alerts, history
│       ├── analytics.py        # Reports, Explore, Data tabs + shared chart helpers
│       ├── analytics_reports.py # Reports tab panels (used by analytics.py)
│       ├── fleet_management.py # Firmware inventory, batch OTA, versions, history
│       ├── health_dashboard.py # Device health metrics
│       ├── relay_scheduler.py  # Relay schedule timeline
│       ├── business.py         # Business dashboard scaffold
│       └── settings.py         # Profile, preferences, weather, email, users, hub updates
├── storage/
│   ├── tables/                 # One module per table (devices, readings, alerts, business, ...)
│   ├── create_unified_database.sql
│   ├── initialize_database.py  # Creates the DB and applies additive migrations on startup
│   ├── db_utils.py             # SQLite helpers (WAL mode, parameterized queries)
│   └── crypto.py               # Fernet encryption for secrets at rest
├── config/
│   ├── app_config.json         # App name/host/port and polling intervals
│   └── ca_root.pem             # Myco-Monitor device CA root certificate
├── data/                       # SQLite DB, firmware binaries, encryption keys (gitignored)
├── docs/                       # Deployment, email, certificates, schema, design notes
├── deploy/mycelium-update.sh   # Privileged updater used by the hub appliance
├── scripts/release.sh          # Tag-and-push release helper
├── cert_manager.py             # Per-install local CA and web-UI certificate
├── mdns_advertise.py           # Advertises mycelium.local
├── run.py                      # Application entry point
├── setup.py                    # Environment setup and database initialization
├── version.py                  # Single source of truth for the app version
├── Makefile                    # setup-venv / setup-conda / run / dev / release shortcuts
├── SECURITY.md                 # Security policy and model summary
└── requirements.txt            # Python dependencies
```

---

## Quick Start

### Prerequisites
- Python 3.9 or later (Python 3.13 is supported)
- pip for managing dependencies
- Local network access to Spore, Hyphae and Sentinel devices (optional)

### Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Myco-Monitor/Mycelium.git
   cd Mycelium
   ```

2. **Run the setup script:**

   The setup script builds an isolated environment (virtualenv or conda), installs
   all dependencies into it, and initializes the database. You do **not** need to
   run `pip install` separately.

   ```bash
   # Basic setup (prompts for environment type)
   python setup.py

   # Non-interactive: create a virtualenv named 'mycelium'
   python setup.py --env-type venv

   # Reset database (WARNING: deletes existing data)
   python setup.py --env-type venv --reset-db
   ```

   `make setup-venv` / `make setup-conda` wrap the same steps.

3. **Activate the environment:**
   ```bash
   # virtualenv
   source mycelium/bin/activate
   # OR use the generated helper script
   source activate_mycelium.sh

   # conda
   conda activate mycelium
   ```

4. **Start the application** — HTTPS is the default:

   Over the network (reachable from other devices) — **the default:**
   ```bash
   python run.py
   ```
   Serves HTTPS on port 8443, encrypts logins, auto-generates a per-install
   certificate on first run, and advertises `mycelium.local` over mDNS so any
   computer on the LAN can reach it. Schema migrations run automatically on
   every start.

   Same machine only (loopback) — opt in with `--localhost`:
   ```bash
   python run.py --localhost
   ```

   Development mode (hot reload):
   ```bash
   python run.py --dev
   ```

   > Plain HTTP is available with `--http` (e.g. `python run.py --http`) but it
   > sends logins in the clear — **avoid it** except for throwaway local testing.

5. **Open your browser** — *where* you open it depends on how you started the app:

   | How you started it | Open the browser on… | URL |
   |--------------------|----------------------|-----|
   | `python run.py` — HTTPS on the LAN, **recommended** ✅ | **any device on the same network** (phone, tablet, another computer) | `https://mycelium.local:8443` (or `https://<mycelium-host-ip>:8443`) |
   | `python run.py --localhost` — HTTPS, loopback only | the **same machine** running Mycelium | `https://localhost:8443` (or `https://127.0.0.1:8443`) |
   | `python run.py --http` — plaintext, **avoid** ⚠️ | **any device on the same network** | `http://<mycelium-host-ip>:8051` |
   | `python run.py --http --localhost` — plaintext, loopback only ⚠️ | the **same machine** running Mycelium | `http://localhost:8051` (or `http://127.0.0.1:8051`) |

   > **Always include the port (`:8443`).** Mycelium listens on **8443**, not the
   > default HTTPS port 443, so `https://mycelium.local` with no port will fail to
   > connect — type the full **`https://mycelium.local:8443`**. (Easy to drop the
   > `:8443` on a phone keyboard.)
   >
   > **Default binds to `0.0.0.0` (the whole LAN):** the UI is reachable from any
   > device on the same network. To restrict it to **only the machine running
   > Mycelium** (loopback), start it with `--localhost`.
   >
   > **On an Android phone/tablet, `mycelium.local` may not load** — Android has
   > no system-wide `.local` (mDNS) resolver. Use the host's IP instead
   > (`https://<mycelium-host-ip>:8443`); it works the same and the cert covers it.
   > See [docs/deployment.md](docs/deployment.md#myceliumlocal) for details.
   >
   > First HTTPS run generates a per-install **local CA**. On **each device you
   > browse from**, import `config/mycelium_local_ca.pem` into the browser once
   > (like `ca_root.pem`) for warning-free HTTPS — or just accept the one-time
   > warning. See [docs/deployment.md](docs/deployment.md).

6. **Create the first account** at `/signup`. The first account becomes the
   administrator; after that, new accounts are created from Settings → User
   Management.

7. **Add your devices** on the Devices page: run mDNS discovery, or type a
   hostname such as `spore-1234` together with its device password (or legacy
   PIN). Link each Spore to its Hyphae and assign devices to rooms from there.

---

## Command Line Options

```
python run.py [OPTIONS]

Options:
  --host HOST     Interface to bind to (default: 0.0.0.0, the whole LAN)
  --localhost     Bind to loopback only (127.0.0.1); reachable from this PC only
  --port PORT     Port to bind to (default: 8443 HTTPS / 8051 with --http)
  --debug         Enable debug mode
  --dev           Development mode (auto-reload, verbose logging)
  --http          Serve over plain HTTP instead of HTTPS (INSECURE)
  --https         Serve over HTTPS (the default; accepted for symmetry)
  --cert PATH     TLS certificate (PEM); implies HTTPS
  --key PATH      TLS private key (PEM)
```

By default the server is reachable across the LAN at `https://mycelium.local:8443`
(use `--localhost` to restrict it to the host machine). HTTPS is on by default, so logins are encrypted; see
[docs/deployment.md](docs/deployment.md) for the full security model (TLS, secrets
at rest, host hardening).

---

## Pages

| Page | Route | Description |
|------|-------|-------------|
| Dashboard | `/dashboard` | Live farm overview: per-tent cards, Grower Environment, weather, alerts |
| Devices | `/devices` | Spore / Hyphae / Sentinel discovery, control, credentials, OTA |
| Farm Overview | `/farms` | Farm and room CRUD with device counts |
| Alerts | `/alerts` | Active alerts, history, rules |
| Analytics | `/analytics` | Reports (period summary), Explore (free-form charts), Data (raw rows + CSV) |
| Fleet | `/fleet` | Firmware inventory, batch OTA, device versions, OTA history |
| Health | `/health` | RSSI, heap, uptime, firmware, response time, last error |
| Schedules | `/relay-scheduler` | 24-hour relay schedule timeline per Hyphae |
| Business | `/business` | Business dashboard scaffold |
| Settings | `/settings` | Profile, password, preferences, weather, email ([setup](docs/email_setup.md)), users, hub updates |

---

## Configuration

Only the `app` and `polling` sections of `config/app_config.json` are read by the code:

```json
{
  "app": { "name": "Mycelium Farm Monitor", "debug": false, "host": "0.0.0.0", "port": 8051 },
  "polling": {
    "spore":    { "interval": 60,   "jitter": 5,  "backoff_factor": 2, "max_backoff": 3600,  "enabled": true },
    "hyphae":   { "interval": 60,   "jitter": 5,  "backoff_factor": 2, "max_backoff": 3600,  "enabled": true },
    "sentinel": { "interval": 60,   "jitter": 5,  "backoff_factor": 2, "max_backoff": 3600,  "enabled": true },
    "weather":  { "interval": 1800, "jitter": 60, "backoff_factor": 2, "max_backoff": 14400, "enabled": true },
    "pressure": { "interval": 300,  "jitter": 30, "backoff_factor": 2, "max_backoff": 3600,  "enabled": true },
    "alerts":   { "interval": 60,   "jitter": 5,  "enabled": true }
  }
}
```

Intervals are in seconds. The device CA path (`config/ca_root.pem`), the HTTPS
device port (443) and mDNS discovery are fixed in code. The app version lives in
`version.py`, not in config. Per-user settings (time zone, units, OpenWeatherMap
key, SMTP) are edited on the Settings page and stored in the database.

---

## Security

- **HTTPS for the web UI on by default** (opt out with `--http`) — per-install
  local CA you import once (mkcert-style), or bring your own cert with `--cert`/`--key`
- **HTTPS-only device communication** using CSP-provisioned device certificates
  (`config/ca_root.pem`), addressed by mDNS hostname so certificate validation holds
- **Secrets encrypted at rest** — device credentials, the SMTP password and the
  OpenWeatherMap API key are Fernet-encrypted with a per-install key; the
  session-signing key is generated automatically. All of it lives in the
  gitignored `data/` directory with owner-only permissions
- **Account passwords** stored as PBKDF2-HMAC-SHA256 hashes with a per-user salt;
  sensitive hub actions require re-entering the password
- **REST API** keys stored as SHA-256 hashes, with per-key rate limiting
- **Local-first** — no cloud dependency; your data does not leave your network

See [SECURITY.md](SECURITY.md) for the security policy and
[docs/deployment.md](docs/deployment.md) for the full model and host hardening.

---

## Releases & Updates

- The app version is declared once in `version.py`.
- Releases are annotated git tags `vX.Y.Z` on this repository; `scripts/release.sh`
  tags the current commit from `version.py` (`make release` does the same without pushing).
- On the managed hub appliance, Settings → Hub Updates compares the running
  version against the newest release tag and lets an administrator apply it. The
  privileged step is delegated to `deploy/mycelium-update.sh`, which smoke-tests
  the new checkout and rolls back on failure.
- On a desktop install, update with `git pull` and restart.

---

## Documentation

| Document | Contents |
|----------|----------|
| [docs/deployment.md](docs/deployment.md) | HTTPS for the web UI, `mycelium.local`, secrets at rest, host hardening |
| [docs/trusting-device-certificates.md](docs/trusting-device-certificates.md) | Importing the local CA and device CA into browsers |
| [docs/email_setup.md](docs/email_setup.md) | SMTP / Gmail App Password setup for alert email |
| [docs/consolidated_schema.md](docs/consolidated_schema.md) | Current database schema |
| [docs/database_schema.md](docs/database_schema.md) | Schema design notes and table descriptions |
| [docs/data_management.md](docs/data_management.md) | Validation and time-series handling notes |
| [docs/settings_page.md](docs/settings_page.md) | Settings page design |
| [docs/business_page.md](docs/business_page.md) | Business page design (not yet built) |
| [CLAUDE.md](CLAUDE.md) | Architecture, patterns and device API contract for contributors |

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
- **Sentinel**: ESP32-S3 grower-environment air-quality monitor (PM, VOC, NOx, CO2, temperature, humidity, pressure)
- **Mycelium**: Python data aggregation, control, and analysis platform (open source)

Hardware and support available at [Myco-Monitor](https://myco-monitor.com).

*Precise Control, Maximum Yields*
