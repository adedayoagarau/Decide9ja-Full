# Decide9ja - Claude Code Context

## Project Overview

Decide9ja is a comprehensive AI-powered Nigerian political intelligence platform - an "everything app" for Nigerian politics. It empowers Nigerian voters with accurate, sourced information about:

- **Politicians**: 4,789+ profiles (senators, reps, governors, ministers, military leaders)
- **Elections**: Results from 2007-2023 (presidential, gubernatorial, legislative)
- **Governance**: Budget data, FAAC allocations, constituency projects
- **History**: Coups, constitutional changes, political transitions since 1960
- **Economy**: Interest rates, inflation, exchange rates, fiscal policy

Users interact via WhatsApp bot, web app, or voice calls.

## Data Sources

The platform combines multiple data sources:

| Source | Records | Content |
|--------|---------|---------|
| Wikidata | 8,392 | Politicians, parties, states, events |
| Wikipedia | 1,646 | Historical articles, coups, elections |
| BudgIT | 74,000+ | Budget data, FAAC, MDA projects |
| INEC | 774 LGAs | Electoral geography, results |
| News Crawlers | Live | 5 major Nigerian outlets |

## Tech Stack

### Frontend (`decide9ja_frontend/decide9ja-web/`)
- Next.js 16.1.1 + React 19 + TypeScript 5
- Tailwind CSS 4 + Radix UI components
- Lucide React icons

### Backend (`decide9ja_backend/`)
- FastAPI + Uvicorn (Python)
- SQLAlchemy 2.0 + PostgreSQL (prod) / SQLite (dev)
- Anthropic Claude API (LLM) + OpenAI (embeddings)
- NetworkX Knowledge Graph
- Twilio (WhatsApp + Voice)
- Redis (caching)

### Scrapers
- `decide9ja_scraper/` - INEC election data scraper
- `decide9ja-crawler/` - Azure Functions news crawler

## Key Directories

```
decide9ja_frontend/decide9ja-web/    # Main Next.js web app
  ├── app/                           # Next.js App Router pages
  ├── components/                    # React components by feature
  └── lib/                           # Utilities

decide9ja_backend/
  ├── app/main.py                    # FastAPI entry point
  ├── app/database.py                # SQLAlchemy models
  ├── app/routers/                   # API endpoints
  ├── app/services/                  # Business logic (60+ modules)
  │   └── nigeria_knowledge/         # Knowledge Graph system
  │       ├── knowledge_graph.py     # NetworkX graph implementation
  │       ├── historical_data.py     # Data seeding from all sources
  │       ├── query_engine.py        # Natural language queries
  │       └── entity_extractor.py    # Entity extraction from text
  └── nigeria_knowledge_data/        # Knowledge base storage
      ├── wikidata/                  # Structured entity data
      ├── wikipedia/                 # Historical articles
      ├── excel_imports/             # BudgIT financial data
      ├── internet_archive/          # Archived documents
      └── news/                      # Crawled news articles

decide9ja_scraper/                   # INEC data scraper
decide9ja-crawler/                   # Azure news crawler
```

## Common Commands

### Frontend
```bash
cd decide9ja_frontend/decide9ja-web && npm run dev    # Dev server :3000
cd decide9ja_frontend/decide9ja-web && npm run build  # Production build
cd decide9ja_frontend/decide9ja-web && npm run lint   # ESLint
```

### Backend
```bash
cd decide9ja_backend && uvicorn app.main:app --reload  # Dev server :8000
python decide9ja_backend/scripts/seed_database.py     # Seed DB
python decide9ja_backend/scripts/ingest_knowledge_base.py  # Ingest knowledge
python -m app.scheduler                                # Background jobs
```

### Testing
```bash
python decide9ja_backend/tests/test_fuzzy_matching.py
python decide9ja_backend/tests/test_flow_routing.py
python decide9ja_backend/tests/test_intelligence.py
python decide9ja_backend/test_v2_integration.py
```

## Key Services (in `decide9ja_backend/app/services/`)

### Core Intelligence
- `rag.py` - Retrieval-Augmented Generation (combines DB + Knowledge Graph)
- `nigeria_knowledge/` - Knowledge Graph system for structured queries
- `message_handler*.py` - Message processing (v1-v4)
- `claude_understand.py` - Claude API integration
- `intent_classifier.py` - User intent classification

### Data & Retrieval
- `retrieval.py` / `intelligent_retrieval.py` - Semantic search
- `fuzzy_match.py` - Nigerian name/entity matching
- `news_pipeline.py` - Real-time news integration

### Security & Communication
- `prompt_guard.py` - Security/injection detection
- `whatsapp.py` - WhatsApp bot logic

## Knowledge Graph Capabilities

The knowledge graph supports queries like:
- "Who is the senator for Lagos Central?"
- "Compare Tinubu and Atiku"
- "What coups happened in Nigeria?"
- "Interest rate in 2023"
- "Budget allocation for education"
- "Members of APC"

## Coding Conventions
- Use type hints in Python
- Use TypeScript strict mode in frontend
- All API responses should include sources/citations
- Nigerian-specific matching should use `fuzzy_match.py` utilities
- Security: Always sanitize user input, use prompt guards
- Knowledge Graph: Use `query_knowledge()` for structured data

## Common Mistakes to Avoid
- Don't hardcode API keys - use environment variables
- Don't skip prompt injection guards in LLM calls
- Don't forget to handle Nigerian language variations (Pidgin, Hausa, Yoruba, Igbo)
- Don't create new service files when existing ones can be extended
- Remember: phone numbers are hashed with SHA256 for privacy
- Don't bypass the knowledge graph for structured political queries
- Always cite sources (INEC, BudgIT, Wikipedia, etc.)

## Environment Variables Required
```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DATABASE_URL=           # PostgreSQL connection string (prod)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
REDIS_URL=              # Optional caching
```

## Database Models (in `database.py`)
- `Document` - RAG documents with embeddings
- `Politician` - Politician profiles
- `Interaction` - User query logs
- Plus: parties, states, LGAs, election results

## API Endpoints
- `GET /health` - Health check
- `POST /ask` - Main query endpoint
- `POST /webhook` - WhatsApp webhook
- `POST /voice` - Voice interaction
- `/admin/*` - Admin endpoints

## What Makes Decide9ja Unique

1. **Comprehensive Data**: Not just a lookup tool - full political intelligence
2. **Multi-Source Retrieval**: Combines database, knowledge graph, news, web search
3. **Nigerian Context**: Handles Pidgin, fuzzy matching for Nigerian names
4. **Financial Awareness**: BudgIT integration for budget/allocation queries
5. **Historical Depth**: 1960-present coverage of political events
6. **Neutrality**: Never endorses candidates, presents facts only
