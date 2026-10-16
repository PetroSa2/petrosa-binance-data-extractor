"""Low-cardinality ingest metrics and five-minute summary logging."""

from __future__ import annotations

import json
import logging
import time
from collections import Counter, deque
from datetime import UTC, datetime
from typing import Any

from utils.telemetry import get_meter

logger = logging.getLogger(__name__)
INGEST_EVENT_LABELS = ("source", "outcome", "interval")
INGEST_LATENCY_LABELS = ("source", "interval")
INGEST_RUN_LABELS = ("source", "interval", "outcome")


class IngestObservability:
    """Own the extractor's bounded metric and summary-log contract."""

    def __init__(self, service: str = "petrosa-binance-data-extractor") -> None:
        self.service = service
        self.started_at = datetime.now(UTC)
        self._outcomes: Counter[str] = Counter()
        self._events_by_interval: Counter[str] = Counter()
        self._latencies: deque[float] = deque(maxlen=10_000)
        self._last_summary = time.monotonic()
        meter = get_meter("petrosa.ingest")
        self.events = None
        self.latency = None
        self.runs = None
        self.records_fetched = None
        self.records_written = None
        self.gaps = None
        self.skipped = None
        if meter is not None:
            self.events = meter.create_counter(
                name="petrosa_ingest_events_total",
                description="Ingest events by bounded source, outcome, and interval",
                unit="1",
            )
            self.latency = meter.create_histogram(
                name="petrosa_ingest_latency_seconds",
                description="Ingest event latency in seconds",
                unit="s",
            )
            self.runs = meter.create_counter(
                name="petrosa_ingest_runs_total",
                description="Completed ingest runs by bounded source, interval, and outcome",
                unit="1",
            )
            self.records_fetched = meter.create_counter(
                name="petrosa_ingest_records_fetched_total",
                description="Records fetched by completed ingest runs",
                unit="1",
            )
            self.records_written = meter.create_counter(
                name="petrosa_ingest_records_written_total",
                description="Records written by completed ingest runs",
                unit="1",
            )
            self.gaps = meter.create_counter(
                name="petrosa_ingest_gaps_total",
                description="Gaps found by completed ingest runs",
                unit="1",
            )
            self.skipped = meter.create_counter(
                name="petrosa_ingest_skipped_total",
                description="Skipped outcomes in completed ingest runs",
                unit="1",
            )

    def record_event(
        self,
        *,
        source: str,
        outcome: str,
        interval: str,
        latency_seconds: float,
    ) -> None:
        """Record one event without allowing event data into labels."""
        self._outcomes[outcome] += 1
        self._events_by_interval[interval] += 1
        latency = max(0.0, latency_seconds)
        self._latencies.append(latency)
        if self.events is not None:
            self.events.add(
                1, {"source": source, "outcome": outcome, "interval": interval}
            )
        if self.latency is not None:
            self.latency.record(latency, {"source": source, "interval": interval})

    def maybe_summary(self, *, force: bool = False) -> dict[str, Any] | None:
        """Emit at most one healthy summary per five-minute window."""
        if not force and time.monotonic() - self._last_summary < 300:
            return None
        self._last_summary = time.monotonic()
        values = sorted(self._latencies)
        summary: dict[str, Any] = {
            "event": "SUMMARY",
            "window_seconds": 300,
            "service": self.service,
            "started_at": self.started_at.isoformat().replace("+00:00", "Z"),
            "counters": {
                "events": sum(self._outcomes.values()),
                **self._events_by_interval,
            },
            "outcomes": dict(self._outcomes),
            "latency_ms": {
                "p50": self._percentile(values, 0.50),
                "p95": self._percentile(values, 0.95),
            },
        }
        logger.info(json.dumps(summary, separators=(",", ":"), sort_keys=True))
        return summary

    def record_run(
        self,
        *,
        source: str,
        interval: str,
        symbols: list[str],
        records_fetched: int,
        records_written: int,
        gaps_found: int,
        skipped_outcomes: int,
        duration_seconds: float,
        success: bool,
        errors: list[str] | None = None,
    ) -> dict[str, Any]:
        """Emit one durable run event and aggregate metrics with bounded labels."""
        outcome = "success" if success else "failure"
        labels = {"source": source, "interval": interval, "outcome": outcome}
        if self.runs is not None:
            self.runs.add(1, labels)
            self.records_fetched.add(max(0, records_fetched), labels)
            self.records_written.add(max(0, records_written), labels)
            self.gaps.add(max(0, gaps_found), labels)
            self.skipped.add(max(0, skipped_outcomes), labels)
        if self.latency is not None:
            self.latency.record(
                max(0.0, duration_seconds), {"source": source, "interval": interval}
            )

        summary = {
            "event": "INGEST_RUN",
            "source": source,
            "timeframe": interval,
            "symbols": symbols,
            "symbols_count": len(symbols),
            "records_fetched": records_fetched,
            "records_written": records_written,
            "gaps_found": gaps_found,
            "skipped_outcomes": skipped_outcomes,
            "duration_seconds": round(max(0.0, duration_seconds), 3),
            "success": success,
            "outcome": outcome,
            "errors": errors or [],
        }
        logger.info(json.dumps(summary, separators=(",", ":"), sort_keys=True))
        return summary

    def shutdown(self) -> dict[str, Any] | None:
        """Flush the final bounded summary when the job exits."""
        return self.maybe_summary(force=True)

    @staticmethod
    def _percentile(values: list[float], fraction: float) -> int:
        if not values:
            return 0
        index = min(len(values) - 1, int((len(values) - 1) * fraction))
        return round(values[index] * 1000)
