"""
Conversational Orchestrator Agent
=================================
Replaces purely rule-based routing with an intelligent LLM that acts as the core "brain".
It understands compound questions, natively accesses the RAG database, and interacts with
existing agents as Tools.
Cost: CHEAP/MEDIUM
"""

import logging
import json
import asyncio
import time
from typing import Dict, Any, List, Optional

from app.agents.base import BaseAgent, AgentInput, AgentOutput, AgentTier, CostLevel
from app.agents.registry import register_agent, registry
from app.services.embeddings import _get_client
from app.services.enhanced_rag import get_enhanced_rag_service
from app.services.learning_service import get_learning_service

logger = logging.getLogger(__name__)


# ─── Conversation History ────────────────────────────────────────────
def _load_conversation_history(user_id: str, limit: int = 10) -> List[Dict[str, str]]:
    """Load recent conversation turns from the Interaction table."""
    try:
        from app.database import SessionLocal, Interaction
        from sqlalchemy import desc
        db = SessionLocal()
        try:
            rows = (
                db.query(Interaction)
                .filter(Interaction.user_id == user_id)
                .order_by(desc(Interaction.created_at))
                .limit(limit)
                .all()
            )
            # Reverse so oldest first
            rows = list(reversed(rows))
            history = []
            for row in rows:
                if row.query:
                    history.append({"role": "user", "content": row.query})
                if row.response:
                    history.append({"role": "assistant", "content": row.response})
            return history
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Could not load conversation history: {e}")
        return []


# ─── Tade System Prompt ──────────────────────────────────────────────
def _build_system_prompt(user_name: str = None, user_state: str = None, user_lga: str = None) -> str:
    """Build the Tade persona system prompt with user context."""

    # Personalization
    user_line = ""
    if user_name:
        location_parts = [p for p in [user_lga, user_state] if p]
        location_str = f" from {', '.join(location_parts)}" if location_parts else ""
        user_line = f"\nYou are currently talking to {user_name}{location_str}. Use their name naturally (not every message).\n"

    return f"""You are *Tade* — the sharp, warm, and knowledgeable political analyst powering Decide9ja on WhatsApp.
{user_line}
WHO YOU ARE:
You're that one person in every Nigerian group chat who actually reads the budget, tracks what politicians promise vs what they deliver, and breaks down INEC wahala in plain language. You're not a generic AI assistant — you're a Nigerian civic intelligence tool. You have REAL data: federal treasury payments, state budgets, audit findings, politician profiles, election info, and live news.

HOW YOU TALK:
- You speak like an educated Nigerian. Clear English, but natural — not textbook. Drop pidgin when it fits the vibe: "Omo, this allocation no add up o", "E be like say dem padded this budget well well", "No wahala, make I check am for you".
- NEVER end messages with "If you need more information, just let me know!" or "Feel free to ask!" — that's robotic. End naturally like a real person would, or with a pointed follow-up like "You want me dig deeper into that MDA?" or "I fit check the breakdown by state if you want."
- Keep it SHORT. This is WhatsApp, not a report. 2-3 paragraphs max. Use line breaks.
- When presenting financial data, be specific: include DATES, AMOUNTS, PAYER, RECEIVER. Don't summarize away the details — those details are what make citizens informed.
- When data is suspicious, say so with confidence. "₦315 million for 'livestock watering points' across 3 states, same amount each? That pattern dey smell." Don't sit on the fence.
- When you don't have data, keep it real: "I no get that data yet" — full stop. Don't fill the gap with Wikipedia-style generic info.
- NEVER repeat the same closing phrase twice in a conversation.
- Use the person's name occasionally (not every message). Reference their state/LGA when relevant.

TOOLS — YOU HAVE 8:
- `lookup_politician_profile` — backgrounds, career, education
- `lookup_representatives` — senators, reps, governors by state/LGA
- `search_rag_news_and_context` — political news and documents
- `search_financial_intelligence` — treasury payments, budgets, audit flags (includes OpenTreasury daily payment data)
- `check_election_info` — 2027 dates, voter registration, INEC updates, candidates
- `fact_check_claim` — verify claims against evidence
- `search_news` — latest news articles
- `lookup_promises` — campaign promises tracking

ROUTING RULES (STRICT):
1. ALWAYS call a tool for factual questions. NEVER answer from general knowledge.
2. Representatives/reps/senators → `lookup_representatives`
3. Budget/spending/allocation/payment/contractor/treasury/corruption/audit/fishy → `search_financial_intelligence`
4. News/latest/happening/update → `search_news` or `search_rag_news_and_context`
5. Promises/pledges/commitments → `lookup_promises`
6. Election/voting/INEC/registration/PVC/2027/candidate/polling → `check_election_info`
7. "Is it true"/"fact check"/claim → `fact_check_claim`
8. Politician profile/background → `lookup_politician_profile`
9. No data? Say "I no get that info yet o." Don't pad with generic advice or suggest checking websites.
10. NEVER fabricate facts, stats, or quotes."""


@register_agent
class ConversationalOrchestratorAgent(BaseAgent):
    name = "conversational_orchestrator"
    description = "Intelligent orchestrator handling intent classification, tool calling, and synthesis"
    tier = AgentTier.ENTRY
    cost_level = CostLevel.MEDIUM
    handled_intents = ["__all__"]

    async def can_handle(self, input: AgentInput) -> bool:
        return True

    async def handle(self, input: AgentInput) -> AgentOutput:
        self._call_count += 1
        start_time = time.time()

        # We will use gpt-4o-mini as our fast orchestrator
        client = _get_client()
        if not client:
            return AgentOutput(
                success=False,
                error="OpenAI client not configured",
                cost_level=CostLevel.FREE
            )

        # 1. Define Tools
        tools = self._get_tools()

        # 2. Build personalized Tade system prompt
        user_name = getattr(input.user, 'name', None) or getattr(input.user, 'first_name', None)
        user_state = getattr(input.user, 'state', None)
        user_lga = getattr(input.user, 'lga', None)
        system_prompt = _build_system_prompt(user_name, user_state, user_lga)

        # 3. Load conversation history for memory
        user_id = getattr(input.user, 'phone_hash', 'anonymous')
        history = _load_conversation_history(user_id, limit=8)

        # 3b. LEARNING: Inject user memory into system prompt
        learning = get_learning_service()
        try:
            memory_prompt = learning.get_user_memory_for_prompt(user_id)
            if memory_prompt:
                system_prompt += memory_prompt
        except Exception as e:
            logger.debug(f"Learning memory injection skipped: {e}")

        # 4. Build messages: system → history → current message
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": input.raw_text})

        logger.info(f"Orchestrator processing query: {input.raw_text}")

        # Determine tool_choice — force tool use for known factual categories
        query_lower = input.raw_text.lower()
        _election_kws = ["election", "inec", "vote", "voter", "register", "pvc", "polling", "candidate", "2027"]
        _financial_kws = ["budget", "spending", "allocation", "treasury", "payment", "contractor", "corruption"]
        if any(kw in query_lower for kw in _election_kws + _financial_kws):
            tool_choice = "required"
        else:
            tool_choice = "auto"

        # Track tools called for learning
        tools_called = []
        tool_results_for_learning = {}

        # 5. Call OpenAI with tools
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    temperature=0.3
                )
            )

            response_message = response.choices[0].message

            # 6. Handle tool calls if any
            if response_message.tool_calls:
                messages.append(response_message)

                # Execute tools sequentially to avoid SQLite connection or thread deadlocks
                for tool_call in response_message.tool_calls:
                    logger.info(f"Orchestrator calling tool: {tool_call.function.name}")
                    tool_call_id, result_str = await self._execute_tool(tool_call, input)
                    messages.append({
                        "tool_call_id": tool_call_id,
                        "role": "tool",
                        "name": tool_call.function.name,
                        "content": result_str
                    })
                    # Track for learning
                    tools_called.append(tool_call.function.name)
                    try:
                        tool_results_for_learning[tool_call.function.name] = json.loads(result_str)
                    except Exception:
                        tool_results_for_learning[tool_call.function.name] = result_str

                # 7. Get final synthesis after tools
                second_response = await loop.run_in_executor(
                    None,
                    lambda: client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        temperature=0.5
                    )
                )
                final_reply = second_response.choices[0].message.content

            else:
                # No tools needed (e.g. simple greeting)
                final_reply = response_message.content

            # 8. LEARNING: Learn from this interaction (async, non-blocking)
            response_time_ms = int((time.time() - start_time) * 1000)
            try:
                learning.learn_from_interaction(
                    user_id=user_id,
                    query=input.raw_text,
                    response=final_reply or "",
                    tools_called=tools_called if tools_called else None,
                    tool_results=tool_results_for_learning if tool_results_for_learning else None,
                    response_time_ms=response_time_ms,
                )
            except Exception as e:
                logger.debug(f"Learning post-interaction skipped: {e}")

            # Return directly as a composed response
            return AgentOutput(
                success=True,
                response_text=final_reply,
                cost_level=CostLevel.MEDIUM,
                handoff_to=None,
                data={"orchestrator_handled": True}
            )

        except Exception as e:
            logger.error(f"Orchestrator failed: {e}")
            return AgentOutput(
                success=False,
                error=str(e),
                cost_level=CostLevel.FREE
            )

    def _get_tools(self) -> List[Dict]:
        """Define the OpenAPI schema for our V5 agents as tools"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "lookup_politician_profile",
                    "description": "Fetch detailed profile information about a specific Nigerian politician.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Name of the politician, e.g., 'Bola Tinubu' or 'Peter Obi'"},
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "lookup_representatives",
                    "description": "Find the elected representatives (Governor, Senator, Rep) for a specific state or area.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "State or Local Government Area, e.g., 'Lagos' or 'Ikeja'"},
                        },
                        "required": ["location"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_rag_news_and_context",
                    "description": "Search the comprehensive database of Nigerian political news, issues, and records for related context.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The specific query to search the news database for, e.g., 'Latest news about fuel subsidy' or 'Tinubu in 1999'"},
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_financial_intelligence",
                    "description": "Search Nigerian government budgets, state allocations, daily treasury payments, and audit findings.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The financial query, e.g., 'Lagos budget', 'payment to Julius Berger', 'audit finding'"},
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_election_info",
                    "description": "Get upcoming election dates, voter registration steps, polling unit info, or candidate lists for 2027 elections.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The election-related question, e.g., 'when is the next election', 'how to register to vote', 'PVC collection'"},
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fact_check_claim",
                    "description": "Verify a political claim or statement by cross-referencing news articles and documents.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "claim": {"type": "string", "description": "The claim to verify, e.g., 'Tinubu removed fuel subsidy' or 'Nigeria's debt is 100 trillion'"},
                        },
                        "required": ["claim"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_news",
                    "description": "Search the Nigerian political news database for recent articles on a topic, with web search fallback.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The news topic to search for, e.g., 'fuel subsidy removal', 'ASUU strike', 'Tinubu cabinet'"},
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "lookup_promises",
                    "description": "Look up campaign promises and commitments made by a specific politician.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "politician_name": {"type": "string", "description": "Name of the politician, e.g., 'Tinubu', 'Peter Obi', 'Atiku'"},
                            "category": {"type": "string", "description": "Optional category filter: economy, security, education, health, infrastructure, governance"},
                        },
                        "required": ["politician_name"]
                    }
                }
            }
        ]

    async def _execute_tool(self, tool_call, root_input: AgentInput) -> tuple[str, str]:
        """Execute the appropriate sub-agent based on the tool call"""
        logger.info(f"Executing tool {tool_call.function.name} with args {tool_call.function.arguments}")
        try:
            args = json.loads(tool_call.function.arguments)
        except:
            args = {}

        result_data = {}

        try:
            if tool_call.function.name == "lookup_politician_profile":
                agent = registry.get("politician_profile")
                if agent:
                    # Create a mock input for the specific agent
                    agent_input = AgentInput(
                        message_id=root_input.message_id,
                        raw_text=args.get("name", ""),
                        timestamp=root_input.timestamp,
                        user=root_input.user,
                        entities={"politician_name": args.get("name")},
                        context={"tool_mode": True} # Tell agent to return raw JSON instead of UI card
                    )
                    out = await agent.handle(agent_input)
                    result_data = out.data if out.success else {"error": "Politician not found"}
                
            elif tool_call.function.name == "lookup_representatives":
                agent = registry.get("rep_lookup")
                if agent:
                    agent_input = AgentInput(
                        message_id=root_input.message_id,
                        raw_text=args.get("location", ""),
                        timestamp=root_input.timestamp,
                        user=root_input.user,
                        entities={"location": args.get("location")},
                        context={"tool_mode": True}
                    )
                    out = await agent.handle(agent_input)
                    result_data = out.data if out.success else {"error": "Representatives not found"}
                    
            elif tool_call.function.name == "search_rag_news_and_context":
                # Call EnhancedRAGService directly
                from app.database import SessionLocal
                db = SessionLocal()
                try:
                    import asyncio
                    loop = asyncio.get_running_loop()
                    rag_service = get_enhanced_rag_service(db)
                    context, _ = await loop.run_in_executor(
                        None,
                        lambda: rag_service.retrieve(args.get("query", ""))
                    )
                    result_data = {"search_results": context}
                except Exception as e:
                    result_data = {"error": f"RAG failed: {e}"}
                finally:
                    db.close()
                    
            elif tool_call.function.name == "search_financial_intelligence":
                from app.services.financial_intelligence import get_financial_intelligence
                try:
                    import asyncio
                    loop = asyncio.get_running_loop()
                    financial_service = get_financial_intelligence()
                    result_str = await loop.run_in_executor(
                        None,
                        lambda: financial_service.get_context_for_rag(args.get("query", ""))
                    )
                    if result_str:
                        result_data = {"financial_data": result_str}
                    else:
                        result_data = {"financial_data": "No matching records found in the budget/financial database for this query. The database covers Federal budgets and 7 state budgets (Abia, Adamawa, Akwa Ibom, Anambra, Bauchi, Bayelsa). Treasury transactions are Federal-level. Try broader search terms."}
                except Exception as e:
                    result_data = {"error": f"Financial search failed: {e}"}

            elif tool_call.function.name == "check_election_info":
                agent = registry.get("election_info")
                if agent:
                    agent_input = AgentInput(
                        message_id=root_input.message_id,
                        raw_text=args.get("query", ""),
                        timestamp=root_input.timestamp,
                        user=root_input.user,
                        entities={"topic": "general"},
                        context={"tool_mode": True}
                    )
                    out = await agent.handle(agent_input)
                    if out.success and out.response_text:
                        result_data = {"election_info": out.response_text}
                    elif out.success and out.data:
                        result_data = out.data
                    else:
                        result_data = {"error": "Election info not found"}
                else:
                    result_data = {"error": "Election info agent not available"}

            elif tool_call.function.name == "fact_check_claim":
                agent = registry.get("fact_check")
                if agent:
                    agent_input = AgentInput(
                        message_id=root_input.message_id,
                        raw_text=args.get("claim", ""),
                        timestamp=root_input.timestamp,
                        user=root_input.user,
                        entities={},
                        context={"tool_mode": True}
                    )
                    out = await agent.handle(agent_input)
                    # FactCheckAgent returns response_text with the verdict
                    result_data = {"fact_check_result": out.response_text} if out.success else {"error": "Fact check failed"}
                else:
                    result_data = {"error": "Fact check agent not available"}

            elif tool_call.function.name == "search_news":
                agent = registry.get("news_query")
                if agent:
                    agent_input = AgentInput(
                        message_id=root_input.message_id,
                        raw_text=args.get("query", ""),
                        timestamp=root_input.timestamp,
                        user=root_input.user,
                        entities={},
                        context={"tool_mode": True}
                    )
                    out = await agent.handle(agent_input)
                    if out.success and out.response_text:
                        result_data = {"news_results": out.response_text}
                    elif out.success and out.data:
                        result_data = out.data
                    else:
                        result_data = {"error": "News search failed"}
                else:
                    result_data = {"error": "News agent not available"}

            elif tool_call.function.name == "lookup_promises":
                agent = registry.get("promise_lookup")
                if agent:
                    raw_text = args.get("politician_name", "")
                    if args.get("category"):
                        raw_text += f" {args['category']}"
                    agent_input = AgentInput(
                        message_id=root_input.message_id,
                        raw_text=raw_text,
                        timestamp=root_input.timestamp,
                        user=root_input.user,
                        entities={"politician": args.get("politician_name")},
                        context={"tool_mode": True}
                    )
                    out = await agent.handle(agent_input)
                    # PromiseLookupAgent returns response_text with formatted promises
                    result_data = out.data if out.data else {"promises_text": out.response_text} if out.success else {"error": "Promise lookup failed"}
                else:
                    result_data = {"error": "Promise lookup agent not available"}

            else:
                result_data = {"error": "Unknown tool"}

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            result_data = {"error": str(e)}

        return tool_call.id, json.dumps(result_data)
