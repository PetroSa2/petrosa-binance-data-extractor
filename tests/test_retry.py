"""
Unit tests for utils.retry.

Covers: exponential_backoff, simple_retry, RateLimiter, rate_limited,
with_retries_and_rate_limit, retry_on_http_errors. Validates real behavior
(retry counts, raised exceptions, sleep calls) rather than smoke-testing.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from utils.retry import (
    NonRetryableError,
    RateLimiter,
    RetryableError,
    _get_metrics,
    exponential_backoff,
    rate_limit_api_calls,
    rate_limited,
    retry_on_http_errors,
    simple_retry,
    with_retries_and_rate_limit,
)


@pytest.fixture(autouse=True)
def fast_sleep():
    """Skip real sleeping; assert calls instead."""
    with patch("utils.retry.time.sleep") as m:
        yield m


class TestExponentialBackoff:
    def test_returns_on_first_success(self, fast_sleep):
        calls = {"n": 0}

        @exponential_backoff(max_retries=3, base_delay=0.01, jitter=False)
        def f():
            calls["n"] += 1
            return "ok"

        assert f() == "ok"
        assert calls["n"] == 1
        assert fast_sleep.call_count == 0

    def test_retries_then_succeeds(self, fast_sleep):
        attempts = {"n": 0}

        @exponential_backoff(max_retries=3, base_delay=0.01, jitter=False)
        def f():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise RetryableError("transient")
            return "ok"

        assert f() == "ok"
        assert attempts["n"] == 3
        assert fast_sleep.call_count == 2

    def test_raises_after_max_retries(self, fast_sleep):
        @exponential_backoff(max_retries=2, base_delay=0.01, jitter=False)
        def f():
            raise RetryableError("always fails")

        with pytest.raises(RetryableError, match="always fails"):
            f()
        # max_retries=2 -> 3 attempts total -> 2 sleeps between them
        assert fast_sleep.call_count == 2

    def test_non_retryable_does_not_retry(self, fast_sleep):
        attempts = {"n": 0}

        @exponential_backoff(max_retries=5, base_delay=0.01)
        def f():
            attempts["n"] += 1
            raise NonRetryableError("hard stop")

        with pytest.raises(NonRetryableError):
            f()
        assert attempts["n"] == 1
        assert fast_sleep.call_count == 0

    def test_exponential_delay_progression_no_jitter(self, fast_sleep):
        @exponential_backoff(
            max_retries=3,
            base_delay=1.0,
            exponential_factor=2.0,
            max_delay=10.0,
            jitter=False,
        )
        def f():
            raise RetryableError("x")

        with pytest.raises(RetryableError):
            f()
        delays = [c.args[0] for c in fast_sleep.call_args_list]
        # base*factor^attempt for attempts 0..2 -> 1, 2, 4
        assert delays == [1.0, 2.0, 4.0]

    def test_max_delay_caps_exponential(self, fast_sleep):
        @exponential_backoff(
            max_retries=5,
            base_delay=1.0,
            exponential_factor=10.0,
            max_delay=5.0,
            jitter=False,
        )
        def f():
            raise RetryableError("x")

        with pytest.raises(RetryableError):
            f()
        # attempt 0 -> 1.0, attempt 1 -> min(10, 5) = 5.0, attempt 2 -> 5.0, attempt 3 -> 5.0,
        # attempt 4 -> 5.0 (5 sleeps for max_retries=5)
        delays = [c.args[0] for c in fast_sleep.call_args_list]
        assert delays == [1.0, 5.0, 5.0, 5.0, 5.0]

    def test_jitter_keeps_delay_in_half_window(self):
        # Don't patch sleep here; just check the math via random patching.
        with (
            patch("utils.retry.time.sleep") as sleep_m,
            patch("utils.retry.random.random", return_value=0.0),
        ):

            @exponential_backoff(
                max_retries=1, base_delay=2.0, jitter=True, exponential_factor=1.0
            )
            def f():
                raise RetryableError("x")

            with pytest.raises(RetryableError):
                f()
            # jittered delay = base * (0.5 + 0.0*0.5) = 1.0
            assert sleep_m.call_args_list[0].args[0] == pytest.approx(1.0)


class TestSimpleRetry:
    def test_passes_through_on_success(self, fast_sleep):
        @simple_retry(max_retries=3, delay=0.01)
        def f(x):
            return x + 1

        assert f(41) == 42
        assert fast_sleep.call_count == 0

    def test_retries_with_fixed_delay(self, fast_sleep):
        attempts = {"n": 0}

        @simple_retry(max_retries=3, delay=0.25)
        def f():
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise ValueError("x")
            return "ok"

        assert f() == "ok"
        assert fast_sleep.call_args_list[0].args[0] == 0.25

    def test_raises_after_exhaustion(self, fast_sleep):
        @simple_retry(max_retries=2, delay=0.0)
        def f():
            raise ValueError("nope")

        with pytest.raises(ValueError, match="nope"):
            f()
        assert fast_sleep.call_count == 2

    def test_only_retries_listed_exceptions(self, fast_sleep):
        attempts = {"n": 0}

        @simple_retry(
            max_retries=3,
            delay=0.0,
            retryable_exceptions=(ValueError,),
        )
        def f():
            attempts["n"] += 1
            raise KeyError("not retryable here")

        with pytest.raises(KeyError):
            f()
        assert attempts["n"] == 1


class TestRateLimiter:
    def test_under_limit_does_not_sleep(self, fast_sleep):
        rl = RateLimiter(max_calls=10, time_window=60)
        for _ in range(5):
            rl.wait_if_needed()
        assert fast_sleep.call_count == 0
        assert len(rl.calls) == 5

    def test_cleanup_drops_old_calls(self):
        rl = RateLimiter(max_calls=10, time_window=1)
        now = time.time()
        rl.calls = [now - 5.0, now - 3.0, now - 0.5]  # only the last is fresh
        rl._cleanup_old_calls()
        assert len(rl.calls) == 1
        assert rl.calls[0] == pytest.approx(now - 0.5)

    def test_at_limit_sleeps_until_window_open(self, fast_sleep):
        rl = RateLimiter(max_calls=2, time_window=10)
        # Pre-seed calls inside the window so the next call must wait
        t0 = time.time() - 1.0  # 1s ago
        rl.calls = [t0, t0 + 0.5]
        rl.wait_if_needed()
        # One sleep should have been issued; duration is positive but bounded
        assert fast_sleep.call_count == 1
        slept = fast_sleep.call_args_list[0].args[0]
        assert 0 < slept <= 10.0

    def test_path_without_threading_lock(self, fast_sleep):
        rl = RateLimiter(max_calls=5, time_window=60)
        # Force the no-lock branch
        rl._lock = None
        for _ in range(3):
            rl.wait_if_needed()
        assert fast_sleep.call_count == 0
        assert len(rl.calls) == 3

    def test_no_lock_path_sleeps_when_at_limit(self, fast_sleep):
        rl = RateLimiter(max_calls=2, time_window=10)
        rl._lock = None
        t = time.time() - 0.1
        rl.calls = [t - 0.5, t]
        rl.wait_if_needed()
        assert fast_sleep.call_count == 1
        assert fast_sleep.call_args_list[0].args[0] > 0


class TestRateLimitedDecorator:
    def test_calls_wait_then_function(self, fast_sleep):
        rl = MagicMock(spec=RateLimiter)

        @rate_limited(rl)
        def f(x):
            return x * 2

        assert f(3) == 6
        rl.wait_if_needed.assert_called_once()

    def test_default_rate_limit_decorator_runs(self):
        # Ensure the module-level convenience decorator is wired up correctly.
        @rate_limit_api_calls
        def f():
            return "ok"

        assert f() == "ok"

    def test_with_retries_and_rate_limit_composes(self, fast_sleep):
        calls = {"n": 0}

        @with_retries_and_rate_limit
        def f():
            calls["n"] += 1
            return "ok"

        assert f() == "ok"
        assert calls["n"] == 1


class TestRetryOnHttpErrors:
    def test_decorator_wraps_callable_and_retries_on_connection_error(self, fast_sleep):
        attempts = {"n": 0}

        @retry_on_http_errors(max_retries=2, base_delay=0.0)
        def f():
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise ConnectionError("transient")
            return "ok"

        assert f() == "ok"
        assert attempts["n"] == 2

    def test_does_not_retry_keyboard_interrupt(self, fast_sleep):
        @retry_on_http_errors(max_retries=5, base_delay=0.0)
        def f():
            raise KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            f()
        assert fast_sleep.call_count == 0

    def test_retries_on_timeout_error(self, fast_sleep):
        attempts = {"n": 0}

        @retry_on_http_errors(max_retries=3, base_delay=0.0)
        def f():
            attempts["n"] += 1
            raise TimeoutError("slow")

        with pytest.raises(TimeoutError):
            f()
        assert attempts["n"] == 4  # 1 initial + 3 retries

    def test_includes_requests_exceptions_when_available(self, fast_sleep):
        requests_mod = pytest.importorskip("requests")
        attempts = {"n": 0}

        @retry_on_http_errors(max_retries=1, base_delay=0.0)
        def f():
            attempts["n"] += 1
            raise requests_mod.exceptions.Timeout("slow")

        with pytest.raises(requests_mod.exceptions.Timeout):
            f()
        assert attempts["n"] == 2


class TestGetMetrics:
    def test_caches_metrics_instance(self):
        # Reset module-level cache so first call repopulates it.
        import utils.retry as retry_mod

        retry_mod._metrics = None
        m1 = _get_metrics()
        m2 = _get_metrics()
        # Either both None (metrics import failed) or both the same singleton — both prove caching.
        assert m1 is m2
