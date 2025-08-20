#!/usr/bin/env python3
"""
Tests for database adapters.
"""

import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from db.base_adapter import BaseAdapter, DatabaseError  # noqa: E402
from db.mongodb_adapter import MongoDBAdapter  # noqa: E402
from db.mysql_adapter import MySQLAdapter  # noqa: E402
from models.kline import KlineModel  # noqa: E402


class TestBaseAdapter:
    """Test BaseAdapter interface."""

    def test_base_adapter_is_abstract(self):
        """Test that BaseAdapter cannot be instantiated."""
        with pytest.raises(TypeError):
            # Attempting to instantiate BaseAdapter directly should raise TypeError
            class DummyAdapter(BaseAdapter):
                def connect(self):
                    pass

                def disconnect(self):
                    pass

                def write(self, model_instances, collection):
                    pass

                def write_batch(self, model_instances, collection, batch_size=1000):
                    pass

                def query_range(self, collection, start, end, symbol=None):
                    pass

                def query_latest(self, collection, symbol=None, limit=1):
                    pass

                def find_gaps(
                    self, collection, start, end, interval_minutes, symbol=None
                ):
                    pass

                def get_record_count(
                    self, collection, start=None, end=None, symbol=None
                ):
                    pass

                def ensure_indexes(self, collection):
                    pass

                def delete_range(self, collection, start, end, symbol=None):
                    pass

            BaseAdapter("test://connection")

    def test_context_manager_interface(self):
        """Test context manager methods exist."""

        # Create a concrete implementation for testing
        class TestAdapter(BaseAdapter):
            def connect(self):
                pass

            def disconnect(self):
                pass

            def write(self, model_instances, collection):
                return 0

            def write_batch(self, model_instances, collection, batch_size=1000):
                return 0

            def query_range(self, collection, start, end, symbol=None):
                return []

            def query_latest(self, collection, symbol=None, limit=1):
                return []

            def find_gaps(self, collection, start, end, interval_minutes, symbol=None):
                return []

            def get_record_count(self, collection, start=None, end=None, symbol=None):
                return 0

            def ensure_indexes(self, collection):
                pass

            def delete_range(self, collection, start, end, symbol=None):
                return 0

        adapter = TestAdapter("test://connection")

        # Test context manager methods exist
        assert hasattr(adapter, "__enter__")
        assert hasattr(adapter, "__exit__")


@pytest.mark.skipif(
    not hasattr(MongoDBAdapter, "__init__"), reason="MongoDB dependencies not available"
)
class TestMongoDBAdapter:
    """Test MongoDBAdapter functionality."""

    @patch("db.mongodb_adapter.MongoClient")
    def test_mongodb_adapter_connection(self, mock_mongo_client):
        """Test MongoDB connection."""
        mock_client = MagicMock()
        mock_mongo_client.return_value = mock_client
        mock_client.admin.command.return_value = {"ok": 1}

        adapter = MongoDBAdapter("mongodb://test:27017/test")
        adapter.connect()

        assert adapter._connected is True
        mock_mongo_client.assert_called_once()
        mock_client.admin.command.assert_called_with("ping")

    @patch("db.mongodb_adapter.MongoClient")
    def test_mongodb_adapter_write(self, mock_mongo_client):
        """Test MongoDB write operation."""
        # Setup mocks
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_collection = MagicMock()
        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__.return_value = mock_database
        mock_database.__getitem__.return_value = mock_collection

        # Mock successful bulk write
        mock_result = MagicMock()
        mock_result.inserted_count = 2
        mock_collection.bulk_write.return_value = mock_result

        # Create test data
        now = datetime.now(timezone.utc)
        klines = [
            KlineModel(
                symbol="BTCUSDT",
                timestamp=now,
                open_time=now,
                close_time=now,
                interval="15m",
                open_price=Decimal("50000"),
                high_price=Decimal("50000"),
                low_price=Decimal("50000"),
                close_price=Decimal("50000"),
                volume=Decimal("0"),
                quote_asset_volume=Decimal("0"),
                number_of_trades=0,
                taker_buy_base_asset_volume=Decimal("0"),
                taker_buy_quote_asset_volume=Decimal("0"),
            ),
            KlineModel(
                symbol="ETHUSDT",
                timestamp=now,
                open_time=now,
                close_time=now,
                interval="15m",
                open_price=Decimal("3000"),
                high_price=Decimal("3000"),
                low_price=Decimal("3000"),
                close_price=Decimal("3000"),
                volume=Decimal("0"),
                quote_asset_volume=Decimal("0"),
                number_of_trades=0,
                taker_buy_base_asset_volume=Decimal("0"),
                taker_buy_quote_asset_volume=Decimal("0"),
            ),
        ]

        # Test write
        adapter = MongoDBAdapter("mongodb://test:27017/test")
        adapter._connected = True
        adapter.database = mock_database

        result = adapter.write(klines, "klines_m15")

        assert result == 2
        mock_collection.bulk_write.assert_called_once()

    @patch("db.mongodb_adapter.MongoClient")
    def test_mongodb_adapter_query_range(self, mock_mongo_client):
        """Test MongoDB range query."""
        # Setup mocks
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_collection = MagicMock()
        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__.return_value = mock_database
        mock_database.__getitem__.return_value = mock_collection

        # Mock query result
        mock_cursor = MagicMock()
        mock_cursor.__iter__.return_value = iter(
            [
                {"symbol": "BTCUSDT", "timestamp": datetime.now(timezone.utc)},
                {"symbol": "BTCUSDT", "timestamp": datetime.now(timezone.utc)},
            ]
        )
        mock_collection.find.return_value = mock_cursor
        mock_cursor.sort.return_value = mock_cursor

        # Test query
        adapter = MongoDBAdapter("mongodb://test:27017/test")
        adapter._connected = True
        adapter.database = mock_database

        start = datetime.now(timezone.utc)
        end = datetime.now(timezone.utc)

        result = adapter.query_range("klines_m15", start, end, "BTCUSDT")

        assert isinstance(result, list)
        mock_collection.find.assert_called_once()

    @patch("db.mongodb_adapter.MongoClient")
    def test_mongodb_adapter_disconnect(self, mock_mongo_client):
        mock_client = MagicMock()
        mock_mongo_client.return_value = mock_client
        adapter = MongoDBAdapter("mongodb://test:27017/test")
        adapter.client = mock_client
        adapter._connected = True
        adapter.disconnect()
        mock_client.close.assert_called_once()
        assert adapter._connected is False

    @patch("db.mongodb_adapter.MongoClient")
    def test_mongodb_adapter_write_batch(self, mock_mongo_client):
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_collection = MagicMock()
        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__.return_value = mock_database
        mock_database.__getitem__.return_value = mock_collection
        # Mock different results for different calls
        mock_result1 = MagicMock()
        mock_result1.inserted_count = 2
        mock_result2 = MagicMock()
        mock_result2.inserted_count = 1
        mock_collection.bulk_write.side_effect = [mock_result1, mock_result2]
        now = datetime.now(timezone.utc)
        klines = [
            KlineModel(
                symbol="BTCUSDT",
                timestamp=now,
                open_time=now,
                close_time=now,
                interval="15m",
                open_price=Decimal("50000"),
                high_price=Decimal("50000"),
                low_price=Decimal("50000"),
                close_price=Decimal("50000"),
                volume=Decimal("0"),
                quote_asset_volume=Decimal("0"),
                number_of_trades=0,
                taker_buy_base_asset_volume=Decimal("0"),
                taker_buy_quote_asset_volume=Decimal("0"),
            )
            for _ in range(3)
        ]
        adapter = MongoDBAdapter("mongodb://test:27017/test")
        adapter._connected = True
        adapter.database = mock_database
        result = adapter.write_batch(klines, "klines_m15", batch_size=2)
        assert result == 3  # 2 + 1 = 3 total inserted
        assert mock_collection.bulk_write.call_count >= 1

    @patch("db.mongodb_adapter.MongoClient")
    def test_mongodb_adapter_query_latest(self, mock_mongo_client):
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_collection = MagicMock()
        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__.return_value = mock_database
        mock_database.__getitem__.return_value = mock_collection
        mock_cursor = MagicMock()
        mock_cursor.__iter__.return_value = iter(
            [{"symbol": "BTCUSDT", "timestamp": datetime.now(timezone.utc)}]
        )
        mock_collection.find.return_value = mock_cursor
        mock_cursor.sort.return_value = mock_cursor
        adapter = MongoDBAdapter("mongodb://test:27017/test")
        adapter._connected = True
        adapter.database = mock_database
        result = adapter.query_latest("klines_m15", symbol="BTCUSDT", limit=1)
        assert isinstance(result, list)
        mock_collection.find.assert_called_once()

    @patch("db.mongodb_adapter.MongoClient")
    def test_mongodb_adapter_find_gaps(self, mock_mongo_client):
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_collection = MagicMock()
        mock_cursor = MagicMock()
        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__.return_value = mock_database
        mock_database.__getitem__.return_value = mock_collection

        # Mock the cursor chain: find().sort()
        mock_collection.find.return_value = mock_cursor
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.__iter__.return_value = []  # Empty result

        adapter = MongoDBAdapter("mongodb://test:27017/test")
        adapter._connected = True
        adapter.database = mock_database
        start = datetime.now(timezone.utc)
        end = datetime.now(timezone.utc)
        result = adapter.find_gaps(
            "klines_m15", start, end, interval_minutes=15, symbol="BTCUSDT"
        )
        assert isinstance(result, list)
        mock_collection.find.assert_called()

    @patch("db.mongodb_adapter.MongoClient")
    def test_mongodb_adapter_get_record_count(self, mock_mongo_client):
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_collection = MagicMock()
        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__.return_value = mock_database
        mock_database.__getitem__.return_value = mock_collection
        mock_collection.count_documents.return_value = 42
        adapter = MongoDBAdapter("mongodb://test:27017/test")
        adapter._connected = True
        adapter.database = mock_database
        start = datetime.now(timezone.utc)
        end = datetime.now(timezone.utc)
        result = adapter.get_record_count(
            "klines_m15", start=start, end=end, symbol="BTCUSDT"
        )
        assert result == 42
        mock_collection.count_documents.assert_called()

    @patch("db.mongodb_adapter.MongoClient")
    def test_mongodb_adapter_ensure_indexes(self, mock_mongo_client):
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_collection = MagicMock()
        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__.return_value = mock_database
        mock_database.__getitem__.return_value = mock_collection
        adapter = MongoDBAdapter("mongodb://test:27017/test")
        adapter._connected = True
        adapter.database = mock_database
        adapter.ensure_indexes("klines_m15")
        mock_collection.create_index.assert_called()

    @patch("db.mongodb_adapter.MongoClient")
    def test_mongodb_adapter_delete_range(self, mock_mongo_client):
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_collection = MagicMock()
        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__.return_value = mock_database
        mock_database.__getitem__.return_value = mock_collection
        mock_collection.delete_many.return_value = MagicMock(deleted_count=2)
        adapter = MongoDBAdapter("mongodb://test:27017/test")
        adapter._connected = True
        adapter.database = mock_database
        start = datetime.now(timezone.utc)
        end = datetime.now(timezone.utc)
        result = adapter.delete_range("klines_m15", start, end, symbol="BTCUSDT")
        assert result == 2
        mock_collection.delete_many.assert_called()

    @patch("db.mongodb_adapter.MongoClient")
    def test_mongodb_adapter_connect_error(self, mock_mongo_client):
        mock_mongo_client.side_effect = Exception("connection error")
        adapter = MongoDBAdapter("mongodb://test:27017/test")
        with pytest.raises(Exception):
            adapter.connect()

    @patch("db.mongodb_adapter.MongoClient")
    def test_mongodb_adapter_write_error(self, mock_mongo_client):
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_collection = MagicMock()
        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__.return_value = mock_database
        mock_database.__getitem__.return_value = mock_collection
        mock_collection.bulk_write.side_effect = Exception("write error")
        now = datetime.now(timezone.utc)
        klines = [
            KlineModel(
                symbol="BTCUSDT",
                timestamp=now,
                open_time=now,
                close_time=now,
                interval="15m",
                open_price=Decimal("50000"),
                high_price=Decimal("50000"),
                low_price=Decimal("50000"),
                close_price=Decimal("50000"),
                volume=Decimal("0"),
                quote_asset_volume=Decimal("0"),
                number_of_trades=0,
                taker_buy_base_asset_volume=Decimal("0"),
                taker_buy_quote_asset_volume=Decimal("0"),
            )
        ]
        adapter = MongoDBAdapter("mongodb://test:27017/test")
        adapter._connected = True
        adapter.database = mock_database
        with pytest.raises(Exception):
            adapter.write(klines, "klines_m15")


@pytest.mark.skipif(
    not hasattr(MySQLAdapter, "__init__"), reason="MySQL dependencies not available"
)
class TestMySQLAdapter:
    """Test MySQLAdapter functionality."""

    @patch("db.mysql_adapter.create_engine")
    def test_mysql_adapter_connection(self, mock_create_engine):
        """Test MySQL connection."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        mock_connection = MagicMock()
        mock_context_manager = MagicMock()
        mock_context_manager.__enter__.return_value = mock_connection
        mock_context_manager.__exit__.return_value = None
        mock_engine.connect.return_value = mock_context_manager

        adapter = MySQLAdapter("mysql://test:3306/test")
        adapter.connect()

        assert adapter._connected is True
        mock_create_engine.assert_called_once()

    @patch("db.mysql_adapter.create_engine")
    def test_mysql_adapter_write(self, mock_create_engine):
        """Test MySQL write operation."""
        # Setup mocks
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        mock_connection = MagicMock()
        mock_transaction = MagicMock()
        mock_context_manager = MagicMock()
        mock_context_manager.__enter__.return_value = mock_connection
        mock_context_manager.__exit__.return_value = None
        mock_engine.connect.return_value = mock_context_manager
        mock_connection.begin.return_value = mock_transaction

        # Mock successful insert
        mock_result = Mock()
        mock_result.rowcount = 1  # Should match the number of klines being inserted
        mock_connection.execute.return_value = mock_result

        # Create test data
        now = datetime.now(timezone.utc)
        klines = [
            KlineModel(
                symbol="BTCUSDT",
                timestamp=now,
                open_time=now,
                close_time=now,
                interval="15m",
                open_price=Decimal("50000"),
                high_price=Decimal("50000"),
                low_price=Decimal("50000"),
                close_price=Decimal("50000"),
                volume=Decimal("0"),
                quote_asset_volume=Decimal("0"),
                number_of_trades=0,
                taker_buy_base_asset_volume=Decimal("0"),
                taker_buy_quote_asset_volume=Decimal("0"),
            )
        ]

        # Test write
        adapter = MySQLAdapter("mysql://test:3306/test")
        adapter._connected = True
        adapter.engine = mock_engine

        # Mock table creation
        with patch.object(adapter, "_get_table") as mock_get_table:
            mock_table = Mock()
            mock_get_table.return_value = mock_table
            mock_insert = Mock()
            mock_table.insert.return_value = mock_insert
            mock_insert.prefix_with.return_value = mock_insert

            result = adapter.write(klines, "klines_m15")

            assert result == 1  # Only one kline in test data
            mock_connection.execute.assert_called()


class TestDatabaseErrors:
    """Test database error handling."""

    def test_database_error_creation(self):
        """Test DatabaseError creation."""
        error = DatabaseError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_database_error_inheritance(self):
        """Test that DatabaseError inherits from Exception."""
        error = DatabaseError("Test error")
        assert isinstance(error, Exception)


class MockAdapter(BaseAdapter):
    """Mock adapter for testing base functionality."""

    def __init__(self, connection_string, **kwargs):
        super().__init__(connection_string, **kwargs)
        self.operations = []  # Track operations for testing

    def connect(self):
        self._connected = True
        self.operations.append("connect")

    def disconnect(self):
        self._connected = False
        self.operations.append("disconnect")

    def write(self, model_instances, collection):
        self.operations.append(("write", len(model_instances), collection))
        return len(model_instances)

    def write_batch(self, model_instances, collection, batch_size=1000):
        self.operations.append(
            ("write_batch", len(model_instances), collection, batch_size)
        )
        return len(model_instances)

    def query_range(self, collection, start, end, symbol=None):
        self.operations.append(("query_range", collection, start, end, symbol))
        return []

    def query_latest(self, collection, symbol=None, limit=1):
        self.operations.append(("query_latest", collection, symbol, limit))
        return []

    def find_gaps(self, collection, start, end, interval_minutes, symbol=None):
        self.operations.append(
            ("find_gaps", collection, start, end, interval_minutes, symbol)
        )
        return []

    def get_record_count(self, collection, start=None, end=None, symbol=None):
        self.operations.append(("get_record_count", collection, start, end, symbol))
        return 0

    def ensure_indexes(self, collection):
        self.operations.append(("ensure_indexes", collection))

    def delete_range(self, collection, start, end, symbol=None):
        self.operations.append(("delete_range", collection, start, end, symbol))
        return 0


class TestMockAdapter:
    """Test the mock adapter for base functionality."""

    def test_mock_adapter_context_manager(self):
        """Test context manager functionality."""
        adapter = MockAdapter("test://connection")

        with adapter:
            assert adapter.is_connected()
            assert "connect" in adapter.operations

        assert not adapter.is_connected()
        assert "disconnect" in adapter.operations

    def test_mock_adapter_operations(self):
        """Test that operations are tracked."""
        adapter = MockAdapter("test://connection")
        adapter.connect()

        # Test write operation
        now = datetime.now(timezone.utc)
        klines = [
            KlineModel(
                symbol="BTCUSDT",
                timestamp=now,
                open_time=now,
                close_time=now,
                interval="15m",
                open_price=Decimal("50000"),
                high_price=Decimal("50000"),
                low_price=Decimal("50000"),
                close_price=Decimal("50000"),
                volume=Decimal("0"),
                quote_asset_volume=Decimal("0"),
                number_of_trades=0,
                taker_buy_base_asset_volume=Decimal("0"),
                taker_buy_quote_asset_volume=Decimal("0"),
            )
        ]

        result = adapter.write(klines, "test_collection")
        assert result == 1
        assert ("write", 1, "test_collection") in adapter.operations

        # Test batch write
        result = adapter.write_batch(klines, "test_collection", 500)
        assert result == 1
        assert ("write_batch", 1, "test_collection", 500) in adapter.operations
