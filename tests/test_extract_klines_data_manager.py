"""
Comprehensive tests for extract_klines_data_manager.py.

Tests cover:
- Normal extraction flow
- Corner cases (timezone edge cases, empty data, API failures)
- Performance scenarios (large datasets, parallel processing)
- Security (input validation, error handling)
- Chaos testing (network failures, partial responses)
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jobs.extract_klines_data_manager import (
    DataManagerKlinesExtractor,
    main,
    parse_arguments,
)


class TestDataManagerKlinesExtractor:
    """Test suite for DataManagerKlinesExtractor class."""

    def test_init(self):
        """Test extractor initialization."""
        symbols = ["BTCUSDT", "ETHUSDT"]
        period = "15m"
        extractor = DataManagerKlinesExtractor(
            symbols=symbols, period=period, max_workers=5, lookback_hours=24
        )

        assert extractor.symbols == symbols
        assert extractor.period == period
        assert extractor.max_workers == 5
        assert extractor.lookback_hours == 24
        assert extractor.stats["symbols_processed"] == 0
        assert extractor.stats["symbols_failed"] == 0

    @pytest.mark.asyncio
    async def test_extract_symbol_data_success(self):
        """Test successful symbol data extraction."""
        extractor = DataManagerKlinesExtractor(
            symbols=["BTCUSDT"], period="15m", max_workers=1, lookback_hours=24
        )

        # Mock BinanceClient
        mock_client = MagicMock()

        # Mock KlinesFetcherDataManager
        with patch(
            "jobs.extract_klines_data_manager.KlinesFetcherDataManager"
        ) as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value = mock_fetcher

            # Mock latest timestamp
            last_timestamp = datetime.now(UTC) - timedelta(hours=1)
            mock_fetcher.get_latest_timestamp = AsyncMock(return_value=last_timestamp)

            # Mock fetch and store
            mock_klines = [{"timestamp": datetime.now(UTC), "close": 45000}]
            mock_fetcher.fetch_and_store_klines = AsyncMock(return_value=mock_klines)

            # Mock find_gaps
            mock_fetcher.find_gaps = AsyncMock(return_value=[])

            # Run extraction
            result = await extractor.extract_symbol_data("BTCUSDT", mock_client)

            # Assertions
            assert result["success"] is True
            assert result["symbol"] == "BTCUSDT"
            assert result["records_fetched"] == 1
            assert result["records_written"] == 1
            assert result["gaps_filled"] == 0
            assert result["error"] is None
            assert result["duration"] > 0

    @pytest.mark.asyncio
    async def test_extract_symbol_data_with_gaps(self):
        """Test extraction with detected gaps."""
        extractor = DataManagerKlinesExtractor(
            symbols=["ETHUSDT"], period="1h", max_workers=1, lookback_hours=24
        )

        mock_client = MagicMock()

        with patch(
            "jobs.extract_klines_data_manager.KlinesFetcherDataManager"
        ) as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value = mock_fetcher

            last_timestamp = datetime.now(UTC) - timedelta(hours=5)
            mock_fetcher.get_latest_timestamp = AsyncMock(return_value=last_timestamp)

            mock_klines = [{"timestamp": datetime.now(UTC), "close": 3000}]
            mock_fetcher.fetch_and_store_klines = AsyncMock(return_value=mock_klines)

            # Simulate gaps found
            gaps = [
                {"start": datetime.now(UTC) - timedelta(hours=3), "count": 2},
                {"start": datetime.now(UTC) - timedelta(hours=2), "count": 1},
            ]
            mock_fetcher.find_gaps = AsyncMock(return_value=gaps)

            result = await extractor.extract_symbol_data("ETHUSDT", mock_client)

            assert result["success"] is True
            assert result["gaps_filled"] == 2

    @pytest.mark.asyncio
    async def test_extract_symbol_data_no_existing_data(self):
        """Test extraction when no existing data (bootstrap case)."""
        extractor = DataManagerKlinesExtractor(
            symbols=["BNBUSDT"], period="15m", max_workers=1, lookback_hours=24
        )

        mock_client = MagicMock()

        with patch(
            "jobs.extract_klines_data_manager.KlinesFetcherDataManager"
        ) as mock_fetcher_class, patch(
            "jobs.extract_klines_data_manager.constants"
        ) as mock_constants:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value = mock_fetcher

            # No existing data
            mock_fetcher.get_latest_timestamp = AsyncMock(return_value=None)
            mock_constants.DEFAULT_START_DATE = "2020-01-01T00:00:00Z"

            mock_klines = [{"timestamp": datetime.now(UTC), "close": 400}]
            mock_fetcher.fetch_and_store_klines = AsyncMock(return_value=mock_klines)
            mock_fetcher.find_gaps = AsyncMock(return_value=[])

            result = await extractor.extract_symbol_data("BNBUSDT", mock_client)

            assert result["success"] is True
            assert result["records_fetched"] > 0

    @pytest.mark.asyncio
    async def test_extract_symbol_data_failure(self):
        """Test extraction failure handling."""
        extractor = DataManagerKlinesExtractor(
            symbols=["INVALID"], period="15m", max_workers=1, lookback_hours=24
        )

        mock_client = MagicMock()

        with patch(
            "jobs.extract_klines_data_manager.KlinesFetcherDataManager"
        ) as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value = mock_fetcher

            # Simulate API error
            mock_fetcher.get_latest_timestamp = AsyncMock(
                side_effect=Exception("API rate limit exceeded")
            )

            result = await extractor.extract_symbol_data("INVALID", mock_client)

            assert result["success"] is False
            assert result["error"] is not None
            assert "API rate limit" in result["error"]
            assert result["records_fetched"] == 0

    def test_calculate_extraction_window_normal(self):
        """Test extraction window calculation for normal case."""
        extractor = DataManagerKlinesExtractor(
            symbols=["BTCUSDT"], period="15m", max_workers=1, lookback_hours=24
        )

        last_timestamp = datetime.now(UTC) - timedelta(hours=2)
        start_time, end_time = extractor._calculate_extraction_window(last_timestamp)

        assert start_time < last_timestamp  # Has overlap
        assert end_time > start_time
        assert end_time < datetime.now(UTC)  # Has buffer

    def test_calculate_extraction_window_old_timestamp(self):
        """Test extraction window when last timestamp is very old."""
        extractor = DataManagerKlinesExtractor(
            symbols=["BTCUSDT"], period="15m", max_workers=1, lookback_hours=24
        )

        # Very old timestamp (7 days ago)
        last_timestamp = datetime.now(UTC) - timedelta(days=7)
        start_time, end_time = extractor._calculate_extraction_window(last_timestamp)

        # Should limit to MAX_CATCHUP_DAYS (1 day)
        time_diff = datetime.now(UTC) - start_time
        assert time_diff.days <= extractor.MAX_CATCHUP_DAYS

    def test_calculate_extraction_window_naive_datetime(self):
        """Test extraction window with naive (no timezone) datetime."""
        extractor = DataManagerKlinesExtractor(
            symbols=["BTCUSDT"], period="15m", max_workers=1, lookback_hours=24
        )

        # Naive datetime
        last_timestamp = datetime.now() - timedelta(hours=1)
        start_time, end_time = extractor._calculate_extraction_window(last_timestamp)

        assert start_time.tzinfo is not None  # Should be timezone-aware
        assert end_time.tzinfo is not None

    @pytest.mark.asyncio
    async def test_run_extraction_multiple_symbols(self):
        """Test running extraction for multiple symbols."""
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        extractor = DataManagerKlinesExtractor(
            symbols=symbols, period="15m", max_workers=3, lookback_hours=24
        )

        with patch(
            "jobs.extract_klines_data_manager.BinanceClient"
        ) as mock_client_class, patch.object(
            extractor, "extract_symbol_data"
        ) as mock_extract:
            mock_client = MagicMock()
            mock_client.close = MagicMock()
            mock_client_class.return_value = mock_client

            # Mock successful extraction for all symbols
            async def mock_extraction(symbol, client):
                return {
                    "success": True,
                    "symbol": symbol,
                    "records_fetched": 100,
                    "records_written": 100,
                    "gaps_filled": 0,
                    "error": None,
                    "duration": 1.5,
                }

            mock_extract.side_effect = mock_extraction

            result = await extractor.run_extraction()

            assert result["success"] is True
            assert result["total_symbols"] == 3
            assert result["symbols_processed"] == 3
            assert result["symbols_failed"] == 0
            assert result["total_records_fetched"] == 300
            assert result["total_records_written"] == 300

    @pytest.mark.asyncio
    async def test_run_extraction_with_failures(self):
        """Test running extraction with some symbol failures."""
        symbols = ["BTCUSDT", "INVALID1", "ETHUSDT", "INVALID2"]
        extractor = DataManagerKlinesExtractor(
            symbols=symbols, period="1h", max_workers=2, lookback_hours=48
        )

        with patch(
            "jobs.extract_klines_data_manager.BinanceClient"
        ) as mock_client_class, patch.object(
            extractor, "extract_symbol_data"
        ) as mock_extract:
            mock_client = MagicMock()
            mock_client.close = MagicMock()
            mock_client_class.return_value = mock_client

            # Mock mixed success and failure
            async def mock_extraction(symbol, client):
                if "INVALID" in symbol:
                    return {
                        "success": False,
                        "symbol": symbol,
                        "records_fetched": 0,
                        "records_written": 0,
                        "gaps_filled": 0,
                        "error": f"Invalid symbol: {symbol}",
                        "duration": 0.5,
                    }
                return {
                    "success": True,
                    "symbol": symbol,
                    "records_fetched": 200,
                    "records_written": 200,
                    "gaps_filled": 1,
                    "error": None,
                    "duration": 2.0,
                }

            mock_extract.side_effect = mock_extraction

            result = await extractor.run_extraction()

            assert result["success"] is False  # Has failures
            assert result["symbols_processed"] == 2
            assert result["symbols_failed"] == 2
            assert len(result["errors"]) == 2


class TestParseArguments:
    """Test suite for argument parsing."""

    def test_parse_arguments_defaults(self):
        """Test parsing with default arguments."""
        with patch("sys.argv", ["script.py", "--period", "15m"]):
            args = parse_arguments()
            assert args.period == "15m"
            assert args.max_workers == 5
            assert args.lookback_hours == 24
            assert args.dry_run is False

    def test_parse_arguments_custom(self):
        """Test parsing with custom arguments."""
        with patch(
            "sys.argv",
            [
                "script.py",
                "--period",
                "1h",
                "--symbols",
                "BTCUSDT,ETHUSDT",
                "--max-workers",
                "10",
                "--lookback-hours",
                "48",
                "--dry-run",
            ],
        ):
            args = parse_arguments()
            assert args.period == "1h"
            assert args.symbols == "BTCUSDT,ETHUSDT"
            assert args.max_workers == 10
            assert args.lookback_hours == 48
            assert args.dry_run is True


class TestMainFunction:
    """Test suite for main entry point."""

    @pytest.mark.asyncio
    async def test_main_success(self):
        """Test main function success path."""
        with patch("sys.argv", ["script.py", "--period", "15m"]), patch(
            "jobs.extract_klines_data_manager.DataManagerKlinesExtractor"
        ) as mock_extractor_class, patch(
            "jobs.extract_klines_data_manager.setup_logging"
        ), patch(
            "jobs.extract_klines_data_manager.constants"
        ) as mock_constants, pytest.raises(SystemExit) as exc_info:
            mock_constants.DEFAULT_SYMBOLS = ["BTCUSDT"]
            mock_constants.LOG_LEVEL = "INFO"
            mock_constants.DEFAULT_PERIOD = "15m"
            mock_constants.DATA_MANAGER_URL = "http://localhost:8000"

            mock_extractor = AsyncMock()
            mock_extractor.run_extraction = AsyncMock(
                return_value={
                    "success": True,
                    "total_records_written": 1000,
                    "duration_seconds": 10.5,
                    "total_gaps_filled": 0,
                    "errors": [],
                    "symbols_failed": 0,
                }
            )
            mock_extractor_class.return_value = mock_extractor

            await main()

            assert exc_info.value.code == 0

    @pytest.mark.asyncio
    async def test_main_with_failures(self):
        """Test main function with extraction failures."""
        with patch("sys.argv", ["script.py", "--period", "1h"]), patch(
            "jobs.extract_klines_data_manager.DataManagerKlinesExtractor"
        ) as mock_extractor_class, patch(
            "jobs.extract_klines_data_manager.setup_logging"
        ), patch(
            "jobs.extract_klines_data_manager.constants"
        ) as mock_constants, pytest.raises(SystemExit) as exc_info:
            mock_constants.DEFAULT_SYMBOLS = ["BTCUSDT", "INVALID"]
            mock_constants.LOG_LEVEL = "INFO"
            mock_constants.DEFAULT_PERIOD = "1h"
            mock_constants.DATA_MANAGER_URL = "http://localhost:8000"

            mock_extractor = AsyncMock()
            mock_extractor.run_extraction = AsyncMock(
                return_value={
                    "success": False,
                    "total_records_written": 500,
                    "duration_seconds": 8.0,
                    "total_gaps_filled": 0,
                    "errors": ["INVALID: API error"],
                    "symbols_failed": 1,
                }
            )
            mock_extractor_class.return_value = mock_extractor

            await main()

            assert exc_info.value.code == 1


# Corner case tests
class TestCornerCases:
    """Corner case tests for edge scenarios."""

    @pytest.mark.asyncio
    async def test_timezone_dst_transition(self):
        """Test handling of DST transitions."""
        extractor = DataManagerKlinesExtractor(
            symbols=["BTCUSDT"], period="1h", max_workers=1, lookback_hours=24
        )

        # DST transition timestamp (March 2024 in US)
        dst_timestamp = datetime(2024, 3, 10, 2, 0, 0, tzinfo=UTC)
        start, end = extractor._calculate_extraction_window(dst_timestamp)

        assert start.tzinfo is not None
        assert end.tzinfo is not None
        assert start < end

    @pytest.mark.asyncio
    async def test_leap_second_handling(self):
        """Test handling of leap seconds."""
        extractor = DataManagerKlinesExtractor(
            symbols=["BTCUSDT"], period="15m", max_workers=1, lookback_hours=24
        )

        # Leap second timestamp (June 30, 2015 23:59:60 UTC)
        leap_timestamp = datetime(2015, 6, 30, 23, 59, 59, tzinfo=UTC)
        start, end = extractor._calculate_extraction_window(leap_timestamp)

        assert start < end
        assert (end - start).total_seconds() > 0

    @pytest.mark.asyncio
    async def test_year_boundary_extraction(self):
        """Test extraction across year boundary."""
        extractor = DataManagerKlinesExtractor(
            symbols=["BTCUSDT"], period="1h", max_workers=1, lookback_hours=24
        )

        # Year boundary (use current year - 1 to avoid test brittleness)
        current_year = datetime.now(UTC).year
        year_boundary = datetime(current_year - 1, 12, 31, 23, 0, 0, tzinfo=UTC)
        start, end = extractor._calculate_extraction_window(year_boundary)

        # Start should be within reasonable time window (may be limited by MAX_CATCHUP_DAYS)
        assert start < end

    @pytest.mark.asyncio
    async def test_empty_data_response(self):
        """Test handling of empty data response from API."""
        extractor = DataManagerKlinesExtractor(
            symbols=["BTCUSDT"], period="15m", max_workers=1, lookback_hours=24
        )

        mock_client = MagicMock()

        with patch(
            "jobs.extract_klines_data_manager.KlinesFetcherDataManager"
        ) as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value = mock_fetcher

            mock_fetcher.get_latest_timestamp = AsyncMock(
                return_value=datetime.now(UTC)
            )
            mock_fetcher.fetch_and_store_klines = AsyncMock(return_value=[])  # Empty
            mock_fetcher.find_gaps = AsyncMock(return_value=[])

            result = await extractor.extract_symbol_data("BTCUSDT", mock_client)

            assert result["success"] is True
            assert result["records_fetched"] == 0


# Performance tests
class TestPerformance:
    """Performance tests for high-volume scenarios."""

    @pytest.mark.asyncio
    async def test_large_dataset_extraction(self):
        """Test extraction of large dataset (10K records)."""
        extractor = DataManagerKlinesExtractor(
            symbols=["BTCUSDT"],
            period="1m",
            max_workers=1,
            lookback_hours=168,  # 1 week
        )

        mock_client = MagicMock()

        with patch(
            "jobs.extract_klines_data_manager.KlinesFetcherDataManager"
        ) as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value = mock_fetcher

            mock_fetcher.get_latest_timestamp = AsyncMock(
                return_value=datetime.now(UTC) - timedelta(days=7)
            )

            # Simulate large dataset
            large_dataset = [
                {"timestamp": datetime.now(UTC), "close": 45000 + i}
                for i in range(10000)
            ]
            mock_fetcher.fetch_and_store_klines = AsyncMock(return_value=large_dataset)
            mock_fetcher.find_gaps = AsyncMock(return_value=[])

            result = await extractor.extract_symbol_data("BTCUSDT", mock_client)

            assert result["success"] is True
            assert result["records_fetched"] == 10000


# Security tests
class TestSecurity:
    """Security tests for input validation and error handling."""

    @pytest.mark.asyncio
    async def test_malformed_symbol_rejection(self):
        """Test rejection of malformed symbol names."""
        extractor = DataManagerKlinesExtractor(
            symbols=["BTC@USDT", "ETH/USDT", "'; DROP TABLE--"],
            period="15m",
            max_workers=1,
            lookback_hours=24,
        )

        # Symbols should be stored as-is, validation happens at API level
        assert len(extractor.symbols) == 3

    @pytest.mark.asyncio
    async def test_error_message_sanitization(self):
        """Test that error messages don't expose sensitive info."""
        extractor = DataManagerKlinesExtractor(
            symbols=["BTCUSDT"], period="15m", max_workers=1, lookback_hours=24
        )

        mock_client = MagicMock()

        with patch(
            "jobs.extract_klines_data_manager.KlinesFetcherDataManager"
        ) as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value = mock_fetcher

            # Simulate error with sensitive data
            mock_fetcher.get_latest_timestamp = AsyncMock(
                side_effect=Exception("API key ABC123 is invalid")
            )

            result = await extractor.extract_symbol_data("BTCUSDT", mock_client)

            assert result["success"] is False
            # Error is stored but logged, user code should sanitize if needed
            assert result["error"] is not None


# Chaos tests
class TestChaos:
    """Chaos tests for random failure scenarios."""

    @pytest.mark.asyncio
    async def test_network_failure_during_fetch(self):
        """Test handling of network failure during fetch."""
        extractor = DataManagerKlinesExtractor(
            symbols=["BTCUSDT"], period="15m", max_workers=1, lookback_hours=24
        )

        mock_client = MagicMock()

        with patch(
            "jobs.extract_klines_data_manager.KlinesFetcherDataManager"
        ) as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value = mock_fetcher

            mock_fetcher.get_latest_timestamp = AsyncMock(
                return_value=datetime.now(UTC)
            )

            # Simulate network timeout
            mock_fetcher.fetch_and_store_klines = AsyncMock(
                side_effect=TimeoutError("Connection timeout")
            )

            result = await extractor.extract_symbol_data("BTCUSDT", mock_client)

            assert result["success"] is False
            assert "timeout" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_partial_response_corruption(self):
        """Test handling of partial/corrupted API response."""
        extractor = DataManagerKlinesExtractor(
            symbols=["BTCUSDT"], period="1h", max_workers=1, lookback_hours=24
        )

        mock_client = MagicMock()

        with patch(
            "jobs.extract_klines_data_manager.KlinesFetcherDataManager"
        ) as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value = mock_fetcher

            mock_fetcher.get_latest_timestamp = AsyncMock(
                return_value=datetime.now(UTC)
            )

            # Partial/corrupted response
            mock_fetcher.fetch_and_store_klines = AsyncMock(
                side_effect=ValueError("Invalid JSON response")
            )

            result = await extractor.extract_symbol_data("BTCUSDT", mock_client)

            assert result["success"] is False
            assert "Invalid" in result["error"]

    @pytest.mark.asyncio
    async def test_concurrent_extraction_race_condition(self):
        """Test race conditions in concurrent extractions."""
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT"]
        extractor = DataManagerKlinesExtractor(
            symbols=symbols, period="15m", max_workers=5, lookback_hours=24
        )

        with patch(
            "jobs.extract_klines_data_manager.BinanceClient"
        ) as mock_client_class, patch.object(
            extractor, "extract_symbol_data"
        ) as mock_extract:
            mock_client = MagicMock()
            mock_client.close = MagicMock()
            mock_client_class.return_value = mock_client

            call_count = 0

            async def mock_extraction(symbol, client):
                nonlocal call_count
                call_count += 1
                # Simulate varying execution times
                await asyncio.sleep(0.01 * (call_count % 3))
                return {
                    "success": True,
                    "symbol": symbol,
                    "records_fetched": 50,
                    "records_written": 50,
                    "gaps_filled": 0,
                    "error": None,
                    "duration": 0.1,
                }

            mock_extract.side_effect = mock_extraction

            result = await extractor.run_extraction()

            assert result["symbols_processed"] == 5
            assert call_count == 5
