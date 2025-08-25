"""
Utility functions for the Soil Analysis Tool
"""

import os
import json
import requests
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from models import LocationInfo
from config import (
    CLIMATE_ZONES, 
    PROPERTY_CONVERSIONS, 
    DEFAULT_VALUES,
    SOIL_QUALITY_THRESHOLDS,
    REPORT_CONFIG
)


def determine_climate_zone(latitude: float) -> str:
    """
    Determine climate zone based on latitude
    
    Args:
        latitude: Latitude coordinate
        
    Returns:
        Climate zone string
    """
    abs_lat = abs(latitude)
    
    for zone, bounds in CLIMATE_ZONES.items():
        if abs_lat <= abs(bounds["max_lat"]):
            if zone == "tropical" and abs_lat <= 23.5:
                return "Tropical"
            elif zone == "subtropical" and abs_lat <= 35:
                return "Subtropical"
            elif zone == "temperate" and abs_lat <= 50:
                return "Temperate"
            else:
                return "Cold"
    
    return "Cold"


def validate_coordinates(latitude: float, longitude: float) -> Tuple[bool, str]:
    """
    Validate latitude and longitude coordinates
    
    Args:
        latitude: Latitude value
        longitude: Longitude value
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not (-90 <= latitude <= 90):
        return False, f"Latitude must be between -90 and 90, got {latitude}"
    
    if not (-180 <= longitude <= 180):
        return False, f"Longitude must be between -180 and 180, got {longitude}"
    
    return True, ""


def convert_soil_property(property_name: str, raw_value: Optional[float]) -> float:
    """
    Convert raw soil property value to standard units
    
    Args:
        property_name: Name of the soil property
        raw_value: Raw value from API
        
    Returns:
        Converted value in standard units
    """
    if raw_value is None:
        raw_value = DEFAULT_VALUES.get(property_name, 0)
    
    conversion_info = PROPERTY_CONVERSIONS.get(property_name, {"factor": 1})
    factor = conversion_info["factor"]
    
    return raw_value / factor if factor != 1 else raw_value


def classify_soil_ph(ph: float) -> str:
    """
    Classify soil pH level
    
    Args:
        ph: pH value
        
    Returns:
        pH classification string
    """
    thresholds = SOIL_QUALITY_THRESHOLDS["ph"]
    
    if ph < thresholds["very_acidic"]:
        return "Very Acidic"
    elif ph < thresholds["acidic"]:
        return "Acidic"
    elif ph < thresholds["slightly_acidic"]:
        return "Slightly Acidic"
    elif ph < thresholds["neutral"]:
        return "Neutral"
    elif ph < thresholds["alkaline"]:
        return "Slightly Alkaline"
    else:
        return "Alkaline"


def classify_organic_carbon(oc: float) -> str:
    """
    Classify organic carbon content
    
    Args:
        oc: Organic carbon percentage
        
    Returns:
        Organic carbon classification string
    """
    thresholds = SOIL_QUALITY_THRESHOLDS["organic_carbon"]
    
    if oc < thresholds["very_low"]:
        return "Very Low"
    elif oc < thresholds["low"]:
        return "Low"
    elif oc < thresholds["moderate"]:
        return "Moderate"
    elif oc < thresholds["high"]:
        return "High"
    else:
        return "Very High"


def classify_nitrogen_content(nitrogen: float) -> str:
    """
    Classify nitrogen content
    
    Args:
        nitrogen: Nitrogen percentage
        
    Returns:
        Nitrogen classification string
    """
    thresholds = SOIL_QUALITY_THRESHOLDS["nitrogen"]
    
    if nitrogen < thresholds["low"]:
        return "Low"
    elif nitrogen < thresholds["moderate"]:
        return "Moderate"
    elif nitrogen < thresholds["high"]:
        return "High"
    else:
        return "Very High"


def calculate_soil_health_score(soil_props) -> float:
    """
    Calculate overall soil health score (0-100)
    
    Args:
        soil_props: SoilProperties object
        
    Returns:
        Soil health score
    """
    score = 0
    
    # pH score (0-25 points)
    ph = soil_props.ph
    if 6.0 <= ph <= 7.5:
        ph_score = 25
    elif 5.5 <= ph <= 8.0:
        ph_score = 20
    elif 5.0 <= ph <= 8.5:
        ph_score = 15
    else:
        ph_score = 10
    
    # Organic carbon score (0-25 points)
    oc = soil_props.organic_carbon
    if oc >= 3.0:
        oc_score = 25
    elif oc >= 2.0:
        oc_score = 20
    elif oc >= 1.0:
        oc_score = 15
    elif oc >= 0.5:
        oc_score = 10
    else:
        oc_score = 5
    
    # CEC score (0-20 points)
    cec = soil_props.cation_exchange_capacity
    if cec >= 20:
        cec_score = 20
    elif cec >= 15:
        cec_score = 15
    elif cec >= 10:
        cec_score = 10
    else:
        cec_score = 5
    
    # Bulk density score (0-15 points)
    bd = soil_props.bulk_density
    if 1.0 <= bd <= 1.4:
        bd_score = 15
    elif 0.8 <= bd <= 1.6:
        bd_score = 12
    elif 0.6 <= bd <= 1.8:
        bd_score = 8
    else:
        bd_score = 5
    
    # Nutrient balance score (0-15 points)
    n_score = min(soil_props.nitrogen * 500, 5)  # Max 5 points
    p_score = min(soil_props.phosphorus / 10, 5)  # Max 5 points
    k_score = min(soil_props.potassium / 2, 5)   # Max 5 points
    nutrient_score = n_score + p_score + k_score
    
    total_score = ph_score + oc_score + cec_score + bd_score + nutrient_score
    return min(total_score, 100)


def format_report_header(location: LocationInfo) -> str:
    """
    Format the report header section
    
    Args:
        location: LocationInfo object
        
    Returns:
        Formatted header string
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    header = f"""
{REPORT_CONFIG['title']}
{REPORT_CONFIG['separator']}

📍 Location: Latitude {location.latitude}°, Longitude {location.longitude}°
🌡️  Climate Zone: {location.climate_zone}
📏 Analysis Depth: {location.depth}
📅 Report Generated: {timestamp}
{REPORT_CONFIG['separator']}
"""
    return header


def format_soil_properties_section(soil_props) -> str:
    """
    Format the soil properties section of the report
    
    Args:
        soil_props: SoilProperties object
        
    Returns:
        Formatted soil properties string
    """
    texture = soil_props.get_soil_texture()
    health_score = calculate_soil_health_score(soil_props)
    
    section = f"""
📊 DETAILED SOIL PROPERTIES:
{REPORT_CONFIG['section_separator']}
• Soil Texture: {texture}
• Soil Health Score: {health_score:.1f}/100
• pH Level: {soil_props.ph:.2f} ({classify_soil_ph(soil_props.ph)})
• Organic Carbon: {soil_props.organic_carbon:.2f}% ({classify_organic_carbon(soil_props.organic_carbon)})
• Total Nitrogen: {soil_props.nitrogen:.3f}% ({classify_nitrogen_content(soil_props.nitrogen)})
• Available Phosphorus: {soil_props.phosphorus:.1f} mg/kg
• Exchangeable Potassium: {soil_props.potassium:.1f} cmol/kg
• Clay Content: {soil_props.clay_content:.1f}%
• Sand Content: {soil_props.sand_content:.1f}%
• Silt Content: {soil_props.silt_content:.1f}%
• Bulk Density: {soil_props.bulk_density:.2f} kg/dm³
• Cation Exchange Capacity: {soil_props.cation_exchange_capacity:.1f} cmol/kg
"""
    return section


def save_report_to_file(report_content: str, location: LocationInfo) -> str:
    """
    Save report to file
    
    Args:
        report_content: Complete report content
        location: LocationInfo object
        
    Returns:
        Filename of saved report
    """
    # Create reports directory if it doesn't exist
    report_dir = REPORT_CONFIG["save_directory"]
    if not os.path.exists(report_dir):
        os.makedirs(report_dir)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"soil_report_{location.latitude}_{location.longitude}_{timestamp}{REPORT_CONFIG['file_extension']}"
    filepath = os.path.join(report_dir, filename)
    
    # Save file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    return filepath


def load_report_from_file(filepath: str) -> str:
    """
    Load report from file
    
    Args:
        filepath: Path to report file
        
    Returns:
        Report content
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def create_json_export(analysis_result) -> str:
    """
    Create JSON export of analysis results
    
    Args:
        analysis_result: SoilAnalysisResult object
        
    Returns:
        JSON string
    """
    export_data = {
        "analysis_timestamp": datetime.now().isoformat(),
        "location": analysis_result.location.to_dict(),
        "soil_properties": analysis_result.soil_properties.to_dict(),
        "soil_classification": analysis_result.soil_classification.to_dict(),
        "soil_texture": analysis_result.soil_texture,
        "soil_health_score": analysis_result.soil_health_score,
        "raw_soil_data": analysis_result.raw_data,
        "ai_recommendations_summary": analysis_result.ai_recommendations[:500] + "..." if len(analysis_result.ai_recommendations) > 500 else analysis_result.ai_recommendations
    }
    
    return json.dumps(export_data, indent=2)


def print_progress(message: str, step: int = None, total_steps: int = None) -> None:
    """
    Print progress message with optional step counter
    
    Args:
        message: Progress message
        step: Current step number
        total_steps: Total number of steps
    """
    if step and total_steps:
        print(f"[{step}/{total_steps}] {message}")
    else:
        print(f"⏳ {message}")


def handle_api_error(response: requests.Response, property_name: str = None) -> str:
    """
    Handle API error responses
    
    Args:
        response: Failed HTTP response
        property_name: Name of property being fetched
        
    Returns:
        Error message string
    """
    error_msg = f"API Error {response.status_code}"
    if property_name:
        error_msg += f" for {property_name}"
    
    try:
        error_data = response.json()
        if 'detail' in error_data:
            error_msg += f": {error_data['detail']}"
        elif 'message' in error_data:
            error_msg += f": {error_data['message']}"
    except:
        error_msg += f": {response.text[:100]}"
    
    return error_msg