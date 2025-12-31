# DECIDE9JA CONTEXT ARCHITECTURE
## Deep Dive on Each Component

Based on your context design diagram, here's how each component works for Decide9ja.

---

# COMPONENT 1: USER INPUT

## What It Receives

```python
@dataclass
class UserInput:
    # Raw from WhatsApp
    message_id: str
    phone_hash: str              # SHA256(phone_number) — never store raw
    timestamp: datetime
    
    # Content
    text: Optional[str]          # User's message text
    media_type: Optional[str]    # image, audio, video, document
    media_url: Optional[str]     # WhatsApp media URL
    location: Optional[dict]     # {lat, long} if shared
    
    # WhatsApp metadata
    message_type: str            # text, image, voice, location, button_reply
    button_payload: Optional[str] # If user clicked a button
    
    # Context
    is_reply_to: Optional[str]   # If replying to specific message
    forwarded: bool              # Is this a forwarded message?
```

## Input Examples

```
Type: text
Content: "Who is my senator?"

Type: text  
Content: "Wetin Tinubu dey do about fuel?"

Type: image
Content: [photo of damaged road]
Caption: "See this road for Alimosho"

Type: location
Content: {lat: 6.5244, long: 3.3792}

Type: button_reply
Content: "1"
Payload: "show_voting_record"

Type: voice
Content: [audio file URL]
Duration: 15 seconds
```

---

# COMPONENT 2: PROMPT HANDLER

## Responsibilities

1. **Parse** — Extract structured data from raw input
2. **Detect Language** — Identify English, Pidgin, Hausa, Yoruba, Igbo
3. **Classify Intent** — What does user want?
4. **Extract Entities** — Names, locations, dates mentioned
5. **Assess Complexity** — Simple fact vs complex research

## Implementation

```python
class PromptHandler:
    
    def process(self, user_input: UserInput) -> ProcessedPrompt:
        
        # 1. PARSE
        text = self.extract_text(user_input)
        
        # 2. DETECT LANGUAGE
        language = self.detect_language(text)
        # Returns: "en", "pcm" (Pidgin), "ha", "yo", "ig"
        
        # 3. CLASSIFY INTENT
        intent = self.classify_intent(text)
        # Returns: IntentClassification with:
        #   - primary_intent: "find_representative"
        #   - confidence: 0.92
        #   - sub_intent: "senator"
        
        # 4. EXTRACT ENTITIES
        entities = self.extract_entities(text)
        # Returns: {
        #   "politicians": ["Tinubu", "Obi"],
        #   "locations": ["Lagos", "Alimosho"],
        #   "parties": ["APC"],
        #   "topics": ["fuel", "subsidy"],
        #   "dates": ["2023"]
        # }
        
        # 5. ASSESS COMPLEXITY
        complexity = self.assess_complexity(text, intent)
        # Returns: "simple" | "moderate" | "complex"
        # Simple: "Who is my governor?" 
        # Moderate: "Compare Tinubu and Obi on education"
        # Complex: "Analyze voting patterns in South-West"
        
        # 6. BUILD SEARCH QUERY
        search_query = self.build_search_query(text, entities, intent)
        
        return ProcessedPrompt(
            original_text=text,
            language=language,
            intent=intent,
            entities=entities,
            complexity=complexity,
            search_query=search_query,
            requires_tools=self.check_tool_requirements(intent),
            input_type=user_input.message_type
        )
```

## Language Detection

```python
LANGUAGE_PATTERNS = {
    "pcm": [  # Pidgin
        r"\bwetin\b", r"\bdey\b", r"\bno be\b", r"\bwahala\b",
        r"\boya\b", r"\babeg\b", r"\bshey\b", r"\bna\b",
        r"\be don\b", r"\bmake\b.*\bjust\b"
    ],
    "ha": [  # Hausa
        r"\bina\b", r"\bko\b", r"\bwane\b", r"\byaya\b",
        r"\bdan\b", r"\ballah\b", r"\bkai\b"
    ],
    "yo": [  # Yoruba
        r"\bṣe\b", r"\bkini\b", r"\bọjọ\b", r"\bawa\b",
        r"\beyin\b", r"\bwọn\b"
    ],
    "ig": [  # Igbo
        r"\bkedu\b", r"\bonye\b", r"\bgini\b", r"\bọ bụ\b",
        r"\bndi\b", r"\banyị\b"
    ]
}

def detect_language(text: str) -> str:
    text_lower = text.lower()
    
    for lang, patterns in LANGUAGE_PATTERNS.items():
        matches = sum(1 for p in patterns if re.search(p, text_lower))
        if matches >= 2:
            return lang
    
    return "en"  # Default to English
```

## Intent Classification

```python
INTENT_PATTERNS = {
    # Electoral
    "voter_registration": [
        r"register.*vote", r"get.*pvc", r"voter.*card", r"inec.*registration"
    ],
    "find_polling_unit": [
        r"polling.*unit", r"where.*vote", r"voting.*center"
    ],
    "election_results": [
        r"who.*won", r"election.*result", r"how.*many.*vote"
    ],
    
    # Representatives
    "find_representative": [
        r"who.*is.*my.*(senator|governor|rep|chairman)",
        r"my.*(senator|governor|rep|representative)",
        r"who.*represent"
    ],
    "representative_profile": [
        r"tell.*me.*about", r"who.*is\s+[A-Z]", r"profile.*of"
    ],
    "representative_record": [
        r"what.*has.*done", r"achievement", r"track.*record", r"promise"
    ],
    
    # Reporting
    "report_issue": [
        r"report", r"complain", r"bad.*road", r"no.*light", r"problem.*in"
    ],
    
    # Information
    "policy_explanation": [
        r"what.*is.*(policy|program|scheme)", r"explain.*subsidy",
        r"how.*does.*work"
    ],
    "fact_check": [
        r"is.*it.*true", r"did.*really", r"verify", r"fact.*check"
    ],
    "compare_candidates": [
        r"compare", r"difference.*between", r"vs\.?", r"versus"
    ]
}

def classify_intent(text: str) -> IntentClassification:
    text_lower = text.lower()
    
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return IntentClassification(
                    primary_intent=intent,
                    confidence=0.85,
                    matched_pattern=pattern
                )
    
    # Fallback: Use embedding similarity or LLM classification
    return classify_with_llm(text)
```

## Entity Extraction

```python
# Pre-built lists for Nigerian political entities
POLITICIAN_NAMES = load_json("data/entities/politician_names.json")
# ["Tinubu", "Bola Tinubu", "BAT", "Jagaban", "Obi", "Peter Obi", ...]

PARTY_NAMES = {
    "APC": ["APC", "All Progressives Congress", "progressives"],
    "PDP": ["PDP", "Peoples Democratic Party", "peoples democratic"],
    "LP": ["LP", "Labour Party", "labour", "obidient"],
    "NNPP": ["NNPP", "New Nigeria Peoples Party", "kwankwasiyya"],
    # ...
}

STATE_NAMES = load_json("data/entities/states.json")
LGA_NAMES = load_json("data/entities/lgas.json")

def extract_entities(text: str) -> dict:
    entities = {
        "politicians": [],
        "parties": [],
        "states": [],
        "lgas": [],
        "topics": [],
        "dates": []
    }
    
    # Extract politicians (fuzzy match)
    for name in POLITICIAN_NAMES:
        if name.lower() in text.lower():
            entities["politicians"].append(normalize_politician_name(name))
    
    # Extract parties
    for party, aliases in PARTY_NAMES.items():
        if any(alias.lower() in text.lower() for alias in aliases):
            entities["parties"].append(party)
    
    # Extract locations
    for state in STATE_NAMES:
        if state.lower() in text.lower():
            entities["states"].append(state)
    
    # Extract topics (from predefined list)
    TOPICS = ["fuel", "subsidy", "education", "security", "health", 
              "road", "economy", "budget", "corruption", "election"]
    for topic in TOPICS:
        if topic in text.lower():
            entities["topics"].append(topic)
    
    # Extract dates/years
    years = re.findall(r"20[0-2][0-9]", text)
    entities["dates"] = years
    
    return entities
```

---

# COMPONENT 3: CONTEXT ASSEMBLER

## The Heart of the System

The Context Assembler takes inputs from multiple sources and builds the final context that goes to the LLM. This is where intelligence happens.

## Responsibilities

1. **Gather** — Collect all context sources
2. **Prioritize** — Rank by relevance
3. **Weight** — Decide how much of each to include
4. **Truncate** — Fit within token limits
5. **Format** — Structure for LLM consumption

## Token Budget Management

```python
class ContextAssembler:
    
    # Token budget (for Claude with ~100K context, but we stay lean)
    TOTAL_BUDGET = 8000  # tokens
    
    BUDGET_ALLOCATION = {
        "system_prompt": 2000,        # Fixed - core identity
        "user_profile": 300,          # Who is this user
        "conversation_memory": 1000,  # Recent turns
        "retrieved_knowledge": 3500,  # RAG results (largest)
        "tool_outputs": 1000,         # API responses
        "buffer": 200                 # Safety margin
    }
    
    def assemble(
        self,
        processed_prompt: ProcessedPrompt,
        user_profile: UserProfile,
        conversation_memory: List[Turn],
        retrieved_docs: List[Document],
        tool_outputs: List[ToolOutput]
    ) -> AssembledContext:
        
        context_parts = {}
        
        # 1. SYSTEM PROMPT (fixed)
        context_parts["system_prompt"] = self.get_system_prompt()
        
        # 2. USER PROFILE (personalization)
        context_parts["user_profile"] = self.format_user_profile(
            user_profile,
            max_tokens=self.BUDGET_ALLOCATION["user_profile"]
        )
        
        # 3. CONVERSATION MEMORY (recent context)
        context_parts["conversation_memory"] = self.format_memory(
            conversation_memory,
            max_tokens=self.BUDGET_ALLOCATION["conversation_memory"]
        )
        
        # 4. RETRIEVED KNOWLEDGE (RAG - most important)
        context_parts["retrieved_knowledge"] = self.format_retrieved(
            retrieved_docs,
            processed_prompt,
            max_tokens=self.BUDGET_ALLOCATION["retrieved_knowledge"]
        )
        
        # 5. TOOL OUTPUTS (if any tools were called)
        if tool_outputs:
            context_parts["tool_outputs"] = self.format_tool_outputs(
                tool_outputs,
                max_tokens=self.BUDGET_ALLOCATION["tool_outputs"]
            )
        
        return AssembledContext(
            system=context_parts["system_prompt"],
            context=self.merge_context_parts(context_parts),
            user_message=processed_prompt.original_text
        )
```

## Priority Ranking for Retrieved Knowledge

```python
def format_retrieved(
    self,
    documents: List[Document],
    prompt: ProcessedPrompt,
    max_tokens: int
) -> str:
    """
    Rank and select documents based on relevance to query.
    """
    
    # Score each document
    scored_docs = []
    for doc in documents:
        score = self.calculate_relevance_score(doc, prompt)
        scored_docs.append((score, doc))
    
    # Sort by score descending
    scored_docs.sort(key=lambda x: x[0], reverse=True)
    
    # Select documents within token budget
    selected = []
    tokens_used = 0
    
    for score, doc in scored_docs:
        doc_tokens = self.count_tokens(doc.content)
        if tokens_used + doc_tokens <= max_tokens:
            selected.append(doc)
            tokens_used += doc_tokens
        else:
            # Try to include truncated version
            remaining = max_tokens - tokens_used
            if remaining > 200:  # Worth including partial
                truncated = self.truncate_document(doc, remaining)
                selected.append(truncated)
            break
    
    # Format for LLM
    return self.format_documents(selected)


def calculate_relevance_score(self, doc: Document, prompt: ProcessedPrompt) -> float:
    """
    Score document relevance based on multiple factors.
    """
    score = 0.0
    
    # 1. Semantic similarity (from vector search)
    score += doc.similarity_score * 0.4
    
    # 2. Entity overlap
    doc_entities = doc.metadata.get("entities", {})
    query_entities = prompt.entities
    
    # Politician name match (high value)
    if any(p in doc_entities.get("politicians", []) 
           for p in query_entities.get("politicians", [])):
        score += 0.25
    
    # Location match
    if any(l in doc_entities.get("locations", [])
           for l in query_entities.get("states", []) + query_entities.get("lgas", [])):
        score += 0.15
    
    # Topic match
    if any(t in doc_entities.get("topics", [])
           for t in query_entities.get("topics", [])):
        score += 0.1
    
    # 3. Recency bonus (for news, polling data)
    if doc.doc_type in ["news", "polls", "election_results"]:
        days_old = (datetime.now() - doc.updated_at).days
        recency_score = max(0, 1 - (days_old / 365))  # Decay over 1 year
        score += recency_score * 0.1
    
    # 4. Source quality
    source_weights = {
        "inec_official": 1.0,
        "politician_profile": 0.9,
        "stears": 0.9,
        "premium_times": 0.8,
        "afrobarometer": 0.8,
        "noi_polls": 0.7,
        "nairaland": 0.5
    }
    source_weight = source_weights.get(doc.source, 0.6)
    score *= source_weight
    
    return score
```

## Context Merging

```python
def merge_context_parts(self, parts: dict) -> str:
    """
    Merge all context parts into single context string.
    Order matters — most important first.
    """
    
    sections = []
    
    # User profile first (personalization)
    if parts.get("user_profile"):
        sections.append(f"""=== USER CONTEXT ===
{parts["user_profile"]}""")
    
    # Retrieved knowledge (facts to use)
    if parts.get("retrieved_knowledge"):
        sections.append(f"""=== RELEVANT INFORMATION ===
{parts["retrieved_knowledge"]}""")
    
    # Tool outputs (if any)
    if parts.get("tool_outputs"):
        sections.append(f"""=== TOOL RESULTS ===
{parts["tool_outputs"]}""")
    
    # Conversation memory last (less critical)
    if parts.get("conversation_memory"):
        sections.append(f"""=== RECENT CONVERSATION ===
{parts["conversation_memory"]}""")
    
    return "\n\n".join(sections)
```

---

# COMPONENT 4: TOOL/API OUTPUTS

## Available Tools

```python
AVAILABLE_TOOLS = {
    "location_lookup": {
        "description": "Derive senatorial district, federal constituency from state + LGA",
        "input": {"state": str, "lga": str},
        "output": {"senatorial_district": str, "federal_constituency": str, ...}
    },
    
    "representative_lookup": {
        "description": "Get current representatives for a location",
        "input": {"state": str, "lga": str},
        "output": {"governor": str, "senator": str, "house_rep": str, ...}
    },
    
    "election_results": {
        "description": "Get official election results",
        "input": {"election_type": str, "year": int, "location": str},
        "output": {"results": List[dict], "winner": str, ...}
    },
    
    "fact_check": {
        "description": "Check claim against fact-check databases",
        "input": {"claim": str},
        "output": {"verdict": str, "source": str, "explanation": str}
    },
    
    "media_analysis": {
        "description": "Analyze uploaded image (e.g., damaged road)",
        "input": {"media_url": str, "media_type": str},
        "output": {"description": str, "issue_type": str, "severity": str}
    },
    
    "polling_unit_lookup": {
        "description": "Find polling unit from location",
        "input": {"state": str, "lga": str, "ward": str},
        "output": {"polling_units": List[dict]}
    }
}
```

## Tool Execution

```python
class ToolExecutor:
    
    def execute(self, tool_name: str, inputs: dict) -> ToolOutput:
        
        if tool_name == "location_lookup":
            return self.location_lookup(inputs["state"], inputs["lga"])
        
        elif tool_name == "representative_lookup":
            return self.representative_lookup(inputs["state"], inputs["lga"])
        
        elif tool_name == "election_results":
            return self.election_results(
                inputs["election_type"],
                inputs["year"],
                inputs.get("location")
            )
        
        # ... etc
    
    def location_lookup(self, state: str, lga: str) -> ToolOutput:
        """
        Derive all political divisions from state + LGA.
        """
        # Load mapping data
        mappings = load_json("data/mappings/lga_to_districts.json")
        
        key = f"{state.lower()}_{lga.lower()}"
        data = mappings.get(key, {})
        
        return ToolOutput(
            tool="location_lookup",
            success=bool(data),
            data={
                "state": state,
                "lga": lga,
                "zone": data.get("zone"),
                "senatorial_district": data.get("senatorial_district"),
                "federal_constituency": data.get("federal_constituency"),
                "state_constituency": data.get("state_constituency")
            }
        )
    
    def representative_lookup(self, state: str, lga: str) -> ToolOutput:
        """
        Get all current representatives for a location.
        """
        # Get location info first
        location = self.location_lookup(state, lga)
        
        # Query database for each representative
        db = get_database()
        
        representatives = {
            "president": "Bola Tinubu (APC)",  # Fixed
            "governor": db.get_governor(state),
            "deputy_governor": db.get_deputy_governor(state),
            "senator": db.get_senator(location.data["senatorial_district"]),
            "house_rep": db.get_rep(location.data["federal_constituency"]),
            "state_rep": db.get_state_rep(location.data["state_constituency"]),
            "lga_chairman": db.get_chairman(state, lga)
        }
        
        return ToolOutput(
            tool="representative_lookup",
            success=True,
            data=representatives
        )
```

---

# COMPONENT 5: SYSTEM PROMPT

Already covered in `SYSTEM_PROMPT.md`. Key points:

- **Fixed** — Same for all users (identity, rules, format)
- **Token budget** — ~2000 tokens
- **Injection points** — {{USER_CONTEXT}}, {{RETRIEVED_CONTEXT}}, {{CURRENT_DATE}}

---

# COMPONENT 6: RETRIEVED KNOWLEDGE (RAG)

## Document Types in Database

```python
DOCUMENT_TYPES = {
    "politician_profile": {
        "description": "Biographical info about politicians",
        "fields": ["name", "party", "position", "state", "bio", "achievements", "controversies"],
        "example_source": "data/candidates/governors/lagos.json"
    },
    
    "election_result": {
        "description": "Official election results",
        "fields": ["election_type", "year", "location", "results", "winner", "turnout"],
        "example_source": "data/elections/stears/presidential_2023.json"
    },
    
    "policy": {
        "description": "Government policies and programs",
        "fields": ["name", "description", "who_benefits", "status", "date"],
        "example_source": "data/policies/federal/*.json"
    },
    
    "campaign_promise": {
        "description": "Promises made during campaigns",
        "fields": ["politician", "promise", "date_made", "status", "evidence"],
        "example_source": "data/promises/*.json"
    },
    
    "bill": {
        "description": "Legislative bills",
        "fields": ["title", "sponsor", "status", "summary", "voting_record"],
        "example_source": "data/bills/*.json"
    },
    
    "poll_result": {
        "description": "Opinion polls and surveys",
        "fields": ["topic", "date", "findings", "sample_size", "source"],
        "example_source": "data/polls/noi_polls/*.json"
    },
    
    "fact_check": {
        "description": "Verified fact checks",
        "fields": ["claim", "verdict", "explanation", "source", "date"],
        "example_source": "data/fact_checks/*.json"
    },
    
    "news_article": {
        "description": "News coverage",
        "fields": ["headline", "source", "date", "summary", "politicians_mentioned"],
        "example_source": "data/news/*.json"
    }
}
```

## RAG Pipeline

```python
class RAGPipeline:
    
    def __init__(self):
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self.vector_store = load_vector_store("data/vectors/")
        self.bm25_index = load_bm25_index("data/bm25/")
    
    def retrieve(self, query: str, filters: dict = None, top_k: int = 10) -> List[Document]:
        """
        Hybrid retrieval: combine vector similarity + keyword (BM25).
        """
        
        # 1. Vector search
        query_embedding = self.embedder.encode(query)
        vector_results = self.vector_store.search(
            query_embedding,
            top_k=top_k * 2,
            filters=filters
        )
        
        # 2. BM25 keyword search
        bm25_results = self.bm25_index.search(
            query,
            top_k=top_k * 2,
            filters=filters
        )
        
        # 3. Reciprocal Rank Fusion (combine results)
        combined = self.reciprocal_rank_fusion(vector_results, bm25_results)
        
        # 4. Return top_k
        return combined[:top_k]
    
    def reciprocal_rank_fusion(
        self,
        vector_results: List[Document],
        bm25_results: List[Document],
        k: int = 60
    ) -> List[Document]:
        """
        Combine rankings using RRF algorithm.
        """
        scores = {}
        
        for rank, doc in enumerate(vector_results):
            doc_id = doc.id
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        
        for rank, doc in enumerate(bm25_results):
            doc_id = doc.id
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        
        # Sort by combined score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        # Get documents
        all_docs = {d.id: d for d in vector_results + bm25_results}
        return [all_docs[doc_id] for doc_id in sorted_ids if doc_id in all_docs]
```

---

# COMPONENT 7: CONVERSATION MEMORY

## What to Remember

```python
@dataclass
class ConversationMemory:
    user_id: str
    
    # Recent turns (last 5-10)
    turns: List[Turn]
    
    # Current conversation state
    active_topic: Optional[str]         # "representative_info", "issue_reporting"
    active_entities: List[str]          # Politicians/locations being discussed
    pending_action: Optional[str]       # "awaiting_lga", "awaiting_photo"
    
    # Session metadata
    session_start: datetime
    turn_count: int
    
@dataclass
class Turn:
    role: str                           # "user" or "assistant"
    content: str
    timestamp: datetime
    intent: Optional[str]               # Classified intent
    entities: Optional[dict]            # Extracted entities
```

## Memory Formatting

```python
def format_memory(self, memory: ConversationMemory, max_tokens: int) -> str:
    """
    Format conversation memory for context injection.
    """
    
    parts = []
    
    # Current state
    if memory.active_topic:
        parts.append(f"Current topic: {memory.active_topic}")
    
    if memory.pending_action:
        parts.append(f"Waiting for: {memory.pending_action}")
    
    if memory.active_entities:
        parts.append(f"Discussing: {', '.join(memory.active_entities)}")
    
    # Recent turns (newest first, but reverse for chronological reading)
    turns_text = []
    for turn in reversed(memory.turns[-5:]):  # Last 5 turns
        role = "User" if turn.role == "user" else "Decide9ja"
        turns_text.append(f"{role}: {turn.content[:200]}")  # Truncate long messages
    
    if turns_text:
        parts.append("Recent conversation:\n" + "\n".join(turns_text))
    
    return "\n\n".join(parts)
```

---

# COMPONENT 8: USER PROFILE

## Already covered in USER_PROFILING_FRAMEWORK.md

Key data:
- Location stack (state, LGA, senatorial district, etc.)
- Representatives (derived from location)
- Voter status
- Language preference
- Issues mentioned
- Engagement level

---

# COMPONENT 9: LLM

## API Call Structure

```python
class LLMService:
    
    def __init__(self, provider: str = "anthropic"):
        if provider == "anthropic":
            self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            self.model = "claude-sonnet-4-20250514"
        elif provider == "openai":
            self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.model = "gpt-4-turbo"
    
    def generate(self, context: AssembledContext) -> LLMResponse:
        """
        Generate response from assembled context.
        """
        
        if self.provider == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=context.system,
                messages=[
                    {"role": "user", "content": f"{context.context}\n\n---\n\nUser message: {context.user_message}"}
                ]
            )
            return LLMResponse(
                content=response.content[0].text,
                model=self.model,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                stop_reason=response.stop_reason
            )
        
        # ... OpenAI implementation
```

---

# COMPONENT 10: MODEL OUTPUT

## Output Structure

```python
@dataclass
class LLMResponse:
    content: str                        # Raw LLM output
    model: str                          # Model used
    tokens_used: int                    # Total tokens
    stop_reason: str                    # "end_turn", "max_tokens", etc.
    
@dataclass
class ModelOutput:
    raw_response: LLMResponse
    
    # Parsed from response
    main_content: str                   # The actual answer
    follow_up_offered: Optional[str]    # Any follow-up question asked
    entities_mentioned: List[str]       # Entities in response
    action_suggested: Optional[str]     # "contact_rep", "submit_report", etc.
    
    # Metadata
    processing_time: float              # Seconds
    confidence: float                   # Model's confidence if expressed
```

---

# COMPONENT 11: RESPONSE FORMATTER

## WhatsApp-Specific Formatting

```python
class ResponseFormatter:
    
    # WhatsApp limits
    MAX_MESSAGE_LENGTH = 4096
    MAX_BUTTONS = 3
    
    def format(self, model_output: ModelOutput, platform: str = "whatsapp") -> FormattedResponse:
        
        if platform == "whatsapp":
            return self.format_whatsapp(model_output)
        elif platform == "web":
            return self.format_web(model_output)
    
    def format_whatsapp(self, output: ModelOutput) -> FormattedResponse:
        """
        Format for WhatsApp:
        - Truncate to 4096 chars
        - Convert markdown to WhatsApp format
        - Add interactive buttons if appropriate
        """
        
        content = output.main_content
        
        # 1. Convert markdown
        content = self.markdown_to_whatsapp(content)
        
        # 2. Truncate if needed
        if len(content) > self.MAX_MESSAGE_LENGTH:
            content = self.smart_truncate(content, self.MAX_MESSAGE_LENGTH)
            content += "\n\n_(Message truncated. Ask for more details.)_"
        
        # 3. Determine if buttons are appropriate
        buttons = None
        if output.follow_up_offered:
            buttons = self.generate_buttons(output)
        
        return FormattedResponse(
            text=content,
            buttons=buttons,
            media=None
        )
    
    def markdown_to_whatsapp(self, text: str) -> str:
        """
        Convert markdown to WhatsApp formatting:
        - **bold** → *bold*
        - _italic_ stays same
        - Headers → *Header*
        - Bullet points → •
        """
        
        # Bold: **text** → *text*
        text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
        
        # Headers: ## Header → *Header*
        text = re.sub(r'^#+\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)
        
        # Bullet points: - item → • item
        text = re.sub(r'^[-*]\s+', '• ', text, flags=re.MULTILINE)
        
        # Tables: Convert to simple format
        # (WhatsApp doesn't support tables well)
        text = self.convert_tables(text)
        
        return text
    
    def generate_buttons(self, output: ModelOutput) -> List[dict]:
        """
        Generate WhatsApp interactive buttons.
        """
        buttons = []
        
        # Common follow-ups based on content
        if "voting record" in output.main_content.lower():
            buttons.append({
                "id": "show_voting_record",
                "title": "📋 Voting Record"
            })
        
        if "contact" in output.follow_up_offered.lower():
            buttons.append({
                "id": "show_contact_info",
                "title": "📞 Contact Info"
            })
        
        if "more details" in output.follow_up_offered.lower():
            buttons.append({
                "id": "show_more_details",
                "title": "🔍 More Details"
            })
        
        return buttons[:self.MAX_BUTTONS]
```

---

# COMPONENT 12: EVALUATION LAYER

## Real-Time Evaluation

```python
class EvaluationLayer:
    
    def evaluate(self, 
                 user_input: ProcessedPrompt,
                 model_output: ModelOutput,
                 context: AssembledContext) -> Evaluation:
        """
        Evaluate response quality in real-time.
        """
        
        scores = {}
        flags = []
        
        # 1. ACCURACY CHECK
        scores["accuracy"] = self.check_accuracy(model_output, context)
        
        # 2. NEUTRALITY CHECK
        neutrality = self.check_neutrality(model_output)
        scores["neutrality"] = neutrality.score
        if neutrality.violations:
            flags.append(f"NEUTRALITY_VIOLATION: {neutrality.violations}")
        
        # 3. RELEVANCE CHECK
        scores["relevance"] = self.check_relevance(user_input, model_output)
        
        # 4. TONE CHECK
        scores["tone"] = self.check_tone(user_input, model_output)
        
        # 5. SAFETY CHECK
        safety = self.check_safety(model_output)
        scores["safety"] = safety.score
        if safety.issues:
            flags.append(f"SAFETY_ISSUE: {safety.issues}")
        
        # Overall score
        weights = {
            "accuracy": 0.3,
            "neutrality": 0.25,
            "relevance": 0.25,
            "tone": 0.1,
            "safety": 0.1
        }
        overall = sum(scores[k] * weights[k] for k in weights)
        
        return Evaluation(
            scores=scores,
            overall=overall,
            flags=flags,
            passed=overall >= 0.7 and not any("SAFETY" in f for f in flags)
        )
    
    def check_neutrality(self, output: ModelOutput) -> NeutralityCheck:
        """
        Check for partisan language.
        """
        content = output.main_content.lower()
        
        violations = []
        
        # Check for comparative judgments
        partisan_patterns = [
            r"\b(apc|pdp|lp|nnpp)\s+is\s+(better|worse|best|worst)",
            r"you\s+should\s+vote\s+for",
            r"(tinubu|obi|atiku)\s+is\s+(better|worse|the best)",
            r"don'?t\s+vote\s+for",
        ]
        
        for pattern in partisan_patterns:
            if re.search(pattern, content):
                violations.append(pattern)
        
        score = 1.0 if not violations else 0.3
        
        return NeutralityCheck(score=score, violations=violations)
    
    def check_accuracy(self, output: ModelOutput, context: AssembledContext) -> float:
        """
        Check if response facts are supported by context.
        """
        # Extract factual claims from response
        claims = self.extract_claims(output.main_content)
        
        # Check each claim against context
        supported = 0
        for claim in claims:
            if self.claim_supported(claim, context.context):
                supported += 1
        
        if not claims:
            return 1.0  # No factual claims to verify
        
        return supported / len(claims)
```

## Logging for Review Loop

```python
class EvaluationLogger:
    
    def log(self, 
            user_input: str,
            model_output: str,
            evaluation: Evaluation,
            user_id: str):
        """
        Log for human review.
        """
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id_hash": hashlib.sha256(user_id.encode()).hexdigest()[:16],
            "user_input": user_input[:500],
            "model_output": model_output[:1000],
            "evaluation": {
                "overall": evaluation.overall,
                "scores": evaluation.scores,
                "flags": evaluation.flags,
                "passed": evaluation.passed
            }
        }
        
        # Flag for human review if:
        # - Overall score < 0.7
        # - Any safety/neutrality flags
        # - User expressed frustration
        
        if not evaluation.passed or evaluation.flags:
            log_entry["requires_review"] = True
            self.send_to_review_queue(log_entry)
        
        # Always log for analytics
        self.write_log(log_entry)
```

---

# COMPONENT 13: PROFILE UPDATER

## Learn from Every Conversation

```python
class ProfileUpdater:
    
    def update(self,
               user_profile: UserProfile,
               processed_prompt: ProcessedPrompt,
               model_output: ModelOutput):
        """
        Update user profile based on conversation.
        """
        
        # 1. Extract new information from user's message
        new_info = self.extract_profile_updates(processed_prompt)
        
        # 2. Update location if mentioned
        if new_info.get("state") and not user_profile.location.state:
            user_profile.location.state = new_info["state"]
        
        if new_info.get("lga") and not user_profile.location.lga:
            user_profile.location.lga = new_info["lga"]
            # Derive senatorial district
            user_profile.location.senatorial_district = self.derive_senatorial(
                new_info["state"], new_info["lga"]
            )
        
        # 3. Update interests
        for topic in processed_prompt.entities.get("topics", []):
            if topic not in user_profile.political.issues_care_about:
                user_profile.political.issues_care_about.append(topic)
        
        # 4. Track politicians asked about
        for politician in processed_prompt.entities.get("politicians", []):
            if politician not in user_profile.political.candidates_queried:
                user_profile.political.candidates_queried.append(politician)
        
        # 5. Update language preference
        if processed_prompt.language != "en":
            user_profile.engagement.preferred_language = processed_prompt.language
        
        # 6. Update engagement stats
        user_profile.engagement.total_messages += 1
        user_profile.engagement.last_active = datetime.utcnow()
        
        # 7. Infer occupation if signals present
        occupation_signal = self.detect_occupation_signal(processed_prompt)
        if occupation_signal and not user_profile.livelihood.occupation:
            user_profile.livelihood.occupation = occupation_signal
            user_profile.livelihood.occupation_confidence = 0.6
        
        # 8. Save updated profile
        self.save_profile(user_profile)
```

---

# COMPONENT 14: CONTEXT REVIEW LOOP

## Continuous Improvement

```python
class ContextReviewLoop:
    """
    Feedback loop for continuous improvement.
    Runs asynchronously, not in real-time.
    """
    
    def process_review_queue(self):
        """
        Process flagged conversations for improvement.
        """
        
        flagged = self.get_flagged_conversations()
        
        for conversation in flagged:
            analysis = self.analyze_failure(conversation)
            
            if analysis.issue_type == "missing_data":
                # Flag for data collection
                self.add_to_data_backlog({
                    "topic": analysis.topic,
                    "entity": analysis.entity,
                    "priority": analysis.priority
                })
            
            elif analysis.issue_type == "poor_retrieval":
                # Improve search/embeddings
                self.log_retrieval_issue({
                    "query": analysis.query,
                    "expected_docs": analysis.expected_docs,
                    "actual_docs": analysis.actual_docs
                })
            
            elif analysis.issue_type == "prompt_issue":
                # Flag for prompt engineering review
                self.log_prompt_issue({
                    "user_input": analysis.user_input,
                    "expected_behavior": analysis.expected,
                    "actual_behavior": analysis.actual
                })
            
            elif analysis.issue_type == "neutrality_violation":
                # Critical — review immediately
                self.alert_team({
                    "type": "NEUTRALITY",
                    "conversation": conversation,
                    "analysis": analysis
                })
    
    def generate_improvement_report(self) -> dict:
        """
        Weekly report on system performance and needed improvements.
        """
        
        return {
            "period": "last_7_days",
            "total_conversations": self.count_conversations(),
            "flagged_count": self.count_flagged(),
            "flag_breakdown": {
                "accuracy": self.count_by_flag("accuracy"),
                "neutrality": self.count_by_flag("neutrality"),
                "relevance": self.count_by_flag("relevance"),
                "missing_data": self.count_by_flag("missing_data")
            },
            "top_unanswered_queries": self.get_top_unanswered(),
            "top_missing_entities": self.get_missing_entities(),
            "recommended_actions": self.generate_recommendations()
        }
```

---

# FULL PIPELINE: PUTTING IT ALL TOGETHER

```python
class Decide9jaPipeline:
    """
    Complete pipeline from user input to response.
    """
    
    def __init__(self):
        self.prompt_handler = PromptHandler()
        self.context_assembler = ContextAssembler()
        self.tool_executor = ToolExecutor()
        self.rag_pipeline = RAGPipeline()
        self.llm_service = LLMService()
        self.response_formatter = ResponseFormatter()
        self.evaluation_layer = EvaluationLayer()
        self.profile_updater = ProfileUpdater()
    
    async def process(self, user_input: UserInput) -> FormattedResponse:
        """
        Process a single user message.
        """
        
        # 1. Get or create user profile
        user_profile = await self.get_user_profile(user_input.phone_hash)
        
        # 2. Get conversation memory
        conversation_memory = await self.get_conversation_memory(user_input.phone_hash)
        
        # 3. Process the prompt
        processed_prompt = self.prompt_handler.process(user_input)
        
        # 4. Execute any required tools
        tool_outputs = []
        if processed_prompt.requires_tools:
            for tool in processed_prompt.requires_tools:
                result = await self.tool_executor.execute(tool, processed_prompt.entities)
                tool_outputs.append(result)
        
        # 5. Retrieve relevant knowledge
        retrieved_docs = self.rag_pipeline.retrieve(
            query=processed_prompt.search_query,
            filters={"location": user_profile.location.state}  # Location-aware retrieval
        )
        
        # 6. Assemble context
        assembled_context = self.context_assembler.assemble(
            processed_prompt=processed_prompt,
            user_profile=user_profile,
            conversation_memory=conversation_memory,
            retrieved_docs=retrieved_docs,
            tool_outputs=tool_outputs
        )
        
        # 7. Generate LLM response
        llm_response = await self.llm_service.generate(assembled_context)
        
        # 8. Parse model output
        model_output = self.parse_output(llm_response)
        
        # 9. Evaluate response
        evaluation = self.evaluation_layer.evaluate(
            user_input=processed_prompt,
            model_output=model_output,
            context=assembled_context
        )
        
        # 10. Log if flagged
        if not evaluation.passed:
            self.log_for_review(user_input, model_output, evaluation)
        
        # 11. Update user profile
        self.profile_updater.update(user_profile, processed_prompt, model_output)
        
        # 12. Update conversation memory
        await self.update_conversation_memory(
            user_input.phone_hash,
            processed_prompt,
            model_output
        )
        
        # 13. Format for WhatsApp
        formatted_response = self.response_formatter.format(
            model_output,
            platform="whatsapp"
        )
        
        return formatted_response
```

---

# SUMMARY: YOUR ARCHITECTURE + DECIDE9JA

| Your Component | Decide9ja Implementation |
|----------------|--------------------------|
| User Input | WhatsApp message (text, image, location, voice) |
| Prompt Handler | Language detection, intent classification, entity extraction |
| Context Assembler | Priority-weighted merger with token budget management |
| Tool/API Outputs | Location lookup, representative finder, fact-checker |
| System Prompt | Fixed identity + rules + format (SYSTEM_PROMPT.md) |
| Retrieved Knowledge | RAG with hybrid search (vector + BM25) |
| Conversation Memory | Last 5 turns + active topic + pending actions |
| User Profile | Political fingerprint (location, interests, engagement) |
| LLM | Claude/GPT-4 with assembled context |
| Model Output | Parsed response with entities and follow-ups |
| Response Formatter | WhatsApp-optimized (4096 char limit, buttons) |
| Evaluation Layer | Accuracy, neutrality, relevance, tone, safety scoring |
| Context Review Loop | Flagged conversations → improvement backlog |

This architecture is production-ready. Each component has a clear responsibility and can be tested independently.
