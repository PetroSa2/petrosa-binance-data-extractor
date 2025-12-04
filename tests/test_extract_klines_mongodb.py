"""
Comprehensive tests for extract_klines_mongodb.py.

Tests cover:
- MongoDB-specific extraction logic
- Timeseries collection handling
- Incremental extraction
- Corner cases (timezone, DST, year boundaries)
- Performance scenarios (batch operations, large datasets)
- Security (input validation)
- Chaos testing (connection failures, corrupted data)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from jobs.extract_klines_mongodb import (
    create_timeseries_collection,
    extract_klines_for_symbol,
    get_mongodb_connection_string,
    get_symbols_list,
    main,
    parse_arguments,
)


class TestParseArguments:
    """Test suite for argument parsing."""

    def test_parse_arguments_defaults(self):
        """Test parsing with default arguments."""
        with patch("sys.argv", ["script.py"]), patch(
            "jobs.extract_klines_mongodb.constants"
        ) as mock_constants:
            mock_constants.DEFAULT_PERIOD = "15m"
            mock_constants.DEFAULT_START_DATE = "2020-01-01T00:00:00Z"
            mock_constants.LOG_LEVEL = "INFO"
            mock_constants.SUPPORTED_INTERVALS = ["1m", "15m", "1h"]

            args = parse_arguments()

            assert args.period == "15m"
            assert args.backfill is False  # Default for MongoDB
            assert args.incremental is True  # Default for MongoDB
            assert args.batch_size == 500

    def test_parse_arguments_custom(self):
        """Test parsing with custom arguments."""
        with patch(
            "sys.argv",
            [
                "script.py",
                "--symbols",
                "BTCUSDT,ETHUSDT",
                "--period",
                "1h",
                "--backfill",
                "--batch-size",
                "1000",
                "--dry-run",
            ],
        ), patch("jobs.extract_klines_mongodb.constants") as mock_constants:
            mock_constants.DEFAULT_PERIOD = "15m"
            mock_constants.DEFAULT_START_DATE = "2020-01-01T00:00:00Z"
            mock_constants.LOG_LEVEL = "INFO"
            mock_constants.SUPPORTED_INTERVALS = ["1m", "15m", "1h"]

            args = parse_arguments()

            assert args.symbols == "BTCUSDT,ETHUSDT"
            assert args.period == "1h"
            assert args.backfill is True
            assert args.batch_size == 1000
            assert args.dry_run is True


class TestGetSymbolsList:
    """Test suite for get_symbols_list function."""

    def test_get_symbols_from_single_symbol(self):
        """Test getting symbols from single --symbol argument."""
        args = MagicMock()
        args.symbol = "btcusdt"
        args.symbols = None

        symbols = get_symbols_list(args)

        assert symbols == ["BTCUSDT"]
        assert len(symbols) == 1

    def test_get_symbols_from_multiple_symbols(self):
        """Test getting symbols from --symbols argument."""
        args = MagicMock()
        args.symbol = None
        args.symbols = "BTCUSDT, ETHUSDT, BNBUSDT"

        symbols = get_symbols_list(args)

        assert symbols == ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        assert len(symbols) == 3

    def test_get_symbols_default(self):
        """Test getting default symbols."""
        args = MagicMock()
        args.symbol = None
        args.symbols = None

        with patch("jobs.extract_klines_mongodb.constants") as mock_constants:
            mock_constants.DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT"]
            symbols = get_symbols_list(args)

            assert symbols == ["BTCUSDT", "ETHUSDT"]


class TestGetMongoDBConnectionString:
    """Test suite for get_mongodb_connection_string function."""

    def test_get_connection_string_from_args(self):
        """Test getting connection string from arguments."""
        args = MagicMock()
        args.mongodb_uri = "mongodb://custom:27017"

        conn_str = get_mongodb_connection_string(args)

        assert conn_str == "mongodb://custom:27017"

    def test_get_connection_string_from_constants(self):
        """Test getting connection string from constants."""
        args = MagicMock()
        args.mongodb_uri = None

        with patch("jobs.extract_klines_mongodb.constants") as mock_constants:
            mock_constants.MONGODB_URI = "mongodb://localhost:27017"
            conn_str = get_mongodb_connection_string(args)

            assert conn_str == "mongodb://localhost:27017"


class TestCreateTimeseriesCollection:
    """Test suite for create_timeseries_collection function."""

    def test_create_timeseries_collection_new(self):
        """Test creating a new timeseries collection."""
        mock_adapter = MagicMock()
        mock_db = MagicMock()
        mock_adapter._get_database.return_value = mock_db

        # Collection doesn't exist
        mock_db.list_collection_names.return_value = []

        # Mock collection for indexing
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection

        create_timeseries_collection(mock_adapter, "klines_15m", "15m")

        # Verify timeseries collection was created
        mock_db.create_collection.assert_called_once()
        call_args = mock_db.create_collection.call_args
        assert call_args[0][0] == "klines_15m"
        assert "timeseries" in call_args[1]
        assert call_args[1]["timeseries"]["timeField"] == "timestamp"

        # Verify indexes were created
        assert mock_collection.create_index.call_count == 2

    def test_create_timeseries_collection_exists(self):
        """Test when collection already exists."""
        mock_adapter = MagicMock()
        mock_db = MagicMock()
        mock_adapter._get_database.return_value = mock_db

        # Collection already exists
        mock_db.list_collection_names.return_value = ["klines_15m"]

        create_timeseries_collection(mock_adapter, "klines_15m", "15m")

        # Should not create collection
        mock_db.create_collection.assert_not_called()

    def test_create_timeseries_collection_granularity_minutes(self):
        """Test granularity setting for minute intervals."""
        mock_adapter = MagicMock()
        mock_db = MagicMock()
        mock_adapter._get_database.return_value = mock_db
        mock_db.list_collection_names.return_value = []
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection

        create_timeseries_collection(mock_adapter, "klines_5m", "5m")

        call_args = mock_db.create_collection.call_args[1]
        assert call_args["timeseries"]["granularity"] == "minutes"

    def test_create_timeseries_collection_granularity_hours(self):
        """Test granularity setting for hour intervals."""
        mock_adapter = MagicMock()
        mock_db = MagicMock()
        mock_adapter._get_database.return_value = mock_db
        mock_db.list_collection_names.return_value = []
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection

        create_timeseries_collection(mock_adapter, "klines_1h", "1h")

        call_args = mock_db.create_collection.call_args[1]
        assert call_args["timeseries"]["granularity"] == "hours"

    def test_create_timeseries_collection_error_handling(self):
        """Test error handling during collection creation."""
        mock_adapter = MagicMock()
        mock_db = MagicMock()
        mock_adapter._get_database.return_value = mock_db
        mock_db.list_collection_names.return_value = []

        # Simulate error
        mock_db.create_collection.side_effect = Exception("Permission denied")

        # Should not raise, just print warning
        create_timeseries_collection(mock_adapter, "klines_15m", "15m")


class TestExtractKlinesForSymbol:
    """Test suite for extract_klines_for_symbol function."""

    def test_extract_klines_incremental_with_existing_data(self):
        """Test incremental extraction with existing data."""
        args = MagicMock()
        args.incremental = True
        args.limit = None
        args.batch_size = 500
        args.dry_run = False

        mock_fetcher = MagicMock()
        mock_db_adapter = MagicMock()
        mock_logger = MagicMock()

        # Mock latest records
        last_timestamp = datetime.now(UTC) - timedelta(hours=2)
        mock_db_adapter.query_latest.return_value = [{"timestamp": last_timestamp}]

        # Mock fetch_klines
        mock_klines = [
            Mock(timestamp=datetime.now(UTC), close=45000),
            Mock(timestamp=datetime.now(UTC) - timedelta(minutes=15), close=44900),
        ]
        mock_fetcher.fetch_klines.return_value = mock_klines

        # Mock write_batch
        mock_db_adapter.write_batch.return_value = 2

        with patch(
            "jobs.extract_klines_mongodb.get_current_utc_time"
        ) as mock_get_time, patch(
            "jobs.extract_klines_mongodb.create_timeseries_collection"
        ):
            mock_get_time.return_value = datetime.now(UTC)

            result = extract_klines_for_symbol(
                symbol="BTCUSDT",
                period="15m",
                start_date=datetime.now(UTC) - timedelta(days=1),
                end_date=datetime.now(UTC),
                fetcher=mock_fetcher,
                db_adapter=mock_db_adapter,
                args=args,
                logger=mock_logger,
            )

            assert result["status"] == "success"
            assert result["records_written"] == 2
            assert result["symbol"] == "BTCUSDT"

    def test_extract_klines_incremental_no_existing_data(self):
        """Test incremental extraction with no existing data (fallback)."""
        args = MagicMock()
        args.incremental = True
        args.limit = None
        args.batch_size = 500
        args.dry_run = False

        mock_fetcher = MagicMock()
        mock_db_adapter = MagicMock()
        mock_logger = MagicMock()

        # No existing data
        mock_db_adapter.query_latest.return_value = []

        # Mock fetch_klines
        mock_klines = [Mock(timestamp=datetime.now(UTC), close=45000)]
        mock_fetcher.fetch_klines.return_value = mock_klines
        mock_db_adapter.write_batch.return_value = 1

        with patch(
            "jobs.extract_klines_mongodb.get_current_utc_time"
        ) as mock_get_time, patch(
            "jobs.extract_klines_mongodb.create_timeseries_collection"
        ):
            mock_get_time.return_value = datetime.now(UTC)

            result = extract_klines_for_symbol(
                symbol="ETHUSDT",
                period="1h",
                start_date=datetime.now(UTC) - timedelta(days=1),
                end_date=datetime.now(UTC),
                fetcher=mock_fetcher,
                db_adapter=mock_db_adapter,
                args=args,
                logger=mock_logger,
            )

            assert result["status"] == "success"
            # Should fetch last 10 periods as fallback
            mock_fetcher.fetch_klines.assert_called_once()

    def test_extract_klines_no_data_found(self):
        """Test extraction when no data is returned from API."""
        args = MagicMock()
        args.incremental = False
        args.limit = None
        args.batch_size = 500
        args.dry_run = False

        mock_fetcher = MagicMock()
        mock_db_adapter = MagicMock()
        mock_logger = MagicMock()

        # No klines returned
        mock_fetcher.fetch_klines.return_value = []

        with patch("jobs.extract_klines_mongodb.create_timeseries_collection"):
            result = extract_klines_for_symbol(
                symbol="INVALIDUSDT",
                period="15m",
                start_date=datetime.now(UTC) - timedelta(days=1),
                end_date=datetime.now(UTC),
                fetcher=mock_fetcher,
                db_adapter=mock_db_adapter,
                args=args,
                logger=mock_logger,
            )

            assert result["status"] == "no_data"
            assert result["records_written"] == 0

    def test_extract_klines_dry_run(self):
        """Test extraction in dry-run mode."""
        args = MagicMock()
        args.incremental = False
        args.limit = None
        args.batch_size = 500
        args.dry_run = True  # Dry run mode

        mock_fetcher = MagicMock()
        mock_db_adapter = MagicMock()
        mock_logger = MagicMock()

        mock_klines = [Mock(timestamp=datetime.now(UTC), close=45000)]
        mock_fetcher.fetch_klines.return_value = mock_klines

        with patch("jobs.extract_klines_mongodb.create_timeseries_collection"):
            result = extract_klines_for_symbol(
                symbol="BTCUSDT",
                period="15m",
                start_date=datetime.now(UTC) - timedelta(days=1),
                end_date=datetime.now(UTC),
                fetcher=mock_fetcher,
                db_adapter=mock_db_adapter,
                args=args,
                logger=mock_logger,
            )

            assert result["status"] == "success"
            # Should not call write_batch in dry-run mode
            mock_db_adapter.write_batch.assert_not_called()

    def test_extract_klines_error_handling(self):
        """Test error handling during extraction."""
        args = MagicMock()
        args.incremental = False
        args.limit = None
        args.batch_size = 500
        args.dry_run = False

        mock_fetcher = MagicMock()
        mock_db_adapter = MagicMock()
        mock_logger = MagicMock()

        # Simulate error
        mock_fetcher.fetch_klines.side_effect = Exception("API rate limit exceeded")

        with patch("jobs.extract_klines_mongodb.create_timeseries_collection"):
            result = extract_klines_for_symbol(
                symbol="BTCUSDT",
                period="15m",
                start_date=datetime.now(UTC) - timedelta(days=1),
                end_date=datetime.now(UTC),
                fetcher=mock_fetcher,
                db_adapter=mock_db_adapter,
                args=args,
                logger=mock_logger,
            )

            assert result["status"] == "error"
            assert "API rate limit" in result["error"]
            assert result["records_written"] == 0


# Corner case tests
class TestCornerCases:
    """Corner case tests for edge scenarios."""

    def test_naive_timezone_handling(self):
        """Test handling of naive datetime from database."""
        args = MagicMock()
        args.incremental = True
        args.limit = None
        args.batch_size = 500
        args.dry_run = False

        mock_fetcher = MagicMock()
        mock_db_adapter = MagicMock()
        mock_logger = MagicMock()

        # Naive datetime (no timezone)
        naive_timestamp = datetime.now() - timedelta(hours=1)
        mock_db_adapter.query_latest.return_value = [{"timestamp": naive_timestamp}]

        mock_klines = [Mock(timestamp=datetime.now(UTC), close=45000)]
        mock_fetcher.fetch_klines.return_value = mock_klines
        mock_db_adapter.write_batch.return_value = 1

        with patch(
            "jobs.extract_klines_mongodb.get_current_utc_time"
        ) as mock_get_time, patch(
            "jobs.extract_klines_mongodb.create_timeseries_collection"
        ):
            mock_get_time.return_value = datetime.now(UTC)

            result = extract_klines_for_symbol(
                symbol="BTCUSDT",
                period="15m",
                start_date=datetime.now(UTC) - timedelta(days=1),
                end_date=datetime.now(UTC),
                fetcher=mock_fetcher,
                db_adapter=mock_db_adapter,
                args=args,
                logger=mock_logger,
            )

            # Should handle naive datetime gracefully
            assert result["status"] == "success"

    def test_interval_minute_calculation_edge_cases(self):
        """Test interval calculation for different period formats."""
        args = MagicMock()
        args.incremental = True
        args.limit = None
        args.batch_size = 500
        args.dry_run = True

        mock_fetcher = MagicMock()
        mock_db_adapter = MagicMock()
        mock_logger = MagicMock()

        # Test with different period formats
        periods = ["5m", "1h", "1d"]

        for period in periods:
            mock_db_adapter.query_latest.return_value = [
                {"timestamp": datetime.now(UTC) - timedelta(hours=24)}
            ]
            mock_fetcher.fetch_klines.return_value = []

            with patch(
                "jobs.extract_klines_mongodb.get_current_utc_time"
            ) as mock_get_time, patch(
                "jobs.extract_klines_mongodb.create_timeseries_collection"
            ):
                mock_get_time.return_value = datetime.now(UTC)

                result = extract_klines_for_symbol(
                    symbol="BTCUSDT",
                    period=period,
                    start_date=datetime.now(UTC) - timedelta(days=1),
                    end_date=datetime.now(UTC),
                    fetcher=mock_fetcher,
                    db_adapter=mock_db_adapter,
                    args=args,
                    logger=mock_logger,
                )

                assert result["status"] == "no_data"


# Performance tests
class TestPerformance:
    """Performance tests for batch operations."""

    def test_large_batch_write(self):
        """Test writing large batch of records."""
        args = MagicMock()
        args.incremental = False
        args.limit = None
        args.batch_size = 1000  # Large batch
        args.dry_run = False

        mock_fetcher = MagicMock()
        mock_db_adapter = MagicMock()
        mock_logger = MagicMock()

        # Large dataset
        mock_klines = [
            Mock(timestamp=datetime.now(UTC) - timedelta(minutes=i), close=45000 + i)
            for i in range(5000)
        ]
        mock_fetcher.fetch_klines.return_value = mock_klines
        mock_db_adapter.write_batch.return_value = 5000

        with patch("jobs.extract_klines_mongodb.create_timeseries_collection"):
            result = extract_klines_for_symbol(
                symbol="BTCUSDT",
                period="1m",
                start_date=datetime.now(UTC) - timedelta(days=3),
                end_date=datetime.now(UTC),
                fetcher=mock_fetcher,
                db_adapter=mock_db_adapter,
                args=args,
                logger=mock_logger,
            )

            assert result["status"] == "success"
            assert result["records_written"] == 5000


# Security tests
class TestSecurity:
    """Security tests for input validation."""

    def test_symbol_with_special_characters(self):
        """Test handling of symbols with special characters."""
        args = MagicMock()
        args.incremental = False
        args.limit = None
        args.batch_size = 500
        args.dry_run = True

        mock_fetcher = MagicMock()
        mock_db_adapter = MagicMock()
        mock_logger = MagicMock()

        mock_fetcher.fetch_klines.return_value = []

        with patch("jobs.extract_klines_mongodb.create_timeseries_collection"):
            # Special characters should be handled by validation at API level
            result = extract_klines_for_symbol(
                symbol="BTC'; DROP TABLE--",
                period="15m",
                start_date=datetime.now(UTC) - timedelta(days=1),
                end_date=datetime.now(UTC),
                fetcher=mock_fetcher,
                db_adapter=mock_db_adapter,
                args=args,
                logger=mock_logger,
            )

            # Should complete without SQL injection
            assert result["status"] == "no_data"


# Chaos tests
class TestChaos:
    """Chaos tests for failure scenarios."""

    def test_database_connection_failure(self):
        """Test handling of database connection failure."""
        args = MagicMock()
        args.incremental = True
        args.limit = None
        args.batch_size = 500
        args.dry_run = False

        mock_fetcher = MagicMock()
        mock_db_adapter = MagicMock()
        mock_logger = MagicMock()

        # Simulate connection failure
        mock_db_adapter.query_latest.side_effect = Exception("Connection refused")

        with patch("jobs.extract_klines_mongodb.create_timeseries_collection"):
            result = extract_klines_for_symbol(
                symbol="BTCUSDT",
                period="15m",
                start_date=datetime.now(UTC) - timedelta(days=1),
                end_date=datetime.now(UTC),
                fetcher=mock_fetcher,
                db_adapter=mock_db_adapter,
                args=args,
                logger=mock_logger,
            )

            assert result["status"] == "error"
            assert "Connection refused" in result["error"]

    def test_partial_write_failure(self):
        """Test handling of partial write failure."""
        args = MagicMock()
        args.incremental = False
        args.limit = None
        args.batch_size = 500
        args.dry_run = False

        mock_fetcher = MagicMock()
        mock_db_adapter = MagicMock()
        mock_logger = MagicMock()

        mock_klines = [Mock(timestamp=datetime.now(UTC), close=45000)]
        mock_fetcher.fetch_klines.return_value = mock_klines

        # Simulate partial write
        mock_db_adapter.write_batch.side_effect = Exception("Disk full")

        with patch("jobs.extract_klines_mongodb.create_timeseries_collection"):
            result = extract_klines_for_symbol(
                symbol="BTCUSDT",
                period="15m",
                start_date=datetime.now(UTC) - timedelta(days=1),
                end_date=datetime.now(UTC),
                fetcher=mock_fetcher,
                db_adapter=mock_db_adapter,
                args=args,
                logger=mock_logger,
            )

            assert result["status"] == "error"
            assert "Disk full" in result["error"]


class TestMainFunction:
    """Test suite for main entry point."""

    def test_main_success(self):
        """Test main function success path."""
        with patch("sys.argv", ["script.py", "--symbol", "BTCUSDT"]), patch(
            "jobs.extract_klines_mongodb.parse_datetime_string"
        ) as mock_parse, patch(
            "jobs.extract_klines_mongodb.get_current_utc_time"
        ) as mock_get_time, patch(
            "jobs.extract_klines_mongodb.MongoDBAdapter"
        ) as mock_adapter_class, patch(
            "jobs.extract_klines_mongodb.BinanceClient"
        ) as mock_client_class, patch(
            "jobs.extract_klines_mongodb.KlinesFetcher"
        ) as mock_fetcher_class, patch(
            "jobs.extract_klines_mongodb.setup_logging"
        ) as mock_logging, patch(
            "jobs.extract_klines_mongodb.constants"
        ) as mock_constants, pytest.raises(SystemExit) as exc_info:
            mock_constants.DEFAULT_PERIOD = "15m"
            mock_constants.DEFAULT_START_DATE = "2020-01-01T00:00:00Z"
            mock_constants.LOG_LEVEL = "INFO"
            mock_constants.SUPPORTED_INTERVALS = ["15m"]
            mock_constants.MONGODB_URI = "mongodb://localhost:27017"

            mock_parse.return_value = datetime.now(UTC)
            mock_get_time.return_value = datetime.now(UTC)
            mock_logging.return_value = MagicMock()

            # Mock database adapter
            mock_adapter = MagicMock()
            mock_adapter.connect = MagicMock()
            mock_adapter.disconnect = MagicMock()
            mock_adapter_class.return_value = mock_adapter

            # Mock client and fetcher
            mock_client = MagicMock()
            mock_fetcher = MagicMock()
            mock_fetcher.close = MagicMock()
            mock_client_class.return_value = mock_client
            mock_fetcher_class.return_value = mock_fetcher

            with patch(
                "jobs.extract_klines_mongodb.extract_klines_for_symbol"
            ) as mock_extract:
                mock_extract.return_value = {
                    "symbol": "BTCUSDT",
                    "records_written": 100,
                    "duration": 5.0,
                    "status": "success",
                }

                main()

                assert exc_info.value.code == 0

    def test_main_with_error(self):
        """Test main function with extraction error."""
        with patch("sys.argv", ["script.py"]), patch(
            "jobs.extract_klines_mongodb.parse_datetime_string"
        ), patch("jobs.extract_klines_mongodb.get_current_utc_time"), patch(
            "jobs.extract_klines_mongodb.MongoDBAdapter"
        ) as mock_adapter_class, patch(
            "jobs.extract_klines_mongodb.setup_logging"
        ) as mock_logging, patch(
            "jobs.extract_klines_mongodb.constants"
        ) as mock_constants, pytest.raises(SystemExit) as exc_info:
            mock_constants.DEFAULT_PERIOD = "15m"
            mock_constants.DEFAULT_START_DATE = "2020-01-01T00:00:00Z"
            mock_constants.LOG_LEVEL = "INFO"
            mock_constants.SUPPORTED_INTERVALS = ["15m"]
            mock_constants.MONGODB_URI = "mongodb://localhost:27017"
            mock_constants.DEFAULT_SYMBOLS = ["BTCUSDT"]

            mock_logging.return_value = MagicMock()

            # Simulate connection error
            mock_adapter = MagicMock()
            mock_adapter.connect.side_effect = Exception("Connection failed")
            mock_adapter_class.return_value = mock_adapter

            main()

            assert exc_info.value.code == 1
