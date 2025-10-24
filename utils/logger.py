"""
Logging utilities for the Binance data extractor.

Provides structured logging with JSON format and OpenTelemetry integration.
"""

import logging
import sys
from datetime import datetime
from typing import Optional

import structlog
from structlog.stdlib import LoggerFactory

import constants


def setup_logging(
    level: str | None = None,
    format_type: str | None = None,
) -> structlog.BoundLogger:
    """
    Set up structured logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Log format type ("json" or "text")

    Returns:
        Configured structlog logger instance
    """
    level = level or constants.LOG_LEVEL
    format_type = format_type or constants.LOG_FORMAT

    # Set up standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # Configure structlog processors based on format type
    if format_type.lower() == "json":
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    else:
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.dev.ConsoleRenderer(),
            ],
            context_class=dict,
            logger_factory=LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

    # Configure third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    # Create logger with service context
    logger = structlog.get_logger(constants.OTEL_SERVICE_NAME)
    
    # Add service metadata
    logger = logger.bind(
        service_name=constants.OTEL_SERVICE_NAME,
        service_version=constants.OTEL_SERVICE_VERSION,
        environment=getattr(constants, "ENVIRONMENT", "production"),
    )

    return logger


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """
    Get a logger instance.

    Args:
        name: Logger name (optional)

    Returns:
        Configured structlog logger
    """
    if name:
        return structlog.get_logger(name)
    else:
        return structlog.get_logger(constants.OTEL_SERVICE_NAME)


def log_extraction_start(
    log: structlog.BoundLogger,
    extractor_type: str,
    symbols: list,
    period: str,
    start_date: str,
    backfill: bool = False,
):
    """Log extraction start with structured data."""
    log.info(
        "Starting data extraction",
        event="extraction_start",
        extractor_type=extractor_type,
        symbols=symbols,
        period=period,
        start_date=start_date,
        backfill=backfill,
        extraction_phase="start",
    )


def log_extraction_progress(
    log: structlog.BoundLogger,
    symbol: str,
    records_processed: int,
    total_records: int,
    current_timestamp: datetime | None = None,
):
    """Log extraction progress."""
    progress_pct = (records_processed / total_records * 100) if total_records > 0 else 0

    log.info(
        "Processing extraction",
        event="extraction_progress",
        symbol=symbol,
        records_processed=records_processed,
        total_records=total_records,
        progress_percent=round(progress_pct, 2),
        current_timestamp=current_timestamp.isoformat() if current_timestamp else None,
        extraction_phase="progress",
    )


def log_extraction_completion(
    log: structlog.BoundLogger,
    extractor_type: str,
    total_records: int,
    duration_seconds: float,
    gaps_found: int = 0,
    errors: list[str] | None = None,
):
    """Log extraction completion with summary."""
    log.info(
        "Extraction completed",
        event="extraction_complete",
        extractor_type=extractor_type,
        total_records=total_records,
        duration_seconds=round(duration_seconds, 2),
        gaps_found=gaps_found,
        errors_count=len(errors) if errors else 0,
        errors=errors or [],
        extraction_phase="complete",
    )


def log_gap_detection(log: structlog.BoundLogger, symbol: str, gaps: list, collection: str):
    """Log gap detection results."""
    log.warning(
        "Data gaps detected",
        event="gaps_detected",
        symbol=symbol,
        collection=collection,
        gaps_count=len(gaps),
        gaps=[
            {"start": gap[0].isoformat(), "end": gap[1].isoformat()} for gap in gaps
        ],
        extraction_phase="gap_detection",
    )


def log_database_operation(
    db_logger: structlog.BoundLogger,
    operation: str,
    collection: str,
    records_count: int,
    duration_seconds: float,
    success: bool = True,
):
    """Log database operations."""
    if success:
        db_logger.info(
            "Database operation completed",
            event="database_operation",
            operation=operation,
            collection=collection,
            records_count=records_count,
            duration_seconds=round(duration_seconds, 3),
            success=success,
            extraction_phase="database",
        )
    else:
        db_logger.error(
            "Database operation failed",
            event="database_operation_error",
            operation=operation,
            collection=collection,
            records_count=records_count,
            duration_seconds=round(duration_seconds, 3),
            success=success,
            extraction_phase="database",
        )


# Module-level logger for this file
logger = get_logger(__name__)
