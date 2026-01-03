# Decide9ja - Claude Code Context

## Project Overview
Decide9ja is an AI-powered political intelligence platform that empowers Nigerian voters with accurate, sourced information about politicians, elections, and governance. Users interact via WhatsApp bot, web app, or voice calls.

## Tech Stack

### Frontend (`decide9ja_frontend/decide9ja-web/`)
- Next.js 16.1.1 + React 19 + TypeScript 5
- Tailwind CSS 4 + Radix UI components
- Lucide React icons

### Backend (`decide9ja_backend/`)
- FastAPI + Uvicorn (Python)
- SQLAlchemy 2.0 + PostgreSQL (prod) / SQLite (dev)
- Anthropic Claude API (LLM) + OpenAI (embeddings)
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
  └── nigeria_knowledge_data/        # Knowledge base storage

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
- `rag.py` - Retrieval-Augmented Generation core
- `message_handler*.py` - Message processing (v1-v4)
- `claude_understand.py` - Claude API integration
- `intent_classifier.py` - User intent classification
- `retrieval.py` / `intelligent_retrieval.py` - Semantic search
- `prompt_guard.py` - Security/injection detection
- `whatsapp.py` - WhatsApp bot logic
- `fuzzy_match.py` - Nigerian name/entity matching

## Coding Conventions
- Use type hints in Python
- Use TypeScript strict mode in frontend
- All API responses should include sources/citations
- Nigerian-specific matching should use `fuzzy_match.py` utilities
- Security: Always sanitize user input, use prompt guards

## Common Mistakes to Avoid
- Don't hardcode API keys - use environment variables
- Don't skip prompt injection guards in LLM calls
- Don't forget to handle Nigerian language variations (Pidgin, Hausa, Yoruba, Igbo)
- Don't create new service files when existing ones can be extended
- Remember: phone numbers are hashed with SHA256 for privacy

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
