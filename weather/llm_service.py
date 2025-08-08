from typing import Dict, List
import logging
from openai import AsyncOpenAI
import os
from datetime import datetime, time

class LLMService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.logger = logging.getLogger(__name__)

    async def analyze_weather_data(self, weather_data: Dict, analysis_type: str = "general") -> Dict:
        try:
            # Prepare the prompt based on analysis type
            prompt = self._create_analysis_prompt(weather_data, analysis_type)
            
            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self._get_system_prompt(analysis_type)},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            return self._parse_llm_response(response.choices[0].message.content, analysis_type)

        except Exception as e:
            self.logger.error(f"Error getting LLM analysis: {str(e)}")
            raise

    def _get_system_prompt(self, analysis_type: str) -> str:
        prompts = {
            "general": "You are a weather analysis expert. Provide clear insights about the weather conditions.",
            "agricultural": "You are an agricultural expert. Analyze weather conditions and their impact on farming activities.",
            "detailed": "You are a meteorological scientist. Provide detailed technical analysis of weather patterns.",
            "policy maker": "You are advising a government policymaker focused on agriculture. Analyze weather trends and provide actionable insights to guide agricultural policy, food security planning, and climate-resilient farming strategies."
        }
        return prompts.get(analysis_type, prompts["general"])

    def _create_analysis_prompt(self, weather_data: Dict, analysis_type: str) -> str:
        current_conditions = f"""
        Current Weather Conditions:
        Temperature: {weather_data.get('temperature', 'N/A')}°C
        Humidity: {weather_data.get('humidity', 'N/A')}%
        Precipitation: {weather_data.get('precipitation', 'N/A')}mm
        Timestamp: {weather_data.get('timestamp', 'N/A')}
        """

        forecast_data = ""
        if weather_data.get('forecast'):
            forecast_data = "\nForecast Data:\n"
            for entry in weather_data['forecast'][:8]:  # Next 8 time periods
                forecast_data += f"Time: {entry['timestamp']}, Temp: {entry['temperature']}°C, "
                forecast_data += f"Humidity: {entry['humidity']}%, Precipitation: {entry['precipitation']}mm\n"

        analysis_requests = {
            "general": "Provide a general analysis of these weather conditions.",
            "agricultural": """
                Analyze these weather conditions from an agricultural perspective:
                1. Suitable crops for these conditions
                2. Farming activities recommended
                3. Potential risks or concerns
                4. Irrigation recommendations
            """,
            "detailed": """
                Provide a detailed meteorological analysis including:
                1. Weather pattern analysis
                2. Potential weather changes
                3. Technical meteorological insights
                4. Recommendations for outdoor activities
            """
        }

        return f"{current_conditions}\n{forecast_data}\n{analysis_requests.get(analysis_type, analysis_requests['general'])}"

    def _parse_llm_response(self, response: str, analysis_type: str) -> Dict:
        return {
            "analysis_type": analysis_type,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "content": response,
            "summary": self._extract_summary(response)
        }

    def _extract_summary(self, response: str) -> Dict:
        # Extract key points from the response
        lines = response.split('\n')
        summary = {
            "key_points": [],
            "recommendations": []
        }
        
        for line in lines:
            if line.strip().startswith(('-', '•', '1.', '2.', '3.', '4.')):
                if 'recommend' in line.lower():
                    summary["recommendations"].append(line.strip())
                else:
                    summary["key_points"].append(line.strip())
        
        return summary