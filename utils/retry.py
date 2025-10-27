"""
Retry utility with exponential backoff for API calls.
"""

import logging
import random
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

import constants

logger = logging.getLogger(__name__)

# Import metrics lazily to avoid circular imports
_metrics = None


def _get_metrics():
    """Lazy load metrics to avoid circular imports."""
    global _metrics
    if _metrics is None:
        try:
            from utils.metrics import get_metrics

            _metrics = get_metrics()
        except ImportError:
            pass
    return _metrics


class RetryableError(Exception):
    """Base class for errors that should trigger retries."""


class NonRetryableError(Exception):
    """Base class for errors that should not trigger retries."""


def exponential_backoff(
    max_retries: int | None = None,
    base_delay: float | None = None,
    max_delay: float = 60.0,
    exponential_factor: float | None = None,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    non_retryable_exceptions: tuple[type[Exception], ...] = (NonRetryableError,),
):
    """
    Decorator that implements exponential backoff retry logic.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_factor: Factor to multiply delay by on each retry
        jitter: Whether to add random jitter to delays
        retryable_exceptions: Tuple of exception types that should trigger retries
        non_retryable_exceptions: Tuple of exception types that should not trigger retries
    """
    # Use constants as defaults
    max_retries = max_retries or constants.MAX_RETRIES
    base_delay = base_delay or constants.RETRY_BACKOFF_SECONDS
    exponential_factor = exponential_factor or constants.RETRY_BACKOFF_MULTIPLIER

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):  # +1 for initial attempt
                try:
                    return func(*args, **kwargs)

                except non_retryable_exceptions as e:
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                    raise

                except retryable_exceptions as e:
                    last_exception = e

                    if attempt == max_retries:  # Last attempt
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}: {e}"
                        )
                        raise

                    # Calculate delay for next attempt
                    delay = min(base_delay * (exponential_factor**attempt), max_delay)

                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay = delay * (0.5 + random.random() * 0.5)

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )

                    time.sleep(delay)

            # This should never be reached, but just in case
            raise last_exception or Exception("Unexpected retry loop exit")

        return wrapper

    return decorator


def simple_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """
    Simple retry decorator with fixed delay.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Fixed delay between retries in seconds
        retryable_exceptions: Tuple of exception types that should trigger retries
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        raise

                    logger.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {delay}s..."
                    )
                    time.sleep(delay)

            raise last_exception or Exception("Unexpected retry loop exit")

        return wrapper

    return decorator


class RateLimiter:
    """
    Rate limiter to prevent API rate limit violations.
    """

    def __init__(self, max_calls: int = 1200, time_window: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_calls: Maximum number of calls allowed
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: list[float] = []
        self._lock = None

        # Try to use threading lock if available
        try:
            import threading

            self._lock = threading.Lock()
        except ImportError:
            pass

    def wait_if_needed(self):
        """Wait if rate limit would be exceeded."""
        if self._lock:
            with self._lock:
                self._cleanup_old_calls()

                if len(self.calls) >= self.max_calls:
                    sleep_time = self.calls[0] + self.time_window - time.time()
                    if sleep_time > 0:
                        logger.info(
                            f"Rate limit reached, sleeping for {sleep_time:.2f} seconds"
                        )
                        time.sleep(sleep_time)
                        self._cleanup_old_calls()

                self.calls.append(time.time())

                # Record rate limit metrics once after updating calls
                used = len(self.calls)
                remaining = self.max_calls - used
                metrics = _get_metrics()
                if metrics:
                    metrics.record_rate_limit_usage(used, remaining, self.max_calls)
        else:
            # No threading available, simplified version
            current_time = time.time()
            self.calls = [
                call_time
                for call_time in self.calls
                if current_time - call_time < self.time_window
            ]

            if len(self.calls) >= self.max_calls:
                sleep_time = self.calls[0] + self.time_window - current_time
                if sleep_time > 0:
                    logger.info(
                        f"Rate limit reached, sleeping for {sleep_time:.2f} seconds"
                    )
                    time.sleep(sleep_time)

            self.calls.append(current_time)

            # Record rate limit metrics once after updating calls
            used = len(self.calls)
            remaining = self.max_calls - used
            metrics = _get_metrics()
            if metrics:
                metrics.record_rate_limit_usage(used, remaining, self.max_calls)

    def _cleanup_old_calls(self):
        """Remove calls outside the time window."""
        current_time = time.time()
        self.calls = [
            call_time
            for call_time in self.calls
            if current_time - call_time < self.time_window
        ]


def rate_limited(rate_limiter: RateLimiter):
    """
    Decorator to apply rate limiting to functions.

    Args:
        rate_limiter: RateLimiter instance
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            rate_limiter.wait_if_needed()
            return func(*args, **kwargs)

        return wrapper

    return decorator


# Global rate limiter instance
default_rate_limiter = RateLimiter(
    max_calls=constants.API_RATE_LIMIT_PER_MINUTE, time_window=60
)

# Convenience decorators using default settings
retry_on_failure = exponential_backoff()
rate_limit_api_calls = rate_limited(default_rate_limiter)


def with_retries_and_rate_limit(func: Callable) -> Callable:
    """
    Convenience decorator that combines retry logic and rate limiting.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function with retry and rate limiting
    """
    return retry_on_failure(rate_limit_api_calls(func))


# HTTP-specific retry decorator
def retry_on_http_errors(
    max_retries: int | None = None, base_delay: float | None = None
):
    """
    Retry decorator specifically for HTTP errors.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries
    """
    # Define HTTP-specific retryable exceptions
    http_retryable_exceptions: tuple[type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
    )

    # Try to import requests exceptions if available
    try:
        from requests.exceptions import (
            ConnectionError as RequestsConnectionError,
            RequestException,
            Timeout,
        )

        http_retryable_exceptions = http_retryable_exceptions + (
            RequestException,
            Timeout,
            RequestsConnectionError,
        )
    except ImportError:
        pass

    # Try to import aiohttp exceptions if available
    try:
        from aiohttp import ClientError, ServerTimeoutError

        http_retryable_exceptions = http_retryable_exceptions + (
            ClientError,
            ServerTimeoutError,
        )
    except ImportError:
        pass

    return exponential_backoff(
        max_retries=max_retries,
        base_delay=base_delay,
        retryable_exceptions=http_retryable_exceptions,
        non_retryable_exceptions=(KeyboardInterrupt, SystemExit, NonRetryableError),  # type: ignore[arg-type]
    )
