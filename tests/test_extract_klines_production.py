#!/usr/bin/env python3
"""
Tests for production klines extraction.
"""

import os
import sys
import threading
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import constants
from jobs.extract_klines_production import (
    ProductionKlinesExtractor,
    _main_impl,
    main,
    parse_arguments,
    retry_with_backoff,
)
from models.kline import KlineModel


class TestRetryWithBackoff:
    """Test retry_with_backoff function."""

    @patch("jobs.extract_klines_production.time.sleep")
    def test_retry_success_on_first_attempt(self, mock_sleep):
        """Test successful execution on first attempt."""
        mock_func = Mock(return_value="success")
        mock_logger = Mock()

        result = retry_with_backoff(mock_func, logger=mock_logger)

        assert result == "success"
        mock_func.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("jobs.extract_klines_production.time.sleep")
    def test_retry_success_after_failures(self, mock_sleep):
        """Test successful execution after some failures."""
        mock_func = Mock(
            side_effect=[Exception("Lost connection to MySQL server"), Exception("MySQL server has gone away"), "success"]
        )
        mock_logger = Mock()

        result = retry_with_backoff(mock_func, max_retries=2, logger=mock_logger)

        assert result == "success"
        assert mock_func.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("jobs.extract_klines_production.time.sleep")
    def test_retry_all_attempts_fail(self, mock_sleep):
        """Test all retry attempts fail."""
        mock_func = Mock(side_effect=Exception("Lost connection to MySQL server"))
        mock_logger = Mock()

        with pytest.raises(Exception) as exc_info:
            retry_with_backoff(mock_func, max_retries=2, logger=mock_logger)

        assert "Lost connection to MySQL server" in str(exc_info.value)
        assert mock_func.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("jobs.extract_klines_production.time.sleep")
    def test_retry_non_connection_error(self, mock_sleep):
        """Test non-connection errors are not retried."""
        mock_func = Mock(side_effect=ValueError("Invalid input"))
        mock_logger = Mock()

        with pytest.raises(ValueError) as exc_info:
            retry_with_backoff(mock_func, logger=mock_logger)

        assert "Invalid input" in str(exc_info.value)
        mock_func.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("jobs.extract_klines_production.time.sleep")
    def test_retry_exponential_backoff(self, mock_sleep):
        """Test exponential backoff timing."""
        mock_func = Mock(
            side_effect=[Exception("Lost connection to MySQL server"), Exception("MySQL server has gone away"), "success"]
        )
        mock_logger = Mock()

        retry_with_backoff(mock_func, max_retries=2, base_delay=1.0, logger=mock_logger)

        # Check that sleep was called with increasing delays in the expected range
        assert mock_sleep.call_count == 2
        first_delay = mock_sleep.call_args_list[0][0][0]
        second_delay = mock_sleep.call_args_list[1][0][0]
        # First delay: 1.0 + jitter (0.1-0.3)
        assert 1.1 <= first_delay <= 1.3
        # Second delay: 2.0 + jitter (0.2-0.6)
        assert 2.2 <= second_delay <= 2.6


class TestProductionKlinesExtractor:
    """Test ProductionKlinesExtractor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.symbols = ["BTCUSDT", "ETHUSDT"]
        self.period = "15m"
        self.db_adapter_name = "mysql"
        self.db_uri = "mysql://test:test@localhost/test"

        self.extractor = ProductionKlinesExtractor(
            symbols=self.symbols, period=self.period, db_adapter_name=self.db_adapter_name, db_uri=self.db_uri, max_workers=2
        )

    def test_initialization(self):
        """Test extractor initialization."""
        assert self.extractor.symbols == self.symbols
        assert self.extractor.period == self.period
        assert self.extractor.db_adapter_name == self.db_adapter_name
        assert self.extractor.db_uri == self.db_uri
        assert self.extractor.max_workers == 2
        assert self.extractor.lookback_hours == 24
        assert self.extractor.batch_size == 2000
        assert self.extractor.logger is not None
        assert isinstance(self.extractor._lock, type(threading.Lock()))
        assert self.extractor.stats == {
            "symbols_processed": 0,
            "symbols_failed": 0,
            "total_records_fetched": 0,
            "total_records_written": 0,
            "total_gaps_filled": 0,
            "errors": [],
        }

    def test_period_to_minutes(self):
        """Test period to minutes conversion."""
        assert self.extractor.period_to_minutes() == 15

        # Test different periods
        self.extractor.period = "1h"
        assert self.extractor.period_to_minutes() == 60

        self.extractor.period = "1d"
        assert self.extractor.period_to_minutes() == 1440

        self.extractor.period = "unknown"
        assert self.extractor.period_to_minutes() == 15  # Default

    def test_get_collection_name(self):
        """Test collection name generation."""
        assert self.extractor.get_collection_name() == "klines_m15"

        self.extractor.period = "1h"
        assert self.extractor.get_collection_name() == "klines_h1"

        self.extractor.period = "1d"
        assert self.extractor.get_collection_name() == "klines_d1"

    @patch("jobs.extract_klines_production.get_adapter")
    def test_get_last_timestamp_for_symbol_with_data(self, mock_get_adapter):
        """Test getting last timestamp when data exists."""
        mock_adapter = Mock()
        mock_get_adapter.return_value = mock_adapter

        # Mock database response with data
        mock_record = {"close_time": datetime(2023, 1, 1, 12, 0, 0), "symbol": "BTCUSDT"}  # timezone-naive
        mock_adapter.query_latest.return_value = [mock_record]

        timestamp = self.extractor.get_last_timestamp_for_symbol(mock_adapter, "BTCUSDT")

        assert timestamp == datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_adapter.query_latest.assert_called_once_with("klines_m15", symbol="BTCUSDT", limit=1)

    @patch("jobs.extract_klines_production.get_adapter")
    def test_get_last_timestamp_for_symbol_no_data(self, mock_get_adapter):
        """Test getting last timestamp when no data exists."""
        mock_adapter = Mock()
        mock_get_adapter.return_value = mock_adapter

        # Mock database response with no data
        mock_adapter.query_latest.return_value = []

        with patch("jobs.extract_klines_production.constants") as mock_constants:
            mock_constants.DEFAULT_START_DATE = "2023-01-01T00:00:00Z"
            timestamp = self.extractor.get_last_timestamp_for_symbol(mock_adapter, "BTCUSDT")

        assert timestamp == datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    @patch("jobs.extract_klines_production.get_current_utc_time")
    def test_calculate_extraction_window(self, mock_current_time):
        """Test extraction window calculation."""
        # Mock current time
        current_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_current_time.return_value = current_time

        # Test with recent timestamp
        last_timestamp = datetime(2023, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        start_time, end_time = self.extractor.calculate_extraction_window(last_timestamp)

        # Should start 30 minutes before last timestamp
        expected_start = datetime(2023, 1, 1, 10, 30, 0, tzinfo=timezone.utc)
        # Should end 5 minutes before current time
        expected_end = datetime(2023, 1, 1, 11, 55, 0, tzinfo=timezone.utc)

        assert start_time == expected_start
        assert end_time == expected_end

    @patch("jobs.extract_klines_production.get_current_utc_time")
    def test_calculate_extraction_window_old_timestamp(self, mock_current_time):
        """Test extraction window with very old timestamp."""
        # Mock current time
        current_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_current_time.return_value = current_time

        # Test with very old timestamp (more than 1 day ago)
        old_timestamp = datetime(2022, 12, 30, 12, 0, 0, tzinfo=timezone.utc)
        start_time, end_time = self.extractor.calculate_extraction_window(old_timestamp)

        # Should limit catch-up to 1 day
        expected_start = datetime(2022, 12, 31, 12, 0, 0, tzinfo=timezone.utc)
        expected_end = datetime(2023, 1, 1, 11, 55, 0, tzinfo=timezone.utc)

        assert start_time == expected_start
        assert end_time == expected_end

    @patch("jobs.extract_klines_production.get_current_utc_time")
    def test_calculate_extraction_window_timezone_naive(self, mock_current_time):
        """Test extraction window with timezone-naive timestamp."""
        # Mock current time
        current_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_current_time.return_value = current_time

        # Test with timezone-naive timestamp
        naive_timestamp = datetime(2023, 1, 1, 11, 0, 0)  # No timezone info
        start_time, end_time = self.extractor.calculate_extraction_window(naive_timestamp)

        # Should convert to timezone-aware
        expected_start = datetime(2023, 1, 1, 10, 30, 0, tzinfo=timezone.utc)
        expected_end = datetime(2023, 1, 1, 11, 55, 0, tzinfo=timezone.utc)

        assert start_time == expected_start
        assert end_time == expected_end

    @patch("jobs.extract_klines_production.get_adapter")
    @patch("jobs.extract_klines_production.KlinesFetcher")
    def test_extract_symbol_data_success(self, mock_klines_fetcher_class, mock_get_adapter):
        """Test successful symbol data extraction."""
        # Mock dependencies
        mock_adapter = Mock()
        mock_get_adapter.return_value = mock_adapter

        mock_fetcher = Mock()
        mock_klines_fetcher_class.return_value = mock_fetcher

        mock_binance_client = Mock()

        # Mock database operations
        mock_adapter.query_latest.return_value = [{"close_time": datetime(2023, 1, 1, 11, 0, 0, tzinfo=timezone.utc)}]

        # Mock klines data
        mock_klines = [
            KlineModel(
                symbol="BTCUSDT",
                interval="15m",
                timestamp=datetime(2023, 1, 1, 11, 15, 0, tzinfo=timezone.utc),
                open_time=datetime(2023, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
                close_time=datetime(2023, 1, 1, 11, 15, 0, tzinfo=timezone.utc),
                open_price=Decimal("50000"),
                high_price=Decimal("50100"),
                low_price=Decimal("49900"),
                close_price=Decimal("50050"),
                volume=Decimal("100.5"),
                quote_asset_volume=Decimal("5025000"),
                number_of_trades=1500,
                taker_buy_base_asset_volume=Decimal("50.25"),
                taker_buy_quote_asset_volume=Decimal("2512500"),
                price_change=Decimal("50"),
                price_change_percent=Decimal("0.1"),
            )
        ]
        mock_fetcher.fetch_klines.return_value = mock_klines

        # Mock database write
        mock_adapter.write.return_value = 1

        # Mock gap detection
        mock_adapter.find_gaps.return_value = []

        result = self.extractor.extract_symbol_data("BTCUSDT", mock_binance_client)

        assert result["success"] is True
        assert result["symbol"] == "BTCUSDT"
        assert result["records_fetched"] == 1
        assert result["records_written"] == 1
        assert result["gaps_filled"] == 0
        assert result["error"] is None
        assert result["duration"] > 0

    @patch("jobs.extract_klines_production.get_adapter")
    def test_extract_symbol_data_database_error(self, mock_get_adapter):
        """Test symbol data extraction with database error."""
        # Mock database error
        mock_adapter = Mock()
        mock_get_adapter.return_value = mock_adapter
        mock_adapter.connect.side_effect = Exception("Database connection failed")

        mock_binance_client = Mock()

        result = self.extractor.extract_symbol_data("BTCUSDT", mock_binance_client)

        assert result["success"] is False
        assert result["symbol"] == "BTCUSDT"
        assert "Database connection failed" in result["error"]

    @patch("jobs.extract_klines_production.get_adapter")
    @patch("jobs.extract_klines_production.KlinesFetcher")
    def test_extract_symbol_data_api_error(self, mock_klines_fetcher_class, mock_get_adapter):
        """Test symbol data extraction with API error."""
        # Mock dependencies
        mock_adapter = Mock()
        mock_get_adapter.return_value = mock_adapter

        mock_fetcher = Mock()
        mock_klines_fetcher_class.return_value = mock_fetcher

        mock_binance_client = Mock()

        # Mock database operations
        mock_adapter.query_latest.return_value = [{"close_time": datetime(2023, 1, 1, 11, 0, 0, tzinfo=timezone.utc)}]

        # Mock API error
        mock_fetcher.fetch_klines.side_effect = Exception("API rate limit exceeded")

        result = self.extractor.extract_symbol_data("BTCUSDT", mock_binance_client)

        assert result["success"] is False
        assert result["symbol"] == "BTCUSDT"
        assert "API rate limit exceeded" in result["error"]

    @patch("jobs.extract_klines_production.BinanceClient")
    @patch("jobs.extract_klines_production.ThreadPoolExecutor")
    def test_run_extraction_success(self, mock_executor_class, mock_binance_client_class):
        """Test successful extraction run."""
        # Mock ThreadPoolExecutor
        mock_executor = Mock()
        mock_executor_class.return_value.__enter__.return_value = mock_executor

        # Mock futures
        mock_future1 = Mock()
        mock_future2 = Mock()
        mock_executor.submit.side_effect = [mock_future1, mock_future2]

        # Mock results
        mock_future1.result.return_value = {
            "success": True,
            "symbol": "BTCUSDT",
            "records_fetched": 10,
            "records_written": 10,
            "gaps_filled": 0,
            "error": None,
            "duration": 1.0,
        }
        mock_future2.result.return_value = {
            "success": True,
            "symbol": "ETHUSDT",
            "records_fetched": 8,
            "records_written": 8,
            "gaps_filled": 0,
            "error": None,
            "duration": 0.8,
        }

        # Mock as_completed
        with patch("jobs.extract_klines_production.as_completed") as mock_as_completed:
            mock_as_completed.return_value = [mock_future1, mock_future2]

            result = self.extractor.run_extraction()

        assert result["success"] is True
        assert result["total_symbols"] == 2
        assert result["symbols_processed"] == 2
        assert result["symbols_failed"] == 0
        assert result["total_records_fetched"] == 18
        assert result["total_records_written"] == 18
        assert result["total_gaps_filled"] == 0
        assert result["duration_seconds"] > 0
        assert result["errors"] == []

    @patch("jobs.extract_klines_production.BinanceClient")
    @patch("jobs.extract_klines_production.ThreadPoolExecutor")
    def test_run_extraction_partial_failure(self, mock_executor_class, mock_binance_client_class):
        """Test extraction run with partial failures."""
        # Mock ThreadPoolExecutor
        mock_executor = Mock()
        mock_executor_class.return_value.__enter__.return_value = mock_executor

        # Mock futures
        mock_future1 = Mock()
        mock_future2 = Mock()
        mock_executor.submit.side_effect = [mock_future1, mock_future2]

        # Mock results - one success, one failure
        mock_future1.result.return_value = {
            "success": True,
            "symbol": "BTCUSDT",
            "records_fetched": 10,
            "records_written": 10,
            "gaps_filled": 0,
            "error": None,
            "duration": 1.0,
        }
        mock_future2.result.return_value = {
            "success": False,
            "symbol": "ETHUSDT",
            "records_fetched": 0,
            "records_written": 0,
            "gaps_filled": 0,
            "error": "API error",
            "duration": 0.5,
        }

        # Mock as_completed
        with patch("jobs.extract_klines_production.as_completed") as mock_as_completed:
            mock_as_completed.return_value = [mock_future1, mock_future2]

            result = self.extractor.run_extraction()

        assert result["success"] is False
        assert result["total_symbols"] == 2
        assert result["symbols_processed"] == 1
        assert result["symbols_failed"] == 1
        assert result["total_records_fetched"] == 10
        assert result["total_records_written"] == 10
        assert result["total_gaps_filled"] == 0
        assert len(result["errors"]) == 1
        assert "ETHUSDT: API error" in result["errors"][0]


class TestParseArguments:
    """Test argument parsing."""

    def test_default_arguments(self):
        """Test default argument values."""
        with patch("sys.argv", ["extract_klines_production.py"]):
            args = parse_arguments()

            assert args.period == "15m"  # Default from constants
            assert args.symbols is None
            assert args.max_workers == 5
            assert args.lookback_hours == 24
            assert args.batch_size == 2000
            assert args.db_adapter == constants.DB_ADAPTER  # Use actual default from constants
            assert args.db_uri is None
            assert args.log_level == "INFO"
            assert args.dry_run is False

    def test_custom_arguments(self):
        """Test custom argument values."""
        with patch(
            "sys.argv",
            [
                "extract_klines_production.py",
                "--period",
                "1h",
                "--symbols",
                "BTCUSDT,ETHUSDT",
                "--max-workers",
                "10",
                "--db-adapter",
                "mongodb",
                "--db-uri",
                "mongodb://localhost:27017/test",
                "--log-level",
                "DEBUG",
                "--dry-run",
            ],
        ):
            args = parse_arguments()

            assert args.period == "1h"
            assert args.symbols == "BTCUSDT,ETHUSDT"
            assert args.max_workers == 10
            assert args.db_adapter == "mongodb"
            assert args.db_uri == "mongodb://localhost:27017/test"
            assert args.log_level == "DEBUG"
            assert args.dry_run is True


class TestMainFunction:
    """Test main function and related functions."""

    @patch("jobs.extract_klines_production.setup_logging")
    @patch("jobs.extract_klines_production.get_logger")
    @patch("jobs.extract_klines_production.log_extraction_start")
    @patch("jobs.extract_klines_production.log_extraction_completion")
    @patch("jobs.extract_klines_production.ProductionKlinesExtractor")
    @patch("jobs.extract_klines_production.constants")
    @patch("jobs.extract_klines_production.parse_arguments")
    def test_main_impl_success(
        self,
        mock_parse_args,
        mock_constants,
        mock_extractor_class,
        mock_log_completion,
        mock_log_start,
        mock_get_logger,
        mock_setup_logging,
    ):
        """Test successful main implementation."""
        # Mock arguments
        mock_args = Mock()
        mock_args.period = "15m"
        mock_args.symbols = None
        mock_args.max_workers = 5
        mock_args.lookback_hours = 24
        mock_args.batch_size = 2000
        mock_args.db_adapter = "mysql"
        mock_args.db_uri = None
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_parse_args.return_value = mock_args

        # Mock constants
        mock_constants.DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT"]
        mock_constants.MYSQL_URI = "mysql://test:test@localhost/test"

        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Mock extractor
        mock_extractor = Mock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.run_extraction.return_value = {
            "success": True,
            "total_symbols": 2,
            "symbols_processed": 2,
            "symbols_failed": 0,
            "total_records_fetched": 20,
            "total_records_written": 20,
            "total_gaps_filled": 0,
            "duration_seconds": 5.0,
            "errors": [],
        }

        with patch("sys.exit") as mock_exit:
            _main_impl()

            # Verify successful execution
            mock_exit.assert_called_once_with(0)

    @patch("jobs.extract_klines_production.setup_logging")
    @patch("jobs.extract_klines_production.get_logger")
    @patch("jobs.extract_klines_production.ProductionKlinesExtractor")
    @patch("jobs.extract_klines_production.constants")
    @patch("jobs.extract_klines_production.parse_arguments")
    def test_main_impl_failure(
        self, mock_parse_args, mock_constants, mock_extractor_class, mock_get_logger, mock_setup_logging
    ):
        """Test main implementation with extraction failure."""
        # Mock arguments
        mock_args = Mock()
        mock_args.period = "15m"
        mock_args.symbols = None
        mock_args.max_workers = 5
        mock_args.lookback_hours = 24
        mock_args.batch_size = 2000
        mock_args.db_adapter = "mysql"
        mock_args.db_uri = None
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_parse_args.return_value = mock_args

        # Mock constants
        mock_constants.DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT"]
        mock_constants.MYSQL_URI = "mysql://test:test@localhost/test"

        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Mock extractor with failure
        mock_extractor = Mock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.run_extraction.return_value = {
            "success": False,
            "total_symbols": 2,
            "symbols_processed": 1,
            "symbols_failed": 1,
            "total_records_fetched": 10,
            "total_records_written": 10,
            "total_gaps_filled": 0,
            "duration_seconds": 5.0,
            "errors": ["ETHUSDT: API error"],
        }

        with patch("sys.exit") as mock_exit:
            _main_impl()

            # Verify failure exit code
            mock_exit.assert_called_once_with(1)

    @patch("jobs.extract_klines_production.setup_logging")
    @patch("jobs.extract_klines_production.get_logger")
    @patch("jobs.extract_klines_production.ProductionKlinesExtractor")
    @patch("jobs.extract_klines_production.constants")
    @patch("jobs.extract_klines_production.parse_arguments")
    def test_main_impl_keyboard_interrupt(
        self, mock_parse_args, mock_constants, mock_extractor_class, mock_get_logger, mock_setup_logging
    ):
        """Test main implementation with keyboard interrupt."""
        # Mock arguments
        mock_args = Mock()
        mock_args.period = "15m"
        mock_args.symbols = None
        mock_args.max_workers = 5
        mock_args.lookback_hours = 24
        mock_args.batch_size = 2000
        mock_args.db_adapter = "mysql"
        mock_args.db_uri = None
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_parse_args.return_value = mock_args

        # Mock constants
        mock_constants.DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT"]
        mock_constants.MYSQL_URI = "mysql://test:test@localhost/test"

        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Mock extractor to raise KeyboardInterrupt
        mock_extractor = Mock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.run_extraction.side_effect = KeyboardInterrupt()

        # Mock sys.exit to prevent actual exit
        with patch("sys.exit") as mock_exit:
            # The KeyboardInterrupt should be caught and sys.exit(130) should be called
            _main_impl()

            # Verify that sys.exit was called with the correct code
            mock_exit.assert_called_once_with(130)

    @patch("jobs.extract_klines_production.setup_logging")
    @patch("jobs.extract_klines_production.get_logger")
    @patch("jobs.extract_klines_production.ProductionKlinesExtractor")
    @patch("jobs.extract_klines_production.constants")
    @patch("jobs.extract_klines_production.parse_arguments")
    def test_main_impl_general_exception(
        self, mock_parse_args, mock_constants, mock_extractor_class, mock_get_logger, mock_setup_logging
    ):
        """Test main implementation with general exception."""
        # Mock arguments
        mock_args = Mock()
        mock_args.symbols = None
        mock_args.period = "15m"
        mock_args.max_workers = 5
        mock_args.lookback_hours = 24
        mock_args.batch_size = 2000
        mock_args.db_adapter = "mysql"
        mock_args.db_uri = None
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_parse_args.return_value = mock_args

        # Mock constants
        mock_constants.DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT"]
        mock_constants.MYSQL_URI = "mysql://test:test@localhost/test"

        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Mock extractor to raise Exception
        mock_extractor = Mock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.run_extraction.side_effect = Exception("Unexpected error")

        with patch("sys.exit") as mock_exit:
            _main_impl()

            # Verify error exit code
            mock_exit.assert_called_once_with(1)

    @patch("jobs.extract_klines_production._main_impl")
    def test_main_with_tracer(self, mock_main_impl):
        """Test main function with tracer available."""
        with patch("jobs.extract_klines_production.get_tracer") as mock_get_tracer:
            mock_tracer = Mock()
            mock_span = Mock()
            mock_span_context = Mock()
            mock_span_context.trace_id = 1234567890  # Must be int for format()
            mock_span.get_span_context.return_value = mock_span_context

            # Create a proper context manager mock
            mock_context_manager = Mock()
            mock_context_manager.__enter__ = Mock(return_value=mock_span)
            mock_context_manager.__exit__ = Mock(return_value=None)
            mock_tracer.start_as_current_span.return_value = mock_context_manager
            mock_get_tracer.return_value = mock_tracer

            main()

            mock_main_impl.assert_called_once()
            mock_get_tracer.assert_called_once_with("jobs.extract_klines_production")
            mock_tracer.start_as_current_span.assert_called_once_with("klines_extraction_main")

    @patch("jobs.extract_klines_production._main_impl")
    def test_main_without_tracer(self, mock_main_impl):
        """Test main function without tracer."""
        with patch("jobs.extract_klines_production.get_tracer", return_value=None):
            main()
            mock_main_impl.assert_called_once()


class TestTimezoneHandling:
    """Test timezone handling functionality."""

    def test_timezone_aware_comparison(self):
        """Test that timezone-aware and timezone-naive datetimes are handled correctly."""
        extractor = ProductionKlinesExtractor(symbols=["BTCUSDT"], period="15m", db_adapter_name="mysql")

        # Test with timezone-naive datetime from database
        naive_timestamp = datetime(2023, 1, 1, 12, 0, 0)  # No timezone info

        # This should not raise an error
        with patch("jobs.extract_klines_production.get_current_utc_time") as mock_current_time:
            mock_current_time.return_value = datetime(2023, 1, 1, 13, 0, 0, tzinfo=timezone.utc)

            start_time, end_time = extractor.calculate_extraction_window(naive_timestamp)

            # Should convert naive timestamp to timezone-aware
            assert start_time.tzinfo is not None
            assert end_time.tzinfo is not None
            assert start_time < end_time

    def test_timezone_aware_timestamp_retrieval(self):
        """Test that timestamps from database are made timezone-aware."""
        extractor = ProductionKlinesExtractor(symbols=["BTCUSDT"], period="15m", db_adapter_name="mysql")

        # Mock database adapter
        mock_adapter = Mock()

        # Mock database response with timezone-naive timestamp
        mock_record = {"close_time": datetime(2023, 1, 1, 12, 0, 0)}  # No timezone info
        mock_adapter.query_latest.return_value = [mock_record]

        timestamp = extractor.get_last_timestamp_for_symbol(mock_adapter, "BTCUSDT")

        # Should be timezone-aware
        assert timestamp.tzinfo is not None
        assert timestamp.tzinfo == timezone.utc


if __name__ == "__main__":
    pytest.main([__file__])
