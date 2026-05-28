"""data-extractor health evaluator (P2.7, petrosa_k8s#697 AC2 / #259).

Emits ``evaluator.data-extractor.verdict`` via the shared P2.1 framework
(:mod:`petrosa_otel.evaluators`) so the operator dashboard's evaluator strip
counts the data-extractor among the reporting subsystems (FR17 / FR23 / FR32).

CronJob design (the explicit choice the ticket asks the implementer to justify):
the data-extractor's real work runs in short-lived Kubernetes CronJob pods —
those pods exit between runs, so an in-pod evaluator would lose its hysteresis
state every run and emit a single sample at a cadence governed by the cron
schedule (sparse and bursty). Instead we host the evaluator in the **long-lived
API pod** (`api/main.py` FastAPI lifespan) and let it **subscribe to the
existing ``binance.extraction.>`` NATS completion stream** that every cron run
already publishes via `utils/messaging.publish_extraction_completion_*`. That
gives the evaluator (a) a long-lived process for hysteresis state and emit
loop, and (b) cross-cron visibility for "completion rate" and "last successful
extraction lag" signals — without adding any new always-on sidecar deployment.

The three signals (per #697 AC2):

1. **CronJob completion rate** — count of ``extraction_completed`` events
   observed inside the rolling window. Zero events over a long window while
   the API pod is healthy means cron pods stopped firing (or NATS connectivity
   to the API pod is broken).
2. **Last-successful-extraction lag** — wall-clock seconds since the most
   recent message with ``success == true``. Beyond the silence threshold
   (default 30 min) the verdict trips, even if failure events keep arriving.
3. **Binance API 429 rate** — fraction of recent completion messages whose
   ``errors`` list mentions a 429 / rate-limit signature. A sustained ratio
   above the threshold trips the verdict (with a minimum-volume guard so a
   single rate-limited cron doesn't flap it).

Verdict vocabulary is the framework's locked three-state contract
(``healthy`` / ``unhealthy`` / ``unknown``); any breached signal maps to
``unhealthy`` with a single-line reason naming the tripped signal (NFR-O5).

Hysteresis / cadence (AC4 / AC7, FR18 per-evaluator ``decision_window``):
emits every ``EMIT_INTERVAL_S`` (15s) with ``ConsecutiveSamplesHysteresis(n=3)``
→ ~45s decision window. The window is generous on the silence + 429 checks
because cron cadence itself is on the order of minutes; transient gaps between
runs must not flap the verdict.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

try:
    from datetime import UTC
except ImportError:  # pragma: no cover - py310 compatibility
    from datetime import timezone

    UTC = timezone.utc  # noqa: UP017

import nats
from petrosa_otel.evaluators import (
    ConsecutiveSamplesHysteresis,
    Evaluator,
    NatsVerdictPublisher,
)

if TYPE_CHECKING:
    from petrosa_otel.evaluators.base import HysteresisPolicy
    from petrosa_otel.evaluators.publisher import VerdictPublisher

logger = logging.getLogger(__name__)

SUBSYSTEM = "data-extractor"

# Cadence + smoothing (documented per AC4 / AC7).
EMIT_INTERVAL_S = 15.0
HYSTERESIS_SAMPLES = 3

# Rolling window for the completion-rate + 429-rate accumulators.
DEFAULT_WINDOW = timedelta(minutes=30)
# No successful extraction in this many seconds → unhealthy. Default 30 min
# accommodates the slowest cron cadence (1h klines would push this higher per
# operator override).
DEFAULT_SILENCE_THRESHOLD_S = 30 * 60
# 429 / rate-limit ratio above this trips the verdict.
DEFAULT_RATE_LIMIT_RATIO_THRESHOLD = 0.5
# Minimum completion volume in the window before the 429-rate check may trip.
DEFAULT_MIN_COMPLETIONS_FOR_RATE_CHECK = 4

# NATS subject the data-extractor already publishes completion events on.
COMPLETION_SUBJECT_DEFAULT = "binance.extraction.>"

_RATE_LIMIT_NEEDLES = ("429", "rate limit", "rate_limit", "too many requests")


def _message_has_rate_limit_error(payload: dict[str, Any]) -> bool:
    """True when the completion message's ``errors`` list mentions a 429."""
    errors = payload.get("errors") or []
    if not isinstance(errors, list):
        return False
    for entry in errors:
        text = str(entry).lower()
        if any(needle in text for needle in _RATE_LIMIT_NEEDLES):
            return True
    return False


class DataExtractorHealthEvaluator(Evaluator):
    """Subsystem evaluator for the data-extractor's CronJob-driven pipeline."""

    def __init__(
        self,
        *,
        publisher: VerdictPublisher | None = None,
        hysteresis: HysteresisPolicy | None = None,
        window: timedelta = DEFAULT_WINDOW,
        silence_threshold_s: float = DEFAULT_SILENCE_THRESHOLD_S,
        rate_limit_ratio_threshold: float = DEFAULT_RATE_LIMIT_RATIO_THRESHOLD,
        min_completions_for_rate_check: int = DEFAULT_MIN_COMPLETIONS_FOR_RATE_CHECK,
        emit_interval_s: float = EMIT_INTERVAL_S,
        time_source: Callable[[], datetime] | None = None,
    ) -> None:
        super().__init__(
            subsystem=SUBSYSTEM,
            publisher=publisher,
            hysteresis=hysteresis or ConsecutiveSamplesHysteresis(n=HYSTERESIS_SAMPLES),
        )
        self._window = window
        self._silence_threshold_s = silence_threshold_s
        self._rate_limit_ratio_threshold = rate_limit_ratio_threshold
        self._min_completions_for_rate_check = max(1, min_completions_for_rate_check)
        self._emit_interval_s = emit_interval_s
        self._time = time_source or (lambda: datetime.now(UTC))

        # In-process completion log: (observed_at, success, has_429).
        self._completions: deque[tuple[datetime, bool, bool]] = deque()
        self._last_success_at: datetime | None = None

        self._emit_task: asyncio.Task[Any] | None = None

    # ----- ingestion -----

    def record_completion(self, payload: dict[str, Any]) -> None:
        """Record one parsed completion message into the rolling window."""
        success = bool(payload.get("success"))
        has_429 = _message_has_rate_limit_error(payload)
        observed_at = self._time()
        self._completions.append((observed_at, success, has_429))
        if success:
            self._last_success_at = observed_at

    async def _on_nats_message(self, msg: Any) -> None:
        try:
            data = json.loads(msg.data.decode())
        except (json.JSONDecodeError, AttributeError, UnicodeDecodeError) as exc:
            logger.warning(
                "data_extractor_health_evaluator_unparseable_message",
                extra={"error": str(exc)},
            )
            return
        event_type = data.get("event_type")
        if event_type in ("extraction_completed", "batch_extraction_completed"):
            self.record_completion(data)

    # ----- lifecycle (used when the evaluator owns its NATS subscription) -----

    async def start_emit_loop(self) -> None:
        """Start the periodic emit loop (idempotent)."""
        if self._emit_task is not None:
            return
        self._emit_task = asyncio.create_task(self._emit_loop())

    async def stop_emit_loop(self) -> None:
        """Stop the periodic emit loop."""
        if self._emit_task is None:
            return
        self._emit_task.cancel()
        try:
            await self._emit_task
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"data_extractor_health_evaluator stop error: {exc}")
        self._emit_task = None

    async def _emit_loop(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception as exc:  # noqa: BLE001 — never crash the loop
                logger.warning(
                    "data_extractor_health_evaluator_tick_failed",
                    extra={"error": str(exc)},
                )
            await asyncio.sleep(self._emit_interval_s)

    # ----- framework hook -----

    async def evaluate(self) -> tuple[str, str]:
        """Compute the raw ``(verdict, reason)`` sample from the rolling window."""
        now = self._time()
        cutoff = now - self._window
        while self._completions and self._completions[0][0] < cutoff:
            self._completions.popleft()

        total = len(self._completions)
        rate_limited = sum(1 for _, _, has429 in self._completions if has429)

        # 1) Last-successful-extraction lag. Tripping this is independent of how
        # many failures are arriving: a flood of 429-failures with zero successes
        # is still unhealthy.
        if self._last_success_at is None:
            if total == 0:
                return "unknown", "no extraction completions observed yet"
            return (
                "unhealthy",
                f"no successful extraction observed ({total} failures in last "
                f"{int(self._window.total_seconds())}s)",
            )
        lag_s = (now - self._last_success_at).total_seconds()
        if lag_s > self._silence_threshold_s:
            return (
                "unhealthy",
                f"last successful extraction {int(lag_s)}s ago > "
                f"{int(self._silence_threshold_s)}s threshold",
            )

        # 2) Binance API 429 rate (only when we have enough samples).
        if total >= self._min_completions_for_rate_check:
            ratio = rate_limited / total
            if ratio > self._rate_limit_ratio_threshold:
                pct = int(round(ratio * 100))
                return (
                    "unhealthy",
                    f"Binance 429 pressure: {rate_limited}/{total} "
                    f"({pct}%) of completions rate-limited",
                )

        # 3) Healthy summary.
        return (
            "healthy",
            f"{total} completions in last "
            f"{int(self._window.total_seconds())}s, last-success {int(lag_s)}s ago, "
            f"{rate_limited} rate-limited",
        )


def build_data_extractor_health_evaluator(
    *,
    nats_servers: str | None,
) -> DataExtractorHealthEvaluator | None:
    """Construct an evaluator subscribed to `binance.extraction.>` completions.

    Returns ``None`` when ``nats_servers`` is empty (NATS disabled).

    The returned object exposes ``start()`` and ``stop()`` async lifecycle
    methods that own the NATS connection + subscription + emit loop. Wire those
    into the FastAPI lifespan in :mod:`api.main`.
    """
    if not nats_servers:
        logger.info(
            "data_extractor_health_evaluator not started: NATS disabled (no servers)"
        )
        return None

    evaluator = DataExtractorHealthEvaluator()

    # Attach the connection-owning start/stop wrapper as bound methods. The
    # wrapper holds the live NATS client; the underlying evaluator stays a
    # plain Evaluator subclass (testable without any NATS in unit tests).
    nc_holder: dict[str, Any] = {"client": None, "sub": None}

    async def _start() -> None:
        if nc_holder["client"] is not None:
            return
        try:
            nc = await nats.connect(
                servers=nats_servers,
                name="petrosa-data-extractor-evaluator",
                allow_reconnect=True,
            )
        except Exception as exc:  # noqa: BLE001 — degrade, never crash startup
            logger.warning(
                "data_extractor_health_evaluator NATS connect failed: %s — "
                "evaluator will not publish",
                exc,
            )
            return
        nc_holder["client"] = nc
        evaluator._publisher = NatsVerdictPublisher(nats_client=nc)
        try:
            nc_holder["sub"] = await nc.subscribe(
                COMPLETION_SUBJECT_DEFAULT, cb=evaluator._on_nats_message
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "data_extractor_health_evaluator subscribe failed: %s — "
                "evaluator will publish unknown verdicts",
                exc,
            )
        await evaluator.start_emit_loop()
        logger.info(
            "data_extractor_health_evaluator_started",
            extra={
                "subsystem": SUBSYSTEM,
                "subject": COMPLETION_SUBJECT_DEFAULT,
                "emit_interval_s": evaluator._emit_interval_s,
            },
        )

    async def _stop() -> None:
        await evaluator.stop_emit_loop()
        sub = nc_holder.get("sub")
        if sub is not None:
            try:
                await sub.unsubscribe()
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"data_extractor_health_evaluator unsubscribe: {exc}")
            nc_holder["sub"] = None
        nc = nc_holder.get("client")
        if nc is not None:
            try:
                await nc.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"data_extractor_health_evaluator close: {exc}")
            nc_holder["client"] = None
            evaluator._publisher = None

    evaluator.start = _start  # type: ignore[method-assign]
    evaluator.stop = _stop  # type: ignore[method-assign]
    return evaluator
