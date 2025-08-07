from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_functions_agent
from langchain.agents import AgentExecutor
from weather_tool import WeatherAnalysisTool
import os

def test_weather_tool_directly():
    """Test the weather tool directly without requiring OpenAI API key."""
    print("Testing weather tool with Indian locations...")
    weather_tool = WeatherAnalysisTool()
    
    # Test queries with Indian locations
    test_queries = [
        "What's the current weather in Mumbai?",
        "What's the weather forecast for Delhi for the next few days?",
        "Show me the historical weather analysis for Bangalore for the past week",
        "What's the current temperature in Chennai?",
        "What's the weather like in Purulia today?"
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        try:
            result = weather_tool._run(query)
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error processing query: {str(e)}")

def test_agent_interface():
    """Test the weather tool with the LangChain agent interface."""
    print("Testing weather tool with LangChain agent interface...")
    weather_tool = WeatherAnalysisTool()
    
    # Test with structured input (as LangChain agent would call it)
    test_cases = [
        {"location": "Mumbai", "analysis_type": "current"},
        {"location": "Delhi", "analysis_type": "forecast"},
        {"location": "Bangalore", "analysis_type": "historical"}
    ]
    
    for case in test_cases:
        print(f"\nTesting with structured input: {case}")
        try:
            result = weather_tool._run(**case)
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error: {str(e)}")

def main():
    # Check if OpenAI API key is available
    if not os.getenv("OPENAI_API_KEY"):
        print("OpenAI API key not found. Testing weather tool directly...")
        test_weather_tool_directly()
        print("\n" + "="*50)
        test_agent_interface()
        return
    
    # Initialize the weather analysis tool
    weather_tool = WeatherAnalysisTool()
    
    # Initialize the language model
    llm = ChatOpenAI(temperature=0)
    
    # Create a prompt template with agent_scratchpad
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helpful weather assistant that provides accurate weather information. 
        When analyzing weather data, provide insights and recommendations based on the conditions."""),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])
    
    # Create the agent
    agent = create_openai_functions_agent(llm, [weather_tool], prompt)
    agent_executor = AgentExecutor(agent=agent, tools=[weather_tool], verbose=True)
    
    # Example queries with Indian locations
    queries = [
        "What's the current weather in Mumbai?",
        "What's the weather forecast for Delhi for the next few days?",
        "Show me the historical weather analysis for Hiware Bazar for the past week",
        "What's the current temperature in Punsari?",
        "What's the weather like in Khonoma today?"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        try:
            result = agent_executor.invoke({"input": query})
            print(f"Result: {result['output']}")
        except Exception as e:
            print(f"Error processing query: {str(e)}")

if __name__ == "__main__":
    main()