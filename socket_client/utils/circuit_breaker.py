"""
Circuit breaker pattern implementation for the Socket Client.

This module provides a circuit breaker pattern to handle connection failures
and prevent cascading failures in the WebSocket client.
"""

import asyncio
import time
from collections.abc import Callable
from enum import Enum
from typing import TypeVar

from structlog import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class AsyncCircuitBreaker:
    """Async circuit breaker implementation."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        name: str = "default",
    ):
        """
        Initialize the circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time in seconds before attempting recovery
            expected_exception: Exception type to count as failures
            name: Circuit breaker name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self._lock = asyncio.Lock()

        logger.info(
            "Circuit breaker initialized",
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute a function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: When circuit is open
            Exception: Original function exception
        """
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    logger.info(
                        "Circuit breaker transitioning to half-open", name=self.name
                    )
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is open"
                    )

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            await self._on_success()
            return result

        except self.expected_exception:
            await self._on_failure()
            raise

    async def _on_success(self):
        """Handle successful execution."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                logger.info(
                    "Circuit breaker closed after successful execution", name=self.name
                )
            self.failure_count = 0

    async def _on_failure(self):
        """Handle failed execution."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            logger.warning(
                "Circuit breaker failure recorded",
                name=self.name,
                failure_count=self.failure_count,
                threshold=self.failure_threshold,
            )

            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(
                    "Circuit breaker opened due to failure threshold",
                    name=self.name,
                    failure_count=self.failure_count,
                )

    def get_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self.state

    def get_metrics(self) -> dict:
        """Get circuit breaker metrics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self.last_failure_time,
            "time_since_last_failure": time.time() - self.last_failure_time,
        }


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""

    pass


# Global circuit breaker instances
websocket_circuit_breaker = AsyncCircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=Exception,
    name="websocket",
)

nats_circuit_breaker = AsyncCircuitBreaker(
    failure_threshold=3, recovery_timeout=30, expected_exception=Exception, name="nats"
)
