"""
Configuration file for the Soil Analysis Tool
"""

import os
from typing import List

# API Configuration
SOILGRIDS_BASE_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
OPENAI_MODEL = "gpt-5-mini"
OPENAI_MAX_TOKENS = 1500
OPENAI_TEMPERATURE = 0.7

# Soil Properties Configuration
SOIL_PROPERTIES = [
    "phh2o",      # pH in water
    "soc",        # Soil organic carbon
    "nitrogen",   # Total nitrogen
    "phosporus",  # Available phosphorus  
    "potassium",  # Exchangeable potassium
    "clay",       # Clay content
    "sand",       # Sand content
    "silt",       # Silt content
    "bdod",       # Bulk density
    "cec"         # Cation exchange capacity
]

# Soil Property Units and Conversion Factors
PROPERTY_CONVERSIONS = {
    "phh2o": {"factor": 10, "unit": "pH units", "description": "pH in water"},
    "soc": {"factor": 10, "unit": "%", "description": "Soil organic carbon"},
    "nitrogen": {"factor": 100, "unit": "%", "description": "Total nitrogen"},
    "phosporus": {"factor": 1, "unit": "mg/kg", "description": "Available phosphorus"},
    "potassium": {"factor": 1, "unit": "cmol/kg", "description": "Exchangeable potassium"},
    "clay": {"factor": 10, "unit": "%", "description": "Clay content"},
    "sand": {"factor": 10, "unit": "%", "description": "Sand content"},
    "silt": {"factor": 10, "unit": "%", "description": "Silt content"},
    "bdod": {"factor": 100, "unit": "kg/dm³", "description": "Bulk density"},
    "cec": {"factor": 10, "unit": "cmol/kg", "description": "Cation exchange capacity"}
}

# Default Values for Missing Data
DEFAULT_VALUES = {
    "phh2o": 70,  # pH 7.0 (neutral)
    "soc": 10,    # 1.0% organic carbon
    "nitrogen": 10,  # 0.1% nitrogen
    "phosporus": 20,  # 20 mg/kg phosphorus
    "potassium": 5,   # 5 cmol/kg potassium
    "clay": 250,      # 25% clay
    "sand": 400,      # 40% sand
    "silt": 350,      # 35% silt
    "bdod": 130,      # 1.3 kg/dm³ bulk density
    "cec": 150        # 15 cmol/kg CEC
}

# Soil Quality Thresholds
SOIL_QUALITY_THRESHOLDS = {
    "ph": {
        "very_acidic": 5.0,
        "acidic": 6.0,
        "slightly_acidic": 6.5,
        "neutral": 7.5,
        "alkaline": 8.0
    },
    "organic_carbon": {
        "very_low": 0.5,
        "low": 1.0,
        "moderate": 2.0,
        "high": 3.0
    },
    "nitrogen": {
        "low": 0.1,
        "moderate": 0.2,
        "high": 0.3
    }
}

# Climate Zones based on latitude
CLIMATE_ZONES = {
    "tropical": {"min_lat": -23.5, "max_lat": 23.5},
    "subtropical": {"min_lat": -35, "max_lat": 35},
    "temperate": {"min_lat": -50, "max_lat": 50},
    "cold": {"min_lat": -90, "max_lat": 90}
}

# Available Soil Depths
AVAILABLE_DEPTHS = [
    "0-5cm",
    "0-30cm", 
    "5-15cm",
    "15-30cm",
    "30-60cm",
    "60-100cm",
    "100-200cm"
]

# Report Configuration
REPORT_CONFIG = {
    "title": "🌾 COMPREHENSIVE SOIL ANALYSIS AND CROP RECOMMENDATION REPORT",
    "separator": "=" * 60,
    "section_separator": "=" * 30,
    "save_directory": "reports",
    "file_extension": ".txt"
}

# Environment Variables
def get_openai_api_key() -> str:
    """Get OpenAI API key from environment variables"""
    return os.getenv('OPENAI_API_KEY', '')

def get_report_directory() -> str:
    """Get report save directory"""
    return os.getenv('REPORT_DIR', REPORT_CONFIG["save_directory"])