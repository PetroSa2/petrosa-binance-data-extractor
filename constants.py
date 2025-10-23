"""
Configuration constants for the Petrosa Binance Data Extractor.
This module contains all configurable parameters for historical data extraction
including API URLs, database settings, and extraction parameters.
"""

import os

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Binance API settings
BINANCE_API_URL = os.getenv("BINANCE_API_URL", "https://api.binance.com")
BINANCE_FUTURES_API_URL = os.getenv(
    "BINANCE_FUTURES_API_URL", "https://fapi.binance.com"
)

# Default trading symbols
DEFAULT_SYMBOLS = os.getenv("DEFAULT_SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT").split(",")

# Supported intervals
SUPPORTED_INTERVALS = [
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "2h",
    "4h",
    "6h",
    "8h",
    "12h",
    "1d",
    "3d",
    "1w",
    "1M",
]
DEFAULT_PERIOD = "15m"

# Date settings
DEFAULT_START_DATE = "2023-01-01T00:00:00Z"
BACKFILL = False
GAP_CHECK_ENABLED = True

# API settings
API_KEY = os.getenv("API_KEY", "")
API_SECRET = os.getenv("API_SECRET", "")

# NATS settings
NATS_ENABLED = os.getenv("NATS_ENABLED", "false").lower() == "true"

# Data Manager configuration
DATA_MANAGER_URL = os.getenv("DATA_MANAGER_URL", "http://petrosa-data-manager:8000")
DATA_MANAGER_TIMEOUT = int(os.getenv("DATA_MANAGER_TIMEOUT", "30"))
DATA_MANAGER_MAX_RETRIES = int(os.getenv("DATA_MANAGER_MAX_RETRIES", "3"))
DATA_MANAGER_DATABASE = os.getenv("DATA_MANAGER_DATABASE", "mongodb")

# Legacy database configuration (deprecated - use DATA_MANAGER_URL instead)
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MYSQL_URI = os.getenv("MYSQL_URI", "mysql://user:pass@localhost:3306")
POSTGRESQL_URI = os.getenv("POSTGRESQL_URI", "postgresql://user:pass@localhost:5432")
DB_ADAPTER = os.getenv("DB_ADAPTER", "mysql")
DB_BATCH_SIZE = int(os.getenv("DB_BATCH_SIZE", "2000"))

# Extraction settings
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "24"))
API_RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "1200"))  # requests per minute
API_RATE_LIMIT_PER_MINUTE = int(
    os.getenv("API_RATE_LIMIT_PER_MINUTE", "1200")
)  # requests per minute
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "0.1"))

# Batch processing settings
MIN_BATCH_SIZE = int(os.getenv("MIN_BATCH_SIZE", "100"))
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "10000"))
SUCCESS_RATE_THRESHOLD = float(os.getenv("SUCCESS_RATE_THRESHOLD", "0.9"))

# Database-specific configurations
MYSQL_SHARED_INSTANCE_CONFIG = {
    "batch_size": 500,
    "max_connections": 10,
    "timeout": 30,
}

MONGODB_ATLAS_FREE_TIER_CONFIG = {
    "batch_size": 100,
    "max_connections": 5,
    "timeout": 60,
}

# OpenTelemetry resource attributes
OTEL_RESOURCE_ATTRIBUTES = os.getenv(
    "OTEL_RESOURCE_ATTRIBUTES", "service.name=binance-data-extractor"
)

# Health check settings
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))
HEALTH_CHECK_TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "5"))
HEALTH_CHECK_PORT = int(os.getenv("HEALTH_CHECK_PORT", "8080"))

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # json or text

# OpenTelemetry settings
OTEL_SERVICE_NAME = "binance-data-extractor"
OTEL_SERVICE_NAME_KLINES = "binance-data-extractor-klines"
OTEL_SERVICE_NAME_FUNDING = "binance-data-extractor-funding"
OTEL_SERVICE_NAME_TRADES = "binance-data-extractor-trades"
OTEL_SERVICE_VERSION = os.getenv("OTEL_SERVICE_VERSION", "1.0.0")
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
OTEL_EXPORTER_OTLP_HEADERS = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
OTEL_METRICS_EXPORTER = os.getenv("OTEL_METRICS_EXPORTER", "otlp")
OTEL_TRACES_EXPORTER = os.getenv("OTEL_TRACES_EXPORTER", "otlp")
OTEL_LOGS_EXPORTER = os.getenv("OTEL_LOGS_EXPORTER", "otlp")

# Environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

# Graceful shutdown settings
GRACEFUL_SHUTDOWN_TIMEOUT = int(os.getenv("GRACEFUL_SHUTDOWN_TIMEOUT", "30"))

# Error handling
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF_SECONDS = float(os.getenv("RETRY_BACKOFF_SECONDS", "1.0"))
RETRY_BACKOFF_MULTIPLIER = float(os.getenv("RETRY_BACKOFF_MULTIPLIER", "2.0"))

# Performance monitoring
METRICS_INTERVAL = int(os.getenv("METRICS_INTERVAL", "60"))
PERFORMANCE_ALERT_THRESHOLD = float(
    os.getenv("PERFORMANCE_ALERT_THRESHOLD", "1000")
)  # ms
