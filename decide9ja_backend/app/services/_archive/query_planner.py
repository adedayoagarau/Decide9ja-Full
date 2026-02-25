"""
Query Planner Service
Breaks complex user queries into subtasks for parallel execution.
This is an ADDITIVE enhancement - original flow works without it.
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from dotenv import load_dotenv
load_dotenv()

from anthropic import Anthropic

logger = logging.getLogger(__name__)

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


class SubtaskType(str, Enum):
    """Types of subtasks the planner can create."""
    POLITICIAN_LOOKUP = "politician_lookup"
    REPRESENTATIVE_LOOKUP = "representative_lookup"
    ISSUE_LOOKUP = "issue_lookup"
    NEWS_SEARCH = "news_search"
    RAG_SEARCH = "rag_search"
    DIRECT_ANSWER = "direct_answer"


@dataclass
class Subtask:
    """A single subtask in the query plan."""
    type: SubtaskType
    query: str
    params: Dict[str, Any]
    priority: int = 1  # 1 = high, 2 = medium, 3 = low
    depends_on: List[str] = None  # IDs of dependent subtasks
    
    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = []


@dataclass
class QueryPlan:
    """A plan for executing a complex query."""
    original_query: str
    is_complex: bool
    subtasks: List[Subtask]
    response_format: str  # "combined", "sequential", "single"
    

PLANNER_PROMPT = """You are a query planner for Decide9ja, a Nigerian political information system.

Given a user query, determine if it's a simple or complex query, and break complex queries into subtasks.

AVAILABLE SUBTASK TYPES:
- politician_lookup: Find info about a specific politician by name
- representative_lookup: Find representatives for a location (needs state/LGA)
- issue_lookup: Find political issues (optionally by politician or domain)
- news_search: Search recent news (optionally by politician or topic)
- rag_search: Search knowledge base for general political info
- direct_answer: Query can be answered directly without lookups

EXAMPLES:

Query: "Who is Tinubu?"
→ Simple query, single subtask
{
  "is_complex": false,
  "subtasks": [{"type": "politician_lookup", "query": "Tinubu", "params": {"name": "Tinubu"}}]
}

Query: "Who is my senator and what issues is he linked to?"
→ Complex query, needs sequential subtasks
{
  "is_complex": true,
  "subtasks": [
    {"type": "representative_lookup", "query": "find senator", "params": {"level": "federal"}, "priority": 1},
    {"type": "issue_lookup", "query": "issues for senator", "params": {"by_politician": true}, "priority": 2, "depends_on": ["0"]}
  ]
}

Query: "What's happening with power outages in Lagos?"
→ Complex query, parallel subtasks
{
  "is_complex": true,
  "subtasks": [
    {"type": "issue_lookup", "query": "power issues Lagos", "params": {"domain": "power", "state": "Lagos"}, "priority": 1},
    {"type": "news_search", "query": "power outage Lagos", "params": {"topic": "power", "state": "Lagos"}, "priority": 1}
  ]
}

Now analyze this query:
USER QUERY: {query}
USER CONTEXT: {context}

Respond with ONLY valid JSON matching the format above. Include "response_format": "combined" for parallel, "sequential" for dependent, or "single" for simple queries."""


def is_complex_query(query: str) -> bool:
    """Quick heuristic check if query might be complex."""
    complex_indicators = [
        " and ", " also ", " what about ",
        "issues", "news", "latest",
        "linked to", "related to",
        "my senator", "my representative",
        "happening", "going on"
    ]
    query_lower = query.lower()
    return any(indicator in query_lower for indicator in complex_indicators)


async def plan_query(
    query: str,
    user_context: Optional[Dict] = None,
) -> QueryPlan:
    """
    Analyze a query and create an execution plan.
    
    Args:
        query: User's original query
        user_context: Optional context (location, previous entities, etc.)
        
    Returns:
        QueryPlan with subtasks
    """
    from app.services.json_utils import extract_json, QUERY_PLAN_DEFAULTS
    
    # Quick check - if clearly simple, skip LLM call
    if not is_complex_query(query) and len(query.split()) < 8:
        return QueryPlan(
            original_query=query,
            is_complex=False,
            subtasks=[Subtask(
                type=SubtaskType.RAG_SEARCH,
                query=query,
                params={}
            )],
            response_format="single"
        )
    
    try:
        context_str = json.dumps(user_context or {})
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            temperature=0,
            messages=[{
                "role": "user",
                "content": PLANNER_PROMPT.format(query=query, context=context_str)
            }]
        )
        
        # Use unified JSON parser
        result = extract_json(response.content[0].text, default=QUERY_PLAN_DEFAULTS)
        
        subtasks = []
        for i, st in enumerate(result.get("subtasks", [])):
            subtasks.append(Subtask(
                type=SubtaskType(st.get("type", "rag_search")),
                query=st.get("query", query),
                params=st.get("params", {}),
                priority=st.get("priority", 1),
                depends_on=st.get("depends_on", [])
            ))
        
        return QueryPlan(
            original_query=query,
            is_complex=result.get("is_complex", False),
            subtasks=subtasks or [Subtask(type=SubtaskType.RAG_SEARCH, query=query, params={})],
            response_format=result.get("response_format", "single")
        )
        
    except Exception as e:
        logger.warning(f"Query planning failed, using default: {e}")
        return QueryPlan(
            original_query=query,
            is_complex=False,
            subtasks=[Subtask(type=SubtaskType.RAG_SEARCH, query=query, params={})],
            response_format="single"
        )


def _parse_plan_response(text: str) -> Dict:
    """Parse the planner response with robust JSON extraction."""
    import re
    text = text.strip()
    
    # Fix Python-style booleans first
    text = text.replace("True", "true").replace("False", "false").replace("None", "null")
    
    # Strategy 1: Try direct parse
    try:
        return json.loads(text)
    except:
        pass
    
    # Strategy 2: Extract from markdown code block
    json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
    if json_match:
        try:
            content = json_match.group(1)
            content = content.replace("True", "true").replace("False", "false")
            return json.loads(content)
        except:
            pass
    
    # Strategy 3: Find first JSON object
    json_match = re.search(r'\{[^{}]*(?:"[^"]*"[^{}]*)*\}', text)
    if json_match:
        try:
            content = json_match.group(0)
            content = content.replace("True", "true").replace("False", "false")
            return json.loads(content)
        except:
            pass
    
    # Strategy 4: Try to find nested JSON
    start = text.find('{')
    if start >= 0:
        depth = 0
        for i, c in enumerate(text[start:], start):
            if c == '{': depth += 1
            elif c == '}': depth -= 1
            if depth == 0:
                try:
                    content = text[start:i+1]
                    content = content.replace("True", "true").replace("False", "false")
                    return json.loads(content)
                except:
                    break
    
    return {"is_complex": False, "subtasks": [], "response_format": "single"}


def plan_query_sync(query: str, user_context: Optional[Dict] = None) -> QueryPlan:
    """Synchronous wrapper for plan_query."""
    import asyncio
    return asyncio.run(plan_query(query, user_context))


# Test
if __name__ == "__main__":
    test_queries = [
        "Who is Tinubu?",
        "Who is my senator and what issues is he linked to?",
        "What's happening with power outages in Lagos?",
        "Tell me about the fuel scarcity"
    ]
    
    for q in test_queries:
        plan = plan_query_sync(q)
        print(f"\nQuery: {q}")
        print(f"  Complex: {plan.is_complex}")
        print(f"  Subtasks: {len(plan.subtasks)}")
        for st in plan.subtasks:
            print(f"    - {st.type}: {st.query}")
