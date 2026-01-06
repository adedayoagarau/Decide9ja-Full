"""
Chatbot Enhancement API Router for Decide9ja.

Provides endpoints for:
- Daily Briefing
- Quiz Mode
- Guided Exploration
- ELI5 (Explain Like I'm 5)
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

router = APIRouter(prefix="/api/chatbot", tags=["chatbot"])


# =============================================================================
# Request/Response Models
# =============================================================================

class StartQuizRequest(BaseModel):
    """Request to start a quiz."""
    phone_hash: str = Field(..., description="User's phone hash")
    category: str = Field("general", description="Quiz category")
    num_questions: int = Field(5, ge=3, le=10)


class AnswerQuizRequest(BaseModel):
    """Request to answer a quiz question."""
    phone_hash: str = Field(..., description="User's phone hash")
    answer: int = Field(..., ge=0, le=3, description="Answer index (0-3)")


class StartExplorationRequest(BaseModel):
    """Request to start guided exploration."""
    phone_hash: str = Field(..., description="User's phone hash")
    topic: str = Field(..., description="Exploration topic ID")


# =============================================================================
# Daily Briefing Endpoints
# =============================================================================

@router.get("/briefing/{phone_hash}")
async def get_daily_briefing(phone_hash: str) -> Dict[str, Any]:
    """
    Get personalized daily briefing for a user.

    Includes:
    - Relevant news
    - Updates on followed politicians
    - Active issues in user's state
    - Election countdown
    """
    from app.services.chatbot_enhancements import (
        get_daily_briefing as get_briefing,
        format_briefing_for_whatsapp
    )

    briefing = get_briefing(phone_hash)

    return {
        "greeting": briefing.greeting,
        "date": briefing.date,
        "items": [
            {
                "category": item.category,
                "title": item.title,
                "summary": item.summary,
                "relevance": item.relevance,
                "action": item.action
            }
            for item in briefing.items
        ],
        "quick_stats": briefing.quick_stats,
        "suggested_questions": briefing.suggested_questions,
        "formatted_whatsapp": format_briefing_for_whatsapp(briefing)
    }


# =============================================================================
# Quiz Mode Endpoints
# =============================================================================

@router.get("/quiz/categories")
async def get_quiz_categories() -> Dict[str, Any]:
    """
    Get available quiz categories.
    """
    from app.services.chatbot_enhancements import QUIZ_QUESTIONS

    categories = []
    for cat_id, questions in QUIZ_QUESTIONS.items():
        categories.append({
            "id": cat_id,
            "name": cat_id.replace("_", " ").title(),
            "question_count": len(questions)
        })

    return {"categories": categories}


@router.post("/quiz/start")
async def start_quiz(request: StartQuizRequest) -> Dict[str, Any]:
    """
    Start a new quiz session.
    """
    from app.services.chatbot_enhancements import (
        start_quiz as do_start_quiz,
        format_quiz_for_whatsapp
    )

    result = do_start_quiz(
        phone_hash=request.phone_hash,
        category=request.category,
        num_questions=request.num_questions
    )

    return {
        **result,
        "formatted_whatsapp": format_quiz_for_whatsapp(result)
    }


@router.post("/quiz/answer")
async def answer_quiz(request: AnswerQuizRequest) -> Dict[str, Any]:
    """
    Submit answer for current quiz question.
    """
    from app.services.chatbot_enhancements import (
        answer_quiz as do_answer,
        format_quiz_for_whatsapp
    )

    result = do_answer(request.phone_hash, request.answer)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        **result,
        "formatted_whatsapp": format_quiz_for_whatsapp(result)
    }


@router.get("/quiz/status/{phone_hash}")
async def get_quiz_status(phone_hash: str) -> Dict[str, Any]:
    """
    Get current quiz session status.
    """
    from app.services.chatbot_enhancements import _quiz_sessions

    session = _quiz_sessions.get(phone_hash)

    if not session:
        return {"active": False}

    return {
        "active": True,
        "session_id": session.session_id,
        "category": session.category,
        "current_question": session.current_index + 1,
        "total_questions": len(session.questions),
        "current_score": session.score,
        "completed": session.completed
    }


# =============================================================================
# Guided Exploration Endpoints
# =============================================================================

@router.get("/explore/topics")
async def get_exploration_topics() -> Dict[str, Any]:
    """
    Get available exploration topics.
    """
    from app.services.chatbot_enhancements import get_available_explorations

    return {"topics": get_available_explorations()}


@router.post("/explore/start")
async def start_exploration(request: StartExplorationRequest) -> Dict[str, Any]:
    """
    Start a guided exploration on a topic.
    """
    from app.services.chatbot_enhancements import (
        start_exploration as do_start,
        format_exploration_for_whatsapp
    )

    result = do_start(request.phone_hash, request.topic)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        **result,
        "formatted_whatsapp": format_exploration_for_whatsapp(result)
    }


@router.post("/explore/next/{phone_hash}")
async def continue_exploration(phone_hash: str) -> Dict[str, Any]:
    """
    Continue to next step in exploration.
    """
    from app.services.chatbot_enhancements import (
        continue_exploration as do_continue,
        format_exploration_for_whatsapp
    )

    result = do_continue(phone_hash)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        **result,
        "formatted_whatsapp": format_exploration_for_whatsapp(result)
    }


@router.get("/explore/status/{phone_hash}")
async def get_exploration_status(phone_hash: str) -> Dict[str, Any]:
    """
    Get current exploration session status.
    """
    from app.services.chatbot_enhancements import (
        _exploration_sessions,
        EXPLORATION_PATHS
    )

    session = _exploration_sessions.get(phone_hash)

    if not session:
        return {"active": False}

    exploration = EXPLORATION_PATHS.get(session["topic"])

    return {
        "active": True,
        "topic": session["topic"],
        "topic_title": exploration.topic if exploration else session["topic"],
        "current_step": session["current_step"] + 1,
        "total_steps": exploration.total_steps if exploration else 0
    }


# =============================================================================
# ELI5 (Explain Like I'm 5) Endpoints
# =============================================================================

@router.get("/eli5/{topic}")
async def get_eli5_explanation(topic: str) -> Dict[str, Any]:
    """
    Get an ELI5 (Explain Like I'm 5) explanation for a topic.

    Uses simple language and relatable analogies.
    """
    from app.services.chatbot_enhancements import (
        explain_eli5,
        format_eli5_for_whatsapp
    )

    result = explain_eli5(topic)

    return {
        **result,
        "formatted_whatsapp": format_eli5_for_whatsapp(result)
    }


@router.get("/eli5")
async def list_eli5_topics() -> Dict[str, Any]:
    """
    Get list of topics available for ELI5 explanations.
    """
    from app.services.chatbot_enhancements import ELI5_TEMPLATES

    topics = []
    for topic_id, template in ELI5_TEMPLATES.items():
        topics.append({
            "id": topic_id,
            "title": template["title"],
            "terms_explained": len(template["simple_terms"])
        })

    return {"topics": topics}


# =============================================================================
# Status Endpoint
# =============================================================================

@router.get("/status")
async def get_enhancement_status() -> Dict[str, Any]:
    """
    Get status of chatbot enhancement features.
    """
    from app.services.chatbot_enhancements import get_chatbot_enhancement_status

    return get_chatbot_enhancement_status()
