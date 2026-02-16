# Tade Improvement Plan — Bringing It to Tafa Standards

**Goal:** Improve Decide9ja/Tade codebase to meet VoltAgent patterns, content design principles, and reduce context costs via QMD.

**Constraint:** Tade remains separate from Tafa. I advise/implement, you own it.

---

## Current State Analysis

### What's Working (From Code Review)
- ✅ FastAPI backend with security hardening
- ✅ WhatsApp webhook integration
- ✅ Claude-first architecture for intent classification
- ✅ State management with persistent memory
- ✅ Controversial topic detection
- ✅ Multiple services (retrieval, gamification, fact-check, community)
- ✅ Rate limiting, CORS, input sanitization

### What's Missing/Vulnerable
- ❌ No QMD integration — retrieving full documents instead of chunks
- ❌ High context costs — passing full retrieved content to Claude
- ❌ No VoltAgent patterns — custom architecture instead of framework
- ❌ Limited RAG — no vector embeddings for semantic search
- ❌ No tool architecture — monolithic handlers instead of composable tools
- ❌ Memory implementation is custom — not using Supermemory or standard patterns
- ❌ No conversation state machine — flow logic scattered
- ❌ Limited error recovery — fragile conversation flows

---

## Phase 1: QMD Integration (Reduce Context Costs)

### Why QMD First
- **Immediate cost savings** — Local search vs. API calls
- **Better RAG** — Retrieve only relevant chunks, not full documents
- **Hybrid search** — BM25 (fast) + semantic (accurate)
- **Privacy** — Nigerian political data stays local

### Implementation Steps

**1.1 Index Current Data as Markdown**
```bash
# Create collections
qmd collection add /data/budgets --name budgets --mask "**/*.md"
qmd collection add /data/news --name news --mask "**/*.md"
qmd collection add /data/politicians --name politicians --mask "**/*.md"
qmd collection add /data/archives --name archives --mask "**/*.md"

# Generate embeddings (one-time, slow)
qmd embed
```

**1.2 Replace Full Retrieval with QMD Search**
```python
# BEFORE (high cost):
full_doc = retrieve_document(doc_id)
context = full_doc.content  # 5000 tokens!

# AFTER (low cost):
chunks = qmd_search(query, collection="budgets", n=5)
context = "\n\n".join([c.content for c in chunks])  # 500 tokens!
```

**1.3 Set Up Auto-Update**
```bash
# Cron: Update index hourly
0 * * * * qmd update

# Cron: Re-embed nightly
0 5 * * * qmd embed
```

### Expected Impact
- **Context cost reduction:** 80-90% fewer tokens per query
- **Latency improvement:** Local search vs. database/API calls
- **Better relevance:** Semantic + keyword search finds better matches

---

## Phase 2: VoltAgent Migration (Better Architecture)

### Why VoltAgent
- **Proven patterns** — Production-tested by thousands of agents
- **Tool architecture** — Composable, testable, reusable
- **Memory system** — Working memory with Zod schemas
- **State management** — Built-in conversation flows
- **Observability** — Tracing, debugging, monitoring

### Migration Strategy

**2.1 Gradual Migration (Not Rewrite)**
```
Current: FastAPI + Custom Services
    ↓
Hybrid: FastAPI + VoltAgent Tools
    ↓
Target: Full VoltAgent (optional)
```

**2.2 Extract Tools from Services**
Convert monolithic services to VoltAgent tools:

```typescript
// BEFORE (Python service):
class BudgetService:
    def query_budget(self, state, query):
        # 200 lines of logic
        pass

// AFTER (VoltAgent tool):
const queryBudget = createTool({
  name: "queryBudget",
  parameters: z.object({
    state: z.string(),
    year: z.number().optional(),
    category: z.enum(["education", "health", "all"])
  }),
  execute: async ({ state, year, category }) => {
    // Use QMD for retrieval
    const chunks = await qmdSearch(`${state} ${category} budget`, "budgets");
    return { results: chunks, totalBudget: calculateTotal(chunks) };
  }
});
```

**2.3 Implement Working Memory Schema**
```typescript
const tadeWorkingMemorySchema = z.object({
  userPhone: z.string(),
  location: z.object({
    state: z.string().optional(),
    lga: z.string().optional(),
  }),
  conversationStage: z.enum([
    "greeting", "location_collection", "query_handling", "follow_up"
  ]),
  currentQuery: z.object({
    type: z.enum(["representative", "budget", "news", "archive"]),
    queryText: z.string(),
    toolsUsed: z.array(z.string()),
  }),
  pendingClarification: z.boolean().default(false),
  lastActivity: z.date(),
});
```

**2.4 Add State Machine**
Replace scattered flow logic with explicit state machine:

```typescript
const stateMachine = {
  greeting: {
    on: { LOCATION_RECEIVED: "location_collection" }
  },
  location_collection: {
    on: { QUERY_RECEIVED: "query_handling" }
  },
  query_handling: {
    entry: "executeTools",
    on: { TOOLS_COMPLETE: "follow_up" }
  },
  follow_up: {
    on: { NEW_QUERY: "query_handling", GOODBYE: "end" }
  }
};
```

---

## Phase 3: Content Design Improvements

### 3.1 Progressive Profiling
Instead of asking everything upfront:
```
User: "Hi Tade"
Tade: "Hello! I'm Tade, your civic companion. I can help you find your representatives, check budgets, or search historical news. What state are you in?"

[Later, after trust built]
Tade: "By the way, would you like me to send you weekly budget updates? What's your LGA?"
```

### 3.2 Better Error Recovery
```python
# BEFORE:
"Sorry, I don't understand."

# AFTER:
"I want to make sure I help you correctly. Are you asking about:
1. Your federal representative (House of Reps)
2. Your senator
3. Your state governor

Reply with 1, 2, or 3."
```

### 3.3 Pidgin/Local Language Handling
```typescript
const languageDetection = createTool({
  name: "detectLanguage",
  execute: async (text) => {
    // Detect: English, Pidgin, Hausa, Yoruba, Igbo
    // Return appropriate response template
  }
});

// Response templates
const templates = {
  en: "Your representative is {name}.",
  pcm: "Your rep na {name}.",
  ha: "Jagoranku shine {name}.",
  yo: "Aṣojú rẹ ni {name}.",
  ig: "Onye nnọchiteanya gị bụ {name}."
};
```

### 3.4 Context Compression Recovery
When context compresses and user loses place:
```
[Context compressed]

Tade: "Quick reminder — we were talking about the Lagos State health budget. You asked about primary healthcare funding. Here's what I found..."
```

---

## Phase 4: Supermemory Integration

### Why Now
- Already have Pro subscription
- Better than custom memory implementation
- Cross-session continuity
- Automatic user profiling

### Implementation
```typescript
// Replace custom user_memory with Supermemory
import { supermemory_store, supermemory_search } from "@supermemory/openclaw-supermemory";

// Auto-profile building
if (user.mentionsLocation) {
  await supermemory_store({
    text: `User ${phone} is in ${state} state, ${lga} LGA`,
    category: "fact"
  });
}

// Before each response, auto-recall injects relevant memories
```

---

## Phase 5: Testing & Quality Assurance

### 5.1 Conversation Test Suite
```typescript
const testCases = [
  {
    name: "First-time user flow",
    messages: ["Hi", "Lagos", "Who is my rep?"],
    expected: ["greeting", "location_stored", "representative_found"]
  },
  {
    name: "Returning user",
    context: { location: { state: "Lagos" } },
    messages: ["Budget news"],
    expected: ["skips_location_ask", "budget_provided"]
  },
  {
    name: "Controversial topic",
    messages: ["Is Tinubu doing a good job?"],
    expected: ["neutral_response", "balanced_facts"]
  }
];
```

### 5.2 Cost Monitoring
```typescript
// Track tokens per conversation
const metrics = {
  tokensPerQuery: [],
  costPerUser: {},
  qmdVsFullRetrieval: {}
};

// Alert if costs spike
if (avgTokens > threshold) {
  logger.warn("High token usage detected — check QMD integration");
}
```

---

## Implementation Priority

| Phase | Task | Impact | Effort | Priority |
|-------|------|--------|--------|----------|
| 1 | QMD Setup | High | Medium | **P0** |
| 1 | Replace Retrieval | High | Medium | **P0** |
| 2 | Extract Tools | Medium | High | P1 |
| 2 | Working Memory | High | Medium | **P0** |
| 3 | Progressive Profiling | Medium | Low | P1 |
| 3 | Error Recovery | High | Low | **P0** |
| 4 | Supermemory | Medium | Low | P2 |
| 5 | Test Suite | High | Medium | P1 |

---

## Success Metrics

### Before → After

| Metric | Before | Target | How |
|--------|--------|--------|-----|
| **Tokens per query** | ~3000 | ~500 | QMD chunking |
| **Context cost** | $0.15/query | $0.03/query | QMD + efficient prompts |
| **Conversation completion** | 60% | 85% | Better error recovery |
| **Location collection** | 100% ask | 20% ask | Supermemory profiles |
| **Response latency** | 3-5s | <2s | QMD local search |
| **Test coverage** | 0% | 70% | Test suite |

---

## Next Steps

**Immediate (Today):**
1. Install QMD: `bun install -g https://github.com/tobi/qmd`
2. Index one collection (budgets) as test
3. Replace one retrieval path with QMD

**This Week:**
4. Index all collections
5. Implement working memory schema
6. Add error recovery patterns
7. Set up cost monitoring

**Next Week:**
8. Extract first tool (queryBudget)
9. Add progressive profiling
10. Begin Supermemory integration

---

**This plan respects:**
- Your time (gradual, not rewrite)
- Your budget (QMD reduces costs immediately)
- Your ownership (I implement, you decide)
- Tade's identity (remains separate from me)

Ready to start with QMD installation? 🦉

