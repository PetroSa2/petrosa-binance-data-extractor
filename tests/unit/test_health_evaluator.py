"""Unit tests for DataExtractorHealthEvaluator (#259, P2.7 AC2)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from petrosa_otel.evaluators import ConsecutiveSamplesHysteresis
from petrosa_otel.evaluators.publisher import (
    EVALUATOR_SUBJECT_TEMPLATE,
    NatsVerdictPublisher,
)

from evaluators import (
    DataExtractorHealthEvaluator,
    build_data_extractor_health_evaluator,
)


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self._t = start

    def __call__(self) -> datetime:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t = self._t + timedelta(seconds=seconds)


class FakeNats:
    def __init__(self) -> None:
        self.messages: list[tuple[str, bytes]] = []

    async def publish(self, subject: str, payload: bytes) -> None:
        self.messages.append((subject, payload))


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 5, 28, 0, 0, 0, tzinfo=UTC))


def _make(
    clock, *, publisher=None, n: int = 1, **kwargs
) -> DataExtractorHealthEvaluator:
    return DataExtractorHealthEvaluator(
        publisher=publisher,
        hysteresis=ConsecutiveSamplesHysteresis(n=n),
        time_source=clock,
        **kwargs,
    )


def _completion(*, success: bool = True, errors: list | None = None) -> dict:
    return {
        "event_type": "extraction_completed",
        "extraction_type": "klines",
        "symbol": "BTCUSDT",
        "period": "15m",
        "success": success,
        "errors": errors or [],
    }


@pytest.mark.asyncio
async def test_no_completions_observed_is_unknown(clock):
    ev = _make(clock)
    verdict, reason = await ev.evaluate()
    assert verdict == "unknown"
    assert "no extraction completions" in reason.lower()


@pytest.mark.asyncio
async def test_healthy_when_recent_successful_completions(clock):
    ev = _make(clock)
    for _ in range(5):
        ev.record_completion(_completion(success=True))
        clock.advance(30)
    verdict, reason = await ev.evaluate()
    assert verdict == "healthy"
    assert "5 completions" in reason


@pytest.mark.asyncio
async def test_unhealthy_when_all_completions_failed(clock):
    ev = _make(clock)
    for _ in range(3):
        ev.record_completion(_completion(success=False, errors=["http 500"]))
        clock.advance(60)
    verdict, reason = await ev.evaluate()
    assert verdict == "unhealthy"
    assert "no successful extraction" in reason


@pytest.mark.asyncio
async def test_unhealthy_when_last_success_exceeds_silence_threshold(clock):
    ev = _make(clock, silence_threshold_s=300)
    ev.record_completion(_completion(success=True))
    clock.advance(400)  # > 5 min silence threshold
    verdict, reason = await ev.evaluate()
    assert verdict == "unhealthy"
    assert "last successful extraction" in reason


@pytest.mark.asyncio
async def test_unhealthy_on_429_pressure_above_threshold(clock):
    ev = _make(
        clock,
        rate_limit_ratio_threshold=0.5,
        min_completions_for_rate_check=4,
    )
    # Establish a recent success first so the silence check stays healthy.
    ev.record_completion(_completion(success=True))
    clock.advance(10)
    # Then five rate-limited failures.
    for _ in range(5):
        ev.record_completion(
            _completion(success=False, errors=["binance: 429 too many requests"])
        )
        clock.advance(10)
    verdict, reason = await ev.evaluate()
    assert verdict == "unhealthy"
    assert "429 pressure" in reason


@pytest.mark.asyncio
async def test_low_volume_429_does_not_trip_rate_check(clock):
    ev = _make(
        clock,
        rate_limit_ratio_threshold=0.5,
        min_completions_for_rate_check=4,
    )
    ev.record_completion(_completion(success=True))
    clock.advance(10)
    # Two rate-limited failures — below the min-volume guard (4).
    ev.record_completion(_completion(success=False, errors=["429"]))
    ev.record_completion(_completion(success=False, errors=["429"]))
    verdict, _ = await ev.evaluate()
    assert verdict == "healthy"


@pytest.mark.asyncio
async def test_window_prunes_old_completions(clock):
    ev = _make(clock, window=timedelta(seconds=60))
    ev.record_completion(_completion(success=True))
    clock.advance(120)  # past the 60s window
    # Inside-window event keeps the window non-empty.
    ev.record_completion(_completion(success=True))
    verdict, reason = await ev.evaluate()
    assert verdict == "healthy"
    # Only the recent completion should be counted.
    assert "1 completions" in reason


@pytest.mark.asyncio
async def test_on_nats_message_records_completion(clock):
    ev = _make(clock)

    class _Msg:
        def __init__(self, payload: dict) -> None:
            self.data = json.dumps(payload).encode()

    await ev._on_nats_message(_Msg(_completion(success=True)))
    await ev._on_nats_message(
        _Msg({"event_type": "something_else", "success": True})
    )  # ignored

    verdict, reason = await ev.evaluate()
    assert verdict == "healthy"
    assert "1 completions" in reason


@pytest.mark.asyncio
async def test_on_nats_message_ignores_malformed(clock):
    ev = _make(clock)

    class _BadMsg:
        data = b"not-json"

    await ev._on_nats_message(_BadMsg())  # must not raise
    verdict, _ = await ev.evaluate()
    assert verdict == "unknown"  # no completions recorded


@pytest.mark.asyncio
async def test_publishes_on_data_extractor_subject(clock):
    nats = FakeNats()
    ev = _make(clock, publisher=NatsVerdictPublisher(nats_client=nats), n=1)

    # First tick: no completions yet → unknown.
    await ev.tick()
    # Second tick: one successful completion → healthy.
    ev.record_completion(_completion(success=True))
    await ev.tick()

    assert nats.messages, "evaluator did not publish"
    subject, payload = nats.messages[-1]
    assert subject == "evaluator.data-extractor.verdict"
    assert subject == EVALUATOR_SUBJECT_TEMPLATE.format(subsystem="data-extractor")
    body = json.loads(payload.decode())
    assert body["subsystem"] == "data-extractor"
    assert body["verdict"] == "healthy"


@pytest.mark.asyncio
async def test_hysteresis_suppresses_single_flap(clock):
    ev = _make(clock, n=3, silence_threshold_s=120)
    # Commit healthy with 3 consecutive samples.
    for _ in range(3):
        ev.record_completion(_completion(success=True))
        v = await ev.tick()
    assert v.verdict == "healthy"

    # One silent tick (advance past silence threshold) — n=3 must keep healthy.
    clock.advance(200)
    v = await ev.tick()
    assert v.verdict == "healthy"


def test_build_returns_none_when_nats_disabled():
    assert build_data_extractor_health_evaluator(nats_servers=None) is None
    assert build_data_extractor_health_evaluator(nats_servers="") is None
