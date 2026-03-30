import asyncio
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.config import get_stream_writer
import time

class State(TypedDict):
    a: int

async def test_node(state):
    w = get_stream_writer()
    for i in range(3):
        w({"test": i})
        print(f"{time.time():.3f} Node emitting {i}")
        await asyncio.sleep(0.5)
    return {"a": 1}

async def run():
    G = StateGraph(State)
    G.add_node("test", test_node)
    G.add_edge(START, "test")
    G.add_edge("test", END)
    app = G.compile()
    
    start = time.time()
    async for event in app.astream({"a": 0}, stream_mode="custom"):
        print(f"{time.time():.3f} Received custom event: {event}")

asyncio.run(run())
