import httpx
from typing import Dict, Optional, List
import logging
from datetime import datetime, timedelta

class WeatherService:
    def __init__(self):
        self.base_url = "https://api.open-meteo.com/v1"
        self.logger = logging.getLogger(__name__)

    # async def get_weather_data(
    #     self, 
    #     latitude: float, 
    #     longitude: float,
    #     start_date: Optional[str] = None,
    #     end_date: Optional[str] = None,
    #     specific_time: Optional[str] = None  # Added this parameter
    # ) -> Dict:
    #     try:
    #         self.logger.info(f"Fetching weather data for coordinates: lat={latitude}, lon={longitude}")
            
    #         async with httpx.AsyncClient(timeout=30.0) as client:
    #             params = {
    #                 "latitude": latitude,
    #                 "longitude": longitude,
    #                 "timezone": "UTC",
    #                 "current_weather": True,
    #                 "hourly": "temperature_2m,relativehumidity_2m,precipitation"
    #             }
                
    #             if start_date:
    #                 params["start_date"] = start_date
    #             if end_date:
    #                 params["end_date"] = end_date

    #             self.logger.debug(f"Making request to {self.base_url}/forecast with params: {params}")

    #             response = await client.get(
    #                 f"{self.base_url}/forecast",
    #                 params=params
    #             )
                
    #             self.logger.debug(f"Received response with status code: {response.status_code}")
    #             response.raise_for_status()
    #             weather_data = response.json()

    #             # Process data for specific time if provided
    #             if specific_time:
    #                 weather_data = self._filter_data_for_specific_time(weather_data, specific_time)

    #             self.logger.info("Successfully retrieved weather data")
    #             return self._format_weather_data(weather_data, specific_time)

    #     except Exception as e:
    #         error_msg = f"Error fetching weather data: {str(e)}"
    #         self.logger.error(error_msg)
    #         raise RuntimeError(error_msg)
    async def get_weather_data(
        self, 
        latitude: float, 
        longitude: float,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        specific_time: Optional[str] = None
    ) -> Dict:
        try:
            self.logger.info(f"Fetching weather data for coordinates: lat={latitude}, lon={longitude}")
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {
                    "latitude": latitude,
                    "longitude": longitude,
                    "timezone": "UTC",
                    "hourly": "temperature_2m,relativehumidity_2m,precipitation",
                    "current_weather": True
                }
                
                # Set date parameters
                if start_date and end_date:
                    params["start_date"] = start_date
                    params["end_date"] = end_date
                else:
                    # If no dates provided, get current day data
                    params["start_date"] = current_date
                    params["end_date"] = current_date

                self.logger.debug(f"Making request to {self.base_url}/forecast with params: {params}")
                response = await client.get(
                    f"{self.base_url}/forecast",
                    params=params
                )
                
                self.logger.debug(f"Received response with status code: {response.status_code}")
                response.raise_for_status()
                weather_data = response.json()

                return self._format_weather_data(weather_data, specific_time)

        except Exception as e:
            error_msg = f"Error fetching weather data: {str(e)}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    def _filter_data_for_specific_time(self, weather_data: Dict, specific_time: str) -> Dict:
        """Filter weather data for a specific time."""
        try:
            hourly_data = weather_data.get("hourly", {})
            times = hourly_data.get("time", [])
            
            # Convert specific_time to hour
            target_hour = int(specific_time.split(":")[0])
            
            filtered_data = {
                "hourly": {
                    "time": [],
                    "temperature_2m": [],
                    "relativehumidity_2m": [],
                    "precipitation": []
                }
            }

            for i, time_str in enumerate(times):
                time_hour = int(time_str.split("T")[1].split(":")[0])
                if time_hour == target_hour:
                    filtered_data["hourly"]["time"].append(times[i])
                    filtered_data["hourly"]["temperature_2m"].append(hourly_data["temperature_2m"][i])
                    filtered_data["hourly"]["relativehumidity_2m"].append(hourly_data["relativehumidity_2m"][i])
                    filtered_data["hourly"]["precipitation"].append(hourly_data["precipitation"][i])

            # Copy current weather data
            if "current_weather" in weather_data:
                filtered_data["current_weather"] = weather_data["current_weather"]

            return filtered_data

        except Exception as e:
            self.logger.error(f"Error filtering data for specific time: {str(e)}")
            raise

    # def _format_weather_data(self, raw_data: Dict, specific_time: Optional[str] = None) -> Dict:
    #     try:
    #         hourly = raw_data.get("hourly", {})
    #         current = raw_data.get("current_weather", {})

    #         # Get the relevant index for specific time or use the first available
    #         time_index = 0
    #         if specific_time and hourly.get("time"):
    #             target_hour = int(specific_time.split(":")[0])
    #             for i, time_str in enumerate(hourly["time"]):
    #                 if int(time_str.split("T")[1].split(":")[0]) == target_hour:
    #                     time_index = i
    #                     break

    #         formatted_data = {
    #             "temperature": hourly.get("temperature_2m", [0])[time_index] if hourly.get("temperature_2m") else current.get("temperature", 0),
    #             "humidity": hourly.get("relativehumidity_2m", [0])[time_index] if hourly.get("relativehumidity_2m") else 0,
    #             "precipitation": hourly.get("precipitation", [0])[time_index] if hourly.get("precipitation") else 0,
    #             "soil_moisture": None,
    #             "timestamp": datetime.utcnow(),
    #             "requested_time": specific_time,
    #             "forecast": self._prepare_forecast(hourly, start_index=time_index)
    #         }

    #         return formatted_data

    #     except Exception as e:
    #         self.logger.error(f"Error formatting weather data: {str(e)}")
    #         raise

    def _format_weather_data(self, raw_data: Dict, specific_time: Optional[str] = None) -> Dict:
        try:
            current = raw_data.get("current_weather", {})
            hourly = raw_data.get("hourly", {})
            
            # Format current weather
            current_weather = {
                "temperature": current.get("temperature", 0),
                "time": current.get("time", datetime.now().isoformat()),
                "windspeed": current.get("windspeed", 0),
                "winddirection": current.get("winddirection", 0)
            }

            # Format historical and forecast data
            time_series = []
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            humidity = hourly.get("relativehumidity_2m", [])
            precip = hourly.get("precipitation", [])

            for i in range(len(times)):
                time_series.append({
                    "timestamp": times[i],
                    "temperature": temps[i],
                    "humidity": humidity[i],
                    "precipitation": precip[i]
                })

            return {
                "current": current_weather,
                "hourly": time_series,
                "metadata": {
                    "latitude": raw_data.get("latitude"),
                    "longitude": raw_data.get("longitude"),
                    "timezone": raw_data.get("timezone"),
                    "updated_at": datetime.now().isoformat()
                }
            }

        except Exception as e:
            self.logger.error(f"Error formatting weather data: {str(e)}")
            raise

    def _prepare_forecast(self, hourly_data: Dict, start_index: int = 0) -> List[Dict]:
        try:
            forecast = []
            if not hourly_data:
                return forecast

            times = hourly_data.get("time", [])[start_index:]
            temps = hourly_data.get("temperature_2m", [])[start_index:]
            humidity = hourly_data.get("relativehumidity_2m", [])[start_index:]
            precip = hourly_data.get("precipitation", [])[start_index:]

            # Limit to next 24 hours
            max_entries = min(24, len(times))

            for i in range(max_entries):
                forecast.append({
                    "timestamp": times[i],
                    "temperature": temps[i],
                    "humidity": humidity[i],
                    "precipitation": precip[i]
                })

            return forecast

        except Exception as e:
            self.logger.error(f"Error preparing forecast data: {str(e)}")
            raise