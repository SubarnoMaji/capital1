import time
import json
from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

import os
import sys

# Add the parent directory (project root) to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.tools.message_logger import MessageHistoryLoggerTool
from agents.curator.utils.tools.user_inputs import UserDataLoggerTool

class ResponseFormatter:
    """
    A class responsible for formatting tool results into agricultural advice and responses.
    It processes raw tool outputs into a user-friendly format and provides
    summary messages for agent-user interactions.
    """
    
    def __init__(self, model, tools):
        """
        Initialize the ResponseFormatter with models and tools.
        
        Args:
            model: The language model for generating summaries
            tools: List of tool objects available for use
        """
        self.model = model
        self.tools = tools
    
    async def process_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formats tool results into agricultural advice and responses.

        Args:
            state: Current state of the agent

        Returns:
            Updated agent state with formatted response and curator message
        """
        print("ResponseFormatter: Starting Response Formatter")
        start_time = time.time()

        # Get message history
        message_history = state.get("message_history", [])

        # Extract URLs from search results for reference
        urls = []
        task_results = state.get('task_results', {})
        if task_results:
            for search_result in task_results.get('GoogleSearchTool', []):
                if isinstance(search_result.get('result'), list):
                    for item in search_result.get('result', []):
                        if isinstance(item, dict) and 'Link' in item:
                            urls.append(item['Link'])

        # Extract conversation_id for data retrieval
        conversation_id = state['message_to_curator']['conversation_id']
        
        # Fetch user inputs
        user_inputs = await self._fetch_user_inputs(conversation_id)
        
        # Generate comprehensive agricultural advice and summary in one call
        message_history = await self._generate_complete_response(
            state, message_history, user_inputs
        )
        
        # Retrieve final user inputs for the response
        user_inputs = await self._fetch_user_inputs(conversation_id)
        
        # Update the state with user inputs and summary
        state["message_from_curator"] = {
            "user_inputs": user_inputs,
            "summary": self._extract_summary(message_history[-1])
        }
        
        # Update message history in state
        state["message_history"] = message_history
        
        print(f"ResponseFormatter: Response Formatter Completed in {time.time() - start_time:.2f} seconds")
        
        return state
    
    async def _fetch_user_inputs(self, conversation_id: str) -> Dict:
        """
        Fetch user inputs for the current conversation.
        
        Args:
            conversation_id: Unique identifier for the conversation
            
        Returns:
            Dictionary containing user input data
        """
        user_inputs = {}
        
        # Try to fetch existing user inputs using Data Logger
        data_logger_tool = UserDataLoggerTool()
        
        if data_logger_tool:
            try:
                # Retrieve user inputs for this conversation
                user_inputs_result = await data_logger_tool._arun(
                    action="retrieve",
                    key=conversation_id
                )
                
                if user_inputs_result and not isinstance(user_inputs_result, str):
                    user_inputs = user_inputs_result
                elif isinstance(user_inputs_result, str):
                    try:
                        user_inputs = json.loads(user_inputs_result)
                    except:
                        print("Failed to parse user inputs as JSON")
            except Exception as e:
                print(f"Error retrieving user inputs: {e}")
                
        return user_inputs
    
    async def _generate_complete_response(self, 
                                         state: Dict[str, Any],
                                         message_history: List[BaseMessage],
                                         user_inputs: Dict) -> List[BaseMessage]:
        """
        Generate a complete agricultural advice response in a single call.
        
        Args:
            state: Current agent state
            message_history: Conversation history
            user_inputs: User inputs for context
            
        Returns:
            Updated conversation history with complete response
        """
        # Streamlined single prompt focused on agent message output
        message_history.append(
            HumanMessage(content=f"""
            Analyze the tool results above and provide a comprehensive agricultural advice response to the user.

            User Query: {state['message_to_curator']['query']}

            User Context: {json.dumps(user_inputs, indent=2) if user_inputs else "No additional context available"}

            Respond in this exact JSON format:
            {{
                "agent_message": "Your comprehensive agricultural advice here",
                "CTAs": ["Follow-up question 1", "Follow-up question 2", "Follow-up question 3"],
                "conversation_caption": "Brief caption (max 8 words)"
            }}

            For the agent_message, include:
            • Practical, actionable response based on tool results
            • Specific recommendations for crops, soil, weather, or pest management (if relevant)
            • Local practices and government schemes (if relevant)
            
            Maintain a warm, friendly tone throughout the length of the conversation
            Try to keep the response length in check, within 70-150 words, would suffice.

            CTAs should be logical follow-up questions the user might ask based on your advice.
            """)
        )
        
        # Get complete response in one call
        complete_response = self.model.invoke(message_history)
        
        # Add response to message history
        message_history.append(complete_response)
        
        return message_history
    
    def _extract_summary(self, summary_response: BaseMessage) -> str:
        """
        Extract the summary content from the response.
        
        Args:
            summary_response: The message containing the summary
            
        Returns:
            Cleaned summary content as a string
        """
        return summary_response.content.replace('```json','').replace('```','').strip()