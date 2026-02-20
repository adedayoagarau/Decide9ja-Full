import sys
import os
import asyncio
import logging

sys.path.append(os.getcwd())

from app.agents.base import AgentInput, UserContext
from app.agents.tier1_entry.classifier import ClassifierAgent
from app.agents.tier1_entry.router import RouterAgent
from app.agents.tier5_output.response_composer import ResponseComposerAgent
from app.agents.registry import get_agent

logging.basicConfig(level=logging.INFO)

async def run():
    print("Testing pipeline components directly...")
    
    from datetime import datetime
    input_data = AgentInput(
        message_id="test-123",
        raw_text="hello",
        timestamp=datetime.now(),
        user=UserContext(phone_hash="dummy")
    )
    
    print("\n--- 1. ClassifierAgent ---")
    classifier = ClassifierAgent()
    try:
        classifier_output = await classifier.handle(input_data)
        print(f"Classifier Success! Intent: {classifier_output.data.get('intent')}")
        input_data.intent = classifier_output.data.get("intent")
        input_data.entities = classifier_output.data.get("entities", {})
    except Exception as e:
        print(f"Classifier crashed!")
        import traceback
        traceback.print_exc()
        return

    print("\n--- 2. RouterAgent ---")
    router = RouterAgent()
    try:
        router_output = await router.handle(input_data)
        print(f"Router Success! Next Agent: {router_output.data.get('next_agent')}")
        next_agent_name = router_output.data.get('next_agent')
    except Exception as e:
        print(f"Router crashed!")
        import traceback
        traceback.print_exc()
        return
        
    print("\n--- 3. ResponseComposerAgent ---")
    composer = ResponseComposerAgent()
    try:
        composer_output = await composer.handle(input_data)
        print(f"Composer Success! Response: {composer_output.response_text}")
    except Exception as e:
        print(f"Composer crashed!")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
