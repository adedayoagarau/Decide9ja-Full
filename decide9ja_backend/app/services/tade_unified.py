"""
Tade Unified Integration

Brings NEW Tade (tade-bot) features into OLD Tade (Decide9ja):
- Advanced location identification (fuzzy matching + Pidgin patterns)
- Working memory enhancement
- Supermemory integration
- Better tool orchestration

This is the master integration file that ties everything together.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass

# Import our modules
from app.services.working_memory_enhanced import (
    WorkingMemory, 
    ConversationStage, 
    handle_stage_transition
)
from app.services.error_recovery_enhanced import ErrorRecoveryHandler, handle_error
from app.services.supermemory_integration import (
    TadeSupermemory,
    enhance_tade_with_supermemory,
    get_supermemory_context
)

logger = logging.getLogger(__name__)


# ============================================================================
# NEW TADE TOOLS (ported from TypeScript)
# ============================================================================

class LocationIdentifier:
    """
    Advanced location identification with fuzzy matching.
    Ported from NEW Tade's identify-location.ts
    """
    
    # Nigerian states
    NIGERIAN_STATES = [
        "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa",
        "Benue", "Borno", "Cross River", "Delta", "Ebonyi", "Edo",
        "Ekiti", "Enugu", "FCT", "Gombe", "Imo", "Jigawa", "Kaduna",
        "Kano", "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa",
        "Niger", "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers",
        "Sokoto", "Taraba", "Yobe", "Zamfara"
    ]
    
    # LGA mapping (abbreviated - full list has 774)
    STATE_LGA_MAP = {
        "Lagos": ["Ikeja", "Lagos Island", "Lagos Mainland", "Surulere", "Eti-Osa", "Kosofe", "Mushin", "Oshodi-Isolo", "Shomolu", "Agege", "Ajeromi-Ifelodun", "Alimosho", "Amuwo-Odofin", "Apapa", "Badagry", "Epe", "Ibeju-Lekki", "Ifako-Ijaiye", "Ikorodu", "Ojo", "Olorunda"],
        "Kano": ["Fagge", "Dala", "Gwale", "Kano Municipal", "Tarauni", "Nasarawa", "Kumbotso", "Ungogo", "Bichi", "Bagwai", "Dambatta", "Dawakin Kudu", "Dawakin Tofa", "Doguwa", "Gabásawa", "Garko", "Garun Mallam", "Gaya", "Gezawa", "Gwale", "Gwarzo", "Kabo", "Kano Municipal", "Karaye", "Kibiya", "Kirù", "Kumbotso", "Kunchi", "Kura", "Madobi", "Makoda", "Minjibir", "Nasarawa", "Rano", "Rimin Gado", "Rogo", "Shanono", "Sumaila", "Takai", "Tarauni", "Tofa", "Tsanyawa", "Tudun Wada", "Ungogo", "Warawa", "Wudil"],
        "Rivers": ["Port Harcourt", "Obio-Akpor", "Okrika", "Ogu-Bolo", "Eleme", "Tai", "Gokana", "Khana", "Oyigbo", "Opobo-Nkoro", "Andoni", "Bonny", "Degema", "Asari-Toru", "Akuku-Toru", "Abua-Odual", "Ahoada West", "Ahoada East", "Ogba-Egbema-Ndoni", "Emohua", "Ikwerre", "Etche"],
        # Add more states as needed
    }
    
    # Location aliases
    LOCATION_ALIASES = {
        "lag": "Lagos",
        "lagos state": "Lagos",
        "kano state": "Kano",
        "ph": "Port Harcourt",
        "portharcourt": "Port Harcourt",
        "abuja": "FCT",
        "fct abuja": "FCT",
        "ibadan": "Oyo",
    }
    
    # Pidgin patterns for location extraction
    PIDGIN_PATTERNS = [
        r"i dey (\w+(?:\s+\w+)*)",
        r"i dey stay (\w+(?:\s+\w+)*)",
        r"na (\w+(?:\s+\w+)*) i dey",
        r"i live for (\w+(?:\s+\w+)*)",
        r"my location na (\w+(?:\s+\w+)*)",
        r"i am in (\w+(?:\s+\w+)*)",
        r"i'm in (\w+(?:\s+\w+)*)",
        r"i stay (\w+(?:\s+\w+)*)",
    ]
    
    def identify(self, message: str, current_state: str = None) -> Dict[str, Any]:
        """
        Identify location from user message.
        
        Returns:
            {
                "success": bool,
                "state": str or None,
                "lga": str or None,
                "message": str,
                "needs_clarification": bool
            }
        """
        import re
        
        normalized = message.lower().strip()
        
        # Try aliases first
        if normalized in self.LOCATION_ALIASES:
            state = self.LOCATION_ALIASES[normalized]
            return {
                "success": True,
                "state": state,
                "lga": None,
                "message": f"Got am! You dey {state} State.",
                "needs_clarification": True,
                "clarification_question": f"Which LGA for {state} you dey?"
            }
        
        # Extract location using patterns
        extracted = None
        for pattern in self.PIDGIN_PATTERNS:
            match = re.search(pattern, normalized, re.IGNORECASE)
            if match:
                extracted = match.group(1).strip()
                break
        
        # If no pattern match, use whole message
        if not extracted:
            extracted = re.sub(r'\b(i|am|in|the|state|area|local|government|lga)\b', '', normalized).strip()
        
        if not extracted:
            return {
                "success": False,
                "state": None,
                "lga": None,
                "message": "I no understand where you dey. Which state you dey?",
                "needs_clarification": True,
                "clarification_question": "Which Nigerian state are you in? (e.g., Lagos, Kano, Rivers)"
            }
        
        # Try to identify state
        state = current_state
        lga = None
        
        if not state:
            state_match = self._fuzzy_match(extracted, self.NIGERIAN_STATES)
            if state_match:
                state = state_match
        
        # If state identified, try to find LGA
        if state and state in self.STATE_LGA_MAP:
            lgas = self.STATE_LGA_MAP[state]
            lga_match = self._fuzzy_match(extracted, lgas)
            if lga_match:
                lga = lga_match
        
        # If no state found but might be LGA
        if not state:
            for st, lgas in self.STATE_LGA_MAP.items():
                lga_match = self._fuzzy_match(extracted, lgas)
                if lga_match:
                    state = st
                    lga = lga_match
                    break
        
        if state:
            response = f"Got am! You dey {lga}, {state} State." if lga else f"Okay, you dey {state} State."
            return {
                "success": True,
                "state": state,
                "lga": lga,
                "message": response,
                "needs_clarification": not lga,
                "clarification_question": None if lga else f"Which LGA for {state} you dey?"
            }
        
        return {
            "success": False,
            "state": None,
            "lga": None,
            "message": "I no fit find that location. Abeg tell me which state you dey.",
            "needs_clarification": True,
            "clarification_question": "Which Nigerian state are you in? (Lagos, Kano, Rivers, etc.)"
        }
    
    def _fuzzy_match(self, input_str: str, options: List[str]) -> Optional[str]:
        """Find best fuzzy match"""
        normalized = input_str.lower().strip()
        
        best_match = None
        best_score = 0
        
        for option in options:
            option_lower = option.lower()
            
            # Exact match
            if normalized == option_lower:
                return option
            
            # Contains match
            if option_lower in normalized or normalized in option_lower:
                score = min(len(normalized), len(option_lower)) / max(len(normalized), len(option_lower))
                if score > best_score:
                    best_score = score
                    best_match = option
            
            # Word matching
            input_words = normalized.split()
            option_words = option_lower.split()
            match_count = sum(1 for word in input_words if len(word) > 2 and any(word in ow or ow in word for ow in option_words))
            
            if input_words:
                word_score = match_count / len(input_words)
                if word_score > best_score:
                    best_score = word_score
                    best_match = option
        
        return best_match if best_score > 0.5 else None


# ============================================================================
# UNIFIED MESSAGE HANDLER
# ============================================================================

@dataclass
class TadeContext:
    """Complete context for handling a message"""
    phone: str
    message: str
    user_state: Any
    working_memory: WorkingMemory
    supermemory: TadeSupermemory
    location_identifier: LocationIdentifier


class UnifiedTadeHandler:
    """
    Master handler that combines:
    - NEW Tade tools (location identification)
    - Working memory enhancement
    - Supermemory integration
    """
    
    def __init__(self):
        self.location_id = LocationIdentifier()
        self.supermemory = TadeSupermemory()
    
    async def handle_message(self, phone: str, message: str, media_url: str = None) -> str:
        """
        Main entry point for handling messages.
        
        Flow:
        1. Load/create working memory
        2. Get Supermemory context
        3. Stage-based routing
        4. Execute tools if needed
        5. Store in Supermemory
        """
        
        # 1. Load states
        user_state = await self._get_user_state(phone)
        working_memory = await self._get_working_memory(phone)
        
        # 2. Get Supermemory context
        supermemory_context = await get_supermemory_context(phone, message)
        
        # 3. Detect intent (simple for now)
        intent = self._detect_intent(message)
        
        # 4. Stage-based handling
        try:
            response = handle_stage_transition(
                working_memory,
                message,
                intent,
                user_state
            )
            
            # Handle special signals
            if response == "__TRIGGER_RETRIEVAL__":
                response = await self._execute_tools(working_memory, user_state)
            
            # 5. Add Supermemory context if relevant
            if supermemory_context and working_memory.stage != ConversationStage.GREETING:
                response = f"*{supermemory_context}*\n\n{response}"
            
            # 6. Store interaction
            await enhance_tade_with_supermemory(
                phone=phone,
                user_message=message,
                tade_response=response,
                metadata={
                    "location": user_state.state if user_state else None,
                    "lga": user_state.lga if user_state else None,
                    "stage": working_memory.stage.value,
                    "intent": intent
                }
            )
            
            # 7. Save working memory
            await self._save_working_memory(working_memory)
            
            return response
            
        except Exception as e:
            logger.error(f"Handler error: {e}")
            working_memory.record_error(str(e))
            return handle_error("general_error", retry_count=working_memory.retry_count)
    
    async def _execute_tools(self, working_memory: WorkingMemory, user_state) -> str:
        """Execute tools based on current query"""
        
        query_type = working_memory.current_query.get("type")
        
        if query_type == "location_collection":
            # Use NEW Tade location tool
            result = self.location_id.identify(
                working_memory.current_query.get("query_text", ""),
                working_memory.location.get("state")
            )
            
            if result["success"]:
                working_memory.set_location(
                    state=result.get("state"),
                    lga=result.get("lga")
                )
                
                # Update user state
                if user_state:
                    user_state.state = result.get("state")
                    user_state.lga = result.get("lga")
                
                working_memory.transition_to(
                    ConversationStage.QUERY_UNDERSTANDING,
                    "location_complete"
                )
                
                return f"{result['message']} How can I help you today?"
            else:
                return result["message"]
        
        # Other tool types...
        return "What would you like to know?"
    
    def _detect_intent(self, message: str) -> str:
        """Simple intent detection"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["representative", "rep", "senator", "governor"]):
            return "find_representative"
        elif any(word in message_lower for word in ["budget", "allocation", "spent", "money"]):
            return "budget_inquiry"
        elif any(word in message_lower for word in ["news", "latest", "today", "recent"]):
            return "news_update"
        elif any(word in message_lower for word in ["history", "archive", "past", "1999"]):
            return "historical_question"
        else:
            return "general"
    
    async def _get_user_state(self, phone: str):
        """Load user state"""
        from app.services.state_manager import _get_state_async
        return await _get_state_async(phone)
    
    async def _get_working_memory(self, phone: str) -> WorkingMemory:
        """Load or create working memory"""
        # Try to load from storage
        # For now, create new (implement persistence later)
        return WorkingMemory(user_phone=phone)
    
    async def _save_working_memory(self, working_memory: WorkingMemory):
        """Save working memory"""
        # Implement persistence
        pass


# ============================================================================
# QUICK START
# ============================================================================

"""
To use in message_handler_v4.py:

    from app.services.tade_unified import UnifiedTadeHandler
    
    # Initialize once
    tade_handler = UnifiedTadeHandler()
    
    # In handle_message:
    response = await tade_handler.handle_message(phone, text)
    return response

That's it! The unified handler manages:
- Working memory
- Supermemory
- NEW Tade tools
- Stage-based routing
- Error recovery
"""
