# Weather Analysis and Crop Recommendation System

A FastAPI-based service that provides weather data analysis and crop recommendations using weather data from Open-Meteo API and LLM-powered insights.

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Endpoints](#api-endpoints)
- [Usage Examples](#usage-examples)
- [Data Formats](#data-formats)
- [Error Handling](#error-handling)

## Features
- Current weather data retrieval
- Historical weather data analysis
- Weather forecasting
- LLM-powered weather analysis
- Agricultural recommendations
- Custom date range queries
- Location-based weather information

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd weather-analysis-system
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
# Create .env file
cp .env.example .env

# Add your OpenAI API key
OPENAI_API_KEY=your-api-key-here
```

4. Run the application:
```bash
python run.py
# or
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

## Configuration

Required environment variables:
- `OPENAI_API_KEY`: Your OpenAI API key for LLM analysis
- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)
- `WORKERS`: Number of workers (default: 4)

## API Endpoints

### 1. Get Current Weather
Retrieves current weather data for a specific location.

```bash
curl -X POST "http://localhost:8000/api/weather/range" \
-H "Content-Type: application/json" \
-d '{
    "location_name": "Mumbai, India",
    "with_analysis": false
}'
```

### 2. Get Historical Weather Data
Retrieves weather data for a specific date range in the past.

```bash
curl -X POST "http://localhost:8000/api/weather/range" \
-H "Content-Type: application/json" \
-d '{
    "location_name": "Mumbai, India",
    "start_date": "2025-08-01",
    "end_date": "2025-08-07",
    "with_analysis": false
}'
```

### 3. Get Weather Forecast
Retrieves weather forecast for future dates.

```bash
curl -X POST "http://localhost:8000/api/weather/range" \
-H "Content-Type: application/json" \
-d '{
    "location_name": "Mumbai, India",
    "start_date": "2025-08-07",
    "end_date": "2025-08-14",
    "with_analysis": false
}'
```

### 4. Get Weather Analysis with LLM Insights
Retrieves weather data with AI-powered analysis.

```bash
curl -X POST "http://localhost:8000/api/weather/range" \
-H "Content-Type: application/json" \
-d '{
    "location_name": "Mumbai, India",
    "start_date": "2025-08-01",
    "end_date": "2025-08-14",
    "with_analysis": true,
    "analysis_type": "agricultural"
}'
```

## Usage Examples

### 1. Current Weather Only
```bash
curl -X POST "http://localhost:8000/api/weather/range" \
-H "Content-Type: application/json" \
-d '{
    "location_name": "Mumbai, India",
    "with_analysis": false
}'
```

Response format:
```json
{
    "location": {
        "name": "Mumbai, India",
        "coordinates": {
            "latitude": 19.0760,
            "longitude": 72.8777
        }
    },
    "weather_data": {
        "current": {
            "temperature": 28.5,
            "time": "2025-08-07T08:00:00",
            "windspeed": 3.5,
            "winddirection": 180
        },
        "metadata": {
            "updated_at": "2025-08-07T08:58:28"
        }
    }
}
```

### 2. Historical Analysis with Agricultural Insights
```bash
curl -X POST "http://localhost:8000/api/weather/range" \
-H "Content-Type: application/json" \
-d '{
    "location_name": "Mumbai, India",
    "start_date": "2025-08-01",
    "end_date": "2025-08-07",
    "with_analysis": true,
    "analysis_type": "agricultural"
}'
```

### 3. Future Forecast with Detailed Analysis
```bash
curl -X POST "http://localhost:8000/api/weather/range" \
-H "Content-Type: application/json" \
-d '{
    "location_name": "Mumbai, India",
    "start_date": "2025-08-07",
    "end_date": "2025-08-14",
    "with_analysis": true,
    "analysis_type": "detailed"
}'
```

## Data Formats

### Input Parameters
- `location_name`: String (e.g., "Mumbai, India")
- `start_date`: YYYY-MM-DD format
- `end_date`: YYYY-MM-DD format
- `with_analysis`: boolean
- `analysis_type`: "general" | "agricultural" | "detailed"

### Weather Data Fields
```json
{
    "temperature": "Temperature in Celsius",
    "humidity": "Relative humidity in percentage",
    "precipitation": "Precipitation in millimeters",
    "windspeed": "Wind speed in m/s",
    "winddirection": "Wind direction in degrees"
}
```

### Analysis Types
1. **General Analysis**
   - Basic weather patterns
   - General conditions summary
   - Simple recommendations

2. **Agricultural Analysis**
   - Crop suitability
   - Farming recommendations
   - Irrigation needs
   - Weather risks for agriculture

3. **Detailed Analysis**
   - Technical weather patterns
   - Meteorological insights
   - Detailed forecasting
   - Weather system analysis

## Error Handling

Common error responses:
```json
{
    "detail": {
        "error": "Error message",
        "timestamp": "2025-08-07 08:58:28",
        "request": {
            "location_name": "Mumbai, India",
            "start_date": "2025-08-01",
            "end_date": "2025-08-14"
        }
    }
}
```

Error types:
1. Invalid location
2. Invalid date range
3. API timeout
4. Service unavailable
5. Invalid parameters

## Limitations
- Historical data limited to past 7 days
- Forecast data limited to next 7 days
- Some weather parameters might not be available for all locations
- LLM analysis requires valid OpenAI API key

## Development
Created by: kBrutal
Last Updated: 2025-08-07 08:58:28 UTC