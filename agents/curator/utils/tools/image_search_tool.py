from typing import Type
from pydantic import BaseModel, Field
import requests
from langchain.tools import BaseTool
import asyncio
import os
import sys

# Ensure the parent directory is in the path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import Config as config

class GoogleImageSearchInput(BaseModel):
    query: str = Field(..., description="Search query")
    k: int = Field(5, description="Number of image search results to return (default: 5)")

class GoogleImageSearchTool(BaseTool):
    name: str = "google_image_search"
    description: str = "Search Google Images using custom search engine by providing a query and number of results."
    args_schema: Type[GoogleImageSearchInput] = GoogleImageSearchInput

    async def _arun(self, **kwargs) -> list:
        try:
            search_results = []
            response = requests.get(
                f"https://www.googleapis.com/customsearch/v1?q={kwargs['query']}&key={config.GOOGLE_API_KEY}&cx={config.GOOGLE_CSE_ID}&num={kwargs['k']}&searchType=image&gl=in&safe=off"
            )
            response_json = response.json()
            for item in response_json.get("items", []):
                search_results.append({
                    "Title": item.get("title", "No title"),
                    "Image Link": item.get("link", ""),
                    "Thumbnail": item.get("image", {}).get("thumbnailLink", "")
                })
            return search_results
        except Exception as e:
            return f"Error: {str(e)}"

    def _run(self, *args, **kwargs):
        raise NotImplementedError("Sync version not implemented.")
    
if __name__ == "__main__":
    async def main():
        tool = GoogleImageSearchTool()
        result = await tool._arun(query="Cute cats", k=3)
        print(result)

    asyncio.run(main())