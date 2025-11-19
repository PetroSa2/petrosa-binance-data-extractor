"""
Tests for configuration manager service.
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from services.config_manager import ConfigManager, get_config_manager, set_config_manager  # noqa: E402


class TestConfigManager:
    """Test configuration manager."""

    @patch("services.config_manager.MongoDBAdapter")
    def test_get_symbols_default(self, mock_adapter_class):
        """Test getting default symbols when no config exists."""
        mock_adapter = Mock()
        mock_adapter._connected = True
        mock_adapter.database = Mock()
        mock_collection = Mock()
        mock_collection.find_one = Mock(return_value=None)
        mock_adapter.database.__getitem__ = Mock(return_value=mock_collection)
        mock_adapter_class.return_value = mock_adapter

        manager = ConfigManager()
        manager.adapter = mock_adapter
        manager.adapter._connected = True

        symbols = manager.get_symbols()
        assert symbols == ["BTCUSDT", "ETHUSDT", "BNBUSDT"]  # Default from constants

    @patch("services.config_manager.MongoDBAdapter")
    def test_get_symbols_from_config(self, mock_adapter_class):
        """Test getting symbols from MongoDB config."""
        mock_adapter = Mock()
        mock_adapter._connected = True
        mock_adapter.database = Mock()
        mock_collection = Mock()
        mock_collection.find_one = Mock(
            return_value={"key": "symbols", "value": ["BTCUSDT", "ETHUSDT"]}
        )
        mock_adapter.database.__getitem__ = Mock(return_value=mock_collection)
        mock_adapter_class.return_value = mock_adapter

        manager = ConfigManager()
        manager.adapter = mock_adapter
        manager.adapter._connected = True

        symbols = manager.get_symbols()
        assert symbols == ["BTCUSDT", "ETHUSDT"]

    @patch("services.config_manager.MongoDBAdapter")
    def test_set_symbols(self, mock_adapter_class):
        """Test setting symbols."""
        mock_adapter = Mock()
        mock_adapter._connected = True
        mock_adapter.database = Mock()
        mock_collection = Mock()
        mock_collection.update_one = Mock()
        mock_adapter.database.__getitem__ = Mock(return_value=mock_collection)
        mock_adapter_class.return_value = mock_adapter

        manager = ConfigManager()
        manager.adapter = mock_adapter
        manager.adapter._connected = True

        manager.set_symbols(["BTCUSDT", "ETHUSDT"], "test_user", "Test")
        mock_collection.update_one.assert_called_once()

    @patch("services.config_manager.MongoDBAdapter")
    def test_get_rate_limits_default(self, mock_adapter_class):
        """Test getting default rate limits."""
        mock_adapter = Mock()
        mock_adapter._connected = True
        mock_adapter.database = Mock()
        mock_collection = Mock()
        mock_collection.find_one = Mock(return_value=None)
        mock_adapter.database.__getitem__ = Mock(return_value=mock_collection)
        mock_adapter_class.return_value = mock_adapter

        manager = ConfigManager()
        manager.adapter = mock_adapter
        manager.adapter._connected = True

        limits = manager.get_rate_limits()
        assert "requests_per_minute" in limits
        assert "concurrent_requests" in limits

    @patch("services.config_manager.MongoDBAdapter")
    def test_set_rate_limits(self, mock_adapter_class):
        """Test setting rate limits."""
        mock_adapter = Mock()
        mock_adapter._connected = True
        mock_adapter.database = Mock()
        mock_collection = Mock()
        mock_collection.update_one = Mock()
        mock_adapter.database.__getitem__ = Mock(return_value=mock_collection)
        mock_adapter_class.return_value = mock_adapter

        manager = ConfigManager()
        manager.adapter = mock_adapter
        manager.adapter._connected = True

        manager.set_rate_limits(1000, 5, "test_user", "Test")
        mock_collection.update_one.assert_called_once()


class TestConfigManagerSingleton:
    """Test config manager singleton pattern."""

    def test_get_config_manager_returns_singleton(self):
        """Test that get_config_manager returns the same instance."""
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        assert manager1 is manager2

    def test_set_config_manager(self):
        """Test setting custom config manager."""
        original = get_config_manager()
        new_manager = ConfigManager()
        set_config_manager(new_manager)
        assert get_config_manager() is new_manager
        # Restore original
        set_config_manager(original)

