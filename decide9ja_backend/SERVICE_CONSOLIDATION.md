# Decide9ja Service Consolidation Plan

## Current State: 110+ Services

The current `app/services/` directory has too many modules with overlapping functionality.
This document maps the consolidation from 110+ services to ~20 core modules.

## Target Architecture: 20 Core Modules

### 1. Core Intelligence

| New Module | Replaces | Description |
|------------|----------|-------------|
| `core/llm.py` | `llm.py`, `claude_understand.py` | Unified LLM interface (Claude + fallbacks) |
| `core/retrieval.py` | `retrieval.py`, `intelligent_retrieval.py`, `agentic_retrieval.py`, `enhanced_rag.py`, `rag.py` | Unified retrieval (semantic search + knowledge graph) |
| `core/embeddings.py` | `embeddings.py` | Embedding generation (OpenAI, with caching) |
| `core/intent.py` | `intent_classifier.py`, `router.py`, `query_planner.py` | Intent classification and query routing |

### 2. Knowledge & Data

| New Module | Replaces | Description |
|------------|----------|-------------|
| `knowledge/graph.py` | `nigeria_knowledge/*`, `governance_knowledge.py` | Knowledge graph queries (now PostgreSQL-backed) |
| `knowledge/politicians.py` | `politician_lookup.py`, `politician_comparison.py`, `politician_dossier_generator.py`, `politician_mention_service.py` | All politician-related operations |
| `knowledge/elections.py` | `elections_service.py`, `poll_service.py`, `poll_results_service.py` | Election data and results |
| `knowledge/budget.py` | `projects_service.py` | Budget, FAAC, and constituency projects |
| `knowledge/legislative.py` | `legislative_service.py`, `voting_record_service.py` | Bills and voting records |

### 3. Messaging & Channels

| New Module | Replaces | Description |
|------------|----------|-------------|
| `channels/whatsapp.py` | `whatsapp.py`, `twilio_whatsapp.py` | WhatsApp via Twilio |
| `channels/voice.py` | `voice.py`, `voice_handler.py` | Voice calls and transcription |
| `messaging/handler.py` | `message_handler_v5.py` (primary handler) | Single message handler |
| `messaging/broadcast.py` | `broadcast_service.py`, `broadcast_sender.py` | Broadcast messaging |

### 4. Memory & User

| New Module | Replaces | Description |
|------------|----------|-------------|
| `memory/supermemory.py` | `supermemory_integration.py`, `user_memory.py`, `context_memory.py`, `memory.py`, `enhanced_memory.py`, `working_memory_enhanced.py` | SuperMemory for all memory needs |
| `users/profile.py` | `personalization_service.py`, `progressive_profiling.py`, `user_segmentation.py` | User profiles and preferences |
| `users/onboarding.py` | `onboarding.py` | User onboarding flow |

### 5. Content & News

| New Module | Replaces | Description |
|------------|----------|-------------|
| `content/crawler.py` | `news_scraper.py`, `news_scraper_resilient.py`, `news_scraper_wayback.py`, `ai_crawler.py`, `archiving_scraper.py`, `historical_news_backfill.py`, `enhanced_scraper.py` → **USE `unified_crawler.py`** | All crawling in one place |
| `content/news.py` | `news_pipeline.py`, `news_agent.py`, `news_digest_service.py` | News processing and delivery |
| `content/search.py` | `search_discovery.py`, `search_orchestrator.py`, `realtime_search.py`, `web_search.py` | Unified search interface |

### 6. Community & Civic

| New Module | Replaces | Description |
|------------|----------|-------------|
| `civic/issues.py` | `issue_pipeline.py`, `issue_agent.py`, `civic_issues/*` | Issue tracking and reporting |
| `civic/community.py` | `community_service.py`, `constituency_service.py` | Community features |
| `civic/gamification.py` | `gamification_service.py` | Points and badges |

### 7. Security & Infrastructure

| New Module | Replaces | Description |
|------------|----------|-------------|
| `security/guards.py` | `prompt_guard.py`, `output_guard.py`, `security.py` | All security checks |
| `infra/cache.py` | `cache.py` | Redis caching |
| `infra/analytics.py` | `analytics.py`, `analytics_service.py`, `dashboard.py` | Analytics and metrics |
| `infra/scheduler.py` | `scheduler.py` | Background job scheduling |

### 8. Utilities

| New Module | Replaces | Description |
|------------|----------|-------------|
| `utils/fuzzy.py` | `fuzzy_match.py` | Nigerian name matching |
| `utils/location.py` | `location.py` | Location processing |
| `utils/localization.py` | `localization.py` | Multi-language support |
| `utils/media.py` | `media.py`, `image_handler.py`, `multimodal.py`, `document_handler.py` | Media processing |

---

## Files to Archive (Deprecated)

These files should be moved to `_archive/` and not used:

```
message_handler.py (archived, use v5)
message_handler_v1.py (archived)
message_handler_v2.py (archived)
message_handler_v3.py (archived)
message_handler_v4.py (archived, replaced by v5)
realtime.py (unused)
schema_generator.py (one-time use)
procedure_generator.py (one-time use)
jurisdiction_generator.py (one-time use)
dossier_generator.py (use politician_dossier_generator.py)
templates.py (consolidate into messaging)
tade_persona.py (consolidate into llm.py)
tade_unified.py (consolidate into handler.py)
state_manager.py (replaced by memory)
conversation.py (replaced by memory)
content_context_engine.py (consolidate into retrieval)
context_assembler.py (consolidate into retrieval)
oyo_state_data.py (move to knowledge data)
```

---

## Migration Steps

### Phase 1: Create Core Module Structure
```
app/services/
├── core/           # LLM, retrieval, embeddings, intent
├── knowledge/      # Knowledge graph, politicians, elections
├── channels/       # WhatsApp, voice
├── messaging/      # Message handling, broadcast
├── memory/         # SuperMemory integration
├── users/          # Profiles, onboarding
├── content/        # News, crawlers, search
├── civic/          # Issues, community
├── security/       # Guards, auth
├── infra/          # Cache, analytics, scheduler
├── utils/          # Fuzzy matching, location, media
└── _archive/       # Deprecated modules
```

### Phase 2: Create New Consolidated Modules
1. Start with `core/` modules (most critical)
2. Then `knowledge/` (data layer)
3. Then `messaging/` (user-facing)
4. Then everything else

### Phase 3: Update Imports
- Update `main.py` and all routers to use new paths
- Run tests after each module migration

### Phase 4: Archive Old Files
- Move deprecated files to `_archive/`
- Keep for reference but don't import

---

## New Directory Structure

```
app/
├── main.py                    # FastAPI app (updated imports)
├── database.py                # Original models
├── database_v2.py             # New knowledge graph models
├── routers/                   # API endpoints (unchanged)
├── api/                       # Additional APIs (unchanged)
├── channels/                  # Channel implementations
└── services/
    ├── __init__.py
    ├── core/
    │   ├── __init__.py
    │   ├── llm.py            # LLM interface
    │   ├── retrieval.py      # Unified retrieval
    │   ├── embeddings.py     # Embedding generation
    │   └── intent.py         # Intent classification
    ├── knowledge/
    │   ├── __init__.py
    │   ├── graph.py          # Knowledge graph
    │   ├── politicians.py    # Politician operations
    │   ├── elections.py      # Election data
    │   ├── budget.py         # Budget data
    │   └── legislative.py    # Bills and votes
    ├── messaging/
    │   ├── __init__.py
    │   ├── handler.py        # Message handling
    │   └── broadcast.py      # Broadcast messaging
    ├── memory/
    │   ├── __init__.py
    │   └── supermemory.py    # SuperMemory integration
    ├── users/
    │   ├── __init__.py
    │   ├── profile.py        # User profiles
    │   └── onboarding.py     # Onboarding flow
    ├── content/
    │   ├── __init__.py
    │   ├── unified_crawler.py # All crawling
    │   ├── news.py           # News processing
    │   └── search.py         # Search interface
    ├── civic/
    │   ├── __init__.py
    │   ├── issues.py         # Issue tracking
    │   ├── community.py      # Community features
    │   └── gamification.py   # Gamification
    ├── security/
    │   ├── __init__.py
    │   └── guards.py         # All security checks
    ├── infra/
    │   ├── __init__.py
    │   ├── cache.py          # Redis caching
    │   ├── analytics.py      # Analytics
    │   └── scheduler.py      # Job scheduling
    ├── utils/
    │   ├── __init__.py
    │   ├── fuzzy.py          # Fuzzy matching
    │   ├── location.py       # Location processing
    │   ├── localization.py   # i18n
    │   └── media.py          # Media processing
    └── _archive/             # Deprecated modules
```

---

## Benefits of Consolidation

1. **Maintainability**: 20 modules vs 110+ is much easier to understand
2. **Performance**: Fewer imports, cleaner dependency graph
3. **Testing**: Clearer boundaries make testing easier
4. **Onboarding**: New developers can understand the codebase faster
5. **Deployment**: Smaller, more focused containers possible
