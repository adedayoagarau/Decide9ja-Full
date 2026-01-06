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
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
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
# STARTUP
# ===========================================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()
    
    # Include WhatsApp webhook router
    app.include_router(webhook_router.router, prefix="/api", tags=["WhatsApp"])
    
    # Include Issues router
    from app.routers import issues as issues_router
    app.include_router(issues_router.router, tags=["Issues"])
    app.include_router(issues_router.admin_router, tags=["Admin"])
    
    # Include Admin router  
    from app.routers import admin as admin_router
    app.include_router(admin_router.router, tags=["Admin"])
    
    # Include Voice router (Twilio Voice AI)
    app.include_router(voice_router.router, tags=["Voice"])

    # Include Election 2027 Analytics API
    from app.api import election_analytics
    app.include_router(election_analytics.router, tags=["Election Analytics"])

    # Mount static files for admin dashboard
    import pathlib
    static_dir = pathlib.Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.info(f"   Static Files: /static")

    logger.info("✅ Decide9ja Backend Started")
    logger.info(f"   Environment: {ENVIRONMENT}")
    logger.info(f"   Rate Limiting: {RATE_LIMITING_ENABLED}")
    logger.info(f"   WhatsApp Webhook: /api/webhook")
    logger.info(f"   Voice Webhook: /voice/incoming")
    logger.info(f"   Issues API: /api/issues")
    logger.info(f"   Admin API: /api/admin")
    logger.info(f"   Election Analytics: /api/v1/election")


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


@app.get("/health", response_model=HealthResponse)
@limiter.limit("60/minute")
async def health_check(request: Request, db: Session = Depends(get_db)):
    """Health check endpoint with database stats."""
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
        logger.error(f"Health check failed: {e}")
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
    from app.services.rag import RAGService
    from app.services.llm import generate_response_sync
    
    # Initialize RAG service
    rag = RAGService(db)
    
    # Build filters from request (already validated by Pydantic)
    filters = {}
    if body.state:
        filters["state"] = body.state
    
    # Retrieve relevant context
    context, sources = rag.retrieve(
        query=body.query,
        top_k=5,
        filters=filters if filters else None
    )
    
    # Check if we have an API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if api_key:
        try:
            response_text = generate_response_sync(
                user_message=body.query,
                context=context
            )
        except Exception as e:
            logger.error(f"LLM error: {e}")
            response_text = "I'm having trouble processing your request. Please try again."
    else:
        # Fallback: return raw context if no API key
        response_text = f"[API Key not configured - Showing raw context]\n\n{context}"
    
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


@app.post("/webhook")
@limiter.limit("200/minute")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    """
    WhatsApp webhook endpoint (Twilio format).
    Receives incoming messages and returns TwiML response.
    Supports text and voice note messages.
    """
    try:
        # Parse form data (Twilio sends as form)
        form_data = await request.form()
        
        phone_from = str(form_data.get("From", ""))
        message_body = str(form_data.get("Body", ""))
        profile_name = str(form_data.get("ProfileName", "User"))
        num_media = int(form_data.get("NumMedia", 0))
        media_url = str(form_data.get("MediaUrl0", "")) if num_media > 0 else ""
        media_type = str(form_data.get("MediaContentType0", ""))
        
        # User identification
        from app.services.twilio_whatsapp import hash_phone
        user_hash = hash_phone(phone_from)
        
        # Use V4 Handler with Claude-First architecture
        from app.services.message_handler_v4 import handle_message
        
        # Handle incoming voice note
        if media_url and "audio" in media_type:
            logger.info(f"Incoming voice note from {user_hash}")
            from app.services import voice
            try:
                transcribed = await voice.speech_to_text(media_url)
                if transcribed:
                    message_body = transcribed
                    logger.info(f"Transcribed: {transcribed[:100]}...")
            except Exception as e:
                logger.error(f"Voice transcription error: {e}")
                return Response(
                    content="""<?xml version="1.0" encoding="UTF-8"?><Response><Message>Sorry, I couldn't understand that voice note. Please try again.</Message></Response>""",
                    media_type="application/xml"
                )
        
        if not message_body:
            logger.info(f"Empty message from {user_hash}")
            return {"status": "no message"}
        
        # SECURITY: Sanitize
        message_body = sanitize_input(message_body)[:1000]
        
        # Log for debugging
        logger.info(f"📨 Processing message from {user_hash[:8]}...: '{message_body[:50]}'")
        
        # Process message with V4 Claude-First handler
        response_text = await handle_message(phone_from, message_body, media_url)
        
        logger.info(f"📤 Response ready ({len(response_text)} chars): '{response_text[:80]}...'")
        
        # Regular text response (simplified - voice mode can be added later)
        safe_response = escape_xml(response_text[:1500])
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{safe_response}</Message>
</Response>"""
        
        return Response(content=twiml, media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return Response(
            content="""<?xml version="1.0" encoding="UTF-8"?><Response><Message>Sorry, an error occurred.</Message></Response>""",
            media_type="application/xml"
        )


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
