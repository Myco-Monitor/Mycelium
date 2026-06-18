# API Clients Documentation

This document provides detailed information about the API clients used in the Mycelium project for interacting with Spore and Hyphae devices, as well as external weather data services.

## Table of Contents

1. [Base API Client](#base-api-client)
2. [Spore API Client](#spore-api-client)
3. [Hyphae API Client](#hyphae-api-client)
4. [Weather API Client](#weather-api-client)

## Base API Client

The `BaseApiClient` provides core HTTP functionality used by all other API clients in the system.

### Features

- Connection pooling for efficient resource usage
- Automatic retries with exponential backoff
- Request throttling to prevent overwhelming devices
- Comprehensive error handling and logging
- Support for both HTTP and HTTPS protocols
- Timeout management for network operations

### Usage

```python
from api.clients.base_client import BaseApiClient

# Create a client instance
client = BaseApiClient(
    base_url="http://example.com/api",
    timeout=10,
    max_retries=3,
    retry_delay=1.0,
    throttle_rate=5.0  # requests per second
)

# Make GET request
response = await client.get("/endpoint")

# Make POST request with data
response = await client.post("/endpoint", data={"key": "value"})
```

### Error Handling

The client provides standardized error handling through the `ApiError` exception class, which includes:

- HTTP status code
- Error type classification (client error, server error, network error, etc.)
- Detailed error message
- Original exception (if applicable)

## Spore API Client

The `SporeClient` is designed to interact with Spore environmental monitoring devices.

### Features

- Retrieve current and historical sensor readings
- Set ambient pressure for calibration
- Get device information and status
- Check device connectivity

### Device Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/readings/latest` | Get latest sensor readings |
| `/api/readings/all` | Get all historical readings |
| `/api/info` | Get device information |
| `/api/settings/pressure` | Set ambient pressure |

### Usage

```python
from api.clients.spore_client import SporeClient

# Create a client instance
client = SporeClient(
    ip_address="192.168.1.100",
    timeout=5,
    max_retries=3
)

# Get latest readings
readings = await client.get_latest_readings()

# Set ambient pressure
success = await client.set_ambient_pressure(1013.25)  # hPa

# Get device information
info = await client.get_device_info()

# Check if device is connected
is_connected = await client.check_connection()
```

### Reading Format

Readings are returned as dictionaries with the following structure:

```python
{
    "temperature": 23.5,       # Celsius
    "humidity": 45.2,          # Percent
    "pressure": 1013.25,       # hPa
    "co2": 450,                # ppm
    "tvoc": 125,               # ppb
    "timestamp": 1626619200    # Unix timestamp
}
```

## Hyphae API Client

The `HyphaeClient` is designed to interact with Hyphae relay control devices.

### Features

- Retrieve current and historical sensor readings
- Configure and test relays
- Set thresholds for automated control
- Manage relay schedules and modes
- Get device information and status
- Check device connectivity

### Device Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/readings/latest` | Get latest sensor readings |
| `/api/readings/all` | Get all historical readings |
| `/api/info` | Get device information |
| `/api/relay/config` | Configure relay settings |
| `/api/relay/test` | Test relay operation |
| `/api/relay/thresholds` | Set control thresholds |
| `/api/relay/schedule` | Set relay schedules |
| `/api/relay/mode` | Set relay operation mode |

### Usage

```python
from api.clients.hyphae_client import HyphaeClient

# Create a client instance
client = HyphaeClient(
    ip_address="192.168.1.200",
    timeout=5,
    max_retries=3,
    pin="1234"  # Optional PIN for secure operations
)

# Get latest readings
readings = await client.get_latest_readings()

# Configure relay
config = {
    "relay_id": 1,
    "name": "Humidifier",
    "type": "humidity",
    "normally_open": True
}
success = await client.configure_relay(config)

# Test relay
success = await client.test_relay(1, True)  # Turn on relay 1

# Set threshold
threshold = {
    "relay_id": 1,
    "sensor_type": "humidity",
    "low_threshold": 40.0,
    "high_threshold": 60.0,
    "hysteresis": 5.0
}
success = await client.set_threshold(threshold)

# Set schedule
schedule = {
    "relay_id": 1,
    "schedule": [
        {"day": 0, "start_time": "08:00", "end_time": "20:00", "active": True},
        {"day": 1, "start_time": "08:00", "end_time": "20:00", "active": True},
        # ... other days
    ]
}
success = await client.set_schedule(schedule)

# Set mode
success = await client.set_relay_mode(1, "auto")  # Options: "auto", "manual", "schedule"

# Get device information
info = await client.get_device_info()

# Check if device is connected
is_connected = await client.check_connection()
```

### Reading Format

Readings are returned as dictionaries with the following structure:

```python
{
    "temperature": 23.5,       # Celsius
    "humidity": 45.2,          # Percent
    "light": 450,              # Lux
    "soil_moisture": 65.3,     # Percent
    "relay_states": [1, 0, 0, 1, 0, 0],  # 1=on, 0=off
    "timestamp": 1626619200    # Unix timestamp
}
```

## Weather API Client

The `WeatherClient` is designed to interact with the OpenWeatherMap API to retrieve weather data.

### Features

- Get current weather conditions
- Get weather forecasts
- Get air pollution data
- Support for location lookup by ZIP code or coordinates

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/data/2.5/weather` | Get current weather |
| `/data/2.5/forecast` | Get weather forecast |
| `/data/2.5/air_pollution` | Get air pollution data |

### Usage

```python
from api.clients.weather_client import WeatherClient

# Create a client instance
client = WeatherClient(
    api_key="your_api_key",
    timeout=10,
    max_retries=3
)

# Get current weather by ZIP code
weather = await client.get_current_weather_by_zip("12345", "us")

# Get current weather by coordinates
weather = await client.get_current_weather_by_coords(40.7128, -74.0060)

# Get forecast by ZIP code
forecast = await client.get_forecast_by_zip("12345", "us")

# Get forecast by coordinates
forecast = await client.get_forecast_by_coords(40.7128, -74.0060)

# Get air pollution data
pollution = await client.get_air_pollution_by_coords(40.7128, -74.0060)
```

### Weather Data Format

Current weather data is returned as a dictionary with the following structure:

```python
{
    "temperature": 23.5,              # Celsius
    "feels_like": 24.0,               # Celsius
    "humidity": 45,                   # Percent
    "pressure": 1013,                 # hPa
    "wind_speed": 5.2,                # m/s
    "wind_direction": 180,            # degrees
    "cloud_coverage": 75,             # percent
    "condition": "Clear",             # Main condition
    "condition_description": "clear sky",  # Detailed description
    "timestamp": 1626619200,          # Unix timestamp
    "location_name": "New York"       # City name
}
```

Forecast data includes multiple time points with the same structure plus a datetime field.

Air pollution data includes:

```python
{
    "timestamp": 1626619200,  # Unix timestamp
    "aqi": 2,                 # Air Quality Index (1-5)
    "co": 250.34,             # Carbon monoxide (μg/m³)
    "no": 5.67,               # Nitrogen monoxide (μg/m³)
    "no2": 10.23,             # Nitrogen dioxide (μg/m³)
    "o3": 80.56,              # Ozone (μg/m³)
    "so2": 2.45,              # Sulphur dioxide (μg/m³)
    "pm2_5": 8.12,            # Fine particles (μg/m³)
    "pm10": 12.34,            # Coarse particles (μg/m³)
    "nh3": 1.23               # Ammonia (μg/m³)
}
```
