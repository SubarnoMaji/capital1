import time
import json
from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

import os
import sys

# Add the parent directory (project root) to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.tools.message_logger import MessageHistoryLoggerTool
from utils.tools.trip_inputs import UserDataLoggerTool
from utils.tools.suggestions_logger import SuggestionDataLoggerTool

class ResponseFormatter:
    """
    A class responsible for formatting tool results into structured suggestions.
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
        Formats tool results into structured suggestions.

        Args:
            state: Current state of the agent

        Returns:
            Updated agent state with formatted suggestions and curator message
        """
        print("ResponseFormatter: Starting Response Formatter")
        start_time = time.time()

        # Get curator message history
        curator_message_history = state.get("curator_message_history", [])

        # Extract URLs from search results
        urls = [item['Link'] for search_result in state['task_results'].get('GoogleSearchTool', []) 
                for item in search_result.get('result', [])]

        # Extract conversation_id for data retrieval
        conversation_id = state['message_to_curator']['conversation_id']
        
        # Fetch user inputs and previous suggestions
        user_inputs = await self._fetch_user_inputs(conversation_id)
        prev_suggestions = await self._fetch_previous_suggestions(conversation_id)
        
        # Format suggestions using the model
        curator_message_history = await self._generate_suggestions(
            state, curator_message_history, user_inputs
        )
        
        # Process the formatter response
        curator_response = self._extract_curator_response(curator_message_history[-1])
        
        # Add reference URLs to the response
        curator_response["reference_urls"] = urls
        
        # Update suggestions in state
        state["curated_suggestions"] = self._merge_suggestions(prev_suggestions, curator_response)
        
        # Store the newly created suggestion
        await self._store_suggestion(curator_response, conversation_id)
        
        # Generate summary message
        curator_message_history = await self._generate_summary(curator_message_history)
        
        # Retrieve final user inputs for the response
        user_inputs = await self._fetch_user_inputs(conversation_id)
        
        # Update the state with user inputs, suggestions, and summary
        state["message_from_curator"] = {
            "user_inputs": user_inputs,
            "suggestions": state["curated_suggestions"],
            "summary": self._extract_summary(curator_message_history[-1])
        }
        
        # Update message history in state
        state["curator_message_history"] = curator_message_history
        
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
    
    async def _fetch_previous_suggestions(self, conversation_id: str) -> List[Dict]:
        """
        Fetch previous suggestions for the current conversation.
        
        Args:
            conversation_id: Unique identifier for the conversation
            
        Returns:
            List of previous suggestions
        """
        # Create a tool call for retrieving suggestions
        suggestion_logger_tool = SuggestionDataLoggerTool()
        
        # Execute the tool call to retrieve suggestions
        prev_suggestions = await suggestion_logger_tool._arun(
            action="retrieve",
            key=conversation_id
        )
        
        if prev_suggestions == 'No suggestions found for the specified conversation ID':
            return []
        else:
            # Filter to_be_approved suggestions
            return [suggestion for suggestion in json.loads(prev_suggestions) 
                   if suggestion.get("status", "") == "to_be_approved"]
    
    async def _generate_suggestions(self, 
                                   state: Dict[str, Any],
                                   curator_message_history: List[BaseMessage],
                                   user_inputs: Dict) -> List[BaseMessage]:
        """
        Generate suggestions using the model.
        
        Args:
            state: Current agent state
            curator_message_history: Conversation history
            user_inputs: User inputs for context
            
        Returns:
            Updated conversation history with suggestion response
        """
        # Add task results for formatting
        curator_message_history.append(
            HumanMessage(content=f"""
            Please format the following above tool results into a single piece of suggestion content containing everything from the tool results according to the required structure and guidelines:
            -- Suggestion ID (10 alphanumeric characters)
            -- Suggestion Content (Should not contain any links)
            -- Suggestion Status (To be approved)
                         
            JSON Format:
            {{
                "suggestion_id": "xxxxxxxxxx",
                "content": "Formatted suggestion content",
                "status": "to_be_approved"
            }}

            User Query:
            {state['message_to_curator']['query']}

            Current User Requirements:
            {json.dumps(user_inputs, indent=2)}

            Guidelines:
            - Ensure that the suggestion content is a well formatted markdown with each suggestion as a bullet point.
            - The content should be succint, to the point, and not very verbose. It should not contain more than 6-7 bullet points
            - The first line of the suggestion should clearly state the place (specific or generic) for which these suggestions are curated. That place should be formatted in bold.
            - The key locations/activities covered in the suggestion content should be formmated in bold, and you should also generate an emoticon for the following (The emoticon should be related to the location/activity).
            - Only names of specific tourist locations or specific activities in specific locations must be formatted in bold (for eg. Hill Resort should not be boldened, but Tiger Hills should be). Also specify the state/county/city where it is located (as in The Ridge, Shimla or Tiger Hills, Darjeeling).
            - Generic activity names or generic location names or even broad citiy/state names should not be formatted as bold
            - As a rule of thumb, for every bullet point don't have more than 1 or two things formatted in bold
            - DO NOT format anything except these specific tourist locations/activities. Headings should not be boldened.
            - Keep the overall tone friendly and warm. Avoid using any complex language.

            Note:if suggestions == 'No suggestions found for the specified conversation ID':
            filtered_suggestions = []
            - Do not generate any other text other than the suggestions.
            - Ensure the suggestions are in the correct JSON format.
            - Make sure to follow the guidelines for suggestions.
            """)
        )
        
        # Get formatted suggestions
        formatter_response = self.model.invoke(curator_message_history)
        
        # Add formatter response to message history
        curator_message_history.append(formatter_response)
        
        return curator_message_history
    
    def _extract_curator_response(self, formatter_response: BaseMessage) -> Dict:
        """
        Extract structured response from formatter message.
        
        Args:
            formatter_response: The message containing formatted response
            
        Returns:
            Structured curator response as a dictionary
        """
        curator_message = formatter_response.content
        curator_message = curator_message.replace('```json','').replace('```','').strip()
        return json.loads(curator_message)
    
    def _merge_suggestions(self, previous_suggestions: List[Dict], new_suggestion: Dict) -> List[Dict]:
        """
        Merge previous suggestions with the new suggestion.
        
        Args:
            previous_suggestions: List of previous suggestions
            new_suggestion: Newly generated suggestion
            
        Returns:
            Combined list of suggestions
        """
        try:
            return previous_suggestions + [new_suggestion]
        except:
            return [new_suggestion] if isinstance(new_suggestion, dict) else new_suggestion
    
    async def _store_suggestion(self, curator_response: Dict, conversation_id: str) -> None:
        """
        Store the curated suggestion in the data store.
        
        Args:
            curator_response: The suggestion to store
            conversation_id: Unique identifier for the conversation
        """
        # Create a tool call for storing suggestions
        suggestion_logger_tool = SuggestionDataLoggerTool()
        
        # Execute the tool call to store suggestions with detailed elements
        try:
            res = await suggestion_logger_tool._arun(
                action="store",
                data=curator_response,
                key=conversation_id
            )
            print(res)
        except Exception as e:
            raise e
    
    async def _generate_summary(self, curator_message_history: List[BaseMessage]) -> List[BaseMessage]:
        """
        Generate a summary message for the user.
        
        Args:
            curator_message_history: Conversation history
            
        Returns:
            Updated conversation history with summary response
        """
        # Add summary request to message history
        curator_message_history.append(
            HumanMessage(content=f"""
            Now that you have curated some suggestions, can you should write a small final message that explains the thought process behind curating these suggestions, including any assumptions made to fill gaps in user input.
            In this same message, in a new line, you can ask/guide users on how to give feedback on the recommendations

            Additionally, you should also offer them them 3 CTAs to help them give feedback based on your suggestions. These must be logical queries/feedback that the user might have based on your response.

            Your response should be in the following format:
            {{"agent_message": "A well articulated message with the curated suggestions", "CTAs": "A comma-separated list (i.e. within square brackets) of the two prescribed CTAs", "plan_gen_flag": "yes" if user has asked for detailed plan and provided all mandatory inputs, else "no","conversation_caption": "A short caption, less than 10 words, for the conversation. If this is a new conversation, create a new caption. If continuing the same topic, use the previous caption."}}.

            Make sure that the tone of your final message is friendly and warm. And it should not focus too much on relisting the contents of the curated suggestions.
            """)
        )
        
        # Get summary message
        summary_response = self.model.invoke(curator_message_history)
        
        # Add summary response to message history
        curator_message_history.append(summary_response)
        
        return curator_message_history
    
    def _extract_summary(self, summary_response: BaseMessage) -> str:
        """
        Extract the summary content from the response.
        
        Args:
            summary_response: The message containing the summary
            
        Returns:
            Cleaned summary content as a string
        """
        return summary_response.content.replace('```json','').replace('```','').strip()