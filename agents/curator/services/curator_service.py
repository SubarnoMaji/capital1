import json
import time
import asyncio
from enum import Enum
from typing import TypedDict, List, Dict, Any, Literal, Tuple
import nest_asyncio
import base64
import datetime

import os
import sys

# Add the parent directory (project root) to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.graph import MessagesState, StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from concurrent.futures import ThreadPoolExecutor
import concurrent.futures

from curator.utils.query_router import QueryRouter
from curator.utils.task_manager import TaskManager
from curator.utils.response_formatter import ResponseFormatter
from curator.utils.gather_elements import ElementDetailGatherer
from curator.utils.tools.search_tool import GoogleSearchTool
from curator.utils.tools.image_search_tool import GoogleImageSearchTool
from curator.utils.tools.message_logger import MessageHistoryLoggerTool
from curator.utils.tools.trip_inputs import UserDataLoggerTool
from curator.utils.tools.suggestions_logger import SuggestionDataLoggerTool
from curator.utils.prompts import CURATOR_SYSTEM_PROMPT

nest_asyncio.apply()

class CuratorResponse(TypedDict):
    user_inputs: Dict
    curated_suggestions: List[Dict]
    agent_message: str
    CTAs: List[str]
    plan_gen_flag: str
    conversation_caption: str

class AgentState(TypedDict):
    message_to_curator: Dict
    message_from_curator: Dict
    curator_message_history: List[BaseMessage]
    planner_message_history: List[BaseMessage]
    task_history: List[Dict[str, Any]]
    conversation_summary: List[Dict[str, Any]]
    curated_suggestions: List[Dict]
    itinerary: str

class CuratorNode:
    """
    CuratorNode orchestrates the query routing, task management, and response formatting
    components to process user queries and generate curated suggestions.
    """
    
    def __init__(self, model, tools, system_prompt = CURATOR_SYSTEM_PROMPT):
        """
        Initialize the CuratorNode with models, tools, and system prompt.
        
        Args:
            model: Language model for generating summaries
            tools: List of tool objects available for use
            system_prompt: System prompt for the curator
        """
        self.model = model
        self.tools = tools
        self.system_prompt = system_prompt
        
        # Initialize components
        self.query_router = QueryRouter(model, system_prompt)
        self.task_manager = TaskManager(tools)
        self.response_formatter = ResponseFormatter(model, tools)
        self.element_detail_gatherer = ElementDetailGatherer(model)
    
    async def __call__(self, query: str, conversation_id: str, inputs: Dict[str, Any]) -> Dict:
        """
        Main execution flow for the CuratorNode

        Args:
            query: User's query string
            conversation_id: Unique conversation identifier

        Returns:
            Dictionary containing user_inputs, suggestions, and summary
        """
        print("CuratorNode: Starting Execution")
        start_time = time.time()

        # Create the agent state internally
        state = AgentState()
        state["message_to_curator"] = {
            "query": query,
            "conversation_id": conversation_id,
            "inputs": inputs
        }

        user_data_logger_tool = UserDataLoggerTool()
        initial_inputs = await user_data_logger_tool._arun(
            action="retrieve",
            key=conversation_id
        )

        if initial_inputs:
            initial_inputs = json.loads(initial_inputs)
            # Compare and update inputs with any new values from the user
            modified = False
            for key, value in inputs.items():
                if value and (key not in initial_inputs or initial_inputs[key] != value):
                    initial_inputs[key] = value
                    modified = True
                    print(f"CuratorNode: Updated {key} from {initial_inputs.get(key, 'None')} to {value}")
                    # Log the update in the history
                    await user_data_logger_tool._arun(
                        action="update",
                        key=conversation_id,
                        data={key: value}
                    )

            if modified:
                print(f"CuratorNode: Modified Inputs: {initial_inputs}")
                # Store the complete updated inputs
                await user_data_logger_tool._arun(
                    action="store",
                    key=conversation_id,
                    data=initial_inputs
                )

        # Initialize result dictionary
        result: CuratorResponse = {
            "user_inputs": {},
            "suggestions": {},
            "agent_message": "",
            "CTAs": [],
            "plan_gen_flag": "no",
            "conversation_caption": ""
        }

        # Decide an appropriate next action (tool calls or Response)
        state = await self.query_router.process_state(state)

        # Check if router generated tool calls
        curator_message_history = state.get("curator_message_history", [])

        if curator_message_history:
            last_ai_message = next((msg for msg in reversed(curator_message_history)
                                if isinstance(msg, AIMessage)), None)
            last_ai_message = json.loads(last_ai_message.content.replace('```json','').replace('```','').strip())

            # If we have tool calls, execute them and format the results
            if last_ai_message and last_ai_message.get("tool_calls", None) is not None:
                # Execute tools
                state = await self.task_manager.process_state(state)

                # Only proceed if we have task results and we have a GoogleSearchTool call
                if state.get('task_results', None) is None or not any(tool_call.get("name") == "GoogleSearchTool" for tool_call in last_ai_message.get("tool_calls", [])):
                    print("No GoogleSearchTool results found, directly returning")

                    # Create a tool call for retrieving user inputs
                    user_data_logger_tool = UserDataLoggerTool()

                    # Execute the tool call to retrieve user inputs
                    user_inputs_result = await user_data_logger_tool._arun(
                        action="retrieve",
                        key=conversation_id
                    )

                    user_inputs = json.loads(user_inputs_result)
                    user_inputs = {k: v for k, v in user_inputs.items() if k not in ["timestamp", "created_at", "updated_at"]}

                    result["user_inputs"] = user_inputs
                    result["suggestions"] = {}
                    result["agent_message"] = last_ai_message.get("agent_message", "")
                    result["CTAs"] = last_ai_message.get("CTAs", [])
                    result["plan_gen_flag"] = last_ai_message.get("plan_gen_flag", "no")
                    result["conversation_caption"] = last_ai_message.get("conversation_caption", "")

                    await MessageHistoryLoggerTool()._arun(action="store", conversation_id=conversation_id, messages=state["curator_message_history"], agent_type="curator")

                else:
                    # Format the results
                    state = await self.response_formatter.process_state(state)

                    # Extract suggestions from state for the result
                    suggestions = state.get("curated_suggestions", [])
                    if len(suggestions)>0:
                      result["suggestions"] = [{key: value for key, value in suggestion.items() if key in ["suggestion_id", "content", "status", "reference_urls", "timestamp", "updated_at"]} for suggestion in suggestions]
                    else:
                      result["suggestions"] = {}

                    # Keep only latest suggestion
                    if result["suggestions"]:
                      for suggestion in result["suggestions"]:
                        if "timestamp" in suggestion and isinstance(suggestion["timestamp"], str):
                          try:
                            # Attempt to parse with the given format
                            suggestion["timestamp"] = datetime.datetime.strptime(suggestion["timestamp"], '%Y-%m-%dT%H:%M:%S.%f')
                          except ValueError:
                            try:
                              # Attempt to parse without milliseconds
                              suggestion["timestamp"] = datetime.datetime.strptime(suggestion["timestamp"], '%Y-%m-%dT%H:%M:%S')
                            except ValueError:
                              # Handle cases where timestamp format might be different.
                              print(f"Warning: Could not parse timestamp: {suggestion['timestamp']}")
                              suggestion["timestamp"] = None  # Or a default datetime


                      # Find the suggestion with the maximum timestamp (latest suggestion)
                      latest_suggestion = max(result["suggestions"], key=lambda x: x["timestamp"] or datetime.datetime.min)

                      # Update result["suggestions"] to keep only the suggestion with the maximum timestamp
                      result["suggestions"] = latest_suggestion

                    # Extract user inputs from state for the result
                    result["user_inputs"] = state.get("message_from_curator", {}).get("user_inputs", {})

                    # Extract other info from state for the result
                    raw_summary = state.get("message_from_curator", {}).get("summary", "")
                    summary = json.loads(raw_summary)
                    result["agent_message"] = summary["agent_message"]
                    result["CTAs"] = summary["CTAs"]
                    result["plan_gen_flag"] = state.get("plan_gen_flag", "no")
                    result["conversation_caption"] = summary["conversation_caption"]

                    await MessageHistoryLoggerTool()._arun(action="store", conversation_id=conversation_id, messages=state["curator_message_history"], agent_type="curator")

                    # Start background element processing
                    asyncio.create_task(self._process_element_details(state, conversation_id))

        print(f"CuratorNode: Execution Completed in {time.time() - start_time:.2f} seconds")

        # Return the result immediately, before the background task completes
        return result
    
    async def _process_element_details(self, state: Dict[str, Any], conversation_id: str) -> None:
        """
        Process element details in the background.
        
        Args:
            state: Current agent state
            conversation_id: Unique conversation identifier
        """
        try:
            print("Starting background element details processing")
            element_details_state = await self.element_detail_gatherer.gather_element_details(state)

            if "curated_suggestions" in element_details_state:
                curated_suggestions = element_details_state["curated_suggestions"]

                for suggestion in curated_suggestions:
                    element_details = suggestion.get("element_details", None)
                    suggestion_id = suggestion.get("suggestion_id", None)
                    if element_details is None or suggestion_id is None:
                        continue
                    # Update the stored suggestion with element_details
                    suggestion_logger_tool = SuggestionDataLoggerTool()
                    tool_result = await suggestion_logger_tool._arun(
                        action="update",
                        data={"element_details": element_details},
                        key=conversation_id,
                        suggestion_id=suggestion_id
                    )
                    print(tool_result)
        except Exception as e:
            print(f"Error in background element details processing: {str(e)}")
            # Log the full traceback for debugging
            import traceback
            print(traceback.format_exc())


if __name__ == "__main__":
    async def test_curator():
        """
        Test function to demonstrate the CuratorNode functionality.
        """
        print("Testing CuratorNode...")
        
        # Initialize the model
        model = ChatOpenAI(model="gpt-4o", temperature=0.2)
        
        # Define basic tools
        tools = [
            GoogleSearchTool(), UserDataLoggerTool(), SuggestionDataLoggerTool()
        ]
        
        # Initialize the CuratorNode
        curator = CuratorNode(model, tools)
        
        # Test query and conversation IDeleme
        test_query = "can you tell me about Baga beach?"
        test_conversation_id = f"xyz12"
        
        # Call the curator
        result = await curator(test_query, test_conversation_id)
        
        # Print the results
        print("\n=== Test Results ===")
        print(f"Query: {test_query}")
        print(f"Conversation ID: {test_conversation_id}")
        
        print(f"\nAgent Message: {result.get('agent_message', 'No message')}")
        print(f"Plan Generation Flag: {result.get('plan_gen_flag', 'no')}")
        
        return result

    # Run the test
    asyncio.run(test_curator())