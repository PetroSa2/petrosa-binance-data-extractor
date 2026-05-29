#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Starting Local CI/CD Pipeline Simulation"
echo "============================================="
echo "Date: $(date)"
echo "Working Directory: $(pwd)"
echo "Python Version: $("$SCRIPT_DIR/.venv/bin/python" --version)"
echo "============================================="

# Step 1: Install dependencies
echo ""
echo "📦 Step 1: Installing Dependencies"
echo "-----------------------------------"
"$SCRIPT_DIR/.venv/bin/python" -m pip install --upgrade pip
"$SCRIPT_DIR/.venv/bin/pip" install -r requirements.txt
"$SCRIPT_DIR/.venv/bin/pip" install -r requirements-dev.txt
echo "✅ Dependencies installed successfully"

# Step 2: Run linting
echo ""
echo "🔍 Step 2: Running Code Linting"
echo "--------------------------------"
echo "Running critical errors check..."
"$SCRIPT_DIR/.venv/bin/python" -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics --exclude=.venv,venv,htmlcov,__pycache__,.git,.mypy_cache,.pytest_cache
echo "✅ Critical errors check passed"

echo "Running style check..."
"$SCRIPT_DIR/.venv/bin/python" -m flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics --exclude=.venv,venv,htmlcov,__pycache__,.git,.mypy_cache,.pytest_cache
echo "✅ Style check completed"

# Step 3: Run type checking
echo ""
echo "🔍 Step 3: Running Type Checking"
echo "---------------------------------"
"$SCRIPT_DIR/.venv/bin/python" -m mypy . --ignore-missing-imports
echo "✅ Type checking passed"

# Step 4: Run tests
echo ""
echo "🧪 Step 4: Running Unit Tests"
echo "------------------------------"
"$SCRIPT_DIR/.venv/bin/python" -m pytest tests/ -v --cov=. --cov-report=xml --cov-report=term
echo "✅ Unit tests completed"

# Step 5: Check coverage
echo ""
echo "📊 Step 5: Coverage Analysis"
echo "-----------------------------"
echo "📊 Coverage Report Summary:"
echo "=========================="

# Generate and display coverage report
"$SCRIPT_DIR/.venv/bin/python" -m coverage report --show-missing --skip-covered

# Get coverage percentage
COVERAGE_PERCENT=$("$SCRIPT_DIR/.venv/bin/python" -m coverage report --format=total)
echo ""
echo "📈 Total Coverage: ${COVERAGE_PERCENT}%"

# Set coverage threshold (adjust as needed)
COVERAGE_THRESHOLD=80

if (( COVERAGE_PERCENT >= COVERAGE_THRESHOLD )); then
  echo "✅ Coverage meets threshold of ${COVERAGE_THRESHOLD}%"
  COVERAGE_STATUS="PASS"
else
  echo "⚠️  Coverage below threshold of ${COVERAGE_THRESHOLD}%"
  echo "❌ Current: ${COVERAGE_PERCENT}%, Required: ${COVERAGE_THRESHOLD}%"
  COVERAGE_STATUS="WARNING"
fi

# Step 6: Run OpenTelemetry Integration Tests
echo ""
echo "🔧 Step 6: OpenTelemetry Integration Tests"
echo "------------------------------------------"
"$SCRIPT_DIR/.venv/bin/python" docs/test_integration.py
echo "✅ OpenTelemetry integration tests passed"

# Final Summary
echo ""
echo "🎉 CI/CD Pipeline Summary"
echo "========================="
echo "✅ Dependencies Installation: PASS"
echo "✅ Code Linting: PASS"
echo "✅ Type Checking: PASS"
echo "✅ Unit Tests: PASS"
echo "${COVERAGE_STATUS == 'PASS' && echo '✅' || echo '⚠️ '} Coverage Analysis: ${COVERAGE_STATUS}"
echo "✅ OpenTelemetry Integration: PASS"
echo ""
echo "🚀 Pipeline Status: ${COVERAGE_STATUS == 'WARNING' && echo 'SUCCESS WITH WARNINGS' || echo 'SUCCESS'}"
echo "🎯 Ready for deployment!"
echo ""
echo "============================================="
echo "CI/CD Pipeline completed at: $(date)"
echo "============================================="
