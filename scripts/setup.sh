#!/bin/bash
# Clawd Domain Marketplace - Setup Script

set -e

echo "🚀 Setting up Clawd Domain Marketplace..."

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 required"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ Node.js required"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "❌ npm required"; exit 1; }

cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "📁 Project root: $PROJECT_ROOT"

# Backend setup
echo ""
echo "🐍 Setting up Python backend..."
cd "$PROJECT_ROOT/backend"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "   Created virtual environment"
fi

source venv/bin/activate
pip install -q -r requirements.txt
echo "   Installed dependencies"

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "   Created .env from template"
    echo "   ⚠️  Edit .env to add your Porkbun API keys (or leave blank for mock mode)"
fi

# MCP server setup
echo ""
echo "📦 Setting up MCP server..."
cd "$PROJECT_ROOT/mcp-server"

npm install --silent
npm run build
echo "   Built MCP server"

# Create Claude Code config
echo ""
echo "🔧 Configuring Claude Code..."

MCP_PATH="$PROJECT_ROOT/mcp-server/dist/index.js"
CLAUDE_CONFIG="$HOME/.claude.json"

# Check if claude.json exists and has mcpServers
if [ -f "$CLAUDE_CONFIG" ]; then
    echo "   Found existing ~/.claude.json"
    echo ""
    echo "   Add this to your mcpServers configuration:"
else
    echo "   Create ~/.claude.json with:"
fi

cat << EOF

{
  "mcpServers": {
    "clawd-domains": {
      "command": "node",
      "args": ["$MCP_PATH"],
      "env": {
        "CLAWD_BACKEND_URL": "http://localhost:8402"
      }
    }
  }
}

EOF

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Add the MCP server config to ~/.claude.json"
echo "   2. Start the backend:  cd backend && source venv/bin/activate && python -m src.main"
echo "   3. Restart Claude Code to pick up the new MCP server"
echo "   4. Try: 'search for a domain called myproject'"
echo ""
