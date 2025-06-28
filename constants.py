"""
Configuration constants for the Binance Futures data extractor.
This module contains all configurable parameters including API credentials,
database URIs, and extraction settings.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Binance API settings
BINANCE_API_URL = "https://fapi.binance.com"
API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# Default extraction parameters
DEFAULT_PERIOD = "15m"
DEFAULT_START_DATE = "2021-01-01T00:00:00Z"
BACKFILL = True
MAX_RETRIES = 5
RETRY_BACKOFF_SECONDS = 2
RETRY_BACKOFF_MULTIPLIER = 2.0

# Symbols to extract (Binance Futures perpetual contracts)
DEFAULT_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "ADAUSDT",
    "DOTUSDT",
    "LINKUSDT",
    "LTCUSDT",
    "BCHUSDT",
    "XLMUSDT",
    "XRPUSDT"
]

# Time intervals supported by Binance
SUPPORTED_INTERVALS = [
    "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"
]

# Database URIs (pluggable)
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/binance")
MYSQL_URI = os.getenv("MYSQL_URI", "mysql+pymysql://user:pass@localhost:3306/binance")
POSTGRESQL_URI = os.getenv("POSTGRESQL_URI", "postgresql://user:pass@localhost:5432/binance")

# Database settings
DB_ADAPTER = os.getenv("DB_ADAPTER", "mongodb")  # mongodb, mysql, postgresql
DB_BATCH_SIZE = int(os.getenv("DB_BATCH_SIZE", "1000"))
DB_CONNECTION_TIMEOUT = int(os.getenv("DB_CONNECTION_TIMEOUT", "30"))

# API rate limiting
API_RATE_LIMIT_PER_MINUTE = 1200  # Binance limit
API_WEIGHT_LIMIT_PER_MINUTE = 2400  # Binance limit
REQUEST_DELAY_SECONDS = 0.1  # Delay between requests

# Gap detection settings
MAX_ALLOWED_GAP_MINUTES = 60  # Maximum gap before triggering backfill
GAP_CHECK_ENABLED = True

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "json"  # json or text

# OpenTelemetry settings
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "binance-extractor")
OTEL_SERVICE_VERSION = os.getenv("OTEL_SERVICE_VERSION", "1.0.0")
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")

# Kubernetes job settings
K8S_NAMESPACE = os.getenv("K8S_NAMESPACE", "default")
K8S_JOB_NAME_PREFIX = "binance-extractor"

# Data validation settings
VALIDATE_DATA_INTEGRITY = True
ALLOW_DUPLICATE_TIMESTAMPS = False

# Timezone settings
TIMEZONE = "UTC"
