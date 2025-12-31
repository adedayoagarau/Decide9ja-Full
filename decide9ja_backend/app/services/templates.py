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
    
    # ==========================================
    # POLITICIAN INFO
    # ==========================================
    
    "politician_info": (
        "{name} ({party})\n"
        "{position}\n\n"
        "{bio}\n\n"
        "Want to know about their record?"
    ),
    
    "politician_not_found": (
        "I don't have information on \"{query}\".\n\n"
        "Try the full name, or ask about a specific position like "
        "\"Who is the governor of Lagos?\""
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
    
    "news_not_found": (
        "I don't have recent news on that topic.\n\n"
        "Try asking about a specific politician or policy."
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
}


def get_template(key: str, **kwargs) -> str:
    """Get a template and format it with provided values."""
    template = TEMPLATES.get(key, TEMPLATES["fallback"])
    try:
        return template.format(**kwargs)
    except KeyError as e:
        # Missing placeholder, return template as-is
        return template
