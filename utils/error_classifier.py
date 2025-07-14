"""
Enhanced error classification for database operations.

This module provides intelligent error classification to determine
appropriate retry strategies and handling for different types of errors.
"""

import logging
import re
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


def classify_database_error(error: Exception) -> str:
    """
    Classify database errors for appropriate handling.

    Args:
        error: The exception to classify

    Returns:
        Error classification string
    """
    error_msg = str(error).lower()
    error_type = type(error).__name__.lower()

    # 'connection pool exhausted' special handling (timeout, not network error)
    if "connection pool exhausted" in error_msg:
        if "mysql" in error_msg:
            return "CONNECTION_LOST"
        elif "mongodb" in error_msg or "mongo" in error_msg:
            return "CONNECTION_TIMEOUT"
        else:
            return "CONNECTION_TIMEOUT"

    # Authentication/Authorization (check first as it's most specific)
    if any(keyword in error_msg for keyword in [
        "access denied",
        "authentication failed",
        "unauthorized",
        "permission denied",
        "invalid credentials",
        "authenticationerror",
    ]):
        return "AUTHENTICATION_ERROR"

    # Data integrity (check early as it's specific)
    if any(keyword in error_msg for keyword in [
        "duplicate key",
        "integrity constraint",
        "unique constraint",
        "primary key",
        "duplicate entry",
        "bulkwriteerror",
        "duplicatekeyerror",
    ]) or "duplicatekeyerror" in error_type or "integrityerror" in error_type:
        return "DATA_INTEGRITY"

    # API rate limiting (specific pattern)
    if any(keyword in error_msg for keyword in [
        "rate limit",
        "too many requests",
        "429",
        "rate limit exceeded",
        "throttling",
        "quota exceeded",
    ]):
        return "RATE_LIMIT"

    # Temporary/Transient errors (specific patterns)
    if any(keyword in error_msg for keyword in [
        "temporary failure",
        "temporary error",
        "service unavailable",
        "bad gateway",
        "gateway timeout",
        "internal server error",
        "503",
        "502",
        "504",
    ]):
        return "TEMPORARY_ERROR"

    # Network errors (specific patterns, use regex for exact match)
    network_error_patterns = [
        r"dns resolution failed",
        r"name resolution failed",
        r"ssl certificate",
        r"certificate verify failed",
        r"tls handshake",
        r"\bconnection aborted\b",
        r"\bconnection reset\b",
        r"socket timeout",
        r"network unreachable",
    ]
    for pattern in network_error_patterns:
        if re.search(pattern, error_msg):
            return "NETWORK_ERROR"

    # MongoDB-specific connection errors
    if any(keyword in error_msg for keyword in [
        "server selection timeout",
        "network timeout",
        "socket timeout",
        "read timeout",
        "write timeout",
    ]) or "connectionfailure" in error_type:
        return "CONNECTION_TIMEOUT"

    # MySQL-specific connection errors
    if any(keyword in error_msg for keyword in [
        "lost connection to mysql server",
        "mysql server has gone away",
        "connection was killed",
        "2013", "2006", "2003",  # MySQL error codes
        "connection refused",
        "can't connect to mysql server",
        "operationalerror",
        "databaseerror",
        "connection reset by peer",
        "network is unreachable",
        "no route to host",
        "host is unreachable",
    ]) or "operationalerror" in error_type or "databaseerror" in error_type:
        return "CONNECTION_LOST"

    # Resource exhaustion (specific patterns, after connection errors)
    if any(keyword in error_msg for keyword in [
        "too many connections",
        "connection limit exceeded",
        "pool exhausted",
        "max connections",
        "connection pool is at maximum capacity",
        "out of memory",
        "insufficient memory",
        "disk space",
        "storage full",
    ]):
        return "RESOURCE_EXHAUSTED"

    return "UNKNOWN_ERROR"


def get_retry_strategy(error_classification: str) -> Dict:
    """
    Get retry strategy based on error classification.

    Args:
        error_classification: The classified error type

    Returns:
        Retry strategy configuration
    """
    strategies = {
        "CONNECTION_LOST": {
            "max_retries": 3,
            "base_delay": 2.0,
            "max_delay": 30.0,
            "should_retry": True,
            "backoff_multiplier": 2.0,
        },
        "CONNECTION_TIMEOUT": {
            "max_retries": 2,
            "base_delay": 5.0,
            "max_delay": 60.0,
            "should_retry": True,
            "backoff_multiplier": 2.0,
        },
        "RESOURCE_EXHAUSTED": {
            "max_retries": 1,
            "base_delay": 10.0,
            "max_delay": 120.0,
            "should_retry": True,
            "backoff_multiplier": 3.0,
        },
        "DATA_INTEGRITY": {
            "max_retries": 0,
            "base_delay": 0.0,
            "max_delay": 0.0,
            "should_retry": False,
            "backoff_multiplier": 1.0,
        },
        "AUTHENTICATION_ERROR": {
            "max_retries": 0,
            "base_delay": 0.0,
            "max_delay": 0.0,
            "should_retry": False,
            "backoff_multiplier": 1.0,
        },
        "RATE_LIMIT": {
            "max_retries": 2,
            "base_delay": 30.0,
            "max_delay": 300.0,
            "should_retry": True,
            "backoff_multiplier": 2.0,
        },
        "TEMPORARY_ERROR": {
            "max_retries": 3,
            "base_delay": 5.0,
            "max_delay": 60.0,
            "should_retry": True,
            "backoff_multiplier": 2.0,
        },
        "NETWORK_ERROR": {
            "max_retries": 2,
            "base_delay": 3.0,
            "max_delay": 30.0,
            "should_retry": True,
            "backoff_multiplier": 2.0,
        },
        "UNKNOWN_ERROR": {
            "max_retries": 1,
            "base_delay": 1.0,
            "max_delay": 10.0,
            "should_retry": True,
            "backoff_multiplier": 2.0,
        },
    }

    return strategies.get(error_classification, strategies["UNKNOWN_ERROR"])


def should_retry_operation(error: Exception) -> Tuple[bool, Dict]:
    """
    Determine if an operation should be retried based on the error.

    Args:
        error: The exception that occurred

    Returns:
        Tuple of (should_retry, retry_strategy)
    """
    error_classification = classify_database_error(error)
    retry_strategy = get_retry_strategy(error_classification)

    logger.debug(f"Error classified as {error_classification}: {error}")

    return retry_strategy["should_retry"], retry_strategy


class ErrorClassifier:
    """
    Enhanced error classifier with statistics and monitoring.
    """

    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.total_errors = 0

    def classify_and_log(self, error: Exception) -> str:
        """
        Classify error and log statistics.

        Args:
            error: The exception to classify

        Returns:
            Error classification
        """
        classification = classify_database_error(error)

        # Update statistics
        self.error_counts[classification] = self.error_counts.get(classification, 0) + 1
        self.total_errors += 1

        # Log if this is a new error type or high frequency
        if self.error_counts[classification] == 1:
            logger.info(f"New error classification: {classification}")
        elif self.error_counts[classification] % 10 == 0:
            logger.warning(f"Error classification {classification} occurred {self.error_counts[classification]} times")

        return classification

    def get_error_stats(self) -> Dict:
        """Get error classification statistics."""
        return {
            "total_errors": self.total_errors,
            "error_counts": self.error_counts.copy(),
            "error_distribution": {
                error_type: count / self.total_errors
                for error_type, count in self.error_counts.items()
            } if self.total_errors > 0 else {}
        }

    def reset_stats(self):
        """Reset error statistics."""
        self.error_counts.clear()
        self.total_errors = 0
