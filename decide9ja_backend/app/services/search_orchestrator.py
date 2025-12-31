"""
Search Orchestrator Service
Executes query plans with parallel/sequential subtask execution.
This is an ADDITIVE enhancement - uses existing services without modifying them.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from app.services.query_planner import QueryPlan, Subtask, SubtaskType

logger = logging.getLogger(__name__)


@dataclass
class SubtaskResult:
    """Result of executing a subtask."""
    subtask_type: SubtaskType
    success: bool
    data: Any
    error: Optional[str] = None


@dataclass
class OrchestrationResult:
    """Combined results from orchestration."""
    original_query: str
    results: List[SubtaskResult]
    combined_context: str  # Formatted for LLM consumption
    

# Thread pool for parallel execution
executor = ThreadPoolExecutor(max_workers=4)


async def execute_plan(plan: QueryPlan, user_context: Optional[Dict] = None) -> OrchestrationResult:
    """
    Execute a query plan, running subtasks in parallel where possible.
    
    Args:
        plan: QueryPlan from the planner
        user_context: Optional user context (location, etc.)
        
    Returns:
        OrchestrationResult with all subtask results
    """
    if not plan.subtasks:
        return OrchestrationResult(
            original_query=plan.original_query,
            results=[],
            combined_context=""
        )
    
    # Group subtasks by priority/dependencies
    independent = [st for st in plan.subtasks if not st.depends_on]
    dependent = [st for st in plan.subtasks if st.depends_on]
    
    results = []
    
    # Execute independent subtasks in parallel
    if independent:
        tasks = [_execute_subtask(st, user_context, {}) for st in independent]
        parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, res in enumerate(parallel_results):
            if isinstance(res, Exception):
                results.append(SubtaskResult(
                    subtask_type=independent[i].type,
                    success=False,
                    data=None,
                    error=str(res)
                ))
            else:
                results.append(res)
    
    # Build context from results for dependent subtasks
    result_context = _build_result_context(results)
    
    # Execute dependent subtasks sequentially
    for st in dependent:
        res = await _execute_subtask(st, user_context, result_context)
        results.append(res)
    
    # Combine all results into context string
    combined = _format_combined_context(results, plan.original_query)
    
    return OrchestrationResult(
        original_query=plan.original_query,
        results=results,
        combined_context=combined
    )


async def _execute_subtask(
    subtask: Subtask,
    user_context: Optional[Dict],
    previous_results: Dict
) -> SubtaskResult:
    """Execute a single subtask using existing services."""
    try:
        data = None
        
        if subtask.type == SubtaskType.POLITICIAN_LOOKUP:
            data = await _lookup_politician(subtask.params, user_context)
            
        elif subtask.type == SubtaskType.REPRESENTATIVE_LOOKUP:
            data = await _lookup_representative(subtask.params, user_context)
            
        elif subtask.type == SubtaskType.ISSUE_LOOKUP:
            data = await _lookup_issues(subtask.params, user_context, previous_results)
            
        elif subtask.type == SubtaskType.NEWS_SEARCH:
            data = await _search_news(subtask.params, user_context)
            
        elif subtask.type == SubtaskType.RAG_SEARCH:
            data = await _search_rag(subtask.query, user_context)
            
        elif subtask.type == SubtaskType.DIRECT_ANSWER:
            data = {"answer": subtask.query}
        
        return SubtaskResult(
            subtask_type=subtask.type,
            success=data is not None,
            data=data
        )
        
    except Exception as e:
        logger.error(f"Subtask {subtask.type} failed: {e}")
        return SubtaskResult(
            subtask_type=subtask.type,
            success=False,
            data=None,
            error=str(e)
        )


# ===========================================
# SUBTASK EXECUTORS (Use existing services)
# ===========================================

async def _lookup_politician(params: Dict, context: Optional[Dict]) -> Optional[Dict]:
    """Look up politician info using existing politician service."""
    from app.database import SessionLocal, Politician
    
    name = params.get("name", "")
    if not name:
        return None
    
    db = SessionLocal()
    try:
        # Search by name (partial match)
        politician = db.query(Politician).filter(
            Politician.name.ilike(f"%{name}%")
        ).first()
        
        if politician:
            return {
                "slug": politician.slug,
                "name": politician.name,
                "party": politician.party,
                "position": politician.position,
                "state": politician.state,
                "bio": politician.bio,
            }
        return None
    finally:
        db.close()


async def _lookup_representative(params: Dict, context: Optional[Dict]) -> Optional[Dict]:
    """Look up representatives using existing services."""
    from app.database import SessionLocal, Politician
    
    # Get location from context or params
    state = params.get("state") or (context or {}).get("state")
    lga = params.get("lga") or (context or {}).get("lga")
    level = params.get("level", "all")
    
    if not state:
        return {"error": "No location provided", "need_location": True}
    
    db = SessionLocal()
    try:
        query = db.query(Politician).filter(Politician.state.ilike(f"%{state}%"))
        
        if level == "federal":
            query = query.filter(Politician.position.ilike("%senator%") | 
                                Politician.position.ilike("%representative%"))
        
        reps = query.limit(5).all()
        
        return {
            "state": state,
            "representatives": [
                {"name": r.name, "position": r.position, "party": r.party}
                for r in reps
            ]
        }
    finally:
        db.close()


async def _lookup_issues(
    params: Dict,
    context: Optional[Dict],
    previous_results: Dict
) -> Optional[Dict]:
    """Look up issues using existing issue pipeline."""
    from app.services.issue_pipeline import list_issues, get_issues_for_politician
    
    # Check if we should look up by politician from previous results
    if params.get("by_politician") and previous_results:
        # Get politician from previous lookup
        pol_data = previous_results.get("politician_lookup")
        if pol_data and pol_data.get("slug"):
            issues = get_issues_for_politician(pol_data["slug"])
            return {"issues": issues[:5], "politician": pol_data.get("name")}
    
    # Otherwise look up by domain/state
    domain = params.get("domain")
    state = params.get("state") or (context or {}).get("state")
    
    issues = list_issues(domain=domain, state=state, limit=5)
    return {"issues": issues, "domain": domain, "state": state}


async def _search_news(params: Dict, context: Optional[Dict]) -> Optional[Dict]:
    """Search news using existing news pipeline."""
    from app.services.news_pipeline import get_recent_news
    
    topic = params.get("topic")
    politician = params.get("politician")
    hours = params.get("hours", 72)
    
    news = get_recent_news(hours=hours, politician=politician, topic=topic, limit=5)
    return {"articles": news, "topic": topic or politician}


async def _search_rag(query: str, context: Optional[Dict]) -> Optional[Dict]:
    """Search RAG using existing service."""
    from app.services.rag import retrieve
    
    context_text = retrieve(query)
    return {"context": context_text}


# ===========================================
# RESULT FORMATTING
# ===========================================

def _build_result_context(results: List[SubtaskResult]) -> Dict:
    """Build context from completed results for dependent subtasks."""
    context = {}
    for res in results:
        if res.success and res.data:
            context[res.subtask_type.value] = res.data
    return context


def _format_combined_context(results: List[SubtaskResult], query: str) -> str:
    """Format all results into a context string for LLM."""
    parts = [f"Query: {query}\n"]
    
    for res in results:
        if not res.success:
            continue
            
        if res.subtask_type == SubtaskType.POLITICIAN_LOOKUP and res.data:
            p = res.data
            parts.append(f"\n**Politician Found:**")
            parts.append(f"- Name: {p.get('name')}")
            parts.append(f"- Party: {p.get('party')}")
            parts.append(f"- Position: {p.get('position')}")
            if p.get('bio'):
                parts.append(f"- Bio: {p.get('bio')[:200]}...")
                
        elif res.subtask_type == SubtaskType.REPRESENTATIVE_LOOKUP and res.data:
            r = res.data
            parts.append(f"\n**Representatives for {r.get('state')}:**")
            for rep in r.get('representatives', [])[:3]:
                parts.append(f"- {rep['name']} ({rep['party']}) - {rep['position']}")
                
        elif res.subtask_type == SubtaskType.ISSUE_LOOKUP and res.data:
            i = res.data
            parts.append(f"\n**Related Issues:**")
            for issue in i.get('issues', [])[:3]:
                parts.append(f"- [{issue.get('severity', 'moderate').upper()}] {issue.get('title')}")
                
        elif res.subtask_type == SubtaskType.NEWS_SEARCH and res.data:
            n = res.data
            parts.append(f"\n**Recent News:**")
            for article in n.get('articles', [])[:3]:
                parts.append(f"- {article.get('title')} ({article.get('source')})")
                
        elif res.subtask_type == SubtaskType.RAG_SEARCH and res.data:
            parts.append(f"\n**Knowledge Base:**")
            parts.append(res.data.get('context', '')[:500])
    
    return "\n".join(parts)


def execute_plan_sync(plan: QueryPlan, user_context: Optional[Dict] = None) -> OrchestrationResult:
    """Synchronous wrapper."""
    return asyncio.run(execute_plan(plan, user_context))


# Test
if __name__ == "__main__":
    from app.services.query_planner import plan_query_sync
    
    test_query = "Who is Tinubu and what issues is he linked to?"
    plan = plan_query_sync(test_query)
    
    print(f"Plan: {len(plan.subtasks)} subtasks")
    
    result = execute_plan_sync(plan)
    print(f"\nCombined Context:\n{result.combined_context}")
