# Makefile for Petrosa Binance Data Extractor
# Provides development and testing procedures

.PHONY: help install install-dev test_mypy run_unit_tests run_lint run_pipeline clean

# Default target
help:
	@echo "🚀 Petrosa Binance Data Extractor - Development Commands"
	@echo "======================================================"
	@echo ""
	@echo "📦 Installation:"
	@echo "  install        - Install production dependencies"
	@echo "  install-dev    - Install development dependencies"
	@echo ""
	@echo "🧪 Testing:"
	@echo "  test_mypy      - Run type checking with mypy"
	@echo "  run_unit_tests - Run unit tests with pytest"
	@echo "  run_lint       - Run code linting with flake8"
	@echo "  fix_lint       - Auto-fix common linting issues (W291, W293, F401, imports)"
	@echo "  run_pipeline   - Run complete CI pipeline (lint + type check + tests)"
	@echo ""
	@echo "🧹 Maintenance:"
	@echo "  clean          - Clean up cache and temporary files"
	@echo "  format         - Format code with black and isort"
	@echo ""
	@echo "📊 Coverage:"
	@echo "  coverage       - Run tests with coverage report"
	@echo "  coverage-html  - Generate HTML coverage report"
	@echo ""

# Installation targets
install:
	@echo "📦 Installing production dependencies..."
	python -m pip install --upgrade pip
	pip install -r requirements.txt

install-dev: install
	@echo "🔧 Installing development dependencies..."
	pip install -r requirements-dev.txt

# Testing targets
test_mypy:
	@echo "🔍 Running type checking with mypy..."
	mypy . --ignore-missing-imports

run_unit_tests:
	@echo "🧪 Running unit tests..."
	OTEL_NO_AUTO_INIT=1 pytest tests/ -v --tb=short

run_lint:
	@echo "✨ Running code linting..."
	@echo "Running flake8 with strict checks..."
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics --exclude=venv/*,.venv/*,htmlcov/*,.git/*,__pycache__/*,*.egg-info/*
	@echo "Running flake8 with style checks..."
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics --exclude=venv/*,.venv/*,htmlcov/*,.git/*,__pycache__/*,*.egg-info/*

fix_lint:
	@echo "🔧 Auto-fixing common linting issues..."
	@echo "Installing auto-fix dependencies..."
	pip install -q autopep8 isort autoflake
	@echo "Removing unused imports (F401)..."
	autoflake --in-place --remove-all-unused-imports --recursive --exclude=venv,.venv,htmlcov,.git,__pycache__,*.egg-info .
	@echo "Fixing whitespace issues (W291, W293)..."
	autopep8 --in-place --recursive --select=W291,W293 --exclude=venv,.venv,htmlcov,.git,__pycache__,*.egg-info .
	@echo "Sorting imports..."
	isort . --profile=black --skip=venv,.venv,htmlcov,.git,__pycache__,*.egg-info
	@echo "✅ Auto-fix completed! Run 'make run_lint' to check remaining issues."

# Combined pipeline target
run_pipeline: install-dev
	@echo "🚀 Running complete CI pipeline..."
	@echo "=================================="
	@echo ""
	@echo "1️⃣ Running linting..."
	$(MAKE) run_lint
	@echo ""
	@echo "2️⃣ Running type checking..."
	$(MAKE) test_mypy
	@echo ""
	@echo "3️⃣ Running unit tests..."
	$(MAKE) run_unit_tests
	@echo ""
	@echo "✅ Pipeline completed successfully!"

# Code formatting
format:
	@echo "🎨 Formatting code with black and isort..."
	black . --line-length=127
	isort . --profile=black

# Coverage targets
coverage: install-dev
	@echo "📊 Running tests with coverage..."
	OTEL_NO_AUTO_INIT=1 pytest tests/ -v --cov=. --cov-report=xml --cov-report=term

coverage-html: coverage
	@echo "📈 Generating HTML coverage report..."
	coverage html
	@echo "📄 HTML report generated in htmlcov/index.html"

# Check coverage threshold
check-coverage: coverage
	@echo "📊 Checking coverage threshold..."
	@COVERAGE_PERCENT=$$(coverage report --format=total); \
	echo "📈 Total Coverage: $${COVERAGE_PERCENT}%"; \
	COVERAGE_THRESHOLD=80; \
	if (( $$(echo "$${COVERAGE_PERCENT} >= $${COVERAGE_THRESHOLD}" | bc -l) )); then \
		echo "✅ Coverage meets threshold of $${COVERAGE_THRESHOLD}%"; \
	else \
		echo "⚠️  Coverage below threshold of $${COVERAGE_THRESHOLD}%"; \
		echo "❌ Current: $${COVERAGE_PERCENT}%, Required: $${COVERAGE_THRESHOLD}%"; \
		exit 1; \
	fi

# Security scanning
security-scan:
	@echo "🔒 Running security scan..."
	@if command -v trivy >/dev/null 2>&1; then \
		echo "Running Trivy vulnerability scanner..."; \
		trivy fs . --format table; \
	else \
		echo "⚠️  Trivy not installed. Install with: brew install trivy (macOS) or see https://aquasecurity.github.io/trivy/latest/getting-started/installation/"; \
	fi

# Development helpers
dev-setup: install-dev
	@echo "🚀 Setting up development environment..."
	@echo "✅ Development environment ready!"
	@echo ""
	@echo "Available commands:"
	@echo "  make run_pipeline    - Run complete CI pipeline"
	@echo "  make test_mypy       - Type checking"
	@echo "  make run_unit_tests  - Unit tests"
	@echo "  make run_lint        - Code linting"
	@echo "  make format          - Code formatting"

# Cleanup
clean:
	@echo "🧹 Cleaning up cache and temporary files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name "*.pyd" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "✅ Cleanup completed!"

# Docker helpers
docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t petrosa-binance-extractor .

docker-run:
	@echo "🐳 Running Docker container..."
	docker run --rm -it petrosa-binance-extractor

# Kubernetes helpers
k8s-apply:
	@echo "☸️  Applying Kubernetes manifests..."
	kubectl apply -f k8s/ --recursive

k8s-status:
	@echo "📊 Kubernetes deployment status:"
	kubectl get all -l app=binance-extractor -n petrosa-apps || echo "No resources found"
	kubectl get cronjobs -n petrosa-apps || echo "No CronJobs found"

# Quick test for specific components
test-production:
	@echo "🧪 Testing production extractor..."
	python jobs/extract_klines_production.py --help

test-gap-filler:
	@echo "🧪 Testing gap filler..."
	python jobs/extract_klines_gap_filler.py --help

# All-in-one development command
dev: dev-setup run_pipeline
	@echo "🎉 Development setup and pipeline completed!"

# CI/CD simulation (matches GitHub Actions workflow)
ci-simulation: install-dev
	@echo "🔄 Simulating CI/CD pipeline..."
	@echo "=================================="
	@echo ""
	@echo "1️⃣ Running linting (flake8)..."
	$(MAKE) run_lint
	@echo ""
	@echo "2️⃣ Running type checking (mypy)..."
	$(MAKE) test_mypy
	@echo ""
	@echo "3️⃣ Running tests with coverage..."
	$(MAKE) coverage
	@echo ""
	@echo "4️⃣ Checking coverage threshold..."
	$(MAKE) check-coverage
	@echo ""
	@echo "5️⃣ Running security scan..."
	$(MAKE) security-scan
	@echo ""
	@echo "✅ CI/CD simulation completed successfully!" 