"""
Enhanced Response Handler
Wraps the existing RAG response with optional orchestration for complex queries.
This is ADDITIVE - the original generate_rag_response is not modified.
"""
import logging
import os
from typing import Optional, Dict

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# Feature flag - can be disabled without code changes
ORCHESTRATION_ENABLED = os.getenv("ENABLE_ORCHESTRATION", "true").lower() == "true"


async def generate_enhanced_response(
    text: str,
    user_hash: str,
    conv_state: dict,
) -> str:
    """
    Enhanced response generator that uses orchestration for complex queries.
    Falls back to standard RAG for simple queries or if orchestration fails.
    
    Args:
        text: User's message
        user_hash: User identifier
        conv_state: Conversation state
        
    Returns:
        Formatted response string
    """
    from app.services.message_handler import generate_rag_response
    
    # Quick check - if orchestration disabled or query is simple, use original
    if not ORCHESTRATION_ENABLED or len(text.split()) < 6:
        return await generate_rag_response(text, user_hash, conv_state)
    
    try:
        from app.services.query_planner import plan_query_sync, is_complex_query
        from app.services.search_orchestrator import execute_plan_sync
        from app.services.llm import generate_response_sync
        from app.services.twilio_whatsapp import format_for_whatsapp
        from app.services import conversation
        
        # Quick heuristic check
        if not is_complex_query(text):
            return await generate_rag_response(text, user_hash, conv_state)
        
        # Get user context for planning
        user_profile = conversation.get_user_profile(user_hash)
        user_context = {
            "state": user_profile.get("state"),
            "lga": user_profile.get("lga"),
            "active_politician": conversation.get_active_politician(user_hash),
        }
        
        # Plan the query
        plan = plan_query_sync(text, user_context)
        
        # If not complex, fall back to standard RAG
        if not plan.is_complex or len(plan.subtasks) <= 1:
            return await generate_rag_response(text, user_hash, conv_state)
        
        logger.info(f"Using orchestration for complex query: {len(plan.subtasks)} subtasks")
        
        # Execute the plan
        result = execute_plan_sync(plan, user_context)
        
        # Generate response using combined context
        conv_context = conversation.get_conversation_context_string(user_hash)
        user_context_str = conversation.get_user_profile_string(user_hash)
        
        response = generate_response_sync(
            user_message=text,
            context=result.combined_context,
            user_context=user_context_str,
            conversation_context=conv_context
        )
        
        return format_for_whatsapp(response)
        
    except Exception as e:
        logger.warning(f"Orchestration failed, falling back to RAG: {e}")
        return await generate_rag_response(text, user_hash, conv_state)


def should_use_orchestration(text: str) -> bool:
    """Check if a query should use orchestration."""
    if not ORCHESTRATION_ENABLED:
        return False
    
    from app.services.query_planner import is_complex_query
    return is_complex_query(text)


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        # This would need a real user_hash and conv_state
        print("Enhanced handler module loaded successfully")
        print(f"Orchestration enabled: {ORCHESTRATION_ENABLED}")
    
    asyncio.run(test())
