"""
Tests for AC3.1 — abandoned-batch observability (petrosa-binance-data-extractor#263).

Verifies that when DataManagerAdapter.write() exhausts retries and raises, it:
  1. Increments extractor.batches_abandoned.total BEFORE re-raising.
  2. Publishes an alerts.extractor.persist_failed NATS message BEFORE re-raising.
  3. Still re-raises the original exception so callers see the failure.
  4. Does not suppress the original exception even if the observability path itself fails.
"""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_model(symbol: str = "BTCUSDT") -> MagicMock:
    m = MagicMock()
    m.to_dict.return_value = {"symbol": symbol, "open": 1.0}
    return m


# ---------------------------------------------------------------------------
# DataManagerAdapter.write() — observability on abandon
# ---------------------------------------------------------------------------


class TestAdapterWriteObservabilityOnAbandon:
    @pytest.fixture
    def adapter(self):
        from adapters.data_manager_adapter import DataManagerAdapter

        a = DataManagerAdapter(base_url="http://fake", timeout=5, max_retries=0)
        a._connected = True
        inner = MagicMock()
        inner.insert_klines = AsyncMock(side_effect=ConnectionError("timeout"))
        a._client = MagicMock()
        a._client.insert_klines = AsyncMock(side_effect=ConnectionError("timeout"))
        a._client.insert_trades = AsyncMock(side_effect=ConnectionError("timeout"))
        return a

    @pytest.mark.asyncio
    async def test_record_batch_abandoned_called_before_reraise(self, adapter):
        mock_metrics = MagicMock()
        with (
            patch("utils.metrics.get_metrics", return_value=mock_metrics),
            patch(
                "utils.messaging.publish_persist_failed_alert_async",
                new_callable=AsyncMock,
            ) as mock_alert,
        ):
            with pytest.raises(ConnectionError):
                await adapter.write([_make_model()], "klines_1h")

        mock_metrics.record_batch_abandoned.assert_called_once()
        assert mock_alert.called

    @pytest.mark.asyncio
    async def test_record_batch_abandoned_labels_klines(self, adapter):
        captured = {}

        def fake_record(symbol, interval, reason):
            captured["symbol"] = symbol
            captured["interval"] = interval
            captured["reason"] = reason

        mock_metrics = MagicMock()
        mock_metrics.record_batch_abandoned.side_effect = fake_record

        with (
            patch("utils.metrics.get_metrics", return_value=mock_metrics),
            patch(
                "utils.messaging.publish_persist_failed_alert_async",
                new_callable=AsyncMock,
            ),
        ):
            with pytest.raises(ConnectionError):
                await adapter.write([_make_model("ETHUSDT")], "klines_4h")

        assert captured["symbol"] == "ETHUSDT"
        assert captured["interval"] == "4h"
        assert captured["reason"] == "ConnectionError"

    @pytest.mark.asyncio
    async def test_nats_alert_uses_persist_failed_subject(self, adapter):
        published = {}

        async def fake_alert(symbol, interval, collection, error):
            published["symbol"] = symbol
            published["interval"] = interval
            published["collection"] = collection
            published["error"] = error

        mock_metrics = MagicMock()
        with (
            patch("utils.metrics.get_metrics", return_value=mock_metrics),
            patch(
                "utils.messaging.publish_persist_failed_alert_async",
                side_effect=fake_alert,
            ),
        ):
            with pytest.raises(ConnectionError):
                await adapter.write([_make_model()], "klines_1h")

        assert published["collection"] == "klines_1h"
        assert "timeout" in published["error"].lower()

    @pytest.mark.asyncio
    async def test_original_exception_reraised_even_if_observability_fails(
        self, adapter
    ):
        mock_metrics = MagicMock()
        mock_metrics.record_batch_abandoned.side_effect = RuntimeError("otel down")

        with (
            patch("utils.metrics.get_metrics", return_value=mock_metrics),
            patch(
                "utils.messaging.publish_persist_failed_alert_async",
                new_callable=AsyncMock,
            ),
        ):
            with pytest.raises(ConnectionError):
                await adapter.write([_make_model()], "klines_1h")

    @pytest.mark.asyncio
    async def test_trades_collection_symbol_label(self, adapter):
        captured = {}

        def fake_record(symbol, interval, reason):
            captured["symbol"] = symbol
            captured["interval"] = interval

        mock_metrics = MagicMock()
        mock_metrics.record_batch_abandoned.side_effect = fake_record

        with (
            patch("utils.metrics.get_metrics", return_value=mock_metrics),
            patch(
                "utils.messaging.publish_persist_failed_alert_async",
                new_callable=AsyncMock,
            ),
        ):
            with pytest.raises(ConnectionError):
                await adapter.write([_make_model("BNBUSDT")], "trades_BNBUSDT")

        assert captured["symbol"] == "BNBUSDT"
        assert captured["interval"] == "n/a"


# ---------------------------------------------------------------------------
# ExtractionMetrics.record_batch_abandoned()
# ---------------------------------------------------------------------------


class TestRecordBatchAbandoned:
    def test_increments_counter_with_labels(self):
        from utils.metrics import ExtractionMetrics

        m = ExtractionMetrics.__new__(ExtractionMetrics)
        m._metrics_enabled = True
        counter = MagicMock()
        m.batches_abandoned = counter

        m.record_batch_abandoned("BTCUSDT", "1h", "ConnectionError")

        counter.add.assert_called_once_with(
            1, {"symbol": "BTCUSDT", "interval": "1h", "reason": "ConnectionError"}
        )

    def test_noop_when_metrics_disabled(self):
        from utils.metrics import ExtractionMetrics

        m = ExtractionMetrics.__new__(ExtractionMetrics)
        m._metrics_enabled = False
        # Should not raise even without batches_abandoned attribute
        m.record_batch_abandoned("BTCUSDT", "1h", "ConnectionError")
        assert m._metrics_enabled is False  # guard: disabled path ran without exception

    def test_swallows_counter_error(self):
        from utils.metrics import ExtractionMetrics

        m = ExtractionMetrics.__new__(ExtractionMetrics)
        m._metrics_enabled = True
        counter = MagicMock()
        counter.add.side_effect = RuntimeError("otel broken")
        m.batches_abandoned = counter
        # Must not raise
        m.record_batch_abandoned("BTCUSDT", "1h", "ConnectionError")
        assert counter.add.called  # counter.add was attempted despite raising


# ---------------------------------------------------------------------------
# NATSMessenger.publish_persist_failed_alert()
# ---------------------------------------------------------------------------


class TestPublishPersistFailedAlert:
    @pytest.mark.asyncio
    async def test_publishes_to_alerts_extractor_persist_failed(self):
        from utils.messaging import NATSMessenger

        messenger = NATSMessenger.__new__(NATSMessenger)
        nats_client = MagicMock()
        nats_client.is_closed = False
        nats_client.publish = AsyncMock()
        messenger.client = nats_client
        messenger.nats_url = "nats://localhost:4222"

        await messenger.publish_persist_failed_alert(
            symbol="BTCUSDT", interval="1h", collection="klines_1h", error="timeout"
        )

        nats_client.publish.assert_called_once()
        subject, payload = nats_client.publish.call_args[0]
        assert subject == "alerts.extractor.persist_failed"

        import json

        body = json.loads(payload.decode())
        assert body["event_type"] == "persist_failed"
        assert body["symbol"] == "BTCUSDT"
        assert body["interval"] == "1h"
        assert body["service"] == "extractor"


# ---------------------------------------------------------------------------
# retry_with_backoff — should_retry_operation routing (Task 3.2)
# ---------------------------------------------------------------------------


class TestRetryWithBackoffUsesClassifier:
    def test_retries_on_transient_error(self):
        from jobs.extract_klines_production import retry_with_backoff

        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("lost connection to mysql server")
            return "ok"

        with patch("time.sleep"):
            result = retry_with_backoff(flaky, max_retries=3)

        assert result == "ok"
        assert call_count == 3

    def test_does_not_retry_non_transient(self):
        from jobs.extract_klines_production import retry_with_backoff

        call_count = 0

        def bad():
            nonlocal call_count
            call_count += 1
            # "duplicate entry" triggers DATA_INTEGRITY classification → should_retry=False
            raise ValueError("duplicate entry violates unique constraint")

        with patch("time.sleep"):
            with pytest.raises(ValueError):
                retry_with_backoff(bad, max_retries=3)

        assert call_count == 1

    def test_raises_after_exhausting_transient_retries(self):
        from jobs.extract_klines_production import retry_with_backoff

        def always_transient():
            raise ConnectionError("2013 connection lost")

        with patch("time.sleep"):
            with pytest.raises(ConnectionError) as exc_info:
                retry_with_backoff(always_transient, max_retries=2)
        assert "2013" in str(exc_info.value)
