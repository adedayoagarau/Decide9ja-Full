"""
Message Handler V4 — Claude-First Architecture

Key changes from V3:
1. Uses Claude for intent classification (not regex)
2. Claude decides retrieval strategy
3. Intelligent retrieval orchestration
4. Still maintains flow-first routing for active flows
5. Persistent conversation memory across sessions
"""
import os
import logging
from datetime import datetime
from typing import Optional

from app.models.state import UserState, ConversationFlow
from app.services.state_manager import state_manager, _get_state_async, _save_state_async
from app.services.templates import get_template, TEMPLATES
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
from app.services.agentic_retrieval import (
    agentic_retrieve,
    AgenticResult,
    RetrievalStatus
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
from app.services.gamification_service import GamificationService
from app.services.fact_check_service import FactCheckService
from app.services.community_service import CommunityService
from app.services.news_digest_service import NewsDigestService
from app.services.user_memory import user_memory
from app.services.enhanced_memory import enhanced_memory
from app.services.prompts import (
    build_tade_system_prompt,
    build_tade_user_prompt,
    get_current_context
)
from app.services.output_guard import guard_output

logger = logging.getLogger(__name__)

# Escape commands that reset conversation
ESCAPE_COMMANDS = {"reset", "restart", "cancel", "menu", "stop", "start over", "new"}

# Controversial topics that need balanced treatment (from v3)
CONTROVERSIAL_TOPICS = [
    "tax reform", "tax bill", "vat", "derivation",
    "pdp crisis", "apc crisis", "party", "defection",
    "north vs south", "northern governors", "southern governors",
    "restructuring", "true federalism", "secession",
    "election", "rigging", "inec", "tribunal",
    "subsidy", "fuel price", "palliative",
    "insecurity", "banditry", "terrorism",
    "muslim-muslim", "christian", "religion",
    "ethnic", "tribe", "marginalization",
    "obi vs tinubu", "atiku vs tinubu", "labour party",
    "wike", "fubara", "rivers crisis",
]


def is_controversial_topic(query: str) -> bool:
    """Detect if a query touches on politically controversial topics."""
    query_lower = query.lower()
    return any(topic in query_lower for topic in CONTROVERSIAL_TOPICS)


async def handle_message(phone: str, text: str, media_url: str = None) -> str:
    """
    Main entry point — Claude-First Architecture with Persistent Memory.

    Flow:
    1. Load state & memory
    2. Save user message to persistent history
    3. Check escape commands
    4. Check for returning user greeting
    5. If in active flow → handle flow (skip Claude understanding)
    6. If IDLE → Claude understands → intelligent retrieval → Claude responds
    7. Save state & response to persistent history
    """
    text = text.strip() if text else ""
    text_lower = text.lower()

    # ===========================================
    # STEP 1: Load State & Check Returning User
    # ===========================================
    try:
        state = await _get_state_async(phone)
        # Load user memory for context
        memory = user_memory.get_user_memory(phone)
        is_returning = memory.is_returning_user
    except Exception as e:
        logger.error(f"Failed to load state: {e}")
        state = UserState(
            user_id="temp",
            phone=phone,
            flow=ConversationFlow.IDLE
        )
        memory = None
        is_returning = False

    # ===========================================
    # STEP 2: Save User Message to Persistent History
    # ===========================================
    user_memory.save_message(phone, "user", text)

    # ===========================================
    # STEP 2.5: Check for Progressive Onboarding Responses
    # ===========================================
    progressive_response = _detect_progressive_onboarding_response(phone, text_lower)
    if progressive_response:
        # Save the response and acknowledge it, but continue processing normally
        pass  # The detection function handles saving

    # ===========================================
    # STEP 3: Check Escape Commands
    # ===========================================
    if text_lower in ESCAPE_COMMANDS:
        state.clear_flow()
        state.clear_context()
        await _save_state_async(state)
        response = get_template("menu")
        user_memory.save_message(phone, "assistant", response)
        return response

    # ===========================================
    # STEP 4: Add to Session History
    # ===========================================
    state.add_to_history("user", text)

    # ===========================================
    # STEP 5: Route Based on Flow State
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
            # Pass memory for context awareness
            response = await handle_idle_claude_first(state, text, memory)

    except Exception as e:
        logger.exception(f"Error handling message: {e}")
        response = TEMPLATES.get("error_generic", "Something went wrong. Please try again.")

    # ===========================================
    # STEP 6: Update State & Save to Persistent History
    # ===========================================
    state.add_to_history("assistant", response)
    await _save_state_async(state)

    # Save assistant response to persistent memory
    user_memory.save_message(phone, "assistant", response)

    # ===========================================
    # STEP 7: Enhanced Memory Processing
    # ===========================================
    # Store embeddings for semantic search (async, non-blocking)
    try:
        import asyncio
        # Store user message embedding for future semantic search
        asyncio.create_task(
            enhanced_memory.embed_and_store_message(
                phone, "user", text,
                metadata={"intent": state.flow.value if state.flow else "idle"}
            )
        )

        # Periodic memory consolidation (every 10 messages)
        memory_stats = enhanced_memory.get_memory_stats(phone)
        if memory_stats.get("total_messages", 0) % 10 == 0:
            asyncio.create_task(enhanced_memory.consolidate_memory(phone))
    except Exception as e:
        logger.warning(f"Enhanced memory processing error: {e}")

    # ===========================================
    # STEP 8: Check for Progressive Onboarding
    # ===========================================
    # Occasionally ask for more user info at milestones
    progressive_prompt = user_memory.get_progressive_onboarding_prompt(phone)
    if progressive_prompt:
        response = response + "\n\n---\n" + progressive_prompt

    return response


async def handle_idle_claude_first(state: UserState, text: str, memory=None) -> str:
    """
    Handle IDLE state using Claude-First architecture.

    Flow:
    1. Check if onboarding complete
    2. Handle returning user greetings with memory context
    3. Claude understands the query
    4. Route to intelligent retrieval
    5. Claude generates response with context
    """

    # ===========================================
    # Check Onboarding
    # ===========================================
    if not state.is_onboarding_complete():
        # User hasn't completed onboarding - start it regardless of what they said
        # Users can start with anything: "hi", "who is the governor?", "help", etc.
        from app.services.flows.onboarding import handle_onboarding

        # Capture old flow state BEFORE changing it
        was_already_onboarding = state.flow == ConversationFlow.ONBOARDING
        state.flow = ConversationFlow.ONBOARDING

        # Only reset flow_step if not already in onboarding (prevents restarting mid-flow)
        if not was_already_onboarding:
            state.flow_step = 0
            state.greeted = False
        return await handle_onboarding(state, text)
    
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
    # EARLY EXIT FOR GIBBERISH/LOW CONFIDENCE
    # ===========================================
    # If confidence is very low (< 0.2) and intent is FALLBACK, return short response
    # This prevents long irrelevant responses to random key mashes like "Awwaftghvdesxh"
    if understanding.confidence < 0.2 and understanding.intent == Intent.FALLBACK:
        logger.info(f"Low confidence gibberish detected: '{text[:30]}...' conf={understanding.confidence}")
        return get_template("gibberish_short")

    # ===========================================
    # ROUTE BY INTENT
    # ===========================================

    # Simple responses (no retrieval needed)
    if understanding.intent == Intent.GREETING:
        # Check if returning user with memory context
        if memory and memory.is_returning_user:
            welcome_back = user_memory.get_returning_user_summary(state.phone)
            if welcome_back:
                return welcome_back + "\n\nHow can I help you today?"
        return get_template("greeting_returning", first_name=state.first_name or state.name)
    
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
    # PROACTIVE MESSAGING & COMMUNITY HANDLERS
    # ===========================================

    # Subscribe to daily digest
    if understanding.intent == Intent.SUBSCRIBE_DIGEST:
        try:
            from app.services.twilio_whatsapp import hash_phone
            user_hash = hash_phone(state.phone)
            digest_service = NewsDigestService()
            frequency = understanding.entities.get("frequency", "daily")
            success = digest_service.subscribe_user(user_hash, frequency)
            if success:
                return f"""✅ *Subscribed to {frequency.title()} Digest!*

You'll receive political news and updates {frequency} at 7 AM WAT.

📰 What you'll get:
• Breaking political news
• Policy updates and explainers
• 2027 election updates
• Local updates for {state.state or 'your state'}

Reply "unsubscribe" anytime to stop.

Is there anything specific you want me to focus on? (e.g., elections, economy, security)"""
            else:
                return "You're already subscribed to the digest! Reply 'unsubscribe' to stop receiving updates."
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            return "Sorry, I couldn't process your subscription. Please try again later."

    # Unsubscribe from digest
    if understanding.intent == Intent.UNSUBSCRIBE_DIGEST:
        try:
            from app.services.twilio_whatsapp import hash_phone
            user_hash = hash_phone(state.phone)
            digest_service = NewsDigestService()
            success = digest_service.unsubscribe_user(user_hash)
            if success:
                return """✅ *Unsubscribed from Digest*

You won't receive automatic updates anymore.

You can still:
• Ask me questions anytime
• Say "subscribe" to get updates again
• Follow specific politicians for their news

Anything else I can help with?"""
            else:
                return "You're not currently subscribed to any digest. Say 'subscribe' to start receiving updates."
        except Exception as e:
            logger.error(f"Unsubscribe error: {e}")
            return "Sorry, I couldn't process that. Please try again."

    # Fact-check / Verify claim
    if understanding.intent == Intent.VERIFY_CLAIM:
        try:
            claim = understanding.entities.get("claim", text)
            # Clean up common prefixes
            for prefix in ["verify", "fact check", "is it true that", "check if"]:
                if claim.lower().startswith(prefix):
                    claim = claim[len(prefix):].strip()

            from app.services.twilio_whatsapp import hash_phone
            user_hash = hash_phone(state.phone)
            fact_service = FactCheckService()
            result = fact_service.check_claim(claim, user_hash)

            if result.get("found"):
                fc = result["fact_check"]
                verdict_emoji = {
                    "true": "✅",
                    "mostly_true": "🟢",
                    "half_true": "🟡",
                    "mostly_false": "🟠",
                    "false": "❌",
                    "unverifiable": "❓"
                }
                emoji = verdict_emoji.get(fc.get("verdict", ""), "🔍")
                return f"""{emoji} *Fact Check Result*

📋 *Claim:* {claim[:100]}...

🔍 *Verdict:* {fc.get('verdict', 'Unknown').replace('_', ' ').title()}

📝 *Explanation:*
{fc.get('explanation', 'No explanation available')[:400]}

📰 *Sources:* {len(fc.get('sources', []))} verified source(s)

Want me to explain more about this topic?"""
            else:
                # Submit for review
                request_id = result.get("request_id", "pending")
                return f"""🔍 *Fact Check Request Submitted*

I'm checking: "{claim[:80]}..."

This claim hasn't been verified yet. Your request has been submitted for review by our fact-checkers.

📋 Request ID: {request_id}

I'll check our database and news sources. You can also:
• Ask me to explain the topic
• Share where you heard this claim
• Check back later for updates

Want me to search for related news on this topic?"""
        except Exception as e:
            logger.error(f"Fact check error: {e}")
            return "Sorry, I couldn't process that fact-check. Please try again with a clearer claim."

    # Report community issue
    if understanding.intent == Intent.REPORT_COMMUNITY_ISSUE:
        # Start the community issue reporting flow
        state.flow = ConversationFlow.ISSUE_FLOW
        state.flow_step = 0
        state.flow_data = {
            "type": "community",
            "initial_description": understanding.entities.get("description", text)
        }

        category = understanding.entities.get("category", "")
        category_options = """
📂 *Issue Categories:*
1️⃣ Roads/Potholes
2️⃣ Electricity (NEPA)
3️⃣ Water Supply
4️⃣ Security
5️⃣ Sanitation/Waste
6️⃣ Education
7️⃣ Health
8️⃣ Other

Reply with the number or name of the category."""

        if category:
            state.flow_data["category"] = category
            state.flow_step = 1
            return f"""📍 *Reporting: {category.title()} Issue*

Got it! Now I need more details:

1. What's the exact location? (Street, area, LGA)
2. Brief description of the problem

Please share the location first:"""

        return f"""📢 *Report a Community Issue*

I'll help you report this issue to the relevant authorities and track it.

{category_options}"""

    # My points / civic score
    if understanding.intent == Intent.MY_POINTS:
        try:
            from app.services.twilio_whatsapp import hash_phone
            user_hash = hash_phone(state.phone)
            gamification = GamificationService()
            profile = gamification.get_profile(user_hash, state.name, state.state, state.lga)

            # Format badges
            badges_text = ""
            if profile.get("badges"):
                badges_text = "\n🏅 *Badges:* " + " ".join(profile["badges"][:5])

            streak_emoji = "🔥" if profile.get("current_streak", 0) >= 3 else "📅"

            return f"""🏆 *Your Civic Score*

👤 *{profile.get('display_name', state.name or 'Citizen')}*
📍 {profile.get('state', state.state or 'Nigeria')}

⭐ *Total Points:* {profile.get('total_points', 0):,}
📊 *Level:* {profile.get('level', 1)} - {profile.get('title', 'Civic Observer')}
{streak_emoji} *Current Streak:* {profile.get('current_streak', 0)} days{badges_text}

📈 *This Week:* {profile.get('points_this_week', 0)} points
📆 *This Month:* {profile.get('points_this_month', 0)} points

💡 *Earn more points by:*
• Asking questions (+5)
• Reporting issues (+20)
• Verifying facts (+15)
• Daily check-ins (+10)

Say 'leaderboard' to see top citizens!"""
        except Exception as e:
            logger.error(f"Points error: {e}")
            return "Sorry, I couldn't load your points. Please try again."

    # Leaderboard
    if understanding.intent == Intent.LEADERBOARD:
        try:
            from app.services.twilio_whatsapp import hash_phone
            user_hash = hash_phone(state.phone)
            gamification = GamificationService()
            leaderboard = gamification.get_leaderboard(
                state=state.state,
                lga=state.lga,
                user_hash=user_hash
            )

            location = state.lga or state.state or "Nigeria"

            text = f"""🏆 *{location} Leaderboard*

"""
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

            for i, entry in enumerate(leaderboard.get("top_10", [])[:10]):
                medal = medals[i] if i < len(medals) else f"{i+1}."
                name = entry.get("display_name", "Anonymous")[:15]
                points = entry.get("total_points", 0)
                level = entry.get("level", 1)
                text += f"{medal} {name} - {points:,} pts (Lv.{level})\n"

            # User's position if not in top 10
            user_rank = leaderboard.get("user_rank")
            if user_rank and user_rank > 10:
                text += f"\n📍 *Your rank:* #{user_rank}"

            text += f"""

🎯 *Weekly Challenge:*
Be more active to climb the ranks!

Say 'my points' to see your score."""

            return text
        except Exception as e:
            logger.error(f"Leaderboard error: {e}")
            return "Sorry, I couldn't load the leaderboard. Please try again."

    # My civic profile (detailed)
    if understanding.intent == Intent.MY_CIVIC_PROFILE:
        try:
            from app.services.twilio_whatsapp import hash_phone
            user_hash = hash_phone(state.phone)
            gamification = GamificationService()
            profile = gamification.get_profile(user_hash, state.name, state.state, state.lga)

            # Badge details
            badges_section = ""
            all_badges = profile.get("all_badges", [])
            earned = profile.get("badges", [])

            if earned:
                badges_section = "\n\n🏅 *Your Badges:*\n"
                for badge in earned[:5]:
                    badges_section += f"✅ {badge}\n"

            # Action counts
            actions = profile.get("action_counts", {})
            actions_section = ""
            if actions:
                actions_section = "\n\n📊 *Your Activity:*\n"
                action_names = {
                    "daily_login": "Daily Logins",
                    "question_asked": "Questions Asked",
                    "issue_reported": "Issues Reported",
                    "fact_checked": "Fact Checks",
                    "poll_voted": "Polls Voted"
                }
                for action, count in actions.items():
                    name = action_names.get(action, action.replace("_", " ").title())
                    actions_section += f"• {name}: {count}\n"

            return f"""👤 *Your Civic Profile*

📛 *Name:* {profile.get('display_name', state.name or 'Citizen')}
📍 *Location:* {profile.get('lga', state.lga or '')} {profile.get('state', state.state or 'Nigeria')}

⭐ *Total Points:* {profile.get('total_points', 0):,}
📊 *Level:* {profile.get('level', 1)}
🎖️ *Title:* {profile.get('title', 'Civic Observer')}

🔥 *Streaks:*
• Current: {profile.get('current_streak', 0)} days
• Longest: {profile.get('longest_streak', 0)} days{badges_section}{actions_section}

📅 *Member Since:* {profile.get('joined_at', 'Recently')[:10] if profile.get('joined_at') else 'Recently'}

Keep engaging to earn more badges and climb the ranks! 🚀"""
        except Exception as e:
            logger.error(f"Profile error: {e}")
            return "Sorry, I couldn't load your profile. Please try again."

    # ===========================================
    # AGENTIC RETRIEVAL (Self-correcting, graded)
    # ===========================================
    # Use new agentic retrieval system with:
    # - Pattern-matching fast path
    # - Tool grouping and routing
    # - Document grading
    # - Query rewriting on failure
    # - Self-correction loop
    # - Handoff between tool groups

    user_context = {
        "state": state.state,
        "lga": state.lga,
        "name": state.first_name or state.name,
        "phone": state.phone  # Pass phone for memory retrieval tool
    }

    agentic_result = await agentic_retrieve(text, user_context)

    logger.info(f"Agentic retrieval: {agentic_result.total_attempts} attempts, status={agentic_result.status.value}, sources={agentic_result.sources_used}")

    # Also run legacy retrieval for fallback/comparison
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
        agentic=agentic_result,
        state=state
    )


async def generate_response_with_context(
    query: str,
    understanding: QueryUnderstanding,
    retrieval: RetrievalResult,
    state: UserState,
    agentic: AgenticResult = None
) -> str:
    """Generate Claude response using retrieved context with Nigerian politics expertise."""

    import anthropic

    # Load conversation history for multi-turn context
    conversation_history = user_memory.get_conversation_context(state.phone, limit=6)  # Last 6 messages

    # Format context from retrieval (legacy)
    legacy_context = format_retrieval_for_context(retrieval)

    # Prefer agentic context if available and successful
    from app.services.agentic_retrieval import RetrievalStatus
    agentic_success = agentic and agentic.status in [RetrievalStatus.SUCCESS, RetrievalStatus.PARTIAL]

    if agentic_success and agentic.graded_context:
        context = f"""AGENTIC RETRIEVAL (graded, self-corrected):
{agentic.graded_context}

LEGACY RETRIEVAL (for reference):
{legacy_context}"""
        logger.info(f"Using agentic context ({agentic.total_attempts} attempts, status={agentic.status.value}, confidence={agentic.confidence:.2f})")
    else:
        context = legacy_context

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

    # Build system prompt using federated prompt architecture (Source of Truth)
    user_context_for_prompt = {
        "name": state.first_name or state.name,
        "state": state.state,
        "lga": state.lga
    }

    # Build Tade's system prompt from Source of Truth
    system_prompt = build_tade_system_prompt(
        user_context=user_context_for_prompt,
        include_full_sot=False  # Use minimal SOT for faster inference
    )

    # Add dynamic current context
    system_prompt += get_current_context()

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

    # Build conversation history summary for the prompt
    history_summary = ""
    if conversation_history and len(conversation_history) > 1:
        # Summarize recent conversation (exclude current message)
        recent = conversation_history[:-1][-4:]  # Last 4 messages before current
        if recent:
            history_summary = "\n\nRECENT CONVERSATION:\n"
            for msg in recent:
                role_label = "User" if msg["role"] == "user" else "Tade"
                # Truncate long messages
                content = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
                history_summary += f"[{role_label}]: {content}\n"

    # Build user context - only include known fields, never announce these directly
    user_context_parts = []
    if state.first_name:
        user_context_parts.append(f"first_name: {state.first_name}")
        if state.last_name:
            user_context_parts.append(f"full_name: {state.first_name} {state.last_name}")
    elif state.name:
        # Fallback for legacy users without first_name
        user_context_parts.append(f"name: {state.name}")
    if state.state:
        user_context_parts.append(f"state: {state.state}")
    if state.lga:
        user_context_parts.append(f"lga: {state.lga}")

    user_context = ", ".join(user_context_parts) if user_context_parts else "new user (no profile yet)"

    # Get enhanced memory personalization context
    personalization_context = ""
    try:
        personalization_context = enhanced_memory.get_personalization_context(state.phone)
        # Also get relevant semantic context from past conversations
        relevant_past = enhanced_memory.get_relevant_context(state.phone, query, max_context=3)
        if relevant_past:
            personalization_context += f"\n\n{relevant_past}"
    except Exception as e:
        logger.warning(f"Enhanced memory error: {e}")

    # Build user prompt using federated prompt system
    user_prompt = build_tade_user_prompt(
        query=query,
        retrieved_context=full_context,
        intent=understanding.intent.value,
        conversation_history=history_summary if history_summary else None,
        personalization=f"User: {user_context}\n{personalization_context}" if personalization_context else f"User: {user_context}"
    )

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Build messages array with conversation history for multi-turn context
        messages = []

        # Add past conversation history (excluding current message since we saved it earlier)
        # This gives Claude context about what was discussed before
        if conversation_history and len(conversation_history) > 1:
            # Skip the last message since it's the current query (already saved to DB)
            past_messages = conversation_history[:-1]

            # Ensure messages alternate properly (Claude API requirement)
            # Start from the first user message in history
            for msg in past_messages:
                # Skip if this would create consecutive same-role messages
                if messages and messages[-1]["role"] == msg["role"]:
                    continue
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

            # If last message in history is from assistant, we're good
            # If not, ensure proper alternation by clearing messages that don't end with assistant
            if messages and messages[-1]["role"] == "user":
                # Pop the last user message to allow our current user_prompt
                messages.pop()

        # Add current query with full context (always from user)
        messages.append({"role": "user", "content": user_prompt})

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=600,
            system=system_prompt,
            messages=messages
        )

        # Apply output guardrails (neutrality, sources, hallucination check)
        raw_response = response.content[0].text.strip()
        return await guard_output(raw_response, context=query)

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


def _detect_progressive_onboarding_response(phone: str, text_lower: str) -> bool:
    """
    Detect and save responses to progressive onboarding questions.
    Returns True if a progressive onboarding response was detected.
    """
    # Get user preferences to check what we've asked about
    prefs = user_memory.get_user_preferences(phone)

    # Check for PVC response (asked at 5 messages)
    pvc_keywords_yes = ["yes", "i have", "got pvc", "registered", "have pvc", "i do"]
    pvc_keywords_no = ["no", "i don't", "not yet", "haven't", "no pvc", "not registered"]

    last_asked = prefs.get("last_onboarding_ask_at", 0)

    # If we just asked about PVC
    if last_asked == 5 and not prefs.get("has_pvc"):
        for keyword in pvc_keywords_yes:
            if keyword in text_lower:
                user_memory.save_progressive_response(phone, "has_pvc", "yes")
                logger.info(f"Saved PVC status: yes for user")
                return True
        for keyword in pvc_keywords_no:
            if keyword in text_lower:
                user_memory.save_progressive_response(phone, "has_pvc", "no")
                logger.info(f"Saved PVC status: no for user")
                return True

    # Check for interests response (asked at 15 messages)
    if last_asked == 15 and not prefs.get("interests"):
        interest_keywords = {
            "economy": ["economy", "money", "jobs", "business", "naira", "dollar", "inflation"],
            "security": ["security", "safety", "police", "army", "crime", "bandits"],
            "education": ["education", "school", "university", "students", "teachers"],
            "healthcare": ["healthcare", "health", "hospital", "doctors", "medicine"]
        }

        detected_interests = []
        for interest, keywords in interest_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    detected_interests.append(interest)
                    break

        if detected_interests:
            user_memory.save_progressive_response(phone, "interests", ",".join(detected_interests))
            logger.info(f"Saved interests: {detected_interests} for user")
            return True

    # Check for 2027 election tracking response (asked at 30 messages)
    if last_asked == 30 and not prefs.get("following_2027"):
        for keyword in ["yes", "i want", "help me", "track", "interested"]:
            if keyword in text_lower:
                user_memory.save_progressive_response(phone, "following_2027", "yes")
                logger.info(f"Saved 2027 election interest: yes for user")
                return True
        for keyword in ["no", "not now", "later", "not interested"]:
            if keyword in text_lower:
                user_memory.save_progressive_response(phone, "following_2027", "no")
                logger.info(f"Saved 2027 election interest: no for user")
                return True

    return False


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
