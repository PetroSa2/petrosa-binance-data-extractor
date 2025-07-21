"""
Unit tests for circuit breaker functionality.
"""

import time
from unittest.mock import Mock

import pytest

from utils.circuit_breaker import CircuitBreaker, DatabaseCircuitBreaker


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initialization."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)

        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 60
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0
        assert cb.total_calls == 0

    def test_successful_operation(self):
        """Test successful operation doesn't affect circuit."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        mock_func = Mock(return_value="success")

        result = cb.call(mock_func)

        assert result == "success"
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0
        assert cb.total_calls == 1
        assert cb.successful_calls == 1

    def test_failure_below_threshold(self):
        """Test failures below threshold don't open circuit."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        mock_func = Mock(side_effect=Exception("test error"))

        # First failure
        with pytest.raises(Exception):
            cb.call(mock_func)

        assert cb.state == "CLOSED"
        assert cb.failure_count == 1
        assert cb.total_calls == 1
        assert cb.failed_calls == 1

    def test_circuit_opens_after_threshold(self):
        """Test circuit opens after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        mock_func = Mock(side_effect=Exception("test error"))

        # First failure
        with pytest.raises(Exception):
            cb.call(mock_func)

        # Second failure - should open circuit
        with pytest.raises(Exception):
            cb.call(mock_func)

        assert cb.state == "OPEN"
        assert cb.failure_count == 2

    def test_circuit_blocks_when_open(self):
        """Test circuit blocks calls when open."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        mock_func = Mock(side_effect=Exception("test error"))

        # Trigger circuit to open
        with pytest.raises(Exception):
            cb.call(mock_func)

        # Circuit should be open and block calls
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            cb.call(mock_func)

    def test_circuit_recovery(self):
        """Test circuit recovery after timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        mock_func = Mock(side_effect=Exception("test error"))

        # Trigger circuit to open
        with pytest.raises(Exception):
            cb.call(mock_func)

        assert cb.state == "OPEN"

        # Wait for recovery timeout
        time.sleep(0.2)

        # Check if circuit transitions to HALF_OPEN by making a call
        # The call should not raise an exception if circuit is HALF_OPEN
        success_func = Mock(return_value="success")
        result = cb.call(success_func)

        assert result == "success"
        assert cb.state == "CLOSED"  # Should reset to CLOSED after successful call

    def test_circuit_reset_on_success(self):
        """Test circuit resets to CLOSED on successful operation."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        failing_func = Mock(side_effect=Exception("test error"))
        success_func = Mock(return_value="success")

        # Trigger circuit to open
        with pytest.raises(Exception):
            cb.call(failing_func)

        # Wait for recovery timeout
        time.sleep(0.2)

        # Successful call should reset circuit
        result = cb.call(success_func)

        assert result == "success"
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0

    def test_get_stats(self):
        """Test circuit breaker statistics."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        mock_func = Mock(side_effect=Exception("test error"))

        # Make some calls
        with pytest.raises(Exception):
            cb.call(mock_func)

        stats = cb.get_stats()

        assert stats["name"] == "circuit_breaker"
        assert stats["state"] == "CLOSED"
        assert stats["failure_count"] == 1
        assert stats["total_calls"] == 1
        assert stats["successful_calls"] == 0
        assert stats["failed_calls"] == 1
        assert stats["success_rate"] == 0.0

    def test_manual_reset(self):
        """Test manual circuit breaker reset."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        mock_func = Mock(side_effect=Exception("test error"))

        # Trigger circuit to open
        with pytest.raises(Exception):
            cb.call(mock_func)

        assert cb.state == "OPEN"

        # Manual reset
        cb.reset()

        assert cb.state == "CLOSED"
        assert cb.failure_count == 0
        assert cb.last_failure_time == 0


class TestDatabaseCircuitBreaker:
    """Test database-specific circuit breaker."""

    def test_database_circuit_breaker_initialization(self):
        """Test database circuit breaker initialization."""
        db_cb = DatabaseCircuitBreaker("mysql")

        assert db_cb.adapter_type == "mysql"
        assert db_cb.failure_threshold == 3  # Lower threshold for databases
        assert db_cb.recovery_timeout == 30  # Faster recovery for databases
        assert db_cb.name == "db_circuit_breaker_mysql"

    def test_different_adapter_types(self):
        """Test circuit breaker with different adapter types."""
        mysql_cb = DatabaseCircuitBreaker("mysql")
        mongodb_cb = DatabaseCircuitBreaker("mongodb")

        assert mysql_cb.adapter_type == "mysql"
        assert mongodb_cb.adapter_type == "mongodb"
        assert mysql_cb.name == "db_circuit_breaker_mysql"
        assert mongodb_cb.name == "db_circuit_breaker_mongodb"
