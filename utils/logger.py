"""
Logging utilities for the Binance data extractor.

Provides structured logging with JSON format and OpenTelemetry integration.
"""

import json
import logging
import sys
from datetime import datetime
from typing import List, Optional

import constants

# Try to import OpenTelemetry components
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "exc_info",
                "exc_text",
                "stack_info",
            ]:
                log_entry[key] = value

        # Add service information
        log_entry["service"] = {
            "name": constants.OTEL_SERVICE_NAME,
            "version": constants.OTEL_SERVICE_VERSION,
        }

        # Add trace context if available
        if OTEL_AVAILABLE:
            span = trace.get_current_span()
            if span:
                span_context = span.get_span_context()
                log_entry["trace_id"] = format(span_context.trace_id, "032x")
                log_entry["span_id"] = format(span_context.span_id, "016x")

        return json.dumps(log_entry, default=str)


def setup_logging(level: Optional[str] = None, format_type: Optional[str] = None, enable_otel: bool = True) -> logging.Logger:
    """
    Set up logging configuration for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Log format ('json' or 'text')
        enable_otel: Whether to enable OpenTelemetry integration

    Returns:
        Configured logger instance
    """
    level = level or constants.LOG_LEVEL
    format_type = format_type or constants.LOG_FORMAT

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))

    # Set formatter
    if format_type.lower() == "json":
        formatter: logging.Formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Set up OpenTelemetry if available and enabled
    if OTEL_AVAILABLE and enable_otel and constants.OTEL_EXPORTER_OTLP_ENDPOINT:
        setup_otel_tracing()
        LoggingInstrumentor().instrument(set_logging_format=True)

    # Configure third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    local_logger = logging.getLogger(__name__)
    local_logger.info("Logging configured: level=%s, format=%s, otel=%s", level, format_type, enable_otel and OTEL_AVAILABLE)

    return local_logger


def setup_otel_tracing():
    """Set up OpenTelemetry tracing."""
    if not OTEL_AVAILABLE:
        return

    # Create resource
    resource = Resource.create(
        {
            "service.name": constants.OTEL_SERVICE_NAME,
            "service.version": constants.OTEL_SERVICE_VERSION,
        }
    )

    # Set up tracer provider
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)

    # Set up OTLP exporter
    if constants.OTEL_EXPORTER_OTLP_ENDPOINT:
        otlp_exporter = OTLPSpanExporter(
            endpoint=constants.OTEL_EXPORTER_OTLP_ENDPOINT,
            insecure=True,  # Configure based on your setup
        )
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_extraction_start(
    log: logging.Logger,
    extractor_type: str,
    symbols: list,
    period: str,
    start_date: str,
    backfill: bool = False,
):
    """Log extraction start with structured data."""
    log.info(
        "Starting data extraction",
        extra={
            "extractor_type": extractor_type,
            "symbols": symbols,
            "period": period,
            "start_date": start_date,
            "backfill": backfill,
            "extraction_phase": "start",
        },
    )


def log_extraction_progress(
    log: logging.Logger,
    symbol: str,
    records_processed: int,
    total_records: int,
    current_timestamp: Optional[datetime] = None,
):
    """Log extraction progress."""
    progress_pct = (records_processed / total_records * 100) if total_records > 0 else 0

    extra_data = {
        "symbol": symbol,
        "records_processed": records_processed,
        "total_records": total_records,
        "progress_percent": round(progress_pct, 2),
        "extraction_phase": "progress",
    }

    if current_timestamp:
        extra_data["current_timestamp"] = current_timestamp.isoformat()

    log.info(
        f"Processing {symbol}: {records_processed}/{total_records} records",
        extra=extra_data,
    )


def log_extraction_completion(
    log: logging.Logger,
    extractor_type: str,
    total_records: int,
    duration_seconds: float,
    gaps_found: int = 0,
    errors: Optional[List[str]] = None,
):
    """Log extraction completion with summary."""
    log.info(
        "Extraction completed",
        extra={
            "extractor_type": extractor_type,
            "total_records": total_records,
            "duration_seconds": round(duration_seconds, 2),
            "gaps_found": gaps_found,
            "errors_count": len(errors) if errors else 0,
            "errors": errors or [],
            "extraction_phase": "complete",
        },
    )


def log_gap_detection(log: logging.Logger, symbol: str, gaps: list, collection: str):
    """Log gap detection results."""
    log.warning(
        f"Data gaps detected for {symbol}",
        extra={
            "symbol": symbol,
            "collection": collection,
            "gaps_count": len(gaps),
            "gaps": [{"start": gap[0].isoformat(), "end": gap[1].isoformat()} for gap in gaps],
            "extraction_phase": "gap_detection",
        },
    )


def log_database_operation(
    db_logger: logging.Logger,
    operation: str,
    collection: str,
    records_count: int,
    duration_seconds: float,
    success: bool = True,
):
    """Log database operations."""
    log_level = logging.INFO if success else logging.ERROR

    db_logger.log(
        log_level,
        f"Database {operation}: {records_count} records in {collection}",
        extra={
            "operation": operation,
            "collection": collection,
            "records_count": records_count,
            "duration_seconds": round(duration_seconds, 3),
            "success": success,
            "extraction_phase": "database",
        },
    )


# Module-level logger for this file
logger = get_logger(__name__)
