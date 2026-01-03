"""
Message Handler V4 — Claude-First Architecture

Key changes from V3:
1. Uses Claude for intent classification (not regex)
2. Claude decides retrieval strategy
3. Intelligent retrieval orchestration
4. Still maintains flow-first routing for active flows
"""
import os
import logging
from datetime import datetime
from typing import Optional

from app.models.state import UserState, ConversationFlow
from app.services.state_manager import state_manager, _get_state_async, _save_state_async
from app.services.templates import get_template, TEMPLATES, get_time_aware_greeting
from app.services.claude_understand import (
    claude_understand, 
    QueryUnderstanding, 
    Intent, 
    RetrievalStrategy
)
from app.services.intelligent_retrieval import (
    intelligent_retrieve,
    RetrievalResult,
    format_retrieval_for_context
)
from app.services.nigerian_politics import (
    get_hot_issues_context,
    get_governance_context,
    analyze_query_for_hot_issues,
    get_politician_context
)
from app.services.content_context_engine import (
    get_content_engine,
    get_query_context,
    get_today_hot_topic
)
from app.services.explainer import (
    get_explainer,
    explain,
    explain_simple
)
from app.services.election_2027.candidate_tracker import (
    get_candidate_tracker,
    get_candidate,
    follow,
    get_my_candidates,
    compare
)
from app.services.election_2027.polling_system import (
    get_polling_system,
    get_user_polls,
    submit_vote,
    get_poll_display,
    get_results_display
)
from app.services.progressive_profiling import (
    get_profile_prompt,
    update_interests_from_query,
    progressive_profiling
)

logger = logging.getLogger(__name__)

# Escape commands that reset conversation
ESCAPE_COMMANDS = {"reset", "restart", "cancel", "menu", "stop", "start over", "new"}


async def handle_message(phone: str, text: str, media_url: str = None) -> str:
    """
    Main entry point — Claude-First Architecture.
    
    Flow:
    1. Load state
    2. Check escape commands
    3. If in active flow → handle flow (skip Claude understanding)
    4. If IDLE → Claude understands → intelligent retrieval → Claude responds
    5. Save state
    """
    text = text.strip() if text else ""
    text_lower = text.lower()
    
    # ===========================================
    # STEP 1: Load State
    # ===========================================
    try:
        state = await _get_state_async(phone)
    except Exception as e:
        logger.error(f"Failed to load state: {e}")
        state = UserState(
            user_id="temp",
            phone=phone,
            flow=ConversationFlow.IDLE
        )
    
    # ===========================================
    # STEP 2: Check Escape Commands
    # ===========================================
    if text_lower in ESCAPE_COMMANDS:
        state.clear_flow()
        state.clear_context()
        await _save_state_async(state)
        return get_template("menu")
    
    # ===========================================
    # STEP 3: Add to History
    # ===========================================
    state.add_to_history("user", text)
    
    # ===========================================
    # STEP 4: Route Based on Flow State
    # Flow-first: active flows skip Claude understanding
    # ===========================================
    try:
        if state.flow == ConversationFlow.ONBOARDING:
            from app.services.flows.onboarding import handle_onboarding
            response = await handle_onboarding(state, text)
        
        elif state.flow == ConversationFlow.ISSUE_FLOW:
            response = await _handle_issue_flow(state, text, media_url)
        
        elif state.flow == ConversationFlow.CONFIRMING:
            response = await _handle_confirmation(state, text)
        
        elif state.flow == ConversationFlow.AWAITING_CLARIFY:
            response = await _handle_clarification(state, text)
        
        else:
            # IDLE state — use Claude-First architecture
            response = await handle_idle_claude_first(state, text)
    
    except Exception as e:
        logger.exception(f"Error handling message: {e}")
        response = TEMPLATES.get("error_generic", "Something went wrong. Please try again.")
    
    # ===========================================
    # STEP 5: Update State
    # ===========================================
    state.add_to_history("assistant", response)
    await _save_state_async(state)
    
    return response


async def handle_idle_claude_first(state: UserState, text: str) -> str:
    """
    Handle IDLE state using Claude-First architecture.
    
    Flow:
    1. Check if onboarding complete
    2. Claude understands the query
    3. Route to intelligent retrieval
    4. Claude generates response with context
    """
    
    # ===========================================
    # Check Onboarding
    # ===========================================
    if not state.is_onboarding_complete():
        # User hasn't completed onboarding
        from app.services.flows.onboarding import handle_onboarding
        
        # Check if this is a greeting to start onboarding
        greetings = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "start"}
        if text.lower().strip() in greetings:
            state.flow = ConversationFlow.ONBOARDING
            state.flow_step = 0
            return await handle_onboarding(state, text)
        else:
            # Prompt them to complete onboarding
            return get_template("incomplete_profile")
    
    # ===========================================
    # CLAUDE UNDERSTANDING
    # ===========================================
    understanding = await claude_understand(
        query=text,
        user_state=state.state,
        user_lga=state.lga,
        user_name=state.name,
        active_topic=state.active_politician_name
    )
    
    logger.info(f"Claude understanding: intent={understanding.intent.value}, "
                f"strategy={understanding.retrieval_strategy.value}, "
                f"confidence={understanding.confidence}")

    # ===========================================
    # PROGRESSIVE PROFILING: Track interests
    # ===========================================
    update_interests_from_query(state, text)
    state.add_topic_asked(understanding.intent.value)

    # ===========================================
    # ROUTE BY INTENT
    # ===========================================
    
    # Simple responses (no retrieval needed)
    if understanding.intent == Intent.GREETING:
        return get_time_aware_greeting(
            name=state.name,
            last_active_at=state.last_active_at,
            message_count=state.message_count
        )
    
    if understanding.intent == Intent.HELP:
        return get_template("menu")
    
    if understanding.intent == Intent.THANKS:
        return get_template("thanks_response")
    
    # Issue report — start flow
    if understanding.intent == Intent.ISSUE_REPORT:
        state.flow = ConversationFlow.ISSUE_FLOW
        state.flow_step = 0
        state.flow_data = {}
        return get_template("issue_start")
    
    # Voter registration
    if understanding.intent == Intent.VOTER_REGISTRATION:
        return get_template("voter_reg_info")

    # ===========================================
    # 2027 ELECTION SYSTEM HANDLERS
    # ===========================================

    # Follow candidate
    if understanding.intent == Intent.FOLLOW_CANDIDATE:
        candidate_name = understanding.entities.get("candidate_name", text.replace("follow", "").strip())
        return follow(state.phone, candidate_name)

    # Unfollow candidate
    if understanding.intent == Intent.UNFOLLOW_CANDIDATE:
        candidate_name = understanding.entities.get("candidate_name", text.replace("unfollow", "").strip())
        tracker = get_candidate_tracker()
        candidate = get_candidate(candidate_name)
        if candidate:
            success, message = tracker.unfollow_candidate(state.phone, candidate.id)
            return message
        return f"I couldn't find a candidate matching '{candidate_name}'."

    # My candidates (followed)
    if understanding.intent == Intent.MY_CANDIDATES:
        return get_my_candidates(state.phone)

    # Compare candidates
    if understanding.intent == Intent.COMPARE_CANDIDATES:
        candidates_list = understanding.entities.get("candidates", [])
        if not candidates_list:
            # Try to parse from text
            import re
            text_clean = re.sub(r"compare|and|vs|versus", " ", text, flags=re.IGNORECASE)
            candidates_list = [c.strip() for c in text_clean.split() if c.strip()]
        return compare(candidates_list[:4])  # Max 4 candidates

    # Candidate search (who is running)
    if understanding.intent == Intent.CANDIDATE_SEARCH:
        position = understanding.entities.get("position", "president")
        tracker = get_candidate_tracker()
        if position == "president":
            candidates = tracker.get_presidential_candidates()
            text = "🗳️ *2027 Presidential Candidates*\n\n"
            for c in candidates:
                emoji = "🟢" if c.party == "APC" else "🔴" if c.party == "PDP" else "🟡"
                incumbent = " (Incumbent)" if c.is_incumbent else ""
                text += f"{emoji} {c.name} - {c.party}{incumbent}\n"
            text += "\nSay a name for more details, or 'follow [name]' to get updates."
            return text
        else:
            state_name = understanding.entities.get("state", state.state)
            candidates = tracker.get_gubernatorial_candidates(state_name)
            if candidates:
                text = f"🗳️ *2027 {state_name} Gubernatorial Candidates*\n\n"
                for c in candidates:
                    text += f"• {c.name} ({c.party})\n"
                return text
            return f"I don't have gubernatorial candidates for {state_name} yet. Check back soon!"

    # Poll list
    if understanding.intent == Intent.POLL_LIST:
        polls = get_user_polls(user_state=state.state, user_lga=state.lga)
        if not polls:
            return "No active polls right now. Check back soon! 📊"
        text = "📊 *Available Polls*\n\n"
        for i, poll in enumerate(polls[:5], 1):
            text += f"{i}. {poll.title}\n"
        text += "\nReply with the poll number to participate."
        state.flow_data["available_polls"] = [p.id for p in polls[:5]]
        return text

    # Poll vote
    if understanding.intent == Intent.POLL_VOTE:
        # Check if we're continuing a poll vote
        poll_id = state.flow_data.get("active_poll")
        if poll_id:
            ps = get_polling_system()
            poll = ps.get_poll(poll_id)
            if poll:
                # Try to match user input to option
                try:
                    choice = int(text) - 1
                    if 0 <= choice < len(poll.options):
                        option_id = poll.options[choice].id
                        success, message = submit_vote(poll_id, option_id, state.phone, state.state)
                        state.flow_data.pop("active_poll", None)
                        if success:
                            # Show results after voting
                            results = get_results_display(poll_id)
                            return f"{message}\n\n{results}"
                        return message
                except ValueError:
                    pass
        # Start poll selection
        polls = get_user_polls(user_state=state.state, user_lga=state.lga)
        if polls:
            state.flow_data["active_poll"] = polls[0].id
            return get_poll_display(polls[0].id)
        return "No active polls right now. Check back soon! 📊"

    # Poll results
    if understanding.intent == Intent.POLL_RESULTS:
        ps = get_polling_system()
        polls = ps.get_active_polls()
        if not polls:
            return "No poll results available yet."
        # Show most popular poll results
        main_poll = next((p for p in polls if "president" in p.title.lower()), polls[0])
        return get_results_display(main_poll.id)

    # Trending topics
    if understanding.intent == Intent.TRENDING_TOPICS:
        content_engine = get_content_engine()
        hot_topics = content_engine.get_trending_today()
        text = "🔥 *Trending in Nigerian Politics*\n\n"
        for topic in hot_topics[:5]:
            text += f"• {topic['name']}: {topic['summary']}\n\n"
        text += "Ask about any topic for more details."
        return text

    # Election info
    if understanding.intent == Intent.ELECTION_INFO:
        return """🗳️ *2027 General Elections*

📅 *Key Dates:*
• Presidential/NASS: February 2027
• Governorship/State Assembly: March 2027

📌 *Current Status:*
• Campaign season begins: Late 2026
• Voter registration: Ongoing at INEC offices
• PVC collection: Check your INEC office

👥 *Key Candidates:*
• APC: President Tinubu (Incumbent)
• PDP: Atiku Abubakar (Expected)
• LP: Peter Obi (Expected)
• NNPP: Rabiu Kwankwaso (Expected)

Say 'who is running' for full candidate list.
Say 'follow [name]' to track a candidate."""

    # ===========================================
    # INTELLIGENT RETRIEVAL
    # ===========================================
    retrieval_result = await intelligent_retrieve(
        understanding=understanding,
        user_state=state.state,
        user_lga=state.lga
    )
    
    # ===========================================
    # GENERATE RESPONSE WITH CONTEXT
    # ===========================================
    return await generate_response_with_context(
        query=text,
        understanding=understanding,
        retrieval=retrieval_result,
        state=state
    )


async def generate_response_with_context(
    query: str,
    understanding: QueryUnderstanding,
    retrieval: RetrievalResult,
    state: UserState
) -> str:
    """Generate Claude response using retrieved context with Nigerian politics expertise."""

    import anthropic

    # Format context from retrieval
    context = format_retrieval_for_context(retrieval)

    # Check if query relates to hot issues and add context
    hot_issue = analyze_query_for_hot_issues(query)
    hot_issue_context = ""
    if hot_issue:
        hot_issue_context = f"\n\nRELATED HOT ISSUE ({hot_issue['category'].upper()}):\n"
        hot_issue_context += f"Issue: {hot_issue['issue']}\n"
        if isinstance(hot_issue['context'], dict):
            for key, value in hot_issue['context'].items():
                if key != 'key_players':
                    hot_issue_context += f"- {key}: {value}\n"

    # Check if query mentions a known politician
    politician_knowledge = get_politician_context(query)
    politician_context = ""
    if politician_knowledge and not retrieval.politician:
        politician_context = f"\n\nKNOWN FIGURE: {politician_knowledge.get('name', '')}\n"
        politician_context += f"Position: {politician_knowledge.get('position', '')}\n"
        politician_context += f"Party: {politician_knowledge.get('party', '')}\n"
        if 'known_for' in politician_knowledge:
            politician_context += f"Known for: {', '.join(politician_knowledge['known_for'])}\n"

    # Update state with active politician if found
    if retrieval.politician:
        state.active_politician_id = str(retrieval.politician.get("id", ""))
        state.active_politician_name = retrieval.politician.get("name", "")

    # Get context from Content Context Engine
    content_engine = get_content_engine()
    engine_context = content_engine.build_context_for_query(query)

    # Get explainer for potential analogies
    explainer = get_explainer()

    # Enhanced system prompt with Nigerian politics expertise (2026 Updated)
    system_prompt = """You are Tade, the AI assistant for Decide9ja — Nigeria's leading non-partisan civic engagement platform.

TODAY'S DATE: January 1, 2026
🔥 HOT TOPIC: The 2026 Tax Reform Laws took effect TODAY!

=== YOUR EXPERTISE ===
You are a NIGERIAN POLITICS EXPERT with deep knowledge of:
• Nigerian governance (Federal, State, LGA structure)
• All 36 states + FCT, 774 LGAs, 109 Senators, 360 House Reps
• Political parties (APC, PDP, LP, NNPP, others)
• Current administration (Tinubu government since May 2023)
• 2026 Hot issues: NEW TAX LAWS (effective today!), cost of living, naira, security, Rivers crisis
• Electoral system: INEC, PVC, 2027 elections coming
• Historical context: Fourth Republic, past presidents, key events

=== YOUR COMMUNICATION STYLE ===
You explain like NotebookLM — using:
• SIMPLE LANGUAGE: No jargon, explain like talking to your grandmother
• LOCAL ANALOGIES: Use Nigerian examples (market, NEPA, danfo, landlord, DSTV)
• RELATABLE EXAMPLES: Connect to everyday Nigerian experiences
• PIDGIN OPTION: You can explain in Pidgin if it helps

Example analogies you use:
- "VAT is like the 'change' the trader adds when you buy something"
- "It's like when your landlord changes how bills are calculated"
- "Like NEPA meter units that now run faster"
- "Think of it like DSTV changing their bouquet"

=== RESPONSE GUIDELINES ===

1. **EXPLAIN SIMPLY FIRST, DETAILS IF ASKED**
   - Start with 2-3 simple sentences
   - Offer to explain more if they want
   - Use analogies to make complex things clear

2. **NEVER SAY "I DON'T HAVE INFORMATION"** for basic questions
   - You know Nigerian politics
   - You know about the 2026 tax reform
   - You know who the president, VP, governors are
   - Use your knowledge when database is empty

3. **BE NEUTRAL ON PARTISAN ISSUES**
   - "Supporters say X, critics argue Y"
   - Don't say who is "good" or "bad"
   - Present multiple perspectives

4. **CURRENT 2026 CONTEXT**:
   - Tax Reform: NEW LAWS EFFECTIVE TODAY (Jan 1, 2026) — VAT sharing changed, new rules for businesses
   - Naira: Trading around ₦1,500-1,800 per dollar
   - Fuel: Still expensive since 2023 subsidy removal
   - Security: Mixed progress — banditry (NW), insurgency (NE)
   - Rivers crisis: Wike vs Fubara ongoing
   - 2027 Elections: 13 months away, positioning has begun

5. **BE CONCISE**: Users are on WhatsApp. 2-5 sentences, then ask if they want more.

=== EXAMPLES FOR TODAY ===

USER: What's this new tax thing?
RESPONSE: The 2026 Tax Reform Laws came into effect today! The biggest change is how VAT (the tax added when you buy things) is shared between states. Think of it like a family where they changed who contributes what to the food pot. Lagos and commercial states might keep more of what they generate, while others are worried they'll get less. Want me to explain how it affects you specifically?

USER: Will things become more expensive because of tax?
RESPONSE: Some things might adjust slightly, but basic food items like rice, beans, and vegetables are still VAT-exempt, so those shouldn't change from this law. The bigger cost increases we've been experiencing are from the Naira falling and fuel prices — those started in 2023. Shall I explain any specific item you're concerned about?

USER: Explain the tax in Pidgin
RESPONSE: Na so e be: Government don change how dem dey collect and share tax money. Before, all states dey share the money equal-equal. Now, state wey dey generate more money go keep more. That's why Lagos dey happy, but some other states dey vex. For you wey dey buy things, some prices fit adjust small, but your garri and rice no go change because of this one. Anything else wey you wan know?

USER: Who is the president?
RESPONSE: Nigeria's president is Bola Ahmed Tinubu of the APC. He's been president since May 29, 2023. His major policies include removing fuel subsidy (why fuel is expensive now) and floating the Naira (why dollar is high). The new tax reform that started today is also his government's initiative. Want to know more about any of these policies?

=== THINGS TO AVOID ===
- Don't say "I don't have information" for Nigerian politics
- Don't say "Great question!" or "I'd be happy to help!"
- Don't use big grammar when simple words work
- Don't express partisan opinions
- Don't give very long responses without asking if they want more"""

    # Combine all context
    full_context = context

    # Add Content Engine context (2026 issues, analogies, etc.)
    if engine_context.get("identified_issues"):
        full_context += "\n\n" + content_engine.format_context_for_claude(engine_context)

    if hot_issue_context:
        full_context += hot_issue_context
    if politician_context:
        full_context += politician_context

    # If retrieval failed but we know about the topic, add governance context
    if "No relevant information found" in context:
        full_context += "\n\n" + get_governance_context()

    # Add explainer analogies if available
    if engine_context.get("analogies"):
        full_context += "\n\n💡 ANALOGIES TO USE IN YOUR EXPLANATION:\n"
        for analogy in engine_context["analogies"][:3]:
            full_context += f"• {analogy}\n"

    user_prompt = f"""Answer this user's question using your Nigerian politics expertise and any retrieved context.

USER INFO: {state.name or "Friend"} from {state.lga or "Unknown LGA"}, {state.state or "Nigeria"}

QUESTION: {query}

INTENT: {understanding.intent.value}

RETRIEVED CONTEXT:
{full_context}

---

IMPORTANT: If the retrieved context is empty or says "No relevant information", use your built-in knowledge about Nigerian politics to answer. You are an expert — act like one.

Provide a helpful, concise response (2-5 sentences). End with a relevant follow-up question or suggestion."""

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=600,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        final_response = response.content[0].text.strip()

        # ===========================================
        # PROGRESSIVE PROFILING: Add profile prompt
        # ===========================================
        profile_prompt = get_profile_prompt(state, understanding.intent.value)
        if profile_prompt:
            final_response += profile_prompt

        return final_response

    except Exception as e:
        logger.error(f"Response generation error: {e}")

        # Enhanced fallback with Nigerian politics knowledge
        return await _smart_fallback(query, retrieval, state)


async def _smart_fallback(query: str, retrieval: RetrievalResult, state: UserState) -> str:
    """Smart fallback when Claude API fails — uses web search and templates."""

    # If we have retrieval results, format them
    if retrieval.politician:
        p = retrieval.politician
        return get_template("politician_info",
            name=p.get("name", "Unknown"),
            party=p.get("party", "Unknown"),
            position=p.get("position", "Politician"),
            bio=p.get("bio", "No biography available.")
        )

    if retrieval.representatives:
        reps = retrieval.representatives
        return get_template("rep_all",
            lga=state.lga,
            state=state.state,
            governor=f"{reps[0]['name']} ({reps[0]['party']})" if reps else "Not found",
            senator=f"{reps[1]['name']} ({reps[1]['party']})" if len(reps) > 1 else "Not found",
            house_rep=f"{reps[2]['name']} ({reps[2]['party']})" if len(reps) > 2 else "Not found"
        )

    if retrieval.web_results:
        news = retrieval.web_results
        result = "Here's what I found:\n\n"
        for item in news[:3]:
            title = item.get('title', 'News')
            summary = item.get('summary', '')[:150]
            result += f"• {title}\n  {summary}\n\n"
        result += "Want me to search for more details?"
        return result

    # Last resort: Try web search directly
    try:
        from app.services.realtime import fetch_web_search
        web_results = fetch_web_search(query, limit=3)
        if web_results:
            result = "Here's what I found online:\n\n"
            for item in web_results[:3]:
                result += f"• {item.get('title', 'News')}\n"
            result += "\nWant more details on any of these?"
            return result
    except Exception as e:
        logger.error(f"Fallback web search failed: {e}")

    # Check if it's a hot issue we know about
    hot_issue = analyze_query_for_hot_issues(query)
    if hot_issue:
        ctx = hot_issue['context']
        if isinstance(ctx, dict):
            result = f"Regarding {hot_issue['issue'].replace('_', ' ')}:\n\n"
            if 'status' in ctx:
                result += f"Status: {ctx['status']}\n"
            if 'impact' in ctx:
                result += f"Impact: {ctx['impact']}\n"
            if 'sentiment' in ctx:
                result += f"Public sentiment: {ctx['sentiment']}\n"
            result += "\nWant more current details?"
            return result

    # Final fallback
    return get_template("no_info_found", query=query)


# ===========================================
# FLOW HANDLERS
# ===========================================

async def _handle_issue_flow(state: UserState, text: str, media_url: str = None) -> str:
    """Handle issue reporting flow."""
    step = state.flow_step
    
    if step == 0:
        # Initial prompt already shown, now waiting for location
        state.flow_step = 1
        return get_template("issue_start")
    
    elif step == 1:
        # Got location
        state.flow_data["location"] = text
        state.flow_step = 2
        return get_template("issue_got_location", location=text)
    
    elif step == 2:
        # Got description
        state.flow_data["description"] = text
        if media_url:
            state.flow_data["media_url"] = media_url
        
        # Move to confirmation
        state.flow = ConversationFlow.CONFIRMING
        state.flow_data["confirm_action"] = "save_issue"
        
        return get_template("issue_confirm",
            issue_type="Community Issue",
            location=state.flow_data.get("location", ""),
            description=text
        )
    
    return get_template("issue_start")


async def _handle_confirmation(state: UserState, text: str) -> str:
    """Handle confirmation responses."""
    text_lower = text.lower().strip()
    
    if text_lower in {"yes", "y", "yeah", "yep", "sure", "ok", "confirm", "correct"}:
        action = state.flow_data.get("confirm_action")
        
        if action == "save_issue":
            # Save the issue
            try:
                from app.database import get_db, UserReport
                db = next(get_db())
                
                report = UserReport(
                    user_hash=state.user_id,
                    location=state.flow_data.get("location", ""),
                    description=state.flow_data.get("description", ""),
                    media_url=state.flow_data.get("media_url"),
                    status="submitted"
                )
                db.add(report)
                db.commit()
                
                state.clear_flow()
                return get_template("issue_saved",
                    issue_type="Community Issue",
                    location=state.flow_data.get("location", "Unknown"),
                    authority="relevant authorities",
                    reference_id=f"ISS-{report.id:05d}"
                )
                
            except Exception as e:
                logger.error(f"Failed to save issue: {e}")
                state.clear_flow()
                return "I had trouble saving your report. Please try again later."
        
        state.clear_flow()
        return "Confirmed. What else can I help with?"
    
    elif text_lower in {"no", "n", "nope", "cancel", "wrong"}:
        state.clear_flow()
        return "No problem. What else can I help with?"
    
    else:
        return "Please respond with 'yes' to confirm or 'no' to cancel."


async def _handle_clarification(state: UserState, text: str) -> str:
    """Handle clarification responses."""
    # Re-process with the clarification as new query
    state.flow = ConversationFlow.IDLE
    return await handle_idle_claude_first(state, text)
