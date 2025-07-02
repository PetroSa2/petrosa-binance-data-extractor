#!/usr/bin/env python3
"""
Unit tests for jobs/extract_klines.py
"""
import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import jobs.extract_klines as extract_klines


class TestParseArguments:
    def test_default_arguments(self):
        with patch("sys.argv", ["extract_klines.py"]):
            args = extract_klines.parse_arguments()
            assert args.period == extract_klines.constants.DEFAULT_PERIOD
            assert args.start_date == extract_klines.constants.DEFAULT_START_DATE
            assert args.db_adapter == extract_klines.constants.DB_ADAPTER
            assert args.batch_size == extract_klines.constants.DB_BATCH_SIZE
            assert args.log_level == extract_klines.constants.LOG_LEVEL
            assert args.backfill == extract_klines.constants.BACKFILL
            assert args.check_gaps == extract_klines.constants.GAP_CHECK_ENABLED

    def test_custom_arguments(self):
        with patch(
            "sys.argv",
            [
                "extract_klines.py",
                "--symbol",
                "BTCUSDT",
                "--period",
                "1h",
                "--start-date",
                "2024-01-01T00:00:00Z",
                "--end-date",
                "2024-01-02T00:00:00Z",
                "--backfill",
                "--incremental",
                "--limit",
                "100",
                "--batch-size",
                "50",
                "--db-adapter",
                "mysql",
                "--db-uri",
                "mysql://test",
                "--log-level",
                "DEBUG",
                "--dry-run",
                "--check-gaps",
            ],
        ):
            args = extract_klines.parse_arguments()
            assert args.symbol == "BTCUSDT"
            assert args.period == "1h"
            assert args.start_date == "2024-01-01T00:00:00Z"
            assert args.end_date == "2024-01-02T00:00:00Z"
            assert args.backfill is True
            assert args.incremental is True
            assert args.limit == 100
            assert args.batch_size == 50
            assert args.db_adapter == "mysql"
            assert args.db_uri == "mysql://test"
            assert args.log_level == "DEBUG"
            assert args.dry_run is True
            assert args.check_gaps is True


class TestHelpers:
    def test_get_symbols_list(self):
        args = Mock(symbol="BTCUSDT", symbols=None)
        assert extract_klines.get_symbols_list(args) == ["BTCUSDT"]
        args = Mock(symbol=None, symbols="BTCUSDT,ethusdt")
        assert extract_klines.get_symbols_list(args) == ["BTCUSDT", "ETHUSDT"]
        args = Mock(symbol=None, symbols=None)
        assert extract_klines.get_symbols_list(args) == extract_klines.constants.DEFAULT_SYMBOLS

    def test_get_database_connection_string(self):
        args = Mock(db_uri="custom://uri", db_adapter="mongodb")
        assert extract_klines.get_database_connection_string(args) == "custom://uri"
        args = Mock(db_uri=None, db_adapter="mongodb")
        assert extract_klines.get_database_connection_string(args) == extract_klines.constants.MONGODB_URI
        args = Mock(db_uri=None, db_adapter="mysql")
        assert extract_klines.get_database_connection_string(args) == extract_klines.constants.MYSQL_URI
        args = Mock(db_uri=None, db_adapter="postgresql")
        assert extract_klines.get_database_connection_string(args) == extract_klines.constants.POSTGRESQL_URI
        args = Mock(db_uri=None, db_adapter="unknown")
        assert extract_klines.get_database_connection_string(args) == extract_klines.constants.MONGODB_URI


class TestExtractKlinesForSymbol:
    @patch("utils.time_utils.binance_interval_to_table_suffix", return_value="1h")
    def test_full_extraction(self, mock_suffix):
        fetcher = Mock()
        fetcher.fetch_klines.return_value = [Mock(), Mock()]
        db_adapter = Mock()
        db_adapter.ensure_indexes.return_value = None
        db_adapter.write_batch.return_value = 2
        args = Mock(incremental=False, dry_run=False, check_gaps=False, limit=100, batch_size=50)
        logger = Mock()
        result = extract_klines.extract_klines_for_symbol(
            symbol="BTCUSDT",
            period="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            fetcher=fetcher,
            db_adapter=db_adapter,
            args=args,
            logger=logger,
        )
        assert result["success"] is True
        assert result["records_fetched"] == 2
        assert result["records_written"] == 2
        assert result["gaps_found"] == 0
        assert result["errors"] == []

    @patch("utils.time_utils.binance_interval_to_table_suffix", return_value="1h")
    def test_incremental_extraction(self, mock_suffix):
        fetcher = Mock()
        fetcher.fetch_incremental.return_value = [Mock()]
        db_adapter = Mock()
        db_adapter.query_latest.return_value = [{"timestamp": 1234567890}]
        db_adapter.ensure_indexes.return_value = None
        db_adapter.write_batch.return_value = 1
        args = Mock(incremental=True, dry_run=False, check_gaps=False, limit=100, batch_size=50)
        logger = Mock()
        result = extract_klines.extract_klines_for_symbol(
            symbol="BTCUSDT",
            period="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            fetcher=fetcher,
            db_adapter=db_adapter,
            args=args,
            logger=logger,
        )
        assert result["success"] is True
        assert result["records_fetched"] == 1
        assert result["records_written"] == 1
        assert result["gaps_found"] == 0
        assert result["errors"] == []

    @patch("utils.time_utils.binance_interval_to_table_suffix", return_value="1h")
    @patch("utils.time_utils.get_interval_minutes", return_value=60)
    def test_gap_check(self, mock_interval, mock_suffix):
        fetcher = Mock()
        fetcher.fetch_klines.return_value = [Mock(), Mock()]
        db_adapter = Mock()
        db_adapter.ensure_indexes.return_value = None
        db_adapter.write_batch.return_value = 2
        db_adapter.find_gaps.return_value = [(1, 2), (3, 4)]
        args = Mock(incremental=False, dry_run=False, check_gaps=True, limit=100, batch_size=50)
        logger = Mock()
        result = extract_klines.extract_klines_for_symbol(
            symbol="BTCUSDT",
            period="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            fetcher=fetcher,
            db_adapter=db_adapter,
            args=args,
            logger=logger,
        )
        assert result["gaps_found"] == 2
        assert result["success"] is True

    @patch("utils.time_utils.binance_interval_to_table_suffix", return_value="1h")
    def test_dry_run(self, mock_suffix):
        fetcher = Mock()
        fetcher.fetch_klines.return_value = [Mock(), Mock()]
        db_adapter = Mock()
        args = Mock(incremental=False, dry_run=True, check_gaps=False, limit=100, batch_size=50)
        logger = Mock()
        result = extract_klines.extract_klines_for_symbol(
            symbol="BTCUSDT",
            period="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            fetcher=fetcher,
            db_adapter=db_adapter,
            args=args,
            logger=logger,
        )
        assert result["records_written"] == 0
        assert result["success"] is True

    @patch("utils.time_utils.binance_interval_to_table_suffix", return_value="1h")
    def test_error_handling(self, mock_suffix):
        fetcher = Mock()
        fetcher.fetch_klines.side_effect = Exception("fail")
        db_adapter = Mock()
        args = Mock(incremental=False, dry_run=False, check_gaps=False, limit=100, batch_size=50)
        logger = Mock()
        result = extract_klines.extract_klines_for_symbol(
            symbol="BTCUSDT",
            period="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            fetcher=fetcher,
            db_adapter=db_adapter,
            args=args,
            logger=logger,
        )
        assert result["success"] is False
        assert result["errors"]


class TestMain:
    def _run_main_and_catch_exit(self, *args, **kwargs):
        try:
            extract_klines.main()
        except SystemExit as e:
            return e.code
        except UnboundLocalError:
            # This is expected if date parsing fails and code tries to use start_date
            return None
        return None

    @patch("jobs.extract_klines.parse_arguments")
    @patch("jobs.extract_klines.setup_logging")
    @patch("jobs.extract_klines.log_extraction_start")
    @patch("jobs.extract_klines.log_extraction_completion")
    @patch("jobs.extract_klines.get_adapter")
    @patch("jobs.extract_klines.BinanceClient")
    @patch("jobs.extract_klines.KlinesFetcher")
    @patch("jobs.extract_klines.get_symbols_list")
    @patch("jobs.extract_klines.get_database_connection_string")
    @patch("jobs.extract_klines.parse_datetime_string")
    @patch("jobs.extract_klines.get_current_utc_time")
    def test_main_normal(
        self,
        mock_get_current_utc_time,
        mock_parse_datetime_string,
        mock_get_db_conn_str,
        mock_get_symbols_list,
        mock_klines_fetcher_cls,
        mock_binance_client_cls,
        mock_get_adapter,
        mock_log_completion,
        mock_log_start,
        mock_setup_logging,
        mock_parse_args,
    ):
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_args = Mock()
        mock_args.start_date = "2024-01-01T00:00:00Z"
        mock_args.end_date = None
        mock_args.period = "1h"
        mock_args.db_adapter = "mongodb"
        mock_args.db_uri = None
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_args.check_gaps = False
        mock_args.backfill = False
        mock_parse_args.return_value = mock_args
        mock_parse_datetime_string.side_effect = [datetime(2024, 1, 1, tzinfo=timezone.utc)]
        mock_get_current_utc_time.return_value = datetime(2024, 1, 2, tzinfo=timezone.utc)
        mock_get_symbols_list.return_value = ["BTCUSDT"]
        mock_get_db_conn_str.return_value = "mongodb://test"
        mock_get_adapter.return_value.__enter__.return_value = mock_get_adapter.return_value
        mock_get_adapter.return_value.ensure_indexes.return_value = None
        mock_binance_client = Mock()
        mock_binance_client.ping.return_value = True
        mock_binance_client_cls.return_value = mock_binance_client
        mock_klines_fetcher = Mock()
        mock_klines_fetcher.close.return_value = None
        mock_klines_fetcher.fetch_klines.return_value = [Mock(), Mock()]
        mock_klines_fetcher_cls.return_value = mock_klines_fetcher
        # Patch extract_klines_for_symbol to avoid deep logic
        with patch(
            "jobs.extract_klines.extract_klines_for_symbol",
            return_value={
                "symbol": "BTCUSDT",
                "success": True,
                "records_fetched": 2,
                "records_written": 2,
                "gaps_found": 0,
                "duration_seconds": 1.0,
                "errors": [],
            },
        ):
            exit_code = self._run_main_and_catch_exit()
            assert exit_code == 0
        mock_log_completion.assert_called()

    @patch("jobs.extract_klines.parse_arguments")
    @patch("jobs.extract_klines.setup_logging")
    @patch("jobs.extract_klines.log_extraction_start")
    @patch("jobs.extract_klines.log_extraction_completion")
    @patch("jobs.extract_klines.get_adapter")
    @patch("jobs.extract_klines.BinanceClient")
    @patch("jobs.extract_klines.KlinesFetcher")
    @patch("jobs.extract_klines.get_symbols_list")
    @patch("jobs.extract_klines.get_database_connection_string")
    @patch("jobs.extract_klines.parse_datetime_string")
    @patch("jobs.extract_klines.get_current_utc_time")
    def test_main_ping_fail(
        self,
        mock_get_current_utc_time,
        mock_parse_datetime_string,
        mock_get_db_conn_str,
        mock_get_symbols_list,
        mock_klines_fetcher_cls,
        mock_binance_client_cls,
        mock_get_adapter,
        mock_log_completion,
        mock_log_start,
        mock_setup_logging,
        mock_parse_args,
    ):
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_args = Mock()
        mock_args.start_date = "2024-01-01T00:00:00Z"
        mock_args.end_date = None
        mock_args.period = "1h"
        mock_args.db_adapter = "mongodb"
        mock_args.db_uri = None
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_args.check_gaps = False
        mock_args.backfill = False
        mock_parse_args.return_value = mock_args
        mock_parse_datetime_string.side_effect = [datetime(2024, 1, 1, tzinfo=timezone.utc)]
        mock_get_current_utc_time.return_value = datetime(2024, 1, 2, tzinfo=timezone.utc)
        mock_get_symbols_list.return_value = ["BTCUSDT"]
        mock_get_db_conn_str.return_value = "mongodb://test"
        mock_get_adapter.return_value.__enter__.return_value = mock_get_adapter.return_value
        mock_get_adapter.return_value.ensure_indexes.return_value = None
        mock_binance_client = Mock()
        mock_binance_client.ping.return_value = False
        mock_binance_client_cls.return_value = mock_binance_client
        mock_klines_fetcher = Mock()
        mock_klines_fetcher.close.return_value = None
        mock_klines_fetcher_cls.return_value = mock_klines_fetcher
        with patch("sys.exit") as mock_exit:
            extract_klines.main()
            mock_exit.assert_called_with(1)

    @patch("jobs.extract_klines.parse_arguments")
    @patch("jobs.extract_klines.setup_logging")
    @patch("jobs.extract_klines.log_extraction_start")
    @patch("jobs.extract_klines.log_extraction_completion")
    @patch("jobs.extract_klines.get_adapter")
    @patch("jobs.extract_klines.BinanceClient")
    @patch("jobs.extract_klines.KlinesFetcher")
    @patch("jobs.extract_klines.get_symbols_list")
    @patch("jobs.extract_klines.get_database_connection_string")
    @patch("jobs.extract_klines.parse_datetime_string")
    @patch("jobs.extract_klines.get_current_utc_time")
    def test_main_date_parse_error(
        self,
        mock_get_current_utc_time,
        mock_parse_datetime_string,
        mock_get_db_conn_str,
        mock_get_symbols_list,
        mock_klines_fetcher_cls,
        mock_binance_client_cls,
        mock_get_adapter,
        mock_log_completion,
        mock_log_start,
        mock_setup_logging,
        mock_parse_args,
    ):
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_args = Mock()
        mock_args.start_date = "bad-date"
        mock_args.end_date = None
        mock_args.period = "1h"
        mock_args.db_adapter = "mongodb"
        mock_args.db_uri = None
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_args.check_gaps = False
        mock_args.backfill = False
        mock_parse_args.return_value = mock_args
        mock_parse_datetime_string.side_effect = ValueError("bad date")
        with patch("sys.exit") as mock_exit:
            extract_klines.main()
            mock_exit.assert_called_with(1)

    @patch("jobs.extract_klines.parse_arguments")
    @patch("jobs.extract_klines.setup_logging")
    @patch("jobs.extract_klines.log_extraction_start")
    @patch("jobs.extract_klines.log_extraction_completion")
    @patch("jobs.extract_klines.get_adapter")
    @patch("jobs.extract_klines.BinanceClient")
    @patch("jobs.extract_klines.KlinesFetcher")
    @patch("jobs.extract_klines.get_symbols_list")
    @patch("jobs.extract_klines.get_database_connection_string")
    @patch("jobs.extract_klines.parse_datetime_string")
    @patch("jobs.extract_klines.get_current_utc_time")
    def test_main_db_error(
        self,
        mock_get_current_utc_time,
        mock_parse_datetime_string,
        mock_get_db_conn_str,
        mock_get_symbols_list,
        mock_klines_fetcher_cls,
        mock_binance_client_cls,
        mock_get_adapter,
        mock_log_completion,
        mock_log_start,
        mock_setup_logging,
        mock_parse_args,
    ):
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_args = Mock()
        mock_args.start_date = "2024-01-01T00:00:00Z"
        mock_args.end_date = None
        mock_args.period = "1h"
        mock_args.db_adapter = "mongodb"
        mock_args.db_uri = None
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_args.check_gaps = False
        mock_args.backfill = False
        mock_parse_args.return_value = mock_args
        mock_parse_datetime_string.side_effect = [datetime(2024, 1, 1, tzinfo=timezone.utc)]
        mock_get_current_utc_time.return_value = datetime(2024, 1, 2, tzinfo=timezone.utc)
        mock_get_symbols_list.return_value = ["BTCUSDT"]
        mock_get_db_conn_str.return_value = "mongodb://test"
        mock_get_adapter.side_effect = Exception("db fail")
        with patch("sys.exit") as mock_exit:
            extract_klines.main()
            mock_exit.assert_called_with(1)
