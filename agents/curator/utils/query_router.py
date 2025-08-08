import time
import json
from typing import Dict, Any, List, Optional
import asyncio

import os
import sys

# Add the parent directory (project root) to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from utils.tools.message_logger import MessageHistoryLoggerTool
from utils.tools.trip_inputs import UserDataLoggerTool
from utils.tools.suggestions_logger import SuggestionDataLoggerTool
from config import Config as config
from utils.prompts import CURATOR_SYSTEM_PROMPT

class QueryRouter:
    def __init__(self, model, system_prompt: str):
        """
        Initialize the CuratorNode.

        Args:
            model: A language model with tools capability
            system_prompt: The system prompt to use for the curator
        """
        self.model = model
        self.system_prompt = system_prompt

    async def process_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routes the user query to appropriate actions or responses 

        Args:
            state: Current state of the agent 

        Returns:
            Updated agent state with router response
        """
        print("CuratorNode: Starting Query Router")
        start_time = time.time()
        
        # Extract relevant information from state
        query = state['message_to_curator']['query']
        conversation_id = state['message_to_curator']['conversation_id']
        
        # Initialize or get curator_message_history
        curator_message_history = await MessageHistoryLoggerTool()._arun(
            action="retrieve", 
            conversation_id=state['message_to_curator']['conversation_id'], 
            agent_type="curator"
        )
        
        if not curator_message_history:
            curator_message_history.append(SystemMessage(content=self.system_prompt))
        
        # Format suggestions for display
        suggestions = await SuggestionDataLoggerTool()._arun(
            action="retrieve", 
            key=conversation_id
        )
        
        if suggestions == 'No suggestions found for the specified conversation ID':
            filtered_suggestions = []
        else:
            suggestions = json.loads(suggestions)
            filtered_suggestions = [
                {'content': s['content'], 'status': s['status']} 
                for s in suggestions if s['status'] == 'to_be_approved'
            ]
        
        # Try to fetch existing user inputs using Data Logger
        user_inputs = {}
        user_inputs_result = await UserDataLoggerTool()._arun(
            action="retrieve", 
            key=conversation_id
        )
        
        if user_inputs_result and not isinstance(user_inputs_result, str):
            user_inputs = user_inputs_result
        elif isinstance(user_inputs_result, str):
            try:
                user_inputs = json.loads(user_inputs_result)
            except:
                print(f"Error parsing user inputs: {user_inputs_result}")
        
        # Add the current query to messages
        curator_message_history.append(
            HumanMessage(
                content=f"""
                Latest User Query:
                {query}

                Conversation ID:
                {conversation_id}

                Current Suggestions that are not approved:
                {json.dumps(filtered_suggestions, indent=2)}

                User Preferences provided so far for planning a trip:
                {json.dumps(user_inputs, indent=2)}

                Mandatory User Preferences still pending for planning a trip:
                {list(["source", "destination", "start_date", "end_date"] - user_inputs.keys())}

                Before writing your final response, analyse the latest query and the current scenario (provided above) carefully and then answer the following questions only
                1. Has the user explicitly mentioned a specific destination (place/city) of interest in this query or earlier in the conversation? (yes/no)
                2. In their latest query, does the user seem to be asking (directly/indirectly) for suggestions wrt that specific destination of interest? Or are they making general enquiries about travel ideas i.e. places worth visiting, romantic spot ideas, or weather/climate at a place // Only if former, then while writing the final response, use the `GoogleSearchTool` to curate suggestions.
                3. Has the user completely accepted the previously curated suggestion wrt that specific destination of interest? (yes/no/NA) // If yes, then while writing the final answer you should use `SuggestionDataLoggerTool` to update status as 'approved'
                4. If not, have they completely rejected it or are they are somewhat okay with it even though its not perfect for them? Also have they asked for modifying a small part of the suggestions // If somewhat okay, then you should use `SuggestionDataLoggerTool` to update status as 'approved' and update content as required. If completely rejected, you should use it to update status as 'rejected'
                5. After having accepted, has the user also asked (directly/indirectly) for fresh suggestions? (yes/no/NA). // If yes, make a separate call to `GoogleSearchTool` to get fresh suggestions
                6. Is the user asking for a detailed plan? // If yes, then are there any approved suggestions? If no, then you should revert back to the user asking if they want new suggestions (if they have previously rejected them), or if they want to proceed with the plan generation based on the previously curated suggestions. 

                Note: Check that if there been any change in the user inputs, if you notice any changes, that means, the user has modified that particular input, and you need to work on that, and provide a clarification message that you have noticed the change as well.

                Give only the response to the above questions, in a bullet point format.
                """,
                name="user"
            )
        )
        
        # Get router thoughts and analysis
        router_response = await self.model.ainvoke(curator_message_history)
        print(router_response.content)
        
        # Add router response to message history
        curator_message_history.append(router_response)

        # Ask router to generate the final response
        curator_message_history.append(
            HumanMessage(
                content=f"""
                Now based on the above context as well as your response to the questions, write your final response in the format below:
                {{"agent_message": "A well articulated message along the guidelines suggested", "CTAs": "A comma-separated list (i.e. within square brackets) of prescribed CTAs as per instructions. If plan_gen_flag is yes then this should always be []", "tool_calls": "required tool calls", "plan_gen_flag": "Should be yes only when the user has provided all mandatory inputs (i.e. starting location, destination, travel start and end dates) and approved suggestions and has asked for detailed plan", "conversation_caption": "A short caption, less than 10 words, for the conversation. If this is a new conversation, create a new caption. If continuing the same topic, use the previous caption."}}
                
                Note: 
                1. Output the CTAs as a proper list like [...], not '[...]'
                2. Caption should be same, if there is no major change in the direction of the conversation
                3. Always include the conversation_caption field in your response
                4. If you don't have a previous caption, create a new one based on the current conversation topic

                You have `GoogleSearchTool`, `UserDataLoggerTool` and `SuggestionDataLoggerTool` at your disposal.

                Note:
                -- In the latest user query, take particular note of any newly provided (or updated) User Preferences regarding planning a trip. And use the `UserDataLoggerTool` to store/update these inputs accordingly.
                -- Don't forget to use the `SuggestionDataLoggerTool` to approve or reject any suggestions that are not approved, especially before curating new ones. Deduce the appropriate action to the best of your ability from the latest user query
                -- Use the `GoogleSearchTool` to curate suggestions/information only if the user is enquiring for details (or additional details) about a specific destination that they are interested in.
                -- For general enquiries about travel worthy places (e.g. some romantic locations in India, places to travel with friends, weekend getway spots, etc) do not use `GoogleSearchTool` tool. Rather in the interest of time, answer directly to the best of your knowledge.
                """,
                name="user"
            )
        )

        # Get router response
        router_response = await self.model.ainvoke(curator_message_history)

        # Add router response to message history
        curator_message_history.append(router_response)

        state["curator_message_history"] = curator_message_history
        state["curated_suggestions"] = filtered_suggestions
        
        print(f"CuratorNode: Query Router Completed in {time.time() - start_time:.2f} seconds")
        
        return state

if __name__ == "__main__":
    async def test_query_router():
        """
        Test function to demonstrate the QueryRouter functionality.
        """
        print("Testing QueryRouter...")
        
        # Initialize the model
        model = ChatOpenAI(model="gpt-4o", temperature=0.2, api_key=config.OPENAI_API_KEY)
        
        # Define system prompt
        system_prompt = CURATOR_SYSTEM_PROMPT
        
        # Initialize the QueryRouter
        router = QueryRouter(model, system_prompt)
        
        # Test state
        test_state = {
            'message_to_curator': {
                'query': "Hi",
                'conversation_id': "test123"
            }
        }
        
        # Process the state
        result = await router.process_state(test_state)
        
        # Print the results
        print("\n=== Test Results ===")
        print(f"Query: {test_state['message_to_curator']['query']}")
        print(f"Conversation ID: {test_state['message_to_curator']['conversation_id']}")
        # print(f"Router Response: {result.get('curator_message_history', [])[-1].content}")

        router_response = result.get('curator_message_history', [])[-1].content.replace("```json", "").replace("```", "")
        router_response = json.loads(router_response)

        print(router_response)
        
        return result

    # Run the test
    asyncio.run(test_query_router())