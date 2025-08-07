import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Crop Recommendation System"
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    DEFAULT_FORECAST_DAYS: int = 7
    
    # Weather API Settings
    WEATHER_API_BASE_URL: str = "https://api.open-meteo.com/v1"
    
    # Location Service Settings
    GEOCODING_API_BASE_URL: str = "https://nominatim.openstreetmap.org"
    
    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    RELOAD: bool = True
    
    class Config:
        env_file = ".env"

settings = Settings()