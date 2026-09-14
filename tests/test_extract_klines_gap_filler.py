#!/usr/bin/env python3
"""
Unit tests for jobs/extract_klines_gap_filler.py
"""

import os
import sys
from datetime import datetime, timezone

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone

    UTC = timezone.utc  # noqa: UP017
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import jobs.extract_klines_gap_filler as gap_filler  # noqa: E402

UTC = UTC


class TestRetryWithBackoff:
    def test_retry_success_on_first_attempt(self):
        mock_func = Mock(return_value="success")
        result = gap_filler.retry_with_backoff(mock_func, max_retries=3)
        assert result == "success"
        assert mock_func.call_count == 1

    def test_retry_success_after_failures(self):
        mock_func = Mock(side_effect=[Exception("fail"), Exception("fail"), "success"])
        with patch("time.sleep"):  # Mock sleep to speed up test
            result = gap_filler.retry_with_backoff(
                mock_func, max_retries=3, retry_on_all_errors=True
            )
        assert result == "success"
        assert mock_func.call_count == 3

    def test_retry_all_attempts_fail(self):
        mock_func = Mock(side_effect=Exception("persistent failure"))
        with patch("time.sleep"):  # Mock sleep to speed up test
            with pytest.raises(Exception, match="persistent failure"):
                gap_filler.retry_with_backoff(
                    mock_func, max_retries=2, retry_on_all_errors=True
                )
        assert mock_func.call_count == 3

    def test_retry_connection_error(self):
        mock_func = Mock(side_effect=ConnectionError("lost connection to mysql server"))
        mock_logger = Mock()
        with patch("time.sleep"):
            with pytest.raises(ConnectionError):
                gap_filler.retry_with_backoff(
                    mock_func, max_retries=1, logger=mock_logger
                )
        assert mock_func.call_count == 2

    def test_retry_api_rate_limit(self):
        mock_func = Mock(side_effect=RuntimeError("rate limit exceeded"))
        mock_logger = Mock()
        with patch("time.sleep"):
            with pytest.raises(RuntimeError):
                gap_filler.retry_with_backoff(
                    mock_func, max_retries=1, logger=mock_logger
                )
        assert mock_func.call_count == 2

    def test_retry_non_retryable_error(self):
        mock_func = Mock(side_effect=ValueError("invalid input"))
        mock_logger = Mock()
        with pytest.raises(ValueError, match="invalid input"):
            gap_filler.retry_with_backoff(mock_func, max_retries=3, logger=mock_logger)
        assert mock_func.call_count == 1


class TestGapFillerExtractor:
    def test_initialization(self):
        extractor = gap_filler.GapFillerExtractor(
            symbols=["BTCUSDT", "ETHUSDT"],
            period="15m",
            db_adapter_name="mongodb",
            db_uri="mongodb://test",
            max_workers=5,
            batch_size=500,
            weekly_chunk_days=3,
            max_gap_size_days=15,
        )
        assert extractor.symbols == ["BTCUSDT", "ETHUSDT"]
        assert extractor.period == "15m"
        assert extractor.db_adapter_name == "mongodb"
        assert extractor.db_uri == "mongodb://test"
        assert extractor.max_workers == 5
        assert extractor.batch_size == 500
        assert extractor.weekly_chunk_days == 3
        assert extractor.max_gap_size_days == 15
        assert extractor.stats["symbols_processed"] == 0

    def test_period_to_minutes(self):
        extractor = gap_filler.GapFillerExtractor(["BTCUSDT"], "15m", "mongodb")
        result = extractor.period_to_minutes()
        assert result == 15

    @patch(
        "jobs.extract_klines_gap_filler.binance_interval_to_table_suffix",
        return_value="m15",
    )
    def test_get_collection_name(self, mock_suffix):
        extractor = gap_filler.GapFillerExtractor(["BTCUSDT"], "15m", "mongodb")
        result = extractor.get_collection_name()
        assert result == "klines_m15"
        mock_suffix.assert_called_with("15m")

    def test_get_start_date(self):
        extractor = gap_filler.GapFillerExtractor(["BTCUSDT"], "15m", "mongodb")
        start_date = extractor.get_start_date()
        assert isinstance(start_date, datetime)
        assert start_date.tzinfo is not None

    def test_get_end_date(self):
        extractor = gap_filler.GapFillerExtractor(["BTCUSDT"], "15m", "mongodb")
        end_date = extractor.get_end_date()
        assert isinstance(end_date, datetime)
        assert end_date.tzinfo is not None

    def test_split_weekly_chunks(self):
        extractor = gap_filler.GapFillerExtractor(
            ["BTCUSDT"], "15m", "mongodb", weekly_chunk_days=3
        )
        start_date = datetime(2024, 1, 1, tzinfo=UTC)
        end_date = datetime(2024, 1, 10, tzinfo=UTC)
        chunks = extractor.split_weekly_chunks(start_date, end_date)
        assert len(chunks) > 0
        for chunk_start, chunk_end in chunks:
            assert chunk_start <= chunk_end
            assert chunk_start >= start_date
            assert chunk_end <= end_date

    def test_detect_gaps_for_symbol(self):
        extractor = gap_filler.GapFillerExtractor(["BTCUSDT"], "15m", "mongodb")
        mock_db_adapter = Mock()
        mock_db_adapter.find_gaps.return_value = [
            (
                datetime(2024, 1, 1, tzinfo=UTC),
                datetime(2024, 1, 2, tzinfo=UTC),
            )
        ]
        with patch("utils.time_utils.get_interval_minutes", return_value=15):
            gaps = extractor.detect_gaps_for_symbol("BTCUSDT", mock_db_adapter)
        assert len(gaps) == 1
        mock_db_adapter.find_gaps.assert_called()

    @patch("jobs.extract_klines_gap_filler.KlinesFetcher")
    @patch("models.kline.KlineModel")
    @patch("time.sleep")  # Ensure sleep is mocked
    @patch("random.uniform")  # Mock random delays
    @patch("jobs.extract_klines_gap_filler.retry_with_backoff")  # Mock retry logic
    def test_process_symbol_gaps(
        self,
        mock_retry,
        mock_random,
        mock_sleep,
        mock_kline_model_cls,
        mock_klines_fetcher_cls,
    ):
        # Mock random.uniform to return a small value
        mock_random.return_value = 0.1

        # Mock retry_with_backoff to just call the function directly
        def mock_retry_wrapper(func, *args, **kwargs):
            return func()

        mock_retry.side_effect = mock_retry_wrapper

        extractor = gap_filler.GapFillerExtractor(["BTCUSDT"], "15m", "mongodb")
        mock_binance_client = Mock()
        mock_db_adapter = Mock()
        gap_start = datetime(2024, 1, 1, tzinfo=UTC)
        gap_end = datetime(2024, 1, 2, tzinfo=UTC)
        mock_db_adapter.find_gaps.return_value = [(gap_start, gap_end)]
        mock_fetcher = Mock()

        class FakeKline:
            def model_dump(self):
                return {"open": 1}

        mock_fetcher.fetch_klines.return_value = [FakeKline(), FakeKline()]
        mock_klines_fetcher_cls.return_value = mock_fetcher
        mock_db_adapter.write.side_effect = lambda *args, **kwargs: 2

        with (
            patch.object(extractor, "get_start_date", return_value=gap_start),
            patch.object(extractor, "get_end_date", return_value=gap_end),
            patch(
                "jobs.extract_klines_gap_filler.get_adapter",
                return_value=mock_db_adapter,
            ),
        ):
            result = extractor.process_symbol_gaps("BTCUSDT", mock_binance_client)
        assert result["success"] is True
        assert result["gaps_found"] == 1
        assert result["gaps_filled"] == 1

    def test_run_gap_filling(self):
        extractor = gap_filler.GapFillerExtractor(["BTCUSDT"], "15m", "mongodb")
        mock_db_adapter = Mock()
        mock_db_adapter.find_gaps.return_value = []
        mock_binance_client = Mock()
        mock_fetcher = Mock()
        mock_fetcher.fetch_klines.return_value = []
        mock_binance_client.get_klines_fetcher.return_value = mock_fetcher

        with patch(
            "jobs.extract_klines_gap_filler.get_adapter", return_value=mock_db_adapter
        ):
            with patch(
                "jobs.extract_klines_gap_filler.BinanceClient",
                return_value=mock_binance_client,
            ):
                with patch("utils.time_utils.get_interval_minutes", return_value=15):
                    result = extractor.run_gap_filling()

        assert result["success"] is True
        assert result["total_symbols"] == 1
        assert result["symbols_processed"] == 1


class TestGapFillerDataManagerAdapter:
    """Gateway-adapter dispatch tests (#294).

    DataManagerAdapter is async; GapFillerExtractor is a synchronous class,
    so the job must route connect/find_gaps/write/disconnect through the
    *_sync bridge methods when (and only when) the resolved adapter is a
    DataManagerAdapter instance. Mysql/mongo/postgresql paths (exercised
    above with plain Mock()) must be completely unaffected.
    """

    def test_detect_gaps_for_symbol_normalizes_gateway_dict_shape(self):
        """DataManagerAdapter.find_gaps_sync() returns list[dict]; the job
        must normalize it to list[tuple[datetime, datetime]]."""
        extractor = gap_filler.GapFillerExtractor(["BTCUSDT"], "15m", "data_manager")
        gap_start = datetime(2024, 1, 1, tzinfo=UTC)
        gap_end = datetime(2024, 1, 2, tzinfo=UTC)

        mock_adapter = Mock(spec=gap_filler.DataManagerAdapter)
        mock_adapter.find_gaps_sync.return_value = [
            {
                "start_time": gap_start,
                "end_time": gap_end,
                "symbol": "BTCUSDT",
                "interval": "15m",
            }
        ]

        with patch.object(extractor, "get_start_date", return_value=gap_start):
            with patch.object(extractor, "get_end_date", return_value=gap_end):
                gaps = extractor.detect_gaps_for_symbol("BTCUSDT", mock_adapter)

        assert gaps == [(gap_start, gap_end)]
        mock_adapter.find_gaps_sync.assert_called_once()

    @patch("jobs.extract_klines_gap_filler.KlinesFetcher")
    @patch("time.sleep")
    @patch("random.uniform")
    @patch("jobs.extract_klines_gap_filler.retry_with_backoff")
    def test_process_symbol_gaps_uses_sync_bridge_for_gateway_adapter(
        self, mock_retry, mock_random, mock_sleep, mock_klines_fetcher_cls
    ):
        """connect/find_gaps/write/disconnect all route through the *_sync
        bridge methods (never the raw async methods) for a real
        DataManagerAdapter instance."""
        mock_random.return_value = 0.1

        def mock_retry_wrapper(func, *args, **kwargs):
            return func()

        mock_retry.side_effect = mock_retry_wrapper

        extractor = gap_filler.GapFillerExtractor(
            ["BTCUSDT"], "15m", "data_manager", db_uri="http://data-manager:80"
        )
        mock_binance_client = Mock()
        gap_start = datetime(2024, 1, 1, tzinfo=UTC)
        gap_end = datetime(2024, 1, 2, tzinfo=UTC)

        mock_adapter = Mock(spec=gap_filler.DataManagerAdapter)
        mock_adapter.find_gaps_sync.return_value = [
            {"start_time": gap_start, "end_time": gap_end}
        ]
        mock_adapter.write_batch.return_value = 2

        mock_fetcher = Mock()

        class FakeKline:
            def model_dump(self):
                return {"open": 1}

        mock_fetcher.fetch_klines.return_value = [FakeKline(), FakeKline()]
        mock_klines_fetcher_cls.return_value = mock_fetcher

        with (
            patch.object(extractor, "get_start_date", return_value=gap_start),
            patch.object(extractor, "get_end_date", return_value=gap_end),
            patch(
                "jobs.extract_klines_gap_filler.get_adapter",
                return_value=mock_adapter,
            ),
        ):
            result = extractor.process_symbol_gaps("BTCUSDT", mock_binance_client)

        assert result["success"] is True
        assert result["gaps_found"] == 1
        assert result["gaps_filled"] == 1

        mock_adapter.connect_sync.assert_called_once()
        mock_adapter.connect.assert_not_called()
        mock_adapter.find_gaps_sync.assert_called_once()
        mock_adapter.find_gaps.assert_not_called()
        mock_adapter.write_batch.assert_called_once()
        mock_adapter.write.assert_not_called()
        mock_adapter.disconnect_sync.assert_called_once()
        mock_adapter.disconnect.assert_not_called()


class TestParseArguments:
    def test_default_arguments(self):
        with patch("sys.argv", ["extract_klines_gap_filler.py"]):
            args = gap_filler.parse_arguments()
            assert args.period == gap_filler.constants.DEFAULT_PERIOD
            assert args.max_workers == 3
            assert args.batch_size == gap_filler.constants.DB_BATCH_SIZE
            assert args.weekly_chunk_days == 7
            assert args.max_gap_size_days == 365
            assert args.db_adapter == gap_filler.constants.DB_ADAPTER
            assert args.log_level == gap_filler.constants.LOG_LEVEL
            assert args.dry_run is False

    def test_data_manager_is_valid_db_adapter_choice(self):
        """Per #294: data_manager must be an accepted --db-adapter choice."""
        with patch(
            "sys.argv",
            ["extract_klines_gap_filler.py", "--db-adapter", "data_manager"],
        ):
            args = gap_filler.parse_arguments()
            assert args.db_adapter == "data_manager"

    def test_process_symbol_gaps_resolves_data_manager_uri_when_unset(self):
        """Per #294: when GapFillerExtractor.db_uri is falsy, the
        data_manager branch of the db_uri resolution must fire."""
        extractor = gap_filler.GapFillerExtractor(
            ["BTCUSDT"], "15m", "data_manager", db_uri=None
        )
        mock_adapter = Mock(spec=gap_filler.DataManagerAdapter)
        mock_adapter.find_gaps_sync.return_value = []

        with patch("jobs.extract_klines_gap_filler.get_adapter") as mock_get_adapter:
            mock_get_adapter.return_value = mock_adapter
            extractor.process_symbol_gaps("BTCUSDT", Mock())

        mock_get_adapter.assert_called_once_with(
            "data_manager", gap_filler.constants.DATA_MANAGER_URL
        )

    def test_custom_arguments(self):
        with patch(
            "sys.argv",
            [
                "extract_klines_gap_filler.py",
                "--period",
                "1h",
                "--symbols",
                "BTCUSDT,ETHUSDT",
                "--max-workers",
                "5",
                "--batch-size",
                "500",
                "--weekly-chunk-days",
                "3",
                "--max-gap-size-days",
                "15",
                "--db-adapter",
                "mysql",
                "--db-uri",
                "mysql://test",
                "--log-level",
                "DEBUG",
                "--dry-run",
            ],
        ):
            args = gap_filler.parse_arguments()
            assert args.period == "1h"
            assert args.symbols == "BTCUSDT,ETHUSDT"
            assert args.max_workers == 5
            assert args.batch_size == 500
            assert args.weekly_chunk_days == 3
            assert args.max_gap_size_days == 15
            assert args.db_adapter == "mysql"
            assert args.db_uri == "mysql://test"
            assert args.log_level == "DEBUG"
            assert args.dry_run is True


class TestMainFunction:
    def _run_main_and_catch_exit(self, *args, **kwargs):
        try:
            gap_filler.main()
        except SystemExit as e:
            return e.code
        return None

    @patch("jobs.extract_klines_gap_filler.parse_arguments")
    @patch("jobs.extract_klines_gap_filler.setup_logging")
    @patch("jobs.extract_klines_gap_filler.get_logger")
    @patch("jobs.extract_klines_gap_filler.log_extraction_start")
    @patch("jobs.extract_klines_gap_filler.log_extraction_completion")
    @patch("jobs.extract_klines_gap_filler.GapFillerExtractor")
    def test_main_success(
        self,
        mock_gap_filler_cls,
        mock_log_completion,
        mock_log_start,
        mock_get_logger,
        mock_setup_logging,
        mock_parse_args,
    ):
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        mock_args = Mock()
        mock_args.symbols = None
        mock_args.period = "15m"
        mock_args.max_workers = 3
        mock_args.batch_size = 1000
        mock_args.weekly_chunk_days = 7
        mock_args.max_gap_size_days = 30
        mock_args.db_adapter = "mongodb"
        mock_args.db_uri = None
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_parse_args.return_value = mock_args

        mock_gap_filler = Mock()
        mock_gap_filler.run_gap_filling.return_value = {
            "success": True,
            "total_symbols": 1,
            "symbols_processed": 1,
            "symbols_failed": 0,
            "total_gaps_found": 0,
            "total_gaps_filled": 0,
            "total_records_fetched": 0,
            "total_records_written": 0,
            "total_weekly_chunks_processed": 0,
            "duration_seconds": 1.0,
            "errors": [],
        }
        mock_gap_filler_cls.return_value = mock_gap_filler

        exit_code = self._run_main_and_catch_exit()
        assert exit_code == 0
        mock_gap_filler.run_gap_filling.assert_called()
        mock_log_completion.assert_called()

    @patch("jobs.extract_klines_gap_filler.parse_arguments")
    @patch("jobs.extract_klines_gap_filler.setup_logging")
    @patch("jobs.extract_klines_gap_filler.get_logger")
    @patch("jobs.extract_klines_gap_filler.log_extraction_start")
    @patch("jobs.extract_klines_gap_filler.log_extraction_completion")
    @patch("jobs.extract_klines_gap_filler.GapFillerExtractor")
    def test_main_mysql_adapter_logs_deprecation_warning(
        self,
        mock_gap_filler_cls,
        mock_log_completion,
        mock_log_start,
        mock_get_logger,
        mock_setup_logging,
        mock_parse_args,
    ):
        """Per #294: selecting the direct MySQL adapter must log a
        deprecation warning pointing at --db-adapter=data_manager."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        mock_args = Mock()
        mock_args.symbols = None
        mock_args.period = "15m"
        mock_args.max_workers = 3
        mock_args.batch_size = 1000
        mock_args.weekly_chunk_days = 7
        mock_args.max_gap_size_days = 30
        mock_args.db_adapter = "mysql"
        mock_args.db_uri = None
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_parse_args.return_value = mock_args

        mock_gap_filler = Mock()
        mock_gap_filler.run_gap_filling.return_value = {
            "success": True,
            "total_symbols": 1,
            "symbols_processed": 1,
            "symbols_failed": 0,
            "total_gaps_found": 0,
            "total_gaps_filled": 0,
            "total_records_fetched": 0,
            "total_records_written": 0,
            "total_weekly_chunks_processed": 0,
            "duration_seconds": 1.0,
            "errors": [],
        }
        mock_gap_filler_cls.return_value = mock_gap_filler

        exit_code = self._run_main_and_catch_exit()
        assert exit_code == 0
        assert any(
            "DEPRECATED" in call.args[0] for call in mock_logger.warning.call_args_list
        )

    @patch("jobs.extract_klines_gap_filler.parse_arguments")
    @patch("jobs.extract_klines_gap_filler.setup_logging")
    @patch("jobs.extract_klines_gap_filler.get_logger")
    @patch("jobs.extract_klines_gap_filler.log_extraction_start")
    @patch("jobs.extract_klines_gap_filler.log_extraction_completion")
    @patch("jobs.extract_klines_gap_filler.GapFillerExtractor")
    def test_main_data_manager_adapter_resolves_uri(
        self,
        mock_gap_filler_cls,
        mock_log_completion,
        mock_log_start,
        mock_get_logger,
        mock_setup_logging,
        mock_parse_args,
    ):
        """Per #294: --db-adapter=data_manager resolves DATA_MANAGER_URL
        when --db-uri is not explicitly passed."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        mock_args = Mock()
        mock_args.symbols = None
        mock_args.period = "15m"
        mock_args.max_workers = 3
        mock_args.batch_size = 1000
        mock_args.weekly_chunk_days = 7
        mock_args.max_gap_size_days = 30
        mock_args.db_adapter = "data_manager"
        mock_args.db_uri = None
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_parse_args.return_value = mock_args

        mock_gap_filler = Mock()
        mock_gap_filler.run_gap_filling.return_value = {
            "success": True,
            "total_symbols": 1,
            "symbols_processed": 1,
            "symbols_failed": 0,
            "total_gaps_found": 0,
            "total_gaps_filled": 0,
            "total_records_fetched": 0,
            "total_records_written": 0,
            "total_weekly_chunks_processed": 0,
            "duration_seconds": 1.0,
            "errors": [],
        }
        mock_gap_filler_cls.return_value = mock_gap_filler

        exit_code = self._run_main_and_catch_exit()
        assert exit_code == 0
        _, kwargs = mock_gap_filler_cls.call_args
        assert kwargs["db_uri"] == gap_filler.constants.DATA_MANAGER_URL

    @patch("jobs.extract_klines_gap_filler.parse_arguments")
    @patch("jobs.extract_klines_gap_filler.setup_logging")
    @patch("jobs.extract_klines_gap_filler.get_logger")
    @patch("jobs.extract_klines_gap_filler.log_extraction_start")
    @patch("jobs.extract_klines_gap_filler.log_extraction_completion")
    @patch("jobs.extract_klines_gap_filler.GapFillerExtractor")
    def test_main_failure(
        self,
        mock_gap_filler_cls,
        mock_log_completion,
        mock_log_start,
        mock_get_logger,
        mock_setup_logging,
        mock_parse_args,
    ):
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        mock_args = Mock()
        mock_args.symbols = None
        mock_args.period = "15m"
        mock_args.max_workers = 3
        mock_args.batch_size = 1000
        mock_args.weekly_chunk_days = 7
        mock_args.max_gap_size_days = 30
        mock_args.db_adapter = "mongodb"
        mock_args.db_uri = None
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_parse_args.return_value = mock_args

        mock_gap_filler = Mock()
        mock_gap_filler.run_gap_filling.return_value = {
            "success": False,
            "total_symbols": 1,
            "symbols_processed": 0,
            "symbols_failed": 1,
            "total_gaps_found": 0,
            "total_gaps_filled": 0,
            "total_records_fetched": 0,
            "total_records_written": 0,
            "total_weekly_chunks_processed": 0,
            "duration_seconds": 1.0,
            "errors": ["test error"],
        }
        mock_gap_filler_cls.return_value = mock_gap_filler

        exit_code = self._run_main_and_catch_exit()
        assert exit_code == 1
        mock_gap_filler.run_gap_filling.assert_called()
        mock_log_completion.assert_called()

    @patch("jobs.extract_klines_gap_filler.parse_arguments")
    @patch("jobs.extract_klines_gap_filler.setup_logging")
    @patch("jobs.extract_klines_gap_filler.get_logger")
    @patch("jobs.extract_klines_gap_filler.log_extraction_start")
    @patch("jobs.extract_klines_gap_filler.log_extraction_completion")
    @patch("jobs.extract_klines_gap_filler.GapFillerExtractor")
    def test_main_keyboard_interrupt(
        self,
        mock_gap_filler_cls,
        mock_log_completion,
        mock_log_start,
        mock_get_logger,
        mock_setup_logging,
        mock_parse_args,
    ):
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        mock_args = Mock()
        mock_args.symbols = None
        mock_args.period = "15m"
        mock_args.max_workers = 3
        mock_args.batch_size = 1000
        mock_args.weekly_chunk_days = 7
        mock_args.max_gap_size_days = 30
        mock_args.db_adapter = "mongodb"
        mock_args.db_uri = None
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_parse_args.return_value = mock_args

        mock_gap_filler = Mock()
        # Make the run_gap_filling method raise KeyboardInterrupt
        mock_gap_filler.run_gap_filling.side_effect = KeyboardInterrupt()
        mock_gap_filler_cls.return_value = mock_gap_filler

        with patch("sys.exit") as mock_exit:
            gap_filler._main_impl()
            mock_exit.assert_called_with(130)
            mock_logger.info.assert_called_with("⚠️ Gap filling interrupted by user")

    @patch("jobs.extract_klines_gap_filler.parse_arguments")
    @patch("jobs.extract_klines_gap_filler.setup_logging")
    @patch("jobs.extract_klines_gap_filler.get_logger")
    @patch("jobs.extract_klines_gap_filler.log_extraction_start")
    @patch("jobs.extract_klines_gap_filler.log_extraction_completion")
    @patch("jobs.extract_klines_gap_filler.GapFillerExtractor")
    def test_main_general_exception(
        self,
        mock_gap_filler_cls,
        mock_log_completion,
        mock_log_start,
        mock_get_logger,
        mock_setup_logging,
        mock_parse_args,
    ):
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        mock_args = Mock()
        mock_args.symbols = None
        mock_args.period = "15m"
        mock_args.max_workers = 3
        mock_args.batch_size = 1000
        mock_args.weekly_chunk_days = 7
        mock_args.max_gap_size_days = 30
        mock_args.db_adapter = "mongodb"
        mock_args.db_uri = None
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_parse_args.return_value = mock_args

        mock_gap_filler = Mock()
        # Make the run_gap_filling method raise an exception
        mock_gap_filler.run_gap_filling.side_effect = Exception("test error")
        mock_gap_filler_cls.return_value = mock_gap_filler

        with patch("sys.exit") as mock_exit:
            with patch("traceback.print_exc"):
                gap_filler._main_impl()
                mock_exit.assert_called_with(1)
                mock_logger.error.assert_called_with(
                    "💥 Fatal error during gap filling: test error"
                )
