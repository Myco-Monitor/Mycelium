# API Services Documentation

This document provides detailed information about the API services used in the Mycelium project for managing Spore and Hyphae devices, weather data, device discovery, and polling operations.

## Table of Contents

1. [Spore Service](#spore-service)
2. [Hyphae Service](#hyphae-service)
3. [Weather Service](#weather-service)
4. [Discovery Service](#discovery-service)
5. [Polling Service](#polling-service)

## Spore Service

The `SporeService` provides high-level functionality for managing Spore environmental monitoring devices, including data retrieval, storage, and device configuration.

### Features

- Retrieve and store sensor readings
- Manage device information and status
- Set ambient pressure for calibration
- Handle device polling with error recovery
- Prevent duplicate readings in storage

### Usage

```python
from api.services.spore_service import SporeService
from api.clients.spore_client import SporeClient
import sqlite3

# Create database connection
db_connection = sqlite3.connect("mycelium.db")

# Create service instance
service = SporeService(db_connection=db_connection)

# Create client instance
client = SporeClient(ip_address="192.168.1.100")

# Get latest readings
readings = await service.get_latest_readings(client)

# Store readings
success = await service.store_readings(1, readings)

# Set ambient pressure
success = await service.set_ambient_pressure(client, 1013.25)

# Update device status
success = await service.update_device_status(1, True)

# Poll device
success = await service.poll_device(1, "192.168.1.100")
```

### Database Interactions

The service interacts with the following database tables:

- `device_spore`: Stores device information and status
- `readings_spore`: Stores sensor readings with timestamps

## Hyphae Service

The `HyphaeService` provides high-level functionality for managing Hyphae relay control devices, including data retrieval, storage, relay configuration, and automation settings.

### Features

- Retrieve and store sensor readings
- Manage device information and status
- Configure relay settings and thresholds
- Set and manage relay schedules
- Control relay operation modes
- Test relay functionality
- Handle device polling with error recovery
- Prevent duplicate readings in storage

### Usage

```python
from api.services.hyphae_service import HyphaeService
from api.clients.hyphae_client import HyphaeClient
import sqlite3

# Create database connection
db_connection = sqlite3.connect("mycelium.db")

# Create service instance
service = HyphaeService(db_connection=db_connection)

# Create client instance
client = HyphaeClient(ip_address="192.168.1.200", pin="1234")

# Get latest readings
readings = await service.get_latest_readings(client)

# Store readings
success = await service.store_readings(1, readings)

# Configure relay
config = {
    "relay_id": 1,
    "name": "Humidifier",
    "type": "humidity",
    "normally_open": True
}
success = await service.configure_relay(client, config)

# Set threshold
threshold = {
    "relay_id": 1,
    "sensor_type": "humidity",
    "low_threshold": 40.0,
    "high_threshold": 60.0,
    "hysteresis": 5.0
}
success = await service.set_threshold(client, threshold)

# Set schedule
schedule = {
    "relay_id": 1,
    "schedule": [
        {"day": 0, "start_time": "08:00", "end_time": "20:00", "active": True},
        {"day": 1, "start_time": "08:00", "end_time": "20:00", "active": True},
        # ... other days
    ]
}
success = await service.set_schedule(client, schedule)

# Set mode
success = await service.set_relay_mode(client, 1, "auto")

# Test relay
success = await service.test_relay(client, 1, True)

# Update device status
success = await service.update_device_status(1, True)

# Poll device
success = await service.poll_device(1, "192.168.1.200")
```

### Database Interactions

The service interacts with the following database tables:

- `device_hyphae`: Stores device information and status
- `readings_hyphae`: Stores sensor readings with timestamps
- `relay_config`: Stores relay configuration settings
- `relay_thresholds`: Stores threshold settings for automated control
- `relay_schedules`: Stores time-based operation schedules

## Weather Service

The `WeatherService` provides functionality for retrieving and storing weather data from external weather services.

### Features

- Retrieve current weather conditions
- Retrieve weather forecasts
- Retrieve air pollution data
- Store weather data for multiple locations
- Handle polling with error recovery
- Prevent duplicate data in storage

### Usage

```python
from api.services.weather_service import WeatherService
from api.clients.weather_client import WeatherClient
import sqlite3

# Create database connection
db_connection = sqlite3.connect("mycelium.db")

# Create service instance
service = WeatherService(db_connection=db_connection)

# Create client instance
client = WeatherClient(api_key="your_api_key")

# Get current weather
weather = await service.get_current_weather(client, zip_code="12345")

# Store current weather
success = await service.store_current_weather(weather)

# Get forecast
forecast = await service.get_forecast(client, zip_code="12345")

# Store forecast
success = await service.store_forecast(forecast)

# Get air pollution
pollution = await service.get_air_pollution(client, latitude=40.7128, longitude=-74.0060)

# Store air pollution
success = await service.store_air_pollution(pollution)

# Poll weather data
success = await service.poll_weather(client, zip_code="12345")
```

### Database Interactions

The service interacts with the following database tables:

- `weather_locations`: Stores location information
- `weather_current`: Stores current weather conditions
- `weather_forecast`: Stores forecast data
- `weather_air_pollution`: Stores air quality data

## Discovery Service

The `DiscoveryService` provides functionality for discovering and registering Spore and Hyphae devices on the local network.

### Features

- Scan IP ranges for compatible devices
- Identify device types (Spore or Hyphae)
- Register new devices in the database
- Update existing device information
- Link Spore devices to Hyphae controllers

### Usage

```python
from api.services.discovery_service import DiscoveryService
import sqlite3

# Create database connection
db_connection = sqlite3.connect("mycelium.db")

# Create service instance
service = DiscoveryService(db_connection=db_connection)

# Scan an IP range
devices = await service.scan_ip_range("192.168.1", 100, 150)

# Scan a specific IP
device = await service.scan_ip("192.168.1.100")

# Register a device
result = await service.register_device(device)

# Link a Spore device to a Hyphae controller
success = await service.link_devices(spore_id=1, hyphae_id=2)

# Unlink a Spore device
success = await service.unlink_devices(spore_id=1)

# Discover devices on multiple subnets
results = await service.discover_devices(
    subnets=["192.168.1", "10.0.0"],
    ip_ranges=[[100, 150], [2, 10]]
)
```

### Database Interactions

The service interacts with the following database tables:

- `device_spore`: Stores Spore device information
- `device_hyphae`: Stores Hyphae device information
- `rooms`: Manages room assignments for devices

## Polling Service

The `PollingService` provides functionality for regularly polling all registered devices and weather locations to keep data up-to-date.

### Features

- Poll all Spore devices for new readings
- Poll all Hyphae devices for new readings and status
- Poll all weather locations for current conditions
- Manage device online/offline status
- Provide polling statistics
- Support for configurable polling intervals

### Usage

```python
from api.services.polling_service import PollingService
from api.services.spore_service import SporeService
from api.services.hyphae_service import HyphaeService
from api.services.weather_service import WeatherService
import sqlite3

# Create database connection
db_connection = sqlite3.connect("mycelium.db")

# Create service instances
spore_service = SporeService(db_connection=db_connection)
hyphae_service = HyphaeService(db_connection=db_connection)
weather_service = WeatherService(db_connection=db_connection)

# Create polling service
polling_service = PollingService(
    db_connection=db_connection,
    spore_service=spore_service,
    hyphae_service=hyphae_service,
    weather_service=weather_service
)

# Poll Spore devices
spore_results = await polling_service.poll_spore_devices()

# Poll Hyphae devices
hyphae_results = await polling_service.poll_hyphae_devices()

# Poll weather locations
weather_results = await polling_service.poll_weather_locations()

# Poll all devices and locations
all_results = await polling_service.poll_all()

# Start continuous polling
await polling_service.start_polling(interval_seconds=300)

# Update device status
success = await polling_service.update_device_status("spore", 1, False)

# Get polling statistics
stats = await polling_service.get_polling_stats()
```

### Database Interactions

The service interacts with the following database tables through the other services:

- `device_spore`: Updates device status
- `device_hyphae`: Updates device status
- `readings_spore`: Stores new readings (via SporeService)
- `readings_hyphae`: Stores new readings (via HyphaeService)
- `weather_current`: Stores weather data (via WeatherService)
- `weather_forecast`: Stores forecast data (via WeatherService)
- `weather_air_pollution`: Stores air quality data (via WeatherService)
