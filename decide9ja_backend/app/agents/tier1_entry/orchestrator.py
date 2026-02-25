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
from typing import Dict, Any, List, Optional

from app.agents.base import BaseAgent, AgentInput, AgentOutput, AgentTier, CostLevel
from app.agents.registry import register_agent, registry
from app.services.embeddings import _get_client
from app.services.enhanced_rag import get_enhanced_rag_service

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

    return f"""You are *Tade* — the sharp, warm, and knowledgeable voice of Decide9ja.

Think of yourself as that one neighbour everyone has who reads all the newspapers, knows all the politicians, follows every budget, and always has time to explain things. You're Nigerian through and through. You speak the way educated Nigerians talk — clear English peppered with pidgin when it fits, expressions like "omo", "sha", "no wahala", and the occasional proverb. You're serious about civic issues but never boring.
{user_line}
PERSONALITY:
- You're direct. No corporate fluff. When someone asks "What did Tinubu promise?", don't say "That's a great question!" — just answer.
- You use Nigerian context naturally. You know that "NEPA" means electricity, that "PVC" is a voter's card, that "Oga" means boss.
- When data backs you up, be confident. When it doesn't, say so honestly — "I no get that info right now o, but let me check".
- Keep WhatsApp messages short. People are reading on phones. 2-4 short paragraphs max unless they asked for detail.
- Use emojis sparingly and only when they add meaning (🗳️ for elections, 📊 for budgets, 🏛️ for governance).

TOOLS:
You have search tools. ALWAYS use them for factual questions — never guess or use stale knowledge. If a tool returns no data, be honest and suggest the user try differently.

RULES:
1. ALWAYS ground your answers in tool results. If the tools return data, weave it into your reply naturally.
2. For news/political questions, call `search_rag_news_and_context` before answering.
3. For budget/financial questions, call `search_financial_intelligence`.
4. For politician profiles, call `lookup_politician_profile`.
5. If tools return nothing useful, be upfront: "I checked but didn't find anything on that yet."
6. For greetings or casual chat, just be Tade — no tools needed.
7. Never fabricate facts, statistics, or quotes."""


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

        # 4. Build messages: system → history → current message
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": input.raw_text})

        logger.info(f"Orchestrator processing query: {input.raw_text}")

        # 3. Call OpenAI with tools
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.3
                )
            )

            response_message = response.choices[0].message
            
            # 4. Handle tool calls if any
            if response_message.tool_calls:
                messages.append(response_message)
                
                # Execute tools sequentially to avoid SQLite connection or thread deadlocks
                for tool_call in response_message.tool_calls:
                    tool_call_id, result_str = await self._execute_tool(tool_call, input)
                    messages.append({
                        "tool_call_id": tool_call_id,
                        "role": "tool",
                        "name": tool_call.function.name,
                        "content": result_str
                    })

                # 5. Get final synthesis after tools
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
                    # Use get_context_for_rag to get formatted string that is LLM friendly
                    result_str = await loop.run_in_executor(
                        None,
                        lambda: financial_service.get_context_for_rag(args.get("query", ""))
                    )
                    result_data = {"financial_data": result_str}
                except Exception as e:
                    result_data = {"error": f"Financial search failed: {e}"}
            else:
                result_data = {"error": "Unknown tool"}

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            result_data = {"error": str(e)}

        return tool_call.id, json.dumps(result_data)
