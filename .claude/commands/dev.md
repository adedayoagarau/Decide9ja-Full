# Start Development Environment

Start the development servers for Decide9ja.

## Backend (FastAPI)
```bash
cd decide9ja_backend && uvicorn app.main:app --reload --port 8000
```

## Frontend (Next.js)
```bash
cd decide9ja_frontend/decide9ja-web && npm run dev
```

Start the backend server first, then the frontend in a separate terminal.
Report the URLs when servers are running:
- Backend: http://localhost:8000
- Frontend: http://localhost:3000
