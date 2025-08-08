from typing import Type, Dict, Any, Optional
from pydantic import BaseModel, Field
import json
import asyncio
import datetime
from langchain.tools import BaseTool
import os
import requests
import sys

# Add the parent directory (project root) to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import Config as config

class SuggestionDataLoggerInput(BaseModel):
    action: str = Field(..., description="Action to perform (store, retrieve, update, delete, get_history)")
    key: str = Field(..., description="Key to identify the suggestions")
    data: Optional[Dict[str, Any]] = Field(None, description="Data to store or update")
    suggestion_id: Optional[str] = Field(None, description="Unique identifier for a specific suggestion when updating")

class SuggestionDataLoggerTool(BaseTool):
    name: str = "SuggestionDataLoggerTool"
    description: str = "Log and manage user suggestions, storing, retrieving, updating, and deleting entries."
    args_schema: Type[SuggestionDataLoggerInput] = SuggestionDataLoggerInput
    db_url: str = config.DB_URL

    def update_history(self, action: str, history: list, data: Optional[Dict[str, Any]] = None) -> list:
        """Update history with a new entry"""
        timestamp = datetime.datetime.now().isoformat()
        history_entry = {
            "timestamp": timestamp,
            "action": action,
            "data_summary": str(data)[:100] + "..." if data and len(str(data)) > 100 else str(data)
        }
        history.append(history_entry)
        return history

    async def _arun(self, action: str, key: str, data: Optional[Dict[str, Any]] = None, suggestion_id: Optional[str] = None) -> str:
        timestamp = datetime.datetime.now().isoformat()
        try:
            if action == "store":
                if data:
                    if isinstance(data, dict):
                        data["timestamp"] = timestamp
                
                # Retrieve the existing suggestions
                response = requests.get(
                    self.db_url,
                    params={
                        "collection_name": "curated_suggestions",
                        "_id": key
                    }
                )

                if response.status_code == 200:
                    suggestions = json.loads(json.dumps(response.json().get('data', {}), indent=2))["suggestions"]
                    history = json.loads(json.dumps(response.json().get('data', {}), indent=2))["history"]
                else:
                    suggestions = []
                    history = []
                
                suggestions.append(data)
                history = self.update_history(action, history, data)

                response = requests.post(
                    self.db_url,
                    params={
                        "collection_name": "curated_suggestions",
                        "_id": key
                    },
                    json={
                        "suggestions": suggestions,
                        "history": history,
                    }
                )
                if response.status_code == 200:
                    return f"Suggestion stored for key: {key}"
                else:
                    return f"Error storing suggestion: {response.text}"

            elif action == "retrieve":
                response = requests.get(
                    self.db_url,
                    params={    
                        "collection_name": "curated_suggestions",
                        "_id": key
                    }
                )
                if response.status_code == 200:
                    suggestions = json.loads(json.dumps(response.json().get('data', {}), indent=2))["suggestions"]
                    history = json.loads(json.dumps(response.json().get('data', {}), indent=2))["history"]
                    history = self.update_history(action, history)
                    
                    # Update history in the database
                    requests.post(
                        self.db_url,
                        params={
                            "collection_name": "curated_suggestions",
                            "_id": key
                        },
                        json={
                            "suggestions": suggestions,
                            "history": history,
                        }
                    )
                    return json.dumps(suggestions, indent=2)
                else:
                    return "[]"

            elif action == "update":
                if not data or not suggestion_id:
                    return "Error: Data and suggestion_id required for update"

                # Update each field sequentially
                for field_key, value in data.items():
                    response = requests.put(
                        self.db_url,
                        params={
                            "collection_name": "curated_suggestions",
                            "_id": key,
                            "key": field_key,
                            "suggestion_id": suggestion_id
                        },
                        json=value
                    )
                    if response.status_code != 200:
                        return f"Error updating {field_key}: {response.text}"
                
                # Update history
                response = requests.get(
                    self.db_url,
                    params={
                        "collection_name": "curated_suggestions",
                        "_id": key
                    }
                )
                if response.status_code == 200:
                    suggestions = json.loads(json.dumps(response.json().get('data', {}), indent=2))["suggestions"]
                    # Find the specific suggestion to update
                    suggestion_to_update = next((s for s in suggestions if s.get("suggestion-id") == suggestion_id), None)
                    if suggestion_to_update:
                        suggestion_to_update["updated_at"] = timestamp
                    history = json.loads(json.dumps(response.json().get('data', {}), indent=2))["history"]
                    history = self.update_history(action, history, data)
                    
                    # Update history in the database
                    requests.post(
                        self.db_url,
                        params={
                            "collection_name": "curated_suggestions",
                            "_id": key
                        },
                        json={
                            "suggestions": suggestions,
                            "history": history
                        }
                    )
                
                return f"Fields updated for suggestion ID: {suggestion_id}"

            elif action == "delete":
                response = requests.post(
                    self.db_url,
                    params={
                        "collection_name": "curated_suggestions",
                        "_id": key
                    },
                    json={
                        "suggestions":[]
                    }
                )
                if response.status_code == 200:
                    # Update history
                    response = requests.get(
                        self.db_url,
                        params={
                            "collection_name": "curated_suggestions",
                            "_id": key
                        }
                    )
                    if response.status_code == 200:
                        history = json.loads(json.dumps(response.json().get('data', {}), indent=2))["history"]
                        history = self.update_history(action, history)
                        
                        # Update history in the database
                        requests.post(
                            self.db_url,
                            params={
                                "collection_name": "curated_suggestions",
                                "_id": key
                            },
                            json={
                                "history": history
                            }
                        )
                    return f"Suggestions deleted for key: {key}"
                else:
                    return f"Error deleting suggestions: {response.text}"

            else:
                return f"Error: Unknown action '{action}'. Supported actions are: store, retrieve, update, delete."

        except Exception as e:
            return f"Error processing request: {str(e)}"

    def _run(self, action: str, key: str, data: Optional[Dict[str, Any]] = None, suggestion_id: Optional[str] = None) -> str:
        return asyncio.run(self._arun(action=action, key=key, data=data, suggestion_id=suggestion_id))
    
if __name__ == "__main__":
    # Example usage
    logger_tool = SuggestionDataLoggerTool()

    # Store a suggestion
    suggestion_data = {
        "status": "approved"
    }
    
    # Retrieve suggestions
    response = logger_tool._run(
        action="update",
        key="73b3210b318384f96203697c",
        data=suggestion_data,
        suggestion_id="a1b2c3d4e5"
    )
    print(response)