"""
Unit tests for database adapters.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone
from decimal import Decimal

from db.base_adapter import BaseAdapter, DatabaseError
from db.mongodb_adapter import MongoDBAdapter
from db.mysql_adapter import MySQLAdapter
from models.kline import KlineModel


class TestBaseAdapter:
    """Test BaseAdapter interface."""

    def test_base_adapter_is_abstract(self):
        """Test that BaseAdapter cannot be instantiated."""
        with pytest.raises(TypeError):
            # Attempting to instantiate BaseAdapter directly should raise TypeError
            class DummyAdapter(BaseAdapter):
                def connect(self): pass
                def disconnect(self): pass
                def write(self, model_instances, collection): pass
                def write_batch(self, model_instances, collection, batch_size=1000): pass
                def query_range(self, collection, start, end, symbol=None): pass
                def query_latest(self, collection, symbol=None, limit=1): pass
                def find_gaps(self, collection, start, end, interval_minutes, symbol=None): pass
                def get_record_count(self, collection, start=None, end=None, symbol=None): pass
                def ensure_indexes(self, collection): pass
                def delete_range(self, collection, start, end, symbol=None): pass
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

        # Mock successful insert
        mock_result = MagicMock()
        mock_result.inserted_ids = ["id1", "id2"]
        mock_collection.insert_many.return_value = mock_result

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
        mock_collection.insert_many.assert_called_once()

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
