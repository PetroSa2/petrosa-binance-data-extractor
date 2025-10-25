"""
Custom business metrics for data extraction monitoring.

This module provides OpenTelemetry metrics for tracking:
- Extraction success/failure rates
- Binance API latency
- Rate limit usage
- Data gaps detected
- Extraction throughput
"""

import logging
from typing import Any

from utils.telemetry import get_meter

logger = logging.getLogger(__name__)


class ExtractionMetrics:
    """
    Metrics collector for data extraction operations.

    Provides OpenTelemetry metrics for monitoring extraction health,
    API performance, and data quality.
    """

    def __init__(self):
        """Initialize extraction metrics."""
        self.meter = get_meter(__name__)
        self._metrics_enabled = self.meter is not None

        if not self._metrics_enabled:
            logger.warning(
                "OpenTelemetry metrics not available - metrics will not be recorded"
            )
            return

        # Extraction counter (by symbol, interval, status)
        self.extraction_counter = self.meter.create_counter(
            name="extractor.extractions.total",
            description="Total number of extraction attempts",
            unit="1",
        )

        # API latency histogram (by endpoint)
        self.api_latency = self.meter.create_histogram(
            name="extractor.binance.api_latency",
            description="Binance API request latency in milliseconds",
            unit="ms",
        )

        # Rate limit usage gauge
        self.rate_limit_used = self.meter.create_up_down_counter(
            name="extractor.rate_limit.used",
            description="Current rate limit usage count",
            unit="1",
        )

        # Rate limit remaining gauge
        self.rate_limit_remaining = self.meter.create_up_down_counter(
            name="extractor.rate_limit.remaining",
            description="Remaining rate limit capacity",
            unit="1",
        )

        # Data gaps counter
        self.gaps_counter = self.meter.create_counter(
            name="extractor.data_gaps.total",
            description="Total number of data gaps detected",
            unit="1",
        )

        # Extraction throughput (candles per second) - use histogram
        self.throughput_histogram = self.meter.create_histogram(
            name="extractor.throughput.candles_per_second",
            description="Extraction throughput in candles per second",
            unit="candles/s",
        )

        # Records written counter
        self.records_written = self.meter.create_counter(
            name="extractor.records.written",
            description="Total number of records written to database",
            unit="1",
        )

        # Records fetched counter
        self.records_fetched = self.meter.create_counter(
            name="extractor.records.fetched",
            description="Total number of records fetched from API",
            unit="1",
        )

        logger.info("Extraction metrics initialized successfully")

    def record_extraction(
        self,
        symbol: str,
        interval: str,
        status: str,
        records_fetched: int = 0,
        records_written: int = 0,
        duration_seconds: float = 0.0,
        gaps_found: int = 0,
    ) -> None:
        """
        Record an extraction attempt with outcome metrics.

        Args:
            symbol: Trading symbol (e.g., BTCUSDT)
            interval: Kline interval (e.g., 1m, 5m, 1h)
            status: Extraction status (success, error, rate_limited)
            records_fetched: Number of records fetched from API
            records_written: Number of records written to database
            duration_seconds: Duration of extraction in seconds
            gaps_found: Number of data gaps detected
        """
        if not self._metrics_enabled:
            return

        try:
            # Record extraction attempt
            self.extraction_counter.add(
                1, {"symbol": symbol, "interval": interval, "status": status}
            )

            # Record records fetched and written
            if records_fetched > 0:
                self.records_fetched.add(
                    records_fetched, {"symbol": symbol, "interval": interval}
                )

            if records_written > 0:
                self.records_written.add(
                    records_written, {"symbol": symbol, "interval": interval}
                )

            # Record gaps if any found
            if gaps_found > 0:
                self.gaps_counter.add(
                    gaps_found, {"symbol": symbol, "interval": interval}
                )

            # Calculate and record throughput
            if duration_seconds > 0 and records_fetched > 0:
                throughput = records_fetched / duration_seconds
                self.throughput_histogram.record(
                    throughput, {"symbol": symbol, "interval": interval}
                )

        except Exception as e:
            logger.warning(f"Failed to record extraction metrics: {e}")

    def record_api_latency(
        self, endpoint: str, latency_ms: float, status_code: int = 200
    ) -> None:
        """
        Record Binance API request latency.

        Args:
            endpoint: API endpoint (e.g., /fapi/v1/klines)
            latency_ms: Request latency in milliseconds
            status_code: HTTP status code
        """
        if not self._metrics_enabled:
            return

        try:
            self.api_latency.record(
                latency_ms, {"endpoint": endpoint, "status_code": str(status_code)}
            )
        except Exception as e:
            logger.warning(f"Failed to record API latency: {e}")

    def record_rate_limit_usage(
        self, used: int, remaining: int, limit: int = 1200
    ) -> None:
        """
        Record rate limit usage.

        Args:
            used: Number of requests used in current window
            remaining: Number of requests remaining
            limit: Total rate limit (default: 1200/min for Binance)
        """
        if not self._metrics_enabled:
            return

        try:
            self.rate_limit_used.add(used, {"limit": str(limit)})
            self.rate_limit_remaining.add(remaining, {"limit": str(limit)})
        except Exception as e:
            logger.warning(f"Failed to record rate limit metrics: {e}")


# Global metrics instance
_metrics_instance = None


def get_metrics() -> ExtractionMetrics:
    """
    Get the global metrics instance.

    Returns:
        ExtractionMetrics instance (singleton)
    """
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = ExtractionMetrics()
    return _metrics_instance
