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
        
        # Generate agricultural advice using the model
        message_history = await self._generate_agricultural_advice(
            state, message_history, user_inputs
        )
        
        # Generate summary message
        message_history = await self._generate_summary(message_history)
        
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
    
    async def _generate_agricultural_advice(self, 
                                           state: Dict[str, Any],
                                           message_history: List[BaseMessage],
                                           user_inputs: Dict) -> List[BaseMessage]:
        """
        Generate agricultural advice using the model.
        
        Args:
            state: Current agent state
            message_history: Conversation history
            user_inputs: User inputs for context
            
        Returns:
            Updated conversation history with agricultural advice response
        """
        # Add task results for formatting
        message_history.append(
            HumanMessage(content=f"""
            Please analyze the tool results above and provide comprehensive agricultural advice based on the user's query and context. 

            User Query:
            {state['message_to_curator']['query']}

            Current User Requirements:
            {json.dumps(user_inputs, indent=2)}

            Guidelines:
            - Provide practical, actionable agricultural advice
            - Focus on the specific crops, soil types, or farming techniques mentioned
            - Include relevant information about weather conditions, pest management, or soil health
            - Consider local agricultural practices and government schemes if applicable
            - Structure the advice in a clear, organized manner
            - Include any relevant references or sources if available
            - Try to include as much information as possible from the tool results

            Format your response as a comprehensive agricultural advice message that directly addresses the user's query.
            """)
        )
        
        # Get agricultural advice
        advice_response = self.model.invoke(message_history)
        
        # Add advice response to message history
        message_history.append(advice_response)
        
        return message_history
    
    async def _generate_summary(self, message_history: List[BaseMessage]) -> List[BaseMessage]:
        """
        Generate a summary message for the user.
        
        Args:
            message_history: Conversation history
            
        Returns:
            Updated conversation history with summary response
        """
        # Add summary request to message history
        message_history.append(
            HumanMessage(content=f"""
            Now that you have provided agricultural advice, write a final message that summarizes the key points and offers next steps for the user.

            Additionally, you should also offer them 3 CTAs to help them continue their agricultural journey. These must be logical queries/feedback that the user might have based on your response.

            Your response should be in the following format:
            {{"agent_message": "A well articulated summary message with the key agricultural advice points", "CTAs": "A comma-separated list (i.e. within square brackets) of the three prescribed CTAs", "conversation_caption": "A short caption, less than 10 words, for the conversation. If this is a new conversation, create a new caption. If continuing the same topic, use the previous caption."}}.

            Make sure that the tone of your final message is friendly and warm. Focus on summarizing the key agricultural advice and providing clear next steps.
            """)
        )
        
        # Get summary message
        summary_response = self.model.invoke(message_history)
        
        # Add summary response to message history
        message_history.append(summary_response)
        
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