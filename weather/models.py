from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

class LocationInput(BaseModel):
    location_name: str = Field(..., description="Name of the location (city, region, etc.)")
    start_date: Optional[str] = Field(None, description="Start date for weather data (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date for weather data (YYYY-MM-DD)")

    class Config:
        json_schema_extra = {
            "example": {
                "location_name": "Mumbai, India",
                "start_date": "2025-08-07",
                "end_date": "2025-08-14"
            }
        }

class WeatherData(BaseModel):
    temperature: float = Field(..., description="Temperature in Celsius")
    humidity: float = Field(..., description="Relative humidity in percentage")
    precipitation: float = Field(..., description="Precipitation in millimeters")
    soil_moisture: Optional[float] = Field(None, description="Soil moisture level if available")
    timestamp: datetime = Field(..., description="Timestamp of the weather data")
    forecast: Optional[List[Dict]] = Field(None, description="Weather forecast data")

class CropRecommendation(BaseModel):
    recommended_crops: List[str] = Field(..., description="List of recommended crops")
    confidence_scores: Dict[str, float] = Field(..., description="Confidence scores for each crop")
    weather_summary: WeatherData = Field(..., description="Summary of weather conditions")
    request_time: str = Field(..., description="UTC timestamp of the request")

class TimeRequest(BaseModel):
    location_name: str = Field(..., description="Name of the location (city, region, etc.)")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    time: Optional[str] = Field(None, description="Specific time in HH:MM format (24-hour)")
    include_forecast: Optional[bool] = Field(True, description="Include future forecast data")
    analysis_type: Optional[str] = Field(
        "general",
        description="Type of analysis required (general, agricultural, detailed)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "location_name": "Mumbai, India",
                "date": "2025-08-07",
                "time": "08:30",
                "include_forecast": True,
                "analysis_type": "agricultural"
            }
        }

class WeatherAnalysis(BaseModel):
    weather_data: Dict
    llm_analysis: Dict
    request_time: str
    location: Dict

class WeatherTimeRange(BaseModel):
    location_name: str = Field(..., description="Name of the location")
    start_date: Optional[str] = Field(None, description="Start date for historical data (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date for forecast (YYYY-MM-DD)")
    include_current: bool = Field(True, description="Include current weather data")
    with_analysis: bool = Field(False, description="Include LLM analysis")
    analysis_type: Optional[str] = Field("general", description="Type of analysis (general, agricultural, detailed)")

    class Config:
        json_schema_extra = {
            "example": {
                "location_name": "Mumbai, India",
                "start_date": "2025-08-01",
                "end_date": "2025-08-14",
                "include_current": True,
                "with_analysis": True,
                "analysis_type": "agricultural"
            }
        }