"""
Tade Enhancement Integration Guide

How to integrate Working Memory and Error Recovery into existing Tade.
"""

# STEP 1: Copy new modules to services directory
# Files to copy:
# - working_memory_enhanced.py
# - error_recovery_enhanced.py
# - location_matcher.py (if created)

# STEP 2: Update imports in message_handler_v4.py
"""
Add to imports:

from app.services.working_memory_enhanced import (
    WorkingMemory, 
    ConversationStage, 
    QueryType,
    handle_stage_transition
)
from app.services.error_recovery_enhanced import (
    ErrorRecoveryHandler,
    handle_error
)
"""

# STEP 3: Load working memory alongside UserState
"""
In handle_message():

async def handle_message(phone: str, text: str, ...):
    # Load user state (existing)
    user_state = await _get_state_async(phone)
    
    # NEW: Load working memory
    working_memory = await get_working_memory(phone)
    if not working_memory:
        working_memory = WorkingMemory(user_phone=phone)
    
    # ... rest of handling
"""

# STEP 4: Replace flow-based routing with stage-based
"""
OLD (flow-based):
    if state.flow == ConversationFlow.IDLE:
        # Handle idle
    elif state.flow == ConversationFlow.ONBOARDING:
        # Handle onboarding

NEW (stage-based):
    response = handle_stage_transition(
        working_memory, 
        text, 
        intent, 
        user_state
    )
    
    if response == "__TRIGGER_RETRIEVAL__":
        # Do retrieval
        pass
    elif response == "__FORMULATE_RESPONSE__":
        # Format response
        pass
    else:
        # Return response directly
        return response
"""

# STEP 5: Add working memory persistence
"""
Create helper functions:

async def get_working_memory(phone: str) -> Optional[WorkingMemory]:
    '''Load from Redis/SQLite'''
    # Try Redis first (fast)
    data = await redis.get(f"working_memory:{phone}")
    if data:
        return WorkingMemory.from_dict(json.loads(data))
    
    # Fallback to SQLite
    db = get_db()
    try:
        record = db.query(WorkingMemoryTable).filter_by(phone=phone).first()
        if record:
            return WorkingMemory.from_dict(json.loads(record.data))
    finally:
        db.close()
    
    return None

async def save_working_memory(memory: WorkingMemory):
    '''Save to Redis and SQLite'''
    data = memory.to_dict()
    
    # Save to Redis (30 min TTL)
    await redis.setex(
        f"working_memory:{memory.user_phone}",
        1800,  # 30 minutes
        json.dumps(data)
    )
    
    # Save to SQLite (persistent)
    db = get_db()
    try:
        record = db.query(WorkingMemoryTable).filter_by(phone=memory.user_phone).first()
        if record:
            record.data = json.dumps(data)
            record.updated_at = datetime.utcnow()
        else:
            record = WorkingMemoryTable(
                phone=memory.user_phone,
                data=json.dumps(data),
                created_at=datetime.utcnow()
            )
            db.add(record)
        db.commit()
    finally:
        db.close()
"""

# STEP 6: Update error handling
"""
OLD:
    except Exception as e:
        logger.error(f"Error: {e}")
        return "Sorry, I don't understand"

NEW:
    except Exception as e:
        logger.error(f"Error: {e}")
        working_memory.record_error(str(e))
        
        # Use enhanced error recovery
        return handle_error("general_error", retry_count=working_memory.retry_count)
"""

# STEP 7: Add context compression recovery
"""
In message handler, detect compression:

# Check if context was lost (e.g., after long pause)
if (datetime.utcnow() - working_memory.last_activity).seconds > 600:  # 10 min gap
    recovery_context = working_memory.get_compression_recovery_context()
    response = recovery_context + response
"""

# STEP 8: Database migration (add WorkingMemory table)
"""
Migration script:

from sqlalchemy import Column, String, Text, DateTime
from app.database import Base

class WorkingMemoryTable(Base):
    __tablename__ = "working_memory"
    
    phone = Column(String(20), primary_key=True)
    data = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Run migration:
# alembic revision --autogenerate -m "Add working memory table"
# alembic upgrade head
"""

# STEP 9: Testing checklist
"""
Test these scenarios:

✅ New user flow
   - Greets properly
   - Collects location progressively
   - Remembers location across messages

✅ Returning user
   - Skips location collection
   - References previous conversations
   - Maintains context

✅ Error recovery
   - Ambiguous location → offers options
   - Vague query → gives menu
   - Multiple failures → escalates to menu

✅ Context compression
   - After long gap → reminds user of topic
   - After restart → loads previous state

✅ Stage transitions
   - Each stage transition logged
   - Recovery from any stage possible
   - Clear progression through conversation
"""

# STEP 10: Gradual rollout
"""
Rollout strategy:

Phase 1 (Week 1):
- Deploy to 10% of users
- Monitor error rates
- Collect feedback

Phase 2 (Week 2):
- Deploy to 50% of users
- A/B test vs old system
- Measure completion rates

Phase 3 (Week 3):
- Deploy to 100% of users
- Monitor closely
- Have rollback plan ready
"""

# COMPLETE INTEGRATION EXAMPLE
"""
Full updated handle_message():

async def handle_message(phone: str, text: str, media_url: str = None) -> str:
    # Load states
    user_state = await _get_state_async(phone)
    working_memory = await get_working_memory(phone) or WorkingMemory(user_phone=phone)
    
    # Check for context compression
    if is_context_compression(working_memory):
        recovery_msg = working_memory.get_compression_recovery_context()
    else:
        recovery_msg = ""
    
    try:
        # Stage-based handling
        response = handle_stage_transition(
            working_memory, text, 
            detect_intent(text), user_state
        )
        
        # Handle special signals
        if response == "__TRIGGER_RETRIEVAL__":
            data = await perform_retrieval(working_memory, user_state)
            working_memory.set_data_retrieved(data)
            response = format_response(data, working_memory)
        
        # Add recovery context if needed
        if recovery_msg:
            response = recovery_msg + response
        
        # Mark response sent
        working_memory.mark_response_sent()
        
    except Exception as e:
        logger.error(f"Error: {e}")
        working_memory.record_error(str(e))
        response = handle_error("general_error", retry_count=working_memory.retry_count)
    
    # Save working memory
    await save_working_memory(working_memory)
    
    return response
"""

# BENEFITS AFTER INTEGRATION
"""
✅ Better user experience
   - No dead ends
   - Clear progression
   - Helpful error recovery

✅ Easier debugging
   - Stage transitions logged
   - Error context preserved
   - Clear state visibility

✅ More maintainable
   - Explicit state machine
   - Modular handlers
   - Clear separation of concerns

✅ Better analytics
   - Track stage drop-offs
   - Measure error recovery success
   - Understand user journeys
"""
