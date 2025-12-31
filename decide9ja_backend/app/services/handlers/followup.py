"""
Handle followup queries that reference previous context.
"""
import logging
import re
from typing import Optional

from app.models.state import UserState
from app.services.templates import get_template

logger = logging.getLogger(__name__)


async def handle_followup(state: UserState, text: str, entities: dict) -> str:
    """
    Handle followup questions like "What has he done?" or "Tell me more".
    Uses active_politician from state for pronoun resolution.
    """
    
    # Check if we have an active politician
    if not state.active_politician_id and not state.active_politician_name:
        return get_template("followup_no_context")
    
    # Resolve pronouns to the active politician
    resolved_query = resolve_pronouns(text, state.active_politician_name)
    
    # Determine what aspect they're asking about
    text_lower = text.lower()
    
    if any(word in text_lower for word in ["bill", "sponsor", "legislation", "law"]):
        return await get_politician_bills(state.active_politician_id, state.active_politician_name)
    
    elif any(word in text_lower for word in ["done", "achieve", "record", "project", "accomplish"]):
        return await get_politician_record(state.active_politician_id, state.active_politician_name)
    
    elif any(word in text_lower for word in ["committee", "member", "chairman"]):
        return await get_politician_committees(state.active_politician_id, state.active_politician_name)
    
    elif any(word in text_lower for word in ["vote", "voting", "voted"]):
        return await get_politician_votes(state.active_politician_id, state.active_politician_name)
    
    else:
        # General followup - use LLM with context
        return await get_general_followup(state, resolved_query)


def resolve_pronouns(text: str, politician_name: str) -> str:
    """Replace pronouns with the active politician's name."""
    if not politician_name:
        return text
    
    # Replace common pronouns
    replacements = [
        (r"\bhe\b", politician_name),
        (r"\bshe\b", politician_name),
        (r"\bhim\b", politician_name),
        (r"\bher\b", politician_name),
        (r"\bhis\b", f"{politician_name}'s"),
        (r"\btheir\b", f"{politician_name}'s"),
        (r"\bthey\b", politician_name),
        (r"\bthem\b", politician_name),
    ]
    
    result = text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result


async def get_politician_bills(politician_id: str, name: str) -> str:
    """Fetch bills sponsored by politician."""
    try:
        from app.database import get_db, Politician
        db = next(get_db())
        
        politician = db.query(Politician).filter(Politician.id == politician_id).first()
        
        if politician and politician.bills:
            bills = politician.bills[:5] if isinstance(politician.bills, list) else []
            if bills:
                bills_summary = "\n".join([f"• {b.get('title', 'Unknown')} ({b.get('status', 'Pending')})" for b in bills])
                return get_template("followup_bills", 
                    name=name,
                    count=len(bills),
                    bills_summary=bills_summary
                )
        
        return get_template("followup_no_bills", name=name)
        
    except Exception as e:
        logger.error(f"Error fetching bills: {e}")
        return f"{name} hasn't sponsored any bills that I have on record.\n\nWant to know something else about them?"


async def get_politician_record(politician_id: str, name: str) -> str:
    """Fetch general record/achievements."""
    try:
        from app.database import get_db, Politician
        db = next(get_db())
        
        politician = db.query(Politician).filter(Politician.id == politician_id).first()
        
        if politician:
            achievements = []
            
            if politician.bio:
                achievements.append(politician.bio[:300])
            
            if politician.projects:
                projects = politician.projects[:3] if isinstance(politician.projects, list) else []
                for p in projects:
                    achievements.append(f"• {p.get('title', 'Project')}")
            
            if achievements:
                return f"{name}'s Record:\n\n" + "\n".join(achievements) + "\n\nWant more details?"
        
        return f"I don't have detailed records for {name} yet.\n\nTry asking about their current position or recent news."
        
    except Exception as e:
        logger.error(f"Error fetching record: {e}")
        return f"I couldn't retrieve {name}'s record right now. Try again later."


async def get_politician_committees(politician_id: str, name: str) -> str:
    """Fetch committee memberships."""
    try:
        from app.database import get_db, Politician
        db = next(get_db())
        
        politician = db.query(Politician).filter(Politician.id == politician_id).first()
        
        if politician and politician.committees:
            committees = politician.committees if isinstance(politician.committees, list) else []
            if committees:
                committee_list = "\n".join([f"• {c}" for c in committees[:5]])
                return f"{name}'s Committee Memberships:\n\n{committee_list}"
        
        return f"I don't have committee information for {name}.\n\nWant to know something else about them?"
        
    except Exception as e:
        logger.error(f"Error fetching committees: {e}")
        return f"I couldn't retrieve {name}'s committee memberships right now."


async def get_politician_votes(politician_id: str, name: str) -> str:
    """Fetch voting record."""
    return f"I don't have {name}'s voting record in my database yet.\n\nThis information will be available as we expand our coverage."


async def get_general_followup(state: UserState, resolved_query: str) -> str:
    """Handle general followup using LLM with context."""
    try:
        from app.services.llm import generate_response_sync
        from app.services.rag import RAGService
        from app.database import get_db
        
        db = next(get_db())
        rag = RAGService(db)
        
        # Get relevant context
        context, sources = rag.retrieve(
            query=resolved_query,
            top_k=3
        )
        
        if context:
            response = generate_response_sync(
                user_message=resolved_query,
                context=context
            )
            return response
        else:
            return f"I don't have more information on that.\n\nTry asking a more specific question about {state.active_politician_name}."
            
    except Exception as e:
        logger.error(f"Error in general followup: {e}")
        return "I couldn't find more information on that. Try asking differently."
