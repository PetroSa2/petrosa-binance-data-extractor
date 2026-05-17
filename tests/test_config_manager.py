"""
Tests for configuration manager service.
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add project root to path (must be before imports)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import constants  # noqa: E402
from services.config_manager import (  # noqa: E402
    ConfigManager,
    get_config_manager,
    set_config_manager,
)


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
        assert symbols == constants.DEFAULT_SYMBOLS  # Default from constants

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


class TestConfigManagerLifecycle:
    """Exercise connect/disconnect + error paths that the original suite skips."""

    @patch("services.config_manager.MongoDBAdapter")
    def test_connect_creates_adapter_only_once(self, mock_adapter_class):
        mock_adapter = Mock()
        mock_adapter._connected = True
        mock_adapter_class.return_value = mock_adapter

        manager = ConfigManager(mongodb_uri="mongodb://test:27017")
        assert manager.adapter is None
        manager.connect()
        assert manager.adapter is mock_adapter
        # Second connect() must be a no-op once adapter exists.
        manager.connect()
        mock_adapter_class.assert_called_once_with(
            "mongodb://test:27017", database_name="petrosa_config"
        )
        mock_adapter.connect.assert_called_once()

    @patch("services.config_manager.MongoDBAdapter")
    def test_disconnect_clears_adapter(self, mock_adapter_class):
        mock_adapter = Mock()
        mock_adapter_class.return_value = mock_adapter

        manager = ConfigManager()
        manager.connect()
        assert manager.adapter is not None
        manager.disconnect()
        mock_adapter.disconnect.assert_called_once()
        assert manager.adapter is None

    def test_disconnect_when_never_connected_is_safe(self):
        # adapter is None — disconnect() must not raise.
        manager = ConfigManager()
        manager.disconnect()
        assert manager.adapter is None

    @patch("services.config_manager.MongoDBAdapter")
    def test_get_symbols_swallows_error_and_returns_default(self, mock_adapter_class):
        mock_adapter = Mock()
        mock_adapter._connected = True
        mock_adapter.database = Mock()
        mock_collection = Mock()
        mock_collection.find_one = Mock(side_effect=RuntimeError("mongo down"))
        mock_adapter.database.__getitem__ = Mock(return_value=mock_collection)
        mock_adapter_class.return_value = mock_adapter

        manager = ConfigManager()
        manager.adapter = mock_adapter
        # Error path must fall back to DEFAULT_SYMBOLS rather than raising.
        assert manager.get_symbols() == constants.DEFAULT_SYMBOLS

    @patch("services.config_manager.MongoDBAdapter")
    def test_set_symbols_propagates_errors(self, mock_adapter_class):
        mock_adapter = Mock()
        mock_adapter._connected = True
        mock_adapter.database = Mock()
        mock_collection = Mock()
        mock_collection.update_one = Mock(side_effect=RuntimeError("write failed"))
        mock_adapter.database.__getitem__ = Mock(return_value=mock_collection)
        mock_adapter_class.return_value = mock_adapter

        manager = ConfigManager()
        manager.adapter = mock_adapter
        with pytest.raises(RuntimeError, match="write failed") as exc_info:
            manager.set_symbols(["BTCUSDT"], "tester")
        assert "write failed" in str(exc_info.value)

    @patch("services.config_manager.MongoDBAdapter")
    def test_get_rate_limits_from_stored_config(self, mock_adapter_class):
        mock_adapter = Mock()
        mock_adapter._connected = True
        mock_adapter.database = Mock()
        mock_collection = Mock()
        mock_collection.find_one = Mock(
            return_value={
                "value": {"requests_per_minute": 600, "concurrent_requests": 8}
            }
        )
        mock_adapter.database.__getitem__ = Mock(return_value=mock_collection)
        mock_adapter_class.return_value = mock_adapter

        manager = ConfigManager()
        manager.adapter = mock_adapter
        limits = manager.get_rate_limits()
        assert limits == {"requests_per_minute": 600, "concurrent_requests": 8}

    @patch("services.config_manager.MongoDBAdapter")
    def test_get_rate_limits_swallows_error_and_returns_defaults(
        self, mock_adapter_class
    ):
        mock_adapter = Mock()
        mock_adapter._connected = True
        mock_adapter.database = Mock()
        mock_collection = Mock()
        mock_collection.find_one = Mock(side_effect=RuntimeError("mongo dead"))
        mock_adapter.database.__getitem__ = Mock(return_value=mock_collection)
        mock_adapter_class.return_value = mock_adapter

        manager = ConfigManager()
        manager.adapter = mock_adapter
        limits = manager.get_rate_limits()
        assert "requests_per_minute" in limits
        assert "concurrent_requests" in limits

    @patch("services.config_manager.MongoDBAdapter")
    def test_set_rate_limits_propagates_errors(self, mock_adapter_class):
        mock_adapter = Mock()
        mock_adapter._connected = True
        mock_adapter.database = Mock()
        mock_collection = Mock()
        mock_collection.update_one = Mock(side_effect=RuntimeError("write boom"))
        mock_adapter.database.__getitem__ = Mock(return_value=mock_collection)
        mock_adapter_class.return_value = mock_adapter

        manager = ConfigManager()
        manager.adapter = mock_adapter
        with pytest.raises(RuntimeError, match="write boom") as exc_info:
            manager.set_rate_limits(900, 4, "tester")
        assert "write boom" in str(exc_info.value)

    @patch("services.config_manager.MongoDBAdapter")
    def test_private_get_reconnects_when_adapter_disconnected(self, mock_adapter_class):
        # _get_config() should call connect() when the adapter isn't connected.
        mock_adapter = Mock()
        mock_adapter._connected = False
        mock_adapter.database = Mock()
        mock_collection = Mock()
        mock_collection.find_one = Mock(return_value=None)
        mock_adapter.database.__getitem__ = Mock(return_value=mock_collection)

        manager = ConfigManager()
        manager.adapter = mock_adapter

        # connect() will see existing adapter and skip reinstantiation.
        # The reconnect path itself fires _connected=False -> connect() called.
        manager.get_symbols()
        # connect was only called via _get_config when not connected — the adapter
        # already exists so MongoDBAdapter() should not have been called again.
        mock_adapter_class.assert_not_called()
