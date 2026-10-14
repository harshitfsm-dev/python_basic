import operator
from typing import Annotated, Literal
from typing_extensions import NotRequired, TypedDict
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.types import RetryPolicy

MAX_ATTEMPTS = 3

gemma = ChatOllama(model="gemma4:e4b-mlx", temperature=0.7)
llama = ChatOllama(model="llama3.1:8b", temperature=0.7)
judge_llm = ChatOllama(model="llama3.1:8b", temperature=0)

class Candidate(TypedDict):
    model: str
    text: str

class State(TypedDict):
    topic: str
    # Reducer: parallel branches append instead of overwriting each other
    candidates: Annotated[list[Candidate], operator.add]
    joke: NotRequired[str]
    is_funny: NotRequired[bool]
    feedback: NotRequired[str]
    attempts: NotRequired[int]

class BestPick(BaseModel):
    index: int = Field(description="Zero-based index of the funniest joke")

class Verdict(BaseModel):
    is_funny: bool
    feedback: str = Field(description="Concrete advice to make it funnier")

def make_generator(name: str, model: ChatOllama):
    def generate(state: State) -> dict:
        msg = model.invoke(f"Write a short joke about {state['topic']}")
        return {"candidates": [{"model": name, "text": msg.content}]}
    return generate

def select_best(state: State) -> dict:
    candidates = state["candidates"]
    listing = "\n".join(f"{i}: {c['text']}" for i, c in enumerate(candidates))
    pick = judge_llm.with_structured_output(BestPick).invoke(
        f"Pick the funniest joke:\n{listing}"
    )
    index = pick.index if 0 <= pick.index < len(candidates) else 0
    return {"joke": candidates[index]["text"]}

def evaluate(state: State) -> dict:
    verdict = judge_llm.with_structured_output(Verdict).invoke(
        f"Is this joke funny? Be strict.\n{state['joke']}"
    )
    return {
        "is_funny": verdict.is_funny,
        "feedback": verdict.feedback,
        "attempts": state.get("attempts", 0) + 1,
    }

def improve(state: State) -> dict:
    msg = gemma.invoke(
        f"Rewrite this joke using the feedback.\nJoke: {state['joke']}\nFeedback: {state['feedback']}"
    )
    return {"joke": msg.content}

def route_after_eval(state: State) -> Literal["improve", "__end__"]:
    done = state["is_funny"] or state["attempts"] >= MAX_ATTEMPTS
    return END if done else "improve"

def build_graph():
    retry = RetryPolicy(max_attempts=3)
    g = StateGraph(State)
    g.add_node("gen_gemma", make_generator("gemma", gemma), retry_policy=retry)
    g.add_node("gen_llama", make_generator("llama", llama), retry_policy=retry)
    g.add_node("select_best", select_best)
    g.add_node("evaluate", evaluate, retry_policy=retry)
    g.add_node("improve", improve, retry_policy=retry)

    g.add_edge(START, "gen_gemma")
    g.add_edge(START, "gen_llama")
    g.add_edge(["gen_gemma", "gen_llama"], "select_best")  # join: waits for both
    g.add_edge("select_best", "evaluate")
    g.add_conditional_edges("evaluate", route_after_eval)
    g.add_edge("improve", "evaluate")  # evaluator-optimizer loop
    return g.compile()

if __name__ == "__main__":
    graph = build_graph()
    for update in graph.stream({"topic": "cats"}, stream_mode="updates"):
        print(update)
