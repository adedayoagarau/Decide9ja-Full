"""
LLM Service - Multi-Provider (Claude + OpenAI Fallback).
Generates responses grounded in RAG context with Tade persona.
"""
import os
import logging
import asyncio
from typing import List, Dict, Optional
from anthropic import Anthropic
from openai import OpenAI
from dotenv import load_dotenv

# Import Tade persona
from app.services.tade_persona import build_tade_prompt

load_dotenv()

logger = logging.getLogger(__name__)


def get_anthropic_client():
    """Get Anthropic client."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required.")
    return Anthropic(api_key=api_key)

def get_openai_client():
    """Get OpenAI client."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not found. Fallback will not work.")
        return None
    return OpenAI(api_key=api_key)


def build_prompt(
    context: str, 
    user_context: str = "", 
    conversation_context: str = "",
    current_date: str = None
) -> str:
    """Build the system prompt using Tade persona."""
    return build_tade_prompt(
        user_context=user_context,
        conversation_context=conversation_context,
        retrieved_context=context or "No relevant information found in database.",
        current_date=current_date
    )


async def generate_response(
    user_message: str,
    context: str,
    conversation_history: Optional[List[Dict]] = None,
    user_context: str = "",
    conversation_context: str = ""
) -> str:
    """
    Generate a response using Claude (Primary) with OpenAI fallback.
    """
    system = build_prompt(
        context=context, 
        user_context=user_context,
        conversation_context=conversation_context
    )
    
    messages = []
    if conversation_history:
        for msg in conversation_history[-6:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
    
    messages.append({
        "role": "user",
        "content": user_message
    })
    
    # 1. Try Claude (Primary)
    try:
        client = get_anthropic_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=612,
            system=system,
            messages=messages
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Claude API failed: {e}. Attempting fallback...")
        
    # 2. Try OpenAI (Fallback)
    try:
        client = get_openai_client()
        if not client:
            return "Server is busy. Please try again later. (No Fallback Configured)"
            
        logger.info("Using OpenAI fallback...")
        # Adapt messages for OpenAI (system msg is handled differently)
        openai_messages = [{"role": "system", "content": system}] + messages
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=openai_messages,
            max_tokens=512
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI Fallback failed: {e}")
        return "I'm having trouble connecting to the network right now. Please try again in a moment."


def generate_response_sync(
    user_message: str,
    context: str,
    user_context: str = "",
    conversation_context: str = ""
) -> str:
    """
    Synchronous version for Twilio/simpler use cases.
    Fixed to handle being called from existing async context.
    """
    try:
        # Check if we're already in an async context
        loop = asyncio.get_running_loop()
        # We're in async - use thread pool to avoid nested loop error
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(_run_in_new_loop, user_message, context, user_context, conversation_context)
            return future.result(timeout=30)
    except RuntimeError:
        # No running loop, safe to use asyncio.run
        return asyncio.run(generate_response(user_message, context, None, user_context, conversation_context))


def _run_in_new_loop(user_message: str, context: str, user_context: str, conversation_context: str) -> str:
    """Helper to run async function in a new event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            generate_response(user_message, context, None, user_context, conversation_context)
        )
    finally:
        loop.close()


def extract_politician_name(text: str) -> Optional[str]:
    """
    Extract politician name from response text.
    Used to track active entities.
    """
    import re
    
    # Common patterns for politician mentions
    patterns = [
        r"(?:Hon\.|Honorable|Senator|Governor|President|Minister)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        r"([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:is|has|was|represents)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    
    return None