"""
Tade's response templates.
All responses should use these templates to maintain consistent voice.

RULES:
- One question per turn
- No "Great question!", "I'd be happy to help!"
- Direct, warm, balanced
- Clear next step at end
"""

TEMPLATES = {
    # ==========================================
    # ONBOARDING
    # ==========================================
    
    "welcome_new": (
        "Welcome to Decide9ja. I'm Tade, and I help Nigerians stay informed "
        "about their representatives and government.\n\n"
        "What's your name?"
    ),
    
    "welcome_back": (
        "Tade here. Welcome back, {name}. What do you need?"
    ),

    "welcome_back_no_name": (
        "Tade here. Welcome back. What do you need?"
    ),

    # Time-aware greetings for returning users
    "welcome_back_today": (
        "Back so soon, {name}! What else can I help with?"
    ),

    "welcome_back_yesterday": (
        "Hey {name}, good to see you again. How can I help today?"
    ),

    "welcome_back_few_days": (
        "Welcome back, {name}! It's been a few days. What do you need?"
    ),

    "welcome_back_week": (
        "{name}! Been about a week — hope all is well. What can I help with?"
    ),

    "welcome_back_long": (
        "Long time, {name}! Good to have you back. What do you need?"
    ),

    "welcome_back_first_time_today": (
        "Morning/afternoon/evening, {name}! Ready to help. What's on your mind?"
    ),

    # Active user recognition (high message count)
    "welcome_regular_user": (
        "Hey {name}! You're becoming a regular. What do you need today?"
    ),
    
    "ask_state": (
        "Good to meet you, {name}. Which state are you in?"
    ),
    
    "ask_lga": (
        "Which local government in {state}?"
    ),
    
    "onboarding_complete": (
        "You're set — {lga}, {state} State.\n\n"
        "Ask about your representatives, report an issue, or ask me "
        "anything about Nigerian politics."
    ),

    "incomplete_profile": (
        "I need a bit more info to help you better.\n\n"
        "Say 'hi' to get started, or 'help' for options."
    ),

    "greeting_returning": (
        "Hey {name}! How can I help you today?\n\n"
        "Ask about your representatives, politicians, or current political news."
    ),

    "didnt_catch_name": (
        "I didn't catch your name. What should I call you?"
    ),
    
    "didnt_recognize_state": (
        "I didn't recognize that state. Which Nigerian state are you in?"
    ),
    
    "didnt_recognize_lga": (
        "I didn't recognize that LGA. Which local government in {state}?"
    ),
    
    # ==========================================
    # REPRESENTATIVES
    # ==========================================
    
    "rep_governor": (
        "{name} ({party}) — Governor of {state} State since {since}.\n\n"
        "Want to know more about them?"
    ),
    
    "rep_senator": (
        "{name} ({party}) — {district} Senatorial District.\n\n"
        "Want to know more about them?"
    ),
    
    "rep_house": (
        "{name} ({party}) — {constituency} Federal Constituency.\n\n"
        "Want to know more about them?"
    ),
    
    "rep_all": (
        "Your representatives in {lga}, {state}:\n\n"
        "• Governor: {governor}\n"
        "• Senator: {senator}\n"
        "• House Rep: {house_rep}\n\n"
        "Ask about any of them for more details."
    ),
    
    "rep_not_found": (
        "I don't have representative data for {lga}, {state} yet. "
        "This information is being updated.\n\n"
        "Try asking about a specific politician by name."
    ),

    # Specific representative lookups
    "rep_governor_only": (
        "Your Governor ({state} State):\n"
        "{governor}\n\n"
        "Ask me anything about them."
    ),

    "rep_senator_only": (
        "Your Senator ({district}):\n"
        "{senator}\n\n"
        "Ask me anything about them."
    ),

    "rep_house_only": (
        "Your House Rep ({constituency}):\n"
        "{house_rep}\n\n"
        "Ask me anything about them."
    ),

    "rep_house_not_available": (
        "House Representative data for {lga} is being updated.\n\n"
        "In the meantime, here are your other representatives:\n"
        "• Governor: {governor}\n"
        "• Senator: {senator}"
    ),
    
    # ==========================================
    # POLITICIAN INFO
    # ==========================================
    
    "politician_info": (
        "{name} ({party})\n"
        "{position}\n\n"
        "{bio}\n\n"
        "Want to know about their record?"
    ),

    # Enhanced politician info with structured format
    "politician_info_rich": (
        "*{name}*\n"
        "{party} • {position}\n"
        "{state_or_constituency}\n\n"
        "{bio}\n\n"
        "Ask me about:\n"
        "• Their legislative record\n"
        "• Bills they've sponsored\n"
        "• Their voting history"
    ),

    # Governor-specific template
    "politician_info_governor": (
        "*{name}* ({party})\n"
        "Governor of {state} State\n"
        "Since {since}\n\n"
        "{bio}\n\n"
        "Ask about:\n"
        "• Their budget allocations\n"
        "• Key projects\n"
        "• Policy achievements"
    ),

    # Senator-specific template
    "politician_info_senator": (
        "*{name}* ({party})\n"
        "Senator - {district}\n\n"
        "{bio}\n\n"
        "Ask about:\n"
        "• Bills sponsored\n"
        "• Committee memberships\n"
        "• Constituency projects"
    ),

    # Fuzzy match suggestion
    "politician_fuzzy_match": (
        "Did you mean *{matched_name}*?\n\n"
        "{name} ({party})\n"
        "{position}\n\n"
        "{bio}"
    ),

    "politician_not_found": (
        "I don't have information on \"{query}\".\n\n"
        "Try the full name, or ask about a specific position like "
        "\"Who is the governor of Lagos?\""
    ),

    "politician_not_found_with_suggestions": (
        "I couldn't find \"{query}\".\n\n"
        "Did you mean one of these?\n"
        "{suggestions}\n\n"
        "Or try: \"Who is my senator?\" or \"Governor of Lagos\""
    ),

    "politician_multiple": (
        "I found several matches for \"{query}\":\n\n"
        "{options}\n\n"
        "Which one?"
    ),
    
    # ==========================================
    # NEWS & CURRENT EVENTS
    # ==========================================

    "news_summary": (
        "{summary}\n\n"
        "Source: {source}"
    ),

    # Enhanced news with multiple sources
    "news_summary_multi": (
        "*{headline}*\n\n"
        "{summary}\n\n"
        "Sources: {sources}\n"
        "Updated: {date}"
    ),

    # Hot topic / trending
    "news_hot_topic": (
        "*Trending: {topic}*\n\n"
        "{summary}\n\n"
        "Key points:\n"
        "{key_points}\n\n"
        "Want more details or perspectives?"
    ),

    # News about a politician
    "news_politician": (
        "*Recent news about {politician}*\n\n"
        "{summary}\n\n"
        "Source: {source}\n"
        "Date: {date}"
    ),

    # Policy news
    "news_policy": (
        "*{policy_name}*\n\n"
        "{summary}\n\n"
        "Supporters: {supporters}\n"
        "Opponents: {opponents}\n\n"
        "Want to know more about the debate?"
    ),

    "news_not_found": (
        "I don't have recent news on that topic.\n\n"
        "Try asking about a specific politician or policy."
    ),

    "news_not_found_with_suggestions": (
        "No recent news on \"{query}\".\n\n"
        "Here's what's trending:\n"
        "{trending_topics}\n\n"
        "Ask about any of these."
    ),

    "news_political_balance": (
        "That's a political question with different perspectives.\n\n"
        "{balanced_summary}\n\n"
        "Want more details on any side?"
    ),
    
    # ==========================================
    # ISSUE REPORTING
    # ==========================================
    
    "issue_start": (
        "I'll document this. Share your location or type the address."
    ),
    
    "issue_got_location": (
        "Got it — {location}.\n\n"
        "Describe the issue briefly."
    ),
    
    "issue_confirm": (
        "Confirm this report:\n\n"
        "• Issue: {issue_type}\n"
        "• Location: {location}\n"
        "• Description: {description}\n\n"
        "Save this? (yes/no)"
    ),
    
    "issue_saved": (
        "Documented:\n"
        "• {issue_type} at {location}\n"
        "• Flagged to {authority}\n\n"
        "Reference: {reference_id}\n\n"
        "Anything else?"
    ),
    
    "issue_cancelled": (
        "Issue report cancelled. What else can I help with?"
    ),
    
    # ==========================================
    # VOTER REGISTRATION
    # ==========================================
    
    "voter_reg_info": (
        "To register to vote:\n\n"
        "1. Get your NIN (National Identification Number)\n"
        "2. Pre-register online at cvr.inecnigeria.org\n"
        "3. Visit your nearest INEC office with:\n"
        "   • NIN slip or card\n"
        "   • Passport photo\n"
        "4. Complete biometric capture\n"
        "5. Collect your PVC when ready\n\n"
        "Need help finding your nearest INEC office?"
    ),
    
    # ==========================================
    # HELP & FALLBACK
    # ==========================================
    
    "help": (
        "I can help you:\n\n"
        "• Find your representatives — \"Who is my senator?\"\n"
        "• Learn about politicians — \"Who is Tinubu?\"\n"
        "• Get political news — \"Latest on the tax bill\"\n"
        "• Report community issues — \"Report a bad road\"\n"
        "• Register to vote — \"How do I get my PVC?\"\n\n"
        "What do you need?"
    ),
    
    "fallback": (
        "I'm not sure I understood that.\n\n"
        "You can ask about your representatives, any politician, "
        "current news, or say 'help' for options."
    ),

    "fallback_with_context": (
        "I don't have that information.\n\n"
        "Try asking about a specific politician, your representatives, "
        "or current political news."
    ),

    "no_info_found": (
        "I don't have information on \"{query}\".\n\n"
        "Try asking about a specific politician by full name, "
        "your representatives, or current political news."
    ),
    
    # ==========================================
    # CONVERSATION MANAGEMENT
    # ==========================================
    
    "thanks_response": (
        "No wahala. Reach out anytime."
    ),
    
    "reset_confirm": (
        "Session reset. Send 'hi' to start fresh."
    ),
    
    "cancelled": (
        "No problem. What else can I help with?"
    ),
    
    "error_generic": (
        "Something went wrong on my end. Try again, or type 'reset' to start fresh."
    ),
    
    "error_overloaded": (
        "I'm getting a lot of requests. Try again in a moment."
    ),
    
    # ==========================================
    # PRIVACY
    # ==========================================
    
    "privacy_confirm_delete": (
        "Are you sure you want to delete all your data?\n\n"
        "This will remove:\n"
        "• Your name and location\n"
        "• Conversation history\n"
        "• Any reported issues\n\n"
        "Type 'yes delete' to confirm, or anything else to cancel."
    ),
    
    "privacy_deleted": (
        "Your data has been deleted.\n\n"
        "If you message again, you'll start fresh. Take care! 👋"
    ),
    
    "privacy_delete_cancelled": (
        "Data deletion cancelled. Your information is safe.\n\n"
        "What else can I help with?"
    ),
    
    # ==========================================
    # FOLLOWUP
    # ==========================================

    "followup_no_context": (
        "Who are you asking about?"
    ),

    "followup_bills": (
        "{name} has sponsored {count} bills:\n\n"
        "{bills_summary}\n\n"
        "Want details on any of these?"
    ),

    "followup_no_bills": (
        "{name} hasn't sponsored any bills in the current session.\n\n"
        "Want to know about their committee memberships instead?"
    ),

    # Record/achievements
    "followup_record": (
        "*{name}'s Record*\n\n"
        "{achievements}\n\n"
        "Ask about specific bills or projects."
    ),

    "followup_no_record": (
        "I don't have detailed record information for {name} yet.\n\n"
        "This data is being collected. Try asking about recent news instead."
    ),

    # Voting history
    "followup_voting": (
        "*{name}'s Voting Record*\n\n"
        "{voting_summary}\n\n"
        "Want to see specific votes?"
    ),

    "followup_no_voting": (
        "Voting records for {name} are not yet available.\n\n"
        "Ask about their bills or committee assignments instead."
    ),

    # Committee memberships
    "followup_committees": (
        "*{name}'s Committee Assignments*\n\n"
        "{committees}\n\n"
        "Ask about their work in any committee."
    ),

    "followup_no_committees": (
        "Committee data for {name} isn't available yet.\n\n"
        "Try asking about their bills or recent news."
    ),

    # Projects (for governors/executives)
    "followup_projects": (
        "*{name}'s Key Projects*\n\n"
        "{projects}\n\n"
        "Want details on any project?"
    ),

    "followup_no_projects": (
        "Project data for {name} is being compiled.\n\n"
        "Ask about their policies or recent statements instead."
    ),

    # Budget (for governors)
    "followup_budget": (
        "*{name}'s Budget Priorities ({year})*\n\n"
        "Total Budget: {total}\n\n"
        "{allocations}\n\n"
        "Compare with previous years?"
    ),

    # Comparison
    "followup_compare": (
        "*Comparison: {name1} vs {name2}*\n\n"
        "{comparison}\n\n"
        "Want more details on either?"
    ),

    # Alias for menu
    "menu": (
        "I can help you:\n\n"
        "• Find your representatives — \"Who is my senator?\"\n"
        "• Learn about politicians — \"Who is Tinubu?\"\n"
        "• Get political news — \"Latest on the tax bill\"\n"
        "• Report community issues — \"Report a bad road\"\n"
        "• Register to vote — \"How do I get my PVC?\"\n\n"
        "What do you need?"
    ),
}


def get_template(key: str, **kwargs) -> str:
    """Get a template and format it with provided values."""
    template = TEMPLATES.get(key, TEMPLATES["fallback"])
    try:
        return template.format(**kwargs)
    except KeyError as e:
        # Missing placeholder, return template as-is
        return template


def get_time_aware_greeting(name: str, last_active_at=None, message_count: int = 0) -> str:
    """
    Select appropriate greeting based on when user was last active.

    Args:
        name: User's name
        last_active_at: datetime of last activity (or None for first time)
        message_count: Total messages sent by user

    Returns:
        Personalized greeting string
    """
    from datetime import datetime, timedelta

    # Regular user recognition (50+ messages)
    if message_count >= 50:
        return get_template("welcome_regular_user", name=name)

    # First time or no last_active_at
    if not last_active_at:
        return get_template("greeting_returning", name=name)

    now = datetime.utcnow()

    # Handle timezone-aware vs naive datetime
    if hasattr(last_active_at, 'tzinfo') and last_active_at.tzinfo is not None:
        from datetime import timezone
        now = datetime.now(timezone.utc)

    time_diff = now - last_active_at
    hours = time_diff.total_seconds() / 3600
    days = time_diff.days

    # Same session (< 30 min) - shouldn't happen as they'd still be in Redis
    if hours < 0.5:
        return get_template("welcome_back_today", name=name)

    # Same day (< 12 hours)
    if hours < 12:
        return get_template("welcome_back_today", name=name)

    # Yesterday (12-36 hours)
    if hours < 36:
        return get_template("welcome_back_yesterday", name=name)

    # Few days (2-5 days)
    if days < 6:
        return get_template("welcome_back_few_days", name=name)

    # About a week (6-10 days)
    if days < 11:
        return get_template("welcome_back_week", name=name)

    # Long time (> 10 days)
    return get_template("welcome_back_long", name=name)
