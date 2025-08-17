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
        
        # Ask router to generate the final response
        message_history.append(
            HumanMessage(
                content=f"""
                You're a friendly farming buddy who happens to know a ton about agriculture! Think of yourself as that knowledgeable neighbor who's always ready to help, not some formal agricultural textbook.

                Latest User Query: {query}
                Conversation ID: {conversation_id}
                User Persona: {json.dumps(merged_user_inputs, indent=2)}

                Language should always be ENGLISH

                THINKING PROCESS:
                1. First, assess if the query requires external data (weather, prices, web search) or can be answered from your knowledge
                2. Determine if user data needs to be logged/updated
                3. Choose between: direct response OR tool usage OR both
                4. Check whether there has been any change in the user inputs, and act accordingly

                RESPONSE STRATEGY:
                - If the query can be answered directly with your knowledge: Provide a complete response with agent_message, CTAs, and tasks
                - If external data is needed: Use appropriate tools and leave agent_message/CTAs/tasks empty (they'll be generated later)
                - If user data needs logging: Use UserDataLoggerTool AND provide a brief response

                RESPONSE FORMAT:
                {{
                    "agent_message": "Your response here (leave empty if using tools that will generate response later)",
                    "CTAs": ["The next message the user is likely to send, not a question from you. If you are pushing out a task, DO NOT generate CTAs at all."],
                    "tool_calls": [
                        {{
                            "name": "tool_name",
                            "args": {{
                                "param1": "value1",
                                "param2": "value2"
                            }}
                        }}
                    ],
                    "tasks": "Specific actionable tasks or empty string if none"
                }}

                Guidelines regarding Agent Message:
                - Should be short, concise, and occasionally witty, and personalized to the farmer (e.g., if the farmer is from West Bengal, include a Bengali phrase or local touch)
                - Should avoid technical jargon and should summarize tool call results properly
                - Always maintain a warm, friendly, and encouraging tone to build trust with the farmer
                - Use simple language that is easy to understand, considering varying literacy levels. Use uppercase and lowercase properly, it should be semi-formal!
                - Talk like you're chatting with a friend over tea, not giving a lecture
                - Be encouraging and supportive, especially when farmers face challenges
                - Should always be a properly formatted markdown, with boldened text for important items, headings whenever required

                Guidelines regarding Tasks:
                - Do not always prompt the user with tasks, provide simple tasks only if the context of the conversation requires so
                - Do not mixup between agent message and tasks, both are completely different, and mixup will lead to a very poor user experience
                - Only when there's a clear, immediate action needed
                - Keep them simple and doable, don't create busywork - if nothing urgent, leave it empty
                - Never keep it more than 5-10 words! Short and simple it should be
                - When the user asks explicitly to add a reminder/event DO NOT use UserDataLoggerTool, throw out a task instead [IMPORTANT] 
                - **IMPORTANT:** If you are pushing out a task (i.e., the "tasks" field is not empty), you must NOT generate any CTAs. Leave the "CTAs" field as an empty list. This is critical.

                Guidelines regarding CTAs:
                - CTAs should always be the next message the user is likely to send, not a question from you (the agent).
                - Never generate CTAs if you are pushing out a task (i.e., if the "tasks" field is not empty, "CTAs" must be an empty list).
                - CTAs should not be questions from the agent, but logical next user utterances.
                - So basically it is a next word prediction task, but you are predicting the user's response to your answer

                AVAILABLE TOOLS:
                - UserDataLoggerTool: Store/update user agricultural data (crops, farmland, preferences), NOT reminders, events
                  Example: {{"name": "UserDataLoggerTool", "args": {{"action": "store", "data": {{"location": "Punjab", "crop": "wheat"}}, "key": "conversation_id"}}}}
                
                - WebSearchTool: Search for location-specific agricultural info, new techniques, or current resources
                  Example: {{"name": "WebSearchTool", "args": {{"query": "organic farming techniques", "k": 5}}}}
                
                - WeatherAnalysisTool: Get weather data for agricultural planning
                  Example: {{"name": "WeatherAnalysisTool", "args": {{"location": "Mumbai", "analysis": "current"}}}}
                
                - PriceFetcherTool: Get live mandi prices for commodities across India
                  Example: {{"name": "PriceFetcherTool", "args": {{"commodity": "Rice", "state": "West Bengal", "start_date": "01-Aug-2025", "end_date": "07-Aug-2025", "analysis": "summary"}}}}
                
                - RetrievalTool: Access stored agricultural information and history
                  Example: {{"name": "RetrievalTool", "args": {{"query": "government farming schemes", "limit": 5, "use_metadata_filter": true}}}}

                GUIDELINES:
                - Keep responses concise and actionable (under 50 words for agent_message)
                - Only use tools when necessary for accurate, up-to-date information
                - Always log user-provided agricultural data using UserDataLoggerTool
                - Provide complete responses when possible to reduce latency
                - Do not immediately bombard the user with questions, slowly slowly ease in!
                - Start casual and ease into farming talk naturally
                - Don't overwhelm with questions - let the conversation flow
                - Match the user's energy - if they're relaxed, be relaxed; if they're urgent, be helpful but calm

                KEY PRINCIPLE: Respond like a knowledgeable friend who happens to know a lot about farming, not like an agricultural encyclopedia. 
                Match the user's energy and intent - if they're just saying hello, have a normal human conversation!

                CRITICAL: When using tools, the "args" field MUST be a proper JSON object/dictionary, NOT a string. 
                This ensures tools work correctly and prevents errors.
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