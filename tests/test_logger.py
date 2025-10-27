"""Tests for utils/logger.py logging functions."""

from datetime import datetime
from unittest.mock import MagicMock, call

import pytest
import structlog

from utils.logger import (
    log_database_operation,
    log_extraction_completion,
    log_extraction_progress,
    log_extraction_start,
    log_gap_detection,
)


@pytest.fixture
def mock_logger():
    """Create a mock structlog BoundLogger."""
    logger = MagicMock()
    logger.info = MagicMock()
    return logger


class TestLogExtractionStart:
    """Tests for log_extraction_start function."""

    def test_log_extraction_start_basic(self, mock_logger):
        """Test basic extraction start logging."""
        log_extraction_start(
            log=mock_logger,
            extractor_type="klines_production",
            symbols=["BTCUSDT", "ETHUSDT"],
            period="1h",
            start_date="2024-01-01",
            backfill=False,
        )

        # Verify log.info was called with correct arguments
        mock_logger.info.assert_called_once()
        args, kwargs = mock_logger.info.call_args

        # First positional argument should be the event message
        assert args[0] == "Extraction started"

        # Verify keyword arguments
        assert kwargs["extractor_type"] == "klines_production"
        assert kwargs["symbols"] == ["BTCUSDT", "ETHUSDT"]
        assert kwargs["period"] == "1h"
        assert kwargs["start_date"] == "2024-01-01"
        assert kwargs["backfill"] is False
        assert kwargs["extraction_phase"] == "start"

    def test_log_extraction_start_with_backfill(self, mock_logger):
        """Test extraction start logging with backfill enabled."""
        log_extraction_start(
            log=mock_logger,
            extractor_type="klines_gap_filler",
            symbols=["BTCUSDT"],
            period="5m",
            start_date="2024-01-15",
            backfill=True,
        )

        mock_logger.info.assert_called_once()
        _, kwargs = mock_logger.info.call_args
        assert kwargs["backfill"] is True
        assert kwargs["extractor_type"] == "klines_gap_filler"

    def test_log_extraction_start_no_duplicate_event(self, mock_logger):
        """Test that 'event' is not passed as both positional and keyword argument."""
        log_extraction_start(
            log=mock_logger,
            extractor_type="test",
            symbols=["TEST"],
            period="1m",
            start_date="2024-01-01",
        )

        # Ensure 'event' is not in kwargs (only as positional)
        _, kwargs = mock_logger.info.call_args
        assert "event" not in kwargs


class TestLogExtractionProgress:
    """Tests for log_extraction_progress function."""

    def test_log_extraction_progress_basic(self, mock_logger):
        """Test basic extraction progress logging."""
        log_extraction_progress(
            log=mock_logger,
            symbol="BTCUSDT",
            records_processed=500,
            total_records=1000,
            current_timestamp=None,
        )

        mock_logger.info.assert_called_once()
        args, kwargs = mock_logger.info.call_args

        # First positional argument should be the event message
        assert args[0] == "Processing extraction"

        # Verify keyword arguments
        assert kwargs["symbol"] == "BTCUSDT"
        assert kwargs["records_processed"] == 500
        assert kwargs["total_records"] == 1000
        assert kwargs["progress_percent"] == 50.0
        assert kwargs["current_timestamp"] is None
        assert kwargs["extraction_phase"] == "progress"

    def test_log_extraction_progress_with_timestamp(self, mock_logger):
        """Test extraction progress logging with timestamp."""
        timestamp = datetime(2024, 1, 15, 12, 30, 0)
        log_extraction_progress(
            log=mock_logger,
            symbol="ETHUSDT",
            records_processed=750,
            total_records=1000,
            current_timestamp=timestamp,
        )

        _, kwargs = mock_logger.info.call_args
        assert kwargs["current_timestamp"] == "2024-01-15T12:30:00"
        assert kwargs["progress_percent"] == 75.0

    def test_log_extraction_progress_zero_total(self, mock_logger):
        """Test extraction progress with zero total records (edge case)."""
        log_extraction_progress(
            log=mock_logger,
            symbol="TESTUSDT",
            records_processed=0,
            total_records=0,
        )

        _, kwargs = mock_logger.info.call_args
        assert kwargs["progress_percent"] == 0

    def test_log_extraction_progress_no_duplicate_event(self, mock_logger):
        """Test that 'event' is not passed as both positional and keyword argument."""
        log_extraction_progress(
            log=mock_logger,
            symbol="BTCUSDT",
            records_processed=100,
            total_records=200,
        )

        # Ensure 'event' is not in kwargs (only as positional)
        _, kwargs = mock_logger.info.call_args
        assert "event" not in kwargs


class TestLogExtractionCompletion:
    """Tests for log_extraction_completion function."""

    def test_log_extraction_completion_basic(self, mock_logger):
        """Test basic extraction completion logging."""
        log_extraction_completion(
            log=mock_logger,
            extractor_type="klines_production",
            total_records=5000,
            duration_seconds=123.456,
            gaps_found=0,
            errors=None,
        )

        mock_logger.info.assert_called_once()
        args, kwargs = mock_logger.info.call_args

        # First positional argument should be the event message
        assert args[0] == "Extraction completed"

        # Verify keyword arguments
        assert kwargs["extractor_type"] == "klines_production"
        assert kwargs["total_records"] == 5000
        assert kwargs["duration_seconds"] == 123.46  # Rounded to 2 decimals
        assert kwargs["gaps_found"] == 0
        assert kwargs["errors_count"] == 0
        assert kwargs["errors"] == []
        assert kwargs["extraction_phase"] == "complete"

    def test_log_extraction_completion_with_gaps(self, mock_logger):
        """Test extraction completion logging with gaps found."""
        log_extraction_completion(
            log=mock_logger,
            extractor_type="klines_gap_filler",
            total_records=1200,
            duration_seconds=45.67,
            gaps_found=5,
        )

        _, kwargs = mock_logger.info.call_args
        assert kwargs["gaps_found"] == 5

    def test_log_extraction_completion_with_errors(self, mock_logger):
        """Test extraction completion logging with errors."""
        errors = [
            "Failed to fetch BTCUSDT: timeout",
            "Failed to fetch ETHUSDT: connection reset",
            "Failed to fetch ADAUSDT: rate limit",
        ]
        log_extraction_completion(
            log=mock_logger,
            extractor_type="klines_production",
            total_records=2000,
            duration_seconds=200.0,
            gaps_found=2,
            errors=errors,
        )

        _, kwargs = mock_logger.info.call_args
        assert kwargs["errors_count"] == 3
        assert kwargs["errors"] == errors

    def test_log_extraction_completion_no_duplicate_event(self, mock_logger):
        """Test that 'event' is not passed as both positional and keyword argument.

        This is the critical test for the bug fix in issue #153.
        The TypeError occurred because 'event' was passed both as:
        - First positional argument: "Extraction completed"
        - Keyword argument: event="extraction_complete"

        This test ensures we only use the positional argument.
        """
        log_extraction_completion(
            log=mock_logger,
            extractor_type="test",
            total_records=100,
            duration_seconds=10.0,
        )

        # Ensure 'event' is not in kwargs (only as positional)
        _, kwargs = mock_logger.info.call_args
        assert "event" not in kwargs

        # Verify the positional argument is correct
        args, _ = mock_logger.info.call_args
        assert args[0] == "Extraction completed"

    def test_log_extraction_completion_duration_rounding(self, mock_logger):
        """Test that duration is properly rounded to 2 decimal places."""
        log_extraction_completion(
            log=mock_logger,
            extractor_type="test",
            total_records=100,
            duration_seconds=123.456789,
        )

        _, kwargs = mock_logger.info.call_args
        assert kwargs["duration_seconds"] == 123.46

    def test_log_extraction_completion_empty_errors_list(self, mock_logger):
        """Test extraction completion with empty errors list."""
        log_extraction_completion(
            log=mock_logger,
            extractor_type="test",
            total_records=100,
            duration_seconds=10.0,
            errors=[],
        )

        _, kwargs = mock_logger.info.call_args
        assert kwargs["errors_count"] == 0
        assert kwargs["errors"] == []


class TestLoggerIntegration:
    """Integration tests to ensure logger functions work with real structlog."""

    def test_real_structlog_logger(self):
        """Test that the functions work with a real structlog logger."""
        # Configure a simple structlog logger for testing
        structlog.configure(
            processors=[
                structlog.processors.add_log_level,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.BoundLogger,
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,
        )

        logger = structlog.get_logger()

        # These should not raise TypeError about duplicate 'event' argument
        try:
            log_extraction_start(
                log=logger,
                extractor_type="test",
                symbols=["TEST"],
                period="1h",
                start_date="2024-01-01",
            )

            log_extraction_progress(
                log=logger,
                symbol="TEST",
                records_processed=50,
                total_records=100,
            )

            log_extraction_completion(
                log=logger,
                extractor_type="test",
                total_records=100,
                duration_seconds=10.5,
            )
        except TypeError as e:
            if "multiple values for argument 'event'" in str(e):
                pytest.fail(f"Duplicate 'event' argument error: {e}")
            raise


class TestLogGapDetection:
    """Tests for log_gap_detection function."""

    def test_log_gap_detection_basic(self, mock_logger):
        """Test basic gap detection logging."""
        mock_logger.warning = MagicMock()
        
        gaps = [
            (datetime(2024, 1, 1, 10, 0), datetime(2024, 1, 1, 11, 0)),
            (datetime(2024, 1, 1, 15, 0), datetime(2024, 1, 1, 16, 0)),
        ]
        
        log_gap_detection(
            log=mock_logger,
            symbol="BTCUSDT",
            gaps=gaps,
            collection="klines_1h",
        )

        mock_logger.warning.assert_called_once()
        args, kwargs = mock_logger.warning.call_args

        assert args[0] == "Data gaps detected"
        assert kwargs["symbol"] == "BTCUSDT"
        assert kwargs["collection"] == "klines_1h"
        assert kwargs["gaps_count"] == 2
        assert "event" not in kwargs  # No duplicate event argument


class TestLogDatabaseOperation:
    """Tests for log_database_operation function."""

    def test_log_database_operation_success(self, mock_logger):
        """Test successful database operation logging."""
        mock_logger.info = MagicMock()
        
        log_database_operation(
            db_logger=mock_logger,
            operation="write",
            collection="klines_1h",
            records_count=1000,
            duration_seconds=2.5,
            success=True,
        )

        mock_logger.info.assert_called_once()
        args, kwargs = mock_logger.info.call_args

        assert args[0] == "Database operation completed"
        assert kwargs["operation"] == "write"
        assert kwargs["collection"] == "klines_1h"
        assert kwargs["records_count"] == 1000
        assert kwargs["duration_seconds"] == 2.5
        assert kwargs["success"] is True
        assert "event" not in kwargs  # No duplicate event argument

    def test_log_database_operation_failure(self, mock_logger):
        """Test failed database operation logging."""
        mock_logger.error = MagicMock()
        
        log_database_operation(
            db_logger=mock_logger,
            operation="write",
            collection="klines_1h",
            records_count=500,
            duration_seconds=1.234,
            success=False,
        )

        mock_logger.error.assert_called_once()
        args, kwargs = mock_logger.error.call_args

        assert args[0] == "Database operation failed"
        assert kwargs["operation"] == "write"
        assert kwargs["success"] is False
        assert kwargs["duration_seconds"] == 1.234  # Rounded to 3 decimals
        assert "event" not in kwargs  # No duplicate event argument
