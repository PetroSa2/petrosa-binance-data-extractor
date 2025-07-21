"""
Adaptive batch size management for database operations.

This module provides intelligent batch size adjustment based on
performance metrics and database constraints.
"""

import logging
import time
from typing import Dict, List, Optional

import constants

logger = logging.getLogger(__name__)


class AdaptiveBatchManager:
    """
    Dynamically adjusts batch sizes based on performance and constraints.
    """

    def __init__(
        self,
        initial_batch_size: int = 1000,
        min_batch_size: Optional[int] = None,
        max_batch_size: Optional[int] = None,
        success_rate_threshold: Optional[float] = None,
        adjustment_factor: float = 0.1,
        min_success_rate: float = 0.8,
    ):
        """
        Initialize adaptive batch manager.
        
        Args:
            initial_batch_size: Starting batch size
            min_batch_size: Minimum allowed batch size
            max_batch_size: Maximum allowed batch size
            success_rate_threshold: Threshold for success rate evaluation
            adjustment_factor: Factor for batch size adjustments
            min_success_rate: Minimum success rate before reducing batch size
        """
        self.current_batch_size = initial_batch_size
        self.min_batch_size = min_batch_size or constants.MIN_BATCH_SIZE
        self.max_batch_size = max_batch_size or constants.MAX_BATCH_SIZE
        self.success_rate_threshold = success_rate_threshold or constants.SUCCESS_RATE_THRESHOLD
        self.adjustment_factor = adjustment_factor
        self.min_success_rate = min_success_rate

        # Performance tracking
        self.operation_history: List[Dict] = []
        self.max_history_size = 50

        # Statistics
        self.total_operations = 0
        self.successful_operations = 0
        self.failed_operations = 0

    def record_operation(self, success: bool, duration: float, batch_size: Optional[int] = None):
        """
        Record operation result for batch size adjustment.
        
        Args:
            success: Whether the operation was successful
            duration: Operation duration in seconds
            batch_size: Actual batch size used (if different from current)
        """
        actual_batch_size = batch_size or self.current_batch_size

        operation_record = {
            "timestamp": time.time(),
            "success": success,
            "duration": duration,
            "batch_size": actual_batch_size,
        }

        self.operation_history.append(operation_record)

        # Keep history size manageable
        if len(self.operation_history) > self.max_history_size:
            self.operation_history.pop(0)

        # Update statistics
        self.total_operations += 1
        if success:
            self.successful_operations += 1
        else:
            self.failed_operations += 1

        # Adjust batch size based on recent performance
        self._adjust_batch_size()

    def _adjust_batch_size(self):
        """Adjust batch size based on recent performance."""
        if len(self.operation_history) < 5:
            return  # Need minimum data for adjustment

        # Calculate recent performance metrics
        recent_operations = self.operation_history[-10:]  # Last 10 operations
        success_rate = sum(1 for op in recent_operations if op["success"]) / len(recent_operations)
        avg_duration = sum(op["duration"] for op in recent_operations) / len(recent_operations)

        # Determine if adjustment is needed
        should_increase = (
            success_rate >= self.success_rate_threshold and
            avg_duration < 5.0 and  # Fast operations
            self.current_batch_size < self.max_batch_size
        )

        should_decrease = (
            success_rate < self.min_success_rate or
            avg_duration > 10.0 or  # Slow operations
            self.failed_operations > self.successful_operations * 0.2  # High failure rate
        )

        old_batch_size = self.current_batch_size

        if should_increase:
            # Increase batch size
            increase_factor = 1 + self.adjustment_factor
            self.current_batch_size = min(
                self.max_batch_size,
                int(self.current_batch_size * increase_factor)
            )
            logger.info(f"Batch size increased from {old_batch_size} to {self.current_batch_size}")

        elif should_decrease:
            # Decrease batch size
            decrease_factor = 1 - self.adjustment_factor
            self.current_batch_size = max(
                self.min_batch_size,
                int(self.current_batch_size * decrease_factor)
            )
            logger.warning(f"Batch size decreased from {old_batch_size} to {self.current_batch_size}")

    def get_batch_size(self) -> int:
        """Get current batch size."""
        return self.current_batch_size

    def get_performance_stats(self) -> Dict:
        """Get performance statistics."""
        if not self.operation_history:
            return {
                "current_batch_size": self.current_batch_size,
                "total_operations": 0,
                "success_rate": 0.0,
                "avg_duration": 0.0,
            }

        recent_operations = self.operation_history[-20:]  # Last 20 operations
        success_rate = sum(1 for op in recent_operations if op["success"]) / len(recent_operations)
        avg_duration = sum(op["duration"] for op in recent_operations) / len(recent_operations)

        return {
            "current_batch_size": self.current_batch_size,
            "total_operations": self.total_operations,
            "successful_operations": self.successful_operations,
            "failed_operations": self.failed_operations,
            "success_rate": success_rate,
            "avg_duration": avg_duration,
            "min_batch_size": self.min_batch_size,
            "max_batch_size": self.max_batch_size,
        }

    def reset(self):
        """Reset the batch manager to initial state."""
        self.current_batch_size = self.min_batch_size
        self.operation_history.clear()
        self.total_operations = 0
        self.successful_operations = 0
        self.failed_operations = 0
        logger.info("Batch manager reset to initial state")


class DatabaseSpecificBatchManager(AdaptiveBatchManager):
    """
    Database-specific batch manager with environment-aware configurations.
    """

    def __init__(self, adapter_type: str, environment: str = "production"):
        """
        Initialize database-specific batch manager.
        
        Args:
            adapter_type: Type of database adapter (mysql, mongodb, etc.)
            environment: Environment (production, development, shared, free_tier)
        """
        # Get database-specific configuration
        if adapter_type == "mysql" and environment == "shared":
            initial_batch_size = constants.MYSQL_SHARED_INSTANCE_CONFIG["batch_size"]
        elif adapter_type == "mongodb" and environment == "free_tier":
            initial_batch_size = constants.MONGODB_ATLAS_FREE_TIER_CONFIG["batch_size"]
        else:
            initial_batch_size = constants.DB_BATCH_SIZE

        super().__init__(initial_batch_size=initial_batch_size)
        self.adapter_type = adapter_type
        self.environment = environment

        logger.info(f"Initialized {adapter_type} batch manager for {environment} environment")

    def get_environment_constraints(self) -> Dict:
        """Get environment-specific constraints."""
        if self.adapter_type == "mysql" and self.environment == "shared":
            return {
                "max_connections": 10,
                "max_batch_size": 500,
                "connection_timeout": 30,
            }
        elif self.adapter_type == "mongodb" and self.environment == "free_tier":
            return {
                "max_connections": 5,
                "max_batch_size": 200,
                "storage_limit_gb": 0.5,
                "connection_timeout": 5,
            }
        else:
            return {
                "max_connections": 100,
                "max_batch_size": 2000,
                "connection_timeout": 30,
            }
