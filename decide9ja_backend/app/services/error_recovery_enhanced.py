"""
Tade Error Recovery Module

Implements graceful error handling with:
- Clarification questions instead of dead ends
- Multiple retry paths
- Helpful suggestions
- Menu fallbacks

Usage: Replace generic error messages with recovery handlers.
"""

from typing import Optional, List, Dict, Callable
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RecoveryOption:
    """Single recovery option presented to user"""
    id: str
    label: str
    description: str
    action: str


class ErrorRecoveryHandler:
    """
    Handle conversation errors gracefully.
    
    Instead of "I don't understand", provide options.
    """
    
    @staticmethod
    def ambiguous_location(attempted: str, suggestions: List[str]) -> str:
        """
        When location parsing is unclear.
        
        Example:
        User: "I dey Surulere"
        System: Not sure if Surulere, Lagos or Surulere, Oyo
        """
        options_text = "\n".join([f"{i+1}. {sugg}" for i, sugg in enumerate(suggestions[:5])])
        
        return f"""I want to make sure I help you correctly. Did you mean:

{options_text}

Reply with the number (1-{len(suggestions[:5])}) or type your location again."""
    
    @staticmethod
    def unknown_location(location_text: str) -> str:
        """When location is not recognized"""
        return f"""I'm not familiar with "{location_text}". 

Could you try:
• A major city (e.g., "Lagos", "Kano", "Port Harcourt")
• Your state (e.g., "Lagos State", "Kano State")
• Or type "help" for assistance"""
    
    @staticmethod
    def unknown_representative(location: str) -> str:
        """When representative lookup fails"""
        return f"""I couldn't find representative data for {location}. This might be because:

1. The location is new or recently changed
2. Our database needs updating  
3. You're asking about a local government we don't have yet

What I can do:
• Try a nearby major city
• Give you contact info for your state government
• Help with budget information instead

What would you prefer?"""
    
    @staticmethod
    def query_too_vague(original_query: str) -> str:
        """When we can't determine intent"""
        return f"""I want to help, but I need to understand better. Are you asking about:

1. 🔍 Finding your elected representatives
2. 💰 Budget or spending information
3. 📰 Recent political news
4. 📚 Historical archives (old newspapers)
5. 🗳️ Elections or voting

Reply with 1, 2, 3, 4, or 5."""
    
    @staticmethod
    def no_results_found(query_type: str, query: str) -> str:
        """When search returns no results"""
        suggestions = {
            "representative": "Try checking your voter's card for your constituency",
            "budget": "Try a different year or broader category (e.g., just 'health' instead of 'primary health centers')",
            "news": "Try different keywords or a broader time range",
            "archive": "Try a different year or broader topic"
        }
        
        suggestion = suggestions.get(query_type, "Try different keywords")
        
        return f"""I didn't find anything matching "{query}".

{suggestion}

Or try:
• Type "menu" to see all options
• Type "help" for assistance"""
    
    @staticmethod
    def controversial_topic_detected(topic: str) -> str:
        """When query touches controversial political topics"""
        return f"""That's an important question about {topic}. I'll provide balanced information from multiple sources.

Please note: Tade remains neutral and provides facts from official sources, not opinions.

Here are the perspectives I found..."""
    
    @staticmethod
    def context_compression_recovery(last_topic: str, last_query: str = None) -> str:
        """When context is lost due to compression"""
        recovery = f"Quick reminder — we were talking about {last_topic}."
        
        if last_query:
            recovery += f" You asked about: {last_query}"
        
        recovery += "\n\nWhat would you like to know about it? Or type 'menu' to start fresh."
        
        return recovery
    
    @staticmethod
    def api_failure(service: str) -> str:
        """When external API fails"""
        return f"""I'm having trouble accessing {service} right now. This is a technical issue on our end.

Let me try a different approach, or you can:
• Try again in a few minutes
• Ask about something else
• Type "status" to check system status"""
    
    @staticmethod
    def rate_limit_hit() -> str:
        """When rate limit is exceeded"""
        return """You're sending messages very quickly! To ensure quality responses, please wait a moment before your next question.

This helps me think through your questions properly. ⏱️"""
    
    @staticmethod
    def general_error(retry_count: int = 0) -> str:
        """Generic error with escalation"""
        if retry_count == 0:
            return "I didn't quite catch that. Could you rephrase?"
        elif retry_count == 1:
            return "I'm still not sure I understand. Could you try asking in a different way?"
        else:
            return """I'm having trouble understanding. Let me offer some options:

1. Find my representatives
2. Check budget information  
3. Get recent political news
4. Search historical archives
5. Talk to a human (coming soon)

Reply with 1-5."""
    
    @staticmethod
    def menu_options() -> str:
        """Universal menu fallback"""
        return """Here's what I can help you with:

🗳️ *Your Representatives*
• Who is my representative?
• Who is my senator?
• Contact my governor

💰 *Budget & Spending*
• Lagos budget 2025
• Federal health allocation
• Compare state budgets

📰 *News & Updates*
• Latest political news
• What's happening in [state]
• Breaking news

📚 *Historical Archives*
• What happened in 1999?
• June 12 election history
• [Topic] in 2000s

Type any of these or just ask naturally!"""


class ProgressiveDisclosure:
    """
    Gradually reveal complexity as user engages.
    
    Don't overwhelm new users with all features.
    """
    
    @staticmethod
    def get_onboarding_message(interaction_count: int) -> str:
        """Return appropriate message based on interaction count"""
        
        if interaction_count == 0:
            return """Hello! I'm Tade, your civic engagement companion. 🇳🇬

I can help you:
• Find your elected representatives
• Check government budgets
• Get political news
• Search historical archives

Let's start simple — which state are you in?"""
        
        elif interaction_count == 1:
            return """Great! Now I know where you are. 

Quick tip: You can ask me things like:
• "Who represents me?"
• "What's in the Lagos budget?"
• "News about education"

What would you like to know?"""
        
        elif interaction_count == 2:
            return """By the way, I can also search through historical newspapers from 1960-2010. 

Try asking: "What happened during the 1999 election?" or "Tell me about June 12"

What else can I help with?"""
        
        else:
            # Regular user - no special onboarding
            return None
    
    @staticmethod
    def suggest_advanced_features(usage_patterns: Dict) -> Optional[str]:
        """Suggest features based on usage patterns"""
        
        # If user always asks about representatives
        if usage_patterns.get("representative_queries", 0) > 5:
            return """I noticed you check representatives often. 

💡 Tip: I can send you weekly updates when new information is available. Would you like that?"""
        
        # If user asks about budgets
        if usage_patterns.get("budget_queries", 0) > 3:
            return """You're interested in budgets! 

Did you know I can compare budgets across states? Try: "Compare Lagos and Kano health budgets\""""
        
        return None


# Recovery action registry
RECOVERY_ACTIONS = {
    "show_menu": ErrorRecoveryHandler.menu_options,
    "clarify_location": ErrorRecoveryHandler.ambiguous_location,
    "suggest_representative": ErrorRecoveryHandler.unknown_representative,
    "vague_query_options": ErrorRecoveryHandler.query_too_vague,
    "no_results": ErrorRecoveryHandler.no_results_found,
    "general_error": ErrorRecoveryHandler.general_error,
}


def handle_error(error_type: str, **kwargs) -> str:
    """
    Main error handling entry point.
    
    Usage:
        response = handle_error("ambiguous_location", 
                               attempted="Surulere", 
                               suggestions=["Surulere, Lagos", "Surulere, Oyo"])
    """
    handler = RECOVERY_ACTIONS.get(error_type, ErrorRecoveryHandler.general_error)
    
    try:
        return handler(**kwargs)
    except Exception as e:
        logger.error(f"Error in recovery handler: {e}")
        return ErrorRecoveryHandler.general_error()


# Example usage in message handler
def enhanced_error_handling_example():
    """Example of how to integrate error recovery"""
    
    # OLD WAY (generic):
    # return "Sorry, I don't understand"
    
    # NEW WAY (helpful):
    # return handle_error("vague_query_options")
    
    # Or with context:
    # return handle_error("ambiguous_location", 
    #                    attempted=user_input,
    #                    suggestions=["Option 1", "Option 2"])
    
    pass
