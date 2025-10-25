"""
Tests for custom business metrics.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from utils.metrics import ExtractionMetrics, get_metrics


@pytest.fixture
def mock_meter():
    """Create a mock OpenTelemetry meter with unique instrument mocks."""
    meter = Mock()

    # Track created instruments for different metric names
    counters = {}
    histograms = {}
    updown_counters = {}

    def create_counter(name, **kwargs):
        if name not in counters:
            mock = Mock()
            mock.add = Mock()
            counters[name] = mock
        return counters[name]

    def create_histogram(name, **kwargs):
        if name not in histograms:
            mock = Mock()
            mock.record = Mock()
            histograms[name] = mock
        return histograms[name]

    def create_up_down_counter(name, **kwargs):
        if name not in updown_counters:
            mock = Mock()
            mock.add = Mock()
            updown_counters[name] = mock
        return updown_counters[name]

    meter.create_counter = Mock(side_effect=create_counter)
    meter.create_histogram = Mock(side_effect=create_histogram)
    meter.create_up_down_counter = Mock(side_effect=create_up_down_counter)

    # Store the dictionaries for test access
    meter._counters = counters
    meter._histograms = histograms
    meter._updown_counters = updown_counters

    return meter


@pytest.fixture
def extraction_metrics(mock_meter):
    """Create ExtractionMetrics with mocked meter."""
    with patch("utils.metrics.get_meter", return_value=mock_meter):
        metrics = ExtractionMetrics()
    # Attach the instrument dicts for easy access in tests
    metrics._meter = mock_meter
    return metrics


class TestExtractionMetrics:
    """Test suite for ExtractionMetrics class."""

    def test_initialization_with_meter(self, mock_meter):
        """Test metrics initialization when meter is available."""
        with patch("utils.metrics.get_meter", return_value=mock_meter):
            metrics = ExtractionMetrics()

        assert metrics._metrics_enabled is True
        assert metrics.meter is not None

        # Verify all metrics were created
        assert (
            mock_meter.create_counter.call_count == 4
        )  # extraction, gaps, records_written, records_fetched
        assert mock_meter.create_histogram.call_count == 2  # api_latency, throughput
        assert (
            mock_meter.create_up_down_counter.call_count == 2
        )  # rate_limit_used, rate_limit_remaining

    def test_initialization_without_meter(self):
        """Test metrics initialization when meter is not available."""
        with patch("utils.metrics.get_meter", return_value=None):
            metrics = ExtractionMetrics()

        assert metrics._metrics_enabled is False
        assert metrics.meter is None

    def test_record_extraction_success(self, extraction_metrics):
        """Test recording successful extraction."""
        extraction_metrics.record_extraction(
            symbol="BTCUSDT",
            interval="1h",
            status="success",
            records_fetched=100,
            records_written=100,
            duration_seconds=5.5,
            gaps_found=0,
        )

        # Verify extraction counter was incremented
        extraction_metrics.extraction_counter.add.assert_called_once_with(
            1, {"symbol": "BTCUSDT", "interval": "1h", "status": "success"}
        )

        # Verify records fetched and written were recorded
        extraction_metrics.records_fetched.add.assert_called_once_with(
            100, {"symbol": "BTCUSDT", "interval": "1h"}
        )
        extraction_metrics.records_written.add.assert_called_once_with(
            100, {"symbol": "BTCUSDT", "interval": "1h"}
        )

        # Verify throughput was recorded
        extraction_metrics.throughput_histogram.record.assert_called_once()
        call_args = extraction_metrics.throughput_histogram.record.call_args
        assert call_args[0][0] == pytest.approx(100 / 5.5, rel=0.01)  # throughput

    def test_record_extraction_with_gaps(self, extraction_metrics):
        """Test recording extraction with data gaps."""
        extraction_metrics.record_extraction(
            symbol="ETHUSDT",
            interval="15m",
            status="success",
            records_fetched=50,
            records_written=45,
            duration_seconds=3.0,
            gaps_found=5,
        )

        # Verify gaps counter was incremented
        extraction_metrics.gaps_counter.add.assert_called_once_with(
            5, {"symbol": "ETHUSDT", "interval": "15m"}
        )

    def test_record_extraction_failure(self, extraction_metrics):
        """Test recording failed extraction."""
        extraction_metrics.record_extraction(
            symbol="BNBUSDT",
            interval="5m",
            status="error",
            records_fetched=0,
            records_written=0,
            duration_seconds=1.0,
            gaps_found=0,
        )

        # Verify extraction counter was incremented with error status
        extraction_metrics.extraction_counter.add.assert_called_once_with(
            1, {"symbol": "BNBUSDT", "interval": "5m", "status": "error"}
        )

        # Verify no records or gaps were recorded
        extraction_metrics.records_fetched.add.assert_not_called()
        extraction_metrics.records_written.add.assert_not_called()
        extraction_metrics.gaps_counter.add.assert_not_called()

    def test_record_extraction_when_disabled(self):
        """Test that recording does nothing when metrics are disabled."""
        with patch("utils.metrics.get_meter", return_value=None):
            metrics = ExtractionMetrics()

        # Should not raise any exceptions
        metrics.record_extraction(
            symbol="BTCUSDT",
            interval="1h",
            status="success",
            records_fetched=100,
            records_written=100,
            duration_seconds=5.0,
            gaps_found=0,
        )

    def test_record_api_latency(self, extraction_metrics):
        """Test recording API latency."""
        extraction_metrics.record_api_latency(
            endpoint="/fapi/v1/klines", latency_ms=150.5, status_code=200
        )

        extraction_metrics.api_latency.record.assert_called_once_with(
            150.5, {"endpoint": "/fapi/v1/klines", "status_code": "200"}
        )

    def test_record_api_latency_error(self, extraction_metrics):
        """Test recording API latency for failed requests."""
        extraction_metrics.record_api_latency(
            endpoint="/fapi/v1/klines", latency_ms=2000.0, status_code=429
        )

        extraction_metrics.api_latency.record.assert_called_once_with(
            2000.0, {"endpoint": "/fapi/v1/klines", "status_code": "429"}
        )

    def test_record_rate_limit_usage(self, extraction_metrics):
        """Test recording rate limit usage."""
        extraction_metrics.record_rate_limit_usage(used=800, remaining=400, limit=1200)

        extraction_metrics.rate_limit_used.add.assert_called_once_with(
            800, {"limit": "1200"}
        )
        extraction_metrics.rate_limit_remaining.add.assert_called_once_with(
            400, {"limit": "1200"}
        )

    def test_record_rate_limit_exhausted(self, extraction_metrics):
        """Test recording when rate limit is nearly exhausted."""
        extraction_metrics.record_rate_limit_usage(used=1195, remaining=5, limit=1200)

        extraction_metrics.rate_limit_used.add.assert_called_once_with(
            1195, {"limit": "1200"}
        )
        extraction_metrics.rate_limit_remaining.add.assert_called_once_with(
            5, {"limit": "1200"}
        )

    def test_get_metrics_singleton(self):
        """Test that get_metrics returns a singleton instance."""
        with patch("utils.metrics.get_meter", return_value=Mock()):
            metrics1 = get_metrics()
            metrics2 = get_metrics()

        assert metrics1 is metrics2


class TestMetricsIntegration:
    """Integration tests for metrics with telemetry."""

    @patch("utils.metrics.get_meter")
    def test_metrics_with_real_telemetry_unavailable(self, mock_get_meter):
        """Test metrics behavior when telemetry is unavailable."""
        mock_get_meter.return_value = None

        metrics = ExtractionMetrics()

        # Should handle gracefully
        metrics.record_extraction(
            symbol="BTCUSDT",
            interval="1h",
            status="success",
            records_fetched=100,
            records_written=100,
            duration_seconds=5.0,
            gaps_found=0,
        )

        metrics.record_api_latency("/fapi/v1/klines", 150.0, 200)
        metrics.record_rate_limit_usage(800, 400, 1200)

        # No exceptions should be raised

    def test_metrics_exception_handling(self, extraction_metrics):
        """Test that metrics handle exceptions gracefully."""
        # Make the counter raise an exception
        extraction_metrics.extraction_counter.add.side_effect = Exception(
            "Metric recording failed"
        )

        # Should not raise exception
        extraction_metrics.record_extraction(
            symbol="BTCUSDT",
            interval="1h",
            status="success",
            records_fetched=100,
            records_written=100,
            duration_seconds=5.0,
            gaps_found=0,
        )


class TestMetricsNaming:
    """Test metric naming conventions."""

    def test_metric_names_follow_conventions(self, mock_meter):
        """Test that all metrics follow OpenTelemetry naming conventions."""
        with patch("utils.metrics.get_meter", return_value=mock_meter):
            ExtractionMetrics()

        # Get all create_* calls - use kwargs['name'] instead of positional args
        counter_calls = [
            call.kwargs.get("name") or call.args[0]
            for call in mock_meter.create_counter.call_args_list
        ]
        histogram_calls = [
            call.kwargs.get("name") or call.args[0]
            for call in mock_meter.create_histogram.call_args_list
        ]
        updown_calls = [
            call.kwargs.get("name") or call.args[0]
            for call in mock_meter.create_up_down_counter.call_args_list
        ]

        all_metrics = counter_calls + histogram_calls + updown_calls

        # All metrics should start with "extractor."
        for metric_name in all_metrics:
            assert metric_name.startswith(
                "extractor."
            ), f"Metric {metric_name} doesn't start with 'extractor.'"

        # Check specific expected metrics
        assert "extractor.extractions.total" in counter_calls
        assert "extractor.binance.api_latency" in histogram_calls
        assert "extractor.rate_limit.used" in updown_calls
        assert "extractor.rate_limit.remaining" in updown_calls
        assert "extractor.data_gaps.total" in counter_calls
        assert "extractor.throughput.candles_per_second" in histogram_calls
