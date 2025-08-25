"""
Data models for the Soil Analysis Tool
"""

from dataclasses import dataclass, asdict
from typing import Dict, Optional, Any, List, Tuple
import json


@dataclass
class SoilProperties:
    """Data class to store processed soil properties"""
    ph: float
    organic_carbon: float
    nitrogen: float
    phosphorus: float
    potassium: float
    clay_content: float
    sand_content: float
    silt_content: float
    bulk_density: float
    cation_exchange_capacity: float
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    def get_soil_texture(self) -> str:
        """Determine soil texture based on sand, silt, clay percentages"""
        clay = self.clay_content
        sand = self.sand_content
        silt = self.silt_content
        
        if clay >= 40:
            return "Clay"
        elif clay >= 27:
            if sand >= 20:
                return "Clay Loam"
            else:
                return "Silty Clay"
        elif clay >= 20:
            if sand >= 45:
                return "Sandy Clay Loam"
            elif silt >= 28:
                return "Silty Clay Loam"
            else:
                return "Clay Loam"
        elif clay >= 7:
            if sand >= 52:
                return "Sandy Loam"
            elif silt >= 50:
                return "Silt Loam"
            else:
                return "Loam"
        else:
            if sand >= 85:
                return "Sand"
            elif sand >= 70:
                return "Loamy Sand"
            elif silt >= 80:
                return "Silt"
            else:
                return "Sandy Loam"


@dataclass
class LocationInfo:
    """Data class to store location information"""
    latitude: float
    longitude: float
    climate_zone: str
    depth: str = "0-30cm"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class SoilClassification:
    """Data class for soil classification information"""
    class_name: str
    class_value: int
    probabilities: list
    coordinates: list
    query_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    def get_top_probabilities(self, n: int = 3) -> List[Tuple[str, int]]:
        """Get top N soil class probabilities"""
        return self.probabilities[:n] if self.probabilities else []


@dataclass
class SoilAnalysisResult:
    """Complete soil analysis result"""
    location: LocationInfo
    soil_properties: SoilProperties
    soil_classification: SoilClassification
    raw_data: Dict[str, Any]
    ai_recommendations: str
    soil_texture: str
    soil_health_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "location": self.location.to_dict(),
            "soil_properties": self.soil_properties.to_dict(),
            "soil_classification": self.soil_classification.to_dict(),
            "raw_data": self.raw_data,
            "ai_recommendations": self.ai_recommendations,
            "soil_texture": self.soil_texture,
            "soil_health_score": self.soil_health_score
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class CropRecommendation:
    """Individual crop recommendation"""
    name: str
    suitability_score: float
    season: str
    notes: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class FarmingAdvice:
    """Farming advice and recommendations"""
    irrigation_method: str
    fertilization_schedule: str
    soil_improvements: list
    potential_challenges: list
    seasonal_recommendations: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)