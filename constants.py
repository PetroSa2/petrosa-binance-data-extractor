"""
Configuration constants for the Petrosa Socket Client.
This module contains all configurable parameters including WebSocket URLs,
NATS configuration, and streaming settings.
"""

import os

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Binance WebSocket settings
BINANCE_WS_URL = os.getenv("BINANCE_WS_URL", "wss://stream.binance.com:9443")
BINANCE_FUTURES_WS_URL = os.getenv(
    "BINANCE_FUTURES_WS_URL", "wss://fstream.binance.com"
)

# Default streams to subscribe to
DEFAULT_STREAMS = [
    "btcusdt@trade",
    "btcusdt@ticker",
    "btcusdt@depth20@100ms",
    "ethusdt@trade",
    "ethusdt@ticker",
    "ethusdt@depth20@100ms",
]


# Parse streams from environment variable
def get_streams() -> list[str]:
    """Get streams from environment variable or use defaults."""
    streams_env = os.getenv("BINANCE_STREAMS")
    if streams_env:
        return [s.strip() for s in streams_env.split(",")]
    return DEFAULT_STREAMS


# NATS configuration
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
NATS_TOPIC = os.getenv("NATS_TOPIC", "binance.websocket.data")
NATS_CLIENT_NAME = os.getenv("NATS_CLIENT_NAME", "petrosa-socket-client")

# WebSocket connection settings
WEBSOCKET_RECONNECT_DELAY = int(os.getenv("WEBSOCKET_RECONNECT_DELAY", "5"))
WEBSOCKET_MAX_RECONNECT_ATTEMPTS = int(
    os.getenv("WEBSOCKET_MAX_RECONNECT_ATTEMPTS", "10")
)
WEBSOCKET_PING_INTERVAL = int(os.getenv("WEBSOCKET_PING_INTERVAL", "30"))
WEBSOCKET_PING_TIMEOUT = int(os.getenv("WEBSOCKET_PING_TIMEOUT", "10"))
WEBSOCKET_CLOSE_TIMEOUT = int(os.getenv("WEBSOCKET_CLOSE_TIMEOUT", "10"))

# Message processing settings
MESSAGE_TTL_SECONDS = int(os.getenv("MESSAGE_TTL_SECONDS", "60"))
MAX_MESSAGE_SIZE = int(os.getenv("MAX_MESSAGE_SIZE", "1048576"))  # 1MB
MESSAGE_BATCH_SIZE = int(os.getenv("MESSAGE_BATCH_SIZE", "100"))
MESSAGE_BATCH_TIMEOUT = float(os.getenv("MESSAGE_BATCH_TIMEOUT", "1.0"))

# Resource limits
MAX_MEMORY_MB = int(os.getenv("MAX_MEMORY_MB", "500"))
MAX_CONCURRENT_CONNECTIONS = int(os.getenv("MAX_CONCURRENT_CONNECTIONS", "10"))
MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", "1000"))

# Circuit breaker settings
CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(
    os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")
)
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = int(
    os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "60")
)
CIRCUIT_BREAKER_EXPECTED_EXCEPTION = Exception

# Health check settings
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))
HEALTH_CHECK_TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "5"))
HEALTH_CHECK_PORT = int(os.getenv("HEALTH_CHECK_PORT", "8080"))

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # json or text

# OpenTelemetry settings
OTEL_SERVICE_NAME = "socket-client"
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
ENABLE_METRICS = os.getenv("ENABLE_METRICS", "true").lower() in ("true", "1", "yes")
METRICS_INTERVAL = int(os.getenv("METRICS_INTERVAL", "60"))

# Message validation
ENABLE_MESSAGE_VALIDATION = os.getenv("ENABLE_MESSAGE_VALIDATION", "true").lower() in (
    "true",
    "1",
    "yes",
)
REQUIRED_MESSAGE_FIELDS = ["stream", "data", "timestamp"]

# Backpressure handling
ENABLE_BACKPRESSURE = os.getenv("ENABLE_BACKPRESSURE", "true").lower() in (
    "true",
    "1",
    "yes",
)
BACKPRESSURE_THRESHOLD = int(os.getenv("BACKPRESSURE_THRESHOLD", "100"))
