"""
Unit tests for error classification functionality.
"""

import pytest
from unittest.mock import Mock

from utils.error_classifier import (
    classify_database_error,
    get_retry_strategy,
    should_retry_operation,
    ErrorClassifier,
)


class TestErrorClassification:
    """Test error classification functionality."""

    def test_mysql_connection_errors(self):
        """Test MySQL connection error classification."""
        # Test various MySQL connection errors
        mysql_errors = [
            Exception("Lost connection to MySQL server"),
            Exception("MySQL server has gone away"),
            Exception("Connection was killed"),
            Exception("Error 2013: Lost connection to MySQL server"),
            Exception("Error 2006: MySQL server has gone away"),
            Exception("Error 2003: Can't connect to MySQL server"),
            Exception("Connection refused"),
            Exception("MySQL connection pool exhausted"),  # Updated to be MySQL-specific
        ]
        
        for error in mysql_errors:
            classification = classify_database_error(error)
            assert classification == "CONNECTION_LOST"

    def test_mongodb_connection_errors(self):
        """Test MongoDB connection error classification."""
        # Test various MongoDB connection errors
        mongodb_errors = [
            Exception("MongoDB connection pool exhausted"),  # Updated to be MongoDB-specific
            Exception("Server selection timeout"),
            Exception("Network timeout"),
            Exception("Read timeout"),
            Exception("Write timeout"),
        ]
        
        for error in mongodb_errors:
            classification = classify_database_error(error)
            assert classification == "CONNECTION_TIMEOUT"

    def test_resource_exhaustion_errors(self):
        """Test resource exhaustion error classification."""
        resource_errors = [
            Exception("Too many connections"),
            Exception("Connection limit exceeded"),
            Exception("Pool exhausted"),
            Exception("Out of memory"),
            Exception("Insufficient memory"),
            Exception("Disk space"),
            Exception("Storage full"),
        ]
        
        for error in resource_errors:
            classification = classify_database_error(error)
            assert classification == "RESOURCE_EXHAUSTED"

    def test_data_integrity_errors(self):
        """Test data integrity error classification."""
        integrity_errors = [
            Exception("Duplicate key"),
            Exception("Integrity constraint"),
            Exception("Unique constraint"),
            Exception("Primary key"),
            Exception("Duplicate entry"),
        ]
        
        for error in integrity_errors:
            classification = classify_database_error(error)
            assert classification == "DATA_INTEGRITY"

    def test_authentication_errors(self):
        """Test authentication error classification."""
        auth_errors = [
            Exception("Access denied"),
            Exception("Authentication failed"),
            Exception("Unauthorized"),
            Exception("Permission denied"),
            Exception("Invalid credentials"),
        ]
        
        for error in auth_errors:
            classification = classify_database_error(error)
            assert classification == "AUTHENTICATION_ERROR"

    def test_rate_limit_errors(self):
        """Test rate limit error classification."""
        rate_limit_errors = [
            Exception("Rate limit"),
            Exception("Too many requests"),
            Exception("Error 429"),
            Exception("Rate limit exceeded"),
            Exception("Throttling"),
            Exception("Quota exceeded"),
        ]
        
        for error in rate_limit_errors:
            classification = classify_database_error(error)
            assert classification == "RATE_LIMIT"

    def test_temporary_errors(self):
        """Test temporary error classification."""
        temp_errors = [
            Exception("Temporary failure"),
            Exception("Temporary error"),
            Exception("Service unavailable"),
            Exception("Bad gateway"),
            Exception("Gateway timeout"),
            Exception("Internal server error"),
            Exception("Error 503"),
            Exception("Error 502"),
            Exception("Error 504"),
        ]
        
        for error in temp_errors:
            classification = classify_database_error(error)
            assert classification == "TEMPORARY_ERROR"

    def test_network_errors(self):
        """Test network error classification."""
        network_errors = [
            Exception("DNS resolution failed"),
            Exception("Name resolution failed"),
            Exception("SSL certificate"),
            Exception("Certificate verify failed"),
            Exception("TLS handshake"),
            Exception("Connection aborted"),
            Exception("Connection reset"),
            Exception("Socket timeout"),  # This should be NETWORK_ERROR
            Exception("Network unreachable"),
        ]
        
        for error in network_errors:
            classification = classify_database_error(error)
            assert classification == "NETWORK_ERROR"

    def test_unknown_errors(self):
        """Test unknown error classification."""
        unknown_errors = [
            Exception("Some random error"),
            Exception("Unexpected error"),
            Exception("Unknown issue"),
        ]
        
        for error in unknown_errors:
            classification = classify_database_error(error)
            assert classification == "UNKNOWN_ERROR"


class TestRetryStrategy:
    """Test retry strategy functionality."""

    def test_connection_lost_strategy(self):
        """Test retry strategy for connection lost errors."""
        strategy = get_retry_strategy("CONNECTION_LOST")
        
        assert strategy["max_retries"] == 3
        assert strategy["base_delay"] == 2.0
        assert strategy["max_delay"] == 30.0
        assert strategy["should_retry"] is True
        assert strategy["backoff_multiplier"] == 2.0

    def test_connection_timeout_strategy(self):
        """Test retry strategy for connection timeout errors."""
        strategy = get_retry_strategy("CONNECTION_TIMEOUT")
        
        assert strategy["max_retries"] == 2
        assert strategy["base_delay"] == 5.0
        assert strategy["max_delay"] == 60.0
        assert strategy["should_retry"] is True

    def test_resource_exhausted_strategy(self):
        """Test retry strategy for resource exhaustion errors."""
        strategy = get_retry_strategy("RESOURCE_EXHAUSTED")
        
        assert strategy["max_retries"] == 1
        assert strategy["base_delay"] == 10.0
        assert strategy["max_delay"] == 120.0
        assert strategy["should_retry"] is True

    def test_data_integrity_strategy(self):
        """Test retry strategy for data integrity errors."""
        strategy = get_retry_strategy("DATA_INTEGRITY")
        
        assert strategy["max_retries"] == 0
        assert strategy["should_retry"] is False

    def test_authentication_error_strategy(self):
        """Test retry strategy for authentication errors."""
        strategy = get_retry_strategy("AUTHENTICATION_ERROR")
        
        assert strategy["max_retries"] == 0
        assert strategy["should_retry"] is False

    def test_rate_limit_strategy(self):
        """Test retry strategy for rate limit errors."""
        strategy = get_retry_strategy("RATE_LIMIT")
        
        assert strategy["max_retries"] == 2
        assert strategy["base_delay"] == 30.0
        assert strategy["max_delay"] == 300.0
        assert strategy["should_retry"] is True

    def test_unknown_error_strategy(self):
        """Test retry strategy for unknown errors."""
        strategy = get_retry_strategy("UNKNOWN_ERROR")
        
        assert strategy["max_retries"] == 1
        assert strategy["base_delay"] == 1.0
        assert strategy["max_delay"] == 10.0
        assert strategy["should_retry"] is True


class TestShouldRetryOperation:
    """Test should retry operation functionality."""

    def test_should_retry_connection_lost(self):
        """Test should retry for connection lost error."""
        error = Exception("Lost connection to MySQL server")
        should_retry, strategy = should_retry_operation(error)
        
        assert should_retry is True
        assert strategy["max_retries"] == 3

    def test_should_not_retry_data_integrity(self):
        """Test should not retry for data integrity error."""
        error = Exception("Duplicate key")
        should_retry, strategy = should_retry_operation(error)
        
        assert should_retry is False
        assert strategy["max_retries"] == 0

    def test_should_not_retry_authentication(self):
        """Test should not retry for authentication error."""
        error = Exception("Access denied")
        should_retry, strategy = should_retry_operation(error)
        
        assert should_retry is False
        assert strategy["max_retries"] == 0


class TestErrorClassifier:
    """Test error classifier with statistics."""

    def test_error_classifier_initialization(self):
        """Test error classifier initialization."""
        classifier = ErrorClassifier()
        
        assert classifier.total_errors == 0
        assert classifier.error_counts == {}

    def test_classify_and_log(self):
        """Test classify and log functionality."""
        classifier = ErrorClassifier()
        error = Exception("Lost connection to MySQL server")
        
        classification = classifier.classify_and_log(error)
        
        assert classification == "CONNECTION_LOST"
        assert classifier.total_errors == 1
        assert classifier.error_counts["CONNECTION_LOST"] == 1

    def test_error_statistics(self):
        """Test error statistics collection."""
        classifier = ErrorClassifier()
        
        # Add some errors
        errors = [
            Exception("Lost connection to MySQL server"),
            Exception("Duplicate key"),
            Exception("Lost connection to MySQL server"),
            Exception("Rate limit"),
        ]
        
        for error in errors:
            classifier.classify_and_log(error)
        
        stats = classifier.get_error_stats()
        
        assert stats["total_errors"] == 4
        assert stats["error_counts"]["CONNECTION_LOST"] == 2
        assert stats["error_counts"]["DATA_INTEGRITY"] == 1
        assert stats["error_counts"]["RATE_LIMIT"] == 1
        assert "CONNECTION_LOST" in stats["error_distribution"]
        assert stats["error_distribution"]["CONNECTION_LOST"] == 0.5

    def test_reset_stats(self):
        """Test reset statistics functionality."""
        classifier = ErrorClassifier()
        error = Exception("Lost connection to MySQL server")
        
        classifier.classify_and_log(error)
        assert classifier.total_errors == 1
        
        classifier.reset_stats()
        assert classifier.total_errors == 0
        assert classifier.error_counts == {} 