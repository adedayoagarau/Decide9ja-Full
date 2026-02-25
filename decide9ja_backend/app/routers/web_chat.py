"""
Web Chat API Router
====================
Provides a REST API for the web-based chat interface.
Uses the same orchestrator as WhatsApp, so responses are identical.
"""

import hashlib
import logging
import time
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Web Chat"])


# ─── Models ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User message")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    user_name: Optional[str] = Field(None, description="Optional user name")
    state: Optional[str] = Field(None, description="Nigerian state for context")


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    tools_used: Optional[List[str]] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    tools_used: List[str] = []
    response_time_ms: int


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: List[ChatMessage]
    message_count: int


# ─── In-Memory Session Store ────────────────────────────────────────

_sessions: Dict[str, List[Dict]] = {}


def _get_or_create_session(session_id: Optional[str]) -> str:
    """Get existing session or create a new one."""
    if session_id and session_id in _sessions:
        return session_id
    new_id = hashlib.sha256(f"web_{datetime.utcnow().isoformat()}_{id(object())}".encode()).hexdigest()[:16]
    _sessions[new_id] = []
    return new_id


# ─── Endpoints ──────────────────────────────────────────────────────

@router.post("/send", response_model=ChatResponse)
async def send_message(body: ChatRequest):
    """
    Send a message and get Tade's response.
    Uses the same ConversationalOrchestratorAgent as WhatsApp.
    """
    start_time = time.time()
    session_id = _get_or_create_session(body.session_id)

    # Security: basic injection check
    from app.services.prompt_guard import detect_prompt_injection
    if detect_prompt_injection(body.message):
        return ChatResponse(
            response="I can only answer questions about Nigerian politics and governance. Ask me something real!",
            session_id=session_id,
            tools_used=[],
            response_time_ms=0
        )

    try:
        # Build a mock AgentInput to pass through the orchestrator
        from app.agents.base import AgentInput
        from app.agents.registry import registry

        # Create a pseudo user_id from session
        user_id = f"web_{session_id}"

        class WebUser:
            phone_hash = user_id
            name = body.user_name or "there"
            first_name = body.user_name
            state = body.state
            lga = None

        agent_input = AgentInput(
            message_id=f"web_{int(time.time())}",
            raw_text=body.message,
            timestamp=datetime.utcnow().isoformat(),
            user=WebUser(),
            entities={},
            context={"source": "web_chat", "session_id": session_id}
        )

        # Get orchestrator and run
        orchestrator = registry.get("conversational_orchestrator")
        if not orchestrator:
            raise HTTPException(status_code=500, detail="Orchestrator not available")

        output = await orchestrator.handle(agent_input)

        response_text = output.response_text or "I couldn't process that. Try again?"
        tools_used = []
        if output.data and isinstance(output.data, dict):
            tools_used = output.data.get("tools_called", [])

        # Store in session history
        _sessions[session_id].append({
            "role": "user",
            "content": body.message,
            "timestamp": datetime.utcnow().isoformat()
        })
        _sessions[session_id].append({
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.utcnow().isoformat(),
            "tools_used": tools_used
        })

        # Also log to DB for learning
        try:
            from app.database import SessionLocal, Interaction
            db = SessionLocal()
            interaction = Interaction(
                user_id=user_id,
                query=body.message[:500],
                response=response_text[:2000],
                response_time_ms=int((time.time() - start_time) * 1000)
            )
            db.add(interaction)
            db.commit()
            db.close()
        except Exception:
            pass

        return ChatResponse(
            response=response_text,
            session_id=session_id,
            tools_used=tools_used,
            response_time_ms=int((time.time() - start_time) * 1000)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Web chat error: {e}")
        return ChatResponse(
            response="Something went wrong on my end. Try again?",
            session_id=session_id,
            tools_used=[],
            response_time_ms=int((time.time() - start_time) * 1000)
        )


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(session_id: str):
    """Get conversation history for a session."""
    messages = _sessions.get(session_id, [])
    return ChatHistoryResponse(
        session_id=session_id,
        messages=[ChatMessage(**m) for m in messages],
        message_count=len(messages)
    )


@router.post("/new-session")
async def create_new_session():
    """Create a new chat session."""
    session_id = _get_or_create_session(None)
    return {"session_id": session_id}
