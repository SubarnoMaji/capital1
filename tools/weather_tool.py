from typing import Optional, Dict, Any, List
import requests
from datetime import datetime, timedelta
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict
import json

class WeatherInput(BaseModel):
    """Input schema for the weather tool."""
    location: str = Field(..., description="The location to get weather data for")
    date_range: Optional[str] = Field(None, description="Optional date range in format 'YYYY-MM-DD:YYYY-MM-DD'")
    analysis_type: Optional[str] = Field(
        "current", 
        description="Type of analysis: 'current', 'forecast', or 'historical'"
    )
    
    model_config = ConfigDict(extra="allow")

class WeatherAnalysisTool(BaseTool):
    name: str = "weather_analysis"
    description: str = """
    A specialized tool for analyzing weather data and providing insights for Indian locations using Open-Meteo API.
    Optimized for Indian cities and regions. Input should be a location (preferably Indian city) and optionally a date range and analysis type.
    Returns weather analysis and insights for the specified parameters.
    Supports major Indian cities like Mumbai, Delhi, Bangalore, Chennai, Kolkata, Hyderabad, Pune, etc.
    """
    args_schema: type[BaseModel] = WeatherInput
    
    # Define the API endpoints as class variables
    geocoding_api: str = Field(default="https://geocoding-api.open-meteo.com/v1/search")
    weather_api: str = Field(default="https://api.open-meteo.com/v1/forecast")

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    def _get_coordinates(self, location: str) -> tuple[float, float]:
        """Get coordinates for a location using Open-Meteo Geocoding API."""
        params = {
            "name": location,
            "count": 1,
            "language": "en",
            "format": "json"
        }
        
        try:
            response = requests.get(self.geocoding_api, params=params)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("results"):
                raise ValueError(f"Location not found: {location}")
                
            result = data["results"][0]
            return result["latitude"], result["longitude"]
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error accessing geocoding API: {str(e)}")

    def _get_weather_data(self, lat: float, lon: float, start_date: Optional[str] = None, 
                         end_date: Optional[str] = None) -> Dict:
        """Get weather data from Open-Meteo API."""
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ["temperature_2m", "relative_humidity_2m", "precipitation_probability", 
                      "wind_speed_10m", "weather_code"],
            "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum",
                     "wind_speed_10m_max"],
            "timezone": "UTC",
            "current_weather": True
        }
        
        if start_date and end_date:
            params["start_date"] = start_date
            params["end_date"] = end_date
        
        try:
            response = requests.get(self.weather_api, params=params)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error accessing weather API: {str(e)}")

    def _weather_code_to_condition(self, code: int) -> str:
        """Convert Open-Meteo weather code to human readable condition."""
        conditions = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Foggy",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snow fall",
            73: "Moderate snow fall",
            75: "Heavy snow fall",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail",
        }
        return conditions.get(code, "Unknown")

    def _run(self, query: str = None, location: str = None, date_range: str = None, analysis_type: str = "current", **kwargs: Any) -> str:
        """Execute the weather analysis tool."""
        try:
            # Handle both query-based and structured input
            if query:
                # Parse the natural language query to extract location
                query_lower = query.lower()
                
                # Common patterns for location extraction
                extracted_location = None
                
                # Pattern 1: "weather in [location]"
                if "weather in" in query_lower:
                    extracted_location = query_lower.split("weather in")[-1].strip()
                # Pattern 2: "current weather in [location]"
                elif "current weather in" in query_lower:
                    extracted_location = query_lower.split("current weather in")[-1].strip()
                # Pattern 3: "forecast for [location]"
                elif "forecast for" in query_lower:
                    extracted_location = query_lower.split("forecast for")[-1].strip()
                # Pattern 4: "temperature in [location]"
                elif "temperature in" in query_lower:
                    extracted_location = query_lower.split("temperature in")[-1].strip()
                # Pattern 5: "historical weather analysis for [location]"
                elif "historical weather analysis for" in query_lower:
                    extracted_location = query_lower.split("historical weather analysis for")[-1].strip()
                # Pattern 6: "weather for [location]"
                elif "weather for" in query_lower:
                    extracted_location = query_lower.split("weather for")[-1].strip()
                # Pattern 7: "weather like in [location]"
                elif "weather like in" in query_lower:
                    extracted_location = query_lower.split("weather like in")[-1].strip()
                # Pattern 8: "in [location]" (fallback)
                elif " in " in query_lower:
                    extracted_location = query_lower.split(" in ")[-1].strip()
                else:
                    # If no pattern matches, try to extract the last word as location
                    words = query_lower.split()
                    if len(words) > 0:
                        extracted_location = words[-1].strip()
                
                # Clean up the location (remove punctuation and extra words)
                if extracted_location:
                    # Remove common words that might be at the end
                    extracted_location = extracted_location.replace("?", "").replace(".", "").strip()
                    # Remove common words that shouldn't be part of location
                    common_words = ["the", "for", "next", "few", "days", "past", "week", "current", "weather", "forecast", "historical", "analysis", "today", "like"]
                    location_words = extracted_location.split()
                    
                    # Remove trailing common words
                    while location_words and location_words[-1].lower() in common_words:
                        location_words.pop()
                    
                    extracted_location = " ".join(location_words).strip()
                
                if not extracted_location:
                    return "Error: Could not extract location from query. Please provide a location name."
                
                location = extracted_location
                
                # Determine analysis type from query
                if "forecast" in query_lower:
                    analysis_type = "forecast"
                elif "historical" in query_lower or "past" in query_lower:
                    analysis_type = "historical"
            
            # Use provided location if available, otherwise use extracted location
            if not location:
                return "Error: No location provided. Please specify a location."
            
            # Handle common Indian city name variations
            indian_city_mappings = {
                "kolkata": "Kolkata, India",
                "calcutta": "Kolkata, India",
                "mumbai": "Mumbai, India",
                "bombay": "Mumbai, India",
                "delhi": "Delhi, India",
                "new delhi": "New Delhi, India",
                "bangalore": "Bangalore, India",
                "bengaluru": "Bangalore, India",
                "chennai": "Chennai, India",
                "madras": "Chennai, India",
                "hyderabad": "Hyderabad, India",
                "pune": "Pune, India",
                "ahmedabad": "Ahmedabad, India",
                "jaipur": "Jaipur, India",
                "lucknow": "Lucknow, India",
                "kanpur": "Kanpur, India",
                "nagpur": "Nagpur, India",
                "indore": "Indore, India",
                "thane": "Thane, India",
                "bhopal": "Bhopal, India",
                "visakhapatnam": "Visakhapatnam, India",
                "vizag": "Visakhapatnam, India",
                "patna": "Patna, India",
                "vadodara": "Vadodara, India",
                "baroda": "Vadodara, India",
                "ghaziabad": "Ghaziabad, India",
                "ludhiana": "Ludhiana, India",
                "agra": "Agra, India",
                "nashik": "Nashik, India",
                "faridabad": "Faridabad, India",
                "rajkot": "Rajkot, India",
                "kalyan": "Kalyan, India",
                "vasai": "Vasai, India",
                "vashi": "Vashi, India",
                "aurangabad": "Aurangabad, India",
                "dhanbad": "Dhanbad, India",
                "amritsar": "Amritsar, India",
                "allahabad": "Allahabad, India",
                "prayagraj": "Allahabad, India",
                "ranchi": "Ranchi, India",
                "howrah": "Howrah, India",
                "coimbatore": "Coimbatore, India",
                "jabalpur": "Jabalpur, India",
                "gwalior": "Gwalior, India",
                "vijayawada": "Vijayawada, India",
                "jodhpur": "Jodhpur, India",
                "madurai": "Madurai, India",
                "raipur": "Raipur, India",
                "kota": "Kota, India",
                "guwahati": "Guwahati, India",
                "chandigarh": "Chandigarh, India",
                "solapur": "Solapur, India",
                "hubli": "Hubli, India",
                "hubballi": "Hubli, India",
                "mysore": "Mysore, India",
                "mysuru": "Mysore, India",
                "tiruchirappalli": "Tiruchirappalli, India",
                "trichy": "Tiruchirappalli, India",
                "bhubaneswar": "Bhubaneswar, India",
                "salem": "Salem, India",
                "warangal": "Warangal, India",
                "mira": "Mira, India",
                "bhiwandi": "Bhiwandi, India",
                "srinagar": "Srinagar, India",
                "dehradun": "Dehradun, India",
                "asansol": "Asansol, India",
                "berhampur": "Berhampur, India",
                "durgapur": "Durgapur, India",
                "nanded": "Nanded, India",
                "kolhapur": "Kolhapur, India",
                "ajmer": "Ajmer, India",
                "akola": "Akola, India",
                "gulbarga": "Gulbarga, India",
                "jamnagar": "Jamnagar, India",
                "udaipur": "Udaipur, India",
                "mathura": "Mathura, India",
                "loni": "Loni, India",
                "bareilly": "Bareilly, India",
                "moradabad": "Moradabad, India",
                "aligarh": "Aligarh, India",
                "rohtak": "Rohtak, India",
                "bhilai": "Bhilai, India",
                "firozabad": "Firozabad, India",
                "kochi": "Kochi, India",
                "cochin": "Kochi, India",
                "gorakhpur": "Gorakhpur, India",
                "mangalore": "Mangalore, India",
                "mangaluru": "Mangalore, India",
                "jamshedpur": "Jamshedpur, India",
                "cuttack": "Cuttack, India",
                "bikaner": "Bikaner, India",
                "burhanpur": "Burhanpur, India",
                "hisar": "Hisar, India",
                "panipat": "Panipat, India",
                "karnal": "Karnal, India",
                "bathinda": "Bathinda, India",
                "ratlam": "Ratlam, India",
                "sonipat": "Sonipat, India",
                "noida": "Noida, India",
                "gurgaon": "Gurgaon, India",
                "gurugram": "Gurgaon, India",
                "meerut": "Meerut, India",
                "pimpri": "Pimpri, India",
                "chinchwad": "Pimpri, India",
                "pimpri chinchwad": "Pimpri, India"
            }
            
            # Check if the location matches any Indian city mapping
            location_lower = location.lower()
            if location_lower in indian_city_mappings:
                location = indian_city_mappings[location_lower]
            
            # Get coordinates for the location
            lat, lon = self._get_coordinates(location)
            
            # Set up date range
            start_date = None
            end_date = None
            if analysis_type == "forecast":
                start_date = datetime.utcnow().strftime("%Y-%m-%d")
                end_date = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")
            elif analysis_type == "historical":
                end_date = datetime.utcnow().strftime("%Y-%m-%d")
                start_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
            
            # Get weather data
            weather_data = self._get_weather_data(lat, lon, start_date, end_date)
            
            # Format based on analysis type
            if analysis_type == "current":
                return self._format_current_weather(weather_data, location)
            elif analysis_type == "forecast":
                return self._format_forecast_weather(weather_data, location)
            elif analysis_type == "historical":
                return self._format_historical_weather(weather_data, location)
            else:
                return f"Unsupported analysis type: {analysis_type}"
                
        except Exception as e:
            return f"Error: {str(e)}"

    def _format_current_weather(self, data: Dict, location: str) -> str:
        """Format current weather data."""
        current = data["current_weather"]
        return f"""
Current weather in {location}:
Temperature: {current['temperature']}°C
Conditions: {self._weather_code_to_condition(current['weathercode'])}
Wind Speed: {current['windspeed']} km/h
Last Updated: {current['time']} UTC
"""

    def _format_forecast_weather(self, data: Dict, location: str) -> str:
        """Format weather forecast data."""
        daily = data["daily"]
        forecast_text = f"Weather forecast for {location}:\n"
        
        for i in range(len(daily["time"])):
            forecast_text += f"""
Date: {daily['time'][i]}
Temperature: {daily['temperature_2m_min'][i]}°C to {daily['temperature_2m_max'][i]}°C
Precipitation: {daily['precipitation_sum'][i]}mm
Wind Speed (max): {daily['wind_speed_10m_max'][i]} km/h
---"""
        return forecast_text

    def _format_historical_weather(self, data: Dict, location: str) -> str:
        """Format historical weather data."""
        daily = data["daily"]
        
        # Calculate averages
        avg_temp_max = sum(daily["temperature_2m_max"]) / len(daily["temperature_2m_max"])
        avg_temp_min = sum(daily["temperature_2m_min"]) / len(daily["temperature_2m_min"])
        total_precipitation = sum(daily["precipitation_sum"])
        
        return f"""
Historical weather analysis for {location}:
Date Range: {daily['time'][0]} to {daily['time'][-1]}
Average Temperature Range: {avg_temp_min:.1f}°C to {avg_temp_max:.1f}°C
Total Precipitation: {total_precipitation:.1f}mm
Summary: {len(daily['time'])} days analyzed
"""