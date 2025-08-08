from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from weather_service import WeatherService
from location_service import LocationService
from llm_service import LLMService
from models import LocationInput, WeatherData, CropRecommendation, TimeRequest, WeatherAnalysis, WeatherTimeRange
import logging
import uvicorn
from datetime import datetime, timezone
from typing import Dict, List

app = FastAPI(
    title="Crop Recommendation API",
    description="Weather-based crop recommendation system using LLM inference",
    version="1.0.0"
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
weather_service = WeatherService()
location_service = LocationService()
llm_service = LLMService()

@app.get("/")
async def root():
    return {
        "status": "active",
        "current_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "service": "Crop Recommendation System"
    }

@app.post("/api/crop-recommendation")
async def get_crop_recommendation(location: LocationInput):
    try:
        current_utc = datetime.now(timezone.utc)
        logger.info(f"Processing request for location: {location.location_name} at {current_utc}")
        
        # Get coordinates from location name
        coordinates = await location_service.get_coordinates(location.location_name)
        
        # If dates not provided, use current date and next 7 days
        if not location.start_date:
            location.start_date = current_utc.strftime("%Y-%m-%d")
        if not location.end_date:
            location.end_date = (current_utc + timedelta(days=7)).strftime("%Y-%m-%d")
        
        # Fetch weather data with coordinates
        weather_data = await weather_service.get_weather_data(
            latitude=coordinates["latitude"],
            longitude=coordinates["longitude"],
            start_date=location.start_date,
            end_date=location.end_date
        )
        
        # Get LLM inference for crop recommendation
        recommendation = await llm_service.get_crop_recommendation(weather_data)
        
        return CropRecommendation(
            recommended_crops=recommendation["crops"],
            confidence_scores=recommendation["scores"],
            weather_summary=weather_data,
            request_time=current_utc.strftime("%Y-%m-%d %H:%M:%S")
        )
    
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/weather/{location_name}")
async def get_weather(location_name: str):
    try:
        current_utc = datetime.now(timezone.utc)
        logger.info(f"Fetching weather for location: {location_name} at {current_utc}")
        
        coordinates = await location_service.get_coordinates(location_name)
        logger.info(f"Retrieved coordinates: {coordinates}")
        
        weather_data = await weather_service.get_weather_data(
            latitude=coordinates["latitude"],
            longitude=coordinates["longitude"]
        )
        
        return {
            "weather_data": weather_data,
            "request_time": current_utc.strftime("%Y-%m-%d %H:%M:%S"),
            "location": {
                "name": location_name,
                "coordinates": coordinates
            }
        }
    
    except Exception as e:
        error_msg = f"Error fetching weather: {str(e)}"
        logger.error(error_msg, exc_info=True)  # Include full stack trace
        raise HTTPException(
            status_code=500,
            detail={
                "error": error_msg,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "location": location_name
            }
        )
    
@app.post("/api/weather/analysis")
async def get_weather_analysis(request: TimeRequest):
    try:
        current_utc = datetime.now(timezone.utc)
        logger.info(f"Processing weather analysis request for {request.location_name} at {request.date} {request.time or 'all day'}")
        
        # Get coordinates
        coordinates = await location_service.get_coordinates(request.location_name)
        
        # Get weather data
        weather_data = await weather_service.get_weather_data(
            latitude=coordinates["latitude"],
            longitude=coordinates["longitude"],
            start_date=request.date,
            end_date=request.date,
            specific_time=request.time
        )
        
        # Get LLM analysis
        analysis = await llm_service.analyze_weather_data(
            weather_data,
            analysis_type=request.analysis_type
        )
        
        return WeatherAnalysis(
            weather_data=weather_data,
            llm_analysis=analysis,
            request_time=current_utc.strftime("%Y-%m-%d %H:%M:%S"),
            location={
                "name": request.location_name,
                "coordinates": coordinates,
                "requested_date": request.date,
                "requested_time": request.time
            }
        )
    
    except Exception as e:
        error_msg = f"Error processing weather analysis: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": error_msg,
                "timestamp": current_utc.strftime("%Y-%m-%d %H:%M:%S"),
                "request": request.dict()
            }
        )

# @app.post("/api/weather/range")
# async def get_weather_range(request: WeatherTimeRange):
#     try:
#         current_utc = datetime.now(timezone.utc)
#         logger.info(f"Fetching weather range for {request.location_name}")
        
#         coordinates = await location_service.get_coordinates(request.location_name)
        
#         weather_data = await weather_service.get_weather_data(
#             latitude=coordinates["latitude"],
#             longitude=coordinates["longitude"],
#             start_date=request.start_date,
#             end_date=request.end_date,
#             include_current=request.include_current
#         )
        
#         response = {
#             "location": {
#                 "name": request.location_name,
#                 "coordinates": coordinates
#             },
#             "request_time": current_utc.strftime("%Y-%m-%d %H:%M:%S"),
#             "weather_data": weather_data
#         }
        
#         if request.with_analysis:
#             analysis = await llm_service.analyze_weather_data(
#                 weather_data,
#                 analysis_type=request.analysis_type
#             )
#             response["llm_analysis"] = analysis
            
#         return response
        
#     except Exception as e:
#         error_msg = f"Error processing weather range request: {str(e)}"
#         logger.error(error_msg, exc_info=True)
#         raise HTTPException(
#             status_code=500,
#             detail={
#                 "error": error_msg,
#                 "timestamp": current_utc.strftime("%Y-%m-%d %H:%M:%S"),
#                 "request": request.dict()
#             }
#         )

@app.post("/api/weather/range")
async def get_weather_range(request: WeatherTimeRange):
    try:
        current_utc = datetime.now(timezone.utc)
        logger.info(f"Fetching weather range for {request.location_name}")
        
        coordinates = await location_service.get_coordinates(request.location_name)
        
        # Get weather data
        weather_data = await weather_service.get_weather_data(
            latitude=coordinates["latitude"],
            longitude=coordinates["longitude"],
            start_date=request.start_date,
            end_date=request.end_date
        )
        
        response = {
            "location": {
                "name": request.location_name,
                "coordinates": coordinates
            },
            "request_time": current_utc.strftime("%Y-%m-%d %H:%M:%SS"),
            "weather_data": weather_data
        }
        
        if request.with_analysis:
            analysis = await llm_service.analyze_weather_data(
                weather_data,
                analysis_type=request.analysis_type
            )
            response["llm_analysis"] = analysis
            
        return response
        
    except Exception as e:
        error_msg = f"Error processing weather range request: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": error_msg,
                "timestamp": current_utc.strftime("%Y-%m-%d %H:%M:%S"),
                "request": request.dict()
            }
        )

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=4,
        log_level="info"
    )