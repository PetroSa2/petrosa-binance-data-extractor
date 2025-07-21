"""
Unit tests for adaptive batch size management.
"""

from unittest.mock import patch

from utils.adaptive_batch import AdaptiveBatchManager, DatabaseSpecificBatchManager


class TestAdaptiveBatchManager:
    """Test adaptive batch manager functionality."""

    def test_initialization(self):
        """Test adaptive batch manager initialization."""
        manager = AdaptiveBatchManager(initial_batch_size=500)

        assert manager.current_batch_size == 500
        assert manager.min_batch_size == 100
        assert manager.max_batch_size == 2000
        assert manager.success_rate_threshold == 0.95
        assert manager.total_operations == 0

    def test_record_successful_operation(self):
        """Test recording successful operation."""
        manager = AdaptiveBatchManager(initial_batch_size=1000)

        manager.record_operation(success=True, duration=2.0)

        assert manager.total_operations == 1
        assert manager.successful_operations == 1
        assert manager.failed_operations == 0

    def test_record_failed_operation(self):
        """Test recording failed operation."""
        manager = AdaptiveBatchManager(initial_batch_size=1000)

        manager.record_operation(success=False, duration=5.0)

        assert manager.total_operations == 1
        assert manager.successful_operations == 0
        assert manager.failed_operations == 1

    def test_batch_size_increase_on_good_performance(self):
        """Test batch size increases on good performance."""
        manager = AdaptiveBatchManager(initial_batch_size=1000)

        # Record several successful, fast operations
        for _ in range(10):
            manager.record_operation(success=True, duration=2.0)

        # Batch size should increase
        assert manager.current_batch_size > 1000

    def test_batch_size_decrease_on_poor_performance(self):
        """Test batch size decreases on poor performance."""
        manager = AdaptiveBatchManager(initial_batch_size=1000)

        # Record several failed operations
        for _ in range(5):
            manager.record_operation(success=False, duration=10.0)

        # Batch size should decrease
        assert manager.current_batch_size < 1000

    def test_batch_size_stays_within_limits(self):
        """Test batch size stays within configured limits."""
        manager = AdaptiveBatchManager(
            initial_batch_size=1000,
            min_batch_size=100,
            max_batch_size=1500
        )

        # Try to increase beyond max
        for _ in range(20):
            manager.record_operation(success=True, duration=1.0)

        assert manager.current_batch_size <= 1500

        # Reset and try to decrease below min
        manager.reset()
        for _ in range(10):
            manager.record_operation(success=False, duration=15.0)

        assert manager.current_batch_size >= 100

    def test_get_batch_size(self):
        """Test getting current batch size."""
        manager = AdaptiveBatchManager(initial_batch_size=500)

        assert manager.get_batch_size() == 500

    def test_get_performance_stats(self):
        """Test getting performance statistics."""
        manager = AdaptiveBatchManager(initial_batch_size=1000)

        # Record some operations
        manager.record_operation(success=True, duration=2.0)
        manager.record_operation(success=True, duration=3.0)
        manager.record_operation(success=False, duration=8.0)

        stats = manager.get_performance_stats()

        assert stats["current_batch_size"] == 1000
        assert stats["total_operations"] == 3
        assert stats["successful_operations"] == 2
        assert stats["failed_operations"] == 1
        assert "success_rate" in stats
        assert "avg_duration" in stats

    def test_reset_functionality(self):
        """Test reset functionality."""
        manager = AdaptiveBatchManager(initial_batch_size=1000)

        # Record some operations
        manager.record_operation(success=True, duration=2.0)
        manager.record_operation(success=False, duration=5.0)

        assert manager.total_operations == 2

        # Reset
        manager.reset()

        assert manager.current_batch_size == 100  # Reset to min_batch_size
        assert manager.total_operations == 0
        assert manager.successful_operations == 0
        assert manager.failed_operations == 0

    def test_no_adjustment_with_insufficient_data(self):
        """Test no adjustment with insufficient data."""
        manager = AdaptiveBatchManager(initial_batch_size=1000)
        initial_size = manager.current_batch_size

        # Record only 3 operations (less than minimum 5)
        for _ in range(3):
            manager.record_operation(success=True, duration=2.0)

        # Batch size should not change
        assert manager.current_batch_size == initial_size

    def test_adjustment_with_sufficient_data(self):
        """Test adjustment with sufficient data."""
        manager = AdaptiveBatchManager(initial_batch_size=1000)

        # Record 10 successful, fast operations
        for _ in range(10):
            manager.record_operation(success=True, duration=2.0)

        # Batch size should increase
        assert manager.current_batch_size > 1000

    def test_high_failure_rate_decreases_batch_size(self):
        """Test high failure rate decreases batch size."""
        manager = AdaptiveBatchManager(initial_batch_size=1000)

        # Record operations with high failure rate
        for _ in range(10):
            manager.record_operation(success=False, duration=5.0)

        # Batch size should decrease
        assert manager.current_batch_size < 1000


class TestDatabaseSpecificBatchManager:
    """Test database-specific batch manager."""

    @patch('utils.adaptive_batch.constants')
    def test_mysql_shared_environment(self, mock_constants):
        """Test MySQL shared environment configuration."""
        mock_constants.MYSQL_SHARED_INSTANCE_CONFIG = {"batch_size": 500}
        mock_constants.DB_BATCH_SIZE = 1000

        manager = DatabaseSpecificBatchManager("mysql", "shared")

        assert manager.adapter_type == "mysql"
        assert manager.environment == "shared"
        assert manager.current_batch_size == 500

    @patch('utils.adaptive_batch.constants')
    def test_mongodb_free_tier_environment(self, mock_constants):
        """Test MongoDB free tier environment configuration."""
        mock_constants.MONGODB_ATLAS_FREE_TIER_CONFIG = {"batch_size": 200}
        mock_constants.DB_BATCH_SIZE = 1000

        manager = DatabaseSpecificBatchManager("mongodb", "free_tier")

        assert manager.adapter_type == "mongodb"
        assert manager.environment == "free_tier"
        assert manager.current_batch_size == 200

    @patch('utils.adaptive_batch.constants')
    def test_default_environment(self, mock_constants):
        """Test default environment configuration."""
        mock_constants.DB_BATCH_SIZE = 1000

        manager = DatabaseSpecificBatchManager("postgresql", "production")

        assert manager.adapter_type == "postgresql"
        assert manager.environment == "production"
        assert manager.current_batch_size == 1000

    def test_get_environment_constraints_mysql_shared(self):
        """Test environment constraints for MySQL shared."""
        manager = DatabaseSpecificBatchManager("mysql", "shared")
        constraints = manager.get_environment_constraints()

        assert constraints["max_connections"] == 10
        assert constraints["max_batch_size"] == 500
        assert constraints["connection_timeout"] == 30

    def test_get_environment_constraints_mongodb_free_tier(self):
        """Test environment constraints for MongoDB free tier."""
        manager = DatabaseSpecificBatchManager("mongodb", "free_tier")
        constraints = manager.get_environment_constraints()

        assert constraints["max_connections"] == 5
        assert constraints["max_batch_size"] == 200
        assert constraints["storage_limit_gb"] == 0.5
        assert constraints["connection_timeout"] == 5

    def test_get_environment_constraints_default(self):
        """Test environment constraints for default environment."""
        manager = DatabaseSpecificBatchManager("postgresql", "production")
        constraints = manager.get_environment_constraints()

        assert constraints["max_connections"] == 100
        assert constraints["max_batch_size"] == 2000
        assert constraints["connection_timeout"] == 30
