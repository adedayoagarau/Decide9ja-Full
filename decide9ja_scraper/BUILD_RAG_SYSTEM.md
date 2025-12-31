# DECIDE9JA - BUILD COMPLETE RAG SYSTEM
## Antigravity Mission: Production-Ready Political Intelligence Backend

---

# MASTER MISSION: Build Decide9ja RAG Backend

```
MISSION: Build Complete RAG-Powered Political Intelligence System

You are building Decide9ja, a WhatsApp-based political information chatbot for Nigerian voters. The system must:

1. Accept questions via WhatsApp webhook
2. Retrieve relevant information from a curated political database (RAG)
3. Generate accurate, sourced responses using Claude API
4. NEVER hallucinate - only answer from retrieved context
5. Log all interactions for analytics
6. Support citizen issue reporting with photos/location

## TECHNOLOGY STACK

- Backend: FastAPI (Python 3.11+)
- Database: PostgreSQL with pgvector extension
- Vector Embeddings: OpenAI text-embedding-3-small OR sentence-transformers (local)
- LLM: Claude API (Anthropic) - claude-sonnet-4-20250514
- WhatsApp: Twilio or Infobip webhook
- Image Storage: Cloudinary
- Cache: Redis (optional for MVP)
- Hosting: Railway, Render, or any Docker host

## PROJECT STRUCTURE

Create this exact structure:

```
decide9ja/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Environment configuration
│   ├── database.py             # PostgreSQL + pgvector connection
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── webhooks.py         # WhatsApp webhook handlers
│   │   ├── health.py           # Health check endpoints
│   │   └── admin.py            # Admin/dashboard endpoints
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── rag.py              # RAG retrieval engine
│   │   ├── llm.py              # Claude API integration
│   │   ├── embeddings.py       # Vector embedding service
│   │   ├── whatsapp.py         # WhatsApp message handling
│   │   ├── intent.py           # Intent classification
│   │   ├── reporting.py        # Citizen report handling
│   │   └── analytics.py        # Interaction logging
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py         # SQLAlchemy models
│   │   └── schemas.py          # Pydantic schemas
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── system.py           # System prompts
│   │   └── templates.py        # Response templates
│   │
│   └── utils/
│       ├── __init__.py
│       ├── phone.py            # Phone number hashing
│       └── location.py         # Geo utilities
│
├── data/
│   └── (political data JSON files go here)
│
├── scripts/
│   ├── seed_database.py        # Load JSON data into PostgreSQL
│   ├── generate_embeddings.py  # Create vector embeddings
│   └── test_rag.py             # Test retrieval quality
│
├── tests/
│   ├── test_rag.py
│   ├── test_webhook.py
│   └── test_intents.py
│
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## STEP 1: DATABASE SETUP (app/database.py)

```python
"""
PostgreSQL database with pgvector for semantic search.
"""
import os
from sqlalchemy import create_engine, Column, String, Text, Integer, Float, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import uuid

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ===========================================
# KNOWLEDGE BASE TABLES (for RAG)
# ===========================================

class Document(Base):
    """
    Stores all retrievable documents (candidates, parties, FAQs, etc.)
    Each document is chunked and embedded for semantic search.
    """
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_type = Column(String(50), nullable=False, index=True)  # candidate, party, faq, promise, etc.
    doc_id = Column(String(200), nullable=False, index=True)   # e.g., "tinubu_bola_ahmed"
    title = Column(String(500))
    content = Column(Text, nullable=False)                      # Full text content
    metadata = Column(JSONB)                                    # Structured data (JSON)
    embedding = Column(Vector(1536))                            # OpenAI embedding dimension
    
    # For filtering
    state = Column(String(50), index=True)
    party = Column(String(20), index=True)
    year = Column(Integer, index=True)
    category = Column(String(50), index=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Vector similarity search index
    __table_args__ = (
        Index('idx_documents_embedding', embedding, postgresql_using='ivfflat', postgresql_ops={'embedding': 'vector_cosine_ops'}),
    )


class Candidate(Base):
    """Structured candidate data for direct lookups."""
    __tablename__ = "candidates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(200), unique=True, nullable=False, index=True)
    name = Column(String(300), nullable=False)
    party_id = Column(String(20), ForeignKey("parties.abbreviation"))
    position_sought = Column(String(100))
    election_year = Column(Integer, index=True)
    state = Column(String(50), index=True)
    is_incumbent = Column(Boolean, default=False)
    data = Column(JSONB)  # Full candidate data
    
    party = relationship("Party", back_populates="candidates")
    positions = relationship("CandidatePosition", back_populates="candidate")


class Party(Base):
    """Political parties."""
    __tablename__ = "parties"
    
    abbreviation = Column(String(20), primary_key=True)
    name = Column(String(200), nullable=False)
    chairman = Column(String(200))
    data = Column(JSONB)
    
    candidates = relationship("Candidate", back_populates="party")


class CandidatePosition(Base):
    """Candidate policy positions with sources."""
    __tablename__ = "candidate_positions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"))
    issue_area = Column(String(50), nullable=False, index=True)
    stance = Column(Text)
    quotes = Column(JSONB)  # Array of {text, source, date, url}
    
    candidate = relationship("Candidate", back_populates="positions")


class FAQ(Base):
    """Frequently asked questions (voting process, etc.)."""
    __tablename__ = "faqs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(50), nullable=False, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    keywords = Column(ARRAY(String))
    embedding = Column(Vector(1536))


# ===========================================
# USER & INTERACTION TABLES
# ===========================================

class User(Base):
    """Users (phone hashed, never stored raw)."""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_hash = Column(String(64), unique=True, nullable=False, index=True)
    state = Column(String(50))
    lga = Column(String(100))
    language = Column(String(10), default="en")
    created_at = Column(DateTime, server_default=func.now())
    last_active = Column(DateTime, server_default=func.now())
    
    conversations = relationship("Conversation", back_populates="user")
    reports = relationship("Report", back_populates="user")


class Conversation(Base):
    """Conversation sessions."""
    __tablename__ = "conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime)
    message_count = Column(Integer, default=0)
    primary_intent = Column(String(50))
    
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    """Individual messages with analytics."""
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    direction = Column(String(10), nullable=False)  # inbound, outbound
    content_type = Column(String(20), nullable=False)  # text, image, location
    raw_text = Column(Text)
    
    # Analytics (extracted by LLM)
    intent = Column(String(50), index=True)
    intent_confidence = Column(Float)
    entities = Column(JSONB)
    sentiment = Column(String(20))
    candidates_mentioned = Column(ARRAY(String))
    issues_mentioned = Column(ARRAY(String))
    
    # Location context
    state = Column(String(50), index=True)
    lga = Column(String(100))
    
    created_at = Column(DateTime, server_default=func.now(), index=True)
    
    conversation = relationship("Conversation", back_populates="messages")


# ===========================================
# CITIZEN REPORTING TABLES
# ===========================================

class IssueCategory(Base):
    """Predefined issue categories."""
    __tablename__ = "issue_categories"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    icon = Column(String(20))
    description = Column(Text)


class Report(Base):
    """Citizen issue reports."""
    __tablename__ = "reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_number = Column(String(20), unique=True, nullable=False)  # D9-2025-000001
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    category_id = Column(String(50), ForeignKey("issue_categories.id"))
    
    description = Column(Text)
    photo_url = Column(String(500))
    latitude = Column(Float)
    longitude = Column(Float)
    address = Column(Text)
    state = Column(String(50), index=True)
    lga = Column(String(100), index=True)
    
    status = Column(String(20), default="open", index=True)  # open, acknowledged, in_progress, resolved
    endorsement_count = Column(Integer, default=1)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    user = relationship("User", back_populates="reports")
    category = relationship("IssueCategory")
    endorsements = relationship("Endorsement", back_populates="report")


class Endorsement(Base):
    """Report endorsements ("I've seen this too")."""
    __tablename__ = "endorsements"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    
    report = relationship("Report", back_populates="endorsements")
    
    __table_args__ = (
        Index('idx_endorsement_unique', report_id, user_id, unique=True),
    )


# Create all tables
def init_db():
    # Enable pgvector extension
    with engine.connect() as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()
    Base.metadata.create_all(bind=engine)
```

---

## STEP 2: RAG SERVICE (app/services/rag.py)

```python
"""
Retrieval-Augmented Generation service.
This is the CORE of preventing hallucination.
"""
import os
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
import json

from app.models.database import Document, Candidate, CandidatePosition, FAQ, Party
from app.services.embeddings import get_embedding


class RAGService:
    """
    Retrieves relevant context from the knowledge base.
    CRITICAL: The LLM only sees what this service returns.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.max_context_tokens = 4000  # Leave room for response
    
    async def retrieve(
        self,
        query: str,
        intent: str,
        entities: Dict,
        user_state: Optional[str] = None,
        top_k: int = 5
    ) -> str:
        """
        Main retrieval function. Returns formatted context string.
        """
        context_parts = []
        
        # Route based on intent
        if intent == "candidate_info":
            context = await self._retrieve_candidate(entities, user_state)
            context_parts.append(context)
            
        elif intent == "policy_comparison":
            context = await self._retrieve_comparison(entities)
            context_parts.append(context)
            
        elif intent == "voting_info":
            context = await self._retrieve_faqs("voting_process", query)
            context_parts.append(context)
            
        elif intent == "find_representative":
            context = await self._retrieve_representatives(entities, user_state)
            context_parts.append(context)
            
        elif intent == "party_info":
            context = await self._retrieve_party(entities)
            context_parts.append(context)
            
        elif intent == "promise_tracking":
            context = await self._retrieve_promises(entities)
            context_parts.append(context)
            
        else:
            # Fallback: semantic search across all documents
            context = await self._semantic_search(query, top_k)
            context_parts.append(context)
        
        # Add local context if we have user's state
        if user_state:
            local = await self._get_local_context(user_state)
            if local:
                context_parts.append(f"\n--- LOCAL CONTEXT ({user_state}) ---\n{local}")
        
        # Combine and return
        full_context = "\n\n".join(filter(None, context_parts))
        
        if not full_context.strip():
            return self._no_data_found(intent, entities)
        
        return full_context
    
    async def _retrieve_candidate(self, entities: Dict, user_state: Optional[str]) -> str:
        """Retrieve candidate information."""
        candidate_name = entities.get("candidate_name", "").lower()
        
        if not candidate_name:
            return ""
        
        # Try exact match first
        candidate = self.db.query(Candidate).filter(
            Candidate.slug.ilike(f"%{candidate_name.replace(' ', '_')}%")
        ).first()
        
        if not candidate:
            # Try name search
            candidate = self.db.query(Candidate).filter(
                Candidate.name.ilike(f"%{candidate_name}%")
            ).first()
        
        if not candidate:
            return f"NO DATA FOUND: No candidate matching '{candidate_name}' in database."
        
        # Get positions
        positions = self.db.query(CandidatePosition).filter(
            CandidatePosition.candidate_id == candidate.id
        ).all()
        
        # Format context
        data = candidate.data or {}
        context = f"""
=== CANDIDATE: {candidate.name} ===
Party: {candidate.party_id}
Position Sought: {candidate.position_sought}
Election Year: {candidate.election_year}
State: {candidate.state or 'National'}
Incumbent: {'Yes' if candidate.is_incumbent else 'No'}

BIOGRAPHY:
{json.dumps(data.get('personal', {}), indent=2) if data.get('personal') else 'Not available'}

POLITICAL CAREER:
{json.dumps(data.get('political_career', {}), indent=2) if data.get('political_career') else 'Not available'}

POLICY POSITIONS:
"""
        for pos in positions:
            context += f"\n- {pos.issue_area}: {pos.stance}"
            if pos.quotes:
                for quote in pos.quotes[:2]:  # Limit quotes
                    context += f'\n  Quote: "{quote.get("text", "")}"'
                    context += f'\n  Source: {quote.get("source", "Unknown")} ({quote.get("date", "N/A")})'
        
        if data.get('controversies'):
            context += f"\n\nCONTROVERSIES:\n{json.dumps(data['controversies'][:3], indent=2)}"
        
        context += f"\n\nSOURCE: Decide9ja verified database, last updated {candidate.data.get('metadata', {}).get('last_updated', 'Unknown')}"
        
        return context
    
    async def _retrieve_comparison(self, entities: Dict) -> str:
        """Retrieve data for comparing candidates."""
        candidates = entities.get("candidates", [])
        issue = entities.get("issue", "")
        
        if len(candidates) < 2:
            return "INSUFFICIENT DATA: Need at least 2 candidates to compare."
        
        context = f"=== CANDIDATE COMPARISON: {issue.upper() or 'GENERAL'} ===\n"
        
        for candidate_name in candidates[:4]:  # Max 4 candidates
            candidate = self.db.query(Candidate).filter(
                Candidate.name.ilike(f"%{candidate_name}%")
            ).first()
            
            if not candidate:
                context += f"\n{candidate_name}: NOT FOUND IN DATABASE\n"
                continue
            
            context += f"\n--- {candidate.name} ({candidate.party_id}) ---"
            
            if issue:
                # Get specific position
                position = self.db.query(CandidatePosition).filter(
                    CandidatePosition.candidate_id == candidate.id,
                    CandidatePosition.issue_area.ilike(f"%{issue}%")
                ).first()
                
                if position:
                    context += f"\nPosition on {issue}: {position.stance}"
                    if position.quotes:
                        quote = position.quotes[0]
                        context += f'\nQuote: "{quote.get("text", "")}"'
                        context += f'\nSource: {quote.get("source", "")} ({quote.get("date", "")})'
                else:
                    context += f"\nNo documented position on {issue}"
            else:
                # General comparison
                positions = self.db.query(CandidatePosition).filter(
                    CandidatePosition.candidate_id == candidate.id
                ).limit(5).all()
                
                for pos in positions:
                    context += f"\n- {pos.issue_area}: {pos.stance[:200]}..."
        
        return context
    
    async def _retrieve_faqs(self, category: str, query: str) -> str:
        """Retrieve relevant FAQs."""
        # Get embedding for semantic search
        query_embedding = await get_embedding(query)
        
        # Vector similarity search
        results = self.db.execute(
            text("""
                SELECT question, answer, 1 - (embedding <=> :embedding) as similarity
                FROM faqs
                WHERE category = :category
                ORDER BY embedding <=> :embedding
                LIMIT 5
            """),
            {"embedding": str(query_embedding), "category": category}
        ).fetchall()
        
        if not results:
            # Fallback to keyword search
            faqs = self.db.query(FAQ).filter(
                FAQ.category == category
            ).limit(5).all()
            results = [(f.question, f.answer, 0) for f in faqs]
        
        context = "=== VOTING & ELECTION INFORMATION ===\n"
        for question, answer, _ in results:
            context += f"\nQ: {question}\nA: {answer}\n"
        
        context += "\nSOURCE: INEC official guidelines via Decide9ja"
        return context
    
    async def _retrieve_party(self, entities: Dict) -> str:
        """Retrieve party information."""
        party_name = entities.get("party_name", "") or entities.get("party", "")
        
        party = self.db.query(Party).filter(
            (Party.abbreviation.ilike(f"%{party_name}%")) |
            (Party.name.ilike(f"%{party_name}%"))
        ).first()
        
        if not party:
            return f"NO DATA FOUND: No party matching '{party_name}'"
        
        data = party.data or {}
        context = f"""
=== PARTY: {party.name} ({party.abbreviation}) ===
National Chairman: {party.chairman or 'Not available'}

{json.dumps(data, indent=2) if data else 'Limited data available'}

SOURCE: Decide9ja database (INEC registered parties)
"""
        return context
    
    async def _retrieve_promises(self, entities: Dict) -> str:
        """Retrieve campaign promises."""
        candidate_name = entities.get("candidate_name", "")
        
        # Search promises in documents
        results = self.db.query(Document).filter(
            Document.doc_type == "promise",
            Document.content.ilike(f"%{candidate_name}%") if candidate_name else True
        ).limit(10).all()
        
        if not results:
            return "NO PROMISE DATA: Promise tracking database not yet populated."
        
        context = "=== CAMPAIGN PROMISES ===\n"
        for doc in results:
            metadata = doc.metadata or {}
            context += f"\n- {doc.title}"
            context += f"\n  Status: {metadata.get('status', 'Unknown')}"
            context += f"\n  Source: {metadata.get('source', 'Campaign statement')}\n"
        
        return context
    
    async def _retrieve_representatives(self, entities: Dict, user_state: Optional[str]) -> str:
        """Retrieve user's representatives."""
        state = entities.get("state") or user_state
        lga = entities.get("lga")
        
        if not state:
            return "NEED LOCATION: Please share your state to find your representatives."
        
        # Get representatives from candidates (incumbents)
        reps = self.db.query(Candidate).filter(
            Candidate.is_incumbent == True,
            (Candidate.state == state) | (Candidate.state == None)  # National + state level
        ).all()
        
        context = f"=== YOUR REPRESENTATIVES ({state}) ===\n"
        
        for rep in reps:
            context += f"\n{rep.position_sought}: {rep.name} ({rep.party_id})"
        
        if not reps:
            context += "\nRepresentative data not yet available for your location."
        
        return context
    
    async def _semantic_search(self, query: str, top_k: int = 5) -> str:
        """Fallback semantic search across all documents."""
        query_embedding = await get_embedding(query)
        
        results = self.db.execute(
            text("""
                SELECT doc_type, title, content, metadata,
                       1 - (embedding <=> :embedding) as similarity
                FROM documents
                ORDER BY embedding <=> :embedding
                LIMIT :limit
            """),
            {"embedding": str(query_embedding), "limit": top_k}
        ).fetchall()
        
        if not results:
            return ""
        
        context = "=== RELEVANT INFORMATION ===\n"
        for doc_type, title, content, metadata, similarity in results:
            if similarity > 0.7:  # Only include if reasonably similar
                context += f"\n[{doc_type.upper()}] {title}\n{content[:500]}...\n"
        
        return context
    
    async def _get_local_context(self, state: str) -> str:
        """Get local context for user's state."""
        # Get governor, senators for the state
        officials = self.db.query(Candidate).filter(
            Candidate.is_incumbent == True,
            Candidate.state == state
        ).all()
        
        if not officials:
            return ""
        
        context = f"Current officials for {state}:\n"
        for official in officials:
            context += f"- {official.position_sought}: {official.name} ({official.party_id})\n"
        
        return context
    
    def _no_data_found(self, intent: str, entities: Dict) -> str:
        """Return helpful message when no data found."""
        return f"""
NO VERIFIED DATA FOUND

Intent: {intent}
Search terms: {entities}

The requested information is not in the Decide9ja verified database.
Do NOT make up information. Instead, tell the user:
- What information you DO have
- Offer alternative assistance
- Suggest they check back later as database expands
"""


# Factory function
def get_rag_service(db: Session) -> RAGService:
    return RAGService(db)
```

---

## STEP 3: LLM SERVICE (app/services/llm.py)

```python
"""
Claude API integration with strict grounding.
"""
import os
from typing import List, Dict, Optional
from anthropic import Anthropic

from app.prompts.system import SYSTEM_PROMPT, get_grounded_prompt


client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


async def generate_response(
    user_message: str,
    context: str,
    conversation_history: List[Dict] = None,
    user_state: Optional[str] = None
) -> str:
    """
    Generate a response using Claude with RAG context.
    
    CRITICAL: The system prompt instructs Claude to ONLY use the provided context.
    """
    
    # Build the grounded system prompt
    system_prompt = get_grounded_prompt(context, user_state)
    
    # Build messages
    messages = []
    
    # Add conversation history (last 10 messages for context)
    if conversation_history:
        for msg in conversation_history[-10:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
    
    # Add current user message
    messages.append({
        "role": "user",
        "content": user_message
    })
    
    # Call Claude
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system_prompt,
        messages=messages
    )
    
    return response.content[0].text


async def extract_analytics(
    user_message: str,
    bot_response: str
) -> Dict:
    """
    Extract analytics from the conversation turn.
    Uses Claude to identify intent, entities, sentiment.
    """
    
    extraction_prompt = f"""
Analyze this conversation turn and extract structured data.

USER MESSAGE: {user_message}
BOT RESPONSE: {bot_response}

Return ONLY valid JSON with this structure:
{{
    "intent": "candidate_info|policy_comparison|voting_info|report_issue|find_representative|party_info|greeting|unknown",
    "intent_confidence": 0.0-1.0,
    "entities": {{
        "candidate_names": [],
        "party_names": [],
        "issues": [],
        "locations": []
    }},
    "sentiment": "positive|negative|neutral",
    "candidates_mentioned": [],
    "issues_mentioned": []
}}
"""
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": extraction_prompt}]
    )
    
    import json
    try:
        return json.loads(response.content[0].text)
    except:
        return {
            "intent": "unknown",
            "intent_confidence": 0.5,
            "entities": {},
            "sentiment": "neutral",
            "candidates_mentioned": [],
            "issues_mentioned": []
        }
```

---

## STEP 4: SYSTEM PROMPTS (app/prompts/system.py)

```python
"""
System prompts for Decide9ja chatbot.
These prompts are CRITICAL for preventing hallucination.
"""

SYSTEM_PROMPT = """
You are Decide9ja, a friendly and nonpartisan election information assistant for Nigerian voters.

## YOUR PERSONALITY
- Warm but professional
- Helpful but honest about limitations
- Neutral on all political matters
- Speaks naturally like a helpful Nigerian friend
- Never preachy or condescending

## YOUR CAPABILITIES
1. Answer questions about candidates and their positions
2. Compare candidates on specific issues
3. Help users find their polling unit
4. Explain voting procedures (BVAS, accreditation, etc.)
5. Help users report local infrastructure issues
6. Find users' elected representatives
7. Track politician promises

## CRITICAL RULES - NEVER BREAK THESE

### Rule 1: ONLY USE PROVIDED CONTEXT
You must ONLY answer using the CONTEXT provided below.
If information is NOT in the CONTEXT, you MUST say "I don't have verified information about that."
NEVER invent facts, quotes, statistics, or promises.
NEVER guess candidate positions if not explicitly stated in CONTEXT.

### Rule 2: ALWAYS ATTRIBUTE
When stating facts, always indicate the source:
- "According to their campaign..."
- "Based on their voting record..."
- "They stated in [source]..."

### Rule 3: NONPARTISAN
- Never recommend who to vote for
- Never express political opinions
- Present information factually without bias
- Include both achievements AND criticisms when available

### Rule 4: ADMIT LIMITATIONS
If you don't have information:
- Say "I don't have verified information about that yet"
- Offer what you CAN help with
- Never make things up to seem helpful

## RESPONSE STYLE
- Keep responses under 200 words unless detail is requested
- Use simple language (imagine explaining to your aunt)
- One question at a time
- Use emoji sparingly (1-2 per message max)
- Break long responses into natural paragraphs
- Don't use bullet points in casual chat

## WHAT YOU NEVER DO
- Never recommend who to vote for
- Never express political opinions  
- Never make up facts, quotes, or promises
- Never share unverified rumors
- Never ask for personal information beyond location
- Never be rude, even if user is frustrated
"""


def get_grounded_prompt(context: str, user_state: str = None) -> str:
    """
    Build the full system prompt with retrieved context.
    """
    
    location_context = ""
    if user_state:
        location_context = f"\nUser's location: {user_state}"
    
    return f"""
{SYSTEM_PROMPT}

## CONTEXT FROM DATABASE
Everything below is verified information from the Decide9ja database.
You may ONLY use this information to answer the user's question.
If the answer is not in this context, say you don't have that information.

---
{context}
---
{location_context}

Now respond to the user's message. Remember:
1. ONLY use the CONTEXT above
2. If information isn't there, admit it
3. Be helpful and suggest alternatives
4. Stay nonpartisan
"""


# Response templates for specific situations
TEMPLATES = {
    "no_candidate_data": """
I don't have verified information about {candidate_name} yet. 

My database currently covers major candidates for the 2023 and upcoming 2027 elections.

Would you like me to:
🗳️ Show candidates I DO have information on
📍 Help you report an issue in your area
🏛️ Find your elected representatives
""",

    "no_position_data": """
I don't have {candidate_name}'s documented position on {issue}.

I only share positions I can verify from official sources like manifestos, interviews, or voting records.

Would you like to:
• See issues they HAVE spoken about
• Compare other candidates on {issue}
""",

    "greeting": """
Hello! 👋 I'm Decide9ja, your nonpartisan election assistant.

I can help you with:
🗳️ Candidate information & comparisons
📍 Reporting local issues (roads, water, electricity)
🏛️ Finding your representatives
📋 Understanding voting procedures

What would you like to know?
""",

    "report_started": """
I'll help you report that issue. 📝

Please:
1. 📸 Take a photo of the problem
2. 📍 Share your location
3. 📝 Briefly describe the issue

Your report helps hold leaders accountable!
""",

    "report_complete": """
✅ Report submitted!

📋 Report #{report_number}
📍 Location: {location}
📸 Photo: Attached
👥 Others reporting this issue: {endorsement_count}

Track your report at: decide9ja.com/r/{report_id}

Would you like to report another issue or do something else?
"""
}
```

---

## STEP 5: WHATSAPP WEBHOOK (app/api/webhooks.py)

```python
"""
WhatsApp webhook handlers.
Works with both Twilio and direct Meta WhatsApp Business API.
"""
import os
import hashlib
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.rag import get_rag_service
from app.services.llm import generate_response, extract_analytics
from app.services.whatsapp import send_whatsapp_message, parse_webhook
from app.services.intent import classify_intent
from app.models.database import User, Conversation, Message

router = APIRouter()

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "decide9ja_verify_token")


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = None,
    hub_challenge: str = None,
    hub_verify_token: str = None
):
    """WhatsApp webhook verification (GET request)."""
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Main webhook handler for incoming WhatsApp messages.
    """
    body = await request.json()
    
    # Parse the webhook payload
    message = parse_webhook(body)
    
    if not message:
        return {"status": "no message"}
    
    # Process in background to respond quickly
    background_tasks.add_task(
        process_message,
        message=message,
        db=db
    )
    
    return {"status": "processing"}


async def process_message(message: dict, db: Session):
    """
    Process incoming message and generate response.
    This is where RAG happens.
    """
    
    # 1. Hash phone number (never store raw)
    phone_hash = hashlib.sha256(message["from"].encode()).hexdigest()
    
    # 2. Get or create user
    user = db.query(User).filter(User.phone_hash == phone_hash).first()
    if not user:
        user = User(phone_hash=phone_hash)
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # 3. Get or create conversation
    conversation = db.query(Conversation).filter(
        Conversation.user_id == user.id,
        Conversation.ended_at == None
    ).first()
    
    if not conversation:
        conversation = Conversation(user_id=user.id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    
    # 4. Log inbound message
    inbound_msg = Message(
        conversation_id=conversation.id,
        direction="inbound",
        content_type=message.get("type", "text"),
        raw_text=message.get("text", ""),
        state=user.state,
        lga=user.lga
    )
    db.add(inbound_msg)
    
    # 5. Classify intent
    intent, entities, confidence = await classify_intent(message.get("text", ""))
    
    # 6. RETRIEVE relevant context (RAG)
    rag_service = get_rag_service(db)
    context = await rag_service.retrieve(
        query=message.get("text", ""),
        intent=intent,
        entities=entities,
        user_state=user.state
    )
    
    # 7. Get conversation history for context
    history = db.query(Message).filter(
        Message.conversation_id == conversation.id
    ).order_by(Message.created_at.desc()).limit(10).all()
    
    conversation_history = [
        {"role": "user" if m.direction == "inbound" else "assistant", "content": m.raw_text}
        for m in reversed(history)
    ]
    
    # 8. GENERATE response with Claude (grounded in context)
    response_text = await generate_response(
        user_message=message.get("text", ""),
        context=context,
        conversation_history=conversation_history,
        user_state=user.state
    )
    
    # 9. Extract analytics
    analytics = await extract_analytics(message.get("text", ""), response_text)
    
    # 10. Log outbound message with analytics
    outbound_msg = Message(
        conversation_id=conversation.id,
        direction="outbound",
        content_type="text",
        raw_text=response_text,
        intent=analytics.get("intent"),
        intent_confidence=analytics.get("intent_confidence"),
        entities=analytics.get("entities"),
        sentiment=analytics.get("sentiment"),
        candidates_mentioned=analytics.get("candidates_mentioned"),
        issues_mentioned=analytics.get("issues_mentioned"),
        state=user.state,
        lga=user.lga
    )
    db.add(outbound_msg)
    
    # 11. Update conversation
    conversation.message_count += 2
    conversation.primary_intent = analytics.get("intent")
    
    # 12. Update user activity
    from datetime import datetime
    user.last_active = datetime.utcnow()
    
    db.commit()
    
    # 13. Send response via WhatsApp
    await send_whatsapp_message(message["from"], response_text)
```

---

## STEP 6: EMBEDDING SERVICE (app/services/embeddings.py)

```python
"""
Vector embedding service for semantic search.
Supports OpenAI embeddings or local sentence-transformers.
"""
import os
from typing import List
import numpy as np

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")  # openai or local


async def get_embedding(text: str) -> List[float]:
    """Get embedding vector for text."""
    
    if EMBEDDING_PROVIDER == "openai":
        return await _openai_embedding(text)
    else:
        return await _local_embedding(text)


async def _openai_embedding(text: str) -> List[float]:
    """Use OpenAI's text-embedding-3-small model."""
    from openai import OpenAI
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    
    return response.data[0].embedding


async def _local_embedding(text: str) -> List[float]:
    """Use local sentence-transformers model (no API cost)."""
    from sentence_transformers import SentenceTransformer
    
    # Cache model
    if not hasattr(_local_embedding, "model"):
        _local_embedding.model = SentenceTransformer('all-MiniLM-L6-v2')
    
    embedding = _local_embedding.model.encode(text)
    
    # Pad to 1536 dimensions to match pgvector setup
    # (or change Vector dimension in database.py to 384 for MiniLM)
    padded = np.zeros(1536)
    padded[:len(embedding)] = embedding
    
    return padded.tolist()


async def batch_embed(texts: List[str]) -> List[List[float]]:
    """Batch embed multiple texts (more efficient)."""
    
    if EMBEDDING_PROVIDER == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=texts
        )
        
        return [item.embedding for item in response.data]
    
    else:
        from sentence_transformers import SentenceTransformer
        
        if not hasattr(_local_embedding, "model"):
            _local_embedding.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        embeddings = _local_embedding.model.encode(texts)
        
        # Pad each
        result = []
        for emb in embeddings:
            padded = np.zeros(1536)
            padded[:len(emb)] = emb
            result.append(padded.tolist())
        
        return result
```

---

## STEP 7: DATA SEEDING SCRIPT (scripts/seed_database.py)

```python
"""
Load JSON data into PostgreSQL with embeddings.
Run this after generating data with Antigravity missions.
"""
import os
import sys
import json
from pathlib import Path
import asyncio

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal, init_db, Document, Candidate, Party, CandidatePosition, FAQ
from app.services.embeddings import batch_embed


DATA_DIR = Path(__file__).parent.parent / "data"


async def seed_parties():
    """Load parties from JSON."""
    print("📋 Loading parties...")
    
    db = SessionLocal()
    parties_file = DATA_DIR / "processed" / "parties.json"
    
    if not parties_file.exists():
        print("  ⚠️ parties.json not found")
        return
    
    with open(parties_file) as f:
        parties = json.load(f)
    
    for party_data in parties:
        party = Party(
            abbreviation=party_data["abbreviation"],
            name=party_data["name"],
            chairman=party_data.get("chairman"),
            data=party_data
        )
        db.merge(party)  # Upsert
    
    db.commit()
    print(f"  ✓ Loaded {len(parties)} parties")
    db.close()


async def seed_candidates():
    """Load candidates from JSON files."""
    print("👤 Loading candidates...")
    
    db = SessionLocal()
    candidates_dir = DATA_DIR / "candidates"
    
    if not candidates_dir.exists():
        print("  ⚠️ candidates directory not found")
        return
    
    count = 0
    for json_file in candidates_dir.rglob("*.json"):
        if json_file.name.startswith("_"):
            continue
        
        with open(json_file) as f:
            data = json.load(f)
        
        candidate = Candidate(
            slug=data.get("slug") or data.get("id"),
            name=data.get("name", {}).get("full") if isinstance(data.get("name"), dict) else data.get("name"),
            party_id=data.get("party_id") or data.get("political_career", {}).get("party_history", [{}])[-1].get("party"),
            position_sought=data.get("position_sought"),
            election_year=data.get("election_year"),
            state=data.get("state"),
            is_incumbent=data.get("is_incumbent", False),
            data=data
        )
        db.merge(candidate)
        
        # Add positions
        for position in data.get("policy_positions", []):
            pos = CandidatePosition(
                candidate_id=candidate.id,
                issue_area=position.get("issue_area"),
                stance=position.get("stance_summary"),
                quotes=position.get("quotes", [])
            )
            db.add(pos)
        
        count += 1
    
    db.commit()
    print(f"  ✓ Loaded {count} candidates")
    db.close()


async def seed_documents_with_embeddings():
    """Create searchable documents with vector embeddings."""
    print("📄 Creating document embeddings...")
    
    db = SessionLocal()
    
    # Collect all text to embed
    documents_to_embed = []
    
    # 1. Create documents from candidates
    candidates = db.query(Candidate).all()
    for candidate in candidates:
        # Create a comprehensive text representation
        text = f"""
        Candidate: {candidate.name}
        Party: {candidate.party_id}
        Position: {candidate.position_sought}
        State: {candidate.state or 'National'}
        
        {json.dumps(candidate.data, indent=2) if candidate.data else ''}
        """
        
        documents_to_embed.append({
            "doc_type": "candidate",
            "doc_id": candidate.slug,
            "title": candidate.name,
            "content": text,
            "metadata": candidate.data,
            "state": candidate.state,
            "party": candidate.party_id,
            "year": candidate.election_year,
            "category": "candidate"
        })
    
    # 2. Create documents from parties
    parties = db.query(Party).all()
    for party in parties:
        text = f"""
        Party: {party.name} ({party.abbreviation})
        Chairman: {party.chairman}
        
        {json.dumps(party.data, indent=2) if party.data else ''}
        """
        
        documents_to_embed.append({
            "doc_type": "party",
            "doc_id": party.abbreviation,
            "title": party.name,
            "content": text,
            "metadata": party.data,
            "party": party.abbreviation,
            "category": "party"
        })
    
    # 3. Generate embeddings in batches
    print(f"  Generating embeddings for {len(documents_to_embed)} documents...")
    
    batch_size = 100
    for i in range(0, len(documents_to_embed), batch_size):
        batch = documents_to_embed[i:i+batch_size]
        texts = [d["content"] for d in batch]
        
        embeddings = await batch_embed(texts)
        
        for doc, embedding in zip(batch, embeddings):
            document = Document(
                doc_type=doc["doc_type"],
                doc_id=doc["doc_id"],
                title=doc["title"],
                content=doc["content"],
                metadata=doc["metadata"],
                embedding=embedding,
                state=doc.get("state"),
                party=doc.get("party"),
                year=doc.get("year"),
                category=doc.get("category")
            )
            db.merge(document)
        
        db.commit()
        print(f"    Embedded batch {i//batch_size + 1}/{(len(documents_to_embed)-1)//batch_size + 1}")
    
    print(f"  ✓ Created {len(documents_to_embed)} searchable documents")
    db.close()


async def seed_faqs():
    """Load FAQs for voting process, etc."""
    print("❓ Loading FAQs...")
    
    db = SessionLocal()
    
    # Built-in FAQs (can also load from JSON)
    faqs = [
        {
            "category": "voting_process",
            "question": "How do I find my polling unit?",
            "answer": "You can find your polling unit by visiting the INEC voter verification portal at voters.inecnigeria.org. Enter your Voter Identification Number (VIN) or use your name and date of birth to locate your assigned polling unit.",
            "keywords": ["polling unit", "where to vote", "PU", "location"]
        },
        {
            "category": "voting_process",
            "question": "What is BVAS and how does it work?",
            "answer": "BVAS (Bimodal Voter Accreditation System) is INEC's device for voter accreditation. It uses both fingerprint and facial recognition to verify your identity against your PVC data. On election day, the BVAS operator will scan your face and/or fingerprint before you're allowed to vote.",
            "keywords": ["BVAS", "accreditation", "bimodal", "fingerprint", "facial recognition"]
        },
        {
            "category": "voting_process",
            "question": "What documents do I need to vote?",
            "answer": "You need your Permanent Voter Card (PVC) to vote. No other form of identification is accepted. Make sure to collect your PVC from your local INEC office before election day.",
            "keywords": ["PVC", "voter card", "documents", "ID", "identification"]
        },
        {
            "category": "voting_process",
            "question": "What time do polls open and close?",
            "answer": "Polling units open at 8:30am and close at 2:30pm on election day. Accreditation and voting happen simultaneously. If you're in the queue by 2:30pm, you'll be allowed to vote.",
            "keywords": ["time", "hours", "open", "close", "when"]
        },
        {
            "category": "voting_process",
            "question": "How do I report election irregularities?",
            "answer": "You can report election irregularities to INEC through their official channels, contact election observers like YIAGA Africa or TMG, or use the Decide9ja platform to document and report issues with photos and location.",
            "keywords": ["report", "irregularities", "fraud", "problems", "issues"]
        },
        {
            "category": "registration",
            "question": "How do I register to vote?",
            "answer": "To register to vote, visit the nearest INEC office during a Continuous Voter Registration (CVR) exercise. You'll need to be a Nigerian citizen, at least 18 years old, and provide biometric data. INEC announces CVR dates periodically.",
            "keywords": ["register", "registration", "CVR", "new voter", "how to register"]
        },
        {
            "category": "registration",
            "question": "Can I transfer my voter registration?",
            "answer": "Yes, you can transfer your registration to a new location during a CVR exercise. Visit an INEC office in your new location with your PVC and request a transfer. You'll need to provide a reason and go through re-verification.",
            "keywords": ["transfer", "move", "relocate", "new location"]
        },
    ]
    
    # Generate embeddings
    texts = [f"{faq['question']} {faq['answer']}" for faq in faqs]
    embeddings = await batch_embed(texts)
    
    for faq, embedding in zip(faqs, embeddings):
        faq_obj = FAQ(
            category=faq["category"],
            question=faq["question"],
            answer=faq["answer"],
            keywords=faq["keywords"],
            embedding=embedding
        )
        db.add(faq_obj)
    
    db.commit()
    print(f"  ✓ Loaded {len(faqs)} FAQs")
    db.close()


async def main():
    print("🚀 Seeding Decide9ja Database")
    print("=" * 50)
    
    # Initialize database
    print("Initializing database...")
    init_db()
    
    # Seed data
    await seed_parties()
    await seed_candidates()
    await seed_faqs()
    await seed_documents_with_embeddings()
    
    print("=" * 50)
    print("✅ Database seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## STEP 8: MAIN APP (app/main.py)

```python
"""
Decide9ja FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.webhooks import router as webhook_router
from app.api.health import router as health_router
from app.database import init_db

app = FastAPI(
    title="Decide9ja API",
    description="Political Intelligence Platform for Nigerian Voters",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(webhook_router, prefix="/api", tags=["WhatsApp"])
app.include_router(health_router, prefix="/api", tags=["Health"])

@app.on_event("startup")
async def startup():
    init_db()

@app.get("/")
async def root():
    return {
        "name": "Decide9ja",
        "status": "running",
        "version": "1.0.0"
    }
```

---

## STEP 9: REQUIREMENTS & DOCKER

Create requirements.txt:
```
fastapi>=0.104.0
uvicorn>=0.24.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.9
pgvector>=0.2.0
anthropic>=0.18.0
openai>=1.12.0
python-dotenv>=1.0.0
httpx>=0.26.0
pydantic>=2.5.0
redis>=5.0.0
cloudinary>=1.38.0
sentence-transformers>=2.2.0
numpy>=1.24.0
```

Create .env.example:
```
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/decide9ja

# AI APIs
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# WhatsApp
WHATSAPP_VERIFY_TOKEN=decide9ja_verify_token
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_ID=...

# Optional
CLOUDINARY_URL=cloudinary://...
REDIS_URL=redis://localhost:6379

# Embedding provider: openai or local
EMBEDDING_PROVIDER=openai
```

Create Dockerfile:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## TESTING

Create scripts/test_rag.py to verify RAG is working:
```python
"""Test RAG retrieval quality."""
import asyncio
from app.database import SessionLocal
from app.services.rag import get_rag_service

async def test_queries():
    db = SessionLocal()
    rag = get_rag_service(db)
    
    test_cases = [
        ("Who is Tinubu?", "candidate_info", {"candidate_name": "Tinubu"}),
        ("Compare Tinubu and Obi on economy", "policy_comparison", {"candidates": ["Tinubu", "Obi"], "issue": "economy"}),
        ("How do I vote?", "voting_info", {}),
        ("Who is my senator?", "find_representative", {"state": "Lagos"}),
    ]
    
    for query, intent, entities in test_cases:
        print(f"\n{'='*50}")
        print(f"Query: {query}")
        print(f"Intent: {intent}")
        
        context = await rag.retrieve(query, intent, entities, "Lagos")
        
        print(f"\nRetrieved Context ({len(context)} chars):")
        print(context[:500] + "..." if len(context) > 500 else context)
    
    db.close()

if __name__ == "__main__":
    asyncio.run(test_queries())
```

---

## DEPLOYMENT CHECKLIST

After building, verify:
- [ ] PostgreSQL with pgvector extension running
- [ ] All tables created via init_db()
- [ ] Data seeded from JSON files
- [ ] Embeddings generated for all documents
- [ ] WhatsApp webhook URL configured
- [ ] Claude API key valid
- [ ] Test query retrieves relevant context
- [ ] Test message gets grounded response

---

## SUCCESS CRITERIA

The RAG system is working correctly when:
1. Queries about candidates return ONLY database content
2. Unknown candidates get "I don't have information" response
3. Policy comparisons cite specific quotes with sources
4. No hallucinated facts, names, or statistics
5. Response time < 3 seconds
6. All interactions logged with analytics

Build this complete system. Test each component. Ensure no hallucination.
```

---

# QUICK START COMMAND

Copy this entire mission into Antigravity Agent Manager:

```
Build the complete Decide9ja RAG system as specified in this document.

Start by creating the project structure, then implement each file in order:
1. database.py - PostgreSQL + pgvector models
2. rag.py - Retrieval service (MOST IMPORTANT)
3. llm.py - Claude integration with grounding
4. system.py - Anti-hallucination prompts
5. webhooks.py - WhatsApp handler
6. embeddings.py - Vector embedding service
7. seed_database.py - Data loading script
8. main.py - FastAPI app

After building, run the seed script to load data from the data/ folder.
Then test with test_rag.py to verify retrieval quality.

The system must NEVER hallucinate - only answer from retrieved context.
```
