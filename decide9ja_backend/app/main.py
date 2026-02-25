"""
Decide9ja RAG Backend - FastAPI Application (SECURITY HARDENED)
Main entry point with /health, /ask, and /webhook endpoints.
"""
import os
import re
import time
import html
import logging
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.database import get_db, init_db, Document, Interaction
from app.routers import webhook as webhook_router
from app.routers import voice as voice_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = ENVIRONMENT == "development"

# Initialize FastAPI app
app = FastAPI(
    title="Decide9ja RAG Backend",
    description="Political intelligence API for Nigerian voters",
    version="1.0.0",
    docs_url="/docs" if DEBUG else None,  # Disable Swagger in production
    redoc_url="/redoc" if DEBUG else None
)

# ===========================================
# SECURITY: Rate Limiting
# ===========================================
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    RATE_LIMITING_ENABLED = True
except ImportError:
    logger.warning("SlowAPI not installed - rate limiting disabled")
    RATE_LIMITING_ENABLED = False
    # Dummy decorator
    class DummyLimiter:
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    limiter = DummyLimiter()

# ===========================================
# SECURITY: CORS Configuration
# ===========================================
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
if ENVIRONMENT == "production" and "*" in ALLOWED_ORIGINS:
    logger.warning("⚠️ CORS allows all origins in production! Set ALLOWED_ORIGINS env var.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# ===========================================
# STATIC FILES (Dashboard)
# ===========================================
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info(f"📁 Static files mounted at /static")
else:
    logger.warning(f"⚠️ Static directory not found: {static_dir}")

# ===========================================
# SECURITY: Input Validation & Sanitization
# ===========================================

def sanitize_input(text: str) -> str:
    """Remove potentially dangerous characters from input."""
    if not text:
        return ""
    # Remove null bytes, control characters
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text.strip()


# Import LLM-based prompt guard (replaces regex-based detection)
from app.services.prompt_guard import detect_prompt_injection


def escape_xml(text: str) -> str:
    """Escape text for safe XML/TwiML output."""
    return html.escape(text, quote=True)


# ===========================================
# SCHEMAS with Validation
# ===========================================

class AskRequest(BaseModel):
    query: str
    state: Optional[str] = None
    conversation_id: Optional[str] = None
    
    @field_validator('query')
    @classmethod
    def validate_query(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Query cannot be empty")
        if len(v) > 500:
            raise ValueError("Query too long (max 500 characters)")
        return sanitize_input(v)
    
    @field_validator('state')
    @classmethod
    def validate_state(cls, v):
        if v is None:
            return v
        if len(v) > 50:
            raise ValueError("State name too long")
        # Only allow alphanumeric, spaces, hyphens
        if not re.match(r'^[a-zA-Z\s\-]+$', v):
            raise ValueError("Invalid state name format")
        return sanitize_input(v)


class AskResponse(BaseModel):
    response: str
    sources: list
    response_time_ms: int


class HealthResponse(BaseModel):
    status: str
    database_connected: bool
    document_count: int
    politician_count: int
    timestamp: str


class LocationRequest(BaseModel):
    """Request for location processing."""
    latitude: float
    longitude: float
    
    @field_validator('latitude')
    @classmethod
    def validate_latitude(cls, v):
        if not -90 <= v <= 90:
            raise ValueError("Invalid latitude (must be -90 to 90)")
        return v
    
    @field_validator('longitude')
    @classmethod
    def validate_longitude(cls, v):
        if not -180 <= v <= 180:
            raise ValueError("Invalid longitude (must be -180 to 180)")
        return v


class LocationResponse(BaseModel):
    """Response for location processing."""
    success: bool
    address: Optional[dict] = None
    classification: Optional[dict] = None
    coordinates: Optional[dict] = None
    error: Optional[str] = None
    formatted_message: Optional[str] = None


# ===========================================
# ROUTER INCLUDES (at module level, before startup)
# ===========================================

# Core routers (imported at top of file)
app.include_router(webhook_router.router, prefix="/api", tags=["WhatsApp"])
app.include_router(voice_router.router, tags=["Voice"])

# Additional routers
# Note: Twilio webhook is now handled in routers/webhook.py at /api/webhook/twilio

from app.routers import issues as issues_router
app.include_router(issues_router.router, tags=["Issues"])
app.include_router(issues_router.admin_router, tags=["Admin"])

from app.routers import admin as admin_router
app.include_router(admin_router.router, tags=["Admin"])

from app.api import election_analytics
app.include_router(election_analytics.router, tags=["Election Analytics"])

from app.routers import notifications as notifications_router
app.include_router(notifications_router.router, tags=["Notifications"])

from app.routers import comparison as comparison_router
app.include_router(comparison_router.router, tags=["Comparison"])

from app.routers import scheduler_status as scheduler_router
app.include_router(scheduler_router.router, tags=["Scheduler"])

from app.routers import bills as bills_router
app.include_router(bills_router.router, tags=["Bills"])

from app.routers import personalization as personalization_router
app.include_router(personalization_router.router, tags=["Personalization"])

from app.routers import election_2027 as election_2027_router
app.include_router(election_2027_router.router, tags=["Election 2027"])

from app.routers import chatbot as chatbot_router
app.include_router(chatbot_router.router, tags=["Chatbot"])

from app.routers import search as search_router
app.include_router(search_router.router, tags=["Search"])

from app.routers import broadcast as broadcast_router
app.include_router(broadcast_router.router, tags=["Broadcast"])

from app.routers import constituency as constituency_router
app.include_router(constituency_router.router, tags=["Constituency"])

from app.routers import auth as auth_router
app.include_router(auth_router.router, tags=["Authentication"])

from app.routers import media as media_router
app.include_router(media_router.router, tags=["Media"])

from app.routers import localization as localization_router
app.include_router(localization_router.router, tags=["Localization"])

from app.routers import pipeline as pipeline_router
app.include_router(pipeline_router.router, tags=["Data Pipeline"])

from app.routers import dashboard as dashboard_router
app.include_router(dashboard_router.router, tags=["Dashboard"])

from app.routers import performance as performance_router
app.include_router(performance_router.router, tags=["Performance"])

from app.routers import budget as budget_router
app.include_router(budget_router.router, tags=["Budget"])

from app.routers import catalog as catalog_router
app.include_router(catalog_router.router, tags=["Catalog"])

logger.info("✅ All routers registered")


# ===========================================
# STARTUP (non-blocking — /health works immediately)
# ===========================================

async def _init_db_background():
    """Initialize DB in background so startup doesn't block."""
    import asyncio
    await asyncio.sleep(0)  # yield to event loop first
    try:
        init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.warning(f"⚠️ Database init failed (non-fatal): {e}")
        logger.warning("   App running without DB — check DATABASE_URL")

    # Initialize v2 learning tables (agent_feedback, agent_knowledge_gaps, query_patterns)
    try:
        from app.database_v2 import init_db_v2
        init_db_v2()
        logger.info("✅ Learning tables initialized (v2)")
    except Exception as e:
        logger.warning(f"⚠️ Learning tables init skipped (non-fatal): {e}")

    # Start background scheduler
    try:
        from app.scheduler_unified import start_scheduler
        start_scheduler()
        logger.info("📅 Background scheduler started")
    except Exception as e:
        logger.warning(f"⚠️ Scheduler startup failed (non-critical): {e}")


@app.on_event("startup")
async def startup_event():
    """Fire-and-forget: DB init + scheduler run in background."""
    import asyncio
    asyncio.create_task(_init_db_background())
    logger.info("🚀 Decide9ja Backend started — DB init running in background")




# ===========================================
# ENDPOINTS
# ===========================================

@app.get("/", response_model=dict)
async def root():
    """Root endpoint."""
    return {
        "name": "Decide9ja RAG Backend",
        "version": "1.0.0",
        "endpoints": ["/health", "/ask", "/search", "/location", "/webhook"]
    }


@app.get("/health")
async def health_check():
    """Lightweight health check for Railway."""
    return {"status": "ok"}


@app.get("/api/learning/stats")
async def learning_stats():
    """See what Tade is learning from conversations."""
    try:
        from app.services.learning_service import get_learning_service
        service = get_learning_service()
        stats = service.get_learning_stats()
        return {"status": "ok", "learning": stats}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/health/detailed", response_model=HealthResponse)
@limiter.limit("5/minute")
async def health_check_detailed(request: Request, db: Session = Depends(get_db)):
    """
    Detailed health check with database stats.
    Use this for debugging, not for load balancer checks.
    """
    try:
        doc_count = db.query(Document).count()
        from app.database import Politician
        pol_count = db.query(Politician).count()
        
        return HealthResponse(
            status="healthy",
            database_connected=True,
            document_count=doc_count,
            politician_count=pol_count,
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            database_connected=False,
            document_count=0,
            politician_count=0,
            timestamp=datetime.utcnow().isoformat()
        )


@app.post("/location", response_model=LocationResponse)
@limiter.limit("100/minute")
async def process_location(request: Request, body: LocationRequest):
    """
    Process location coordinates for issue reporting.
    Returns address, road classification, and responsible authority.
    """
    from app.services.location import process_location_for_report, format_location_response
    
    try:
        result = await process_location_for_report(
            latitude=body.latitude,
            longitude=body.longitude
        )
        
        formatted_msg = format_location_response(result) if result.get("success") else None
        
        return LocationResponse(
            success=result.get("success", False),
            address=result.get("address"),
            classification=result.get("classification"),
            coordinates=result.get("coordinates"),
            error=result.get("error"),
            formatted_message=formatted_msg
        )
    except Exception as e:
        logger.error(f"Location processing error: {e}")
        return LocationResponse(
            success=False,
            error="Failed to process location. Please type your address manually."
        )


@app.post("/ask", response_model=AskResponse)
@limiter.limit("100/minute")
async def ask_question(request: Request, body: AskRequest, db: Session = Depends(get_db)):
    """
    Main query endpoint.
    Uses RAG to retrieve context and Claude to generate response.
    """
    start_time = time.time()
    
    # SECURITY: Check for prompt injection
    if detect_prompt_injection(body.query):
        logger.warning(f"Prompt injection attempt detected: {body.query[:100]}")
        return AskResponse(
            response="I can only answer questions about Nigerian politics and elections. Please ask a genuine question.",
            sources=[],
            response_time_ms=0
        )
    
    # Import here to avoid circular imports
    from app.services.rag_router import RAGRouter
    
    # Initialize RAG Router
    router = RAGRouter(db)
    
    # Build filters from request
    filters = {}
    if body.state:
        filters["state"] = body.state
    
    try:
        # Route query to appropriate handler
        # This handles retrieval, context building, and answer synthesis
        result = await router.route(
            query=body.query,
            filters=filters
        )
        
        response_text = result.get("response", "I'm having trouble finding that information.")
        sources = result.get("sources", [])
        context = result.get("context", "")
        
        # Log the intent for debugging
        logger.info(f"Query routed as: {result.get('intent')}")
        
    except Exception as e:
        logger.error(f"Router error: {e}")
        response_text = "I encountered an error while processing your request. Please try again."
        sources = []
    
    # Calculate response time
    response_time = int((time.time() - start_time) * 1000)
    
    # Log interaction (with truncation for safety)
    try:
        interaction = Interaction(
            query=body.query[:500],
            response=response_text[:2000],
            context_used=context[:500],
            response_time_ms=response_time
        )
        db.add(interaction)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log interaction: {e}")
    
    return AskResponse(
        response=response_text,
        sources=sources,
        response_time_ms=response_time
    )


class SearchResponse(BaseModel):
    """Response for web-enabled search."""
    response: str
    sources: list
    used_web_search: bool
    response_time_ms: int


@app.post("/search", response_model=SearchResponse)
@limiter.limit("50/minute")
async def search_with_web(request: Request, body: AskRequest, db: Session = Depends(get_db)):
    """
    Web-enabled search endpoint.
    First searches database, then falls back to web if confidence is low.
    """
    start_time = time.time()
    
    # SECURITY: Check for prompt injection
    if detect_prompt_injection(body.query):
        logger.warning(f"Prompt injection attempt in search: {body.query[:100]}")
        return SearchResponse(
            response="I can only answer questions about Nigerian politics and elections.",
            sources=[],
            used_web_search=False,
            response_time_ms=0
        )
    
    # Import hybrid retrieval
    from app.services.rag import retrieve_with_web_fallback
    from app.services.llm import generate_response_sync
    
    # Build filters
    filters = {}
    if body.state:
        filters["state"] = body.state
    
    # Hybrid retrieval (DB + web fallback)
    context, sources, used_web = await retrieve_with_web_fallback(
        db=db,
        query=body.query,
        top_k=5,
        filters=filters if filters else None
    )
    
    # Generate response
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        try:
            response_text = generate_response_sync(
                user_message=body.query,
                context=context
            )
        except Exception as e:
            logger.error(f"LLM error in search: {e}")
            response_text = "I'm having trouble processing your request."
    else:
        response_text = f"[API Key not configured]\n\n{context}"
    
    # Calculate response time
    response_time = int((time.time() - start_time) * 1000)
    
    # Log interaction
    try:
        interaction = Interaction(
            query=body.query[:500],
            response=response_text[:2000],
            context_used=f"[web={used_web}] {context[:400]}",
            response_time_ms=response_time
        )
        db.add(interaction)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log search interaction: {e}")
    
    return SearchResponse(
        response=response_text,
        sources=sources,
        used_web_search=used_web,
        response_time_ms=response_time
    )


# Note: WhatsApp webhook endpoints moved to routers/webhook.py
# Meta Cloud API: POST /api/webhook
# Twilio: POST /api/webhook/twilio


# ===========================================
# DEBUG ENDPOINTS (disabled in production)
# ===========================================

if DEBUG:
    @app.get("/debug/documents")
    async def list_documents(db: Session = Depends(get_db), limit: int = 10):
        """Debug: List documents in database. DISABLED IN PRODUCTION."""
        if limit > 100:
            limit = 100
        docs = db.query(Document).limit(limit).all()
        return [
            {
                "id": d.id,
                "doc_type": d.doc_type,
                "title": d.title,
                "state": d.state,
                "party": d.party
            }
            for d in docs
        ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
