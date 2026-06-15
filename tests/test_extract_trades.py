#!/usr/bin/env python3
"""
Unit tests for jobs/extract_trades.py
"""

import os
import sys
from unittest.mock import Mock, patch

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import jobs.extract_trades as extract_trades  # noqa: E402


class TestParseArguments:
    def test_default_arguments(self):
        with patch("sys.argv", ["extract_trades.py"]):
            args = extract_trades.parse_arguments()
            assert args.limit == 1000
            assert args.historical is False
            assert args.db_adapter in ["mongodb", "mysql", "data_manager"]
            assert args.batch_size == extract_trades.constants.DB_BATCH_SIZE
            assert args.log_level == extract_trades.constants.LOG_LEVEL
            assert args.dry_run is False

    def test_data_manager_adapter_choice(self):
        with patch("sys.argv", ["extract_trades.py", "--db-adapter", "data_manager"]):
            args = extract_trades.parse_arguments()
            assert args.db_adapter == "data_manager"

    def test_custom_arguments(self):
        with patch(
            "sys.argv",
            [
                "extract_trades.py",
                "--symbol",
                "BTCUSDT",
                "--limit",
                "500",
                "--historical",
                "--from-id",
                "12345",
                "--db-adapter",
                "mysql",
                "--db-uri",
                "mysql://test",
                "--batch-size",
                "50",
                "--log-level",
                "DEBUG",
                "--dry-run",
            ],
        ):
            args = extract_trades.parse_arguments()
            assert args.symbol == "BTCUSDT"
            assert args.limit == 500
            assert args.historical is True
            assert args.from_id == 12345
            assert args.db_adapter == "mysql"
            assert args.db_uri == "mysql://test"
            assert args.batch_size == 50
            assert args.log_level == "DEBUG"
            assert args.dry_run is True


class TestMain:
    def _run_main_and_catch_exit(self, *args, **kwargs):
        try:
            extract_trades.main()
        except SystemExit as e:
            return e.code
        return None

    @patch("jobs.extract_trades.parse_arguments")
    @patch("jobs.extract_trades.setup_logging")
    @patch("jobs.extract_trades.log_extraction_start")
    @patch("jobs.extract_trades.log_extraction_completion")
    @patch("jobs.extract_trades.get_adapter")
    @patch("jobs.extract_trades.BinanceClient")
    @patch("jobs.extract_trades.TradesFetcher")
    def test_main_recent_trades(
        self,
        mock_fetcher_cls,
        mock_client_cls,
        mock_get_adapter,
        mock_log_completion,
        mock_log_start,
        mock_setup_logging,
        mock_parse_args,
    ):
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_args = Mock()
        mock_args.symbol = None
        mock_args.symbols = "BTCUSDT,ETHUSDT"
        mock_args.limit = 1000
        mock_args.historical = False
        mock_args.from_id = None
        mock_args.db_adapter = "mongodb"
        mock_args.db_uri = None
        mock_args.batch_size = 100
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_parse_args.return_value = mock_args
        mock_get_adapter.return_value.__enter__.return_value = (
            mock_get_adapter.return_value
        )
        mock_get_adapter.return_value.ensure_indexes.return_value = None
        mock_fetcher = Mock()
        mock_fetcher.fetch_recent_trades.return_value = [Mock(), Mock()]
        mock_fetcher_cls.return_value = mock_fetcher
        mock_client_cls.return_value = Mock()
        # Run main and catch exit
        exit_code = self._run_main_and_catch_exit()
        assert exit_code == 0
        mock_fetcher.fetch_recent_trades.assert_called()
        mock_get_adapter.return_value.write_batch.assert_called()
        mock_log_completion.assert_called()

    @patch("jobs.extract_trades.parse_arguments")
    @patch("jobs.extract_trades.setup_logging")
    @patch("jobs.extract_trades.log_extraction_start")
    @patch("jobs.extract_trades.log_extraction_completion")
    @patch("jobs.extract_trades.get_adapter")
    @patch("jobs.extract_trades.BinanceClient")
    @patch("jobs.extract_trades.TradesFetcher")
    def test_main_historical_trades(
        self,
        mock_fetcher_cls,
        mock_client_cls,
        mock_get_adapter,
        mock_log_completion,
        mock_log_start,
        mock_setup_logging,
        mock_parse_args,
    ):
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_args = Mock()
        mock_args.symbol = None
        mock_args.symbols = "BTCUSDT"
        mock_args.limit = 1000
        mock_args.historical = True
        mock_args.from_id = None
        mock_args.db_adapter = "mongodb"
        mock_args.db_uri = None
        mock_args.batch_size = 100
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_parse_args.return_value = mock_args
        mock_get_adapter.return_value.__enter__.return_value = (
            mock_get_adapter.return_value
        )
        mock_get_adapter.return_value.ensure_indexes.return_value = None
        mock_fetcher = Mock()
        mock_fetcher.fetch_historical_trades.return_value = [Mock()]
        mock_fetcher_cls.return_value = mock_fetcher
        mock_client_cls.return_value = Mock()
        # Run main and catch exit
        exit_code = self._run_main_and_catch_exit()
        assert exit_code == 0
        mock_fetcher.fetch_historical_trades.assert_called()
        mock_get_adapter.return_value.write_batch.assert_called()
        mock_log_completion.assert_called()

    @patch("jobs.extract_trades.parse_arguments")
    @patch("jobs.extract_trades.setup_logging")
    @patch("jobs.extract_trades.log_extraction_start")
    @patch("jobs.extract_trades.log_extraction_completion")
    @patch("jobs.extract_trades.get_adapter")
    @patch("jobs.extract_trades.BinanceClient")
    @patch("jobs.extract_trades.TradesFetcher")
    def test_main_historical_trades_since_id(
        self,
        mock_fetcher_cls,
        mock_client_cls,
        mock_get_adapter,
        mock_log_completion,
        mock_log_start,
        mock_setup_logging,
        mock_parse_args,
    ):
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_args = Mock()
        mock_args.symbol = None
        mock_args.symbols = "BTCUSDT"
        mock_args.limit = 1000
        mock_args.historical = True
        mock_args.from_id = 12345
        mock_args.db_adapter = "mongodb"
        mock_args.db_uri = None
        mock_args.batch_size = 100
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_parse_args.return_value = mock_args
        mock_get_adapter.return_value.__enter__.return_value = (
            mock_get_adapter.return_value
        )
        mock_get_adapter.return_value.ensure_indexes.return_value = None
        mock_fetcher = Mock()
        mock_fetcher.fetch_trades_since_id.return_value = [Mock()]
        mock_fetcher_cls.return_value = mock_fetcher
        mock_client_cls.return_value = Mock()
        # Run main and catch exit
        exit_code = self._run_main_and_catch_exit()
        assert exit_code == 0
        mock_fetcher.fetch_trades_since_id.assert_called()
        mock_get_adapter.return_value.write_batch.assert_called()
        mock_log_completion.assert_called()

    @patch("jobs.extract_trades.parse_arguments")
    @patch("jobs.extract_trades.setup_logging")
    @patch("jobs.extract_trades.log_extraction_start")
    @patch("jobs.extract_trades.log_extraction_completion")
    @patch("jobs.extract_trades.get_adapter")
    @patch("jobs.extract_trades.BinanceClient")
    @patch("jobs.extract_trades.TradesFetcher")
    def test_main_dry_run(
        self,
        mock_fetcher_cls,
        mock_client_cls,
        mock_get_adapter,
        mock_log_completion,
        mock_log_start,
        mock_setup_logging,
        mock_parse_args,
    ):
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_args = Mock()
        mock_args.symbol = None
        mock_args.symbols = "BTCUSDT"
        mock_args.limit = 1000
        mock_args.historical = False
        mock_args.from_id = None
        mock_args.db_adapter = "mongodb"
        mock_args.db_uri = None
        mock_args.batch_size = 100
        mock_args.log_level = "INFO"
        mock_args.dry_run = True
        mock_parse_args.return_value = mock_args
        mock_get_adapter.return_value.__enter__.return_value = (
            mock_get_adapter.return_value
        )
        mock_get_adapter.return_value.ensure_indexes.return_value = None
        mock_fetcher = Mock()
        mock_fetcher.fetch_recent_trades.return_value = [Mock(), Mock()]
        mock_fetcher_cls.return_value = mock_fetcher
        mock_client_cls.return_value = Mock()
        # Run main and catch exit
        exit_code = self._run_main_and_catch_exit()
        assert exit_code == 0
        mock_fetcher.fetch_recent_trades.assert_called()
        mock_get_adapter.return_value.write_batch.assert_not_called()
        mock_log_completion.assert_called()

    @patch("jobs.extract_trades.parse_arguments")
    @patch("jobs.extract_trades.setup_logging")
    @patch("jobs.extract_trades.log_extraction_start")
    @patch("jobs.extract_trades.log_extraction_completion")
    @patch("jobs.extract_trades.get_adapter")
    @patch("jobs.extract_trades.BinanceClient")
    @patch("jobs.extract_trades.TradesFetcher")
    def test_main_error_handling(
        self,
        mock_fetcher_cls,
        mock_client_cls,
        mock_get_adapter,
        mock_log_completion,
        mock_log_start,
        mock_setup_logging,
        mock_parse_args,
    ):
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_args = Mock()
        mock_args.symbol = None
        mock_args.symbols = "BTCUSDT"
        mock_args.limit = 1000
        mock_args.historical = False
        mock_args.from_id = None
        mock_args.db_adapter = "mongodb"
        mock_args.db_uri = None
        mock_args.batch_size = 100
        mock_args.log_level = "INFO"
        mock_args.dry_run = False
        mock_parse_args.return_value = mock_args
        mock_get_adapter.side_effect = Exception("DB error")
        with patch("sys.exit") as mock_exit:
            extract_trades.main()
            mock_exit.assert_called()


class TestLogExtractionStartCallSites:
    """Regression: AC4 — every job's `log_extraction_start(...)` call must use
    the kwarg name from the function signature (`log=`), not the historical
    `logger=`. The bug in #269 slipped past CI because `test_main_*` patched
    `log_extraction_start` away, so the call-site mismatch never raised.

    This test parses each `jobs/extract_*.py` AST and asserts no caller passes
    a `logger=` keyword to `log_extraction_start`.
    """

    def test_no_caller_uses_logger_kwarg(self):
        import ast
        import glob
        import inspect

        from utils.logger import log_extraction_start

        # Sanity: the canonical kwarg in the signature is `log`.
        sig = inspect.signature(log_extraction_start)
        assert "log" in sig.parameters
        assert "logger" not in sig.parameters

        jobs_dir = os.path.join(project_root, "jobs")
        offenders = []
        for path in sorted(glob.glob(os.path.join(jobs_dir, "extract_*.py"))):
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name != "log_extraction_start":
                    continue
                for kw in node.keywords:
                    if kw.arg == "logger":
                        offenders.append(f"{path}:{node.lineno}")

        assert not offenders, (
            "log_extraction_start() must be called with `log=`, not `logger=`. "
            f"Offenders: {offenders}"
        )


class TestDbUriResolution:
    """Regression: k8s#861 — when DB_ADAPTER=data_manager the job was passing
    constants.MYSQL_URI (a mysql:// DSN) to the data_manager adapter's HTTP
    client, causing an instant crash on health-check.  The fix adds an explicit
    branch: data_manager → DATA_MANAGER_URL."""

    @patch("jobs.extract_trades.parse_arguments")
    @patch("jobs.extract_trades.setup_logging")
    @patch("jobs.extract_trades.log_extraction_start")
    @patch("jobs.extract_trades.log_extraction_completion")
    @patch("jobs.extract_trades.get_adapter")
    @patch("jobs.extract_trades.BinanceClient")
    @patch("jobs.extract_trades.TradesFetcher")
    def test_data_manager_adapter_receives_http_url(
        self,
        mock_fetcher_cls,
        mock_client_cls,
        mock_get_adapter,
        mock_log_completion,
        mock_log_start,
        mock_setup_logging,
        mock_parse_args,
    ):
        mock_setup_logging.return_value = Mock()
        mock_args = Mock()
        mock_args.symbol = None
        mock_args.symbols = "BTCUSDT"
        mock_args.limit = 100
        mock_args.historical = False
        mock_args.from_id = None
        mock_args.db_adapter = "data_manager"
        mock_args.db_uri = None
        mock_args.batch_size = 100
        mock_args.log_level = "INFO"
        mock_args.dry_run = True
        mock_parse_args.return_value = mock_args
        mock_get_adapter.return_value.__enter__.return_value = (
            mock_get_adapter.return_value
        )
        mock_get_adapter.return_value.ensure_indexes.return_value = None
        mock_fetcher_cls.return_value.fetch_recent_trades.return_value = []

        try:
            extract_trades.main()
        except SystemExit:
            pass

        call_args = mock_get_adapter.call_args
        assert call_args is not None
        actual_uri = (
            call_args[0][1]
            if len(call_args[0]) > 1
            else call_args[1].get("connection_string")
        )
        assert actual_uri is not None
        assert actual_uri.startswith("http"), (
            f"data_manager adapter must receive an HTTP URL, got: {actual_uri!r}"
        )
        assert "mysql://" not in actual_uri, (
            f"data_manager adapter must not receive a MySQL DSN, got: {actual_uri!r}"
        )

    @patch("jobs.extract_trades.parse_arguments")
    @patch("jobs.extract_trades.setup_logging")
    @patch("jobs.extract_trades.log_extraction_start")
    @patch("jobs.extract_trades.log_extraction_completion")
    @patch("jobs.extract_trades.get_adapter")
    @patch("jobs.extract_trades.BinanceClient")
    @patch("jobs.extract_trades.TradesFetcher")
    def test_mysql_adapter_receives_mysql_uri(
        self,
        mock_fetcher_cls,
        mock_client_cls,
        mock_get_adapter,
        mock_log_completion,
        mock_log_start,
        mock_setup_logging,
        mock_parse_args,
    ):
        mock_setup_logging.return_value = Mock()
        mock_args = Mock()
        mock_args.symbol = None
        mock_args.symbols = "BTCUSDT"
        mock_args.limit = 100
        mock_args.historical = False
        mock_args.from_id = None
        mock_args.db_adapter = "mysql"
        mock_args.db_uri = None
        mock_args.batch_size = 100
        mock_args.log_level = "INFO"
        mock_args.dry_run = True
        mock_parse_args.return_value = mock_args
        mock_get_adapter.return_value.__enter__.return_value = (
            mock_get_adapter.return_value
        )
        mock_get_adapter.return_value.ensure_indexes.return_value = None
        mock_fetcher_cls.return_value.fetch_recent_trades.return_value = []

        try:
            extract_trades.main()
        except SystemExit:
            pass

        call_args = mock_get_adapter.call_args
        actual_uri = (
            call_args[0][1]
            if len(call_args[0]) > 1
            else call_args[1].get("connection_string")
        )
        assert actual_uri == extract_trades.constants.MYSQL_URI
