"""
AI-powered crop recommendations using OpenAI GPT
"""

import openai
from typing import Optional
from models import SoilProperties, LocationInfo
from config import OPENAI_MODEL, OPENAI_MAX_TOKENS, OPENAI_TEMPERATURE
from utils import print_progress, classify_soil_ph, classify_organic_carbon


class CropRecommendationAI:
    """AI-powered crop recommendation system"""
    
    def __init__(self, api_key: str):
        """
        Initialize with OpenAI API key
        
        Args:
            api_key: OpenAI API key
        """
        self.client = openai.OpenAI(api_key=api_key)
        self.model = OPENAI_MODEL
        self.max_tokens = OPENAI_MAX_TOKENS
        self.temperature = OPENAI_TEMPERATURE
    
    def generate_soil_analysis_prompt(self, soil_props: SoilProperties, location: LocationInfo) -> str:
        """
        Generate comprehensive prompt for soil analysis
        
        Args:
            soil_props: SoilProperties object
            location: LocationInfo object
            
        Returns:
            Formatted prompt string
        """
        soil_texture = soil_props.get_soil_texture()
        
        soil_analysis = f"""
        Location: Latitude {location.latitude}°, Longitude {location.longitude}° ({location.climate_zone} climate)
        Analysis Depth: {location.depth}
        
        Soil Properties Analysis:
        - Soil Texture: {soil_texture}
        - pH Level: {soil_props.ph:.2f} ({classify_soil_ph(soil_props.ph)})
        - Organic Carbon: {soil_props.organic_carbon:.2f}% ({classify_organic_carbon(soil_props.organic_carbon)})
        - Total Nitrogen: {soil_props.nitrogen:.3f}%
        - Available Phosphorus: {soil_props.phosphorus:.1f} mg/kg
        - Exchangeable Potassium: {soil_props.potassium:.1f} cmol/kg
        - Clay Content: {soil_props.clay_content:.1f}%
        - Sand Content: {soil_props.sand_content:.1f}%
        - Silt Content: {soil_props.silt_content:.1f}%
        - Bulk Density: {soil_props.bulk_density:.2f} kg/dm³
        - Cation Exchange Capacity: {soil_props.cation_exchange_capacity:.1f} cmol/kg
        """
        
        prompt = f"""
                You are an agricultural advisor. Read the soil report below and give clear, simple advice that any farmer can easily follow:

                {soil_analysis}

                Write your answer in these sections:

                ## 1. SOIL HEALTH
                - Rate the soil as Poor / Fair / Good / Excellent and explain simply
                - Main strengths and weaknesses
                - How well it holds water and drains
                - Is it rich or poor in nutrients

                ## 2. BEST 5 CROPS
                - List top 5 crops suited for this soil and climate: {location.climate_zone}
                - Say why each crop is a good choice
                - Include food and cash crops

                ## 3. HOW TO IMPROVE SOIL
                - Ways to add fertility (compost, cow dung, crop waste)
                - How to make soil less sour or less salty if needed
                - Simple fertilizer advice (what to add and when)
                - Ways to make soil soft and loose
                - How to stop soil erosion

                ## 4. FARMING PRACTICES
                - Best way to give water (irrigation)
                - Best way to plough (normal, less, or no ploughing)
                - Good 3–4 year crop rotation plan
                - Simple fertilizer schedule (season-wise)
                - Common soil pests and how to prevent them

                ## 5. PROBLEMS & SOLUTIONS
                - Likely soil problems (too much water, hard soil, less nutrients)
                - Easy preventive steps
                - Risks from local climate and how to handle them

                ## 6. SEASONAL ADVICE
                - **Spring**: Land prep and early crops
                - **Summer**: Main crops and water care
                - **Rainy season**: Drainage and crop safety
                - **Winter**: Cool season crops and soil care

                ## 7. LONG-TERM PLAN
                - Steps to improve soil for 5–10 years
                - Simple, low-cost ways to keep soil healthy
                - What to check regularly to track soil health

                Keep the language very simple and practical. Give advice in short points that farmers can follow directly.
                """


        
        return prompt
    
    def get_crop_recommendations(self, soil_props: SoilProperties, location: LocationInfo) -> str:
        """
        Get AI-powered crop recommendations
        
        Args:
            soil_props: SoilProperties object
            location: LocationInfo object
            
        Returns:
            AI-generated recommendations string
        """
        print_progress("Generating AI-powered recommendations...")
        
        try:
            prompt = self.generate_soil_analysis_prompt(soil_props, location)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": """You are an expert agricultural consultant and soil scientist with 20+ years of experience. 
                        You have extensive knowledge of:
                        - Soil chemistry and physics
                        - Crop nutrition and physiology  
                        - Sustainable farming practices
                        - Climate-appropriate agriculture
                        - Integrated pest management
                        - Soil conservation techniques
                        
                        Provide practical, science-based advice that farmers can implement. 
                        Consider economic viability and local resource availability in your recommendations."""
                    },
                    {"role": "user", "content": prompt}
                ],
            )
            
            recommendations = response.choices[0].message.content
            print("✅ AI recommendations generated successfully")
            
            return recommendations
            
        except openai.RateLimitError:
            return "⚠️ OpenAI API rate limit exceeded. Please try again later or check your API quota."
            
        except openai.AuthenticationError:
            return "❌ OpenAI API authentication failed. Please check your API key."
            
        except openai.APIError as e:
            return f"❌ OpenAI API error: {str(e)}"
            
        except Exception as e:
            return f"❌ Error generating AI recommendations: {str(e)}"
    
    def get_quick_recommendations(self, soil_props: SoilProperties, location: LocationInfo) -> str:
        """
        Get quick, concise crop recommendations (shorter response)
        
        Args:
            soil_props: SoilProperties object
            location: LocationInfo object
            
        Returns:
            Concise recommendations string
        """
        soil_texture = soil_props.get_soil_texture()
        
        quick_prompt = f"""
        Provide quick farming advice for:
        - Location: {location.latitude}°, {location.longitude}° ({location.climate_zone})
        - Soil: {soil_texture}, pH {soil_props.ph:.1f}, {soil_props.organic_carbon:.1f}% organic carbon
        
        Give me:
        1. Top 3 recommended crops
        2. Main soil limitation
        3. Key improvement needed
        4. Best fertilizer recommendation
        
        Keep response under 200 words, bullet points preferred.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a concise agricultural advisor. Provide brief, actionable advice."},
                    {"role": "user", "content": quick_prompt}
                ],
                max_tokens=300,
                temperature=0.5
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Error generating quick recommendations: {str(e)}"
    
    def validate_api_key(self) -> bool:
        """
        Validate OpenAI API key
        
        Returns:
            True if API key is valid, False otherwise
        """
        try:
            # Make a simple test request
            response = self.client.chat.completions.create(
                model="gpt-5-mini",
                messages=[{"role": "user", "content": "test"}],
            )
            return True
            
        except openai.AuthenticationError:
            return False
            
        except Exception:
            # Other errors might not be authentication-related
            return True
    
    def get_fertilizer_recommendations(self, soil_props: SoilProperties) -> str:
        """
        Get specific fertilizer recommendations based on soil analysis
        
        Args:
            soil_props: SoilProperties object
            
        Returns:
            Fertilizer recommendations string
        """
        prompt = f"""
        Based on this soil analysis, provide specific fertilizer recommendations:
        
        - pH: {soil_props.ph:.2f}
        - Organic Carbon: {soil_props.organic_carbon:.2f}%
        - Nitrogen: {soil_props.nitrogen:.3f}%
        - Phosphorus: {soil_props.phosphorus:.1f} mg/kg
        - Potassium: {soil_props.potassium:.1f} cmol/kg
        - CEC: {soil_props.cation_exchange_capacity:.1f} cmol/kg
        
        Provide:
        1. NPK ratio recommendation
        2. Application rates (kg/hectare)
        3. Application timing
        4. Organic vs synthetic fertilizer suggestions
        5. Micronutrient needs
        
        Keep response focused and practical.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a soil fertility expert. Provide specific, practical fertilizer recommendations."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Error generating fertilizer recommendations: {str(e)}"