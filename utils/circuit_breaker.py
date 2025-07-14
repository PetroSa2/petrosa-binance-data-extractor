"""
Circuit Breaker pattern implementation for database operations.

This module provides a circuit breaker pattern to prevent cascading failures
when database operations are experiencing issues.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit breaker pattern for database operations.
    
    States:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Calls are blocked, circuit is broken
    - HALF_OPEN: Limited calls allowed to test recovery
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type[BaseException] = Exception,
        name: str = "circuit_breaker"
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type to monitor
            name: Name for logging purposes
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        
        # State tracking
        self.failure_count = 0
        self.last_failure_time: float = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        
        # Statistics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        self.total_calls += 1
        
        # Check circuit state
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                logger.info(f"{self.name}: Circuit transitioning to HALF_OPEN")
                self.state = "HALF_OPEN"
            else:
                raise Exception(f"{self.name}: Circuit breaker is OPEN")
        
        # Execute function
        try:
            result = func(*args, **kwargs)
            self.successful_calls += 1
            
            # Reset on success
            if self.state == "HALF_OPEN":
                logger.info(f"{self.name}: Circuit recovered, transitioning to CLOSED")
                self.state = "CLOSED"
                self.failure_count = 0
                
            return result
            
        except self.expected_exception as e:
            self.failed_calls += 1
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            logger.warning(
                f"{self.name}: Function failed (attempt {self.failure_count}/{self.failure_threshold}): {e}"
            )
            
            # Check if circuit should open
            if self.failure_count >= self.failure_threshold:
                logger.error(f"{self.name}: Circuit breaker opening after {self.failure_count} failures")
                self.state = "OPEN"
            
            raise e
        except Exception as e:
            # Non-expected exceptions don't count toward circuit breaker
            self.failed_calls += 1
            raise e
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": self.successful_calls / self.total_calls if self.total_calls > 0 else 0,
            "last_failure_time": self.last_failure_time,
        }
    
    def reset(self):
        """Manually reset the circuit breaker."""
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_failure_time = 0
        logger.info(f"{self.name}: Circuit breaker manually reset")


class DatabaseCircuitBreaker(CircuitBreaker):
    """
    Specialized circuit breaker for database operations.
    """
    
    def __init__(self, adapter_type: str = "unknown"):
        """
        Initialize database circuit breaker.
        
        Args:
            adapter_type: Type of database adapter (mysql, mongodb, etc.)
        """
        super().__init__(
            failure_threshold=3,  # Lower threshold for databases
            recovery_timeout=30,   # Faster recovery for databases
            expected_exception=Exception,
            name=f"db_circuit_breaker_{adapter_type}"
        )
        self.adapter_type = adapter_type 