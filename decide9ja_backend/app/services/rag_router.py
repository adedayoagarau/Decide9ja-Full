"""
RAG Router Service - The "Brain" of the Retrieval System.
Implements the "Small Models, Big Results" pattern from Google Research.

This service:
1. Classification: Uses a small, fast LLM to classify user intent.
2. Routing: Directs queries to specialized handlers (Budget, Bills, Elections, Legislators, etc.).
3. Privacy: Logs anonymized queries for analytics.
"""
import json
import logging
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.services.budget_search import get_budget_service
from app.services.legislative_service import legislative_service
from app.services.elections_service import elections_service
from app.services.politician_lookup import find_politician, get_representatives
from app.services.enhanced_rag import get_enhanced_rag_service
from app.database import PrivacyLog

logger = logging.getLogger(__name__)

class Intent(str, Enum):
    BUDGET = "budget"           # "How much for health in Lagos?"
    BILL = "bill"               # "What is the status of the Student Loan Bill?"
    LEGISLATOR = "legislator"   # "Who is the senator for Borno South? Contact info?"
    ELECTION = "election"       # "Who won 2023 election? INEC news"
    GENERAL = "general"         # "Tell me about Nigeria vs Benin"
    GREETING = "greeting"       # "Hello"
    CLARIFICATION = "clarification" # "What specific details?"

class RouterOutput(BaseModel):
    intent: Intent
    entities: Dict[str, Any] = {}
    language: str = "en"
    rewritten_query: str
    filters: Dict[str, Any] = {}  # Added filters

class RAGRouter:
    def __init__(self, db: Session):
        self.db = db
        # Lazy load specialized services
        self.budget_service = get_budget_service()
        self.rag_service = get_enhanced_rag_service(db)
        # legislative_service and elections_service are imported singletons

    async def route(self, query: str, filters: Dict[str, Any] = {}, chat_history: List[Dict] = []) -> Dict[str, Any]:
        """
        Main entry point. Classifies and routes the query.
        Returns: {
            "response": str,
            "sources": List[Dict],
            "intent": str,
            "debug_info": Dict
        }
        """
        # 1. Classify Intent (Small Model)
        router_out = await self._classify_intent(query, chat_history)
        
        # Inject filters into router output
        router_out.filters = filters
        
        # 2. Log Privacy (Async/Fire-and-forget ideally)
        self._log_privacy(query, router_out)

        logger.info(f"Routing query '{query}' as {router_out.intent} (Lang: {router_out.language}) Filters: {filters}")

        # 3. Route to Handler
        handlers = {
            Intent.BUDGET: self._handle_budget,
            Intent.BILL: self._handle_bill,
            Intent.LEGISLATOR: self._handle_legislator,
            Intent.ELECTION: self._handle_election,
            Intent.GREETING: self._handle_greeting,
        }
        
        handler = handlers.get(router_out.intent, self._handle_general)
        return await handler(router_out)

    async def _classify_intent(self, query: str, history: List[Dict]) -> RouterOutput:
        """
        Uses OpenAI (gpt-4o-mini) to classify intent.
        """
        from app.services.embeddings import _get_client
        client = _get_client()
        
        if not client:
            return RouterOutput(intent=Intent.GENERAL, rewritten_query=query)

        system_prompt = """
        You are the Intent Classifier for Decide9ja, a Nigerian civic tech AI.
        Classify the user's query into one of:
        - budget: Questions about money, allocations, spending, fiscal (e.g. "budget for health", "how much allocated", "nawao for money")
        - bill: Questions about laws, legislation, acts (e.g. "student loan bill", "FOI act")
        - legislator: Questions about specific politicians, reps, senators, governors, their contact info, bio, or finding who represents an area.
        - election: Questions about voting, INEC, results, candidates, defections, election dates/news.
        - greeting: "hi", "hello", "kedu", "bawo", "sannu"
        - general: Everything else (sports, history not related to politics, random questions).
        
        Also extract key entities (state, politician_name, year, party) and detect language.
        Supported languages: English (en), Pidgin (pidgin), Hausa (hausa), Yoruba (yoruba), Igbo (igbo).
        
        Examples:
        - "Wetin be the budget?" -> intent: budget, language: pidgin
        - "Kedu onye bu governor Abia?" -> intent: legislator, language: igbo, entities: {state: "Abia"}
        - "Yaya zabe na 2023?" -> intent: election, language: hausa, entities: {year: 2023}
        - "Bawo ni tinubu se n se?" -> intent: general, language: yoruba, entities: {politician_name: "Tinubu"}
        
        Return JSON.
        """
        
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
            )
            data = json.loads(response.choices[0].message.content)
            return RouterOutput(
                intent=Intent(data.get("intent", "general")),
                entities=data.get("entities", {}),
                language=data.get("language", "en"),
                rewritten_query=query 
            )
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return RouterOutput(intent=Intent.GENERAL, rewritten_query=query)

    async def _handle_budget(self, router_out: RouterOutput):
        # Specialized logic for budget
        q = router_out.rewritten_query
        
        # Extract filters with fallback to entities
        jurisdiction = router_out.filters.get("state") or router_out.entities.get("state") or router_out.entities.get("location")
        year = router_out.filters.get("year") or router_out.entities.get("year")
        if year:
            try: year = int(year)
            except: year = None

        import asyncio
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None,
            lambda: self.budget_service.search(
                q, 
                limit=5,
                jurisdiction=jurisdiction,
                year=year
            )
        )
        context = results.to_context_string()
        response_text = await self._synthesize_answer(q, context, "Budget Analyst")
        return {
            "response": response_text,
            "sources": [], 
            "context": context,
            "intent": Intent.BUDGET
        }

    async def _handle_bill(self, router_out: RouterOutput):
        # Specialized logic for bills
        q = router_out.rewritten_query
        # Try specific title search first, then general
        bills = legislative_service.get_bill_by_title(q)
        formatted = legislative_service.format_bills_list(bills)
        
        # If we have results, use them as context
        if not bills:
            # Fallback to general RAG if specific bill search fails but intent was bill
            # or try finding by sponsor if entity detected
            if router_out.entities.get("politician_name"):
                 bills = legislative_service.get_bills_by_sponsor(politician_name=router_out.entities["politician_name"])
                 formatted = legislative_service.format_bills_list(bills)
        
        response_text = await self._synthesize_answer(q, formatted, "Legislative Assistant")
        return {
            "response": response_text,
            "sources": [],
            "context": formatted,
            "intent": Intent.BILL
        }

    async def _handle_legislator(self, router_out: RouterOutput):
        # Specialized logic for legislators
        q = router_out.rewritten_query
        entities = router_out.entities
        
        # Merge frontend filters with extracted entities
        state_filter = router_out.filters.get("state") or entities.get("state")
        
        context = ""
        
        # Case 1: Finding a rep for a location ("Who is rep for Ikeja?")
        if "state" in q.lower() or "rep" in q.lower() or state_filter:
            state = state_filter # logic to extract state/lga needs to be robust
            if state:
                reps = await get_representatives(state)
                # Format reps
                formatted = f"Representatives for {state}:\n"
                for r in reps:
                    formatted += f"- {r.get('name')} ({r.get('position')}): {r.get('party')}\n"
                context = formatted
        
        # Case 2: Specific politician info ("Contact for Tinubu")
        name = entities.get("politician_name")
        if not name:
            # Try to infer name from query if entity extraction failed
            name = q 
        
        if name:
            match = await find_politician(name, db=self.db)
            if match.confidence > 0.6:
                p = match.politician
                context += f"\nInfo for {p['name']}:\n"
                context += f"Position: {p['position']}\nParty: {p['party']}\nState: {p['state']}\n"
                if p.get('phone'): context += f"Phone: {p['phone']}\n"
                if p.get('email'): context += f"Email: {p['email']}\n"
                
                # Get legislative summary too
                leg_sum = legislative_service.get_legislative_summary(politician_id=p['id'])
                if leg_sum:
                    context += f"Bills Sponsored: {leg_sum.bills_sponsored}\n"

        if not context:
            context = "No specific legislator records found in database."
            
        response_text = await self._synthesize_answer(q, context, "Parliamentary Assistant")
        return {
            "response": response_text,
            "sources": [],
            "context": context,
            "intent": Intent.LEGISLATOR
        }

    async def _handle_election(self, router_out: RouterOutput):
        # Specialized logic for elections
        q = router_out.rewritten_query
        entities = router_out.entities
        
        # Merge frontend filters
        year = router_out.filters.get("year") or entities.get("year", 2023)
        try: year = int(year)
        except: year = 2023
        
        state_filter = router_out.filters.get("state") or entities.get("state")
        party_filter = router_out.filters.get("party") or entities.get("party")
        
        context = ""
        
        # 1. Check Historical Results
        if "result" in q.lower() or "won" in q.lower():
            if "president" in q.lower():
                results = elections_service.get_presidential_results(year)
                context += elections_service.format_presidential_results(results, year)
            elif state_filter:
                results = elections_service.get_state_results(state_filter, year)
                context += elections_service.format_state_results(results, state_filter)
                
        # 2. Check Party Performance
        if party_filter:
             perf = elections_service.get_party_performance(party_filter, year)
             context += elections_service.format_party_performance(perf)
             
        # 3. Fallback/Supplement with RAG for News (Defections, INEC updates)
        # Election news is best retrieved via the General RAG but filtered for "election" topic
        rag_context, _ = self.rag_service.retrieve(q) # This searches news_articles too
        context += "\n\n=== RECENT ELECTION NEWS ===\n" + rag_context

        response_text = await self._synthesize_answer(q, context, "Election Analyst")
        return {
            "response": response_text,
            "sources": [],
            "context": context,
            "intent": Intent.ELECTION
        }

    async def _handle_greeting(self, router_out: RouterOutput):
        return {
            "response": "Hello! I am your Decide9ja assistant. You can ask me about budgets, bills, elections, or find your representatives.", 
            "sources": [],
            "context": "",
            "intent": Intent.GREETING
        }

    async def _handle_general(self, router_out: RouterOutput):
        # Fallback to existing Enhanced RAG
        # Pass language hint if possible
        import asyncio
        loop = asyncio.get_running_loop()
        
        context, sources = await loop.run_in_executor(
            None,
            lambda: self.rag_service.retrieve(
                router_out.rewritten_query, 
                language=router_out.language,
                filters=router_out.filters  # Pass state/party filters
            )
        )
        
        # Synthesize
        response_text = await self._synthesize_answer(router_out.rewritten_query, context, "Civic Assistant")
        return {
            "response": response_text, 
            "sources": sources, 
            "context": context,
            "intent": router_out.intent
        }

    async def _synthesize_answer(self, query, context, persona):
        # Simple generation
        from app.services.embeddings import _get_client
        client = _get_client()
        if not context: return f"I couldn't find specific information on that in the {persona} database."
        
        import asyncio
        loop = asyncio.get_running_loop()
        
        resp = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="gpt-4o-mini", # Fast, cheap model
                messages=[
                    {"role": "system", "content": f"You are a helpful {persona}. Answer based STRICTLY on the context provided. If the answer isn't there, say so.\n\nContext:\n{context}"},
                    {"role": "user", "content": query}
                ]
            )
        )
        return resp.choices[0].message.content

    def _log_privacy(self, query: str, router_out: RouterOutput):
        try:
            # Privacy Log (Strip PII - simple naive implementation for now)
            clean_query = query # Placeholder for PII stripping
            
            log = PrivacyLog(
                log_id=f"log-{hash(query)}", # Simple ID
                anonymized_query=clean_query,
                intent_category=router_out.intent.value,
                language=router_out.language
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.warning(f"Privacy logging failed: {e}")

def get_rag_router(db: Session):
    return RAGRouter(db)
