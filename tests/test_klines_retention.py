#!/usr/bin/env python3
"""
Unit tests for jobs/klines_retention.py (#282).
"""

import os
import sys
from datetime import UTC, datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import jobs.klines_retention as retention  # noqa: E402


class TestPruneTable:
    def test_dry_run_counts_but_does_not_delete(self):
        adapter = Mock()
        adapter.get_record_count.return_value = 42
        logger = Mock()
        cutoff = datetime(2026, 1, 1, tzinfo=UTC)

        result = retention.prune_table(adapter, "klines_m5", cutoff, True, logger)

        assert result == 42
        adapter.get_record_count.assert_called_once_with(
            "klines_m5", start=retention._EPOCH_START, end=cutoff
        )
        adapter.delete_range.assert_not_called()

    def test_live_run_deletes_range(self):
        adapter = Mock()
        adapter.delete_range.return_value = 17
        logger = Mock()
        cutoff = datetime(2026, 1, 1, tzinfo=UTC)

        result = retention.prune_table(adapter, "klines_m5", cutoff, False, logger)

        assert result == 17
        adapter.delete_range.assert_called_once_with(
            "klines_m5", start=retention._EPOCH_START, end=cutoff
        )
        adapter.get_record_count.assert_not_called()


class TestRunRetention:
    @patch("jobs.klines_retention.get_adapter")
    def test_prunes_all_requested_periods(self, mock_get_adapter):
        adapter = MagicMock()
        adapter.delete_range.side_effect = [5, 10]
        mock_get_adapter.return_value = adapter
        logger = Mock()

        result = retention.run_retention(
            periods=["1m", "5m"],
            retention_days=90,
            db_adapter_name="mysql",
            db_uri="mysql://user:pass@localhost/db",
            dry_run=False,
            logger=logger,
        )

        assert result["success"] is True
        assert result["total_deleted"] == 15
        assert result["tables"] == {"klines_m1": 5, "klines_m5": 10}
        assert result["errors"] == []
        adapter.connect.assert_called_once()
        adapter.disconnect.assert_called_once()

    @patch("jobs.klines_retention.get_adapter")
    def test_one_bad_table_does_not_abort_the_run(self, mock_get_adapter):
        adapter = MagicMock()
        adapter.delete_range.side_effect = [Exception("boom"), 3]
        mock_get_adapter.return_value = adapter
        logger = Mock()

        result = retention.run_retention(
            periods=["1m", "5m"],
            retention_days=90,
            db_adapter_name="mysql",
            db_uri="mysql://user:pass@localhost/db",
            dry_run=False,
            logger=logger,
        )

        assert result["success"] is False
        assert len(result["errors"]) == 1
        assert result["tables"] == {"klines_m5": 3}
        adapter.disconnect.assert_called_once()

    @patch("jobs.klines_retention.get_adapter")
    def test_disconnects_even_on_connect_success_but_prune_exception(
        self, mock_get_adapter
    ):
        adapter = MagicMock()
        adapter.delete_range.side_effect = Exception("db gone")
        mock_get_adapter.return_value = adapter
        logger = Mock()

        result = retention.run_retention(
            periods=["1m"],
            retention_days=30,
            db_adapter_name="mysql",
            db_uri="mysql://user:pass@localhost/db",
            dry_run=False,
            logger=logger,
        )

        assert result["success"] is False
        adapter.disconnect.assert_called_once()


class TestParseArguments:
    def test_defaults(self):
        with patch.object(sys, "argv", ["klines_retention.py"]):
            args = retention.parse_arguments()
        assert args.retention_days == retention.DEFAULT_RETENTION_DAYS
        assert args.db_adapter == "mysql"
        assert args.dry_run is False
        assert args.periods is None

    def test_custom_flags(self):
        argv = [
            "klines_retention.py",
            "--periods",
            "1m,5m",
            "--retention-days",
            "30",
            "--dry-run",
        ]
        with patch.object(sys, "argv", argv):
            args = retention.parse_arguments()
        assert args.periods == "1m,5m"
        assert args.retention_days == 30
        assert args.dry_run is True


class TestMain:
    @patch("jobs.klines_retention.flush_telemetry")
    @patch("jobs.klines_retention.run_retention")
    @patch("jobs.klines_retention.setup_logging")
    def test_main_exits_zero_on_success(
        self, _mock_setup_logging, mock_run_retention, _mock_flush
    ):
        mock_run_retention.return_value = {
            "success": True,
            "total_deleted": 7,
            "tables": {"klines_m1": 7},
            "errors": [],
        }
        with patch.object(sys, "argv", ["klines_retention.py", "--dry-run"]):
            with pytest.raises(SystemExit) as exc_info:
                retention.main()
        assert exc_info.value.code == 0

    @patch("jobs.klines_retention.flush_telemetry")
    @patch("jobs.klines_retention.run_retention")
    @patch("jobs.klines_retention.setup_logging")
    def test_main_exits_one_on_errors(
        self, _mock_setup_logging, mock_run_retention, _mock_flush
    ):
        mock_run_retention.return_value = {
            "success": False,
            "total_deleted": 0,
            "tables": {},
            "errors": ["klines_m1: boom"],
        }
        with patch.object(sys, "argv", ["klines_retention.py"]):
            with pytest.raises(SystemExit) as exc_info:
                retention.main()
        assert exc_info.value.code == 1

    @patch("jobs.klines_retention.flush_telemetry")
    @patch("jobs.klines_retention.run_retention", side_effect=Exception("fatal"))
    @patch("jobs.klines_retention.setup_logging")
    def test_main_exits_one_on_fatal_exception(
        self, _mock_setup_logging, _mock_run_retention, _mock_flush
    ):
        with patch.object(sys, "argv", ["klines_retention.py"]):
            with pytest.raises(SystemExit) as exc_info:
                retention.main()
        assert exc_info.value.code == 1
