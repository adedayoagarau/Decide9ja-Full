"""
Context Assembler

Takes RetrievalResult and assembles formatted context for the LLM.
Manages token budget and prioritizes most relevant information.
"""
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MAX_CONTEXT_TOKENS = 4000  # Leave room for response
CHARS_PER_TOKEN = 4  # Rough estimate


@dataclass
class AssembledContext:
    """Formatted context ready for LLM."""
    system_context: str  # Added to system prompt
    user_context: str    # Added to user message
    total_tokens: int
    sources: List[str]


def assemble_context(
    retrieval,
    user_state,
    query: str
) -> AssembledContext:
    """
    Assemble context from retrieval results.
    
    Priority order:
    1. User profile (always included)
    2. Direct politician match
    3. Representatives list
    4. RAG context
    5. News results
    6. Web search results
    """
    sections = []
    sources = []
    
    # === USER PROFILE ===
    profile_section = format_user_profile(user_state)
    if profile_section:
        sections.append(("USER PROFILE", profile_section))
    
    # === POLITICIAN MATCH ===
    if retrieval.politician:
        pol_section = format_politician(retrieval.politician)
        sections.append(("POLITICIAN INFO", pol_section))
        sources.append("database")
    
    # === REPRESENTATIVES ===
    if retrieval.representatives:
        reps_section = format_representatives(retrieval.representatives)
        sections.append(("USER'S REPRESENTATIVES", reps_section))
        sources.append("database")
    
    # === RAG CONTEXT ===
    if retrieval.rag_context:
        sections.append(("BACKGROUND INFORMATION", retrieval.rag_context))
        sources.append("rag")
    
    # === NEWS ===
    if retrieval.news_results:
        news_section = format_news_results(retrieval.news_results)
        sections.append(("RECENT NEWS", news_section))
        sources.append("news")
    
    # === WEB SEARCH ===
    if retrieval.web_results:
        web_section = format_search_results(retrieval.web_results)
        sections.append(("WEB SEARCH RESULTS", web_section))
        sources.append("web")
    
    # === SUGGESTIONS ===
    if retrieval.suggestions:
        suggestions = "\n".join(f"- {s}" for s in retrieval.suggestions)
        sections.append(("NOTES", suggestions))
    
    # Build context string
    context_parts = []
    for title, content in sections:
        context_parts.append(f"## {title}\n{content}")
    
    full_context = "\n\n".join(context_parts)
    
    # Truncate if too long
    max_chars = MAX_CONTEXT_TOKENS * CHARS_PER_TOKEN
    if len(full_context) > max_chars:
        full_context = truncate_context(sections, max_chars)
    
    return AssembledContext(
        system_context="",  # Could add system-level context here
        user_context=full_context,
        total_tokens=len(full_context) // CHARS_PER_TOKEN,
        sources=list(set(sources))
    )


def format_user_profile(state) -> str:
    """Format user profile for context."""
    if not getattr(state, 'name', None) and not getattr(state, 'state', None):
        return ""
    
    parts = []
    if getattr(state, 'name', None):
        parts.append(f"Name: {state.name}")
    if getattr(state, 'state', None):
        lga = getattr(state, 'lga', '') or ''
        parts.append(f"Location: {lga}, {state.state} State".strip(", "))
    if getattr(state, 'active_politician_name', None):
        parts.append(f"Currently discussing: {state.active_politician_name}")
    if getattr(state, 'active_topic', None):
        parts.append(f"Topic: {state.active_topic}")
    
    return "\n".join(parts)


def format_politician(pol: dict) -> str:
    """Format politician data for context."""
    parts = [
        f"Name: {pol.get('name', 'Unknown')}",
        f"Position: {pol.get('position', 'Unknown')}",
        f"Party: {pol.get('party', 'Unknown')}",
    ]
    
    if pol.get('state'):
        parts.append(f"State: {pol['state']}")
    
    if pol.get('constituency'):
        parts.append(f"Constituency: {pol['constituency']}")
    
    if pol.get('bio'):
        bio = pol['bio'][:500] + "..." if len(pol.get('bio', '')) > 500 else pol.get('bio', '')
        parts.append(f"\nBiography:\n{bio}")
    
    return "\n".join(parts)


def format_representatives(reps: list) -> str:
    """Format representatives list for context."""
    parts = []
    for rep in reps:
        position = rep.get('rep_position', rep.get('position', 'Rep'))
        line = f"• {position}: {rep.get('name', 'Unknown')} ({rep.get('party', '')})"
        if rep.get('constituency'):
            line += f" — {rep['constituency']}"
        parts.append(line)
    
    return "\n".join(parts)


def format_news_results(results: List[Dict]) -> str:
    """Format news results for LLM context."""
    if not results:
        return ""
    
    formatted = []
    for i, r in enumerate(results[:5], 1):
        date_str = r.get('date', r.get('published', ''))
        source = r.get('source', 'Unknown')
        formatted.append(
            f"[{i}] {r.get('title', 'Untitled')}\n"
            f"    {r.get('summary', r.get('snippet', 'No summary'))[:200]}\n"
            f"    Source: {source} | {date_str}"
        )
    
    return "\n\n".join(formatted)


def format_search_results(results: List[Dict]) -> str:
    """Format search results for LLM context."""
    if not results:
        return ""
    
    formatted = []
    for i, r in enumerate(results[:5], 1):
        formatted.append(
            f"[{i}] {r.get('title', 'Untitled')}\n"
            f"    {r.get('summary', r.get('snippet', '')[:200])}\n"
            f"    Source: {r.get('source', 'Unknown')}"
        )
    
    return "\n\n".join(formatted)


def truncate_context(sections: list, max_chars: int) -> str:
    """
    Truncate context to fit within token budget.
    Prioritizes earlier sections.
    """
    result = []
    current_length = 0
    
    for title, content in sections:
        section_text = f"## {title}\n{content}"
        section_length = len(section_text)
        
        if current_length + section_length <= max_chars:
            result.append(section_text)
            current_length += section_length
        else:
            # Try to include truncated version
            remaining = max_chars - current_length - len(f"## {title}\n\n[Truncated]")
            if remaining > 200:
                truncated = content[:remaining] + "\n[Truncated]"
                result.append(f"## {title}\n{truncated}")
            break
    
    return "\n\n".join(result)


def build_llm_messages(
    query: str,
    context: AssembledContext,
    user_state,
    instruction: str = ""
) -> tuple:
    """
    Build messages for LLM call.
    
    Returns:
        Tuple of (system_prompt, user_message, history)
    """
    # Build user message with context
    user_message_parts = []
    
    if context.user_context:
        user_message_parts.append(f"CONTEXT:\n{context.user_context}\n")
    
    if instruction:
        user_message_parts.append(f"INSTRUCTION: {instruction}\n")
    
    user_message_parts.append(f"USER: {query}")
    
    user_message = "\n".join(user_message_parts)
    
    # Get history from state
    history = []
    if hasattr(user_state, 'history') and user_state.history:
        for h in user_state.history[-4:]:  # Last 4 turns
            history.append({
                "role": h.get("role", "user"),
                "content": h.get("content", "")
            })
    
    return context.system_context, user_message, history
