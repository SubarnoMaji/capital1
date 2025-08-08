from fastapi import FastAPI, HTTPException, Body, Depends, APIRouter
from typing import Optional, Any
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv, find_dotenv
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
import os
import sys
from typing import Dict, List, Optional, Any
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from config import Config as config

from core.config import *
from utils import get_logger

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

trip_inputs = TRIP_INPUTS
curated_suggestions = CURATED_SUGGESTIONS
conversation_history = CONVERSATION_HISTORY
curator_message_history = CURATOR_MESSAGE_HISTORY
planner_message_history = PLANNER_MESSAGE_HISTORY

# Initialize the FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

MONGO_URI = config.MONGO_URI
MONGO_DB_NAME = config.MONGO_DB_NAME

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]

@app.get("/api/data")
async def get_data(
    collection_name: str,
    _id: str,
    message_history_type: Optional[str] = None,
    suggestion_id: Optional[str] = None,
    element_id: Optional[str] = None,
    element_name: Optional[str] = None,
):

    logger = get_logger(_id)
    logger.info(
        f"GET /api/data called with ID={_id} and collection_name={collection_name}"
    )

    # Validate collection name
    if collection_name not in [trip_inputs, curated_suggestions, conversation_history]:
        logger.error(f"Invalid collection_name={collection_name} for _id={_id}")
        raise HTTPException(status_code=400, detail="Invalid collection_name")

    # Validate message_history_type for conversation_history
    if collection_name == conversation_history and message_history_type not in [
        curator_message_history,
        planner_message_history,
    ]:
        logger.error(
            f"Invalid message_history_type={message_history_type} for conversation_history with _id={_id}"
        )
        raise HTTPException(
            status_code=400,
            detail="Valid message_history_type required for conversation_history",
        )

    # Validate element parameters
    if element_id is not None or element_name is not None:
        if collection_name != curated_suggestions:
            logger.error(
                f"element_id/element_name only valid for curated_suggestions with _id={_id}"
            )
            raise HTTPException(
                status_code=400,
                detail="element_id/element_name only valid for curated_suggestions",
            )
        if suggestion_id is None:
            logger.error(
                f"element_id/element_name provided without suggestion_id for _id={_id}"
            )
            raise HTTPException(
                status_code=400,
                detail="suggestion_id required when element_id or element_name is provided",
            )

    if suggestion_id is not None and collection_name != curated_suggestions:
        logger.error(f'suggestion_id only valid for collection="curated_suggestions"')
        raise HTTPException(
            status_code=400, detail="suggestion_id only valid for curated_suggestions"
        )

    try:

        obj_id = ObjectId(_id)

        collection = db[collection_name]
        result = collection.find_one({"_id": obj_id})

        if result is None:
            logger.error(f"Error fetching data for _id={_id}: Resource not found.")
            raise HTTPException(status_code=404, detail="Resource not found")

        # Convert ObjectId to string for response
        result["_id"] = str(result["_id"])

        # Process result based on collection type and parameters
        if collection_name == conversation_history:
            # For conversation_history, return only the requested history type
            if message_history_type not in result:
                logger.error(
                    f"Error fetching data for _id={_id}: {message_history_type} not found in result."
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"{message_history_type} not found for this conversation",
                )

            processed_result = {
                "_id": result["_id"],
                message_history_type: result[message_history_type],
            }

        elif collection_name == curated_suggestions:
            if suggestion_id is not None:
                # Find specific suggestion
                suggestion = None
                for s in result.get("suggestions", []):
                    if s.get("suggestion_id") == suggestion_id:
                        suggestion = s
                        break

                if suggestion is None:
                    logger.error(
                        f"Suggestion not found in {collection_name} for _id={_id} and suggestion_id={suggestion_id}"
                    )
                    raise HTTPException(status_code=404, detail="Suggestion not found")

                if element_id is not None or element_name is not None:
                    # Find specific element within suggestion
                    element_details = suggestion.get("element_details", {})
                    element = None

                    if element_id is not None:
                        element = element_details.get(element_id)
                    elif element_name is not None:
                        for elem_id, elem_data in element_details.items():
                            if elem_data.get("name") == element_name:
                                element = elem_data
                                break

                    if element is None:
                        logger.error(
                            f"Element not found in {message_history_type} for _id={_id} and suggestion_id={suggestion_id}"
                        )
                        raise HTTPException(status_code=404, detail="Element not found")

                    processed_result = {"_id": result["_id"], "element": element}
                else:
                    # Return the specific suggestion
                    processed_result = {"_id": result["_id"], "suggestion": suggestion}
            else:
                # Return all suggestions
                processed_result = result
        else:
            processed_result = result

        logger.info(f"Successfully fetched data of {collection_name} for _id={_id}")
        return {
            "status": "success",
            "data": processed_result,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating data for _id={_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.post("/api/data")
async def post_data(collection_name: str, _id: str, data: dict = Body(...)):

    logger = get_logger(_id)
    logger.info(
        f"POST /api/data called with collection_name={collection_name} and _id={_id}"
    )

    # Validate collection name
    valid_collections = [
        curator_message_history,
        planner_message_history,
        trip_inputs,
        curated_suggestions,
    ]
    if collection_name not in valid_collections:
        logger.error(f"Invalid collection_name={collection_name} for _id={_id}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid collection_name. Must be one of {valid_collections}",
        )

    try:
        # Convert _id to ObjectId
        obj_id = ObjectId(_id)

        if collection_name in [curator_message_history, planner_message_history]:
            collection = db[conversation_history]
        else:
            collection = db[collection_name]

        # Check if the document with the given _id exists
        existing_doc = collection.find_one({"_id": obj_id})

        if existing_doc:
            # Update existing document
            if collection_name in [curator_message_history, planner_message_history]:
                # For conversation history, update the specific field
                existing_doc[collection_name] = data
                result = collection.replace_one({"_id": obj_id}, existing_doc)
            else:
                # For other collections, replace the entire document keeping the _id
                data["_id"] = obj_id
                result = collection.replace_one({"_id": obj_id}, data)

            if result.modified_count == 0:
                logger.error(
                    f"Failed to update document in {collection_name} for _id={_id}"
                )
                raise HTTPException(status_code=500, detail="Failed to update document")
        else:
            if collection_name in [curator_message_history, planner_message_history]:
                # For conversation history, create with specific field
                doc_to_insert = {"_id": obj_id, collection_name: data}
            else:
                # For other collections, use data directly and add _id
                doc_to_insert = data
                doc_to_insert["_id"] = obj_id

            result = collection.insert_one(doc_to_insert)

            if not result.acknowledged:
                logger.error(
                    f"Failed to insert document in {collection_name} for _id={_id}"
                )
                raise HTTPException(status_code=500, detail="Failed to insert document")

        return {"status": "success", "timestamp": datetime.now().isoformat()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error posting data for _id={_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.put("/api/data")
async def put_data(
    collection_name: str,
    _id: str,
    key: str,
    suggestion_id: Optional[str] = None,
    data: Any = Body(...),
):

    logger = get_logger(_id)
    logger.info(
        f"PUT /api/data called with collection_name={collection_name}, _id={_id}, key={key}"
    )

    # Validate collection name
    valid_collections = [conversation_history, trip_inputs, curated_suggestions]
    if collection_name not in valid_collections:
        logger.error(f"Invalid collection_name={collection_name} for _id={_id}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid collection_name. Must be one of {valid_collections}",
        )

    try:
        # Convert _id to ObjectId
        obj_id = ObjectId(_id)
        collection = db[collection_name]

        # Check if the document with the given _id exists
        existing_doc = collection.find_one({"_id": obj_id})

        if not existing_doc:
            logger.error(f"Document with _id={_id} not found in {collection_name}")
            raise HTTPException(
                status_code=404, detail=f"Document with _id {_id} not found"
            )

        # Handle updates based on collection type and key
        if collection_name == conversation_history:
            valid_keys = [curator_message_history, planner_message_history]
            if key not in valid_keys:
                logger.error(
                    f"Invalid key={key} for conversation_history in collection {collection_name}"
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid key for conversation_history. Must be one of {valid_keys}",
                )

            existing_doc[key] = data

        elif collection_name == trip_inputs:
            # Define valid keys for user_inputs
            valid_user_input_keys = [
                "user_inputs",  # For updating the whole object
                "source",
                "destination",
                "start_date",
                "end_date",
                "budget",
                "travellers",
                "group_details",
                "preferences",
            ]

            # Validate key
            if key not in valid_user_input_keys:
                logger.error(
                    f"Invalid key={key} for trip_inputs in collection {collection_name}"
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid key for trip_inputs. Must be one of {valid_user_input_keys}",
                )

            # If key is "user_inputs", replace the entire user_inputs object
            if key == "user_inputs":
                # Validate that all keys in the data are allowed
                if isinstance(data, dict):
                    invalid_keys = [
                        k for k in data.keys() if k not in valid_user_input_keys[1:]
                    ]
                    if invalid_keys:
                        logger.error(f"Invalid keys in user_inputs: {invalid_keys}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Invalid keys in user_inputs: {invalid_keys}. Valid keys are: {valid_user_input_keys[1:]}",
                        )
                existing_doc["user_inputs"] = data
            else:
                # Check if user_inputs exists, create if not
                if "user_inputs" not in existing_doc:
                    existing_doc["user_inputs"] = {}

                # Update specific field within user_inputs
                existing_doc["user_inputs"][key] = data

        elif collection_name == curated_suggestions:
            # Valid keys for curated_suggestions
            valid_keys = ["suggestions", "content", "status", "element_details"]

            if key not in valid_keys:
                logger.error(
                    f"Invalid key={key} for curated_suggestions in collection {collection_name}"
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid key for curated_suggestions. Must be one of {valid_keys}",
                )

            # If updating the entire suggestions array
            if key == "suggestions":
                existing_doc["suggestions"] = data
            else:
                # For updating individual suggestion fields, we need suggestion_id
                if not suggestion_id:
                    logger.error(
                        f"Missing suggestion_id for updating fields in curated_suggestions for _id={_id}"
                    )
                    raise HTTPException(
                        status_code=400,
                        detail="suggestion_id is required when updating fields within a suggestion",
                    )

                # Check if suggestions array exists
                if "suggestions" not in existing_doc or not isinstance(
                    existing_doc["suggestions"], list
                ):
                    logger.error(
                        f"Invalid suggestions array in document with _id={_id}"
                    )
                    raise HTTPException(
                        status_code=404,
                        detail="No suggestions array found in the document",
                    )

                # Find the suggestion with the given suggestion_id
                found = False
                for i, suggestion in enumerate(existing_doc["suggestions"]):
                    if suggestion.get("suggestion_id") == suggestion_id:
                        # Update the field in this suggestion
                        existing_doc["suggestions"][i][key] = data
                        found = True
                        break

                if not found:
                    # Show available suggestion IDs for debugging
                    logger.error(
                        f"Suggestion with suggestion_id={suggestion_id} not found in curated_suggestions for _id={_id}"
                    )
                    raise HTTPException(
                        status_code=404,
                        detail=f"Suggestion with suggestion_id '{suggestion_id}' not found.",
                    )

        # Replace the entire document with the updated version
        result = collection.replace_one({"_id": obj_id}, existing_doc)

        if result.matched_count == 0:
            logger.error(
                f"Failed to update document in {collection_name} for _id={_id}"
            )
            raise HTTPException(status_code=500, detail="Failed to update document")

        return {"status": "success", "timestamp": datetime.now().isoformat()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating data for _id={_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify the API is running.
    """
    return {"status": "healthy"}
