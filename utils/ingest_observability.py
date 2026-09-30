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

    def shutdown(self) -> dict[str, Any] | None:
        """Flush the final bounded summary when the job exits."""
        return self.maybe_summary(force=True)

    @staticmethod
    def _percentile(values: list[float], fraction: float) -> int:
        if not values:
            return 0
        index = min(len(values) - 1, int((len(values) - 1) * fraction))
        return round(values[index] * 1000)
