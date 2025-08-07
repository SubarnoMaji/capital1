import httpx
from typing import Dict
import logging

class LocationService:
    def __init__(self):
        self.base_url = "https://nominatim.openstreetmap.org"
        self.logger = logging.getLogger(__name__)

    async def get_coordinates(self, location_name: str) -> Dict[str, float]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/search",
                    params={
                        "q": location_name,
                        "format": "json",
                        "limit": 1
                    },
                    headers={
                        "User-Agent": "CropRecommendationSystem/1.0"
                    }
                )
                response.raise_for_status()
                data = response.json()

                if not data:
                    raise ValueError(f"Location not found: {location_name}")

                return {
                    "latitude": float(data[0]["lat"]),
                    "longitude": float(data[0]["lon"])
                }

        except Exception as e:
            self.logger.error(f"Error getting coordinates for {location_name}: {str(e)}")
            raise