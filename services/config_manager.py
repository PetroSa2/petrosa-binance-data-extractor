"""
Configuration manager for data extractor settings.

Persists configuration to MongoDB and provides access to runtime settings.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import constants
from db.mongodb_adapter import MongoDBAdapter

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration persistence in MongoDB."""

    def __init__(self, mongodb_uri: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            mongodb_uri: MongoDB connection string (defaults to constants.MONGODB_URI)
        """
        self.mongodb_uri = mongodb_uri or constants.MONGODB_URI
        self.adapter: Optional[MongoDBAdapter] = None
        self.collection_name = "data_extractor_config"

    def connect(self):
        """Connect to MongoDB."""
        if not self.adapter:
            self.adapter = MongoDBAdapter(
                self.mongodb_uri, database_name="petrosa_config"
            )
            self.adapter.connect()
            logger.info("Connected to MongoDB for configuration storage")

    def disconnect(self):
        """Disconnect from MongoDB."""
        if self.adapter:
            self.adapter.disconnect()
            self.adapter = None
            logger.info("Disconnected from MongoDB")

    def get_symbols(self) -> list[str]:
        """Get currently configured symbols for extraction."""
        self.connect()
        try:
            config = self._get_config("symbols")
            if config:
                return config.get("value", constants.DEFAULT_SYMBOLS)
            return constants.DEFAULT_SYMBOLS
        except Exception as e:
            logger.error(f"Error getting symbols: {e}")
            return constants.DEFAULT_SYMBOLS

    def set_symbols(
        self, symbols: list[str], changed_by: str, reason: Optional[str] = None
    ):
        """Update symbols for extraction."""
        self.connect()
        try:
            self._set_config(
                "symbols",
                {"value": symbols, "changed_by": changed_by, "reason": reason},
            )
            logger.info(f"Updated extraction symbols: {symbols}")
        except Exception as e:
            logger.error(f"Error setting symbols: {e}")
            raise

    def get_rate_limits(self) -> dict[str, Any]:
        """Get current rate limit configuration."""
        self.connect()
        try:
            config = self._get_config("rate_limits")
            if config:
                return config.get("value", {})
            return {
                "requests_per_minute": constants.API_RATE_LIMIT_PER_MINUTE,
                "concurrent_requests": constants.MAX_WORKERS,
            }
        except Exception as e:
            logger.error(f"Error getting rate limits: {e}")
            return {
                "requests_per_minute": constants.API_RATE_LIMIT_PER_MINUTE,
                "concurrent_requests": constants.MAX_WORKERS,
            }

    def set_rate_limits(
        self,
        requests_per_minute: int,
        concurrent_requests: int,
        changed_by: str,
        reason: Optional[str] = None,
    ):
        """Update rate limit configuration."""
        self.connect()
        try:
            self._set_config(
                "rate_limits",
                {
                    "value": {
                        "requests_per_minute": requests_per_minute,
                        "concurrent_requests": concurrent_requests,
                    },
                    "changed_by": changed_by,
                    "reason": reason,
                },
            )
            logger.info(
                f"Updated rate limits: {requests_per_minute}/min, {concurrent_requests} concurrent"
            )
        except Exception as e:
            logger.error(f"Error setting rate limits: {e}")
            raise

    def _get_config(self, key: str) -> Optional[dict[str, Any]]:
        """Get configuration value by key."""
        if not self.adapter or not self.adapter._connected:
            self.connect()

        collection = self.adapter.database[self.collection_name]
        doc = collection.find_one({"key": key})
        return doc

    def _set_config(self, key: str, value: dict[str, Any]):
        """Set configuration value by key."""
        if not self.adapter or not self.adapter._connected:
            self.connect()

        collection = self.adapter.database[self.collection_name]
        doc = {
            "key": key,
            "value": value.get("value"),
            "changed_by": value.get("changed_by"),
            "reason": value.get("reason"),
            "updated_at": datetime.utcnow(),
        }

        collection.update_one({"key": key}, {"$set": doc}, upsert=True)


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def set_config_manager(manager: ConfigManager):
    """Set global config manager instance (for testing)."""
    global _config_manager
    _config_manager = manager
