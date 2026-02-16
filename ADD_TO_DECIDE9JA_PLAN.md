# Add to Decide9ja — Extraction Plan

**Goal:** Take the best parts from the new Tade bot and add them to your existing Decide9ja codebase without breaking anything.

**Approach:** Copy-paste ready modules that integrate with your FastAPI/Python architecture.

---

## 1. Nigerian Location Data (COPY AS-IS)

**What:** Complete 37 states + 774 LGAs + fuzzy matching
**File to create:** `app/data/nigeria_locations.py`
**Integration:** Replace your existing location lookup

**Code:**
```python
# app/data/nigeria_locations.py
nigerian_states = [
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue", "Borno",
    "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", "Gombe", "Imo",
    "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos",
    "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers",
    "Sokoto", "Taraba", "Yobe", "Zamfara", "FCT"
]

state_lga_map = {
    "Lagos": ["Agege", "Ajeromi-Ifelodun", "Alimosho", ...],  # 20 LGAs
    "Kano": ["Ajingi", "Albasu", "Bagwai", ...],  # 44 LGAs
    # ... all 774 LGAs mapped
}

location_aliases = {
    "abuja": "FCT",
    "ph": "Rivers",
    " Lagos state": "Lagos",
    # ... common aliases
}

pidgin_patterns = [
    r'i dey (\w+)',
    r'i dey stay (\w+)',
    r'na (\w+) i dey',
    r'i stay (\w+)',
]

def identify_location(message: str, current_state: str = None) -> dict:
    '''Fuzzy match location from user message'''
    # Implementation from TypeScript → Python
    # Returns: {state, lga, confidence, needs_clarification}
```

**Value:** Handles Pidgin ("I dey Lagos"), typos, abbreviations automatically.

---

## 2. Budget Red-Flag Detection (ADD TO EXISTING)

**What:** Automatic detection of suspicious budget patterns
**File to modify:** `app/services/budget_service.py` or create new
**Integration:** Add to your existing budget retrieval

**Code:**
```python
# app/services/budget_analyzer.py

def analyze_budget_red_flags(budget_data: dict) -> list:
    """
    Detect suspicious budget patterns.
    Returns list of red flags with explanations.
    """
    red_flags = []
    
    total = budget_data.get('total', 0)
    categories = budget_data.get('categories', {})
    
    # Check 1: Legislature vs Education
    legislature = categories.get('legislature', 0)
    education = categories.get('education', 0)
    
    if legislature > education * 0.5:  # Legislature > 50% of education
        red_flags.append({
            'type': 'high_legislature',
            'severity': 'high',
            'message': f'Legislature budget (₦{legislature:,.0f}) is {legislature/education*100:.0f}% of education budget',
            'amount': legislature - education * 0.5
        })
    
    # Check 2: Low health allocation
    health = categories.get('health', 0)
    health_pct = (health / total) * 100 if total > 0 else 0
    
    if health_pct < 5:
        red_flags.append({
            'type': 'low_health',
            'severity': 'medium',
            'message': f'Health allocation is only {health_pct:.1f}% of total budget (below 5% WHO recommendation)',
            'recommended': total * 0.15
        })
    
    # Check 3: Low education allocation
    edu_pct = (education / total) * 100 if total > 0 else 0
    if edu_pct < 10:
        red_flags.append({
            'type': 'low_education',
            'severity': 'medium',
            'message': f'Education allocation is only {edu_pct:.1f}% of total budget (below UNESCO 15-20% recommendation)',
            'recommended': total * 0.15
        })
    
    # Check 4: International travel vs primary healthcare
    travel = categories.get('intl_travel', 0)
    primary_health = categories.get('primary_health', 0)
    
    if travel > primary_health:
        red_flags.append({
            'type': 'travel_over_health',
            'severity': 'high',
            'message': f'International travel (₦{travel:,.0f}) exceeds primary healthcare (₦{primary_health:,.0f})',
            'amount': travel - primary_health
        })
    
    return red_flags


def format_budget_response(budget_data: dict, red_flags: list) -> str:
    """Format budget with red flags for WhatsApp"""
    total = budget_data.get('total', 0)
    categories = budget_data.get('categories', {})
    
    response = f"""💰 Budget Summary

Total: ₦{total:,.0f}

📊 Allocations:
"""
    
    for cat, amount in sorted(categories.items(), key=lambda x: -x[1]):
        pct = (amount / total) * 100 if total > 0 else 0
        response += f"• {cat.title()}: ₦{amount:,.0f} ({pct:.1f}%)\n"
    
    if red_flags:
        response += "\n🚩 Red Flags:\n"
        for flag in red_flags:
            emoji = "🔴" if flag['severity'] == 'high' else "🟡"
            response += f"{emoji} {flag['message']}\n"
    
    return response
```

**Value:** Automatically surfaces budget issues citizens should know about.

---

## 3. Working Memory Schema (INTEGRATE WITH STATE)

**What:** Structured conversation state with Zod validation
**File to modify:** `app/models/state.py`
**Integration:** Enhance your existing UserState

**Code:**
```python
# app/models/working_memory.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ConversationStage(str, Enum):
    GREETING = "greeting"
    LOCATION_COLLECTION = "location_collection"
    QUERY_UNDERSTANDING = "query_understanding"
    DATA_RETRIEVAL = "data_retrieval"
    RESPONSE_FORMULATION = "response_formulation"
    FOLLOW_UP = "follow_up"

class QueryType(str, Enum):
    REPRESENTATIVE = "representative"
    BUDGET = "budget"
    NEWS = "news"
    ARCHIVE = "archive"
    GENERAL = "general"

class Location(BaseModel):
    state: Optional[str] = None
    lga: Optional[str] = None
    ward: Optional[str] = None
    senatorial_district: Optional[str] = None
    federal_constituency: Optional[str] = None

class UserPreferences(BaseModel):
    language: str = "en"  # en, pcm, ha, yo, ig
    notification_enabled: bool = True
    topics_of_interest: List[str] = Field(default_factory=list)

class CurrentQuery(BaseModel):
    type: QueryType = QueryType.GENERAL
    query_text: str = ""
    tools_used: List[str] = Field(default_factory=list)
    data_retrieved: Optional[dict] = None

class WorkingMemory(BaseModel):
    """Structured working memory for conversation state"""
    user_phone: str
    
    # Progressive profiling
    location: Location = Field(default_factory=Location)
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    
    # Conversation flow
    conversation_stage: ConversationStage = ConversationStage.GREETING
    current_query: CurrentQuery = Field(default_factory=CurrentQuery)
    
    # Pending actions
    pending_clarification: bool = False
    clarification_question: Optional[str] = None
    expected_answer_type: Optional[str] = None
    
    # Session metadata
    interaction_count: int = 0
    first_interaction: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    
    def update_activity(self):
        self.last_activity = datetime.utcnow()
        self.interaction_count += 1
    
    def set_location(self, state: str = None, lga: str = None):
        if state:
            self.location.state = state
        if lga:
            self.location.lga = lga
        self.update_activity()
    
    def transition_stage(self, new_stage: ConversationStage):
        self.conversation_stage = new_stage
        self.update_activity()
```

**Integration with existing:**
```python
# In your message handler
from app.models.working_memory import WorkingMemory, ConversationStage

async def handle_message(phone: str, text: str):
    # Load or create working memory
    memory = await get_working_memory(phone)
    
    # Use stage to determine flow
    if memory.conversation_stage == ConversationStage.GREETING:
        # Handle greeting logic
        memory.transition_stage(ConversationStage.LOCATION_COLLECTION)
    
    # Save updated memory
    await save_working_memory(phone, memory)
```

**Value:** Explicit state machine instead of scattered flow logic.

---

## 4. Error Recovery Patterns (ADD TO HANDLER)

**What:** Better error messages with options instead of dead ends
**File to modify:** `app/services/message_handler_v4.py`
**Integration:** Replace generic "I don't understand" responses

**Code:**
```python
# app/services/error_recovery.py

class ErrorRecovery:
    """Better error handling with options"""
    
    @staticmethod
    def ambiguous_location(attempted: str, options: list) -> str:
        """When location parsing is unclear"""
        options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options[:5])])
        return f"""I want to make sure I help you correctly. Did you mean:

{options_text}

Reply with the number (1-{len(options[:5])}) or type your location again."""
    
    @staticmethod
    def unknown_representative(location: str) -> str:
        """When we can't find representatives"""
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

Reply with 1, 2, 3, or 4."""
    
    @staticmethod
    def context_compression_recovery(last_topic: str) -> str:
        """When context is lost due to compression"""
        return f"""Quick reminder — we were talking about {last_topic}. 

What would you like to know about it? Or type "menu" to start fresh."""


# Usage in handler
from app.services.error_recovery import ErrorRecovery

async def handle_message(phone: str, text: str):
    recovery = ErrorRecovery()
    
    try:
        location = identify_location(text)
        if not location:
            return recovery.ambiguous_location(text, suggest_locations(text))
    except Exception:
        return recovery.query_too_vague(text)
```

**Value:** Users never hit dead ends. Always have options.

---

## 5. Pidgin/Local Language Support (ENHANCE TEMPLATES)

**What:** Response templates in Pidgin, Hausa, Yoruba, Igbo
**File to create:** `app/services/templates_multilingual.py`
**Integration:** Add to your existing templates

**Code:**
```python
# app/services/templates_multilingual.py

TEMPLATES = {
    "en": {
        "welcome": "Hello! I'm Tade, your civic engagement companion. How can I help you today?",
        "location_prompt": "Which state are you in?",
        "rep_found": "Your representative is {name} ({party}).",
        "budget_summary": "Total budget: ₦{amount}",
        "red_flag": "⚠️ Note: {issue}",
        "error": "I didn't understand. Could you rephrase?"
    },
    "pcm": {  # Nigerian Pidgin
        "welcome": "How far! I be Tade, your civic companion. How I fit help you?",
        "location_prompt": "Which state you dey?",
        "rep_found": "Your rep na {name} ({party}).",
        "budget_summary": "Total budget: ₦{amount}",
        "red_flag": "⚠️ See dis: {issue}",
        "error": "I no understand. You fit talk am another way?"
    },
    "ha": {  # Hausa
        "welcome": "Sannu! Ni Tade ne, abokin ku na civic. Yaya zan taimake ku?",
        "location_prompt": "A wane jiha kuke?",
        "rep_found": "Jagoranku shine {name} ({party}).",
        "budget_summary": "Jimlar kasafin kudi: ₦{amount}",
        "red_flag": "⚠️ Lura da: {issue}",
        "error": "Ban fahimta ba. Za ku iya sake fadinsa?"
    },
    "yo": {  # Yoruba
        "welcome": "Ẹ kú àárọ̀! Mo jẹ́ Tade, olùbátan rẹ. Báwo ni mo ṣe lè ràn ọ́ lọ́wọ́?",
        "location_prompt": "Ní ìpínlẹ̀ wo ni o wà?",
        "rep_found": "Aṣojú rẹ ni {name} ({party}).",
        "budget_summary": "Ìṣọkan owó: ₦{amount}",
        "red_flag": "⚠️ Ẹ kíyèsí: {issue}",
        "error": "N kò yé mi. Ṣé o lè sọ ọ́ lọ́nà mìíràn?"
    },
    "ig": {  # Igbo
        "welcome": "Nnọọ! Aha m bụ Tade, enyi gị. Kedu ka m nwere ike inyere gị aka?",
        "location_prompt": "Kedu steeti i nọ?",
        "rep_found": "Onye nnọchiteanya gị bụ {name} ({party}).",
        "budget_summary": "Mmepe ego: ₦{amount}",
        "red_flag": "⚠️ Lẹzie ihe a: {issue}",
        "error": "Ahụghị ihe ị na-ekwu. Ị nwere ike ịkọwa ya nke ọma?"
    }
}

def get_template(key: str, language: str = "en", **kwargs) -> str:
    """Get template in user's preferred language"""
    lang_templates = TEMPLATES.get(language, TEMPLATES["en"])
    template = lang_templates.get(key, TEMPLATES["en"][key])
    return template.format(**kwargs)

# Auto-detect language
import re

def detect_language(text: str) -> str:
    """Detect if text is Pidgin, Hausa, Yoruba, Igbo, or English"""
    text_lower = text.lower()
    
    # Pidgin indicators
    pidgin_markers = ['dey', 'na', 'wahala', 'how far', 'i dey', 'abi', 'sha', 'omo']
    if any(marker in text_lower for marker in pidgin_markers):
        return "pcm"
    
    # Hausa indicators
    hausa_markers = ['sannu', 'na gode', 'yaya', 'lafiya', 'jiha']
    if any(marker in text_lower for marker in hausa_markers):
        return "ha"
    
    # Yoruba indicators
    yoruba_markers = ['ẹ kú', 'báwo', 'ṣé', 'jọwọ', 'ẹ ẹ', 'ọmọ']
    if any(marker in text_lower for marker in yoruba_markers):
        return "yo"
    
    # Igbo indicators
    igbo_markers = ['nnọọ', 'kedu', 'ị', 'gị', 'mbanu', 'chukwu']
    if any(marker in text_lower for marker in igbo_markers):
        return "ig"
    
    return "en"
```

**Value:** Responds in the language the user speaks.

---

## Implementation Priority

| Order | Module | Effort | Impact | Risk |
|-------|--------|--------|--------|------|
| 1 | Location data + fuzzy matching | 2 hrs | **HIGH** | Low |
| 2 | Error recovery patterns | 1 hr | **HIGH** | Low |
| 3 | Budget red-flag detection | 2 hrs | Medium | Low |
| 4 | Multilingual templates | 3 hrs | Medium | Low |
| 5 | Working memory schema | 4 hrs | **HIGH** | Medium |

---

## Integration Strategy

**Week 1:** Location + Error Recovery (3 hours, immediate UX improvement)
**Week 2:** Budget red-flags + Multilingual (5 hours, content improvement)
**Week 3:** Working memory refactor (4 hours, architecture improvement)

**Each module is independent.** You can do just #1, or #1+#2, or all five.

**Want me to start with #1 (Location data)?** I can generate the complete Python file with all 774 LGAs ready to drop into Decide9ja. 🦉

