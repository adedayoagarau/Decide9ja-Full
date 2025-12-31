# Decide9ja RAG Backend

Political intelligence API for Nigerian voters. Uses RAG (Retrieval-Augmented Generation) to provide accurate, sourced information about Nigerian politicians and elections.

## Quick Start

### 1. Install Dependencies
```bash
cd decide9ja_backend
pip install -r requirements.txt
```

### 2. Set Environment Variables
```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 3. Seed the Database
```bash
python scripts/seed_database.py
```

### 4. Start the Server
```bash
uvicorn app.main:app --reload
```

### 5. Test It
```bash
# Health check
curl http://localhost:8000/health

# Ask a question
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "Who is my senator in Lagos Central?"}'
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info |
| `/health` | GET | Health check with DB stats |
| `/ask` | POST | Query endpoint (RAG + Claude) |
| `/webhook` | POST | WhatsApp webhook (Twilio format) |
| `/debug/documents` | GET | List documents (dev only) |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `DATABASE_URL` | No | Database URL (default: SQLite) |

## Architecture

```
User Query
    ↓
FastAPI /ask endpoint
    ↓
RAG Service (semantic search)
    ↓
Claude API (grounded response)
    ↓
Response with sources
```

## Data Loaded

- **Senators**: 109 profiles
- **House of Reps**: 360 profiles  
- **Governors**: 37 profiles
- **Election Results**: 2023 Presidential by state
- **Polls**: NOI Polls data

## Production Deployment

1. Set up PostgreSQL with pgvector extension
2. Update `DATABASE_URL` to PostgreSQL
3. Deploy to Railway/Render/Docker
4. Configure Twilio webhook URL to `/webhook`
