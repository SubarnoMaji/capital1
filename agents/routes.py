from fastapi import FastAPI, HTTPException, Body, Depends, APIRouter
from typing import Optional, Any
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv, find_dotenv
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
import os
from typing import Dict, List, Optional, Any
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.config import Config as config
from curator.services.curator_service import CuratorNode
from curator.utils.tools.search_tool import WebSearchTool
from curator.utils.tools.message_logger import MessageHistoryLoggerTool
from agents.curator.utils.tools.user_inputs import UserDataLoggerTool
from agents.curator.utils.tools.retrieval_tool import RetrievalTool
from agents.curator.utils.tools.price_fetcher import PriceFetcherTool
from agents.curator.utils.tools.weather_tool import WeatherAnalysisTool
# from agents.curator.utils.tools.pest_detection import PestDetectionTool

router = APIRouter(prefix="/api/agent")

# Define request and response models
class CuratorRequest(BaseModel):
    query: str = Field(..., description="User query for agricultural advice")
    conversation_id: str = Field(..., description="Unique identifier for the conversation")
    inputs: Optional[Dict] = Field(None, description="User inputs for the query")

class CuratorResponse(BaseModel):
    user_inputs: Dict[str, Any] = Field(..., description="User inputs extracted from the query")
    agent_message: str = Field(..., description="Agent's response message")
    CTAs: List[str] = Field(..., description="Call-to-action suggestions")
    tasks: str = Field(..., description="Specific tasks or actions assigned to the farmer")

# Initialize the model and tools
def get_curator():
    """
    Dependency to get the CuratorNode instance.
    """
    # Initialize the model
    model = ChatOpenAI(model="gpt-5-mini", temperature=0.3)
    
    # Define tools
    tools = [
        WebSearchTool(),
        UserDataLoggerTool(),
        MessageHistoryLoggerTool(),
        RetrievalTool(),
        PriceFetcherTool(),
        WeatherAnalysisTool()
        # PestDetectionTool()
    ]
    
    # Initialize the CuratorNode
    curator = CuratorNode(model, tools)
    
    return curator
    
@router.post("/curator", response_model=CuratorResponse)
async def curate(
    request: CuratorRequest,
    curator: CuratorNode = Depends(get_curator)
):
    """
    Endpoint to get curated agricultural advice based on user query.
    
    Args:
        request: CuratorRequest containing the user query and conversation ID
        curator: CuratorNode instance (injected by FastAPI)
        
    Returns:
        CuratorResponse containing agricultural advice and agent message
    """
    try:
        # Call the curator service
        result = await curator(request.query, request.conversation_id, request.inputs)
        
        # Return the result
        return CuratorResponse(
            user_inputs=result.get("user_inputs", {}),
            agent_message=result.get("agent_message", ""),
            CTAs=result.get("CTAs", []),
            tasks=result.get("tasks", "")
        )
    except Exception as e:
        # Log the error and return a 500 error
        print(f"Error in curator service: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error in curator service: {str(e)}")
    
@router.get("/health")
async def health_check():
    """
    Health check endpoint to verify the API is running.
    """
    return {"status": "healthy"}

app = FastAPI()
app.include_router(router)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)
