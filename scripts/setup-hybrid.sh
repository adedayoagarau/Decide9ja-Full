#!/bin/bash
# Setup script for Decide9ja Hybrid RAG System

echo "🚀 Setting up Decide9ja Hybrid RAG System..."
echo ""

# Check if running from correct directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Must run from Decide9ja root directory"
    exit 1
fi

# Install ngrok if not present
if ! command -v ngrok &> /dev/null; then
    echo "📦 Installing ngrok..."
    brew install ngrok || npm install -g ngrok
fi

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data/unified data/chroma logs memory

# Setup environment
echo "⚙️  Setting up environment..."
if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
# Local Configuration
NODE_ENV=development
PORT=3000

# Supabase (for hot tier sync - optional)
SUPABASE_URL=https://liosugqvfvubmqaqzrro.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxpb3N1Z3F2ZnZ1Ym1xYXF6cnJvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk5OTQxOTAsImV4cCI6MjA4NTU3MDE5MH0.F45A5NKhJwNrFbzmh_VuMy-o88WIiQw5uoVHY2UasPA
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxpb3N1Z3F2ZnZ1Ym1xYXF6cnJvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk5OTQxOTAsImV4cCI6MjA4NTU3MDE5MH0.F45A5NKhJwNrFbzmh_VuMy-o88WIiQw5uoVHY2UasPA

# Redis (for job queue)
REDIS_URL=redis://localhost:6379

# OpenAI (optional - for embeddings)
OPENAI_API_KEY=
EOF
    echo "✅ .env file created"
else
    echo "✅ .env file already exists"
fi

# Start Redis if not running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "🔄 Starting Redis..."
    brew services start redis || redis-server --daemonize yes
    sleep 2
fi

if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is running"
else
    echo "⚠️  Redis failed to start"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Ingest data:        npm run rag:ingest"
echo "2. Start API server:   npm run rag:api"
echo "3. Expose to internet: npm run tunnel"
echo "4. Sync to Supabase:   npm run rag:sync"
echo ""
echo "API Endpoints (when server is running):"
echo "  GET  http://localhost:3000/api/search?q=query"
echo "  GET  http://localhost:3000/api/documents/:id"
echo "  GET  http://localhost:3000/api/stats"
echo ""
