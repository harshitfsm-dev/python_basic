from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from dotenv import load_dotenv


load_dotenv()
# 1. Define a tool the agent can use
@tool
def calculate_square(n: int) -> int:
    """Calculates the square of a number."""
    return n * n

tools = [calculate_square]

# 2. Define the model and system prompt
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
system_prompt = "You are a helpful assistant that uses tools when necessary."

# 3. Create the agent graph
agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=system_prompt
)

# 4. Invoke the agent
result = agent.invoke({"messages": [{"role": "user", "content": "What is the square of 12?"}]})

# 5. Extract the answer
print(result["messages"][-1].content)
