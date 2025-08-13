import time
import json
from typing import Dict, Any, List, Optional
import asyncio

import os
import sys

# Add the parent directory (project root) to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_openai import ChatOpenAI
from utils.tools.message_logger import MessageHistoryLoggerTool
from agents.curator.utils.tools.user_inputs import UserDataLoggerTool

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
)

from agents.config import Config as config
from utils.prompts import SYSTEM_PROMPT

class QueryRouter:
    def __init__(self, model, system_prompt: str):
        """
        Initialize the QueryRouter.

        Args:
            model: A language model with tools capability
            system_prompt: The system prompt to use for the curator
        """
        self.model = model
        self.system_prompt = system_prompt
        self.message_logger = MessageHistoryLoggerTool()

    async def process_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routes the user query to appropriate actions or responses 

        Args:
            state: Current state of the agent 

        Returns:
            Updated agent state with router response
        """
        print("QueryRouter: Starting Query Router")
        start_time = time.time()
        conversation_id = state['message_to_curator']['conversation_id']

        # Extract relevant information from state
        query = state['message_to_curator']['query']
        user_inputs = state.get('user_inputs', {})

        # Retrieve existing message history for this conversation_id
        message_history: List[BaseMessage] = await self.message_logger._arun(
            action="retrieve",
            conversation_id=conversation_id,
            agent_type="curator"
        )

        # Initialize with system prompt if no history
        if not isinstance(message_history, list) or len(message_history) == 0:
            message_history = [SystemMessage(content=self.system_prompt)]

        # Try to fetch existing user inputs using Data Logger
        existing_user_inputs = {}
        user_inputs_result = await UserDataLoggerTool()._arun(
            action="retrieve", 
            key=conversation_id
        )
        
        if user_inputs_result and not isinstance(user_inputs_result, str):
            existing_user_inputs = user_inputs_result
        elif isinstance(user_inputs_result, str):
            try:
                existing_user_inputs = json.loads(user_inputs_result)
            except:
                print(f"Error parsing user inputs: {user_inputs_result}")
        
        # Merge user inputs
        merged_user_inputs = {**existing_user_inputs, **user_inputs}
        
        # Add the current query to messages
        message_history.append(
            HumanMessage(
                content=f"""
                Latest User Query:
                {query}

                Conversation ID:
                {conversation_id}

                Persona provided by user to about himself and his agricultural land:
                {json.dumps(merged_user_inputs, indent=2)}

                Before writing your final response, analyse the latest query and the current scenario (provided above) carefully and then answer the following questions only
                1. Has the user explicitly mentioned a specific place (place/city) of his farmland in this query or earlier in the conversation? (yes/no)
                2. In their latest query, does the user seem to be asking (directly/indirectly) for suggestions or advice related to a specific place, farm, or crop of interest? Or are they making general enquiries about agricultural practices, crop selection, soil health, pest management, or weather/climate conditions for farming? // Only if the former, then while writing the final response, use the `WebSearchTool` to curate suggestions or provide relevant information.
                3. If the user has mentioned any specific crops, soil types, weather conditions, or farming techniques, highlight these in your analysis.
                4. Check if the user is seeking advice on government schemes, subsidies, or agricultural policies relevant to their region.
                5. Consider if the user is asking about pest/disease management, irrigation methods, or sustainable/organic farming practices.
                6. If the user has provided or updated information about their land size, crop cycle, or resource availability (e.g., water, equipment), note these changes.
                7. If the user is requesting market price information, supply chain advice, or post-harvest management tips, mention this.
                8. If the user is interested in connecting with local experts, agricultural extension services, or farmer communities, include this in your response.
                
                Note: Check that if there been any change in the user inputs, if you notice any changes, that means, the user has modified that particular input, and you need to work on that, and provide a clarification message that you have noticed the change as well.

                Give only the response to the above questions, in a bullet point format.
                """,
                name="user"
            )
        )
        
        # Get router thoughts and analysis
        router_response = await self.model.ainvoke(message_history)
        print(router_response.content)
        
        # Add router response to message history
        message_history.append(router_response)

        # Ask router to generate the final response
        message_history.append(
            HumanMessage(
                content=f"""
                Now based on the above context as well as your response to the questions, write your final response in the format below:
                {{"agent_message": "A well articulated message along the guidelines suggested", "CTAs": "A comma-separated list (i.e. within square brackets) of prescribed CTAs as per instructions.", "tool_calls": "required tool calls", "conversation_caption": "A short caption, less than 10 words, for the conversation. If this is a new conversation, create a new caption. If continuing the same topic, use the previous caption."}}
                
                Note: 
                1. Output the CTAs as a proper list like [...], not '[...]'
                2. Caption should be same, if there is no major change in the direction of the conversation
                3. Always include the conversation_caption field in your response
                4. If you don't have a previous caption, create a new one based on the current conversation topic

                You have `WebSearchTool`, `UserDataLoggerTool`, `WeatherAnalysisTool`, `SoilInfoTool`, `PestDetectionTool` and `RetrievalTool` at your disposal.

                Note:
                -- In the latest user query, take particular note of any newly provided (or updated) User Persona information regarding their crops, farmland, or agricultural practices. Use the `UserDataLoggerTool` to store or update these agricultural inputs as needed.

                -- Use the `WebSearchTool` to curate suggestions or provide information only if the user is enquiring about specific agricultural locations, crops, or farming techniques that require external information or up-to-date resources.

                -- For general enquiries about agricultural best practices, crop selection, soil health, pest management, weather conditions, or government schemes, do not use the `WebSearchTool`. Instead, answer directly to the best of your knowledge or use other relevant tools as appropriate.

                -- Tool Descriptions:
                   - `UserDataLoggerTool`: Log and manage user agricultural inputs, such as crop details, farmland information, and user preferences. Use this tool to store, retrieve, or update user data.
                   - `WebSearchTool`: Search the web for up-to-date agricultural information, news, or resources relevant to specific queries about crops, locations, or farming techniques.
                   - `WeatherAnalysisTool`: Retrieve current and forecasted weather data for a given location to assist with agricultural planning and decision-making.
                   - `SoilInfoTool`: Provide information about soil types, soil health, and recommendations for soil management based on user location or input.
                   - `PestDetectionTool`: Assist in identifying pests or diseases affecting crops and suggest possible management or treatment options.
                   - `RetrievalTool`: Retrieve previously stored information or documents relevant to the user's agricultural queries or history.
                """,
                name="user"
            )
        )

        # Get router response
        final_router_response = await self.model.ainvoke(message_history)

        # Add router response to message history
        message_history.append(final_router_response)

        # Persist updated message history back to DB
        await self.message_logger._arun(
            action="store",
            conversation_id=conversation_id,
            agent_type="curator",
            messages=message_history
        )

        # Update state with new message history (optional)
        state["message_history"] = message_history
        
        print(f"QueryRouter: Query Router Completed in {time.time() - start_time:.2f} seconds")
        
        return state

if __name__ == "__main__":
    async def test_query_router():
        """
        Test function to demonstrate the QueryRouter functionality.
        """
        print("Testing QueryRouter...")
        
        # Initialize the model
        model = ChatOpenAI(model="gpt-5-mini", temperature=0.2, api_key=config.OPENAI_API_KEY)
        
        # Define system prompt
        system_prompt = SYSTEM_PROMPT
        
        # Initialize the QueryRouter
        router = QueryRouter(model, system_prompt)
        
        # Test state
        test_state = {
            'message_to_curator': {
                'query': "Hi",
                'conversation_id': "test123"
            },
            'message_history': [],
            'user_inputs': {}
        }
        
        # Process the state
        result = await router.process_state(test_state)
        
        # Print the results
        print("\n=== Test Results ===")
        print(f"Query: {test_state['message_to_curator']['query']}")
        print(f"Conversation ID: {test_state['message_to_curator']['conversation_id']}")

        router_response = result.get('message_history', [])[-1].content.replace("```json", "").replace("```", "")
        router_response = json.loads(router_response)

        print(router_response)
        
        return result

    # Run the test
    asyncio.run(test_query_router())