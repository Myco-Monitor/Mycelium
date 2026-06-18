"""
Weather Data Service for Mycelium

This module provides services for handling weather data, including:
- Data retrieval from OpenWeatherMap API
- Data transformation and storage
- Weather forecast management
"""

import asyncio
import logging
import json
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta

from api.clients.weather_client import OpenWeatherMapClient
from storage.tables.readings_weather import create_reading as create_weather_data, get_latest_weather as get_latest_weather_data, get_device_readings as get_weather_data_by_date_range

class WeatherDataService:
    """
    Service for handling weather data.
    
    This service is responsible for:
    - Retrieving weather data from the OpenWeatherMap API
    - Transforming and storing weather data
    - Managing weather forecasts
    """
    
    def __init__(self):
        """Initialize the weather data service."""
        self.logger = logging.getLogger("api.WeatherDataService")
        self.clients: Dict[str, OpenWeatherMapClient] = {}
        
        # Cache for weather data
        self._weather_cache: Dict[str, Dict[str, Any]] = {}
        self._weather_cache_time: Dict[str, datetime] = {}
        self._weather_cache_ttl = timedelta(minutes=30)  # OpenWeatherMap data updates every 10 minutes
        
    def initialize_client(
        self, 
        location_id: str, 
        api_key: str, 
        location: Dict[str, Any], 
        units: str = "metric"
    ) -> OpenWeatherMapClient:
        """
        Initialize an OpenWeatherMap client for a location.
        
        Args:
            location_id (str): Unique identifier for the location
            api_key (str): API key for OpenWeatherMap
            location (Dict[str, Any]): Location information
            units (str): Units for weather data
            
        Returns:
            OpenWeatherMapClient: The initialized client
        """
        client = OpenWeatherMapClient(
            api_key=api_key,
            location=location,
            units=units
        )
        self.clients[location_id] = client
        self.logger.info(f"Initialized client for location {location_id}")
        
        return client
        
    def get_client(self, location_id: str) -> Optional[OpenWeatherMapClient]:
        """
        Get an OpenWeatherMap client for a location.
        
        Args:
            location_id (str): Unique identifier for the location
            
        Returns:
            Optional[OpenWeatherMapClient]: The client, or None if not initialized
        """
        return self.clients.get(location_id)
        
    async def check_api_connection(self, location_id: str) -> bool:
        """
        Check if the OpenWeatherMap API is reachable.
        
        Args:
            location_id (str): Unique identifier for the location
            
        Returns:
            bool: True if the API is reachable, False otherwise
        """
        client = self.get_client(location_id)
        if not client:
            self.logger.error(f"No client initialized for location {location_id}")
            return False
            
        try:
            return await client.check_connection()
        except Exception as e:
            self.logger.error(f"Error checking connection for location {location_id}: {e}")
            return False
            
    async def get_current_weather(
        self, 
        location_id: str, 
        use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get current weather data for a location.
        
        Args:
            location_id (str): Unique identifier for the location
            use_cache (bool): Whether to use cached data if available
            
        Returns:
            Optional[Dict[str, Any]]: Current weather data, or None if unavailable
        """
        # Check if we have cached data
        cache_key = f"{location_id}_current"
        if use_cache and cache_key in self._weather_cache:
            cache_time = self._weather_cache_time.get(cache_key)
            if cache_time and datetime.now() - cache_time < self._weather_cache_ttl:
                return self._weather_cache[cache_key]
                
        client = self.get_client(location_id)
        if not client:
            self.logger.error(f"No client initialized for location {location_id}")
            return None
            
        try:
            # Get weather data from API
            weather_data = await client.get_current_weather()
            
            # Transform and store the data
            transformed_data = await self.store_weather_data(location_id, weather_data)
            
            # Cache the data
            self._weather_cache[cache_key] = transformed_data
            self._weather_cache_time[cache_key] = datetime.now()
            
            return transformed_data
        except Exception as e:
            self.logger.error(f"Error getting current weather for location {location_id}: {e}")
            return None
            
    async def get_forecast(
        self, 
        location_id: str, 
        days: int = 5, 
        use_cache: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get weather forecast for a location.
        
        Args:
            location_id (str): Unique identifier for the location
            days (int): Number of days for the forecast
            use_cache (bool): Whether to use cached data if available
            
        Returns:
            Optional[List[Dict[str, Any]]]: Weather forecast data, or None if unavailable
        """
        # Check if we have cached data
        cache_key = f"{location_id}_forecast_{days}"
        if use_cache and cache_key in self._weather_cache:
            cache_time = self._weather_cache_time.get(cache_key)
            if cache_time and datetime.now() - cache_time < self._weather_cache_ttl:
                return self._weather_cache[cache_key]
                
        client = self.get_client(location_id)
        if not client:
            self.logger.error(f"No client initialized for location {location_id}")
            return None
            
        try:
            # Get forecast data from API
            forecast_data = await client.get_forecast(days)
            
            # Transform the data
            transformed_data = self._transform_forecast(location_id, forecast_data)
            
            # Cache the data
            self._weather_cache[cache_key] = transformed_data
            self._weather_cache_time[cache_key] = datetime.now()
            
            return transformed_data
        except Exception as e:
            self.logger.error(f"Error getting forecast for location {location_id}: {e}")
            return None
            
    async def get_air_pollution(
        self, 
        location_id: str, 
        use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get air pollution data for a location.
        
        Args:
            location_id (str): Unique identifier for the location
            use_cache (bool): Whether to use cached data if available
            
        Returns:
            Optional[Dict[str, Any]]: Air pollution data, or None if unavailable
        """
        # Check if we have cached data
        cache_key = f"{location_id}_air"
        if use_cache and cache_key in self._weather_cache:
            cache_time = self._weather_cache_time.get(cache_key)
            if cache_time and datetime.now() - cache_time < self._weather_cache_ttl:
                return self._weather_cache[cache_key]
                
        client = self.get_client(location_id)
        if not client:
            self.logger.error(f"No client initialized for location {location_id}")
            return None
            
        try:
            # Get air pollution data from API
            pollution_data = await client.get_air_pollution()
            
            # Transform the data
            transformed_data = self._transform_air_pollution(location_id, pollution_data)
            
            # Cache the data
            self._weather_cache[cache_key] = transformed_data
            self._weather_cache_time[cache_key] = datetime.now()
            
            return transformed_data
        except Exception as e:
            self.logger.error(f"Error getting air pollution data for location {location_id}: {e}")
            return None
            
    async def store_weather_data(
        self, 
        location_id: str, 
        weather_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform and store weather data in the database.
        
        Args:
            location_id (str): Unique identifier for the location
            weather_data (Dict[str, Any]): Weather data from the API
            
        Returns:
            Dict[str, Any]: Transformed weather data
        """
        try:
            # Transform the data
            transformed_data = self._transform_weather_data(location_id, weather_data)
            
            # Use a stable integer ID for DB storage (extract user number or default to 0)
            try:
                db_device_id = int(location_id.split("_")[-1]) if "_" in location_id else 0
            except (ValueError, IndexError):
                db_device_id = 0

            # Check for duplicates
            if self._is_duplicate(location_id, transformed_data):
                self.logger.debug(f"Duplicate weather data for location {location_id}")
                return transformed_data

            # Store the data — map OWM fields to the DB schema
            weather_id = create_weather_data(
                device_id=db_device_id,
                reading_ts=transformed_data.get("timestamp"),
                current_temp=transformed_data.get("temperature"),
                feels_like=transformed_data.get("feels_like"),
                humidity=transformed_data.get("humidity"),
                ambient_pressure=transformed_data.get("pressure"),
            )
            
            # Add the weather ID to the transformed data
            transformed_data["weather_id"] = weather_id
            
            return transformed_data
        except Exception as e:
            self.logger.error(f"Error storing weather data for location {location_id}: {e}")
            raise
            
    def _transform_weather_data(
        self, 
        location_id: str, 
        weather_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform weather data from the API.
        
        Args:
            location_id (str): Unique identifier for the location
            weather_data (Dict[str, Any]): Weather data from the API
            
        Returns:
            Dict[str, Any]: Transformed weather data
        """
        # Extract timestamp
        timestamp = datetime.fromtimestamp(weather_data.get("dt", 0))
        
        # Extract main weather data
        main = weather_data.get("main", {})
        temperature = main.get("temp")
        feels_like = main.get("feels_like")
        humidity = main.get("humidity")
        pressure = main.get("pressure")
        
        # Extract wind data
        wind = weather_data.get("wind", {})
        wind_speed = wind.get("speed")
        wind_direction = wind.get("deg")
        
        # Extract clouds data
        clouds = weather_data.get("clouds", {}).get("all")
        
        # Extract weather condition
        weather = weather_data.get("weather", [{}])[0]
        weather_condition = weather.get("main")
        weather_description = weather.get("description")
        
        # Extract rain and snow data
        rain_1h = weather_data.get("rain", {}).get("1h", 0)
        snow_1h = weather_data.get("snow", {}).get("1h", 0)
        
        return {
            "location_id": location_id,
            "timestamp": timestamp.isoformat(),
            "temperature": temperature,
            "feels_like": feels_like,
            "humidity": humidity,
            "pressure": pressure,
            "wind_speed": wind_speed,
            "wind_direction": wind_direction,
            "clouds": clouds,
            "weather_condition": weather_condition,
            "weather_description": weather_description,
            "rain_1h": rain_1h,
            "snow_1h": snow_1h
        }
        
    def _transform_forecast(
        self, 
        location_id: str, 
        forecast_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Transform forecast data from the API.
        
        Args:
            location_id (str): Unique identifier for the location
            forecast_data (Dict[str, Any]): Forecast data from the API
            
        Returns:
            List[Dict[str, Any]]: Transformed forecast data
        """
        transformed_data = []
        
        # Extract list of forecasts
        forecasts = forecast_data.get("list", [])
        
        for forecast in forecasts:
            # Extract timestamp
            timestamp = datetime.fromtimestamp(forecast.get("dt", 0))
            
            # Extract temperature data
            temp = forecast.get("temp", {})
            day_temp = temp.get("day")
            min_temp = temp.get("min")
            max_temp = temp.get("max")
            night_temp = temp.get("night")
            evening_temp = temp.get("eve")
            morning_temp = temp.get("morn")
            
            # Extract other data
            humidity = forecast.get("humidity")
            pressure = forecast.get("pressure")
            wind_speed = forecast.get("speed")
            wind_direction = forecast.get("deg")
            clouds = forecast.get("clouds")
            
            # Extract weather condition
            weather = forecast.get("weather", [{}])[0]
            weather_condition = weather.get("main")
            weather_description = weather.get("description")
            
            # Extract rain and snow data
            rain = forecast.get("rain", 0)
            snow = forecast.get("snow", 0)
            
            transformed_data.append({
                "location_id": location_id,
                "timestamp": timestamp.isoformat(),
                "date": timestamp.date().isoformat(),
                "day_temp": day_temp,
                "min_temp": min_temp,
                "max_temp": max_temp,
                "night_temp": night_temp,
                "evening_temp": evening_temp,
                "morning_temp": morning_temp,
                "humidity": humidity,
                "pressure": pressure,
                "wind_speed": wind_speed,
                "wind_direction": wind_direction,
                "clouds": clouds,
                "weather_condition": weather_condition,
                "weather_description": weather_description,
                "rain": rain,
                "snow": snow
            })
            
        return transformed_data
        
    def _transform_air_pollution(
        self, 
        location_id: str, 
        pollution_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform air pollution data from the API.
        
        Args:
            location_id (str): Unique identifier for the location
            pollution_data (Dict[str, Any]): Air pollution data from the API
            
        Returns:
            Dict[str, Any]: Transformed air pollution data
        """
        # Extract list of pollution data (usually just one item)
        pollution_list = pollution_data.get("list", [{}])[0]
        
        # Extract timestamp
        timestamp = datetime.fromtimestamp(pollution_list.get("dt", 0))
        
        # Extract air quality index
        aqi = pollution_list.get("main", {}).get("aqi")
        
        # Extract pollutant concentrations
        components = pollution_list.get("components", {})
        co = components.get("co")
        no = components.get("no")
        no2 = components.get("no2")
        o3 = components.get("o3")
        so2 = components.get("so2")
        pm2_5 = components.get("pm2_5")
        pm10 = components.get("pm10")
        nh3 = components.get("nh3")
        
        return {
            "location_id": location_id,
            "timestamp": timestamp.isoformat(),
            "aqi": aqi,
            "co": co,
            "no": no,
            "no2": no2,
            "o3": o3,
            "so2": so2,
            "pm2_5": pm2_5,
            "pm10": pm10,
            "nh3": nh3
        }
        
    def _is_duplicate(self, location_id: str, weather_data: Dict[str, Any]) -> bool:
        """
        Check if weather data is a duplicate.
        
        A reading is considered a duplicate if there is already a reading
        with the same location ID and timestamp.
        
        Args:
            location_id (str): Unique identifier for the location
            weather_data (Dict[str, Any]): Weather data
            
        Returns:
            bool: True if the data is a duplicate, False otherwise
        """
        # Map location_id to integer device_id for DB lookup
        try:
            db_device_id = int(location_id.split("_")[-1]) if "_" in location_id else 0
        except (ValueError, IndexError):
            db_device_id = 0

        latest_data = get_latest_weather_data(db_device_id)
        if not latest_data:
            return False

        # Parse the timestamps
        try:
            latest_timestamp = datetime.fromisoformat(latest_data.get("reading_ts", ""))
            current_timestamp = datetime.fromisoformat(weather_data["timestamp"])
        except (ValueError, TypeError):
            # If we can't parse the timestamps, assume it's not a duplicate
            return False
            
        # Check if the timestamps are the same
        return latest_timestamp == current_timestamp
