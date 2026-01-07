"""
Decide9ja Message Handler v2
Conversation-design-driven implementation by Google Deepmind agent.

Design principles:
- Single ask per turn
- Context-aware followups
- No filler phrases
- Graceful error recovery
- Action-first responses
- Persistent User Profile Integration
"""
import logging
import re
import hashlib
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import uuid
import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor

# Import services for integration
from app.services import location as location_service
from app.services import whatsapp
from app.database import UserReport, Politician, Interaction
import time

# New Services
from app.services import memory
from app.services import router
from app.services import realtime

logger = logging.getLogger(__name__)


# ===========================================
# ENUMS & DATA CLASSES
# ===========================================

from app.services.router import router, Intent, DataStrategy


class FlowState(Enum):
    IDLE = "idle"
    ONBOARDING = "onboarding"
    ISSUE_FLOW = "issue_flow"
    AWAITING_CLARIFICATION = "awaiting_clarification"


@dataclass
class ActiveContext:
    """Tracks active entities for followup resolution."""
    politician: Optional[str] = None
    politician_position: Optional[str] = None
    politician_party: Optional[str] = None
    topic: Optional[str] = None  # "record", "news", "policies"
    last_updated: Optional[datetime] = None
    
    def set_politician(self, name: str, position: str = None, party: str = None):
        self.politician = name
        self.politician_position = position
        self.politician_party = party
        self.last_updated = datetime.now()
    
    def is_stale(self, minutes: int = 5) -> bool:
        if not self.last_updated:
            return True
        return datetime.now() - self.last_updated > timedelta(minutes=minutes)
    
    def clear(self):
        self.politician = None
        self.politician_position = None
        self.politician_party = None
        self.topic = None


@dataclass
class UserProfile:
    """Persistent user data."""
    name: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    voted_2023: Optional[bool] = None
    concerns: List[str] = field(default_factory=list)
    language: str = "english"  # english, pidgin, yoruba, hausa, igbo
    voice_mode: bool = False  # If True, respond with voice notes
    voice_id: str = "1"  # Voice selection (1-8, male, female)
    
    def has_location(self) -> bool:
        return bool(self.state and self.lga)


@dataclass 
class ConversationState:
    """Full conversation state for a user."""
    user_id: str = "" # Added
    flow: FlowState = FlowState.IDLE
    flow_step: int = 0
    flow_data: Dict = field(default_factory=dict)
    context: ActiveContext = field(default_factory=ActiveContext)
    profile: UserProfile = field(default_factory=UserProfile)

    history: List[Dict] = field(default_factory=list)
    latest_intent: Optional[str] = None # For analytics
    last_updated: datetime = field(default_factory=datetime.now) # State Expiry tracking
    
    # Context Tracking
    active_politician_id: Optional[str] = None
    active_politician_name: Optional[str] = None
    
    def is_stale(self, minutes: int = 30) -> bool:
        """Check if state is stale."""
        return datetime.now() - self.last_updated > timedelta(minutes=minutes)

    def touch(self):
        """Update last updated timestamp."""
        self.last_updated = datetime.now()


# ===========================================
# CONSTANTS
# ===========================================

NIGERIAN_STATES = {
    "abia", "adamawa", "akwa ibom", "anambra", "bauchi", "bayelsa", "benue",
    "borno", "cross river", "delta", "ebonyi", "edo", "ekiti", "enugu",
    "fct", "gombe", "imo", "jigawa", "kaduna", "kano", "katsina", "kebbi",
    "kogi", "kwara", "lagos", "nasarawa", "niger", "ogun", "ondo", "osun",
    "oyo", "plateau", "rivers", "sokoto", "taraba", "yobe", "zamfara",
    "abuja", "federal capital territory"
}

# Nigerian Language Detection Markers
PIDGIN_MARKERS = {
    "wetin", "dey", "no be", "na", "una", "abeg", "abi", "shey", "wahala", 
    "oya", "sha", "biko", "how far", "no vex", "e don", "e dey", "im no",
    "wey", "sabi", "palava", "chop", "yarsh", "japa", "gist", "yarn"
}

YORUBA_MARKERS = {
    "bawo", "ẹ káàárọ̀", "o dabo", "e karo", "e kaale", "se", "ṣé", "kini",
    "ewo", "oruko", "omo", "baba", "iya", "ọjọ", "ile", "ọba", "olori",
    "oluwa", "alafia", "pẹlẹ", "jowo", "dara", "kosi", "rara"
}

HAUSA_MARKERS = {
    "sannu", "yaya", "ina", "lafiya", "nagode", "ba", "kai", "ke", "wannan",
    "wancan", "shi", "ita", "su", "mu", "da", "kuma", "amma", "saboda",
    "domin", "idan", "lokacin", "gobe", "jiya", "yau", "barka"
}

IGBO_MARKERS = {
    "kedu", "ndewo", "daalu", "ọ dị", "biko", "nwanne", "nna", "nne", 
    "ụmụ", "onye", "ebe", "ihe", "oge", "ụbọchị", "afo", "mmiri", "ọrụ",
    "ezigbo", "ọma", "ojoo", "mba", "ee", "ịhụ", "si", "na"
}


def detect_language(text: str) -> str:
    """
    Detect Nigerian language from text.
    Returns: 'english', 'pidgin', 'yoruba', 'hausa', or 'igbo'
    """
    text_lower = text.lower()
    words = set(text_lower.split())
    
    # Count marker matches for each language
    scores = {
        "pidgin": len(words & PIDGIN_MARKERS) + sum(1 for m in PIDGIN_MARKERS if m in text_lower and ' ' in m),
        "yoruba": len(words & YORUBA_MARKERS) + sum(1 for m in YORUBA_MARKERS if m in text_lower and ' ' in m),
        "hausa": len(words & HAUSA_MARKERS) + sum(1 for m in HAUSA_MARKERS if m in text_lower and ' ' in m),
        "igbo": len(words & IGBO_MARKERS) + sum(1 for m in IGBO_MARKERS if m in text_lower and ' ' in m),
    }
    
    # Get highest scoring language
    max_lang = max(scores, key=scores.get)
    max_score = scores[max_lang]
    
    # Require at least 1 marker match to switch from English
    if max_score >= 1:
        return max_lang
    
    return "english"


# Voice Mode Triggers
VOICE_ON_TRIGGERS = {
    "voice", "vn", "audio", "voice note", "voice notes", "send voice", 
    "respond with voice", "talk to me", "speak", "audio mode", 
    "voice mode", "use voice", "with voice"
}

VOICE_OFF_TRIGGERS = {
    "text", "text mode", "no voice", "stop voice", "text only", 
    "typing", "write", "use text"
}


def detect_voice_preference(text: str) -> Optional[bool]:
    """
    Detect if user wants voice mode on/off.
    Returns: True (turn on), False (turn off), None (no change)
    """
    text_lower = text.lower()
    
    # Check for voice on triggers
    for trigger in VOICE_ON_TRIGGERS:
        if trigger in text_lower:
            return True
    
    # Check for voice off triggers
    for trigger in VOICE_OFF_TRIGGERS:
        if trigger in text_lower:
            return False
    
    return None


def detect_voice_selection(text: str) -> Optional[str]:
    """
    Detect if user wants to change voice.
    Returns: voice ID (1-8) or None if no selection.
    """
    import re
    text_lower = text.lower()
    
    # Patterns: "use voice 3", "voice 5", "change voice to 2"
    patterns = [
        r"use voice (\d)",
        r"voice (\d)",
        r"change voice (?:to )?(\d)",
        r"switch (?:to )?voice (\d)",
        r"voice number (\d)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            num = match.group(1)
            if num in "12345678":
                return num
    
    # Check for male/female aliases
    if "male voice" in text_lower or "use male" in text_lower:
        return "male"
    if "female voice" in text_lower or "use female" in text_lower:
        return "female"
    
    return None


# ===========================================
# INTENT CLASSIFICATION
# ===========================================

# ===========================================
# RESPONSE TEMPLATES (imported from Tade persona)
# ===========================================

from app.services.tade_persona import Templates, get_time_of_day


# ===========================================
# PARSING HELPERS  
# ===========================================

def parse_name(text: str) -> str:
    """Extract name from user message."""
    text = text.strip()
    
    patterns = [
        r"(?:my name is|i'm|i am|call me|it's)\s+([A-Za-z]+)",
        r"^([A-Za-z]+)$",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).capitalize()
    
    # First word that's not a common non-name
    non_names = {"my", "name", "is", "i'm", "i", "am", "call", "me", "it's", "yes", "no", "hi", "hello"}
    for word in text.split():
        clean = re.sub(r'[^\w]', '', word.lower())
        if clean and clean not in non_names:
            return word.capitalize()
    
    return text.split()[0].capitalize() if text.split() else "Friend"


def parse_state(text: str) -> Optional[str]:
    """Extract Nigerian state from user message."""
    text_lower = text.lower().strip()
    
    # Prefer "live in" over "from" (residence > origin)
    live_match = re.search(r"(?:live|stay|based|living)\s+(?:in|at)\s+(\w+)", text_lower)
    if live_match:
        potential = live_match.group(1).replace("state", "").strip()
        if potential in NIGERIAN_STATES:
            return potential.title()
    
    # "from X" or "in X"
    from_match = re.search(r"(?:from|in)\s+(\w+)", text_lower)
    if from_match:
        potential = from_match.group(1).replace("state", "").strip()
        if potential in NIGERIAN_STATES:
            return potential.title()
    
    # Direct match
    for state in NIGERIAN_STATES:
        if state in text_lower:
            if state == "fct" or state == "abuja":
                return "FCT"
            return state.title()
    
    return None


def parse_lga(text: str) -> str:
    """Extract LGA from user message."""
    cleaned = re.sub(r"\s*(lga|local\s*government(\s*area)?|lg)\s*$", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(i'm|i am|i live|i stay)\s+(in|at)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip().title()


def extract_politician_from_response(text: str) -> Optional[Tuple[str, str, str]]:
    """Extract politician name, position, party from bot response."""
    # Pattern: Name (Party) or Name is Position
    patterns = [
        r"(?:Governor|Senator|Hon\.|President|Minister)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*\((\w+)\)",
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+is\s+(Governor|Senator|Representative|Minister|President)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip()
            position = None
            party = None
            
            if "Governor" in text: position = "Governor"
            elif "Senator" in text: position = "Senator"
            elif "Representative" in text or "Hon." in text: position = "House Representative"
            
            for p in ["APC", "PDP", "LP", "NNPP", "APGA"]:
                if p in text:
                    party = p
                    break
            
            return (name, position, party)
    
    return None


# ===========================================
# MAIN HANDLER CLASS
# ===========================================

class MessageHandler:
    """
    Dynamic conversation handler.
    Maintains state, classifies intent, routes to handlers.
    """
    
    def __init__(self, db_session=None, llm_service=None, rag_service=None, web_search=None):
        self.db = db_session
        self.llm = llm_service
        self.rag = rag_service
        self.web_search = web_search
        
        # In-memory state (backed by persistent storage)
        self._states: Dict[str, ConversationState] = {}
    
    def get_state(self, user_hash: str) -> ConversationState:
        """Get or create conversation state, sync with persistent storage."""
        if user_hash not in self._states:
            self._states[user_hash] = ConversationState(user_id=user_hash)
            
            # Load persistent data
            try:
                # Load profile from PostgreSQL
                p = memory.get_user_profile(self.db, user_hash)
                if p:
                    self._states[user_hash].profile.name = p.get("name")
                    self._states[user_hash].profile.state = p.get("state")
                    self._states[user_hash].profile.lga = p.get("lga")
                    
                    # Load Flow State
                    fs = p.get("flow_state", {})
                    if fs:
                        try:
                            self._states[user_hash].flow = FlowState(fs.get("flow", "idle"))
                            self._states[user_hash].flow_step = fs.get("step", 0)
                            self._states[user_hash].flow_data = fs.get("data", {})
                        except ValueError:
                            # Fallback if enum value is invalid
                            self._states[user_hash].flow = FlowState.IDLE
                            
                    # Preferences might be stored in a different format, adapting...
                    prefs = p.get("preferences", {})
                    self._states[user_hash].profile.voted_2023 = prefs.get("voted_2023")
                    self._states[user_hash].profile.concerns = prefs.get("concerns", [])
                    self._states[user_hash].profile.language = prefs.get("language", "english")
                    self._states[user_hash].profile.voice_mode = prefs.get("voice_mode", False)
                    self._states[user_hash].profile.voice_id = prefs.get("voice_id", "1")
            except Exception as e:
                logger.warning(f"Could not load persistent profile: {e}")
                
        return self._states[user_hash]
    
    def _save_profile(self, user_hash: str, state: ConversationState):
        """Save profile and flow state to persistent storage."""
        try:
            # Prepare flow state
            flow_state = {
                "flow": state.flow.value,
                "step": state.flow_step,
                "data": state.flow_data
            }
            
            data = {
                "name": state.profile.name,
                "state": state.profile.state,
                "lga": state.profile.lga,
                "flow_state": flow_state,
                "preferences": {
                    "voted_2023": state.profile.voted_2023,
                    "concerns": state.profile.concerns,
                    "language": state.profile.language,
                    "voice_mode": state.profile.voice_mode,
                    "voice_id": state.profile.voice_id
                }
            }
            memory.update_user_profile(self.db, user_hash, data)
        except Exception as e:
            logger.error(f"Failed to save profile: {e}")

    async def handle(self, user_hash: str, text: str, msg_type: str = "text", 
                     location: dict = None) -> str:
        """Main entry point."""
        try:
            state = self.get_state(user_hash)
            
            # --- 1. STATE EXPIRY CHECK ---
            if state.flow != FlowState.IDLE and state.is_stale(minutes=30):
                logger.info(f"Expiring stale flow for {user_hash}")
                state.flow = FlowState.IDLE
                state.flow_step = 0
                state.flow_data = {}
            state.touch()

            # --- 2. FLOW ESCAPE CHECK ---
            if text.lower() in ["cancel", "stop", "reset", "start over", "abort"]:
                state.flow = FlowState.IDLE
                state.flow_step = 0
                state.flow_data = {}
                state.context.clear()
                return "Reset. What can I do for you?"

            # Clear stale context
            if state.context.is_stale(minutes=10):
                state.context.clear()
            
            # Add to history and persistent memory
            state.history.append({"role": "user", "text": text, "time": datetime.now().isoformat()})
            if len(state.history) > 10:
                state.history = state.history[-10:]
                
            # Save user message to persistent memory
            if self.db:
                try:
                    memory.add_message(self.db, user_hash, "user", text)
                except Exception as db_err:
                    logger.error(f"DB Error saving msg: {db_err}")
            
            start_time = time.time()
            
            # Detect and update language preference
            if text and msg_type == "text":
                detected_lang = detect_language(text)
                if detected_lang != "english":
                    state.profile.language = detected_lang
                    logger.info(f"Language detected: {detected_lang}")
                
                # Detect voice preference
                voice_pref = detect_voice_preference(text)
                if voice_pref is not None:
                    state.profile.voice_mode = voice_pref
                    logger.info(f"Voice mode: {'ON' if voice_pref else 'OFF'}")
                
                # Detect voice selection
                voice_sel = detect_voice_selection(text)
                if voice_sel:
                    state.profile.voice_id = voice_sel
                    logger.info(f"Voice selected: {voice_sel}")
            
            
            # Handle location messages
            if msg_type == "location" and location:
                response = await self._handle_location(state, location)
            
            # Handle active flow
            elif state.flow != FlowState.IDLE:
                response = await self._continue_flow(state, text)
            
            # Normal message processing
            else:
                response = await self._process_message(state, text)
            
            # Extract entities from response to update context
            extracted = extract_politician_from_response(response)
            if extracted:
                name, position, party = extracted
                state.context.set_politician(name, position, party)
                state.active_politician_name = name # Update active tracker
            
            # Add response to history
            state.history.append({"role": "assistant", "text": response, "time": datetime.now().isoformat()})
            
            # Save assistant response to persistent memory
            if self.db:
                try:
                    memory.add_message(self.db, user_hash, "assistant", response)
                except Exception as e:
                    logger.error(f"DB Error saving response: {e}")
            
            # Persist profile if changed
            # (Simple check: always save on successful turn or intelligent diff)
            self._save_profile(user_hash, state)

            # Log Interaction
            duration = int((time.time() - start_time) * 1000)
            self._log_interaction(user_hash, text, response, state.latest_intent, duration)

            return response
            
        except Exception as e:
            logger.error(f"Handler error: {e}")
            return Templates.ERROR

    def _log_interaction(self, user_id: str, query: str, response: str, intent: str, duration: int):
        """Log interaction to database asynchronously (fire and forget for now)."""
        if not self.db: return
        try:
            interaction = Interaction(
                user_id=user_id,
                query=query,
                response=response,
                intent=intent,
                response_time_ms=duration
            )
            self.db.add(interaction)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log interaction: {e}")
            self.db.rollback()
    

    
    # === INTENT HANDLERS ===
    
    async def _handle_greeting(self, state: ConversationState, text: str, entities: dict) -> str:
        if state.profile.name:
            # Use time-of-day aware greeting for returning users
            return Templates.get_greeting(name=state.profile.name, time_of_day=get_time_of_day())
        state.flow = FlowState.ONBOARDING
        state.flow_step = 1
        return Templates.WELCOME_NEW
    
    async def _handle_rep_lookup(self, state: ConversationState, text: str, entities: dict) -> str:
        if not state.profile.has_location():
            if state.profile.state:
                state.flow = FlowState.AWAITING_CLARIFICATION
                state.flow_data = {"awaiting": "lga", "for": "rep_lookup"}
                return Templates.NEED_LGA.format(state=state.profile.state)
            else:
                state.flow = FlowState.AWAITING_CLARIFICATION
                state.flow_data = {"awaiting": "state", "for": "rep_lookup"}
                return Templates.NEED_LOCATION
        
        reps = await self._lookup_representatives(state.profile.state, state.profile.lga)
        if reps:
            formatted = self._format_representatives(reps)
            return Templates.REPS_RESULT.format(lga=state.profile.lga, state=state.profile.state, reps_formatted=formatted)
        return Templates.REPS_NOT_FOUND.format(lga=state.profile.lga, state=state.profile.state)
    
    async def _handle_politician_info(self, state: ConversationState, text: str, entities: dict) -> str:
        query = entities.get("politician_query", text)
        info = await self._search_politician(query)
        if info:
            # FIX: Merge with existing context if same politician to preserve Party/Position
            if state.context.politician and info["name"].lower() in state.context.politician.lower():
                if not info.get("party") and state.context.politician_party:
                    info["party"] = state.context.politician_party
                if not info.get("position") and state.context.politician_position:
                    info["position"] = state.context.politician_position

            state.context.set_politician(info["name"], info.get("position"), info.get("party"))
            return Templates.POLITICIAN_INFO.format(
                name=info["name"],
                position=info.get("position", "a political figure"),
                party=info.get("party", "Party unknown"),
                bio=info.get("bio", "")
            )
        return Templates.POLITICIAN_NOT_FOUND.format(name=query)
    
    async def _handle_politician_record(self, state: ConversationState, text: str, entities: dict) -> str:
        politician = entities.get("politician_query") or entities.get("resolved_politician")
        if not politician and state.context.politician:
            politician = state.context.politician
        if not politician:
            return Templates.FOLLOWUP_NO_CONTEXT
        
        record = await self._search_politician_record(politician)
        if record:
            state.context.set_politician(politician)
            state.context.topic = "record"
            return Templates.POLITICIAN_RECORD.format(name=politician, record_summary=record)
        return Templates.POLITICIAN_NO_RECORD.format(name=politician)
    
    async def _handle_news_query(self, state: ConversationState, text: str, entities: dict) -> str:
        """Handle news/issue queries with Real-Time Data + RAG."""
        context = ""
        
        
        # Parallel Fetching (RAG + Realtime) Safe Async
        try:
             # Use asyncio.gather safely, avoiding improper loop usage
             results = await asyncio.gather(
                 self._search_rag(text) if self.rag else asyncio.sleep(0),
                 asyncio.to_thread(realtime.get_realtime_data, text),
                 return_exceptions=True
             )
             
             rag_result = results[0]
             rt_data = results[1]
             
             # Process RAG
             if isinstance(rag_result, str) and rag_result:
                 context += f"\n[Database Context]\n{rag_result}\n"
                 
             # Process Realtime
             if not isinstance(rt_data, Exception) and rt_data and (rt_data.get('news') or rt_data.get('web')):
                 context += f"\n{rt_data['combined_text']}\n"
             elif isinstance(rt_data, Exception):
                 logger.error(f"Realtime fetch failed: {rt_data}")
        except Exception as e:
             logger.error(f"Parallel fetch failed: {e}")
        
        if not context:
            return Templates.NEWS_NOT_FOUND
        
        # Pass through LLM for conversational response
        if self.llm:
            try:
                # Build user context
                user_context = ""
                if state.profile.name:
                    user_context = f"User: {state.profile.name}"
                    if state.profile.state:
                        user_context += f" from {state.profile.state}"
                
                # Add language preference
                if state.profile.language != "english":
                    lang_name = state.profile.language.title()
                    user_context += f"\n\n⚠️ RESPOND IN {lang_name.upper()}. The user prefers {lang_name}."
                
                response = await self.llm.generate_response(
                    user_message=text,
                    context=context,
                    user_context=user_context,
                    conversation_context=""
                )
                return response
            except Exception as e:
                logger.error(f"LLM failed in news query: {e}")
        
        # Fallback to template if LLM not available
        return Templates.NEWS_RESULT.format(summary=context[:400], source="Various sources")
    
    async def _handle_issue_report(self, state: ConversationState, text: str, entities: dict) -> str:
        state.flow = FlowState.ISSUE_FLOW
        state.flow_step = 1
        return Templates.ISSUE_START
    
    async def _handle_voter_reg(self, state: ConversationState, text: str, entities: dict) -> str:
        return Templates.VOTER_REG
    
    async def _handle_followup(self, state: ConversationState, text: str, entities: dict) -> str:
        politician = entities.get("resolved_politician") or state.context.politician
        if not politician:
            return Templates.FOLLOWUP_NO_CONTEXT
        text_lower = text.lower()
        if any(w in text_lower for w in ["done", "record", "bills", "achievements", "projects"]):
            return await self._handle_politician_record(state, text, {"politician_query": politician})
        if any(w in text_lower for w in ["news", "latest", "recent"]):
            return await self._handle_news_query(state, f"news about {politician}", {})
        return await self._handle_politician_info(state, politician, {"politician_query": politician})
    
    async def _handle_help(self, state: ConversationState, text: str, entities: dict) -> str:
        return Templates.HELP
    
    async def _handle_reset(self, state: ConversationState, text: str, entities: dict) -> str:
        state.flow = FlowState.IDLE
        state.flow_step = 0
        state.context.clear()
        return "Reset complete. Say \"hi\" to start fresh."
    
    async def _handle_confirmation(self, state: ConversationState, text: str, entities: dict) -> str:
        return "What would you like to do next?"
    
    async def _handle_fallback(self, state: ConversationState, text: str, entities: dict) -> str:
        """Handle fallback using Smart Router with Hybrid Strategy."""
        context = ""
        
        # 1. Decide Strategy
        strategy = router.decide_data_strategy(Intent.FALLBACK, text)
        logger.info(f"Fallback Strategy: {strategy.value}")
        
        # 2. Execute Strategy
        try:
            rag_task = self._search_rag(text) if self.rag else asyncio.sleep(0)
            rt_task = asyncio.to_thread(realtime.get_realtime_data, text)
            
            # Use gather for concurrency
            if strategy == DataStrategy.HYBRID:
                results = await asyncio.gather(rag_task, rt_task, return_exceptions=True)
                rag_res, rt_res = results[0], results[1]
                
                if isinstance(rag_res, str) and rag_res:
                    context += f"\n[Database Context]\n{rag_res}\n"
                if not isinstance(rt_res, Exception) and rt_res and (rt_res.get('news') or rt_res.get('web')):
                    context += f"\n{rt_res['combined_text']}\n"
                    
            elif strategy == DataStrategy.REALTIME_ONLY:
                rt_res = await rt_task
                if rt_res and (rt_res.get('news') or rt_res.get('web')):
                    context += f"\n{rt_res['combined_text']}\n"
            
            elif strategy == DataStrategy.RAG_ONLY:
                rag_res = await rag_task
                if rag_res:
                    context += f"\n[Database Context]\n{rag_res}\n"
                    
        except Exception as e:
            logger.error(f"Fallback fetch error: {e}")
        
        # If we have context AND an LLM, generate a proper response
        if (context or strategy != DataStrategy.NO_DATA) and self.llm:
            try:
                # Build conversation context
                conv_context = ""
                if state.active_politician_name:
                    conv_context = f"Active Topic: {state.active_politician_name}\n"
                
                user_context = ""
                if state.profile.name:
                    user_context = f"User: {state.profile.name}"
                    if state.profile.state:
                        user_context += f" from {state.profile.state}"
                
                # Add language preference for multilingual response
                if state.profile.language != "english":
                    lang_name = state.profile.language.title()
                    user_context += f"\n\n⚠️ RESPOND IN {lang_name.upper()}. The user prefers {lang_name}."
                
                # Generate LLM response
                response = await self.llm.generate_response(
                    user_message=text,
                    context=context,
                    user_context=user_context,
                    conversation_context=conv_context
                )
                return response
            except Exception as e:
                logger.error(f"LLM generation failed in fallback: {e}")
                # Fall through to static responses
        
        # No LLM or no context - use static responses
        if "?" in text or len(text.split()) > 3:
            return Templates.FALLBACK_CONFIDENT
        return Templates.FALLBACK_UNCLEAR
    
    # === FLOW HANDLERS ===
    
    async def _continue_flow(self, state: ConversationState, text: str) -> str:
        state.latest_intent = state.flow.value
        if state.flow == FlowState.ONBOARDING:
            return await self._continue_onboarding(state, text)
        elif state.flow == FlowState.ISSUE_FLOW:
            return await self._continue_issue_flow(state, text)
        elif state.flow == FlowState.AWAITING_CLARIFICATION:
            return await self._handle_clarification(state, text)
        state.flow = FlowState.IDLE
        return await self._process_message(state, text)
    
    async def _continue_onboarding(self, state: ConversationState, text: str) -> str:
        step = state.flow_step
        if step == 1:
            # Got name, ask for state
            name = parse_name(text)
            state.profile.name = name
            state.flow_step = 2
            return Templates.GOT_NAME.format(name=name)
        if step == 2:
            # Got state, ask for LGA
            parsed_state = parse_state(text)
            if parsed_state:
                state.profile.state = parsed_state
                state.flow_step = 3
                return Templates.GOT_STATE.format(state=parsed_state)
            return Templates.STATE_NOT_FOUND
        if step == 3:
            # Got LGA, complete onboarding (skip voting/concerns for now)
            lga = parse_lga(text)
            state.profile.lga = lga
            state.flow = FlowState.IDLE
            state.flow_step = 0
            self._save_profile("", state.profile)
            return Templates.GOT_LGA.format(lga=lga, state=state.profile.state)
        state.flow = FlowState.IDLE
        return Templates.HELP
    
    async def _process_message(self, state: ConversationState, text: str) -> str:
        if state.active_politician_name:
             # Resolve "he/she/him" to active politician
             entities = {} # Initialize entities
             entities["resolved_politician"] = state.active_politician_name
        
        intent, confidence, entities_new = router.classify_intent(text, state.context)
        if 'entities' in locals() and entities:
            # Merge resolved politician if not found in new classification
            if not entities_new.get("resolved_politician") and not entities_new.get("politician_query"):
                 entities_new["resolved_politician"] = entities["resolved_politician"]
        
        state.latest_intent = intent.value
        entities = entities_new
        
        logger.info(f"Intent: {intent.value} ({confidence:.0%})")
        
        # Route to handler
        handlers = {
            Intent.GREETING: self._handle_greeting,
            Intent.REP_LOOKUP: self._handle_rep_lookup,
            Intent.POLITICIAN_INFO: self._handle_politician_info,
            Intent.POLITICIAN_RECORD: self._handle_politician_record,
            Intent.NEWS_QUERY: self._handle_news_query,
            Intent.ISSUE_REPORT: self._handle_issue_report,
            Intent.VOTER_REG: self._handle_voter_reg,
            Intent.FOLLOWUP: self._handle_followup,
            Intent.HELP: self._handle_help,
            Intent.RESET: self._handle_reset,
            Intent.CONFIRMATION: self._handle_confirmation,
            Intent.FALLBACK: self._handle_fallback,
        }
        
        handler = handlers.get(intent, self._handle_fallback)
        return await handler(state, text, entities)
    
    async def _continue_issue_flow(self, state: ConversationState, text: str) -> str:
        step = state.flow_step
        if step == 1:
            state.flow_data["location_text"] = text
            state.flow_step = 2
            return "Got it. Describe the issue briefly."
        if step == 2:
            state.flow_data["description"] = text
            state.flow = FlowState.IDLE
            location = state.flow_data.get("location_text", state.flow_data.get("location_formatted", "Unknown"))
            
            # Save report
            await self._save_issue_report(state.user_id, state.flow_data)
            
            return Templates.ISSUE_COMPLETE.format(issue_type=text[:50], location=location, authority=state.flow_data.get("authority", "Local Government"))
        state.flow = FlowState.IDLE
        return Templates.HELP
    
    async def _handle_location(self, state: ConversationState, location: dict) -> str:
        lat, lng = location.get("lat"), location.get("lng")
        address_info = await self._reverse_geocode(lat, lng)
        
        if state.flow == FlowState.ISSUE_FLOW:
            state.flow_data["location_formatted"] = address_info.get("formatted", f"{lat}, {lng}")
            state.flow_data["authority"] = address_info.get("authority", "Local Government")
            state.flow_step = 2
            return Templates.ISSUE_GOT_LOCATION.format(address=address_info.get("formatted"), lga=address_info.get("lga", "Unknown"), authority=address_info.get("authority", "Local Government"))
        
        if address_info.get("state"): state.profile.state = address_info["state"]
        if address_info.get("lga"): state.profile.lga = address_info["lga"]
        return f"Location saved: {address_info.get('formatted', 'Unknown')}. What do you need?"
    
    async def _handle_clarification(self, state: ConversationState, text: str) -> str:
        awaiting = state.flow_data.get("awaiting")
        for_intent = state.flow_data.get("for")
        
        if awaiting == "state":
            parsed = parse_state(text)
            if parsed:
                state.profile.state = parsed
                if for_intent == "rep_lookup":
                    state.flow_data = {"awaiting": "lga", "for": "rep_lookup"}
                    return Templates.NEED_LGA.format(state=parsed)
            return Templates.STATE_NOT_FOUND
        
        if awaiting == "lga":
            lga = parse_lga(text)
            state.profile.lga = lga
            state.flow = FlowState.IDLE
            if for_intent == "rep_lookup":
                return await self._handle_rep_lookup(state, "", {})
        
        state.flow = FlowState.IDLE
        return Templates.HELP
    
    # === ABSTRACTIONS ===
    async def _lookup_representatives(self, state: str, lga: str) -> Optional[dict]: return None
    async def _search_politician(self, query: str) -> Optional[dict]: return None
    async def _search_politician_record(self, name: str) -> Optional[str]: return None
    async def _search_news(self, query: str) -> Optional[dict]: return None
    async def _search_rag(self, query: str) -> Optional[str]: return None
    async def _reverse_geocode(self, lat: float, lng: float) -> dict: return {"formatted": f"{lat}, {lng}"}
    async def _save_issue_report(self, user_hash: str, report_data: dict) -> bool: return False # Default structure
    
    def _format_representatives(self, reps: dict) -> str:
        lines = []
        if reps.get("governor"):
            g = reps["governor"]
            lines.append(f"Governor: {g['name']} ({g.get('party', '?')})")
        if reps.get("senator"):
            s = reps["senator"]
            lines.append(f"Senator: {s['name']} ({s.get('party', '?')})")
        if reps.get("house_rep"):
            h = reps["house_rep"]
            lines.append(f"House Rep: {h['name']} ({h.get('party', '?')})")
        return "\n".join(lines)


class IntegratedMessageHandler(MessageHandler):
    """Integrated Message Handler."""
    
    def __init__(self, db_session, llm_service, rag_service, web_search_service=None, location_service=None):
        super().__init__(db_session, llm_service, rag_service, web_search_service)
        self.location_service = location_service
    
    async def _lookup_representatives(self, state: str, lga: str) -> Optional[dict]:
        try:
            state_lower = state.lower()
            if state_lower == "oyo":
                from app.services.oyo_state_data import get_oyo_representatives
                return get_oyo_representatives(lga)
            
            if self.db:
                from app.database import Politician
                result = {}
                governor = self.db.query(Politician).filter(Politician.state.ilike(state), Politician.position.ilike("%governor%")).first()
                if governor: result["governor"] = {"name": governor.name, "party": governor.party, "position": governor.position}
                
                senators = self.db.query(Politician).filter(
                    Politician.state.ilike(state),
                    Politician.position.ilike("%senator%")
                ).all()
                
                # Find senator for this LGA (would need proper mapping)
                if senators:
                    # Pick first one or try to match if constituency available
                    s = senators[0]
                    result["senator"] = {
                        "name": s.name,
                        "party": s.party,
                        "district": s.constituency or "Senatorial District"
                    }
                
                # House Rep (by LGA fuzzy match in constituency)
                house_rep = self.db.query(Politician).filter(
                    Politician.state.ilike(state),
                    Politician.position.ilike("%representative%"),
                    Politician.constituency.ilike(f"%{lga}%")
                ).first()
                
                if house_rep:
                    result["house_rep"] = {
                        "name": house_rep.name,
                        "party": house_rep.party,
                        "constituency": house_rep.constituency
                    }
                
                return result if result else None
            return None
        except Exception as e:
            logger.error(f"Rep lookup error: {e}")
            return None
    
    async def _search_politician(self, query: str) -> Optional[dict]:
        try:
            if not self.rag: return None
            context, sources = self.rag.retrieve(f"politician {query}", top_k=3)
            if not context: return None
            # Return simple structure for now, can enhance with LLM extraction
            return {"name": query.title(), "bio": context[:400]}
        except Exception as e:
            logger.error(f"Politician search error: {e}")
            return None
    
    async def _search_politician_record(self, name: str) -> Optional[str]:
        try:
            results = []
            if self.rag:
                context, _ = self.rag.retrieve(f"{name} achievements projects bills record", top_k=5)
                if context: results.append(context)
            if self.web_search:
                web = self.web_search.search_sync(f"{name} Nigeria achievements 2024")
                if web: results.append(web)
            
            if not results: return None
            return results[0][:600] # Simplified return
        except Exception as e:
            logger.error(f"Record search error: {e}")
            return None
    
    async def _search_news(self, query: str) -> Optional[dict]:
        try:
            if self.web_search:
                res = self.web_search.search_sync(query)
                if res: return {"summary": res[:400], "source": "Web Search"}
            if self.rag:
                ctx, _ = self.rag.retrieve(query, top_k=3)
                if ctx: return {"summary": ctx[:400], "source": "Internal DB"}
            return None
        except Exception as e:
            logger.error(f"News error: {e}")
            return None
    
    async def _search_rag(self, query: str) -> Optional[str]:
        try:
            if not self.rag: return None
            ctx, _ = self.rag.retrieve(query, top_k=5)
            # Integrate web search boost
            if self.web_search and any(w in query.lower() for w in ["latest", "current", "news"]):
                web = self.web_search.search_sync(query)
                if web: ctx = (ctx or "") + "\n\n" + web
            return ctx
        except: return None

    async def _reverse_geocode(self, lat: float, lng: float) -> dict:
        try:
            from app.services import location
            res = await location.process_location_for_report(lat, lng)
            if res.get("success"):
                cls = res.get("classification", {})
                return {
                    "formatted": res.get("address", {}).get("formatted"),
                    "state": res.get("address", {}).get("state"),
                    "lga": res.get("address", {}).get("lga"),
                    "authority": cls.get("authority")
                }
            return {"formatted": f"{lat}, {lng}"}
        except Exception as e:
            logger.error(f"Geocode error: {e}")
            return {"formatted": f"{lat}, {lng}"}

    async def _save_issue_report(self, user_hash: str, report_data: dict) -> bool:
        try:
            if not self.db: return False
            rpt_id = f"rpt_{uuid.uuid4().hex[:12]}"
            report = UserReport(
                report_id=rpt_id,
                user_hash=user_hash,
                description=report_data.get("description", ""),
                location=report_data.get("location_formatted") or report_data.get("location_text"),
                status="pending",
                domain="general"
            )
            # Try to extract state/lga from flow data (if we reverse geocoded)
            # Not explicitly in flow_data structure for text, but for location yes.
            # Could parse it.
            
            self.db.add(report)
            self.db.commit()
            logger.info(f"Saved user report {rpt_id} for {user_hash}")
            return True
        except Exception as e:
            logger.error(f"Save report error: {e}")
            return False


# ===========================================
# GLOBAL HANDLER
# ===========================================

_handler: Optional[IntegratedMessageHandler] = None

def get_handler() -> IntegratedMessageHandler:
    global _handler
    if _handler is None:
        from app.database import SessionLocal
        from app.services.enhanced_rag import EnhancedRAGService
        from app.services import web_search
        
        db = SessionLocal()
        rag = EnhancedRAGService(db)
        
        _handler = IntegratedMessageHandler(db_session=db, llm_service=None, rag_service=rag, web_search_service=web_search)
    return _handler

async def handle_whatsapp_message(incoming: dict) -> None:
    """Webhook entry point."""
    message = whatsapp.parse_incoming_message(incoming)
    if not message: return
    
    user_hash = message["from_hash"]
    phone = message["from"]
    msg_type = message.get("type", "text")
    
    whatsapp.mark_as_read(message["message_id"])
    
    handler = get_handler()
    try:
        if msg_type == "text":
            response = await handler.handle(user_hash, message["text"])
        elif msg_type == "location":
            location = message.get("location", {})
            response = await handler.handle(user_hash, "", msg_type="location", location=location)
        else:
            response = "I can process text and locations. Send a text message to continue."
            
        whatsapp.send_text_message(phone, response)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        whatsapp.send_text_message(phone, "Something went wrong. Try again.")
