import sys
import os
import asyncio
import logging

sys.path.append(os.getcwd())

from app.agents.tier5_output.response_composer import ResponseComposerAgent
from app.agents.base import AgentInput, UserContext

logging.basicConfig(level=logging.INFO)

async def run():
    agent = ResponseComposerAgent()
    input_data = AgentInput(
        message_id="test-123",
        raw_text="hello",
        user=UserContext(phone_hash="dummy"),
        intent="greeting", # Simulating classifier output
        entities={}
    )
    try:
        response = await agent.handle(input_data)
        print(f"Final Output: {response.response_text}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
