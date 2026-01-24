#!/bin/bash
set -euo pipefail

# Only run in remote Claude Code web environment
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "Installing Decide9ja dependencies..."

# Install Python dependencies for backend
cd "$CLAUDE_PROJECT_DIR/decide9ja_backend"
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install Node.js dependencies for frontend
cd "$CLAUDE_PROJECT_DIR/decide9ja_frontend/decide9ja-web"
echo "Installing Node.js dependencies..."
npm install

echo "Decide9ja dependencies installed successfully!"
