from typing import Type
from pydantic import BaseModel, Field
import requests
from langchain.tools import BaseTool
import asyncio
import os
import sys
from utils.safe_url_fetcher import fetch_url_safe

# Ensure the parent directory is in the path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import Config as config

class GoogleSearchInput(BaseModel):
    query: str = Field(..., description="Search query")
    k: int = Field(5, description="Number of search results to return (default: 5)")

class GoogleSearchTool(BaseTool):
    name: str = "GoogleSearchTool"
    description: str = "Search Google using custom search engine by providing a query and number of search results."
    args_schema: Type[GoogleSearchInput] = GoogleSearchInput

    async def _arun(self, **kwargs) -> str:
        # print("Executing Google Search Tool")
        try:
            if not kwargs['k']:
                print("Tool call did not specify number of results. Setting default to 3")
                kwargs['k'] = 3

            # Perform Google search using the custom search engine
            query = f"{kwargs['query']} -tripadvisor -makemytrip -booking.com"
            response = requests.get(f"https://www.googleapis.com/customsearch/v1?q={query}&key={config.GOOGLE_API_KEY}&cx={config.GOOGLE_CSE_ID}&num={kwargs['k']}")
            response_json = response.json()

            fetch_tasks = []
            for item in response_json['items']:
                if 'snippet' in item:
                    print(f"{item['title']} ----- {item['link']}")
                    # Store item info and create fetch task
                    task = {
                        "title": item['title'],
                        "link": item['link'],
                        "snippet": item['snippet'],
                        "fetch_task": asyncio.create_task(asyncio.to_thread(fetch_url_safe, item['link']))
                    }
                    fetch_tasks.append(task)

            print("Fetching Content")
            raw_fetched_results = await asyncio.gather(*[task["fetch_task"] for task in fetch_tasks])
            print(raw_fetched_results)
            fetched_results = []
            for task, result in zip(fetch_tasks, raw_fetched_results):
                if result["error"] !="":
                    print(f"{task['title']} ----- {task['link']} ----- {result['error']}")
                fetched_results.append({
                    "Title": task["title"],
                    "Link": task["link"],
                    "Snippet": task["snippet"],
                    "Success": result["success"],
                    "Error": result["error"],
                    "Content": result["content"] if (result["error"] == "") else task["snippet"]
                })

            return fetched_results

        except Exception as e:
            error_msg = str(e)
            return [{
                "Title": "Search Error",
                "Link": "",
                "Snippet": f"Error during search: {error_msg}",
                "Success": False,
                "Error": error_msg,
                "Content": f"Error during search: {error_msg}"
            }]

    def _run(self, **kwargs):
        raise NotImplementedError("Sync version not implemented.")