#!/bin/bash
# Start the Clawd Domain backend server

cd "$(dirname "$0")/../backend"

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "❌ Virtual environment not found. Run setup.sh first."
    exit 1
fi

echo "🚀 Starting Clawd Domain Backend..."
echo "   URL: http://localhost:8402"
echo "   Health: http://localhost:8402/health"
echo ""

python -m src.main
