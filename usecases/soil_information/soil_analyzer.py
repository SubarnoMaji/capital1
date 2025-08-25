"""
Main soil analyzer class that coordinates all components
"""

from typing import Optional, Tuple, List
from models import SoilProperties, LocationInfo, SoilAnalysisResult, SoilClassification
from soil_api import SoilGridsAPI
from ai_recommendations import CropRecommendationAI
from utils import (
    determine_climate_zone, 
    validate_coordinates, 
    calculate_soil_health_score,
    format_report_header,
    format_soil_properties_section,
    save_report_to_file,
    create_json_export,
    print_progress
)

# Fix: Add missing REPORT_CONFIG with default value to avoid NameError
REPORT_CONFIG = {
    'section_separator': '=' * 30
}

class SoilAnalyzer:
    """Main coordinator class for soil analysis and crop recommendations"""
    
    def __init__(self, openai_api_key: str):
        """
        Initialize SoilAnalyzer
        
        Args:
            openai_api_key: OpenAI API key for AI recommendations
        """
        self.soil_api = SoilGridsAPI()
        self.ai_recommender = CropRecommendationAI(openai_api_key)
        self._validate_apis()
    
    def _validate_apis(self) -> None:
        """Validate that all APIs are accessible"""
        print_progress("Validating API access...")
        
        # Check SoilGrids API
        if not self.soil_api.check_api_status():
            print("⚠️  Warning: SoilGrids API may not be accessible")
        
        # Check OpenAI API
        if not self.ai_recommender.validate_api_key():
            print("❌ Error: Invalid OpenAI API key")
            raise ValueError("Invalid OpenAI API key provided")
        
        print("✅ API validation completed")
    
    def analyze_location(self, latitude: float, longitude: float, depth: str = "0-30cm") -> SoilAnalysisResult:
        """
        Perform complete soil analysis for a location
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            depth: Soil depth for analysis
            
        Returns:
            SoilAnalysisResult object
        """
        # Validate coordinates
        is_valid, error_msg = validate_coordinates(latitude, longitude)
        if not is_valid:
            raise ValueError(error_msg)
        
        print(f"🌱 Starting soil analysis for coordinates: {latitude}, {longitude}")
        print(f"📏 Analysis depth: {depth}")
        print("=" * 60)
        
        # Create location info
        climate_zone = determine_climate_zone(latitude)
        location = LocationInfo(
            latitude=latitude,
            longitude=longitude,
            climate_zone=climate_zone,
            depth=depth
        )
        
        # Fetch soil data
        print_progress("Step 1: Fetching soil data from SoilGrids...")
        soil_properties, raw_data, classification_data = self.soil_api.get_soil_analysis(location)
        
        # Create classification object
        soil_classification = SoilClassification(
            class_name=classification_data['class_name'],
            class_value=classification_data['class_value'],
            probabilities=classification_data['probabilities'],
            coordinates=classification_data['coordinates'],
            query_time=classification_data['query_time']
        )
        
        # Calculate derived properties
        soil_texture = soil_properties.get_soil_texture()
        soil_health_score = calculate_soil_health_score(soil_properties)
        
        print(f"✅ Soil texture identified: {soil_texture}")
        print(f"✅ Soil classification: {soil_classification.class_name}")
        print(f"✅ Soil health score: {soil_health_score:.1f}/100")
        
        # Generate AI recommendations
        print_progress("Step 2: Generating AI-powered recommendations...")
        ai_recommendations = self.ai_recommender.get_crop_recommendations(soil_properties, location)
        
        # Create analysis result
        analysis_result = SoilAnalysisResult(
            location=location,
            soil_properties=soil_properties,
            soil_classification=soil_classification,
            raw_data=raw_data,
            ai_recommendations=ai_recommendations,
            soil_texture=soil_texture,
            soil_health_score=soil_health_score
        )
        
        print("✅ Soil analysis completed successfully!")
        return analysis_result
    
    def generate_report(self, analysis_result: SoilAnalysisResult) -> str:
        """
        Generate comprehensive text report
        
        Args:
            analysis_result: SoilAnalysisResult object
            
        Returns:
            Formatted report string
        """
        header = format_report_header(analysis_result.location)
        soil_section = format_soil_properties_section(analysis_result.soil_properties)
        
        # Format classification section
        classification_section = f"""
🏷️  SOIL CLASSIFICATION:
{REPORT_CONFIG.get('section_separator', '=' * 30)}
• WRB Classification: {analysis_result.soil_classification.class_name}
• Classification Confidence: {analysis_result.soil_classification.class_value}%
• Top Alternative Classifications:"""
        
        top_probs = analysis_result.soil_classification.get_top_probabilities(3)
        for class_name, probability in top_probs:
            classification_section += f"\n  - {class_name}: {probability}%"
        
        report = f"""{header}
{soil_section}
{classification_section}

🤖 AI-POWERED RECOMMENDATIONS:
==============================
{analysis_result.ai_recommendations}

📈 SOIL ANALYSIS SUMMARY:
========================
• Soil Texture Classification: {analysis_result.soil_texture}
• WRB Soil Classification: {analysis_result.soil_classification.class_name}
• Overall Soil Health Score: {analysis_result.soil_health_score:.1f}/100
• Climate Zone: {analysis_result.location.climate_zone}
• Analysis Depth: {analysis_result.location.depth}
"""
        return report
    
    
    def get_quick_analysis(self, latitude: float, longitude: float, depth: str = "0-5cm") -> str:
        """
        Get quick analysis summary (faster, less detailed)
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate  
            depth: Soil depth for analysis

            
        Returns:
            Quick analysis summary string
        """
        # Validate coordinates
        is_valid, error_msg = validate_coordinates(latitude, longitude)
        if not is_valid:
            return f"❌ Error: {error_msg}"
        
        try:
            # Create location info
            climate_zone = determine_climate_zone(latitude)
            location = LocationInfo(latitude, longitude, climate_zone, depth)
            
            # Get basic soil data (fewer properties for speed)
            print_progress("Fetching key soil properties...")
            key_properties = ["phh2o", "soc", "clay", "sand", "nitrogen"]
            
            raw_data = {}
            for prop in key_properties:
                value = self.soil_api.fetch_property(prop, latitude, longitude, depth)
                raw_data[prop] = value
            
            # Parse basic soil properties
            soil_properties = self.soil_api.parse_soil_data(raw_data)
            
            # Get quick AI recommendations
            quick_recommendations = self.ai_recommender.get_quick_recommendations(soil_properties, location)
            
            # Fix: Handle missing attributes gracefully
            ph = getattr(soil_properties, 'ph', None)
            organic_carbon = getattr(soil_properties, 'organic_carbon', None)
            clay_content = getattr(soil_properties, 'clay_content', None)
            soil_texture = soil_properties.get_soil_texture() if hasattr(soil_properties, 'get_soil_texture') else "N/A"
            
            ph_str = f"{ph:.2f}" if ph is not None else "N/A"
            organic_carbon_str = f"{organic_carbon:.2f}%" if organic_carbon is not None else "N/A"
            clay_content_str = f"{clay_content:.1f}%" if clay_content is not None else "N/A"
            
            return f"""
🌱 QUICK SOIL ANALYSIS SUMMARY
==============================
📍 Location: {latitude}°, {longitude}° ({climate_zone})
📏 Depth: {depth}

📊 Key Soil Properties:
• Soil Texture: {soil_texture}
• pH: {ph_str}
• Organic Carbon: {organic_carbon_str}
• Clay Content: {clay_content_str}

🤖 Quick Recommendations:
{quick_recommendations}

💡 For detailed analysis, use the full analysis mode.
"""
        
        except Exception as e:
            return f"❌ Error in quick analysis: {str(e)}"
    
    def get_fertilizer_advice(self, latitude: float, longitude: float, depth: str = "0-30cm") -> str:
        """
        Get specific fertilizer recommendations
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            depth: Soil depth for analysis
            
        Returns:
            Fertilizer recommendation string
        """
        try:
            # Get basic analysis
            climate_zone = determine_climate_zone(latitude)
            location = LocationInfo(latitude, longitude, climate_zone, depth)
            
            # Get soil properties
            soil_properties, _ = self.soil_api.get_soil_analysis(location)
            
            # Get fertilizer recommendations
            fertilizer_advice = self.ai_recommender.get_fertilizer_recommendations(soil_properties)
            
            # Fix: Handle missing attributes gracefully
            ph = getattr(soil_properties, 'ph', None)
            organic_carbon = getattr(soil_properties, 'organic_carbon', None)
            nitrogen = getattr(soil_properties, 'nitrogen', None)
            phosphorus = getattr(soil_properties, 'phosphorus', None)
            potassium = getattr(soil_properties, 'potassium', None)
            
            ph_str = f"{ph:.2f}" if ph is not None else "N/A"
            organic_carbon_str = f"{organic_carbon:.2f}%" if organic_carbon is not None else "N/A"
            nitrogen_str = f"{nitrogen:.3f}%" if nitrogen is not None else "N/A"
            phosphorus_str = f"{phosphorus:.1f} mg/kg" if phosphorus is not None else "N/A"
            potassium_str = f"{potassium:.1f} cmol/kg" if potassium is not None else "N/A"
            
            return f"""
💼 FERTILIZER RECOMMENDATIONS
=============================
📍 Location: {latitude}°, {longitude}°
📏 Analysis Depth: {depth}

📊 Soil Nutrient Status:
• pH: {ph_str}
• Organic Carbon: {organic_carbon_str}
• Nitrogen: {nitrogen_str}
• Phosphorus: {phosphorus_str}
• Potassium: {potassium_str}

🧪 Fertilizer Recommendations:
{fertilizer_advice}
"""
        
        except Exception as e:
            return f"❌ Error generating fertilizer advice: {str(e)}"
    
    def compare_locations(self, locations: list) -> str:
        """
        Compare soil properties across multiple locations
        
        Args:
            locations: List of (lat, lon, depth) tuples
            
        Returns:
            Comparison report string
        """
        if len(locations) < 2:
            return "❌ Need at least 2 locations for comparison"
        
        comparison_data = []
        
        for i, (lat, lon, depth) in enumerate(locations, 1):
            print_progress(f"Analyzing location {i}/{len(locations)}: {lat}, {lon}")
            
            try:
                climate_zone = determine_climate_zone(lat)
                location = LocationInfo(lat, lon, climate_zone, depth)
                soil_properties, _ = self.soil_api.get_soil_analysis(location)
                health_score = calculate_soil_health_score(soil_properties)
                
                # Fix: Handle missing attributes gracefully
                ph = getattr(soil_properties, 'ph', None)
                organic_carbon = getattr(soil_properties, 'organic_carbon', None)
                soil_texture = soil_properties.get_soil_texture() if hasattr(soil_properties, 'get_soil_texture') else "N/A"
                ph_str = f"{ph:.2f}" if ph is not None else "N/A"
                organic_carbon_str = f"{organic_carbon:.2f}%" if organic_carbon is not None else "N/A"
                
                comparison_data.append({
                    'location': f"{lat}, {lon}",
                    'climate': climate_zone,
                    'texture': soil_texture,
                    'ph': ph_str,
                    'organic_carbon': organic_carbon_str,
                    'health_score': health_score
                })
                
            except Exception as e:
                comparison_data.append({
                    'location': f"{lat}, {lon}",
                    'error': str(e)
                })
        
        # Generate comparison report
        report = "\n🔄 SOIL COMPARISON REPORT\n" + "=" * 40 + "\n"
        
        for i, data in enumerate(comparison_data, 1):
            if 'error' in data:
                report += f"\n{i}. {data['location']} - Error: {data['error']}\n"
            else:
                report += f"""
{i}. Location: {data['location']}
   Climate: {data['climate']}
   Soil Texture: {data['texture']}
   pH: {data['ph']}
   Organic Carbon: {data['organic_carbon']}
   Health Score: {data['health_score']:.1f}/100
"""
        
        # Add summary rankings
        valid_data = [d for d in comparison_data if 'error' not in d]
        if len(valid_data) > 1:
            # Rank by health score
            ranked = sorted(valid_data, key=lambda x: x['health_score'], reverse=True)
            
            report += "\n🏆 RANKING BY SOIL HEALTH:\n" + "-" * 30 + "\n"
            for i, data in enumerate(ranked, 1):
                report += f"{i}. {data['location']} - Score: {data['health_score']:.1f}/100\n"
        
        return report
    
    def close(self):
        """Clean up resources"""
        if hasattr(self.soil_api, 'close'):
            self.soil_api.close()