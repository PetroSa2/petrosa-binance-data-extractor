#!/usr/bin/env python3
"""
Unit tests for the MongoDB ``candles_*`` dual-write path of the gap filler.

Covers PetroSa2/petrosa-binance-data-extractor#300:

- AC1: the gap filler can write into the Mongo ``candles_*`` collections.
- AC2: dual-write is configurable (env default + explicit CLI override) and is
  OFF unless asked for.
- AC3: the ``binance_extractor_gaps_filled_mongodb_total`` metric is emitted.
- AC5: this file.

The standing rule inherited from petrosa-data-manager#274/#287 — never write
to the Mongo candle namespace without a bound AND an off-flag — is what the
budget tests below defend.
"""

import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

try:
    from datetime import UTC
except ImportError:  # pragma: no cover - Python < 3.11 fallback
    from datetime import timezone

    UTC = timezone.utc  # noqa: UP017
from unittest.mock import Mock, patch

import pytest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import constants  # noqa: E402
import jobs.extract_klines_gap_filler as gap_filler  # noqa: E402
from models.candle import CandleModel, candle_collection_name  # noqa: E402
from models.kline import KlineModel  # noqa: E402

UTC = UTC


def make_kline(
    symbol: str = "BTCUSDT",
    interval: str = "5m",
    minute: int = 0,
) -> KlineModel:
    """Build a realistic KlineModel for the mapping/mirroring tests."""
    open_time = datetime(2026, 9, 1, 0, minute, tzinfo=UTC)
    close_time = datetime(2026, 9, 1, 0, minute + 4, 59, tzinfo=UTC)
    return KlineModel(
        symbol=symbol,
        interval=interval,
        timestamp=open_time,
        open_time=open_time,
        close_time=close_time,
        open_price=Decimal("100.0"),
        high_price=Decimal("110.0"),
        low_price=Decimal("95.0"),
        close_price=Decimal("105.0"),
        volume=Decimal("12.5"),
        quote_asset_volume=Decimal("1300.0"),
        number_of_trades=42,
        taker_buy_base_asset_volume=Decimal("6.0"),
        taker_buy_quote_asset_volume=Decimal("640.0"),
    )


def make_extractor(**kwargs) -> gap_filler.GapFillerExtractor:
    defaults = {
        "symbols": ["BTCUSDT"],
        "period": "5m",
        "db_adapter_name": "data_manager",
        "candles_dual_write": True,
        "candles_max_records": 1000,
    }
    defaults.update(kwargs)
    return gap_filler.GapFillerExtractor(**defaults)


class TestCandleCollectionNaming:
    def test_collection_name_matches_data_manager_contract(self):
        assert candle_collection_name("btcusdt", "5m") == "candles_BTCUSDT_5m"

    def test_extractor_uses_its_own_period(self):
        extractor = make_extractor(period="1h")
        assert extractor.get_candles_collection_name("ethusdt") == "candles_ETHUSDT_1h"

    def test_candle_model_exposes_collection_name(self):
        candle = CandleModel.from_kline(make_kline(interval="15m"))
        assert candle.collection_name == "candles_BTCUSDT_15m"


class TestCandleMapping:
    def test_kline_projects_onto_canonical_candle_fields(self):
        candle = CandleModel.from_kline(make_kline())
        assert candle.symbol == "BTCUSDT"
        assert candle.timeframe == "5m"
        assert candle.open == Decimal("100.0")
        assert candle.high == Decimal("110.0")
        assert candle.low == Decimal("95.0")
        assert candle.close == Decimal("105.0")
        assert candle.volume == Decimal("12.5")
        assert candle.quote_volume == Decimal("1300.0")
        assert candle.trades_count == 42

    def test_timestamp_uses_open_time_not_close_time(self):
        kline = make_kline()
        candle = CandleModel.from_kline(kline)
        assert candle.timestamp == kline.open_time
        assert candle.timestamp != kline.close_time

    def test_to_dict_is_json_serializable_and_keeps_dedup_keys(self):
        doc = CandleModel.from_kline(make_kline()).to_dict()
        # data-manager derives _id from symbol+timestamp; both must survive.
        assert doc["symbol"] == "BTCUSDT"
        assert isinstance(doc["timestamp"], str)
        assert "id" not in doc

    def test_unsupported_timeframe_is_rejected(self):
        with pytest.raises(ValueError) as exc_info:
            CandleModel(
                symbol="BTCUSDT",
                timestamp=datetime(2026, 9, 1, tzinfo=UTC),
                open=Decimal("1"),
                high=Decimal("1"),
                low=Decimal("1"),
                close=Decimal("1"),
                volume=Decimal("1"),
                timeframe="7s",
            )
        assert "7s" in str(exc_info.value)

    def test_build_candle_documents_skips_malformed_records(self):
        extractor = make_extractor()
        broken = Mock(spec=[])  # no kline attributes at all
        candles = extractor.build_candle_documents([make_kline(), broken])
        assert len(candles) == 1
        assert candles[0].symbol == "BTCUSDT"


class TestDualWriteConfiguration:
    def test_dual_write_is_off_by_default(self):
        extractor = gap_filler.GapFillerExtractor(["BTCUSDT"], "5m", "data_manager")
        assert extractor.candles_dual_write is constants.CANDLES_DUAL_WRITE_ENABLED
        assert constants.CANDLES_DUAL_WRITE_ENABLED is False

    def test_explicit_flag_overrides_env_default(self):
        with patch.object(constants, "CANDLES_DUAL_WRITE_ENABLED", True):
            off = gap_filler.GapFillerExtractor(
                ["BTCUSDT"], "5m", "data_manager", candles_dual_write=False
            )
            assert off.candles_dual_write is False

    def test_env_default_is_honoured_when_flag_absent(self):
        with patch.object(constants, "CANDLES_DUAL_WRITE_ENABLED", True):
            on = gap_filler.GapFillerExtractor(["BTCUSDT"], "5m", "data_manager")
            assert on.candles_dual_write is True

    def test_budget_defaults_to_constant(self):
        extractor = gap_filler.GapFillerExtractor(["BTCUSDT"], "5m", "data_manager")
        assert (
            extractor.candles_max_records
            == constants.CANDLES_DUAL_WRITE_MAX_RECORDS_PER_RUN
        )

    def test_cli_exposes_mutually_exclusive_dual_write_flags(self):
        argv = ["prog", "--period", "5m", "--candles-dual-write"]
        with patch.object(sys, "argv", argv):
            args = gap_filler.parse_arguments()
        assert args.candles_dual_write is True

        argv = ["prog", "--period", "5m", "--no-candles-dual-write"]
        with patch.object(sys, "argv", argv):
            args = gap_filler.parse_arguments()
        assert args.candles_dual_write is False

        with patch.object(sys, "argv", ["prog", "--period", "5m"]):
            args = gap_filler.parse_arguments()
        assert args.candles_dual_write is None

    def test_cli_rejects_both_flags_together(self):
        argv = [
            "prog",
            "--period",
            "5m",
            "--candles-dual-write",
            "--no-candles-dual-write",
        ]
        with patch.object(sys, "argv", argv):
            with pytest.raises(SystemExit) as exc_info:
                gap_filler.parse_arguments()
        assert exc_info.value.code == 2


class TestMirrorChunkToCandles:
    def test_writes_candles_to_the_right_collection(self):
        extractor = make_extractor()
        adapter = Mock()
        adapter.write_batch.return_value = 2

        written = extractor.mirror_chunk_to_candles(
            "BTCUSDT", [make_kline(minute=0), make_kline(minute=5)], adapter
        )

        assert written == 2
        adapter.write_batch.assert_called_once()
        call_args = adapter.write_batch.call_args[0]
        assert call_args[1] == "candles_BTCUSDT_5m"
        assert all(isinstance(c, CandleModel) for c in call_args[0])
        assert extractor.stats["total_mongodb_gaps_filled"] == 1
        assert extractor.stats["total_candles_written"] == 2

    def test_no_write_when_dual_write_disabled(self):
        extractor = make_extractor(candles_dual_write=False)
        adapter = Mock()
        assert (
            extractor.mirror_chunk_to_candles("BTCUSDT", [make_kline()], adapter) == 0
        )
        adapter.write_batch.assert_not_called()

    def test_no_write_without_an_adapter(self):
        extractor = make_extractor()
        assert extractor.mirror_chunk_to_candles("BTCUSDT", [make_kline()], None) == 0

    def test_no_write_for_empty_chunk(self):
        extractor = make_extractor()
        adapter = Mock()
        assert extractor.mirror_chunk_to_candles("BTCUSDT", [], adapter) == 0
        adapter.write_batch.assert_not_called()

    def test_write_failure_is_swallowed_and_budget_is_returned(self):
        extractor = make_extractor(candles_max_records=10)
        adapter = Mock()
        adapter.write_batch.side_effect = RuntimeError("data manager down")

        with patch("time.sleep"):
            written = extractor.mirror_chunk_to_candles(
                "BTCUSDT", [make_kline(), make_kline(minute=5)], adapter
            )

        assert written == 0
        assert extractor.stats["total_mongodb_gaps_filled"] == 0
        # The reservation must be released, otherwise a transient outage
        # would permanently shrink the run's budget.
        assert extractor._candles_budget_remaining == 10

    def test_metric_is_emitted_on_success(self):
        extractor = make_extractor()
        adapter = Mock()
        adapter.write_batch.return_value = 1
        metrics = Mock()

        with patch("utils.metrics.get_metrics", return_value=metrics):
            extractor.mirror_chunk_to_candles("BTCUSDT", [make_kline()], adapter)

        metrics.record_mongodb_gap_filled.assert_called_once_with(
            symbol="BTCUSDT", interval="5m", candles_written=1
        )

    def test_metric_failure_does_not_break_the_mirror(self):
        extractor = make_extractor()
        adapter = Mock()
        adapter.write_batch.return_value = 1

        with patch("utils.metrics.get_metrics", side_effect=RuntimeError("no meter")):
            assert (
                extractor.mirror_chunk_to_candles("BTCUSDT", [make_kline()], adapter)
                == 1
            )


class TestCandlesBudget:
    def test_budget_caps_a_single_oversized_chunk(self):
        extractor = make_extractor(candles_max_records=2)
        adapter = Mock()
        adapter.write_batch.return_value = 2

        klines = [make_kline(minute=m) for m in (0, 5, 10, 15)]
        written = extractor.mirror_chunk_to_candles("BTCUSDT", klines, adapter)

        assert written == 2
        assert len(adapter.write_batch.call_args[0][0]) == 2
        assert extractor.stats["candles_dropped_over_budget"] == 2
        assert extractor._candles_budget_remaining == 0

    def test_exhausted_budget_skips_the_write_entirely(self):
        extractor = make_extractor(candles_max_records=0)
        adapter = Mock()

        written = extractor.mirror_chunk_to_candles("BTCUSDT", [make_kline()], adapter)

        assert written == 0
        adapter.write_batch.assert_not_called()
        assert extractor.stats["candles_dropped_over_budget"] == 1

    def test_budget_is_shared_across_chunks(self):
        extractor = make_extractor(candles_max_records=3)
        adapter = Mock()
        adapter.write_batch.side_effect = lambda records, *a, **k: len(records)

        extractor.mirror_chunk_to_candles(
            "BTCUSDT", [make_kline(minute=0), make_kline(minute=5)], adapter
        )
        extractor.mirror_chunk_to_candles(
            "BTCUSDT", [make_kline(minute=10), make_kline(minute=15)], adapter
        )

        assert extractor._candles_budget_remaining == 0
        assert extractor.stats["total_candles_written"] == 3
        assert extractor.stats["candles_dropped_over_budget"] == 1

    def test_negative_budget_is_clamped_to_zero(self):
        extractor = make_extractor(candles_max_records=-5)
        assert extractor._candles_budget_remaining == 0


class TestCandlesAdapterLifecycle:
    def test_adapter_is_not_opened_when_dual_write_is_off(self):
        extractor = make_extractor(candles_dual_write=False)
        assert extractor._open_candles_adapter("BTCUSDT") is None

    def test_adapter_is_opened_and_connected(self):
        extractor = make_extractor()
        adapter = Mock()
        factory = Mock(return_value=adapter)

        with patch.object(gap_filler, "DataManagerAdapter", factory):
            result = extractor._open_candles_adapter("BTCUSDT")

        assert result is adapter
        adapter.connect_sync.assert_called_once()
        assert factory.call_args.kwargs["database"] == extractor.candles_database

    def test_connection_failure_degrades_to_none(self):
        extractor = make_extractor()
        adapter = Mock()
        adapter.connect_sync.side_effect = ConnectionError("refused")

        with patch.object(gap_filler, "DataManagerAdapter", Mock(return_value=adapter)):
            assert extractor._open_candles_adapter("BTCUSDT") is None

    def test_missing_data_manager_adapter_degrades_to_none(self):
        extractor = make_extractor()
        with patch.object(gap_filler, "DataManagerAdapter", None):
            assert extractor._open_candles_adapter("BTCUSDT") is None

    def test_close_is_a_noop_for_none(self):
        extractor = make_extractor()
        assert extractor._close_candles_adapter(None) is None  # must not raise

    def test_close_disconnects_and_swallows_errors(self):
        extractor = make_extractor()
        adapter = Mock()
        adapter.disconnect_sync.side_effect = RuntimeError("already closed")
        extractor._close_candles_adapter(adapter)
        adapter.disconnect_sync.assert_called_once()


class TestFillGapChunkIntegration:
    @patch("jobs.extract_klines_gap_filler.KlinesFetcher")
    @patch("time.sleep")
    def test_chunk_fill_mirrors_into_candles(self, _sleep, fetcher_cls):
        extractor = make_extractor()
        fetcher = Mock()
        fetcher.fetch_klines.return_value = [make_kline(), make_kline(minute=5)]
        fetcher_cls.return_value = fetcher

        db_adapter = Mock()
        db_adapter.write.return_value = 2
        candles_adapter = Mock()
        candles_adapter.write_batch.return_value = 2

        result = extractor.fill_gap_chunk(
            "BTCUSDT",
            datetime(2026, 9, 1, tzinfo=UTC),
            datetime(2026, 9, 2, tzinfo=UTC),
            Mock(),
            db_adapter,
            candles_adapter,
        )

        assert result["success"] is True
        assert result["records_written"] == 2
        assert result["candles_written"] == 2
        candles_adapter.write_batch.assert_called_once()

    @patch("jobs.extract_klines_gap_filler.KlinesFetcher")
    @patch("time.sleep")
    def test_mirror_failure_does_not_fail_the_primary_fill(self, _sleep, fetcher_cls):
        extractor = make_extractor()
        fetcher = Mock()
        fetcher.fetch_klines.return_value = [make_kline()]
        fetcher_cls.return_value = fetcher

        db_adapter = Mock()
        db_adapter.write.return_value = 1
        candles_adapter = Mock()
        candles_adapter.write_batch.side_effect = RuntimeError("mongo down")

        result = extractor.fill_gap_chunk(
            "BTCUSDT",
            datetime(2026, 9, 1, tzinfo=UTC),
            datetime(2026, 9, 2, tzinfo=UTC),
            Mock(),
            db_adapter,
            candles_adapter,
        )

        assert result["success"] is True
        assert result["records_written"] == 1
        assert result["candles_written"] == 0

    @patch("jobs.extract_klines_gap_filler.KlinesFetcher")
    @patch("time.sleep")
    def test_chunk_fill_without_mirror_keeps_legacy_shape(self, _sleep, fetcher_cls):
        extractor = make_extractor(candles_dual_write=False)
        fetcher = Mock()
        fetcher.fetch_klines.return_value = [make_kline()]
        fetcher_cls.return_value = fetcher

        db_adapter = Mock()
        db_adapter.write.return_value = 1

        result = extractor.fill_gap_chunk(
            "BTCUSDT",
            datetime(2026, 9, 1, tzinfo=UTC),
            datetime(2026, 9, 2, tzinfo=UTC),
            Mock(),
            db_adapter,
        )

        assert result["success"] is True
        assert result["candles_written"] == 0


class TestMetricsCounter:
    def test_record_mongodb_gap_filled_increments_both_counters(self):
        from utils.metrics import ExtractionMetrics

        metrics = ExtractionMetrics.__new__(ExtractionMetrics)
        metrics._metrics_enabled = True
        metrics.gaps_filled_mongodb = Mock()
        metrics.candles_written_mongodb = Mock()

        metrics.record_mongodb_gap_filled("BTCUSDT", "5m", candles_written=7)

        metrics.gaps_filled_mongodb.add.assert_called_once_with(
            1, {"symbol": "BTCUSDT", "interval": "5m"}
        )
        metrics.candles_written_mongodb.add.assert_called_once_with(
            7, {"symbol": "BTCUSDT", "interval": "5m"}
        )

    def test_record_mongodb_gap_filled_is_a_noop_when_disabled(self):
        from utils.metrics import ExtractionMetrics

        metrics = ExtractionMetrics.__new__(ExtractionMetrics)
        metrics._metrics_enabled = False
        metrics.gaps_filled_mongodb = Mock()

        metrics.record_mongodb_gap_filled("BTCUSDT", "5m", candles_written=7)

        metrics.gaps_filled_mongodb.add.assert_not_called()

    def test_zero_candles_still_counts_the_gap_chunk(self):
        from utils.metrics import ExtractionMetrics

        metrics = ExtractionMetrics.__new__(ExtractionMetrics)
        metrics._metrics_enabled = True
        metrics.gaps_filled_mongodb = Mock()
        metrics.candles_written_mongodb = Mock()

        metrics.record_mongodb_gap_filled("BTCUSDT", "5m", candles_written=0)

        metrics.gaps_filled_mongodb.add.assert_called_once()
        metrics.candles_written_mongodb.add.assert_not_called()
