#!/bin/bash

# Test script for Petrosa Socket Client
# This script helps test the WebSocket client locally

set -e

echo "🚀 Testing Petrosa Socket Client locally..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅ Python version: $PYTHON_VERSION"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
echo "🧪 Running tests..."
python -m pytest tests/ -v --cov=socket_client --cov-report=term-missing

# Run linting
echo "✨ Running linting..."
python -m ruff check .
python -m black --check .
python -m isort --check-only .

# Run type checking
echo "🔍 Running type checking..."
python -m mypy socket_client/

# Test health endpoint (if running)
echo "🏥 Testing health endpoint..."
if curl -s http://localhost:8080/healthz > /dev/null 2>&1; then
    echo "✅ Health endpoint is responding"
    curl -s http://localhost:8080/healthz | python -m json.tool
else
    echo "⚠️  Health endpoint not available (service may not be running)"
fi

echo "✅ Local testing completed!"
