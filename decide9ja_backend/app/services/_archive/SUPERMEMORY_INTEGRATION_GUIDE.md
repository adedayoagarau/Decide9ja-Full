"""
SUPERMEMORY INTEGRATION GUIDE for Decide9ja (Old Tade)

Goal: Replace custom memory with Supermemory for 1-month learning period.
"""

# STEP 1: Add Supermemory to requirements.txt
"""
Add to /Volumes/Admin/Decide9ja/decide9ja_backend/requirements.txt:

httpx>=0.24.0
"""

# STEP 2: Copy supermemory_integration.py to services
"""
Copy:
/Volumes/Admin/Decide9ja/decide9ja_backend/app/services/supermemory_integration.py
"""

# STEP 3: Update message_handler_v4.py imports
"""
Add to imports:

from app.services.supermemory_integration import (
    TadeSupermemory,
    enhance_tade_with_supermemory,
    get_supermemory_context,
    migrate_user_to_supermemory
)
"""

# STEP 4: Initialize Supermemory in handle_message
"""
In app/services/message_handler_v4.py, at the top level:

# Initialize Supermemory
tade_memory = TadeSupermemory()

# Or lazy initialization
_tade_memory = None

def get_tade_memory():
    global _tade_memory
    if _tade_memory is None:
        _tade_memory = TadeSupermemory()
    return _tade_memory
"""

# STEP 5: Modify handle_message to use Supermemory
"""
OLD (custom memory):
    # Save user message
    user_memory.save_message(phone, "user", text)
    
    # Load previous context
    context = user_memory.get_user_memory(phone)

NEW (Supermemory):
    # Get Supermemory context BEFORE processing
    supermemory_context = await get_supermemory_context(phone, text)
    
    # Build enhanced prompt with context
    if supermemory_context:
        system_prompt += f"\n\nPrevious conversation context:\n{supermemory_context}"
"""

# STEP 6: Store interaction AFTER responding
"""
OLD:
    # Send response
    await send_response(phone, response_text)
    
    # Save to custom memory
    user_memory.save_message(phone, "assistant", response_text)

NEW:
    # Send response
    await send_response(phone, response_text)
    
    # Store in Supermemory with metadata
    await enhance_tade_with_supermemory(
        phone=phone,
        user_message=text,
        tade_response=response_text,
        metadata={
            "location": user_state.state,
            "lga": user_state.lga,
            "query_type": intent,
            "tools_used": tools_used,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
"""

# STEP 7: Migration for existing users (one-time)
"""
Add migration check:

async def handle_message(phone: str, text: str, ...):
    # Check if user needs migration
    user_state = await _get_state_async(phone)
    
    if user_state and not user_state.get("supermemory_migrated"):
        # Get old history
        history = user_memory.get_conversation_history(phone, limit=10)
        
        # Migrate to Supermemory
        await migrate_user_to_supermemory(phone, user_state, history)
        
        # Mark as migrated
        user_state.supermemory_migrated = True
        await _save_state_async(user_state)
        
        logger.info(f"Migrated user {phone} to Supermemory")
"""

# STEP 8: Update progressive profiling
"""
When collecting location:

OLD:
    user_state.state = identified_state
    user_state.lga = identified_lga

NEW:
    user_state.state = identified_state
    user_state.lga = identified_lga
    
    # Also store in Supermemory as fact
    await tade_memory.store_user_fact(
        phone,
        f"User is located in {identified_lga}, {identified_state}",
        "location"
    )
"""

# STEP 9: Use Supermemory for context compression recovery
"""
When detecting long gap:

    # Check if it's been a while
    last_active = user_state.last_active_at
    if last_active and (datetime.utcnow() - last_active).seconds > 600:
        # Get conversation summary from Supermemory
        summary = await tade_memory.get_conversation_summary(phone)
        
        if summary:
            response = f"Quick reminder — {summary}\n\n" + response
"""

# STEP 10: Graceful fallback
"""
If Supermemory fails, fall back to custom memory:

    try:
        await enhance_tade_with_supermemory(...)
    except Exception as e:
        logger.error(f"Supermemory failed, using fallback: {e}")
        # Fallback to old memory
        user_memory.save_message(phone, "user", text)
        user_memory.save_message(phone, "assistant", response)
"""

# COMPLETE UPDATED handle_message() EXAMPLE
"""
async def handle_message(phone: str, text: str, media_url: str = None) -> str:
    \"\"\"
    Enhanced handle_message with Supermemory integration.
    \"\"\"
    text = text.strip() if text else ""
    
    # Load states
    user_state = await _get_state_async(phone)
    
    # Check migration
    if user_state and not getattr(user_state, 'supermemory_migrated', False):
        history = user_memory.get_conversation_history(phone, limit=10)
        await migrate_user_to_supermemory(phone, user_state, history)
        user_state.supermemory_migrated = True
        await _save_state_async(user_state)
    
    # Get Supermemory context
    supermemory_context = ""
    try:
        supermemory_context = await get_supermemory_context(phone, text)
    except Exception as e:
        logger.warning(f"Could not get Supermemory context: {e}")
    
    # Build system prompt with context
    system_prompt = build_tade_system_prompt()
    if supermemory_context:
        system_prompt += f"\n\nPrevious conversation context:\n{supermemory_context}"
    
    # ... rest of processing (Claude understanding, retrieval, etc.) ...
    
    # Generate response
    response = await generate_response(system_prompt, text, user_state)
    
    # Send response
    await send_whatsapp_message(phone, response)
    
    # Store in Supermemory
    try:
        await enhance_tade_with_supermemory(
            phone=phone,
            user_message=text,
            tade_response=response,
            metadata={
                "location": user_state.state if user_state else None,
                "lga": user_state.lga if user_state else None,
                "query_type": getattr(intent, 'value', 'general'),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Failed to store in Supermemory: {e}")
        # Fallback
        user_memory.save_message(phone, "user", text)
        user_memory.save_message(phone, "assistant", response)
    
    return response
"""

# TESTING CHECKLIST
"""
Before deploying:

[ ] Supermemory API key is set in environment
[ ] httpx is installed
[ ] supermemory_integration.py is in services/
[ ] handle_message imports the integration
[ ] Migration logic handles existing users
[ ] Fallback works if Supermemory fails
[ ] Context is properly retrieved and added to prompts
[ ] Interactions are stored with metadata

Test scenarios:
1. New user conversation
2. Returning user (should recall context)
3. Long gap (should show recovery message)
4. Supermemory failure (should fallback gracefully)
"""

# MONITORING FOR 1-MONTH PERIOD
"""
Track these metrics:

1. Store success rate
   - Log: "Stored interaction for {phone}: {success}"
   
2. Recall relevance
   - After each recall, log relevance scores
   - Track if context actually helps responses
   
3. User satisfaction
   - Are conversations smoother?
   - Fewer "which state are you in?" repeats?
   
4. Cost
   - Supermemory API calls per day
   - Compare to custom memory costs

5. Latency
   - Time for store operations
   - Time for recall operations

After 1 month, decision:
- If effective: Build similar system (semantic search + auto-profiling)
- If not effective: Different architecture (maybe simpler rule-based)

Weekly reports:
- Store/Recall counts
- Average relevance scores
- User feedback (if available)
- Cost analysis
"""
