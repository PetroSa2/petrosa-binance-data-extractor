"""
Comprehensive unit tests for database adapters.

Tests cover the abstract base class, concrete implementations (MongoDB and MySQL),
error handling, connection management, and performance characteristics.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from db.base_adapter import BaseAdapter, DatabaseError
from db.mongodb_adapter import MongoDBAdapter
from db.mysql_adapter import MySQLAdapter
from models.base import BaseTimestampedModel, ExtractionMetadata


class SampleTestModel(BaseTimestampedModel):
    """Test model for adapter testing."""

    test_field: str


@pytest.mark.unit
class TestBaseAdapter:
    """Test cases for BaseAdapter abstract class."""

    def test_abstract_class_cannot_be_instantiated(self):
        """Test that BaseAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseAdapter("test_connection_string")

    def test_concrete_adapter_initialization(self):
        """Test initialization of a concrete adapter."""

        class ConcreteAdapter(BaseAdapter):
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

        adapter = ConcreteAdapter("test_connection")
        assert adapter.connection_string == "test_connection"
        assert adapter._connected is False

    def test_context_manager_protocol(self):
        """Test context manager protocol implementation."""

        class ConcreteAdapter(BaseAdapter):
            def connect(self):
                self._connected = True

            def disconnect(self):
                self._connected = False

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

        adapter = ConcreteAdapter("test_connection")

        with adapter:
            assert adapter._connected is True

        assert adapter._connected is False

    def test_is_connected_method(self):
        """Test is_connected method."""

        class ConcreteAdapter(BaseAdapter):
            def connect(self):
                self._connected = True

            def disconnect(self):
                self._connected = False

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

        adapter = ConcreteAdapter("test_connection")

        assert adapter.is_connected() is False
        adapter.connect()
        assert adapter.is_connected() is True
        adapter.disconnect()
        assert adapter.is_connected() is False

    def test_write_extraction_metadata(self):
        """Test write_extraction_metadata method."""

        class ConcreteAdapter(BaseAdapter):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.written_data = []

            def connect(self):
                pass

            def disconnect(self):
                pass

            def write(self, model_instances, collection):
                self.written_data.append((model_instances, collection))
                return len(model_instances)

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

        adapter = ConcreteAdapter("test_connection")
        metadata = ExtractionMetadata(
            period="15m",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
        )

        adapter.write_extraction_metadata(metadata)

        assert len(adapter.written_data) == 1
        assert adapter.written_data[0][1] == "extraction_metadata"
        assert adapter.written_data[0][0][0] == metadata


@pytest.mark.unit
class TestMongoDBAdapter:
    """Test cases for MongoDBAdapter."""

    @patch("db.mongodb_adapter.MongoClient")
    def test_initialization(self, mock_mongo_client):
        """Test MongoDB adapter initialization."""
        adapter = MongoDBAdapter("mongodb://localhost:27017/test")

        assert adapter.connection_string == "mongodb://localhost:27017/test"
        assert adapter.database_name == "test"
        assert adapter.client is None
        assert adapter.database is None

    @patch("db.mongodb_adapter.MongoClient")
    def test_connection_success(self, mock_mongo_client):
        """Test successful MongoDB connection."""
        mock_client = Mock()
        mock_database = Mock()
        mock_mongo_client.return_value = mock_client
        # Configure mock to support database access via client[database_name]
        mock_client.__getitem__ = Mock(return_value=mock_database)

        adapter = MongoDBAdapter("mongodb://localhost:27017/test")
        adapter.connect()

        assert adapter._connected is True
        assert adapter.client == mock_client
        assert adapter.database == mock_database
        # Check that MongoClient was called with connection string
        assert mock_mongo_client.called

    @patch("db.mongodb_adapter.MongoClient")
    def test_connection_failure(self, mock_mongo_client):
        """Test MongoDB connection failure."""
        mock_mongo_client.side_effect = Exception("Connection failed")

        adapter = MongoDBAdapter("mongodb://localhost:27017/test")

        with pytest.raises(Exception, match="Connection failed"):
            adapter.connect()

        assert adapter._connected is False

    @pytest.mark.skip(reason="TODO: Fix mocking for new adapter implementation")
    @patch("db.mongodb_adapter.MongoClient")
    def test_disconnect(self, mock_mongo_client):
        """Test MongoDB disconnection."""
        mock_client = Mock()
        mock_mongo_client.return_value = mock_client

        adapter = MongoDBAdapter("mongodb://localhost:27017/test")
        adapter.connect()
        adapter.disconnect()

        mock_client.close.assert_called_once()
        assert adapter._connected is False

    @pytest.mark.skip(reason="TODO: Fix mocking for new adapter implementation")
    @patch("db.mongodb_adapter.MongoClient")
    def test_write_single_record(self, mock_mongo_client):
        """Test writing a single record to MongoDB."""
        mock_client = Mock()
        mock_database = MagicMock()
        mock_collection = Mock()
        mock_result = Mock()
        mock_result.inserted_ids = [1, 2, 3]

        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__ = Mock(return_value=mock_database)
        mock_database.__getitem__ = Mock(return_value=mock_collection)
        mock_collection.insert_many.return_value = mock_result

        adapter = MongoDBAdapter("mongodb://localhost:27017/test")
        adapter.connect()

        test_models = [
            SampleTestModel(timestamp=datetime.now(), test_field="test1"),
            SampleTestModel(timestamp=datetime.now(), test_field="test2"),
            SampleTestModel(timestamp=datetime.now(), test_field="test3"),
        ]

        result = adapter.write(test_models, "test_collection")

        assert result == 3
        mock_collection.insert_many.assert_called_once()
        # Verify the data format
        call_args = mock_collection.insert_many.call_args[0][0]
        assert len(call_args) == 3
        assert all(isinstance(doc, dict) for doc in call_args)

    @pytest.mark.skip(reason="TODO: Fix mocking for new adapter implementation")
    @patch("db.mongodb_adapter.MongoClient")
    def test_write_batch(self, mock_mongo_client):
        """Test batch writing to MongoDB."""
        mock_client = Mock()
        mock_database = MagicMock()
        mock_collection = Mock()
        mock_result = Mock()
        mock_result.inserted_ids = list(range(10))

        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__ = Mock(return_value=mock_database)
        mock_database.__getitem__ = Mock(return_value=mock_collection)
        mock_collection.insert_many.return_value = mock_result

        adapter = MongoDBAdapter("mongodb://localhost:27017/test")
        adapter.connect()

        test_models = [
            SampleTestModel(timestamp=datetime.now(), test_field=f"test{i}")
            for i in range(10)
        ]

        result = adapter.write_batch(test_models, "test_collection", batch_size=3)

        assert result == 10
        # Should be called in batches of 3: [3, 3, 3, 1]
        assert mock_collection.insert_many.call_count == 4

    @pytest.mark.skip(reason="TODO: Fix mocking for new adapter implementation")
    @patch("db.mongodb_adapter.MongoClient")
    def test_query_range(self, mock_mongo_client):
        """Test querying records within a time range."""
        mock_client = Mock()
        mock_database = MagicMock()
        mock_collection = Mock()
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(
            return_value=iter(
                [
                    {"timestamp": datetime.now(), "symbol": "BTCUSDT"},
                    {"timestamp": datetime.now(), "symbol": "ETHUSDT"},
                ]
            )
        )

        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__ = Mock(return_value=mock_database)
        mock_database.__getitem__ = Mock(return_value=mock_collection)
        mock_collection.find.return_value = mock_cursor

        adapter = MongoDBAdapter("mongodb://localhost:27017/test")
        adapter.connect()

        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now()

        result = adapter.query_range("test_collection", start_time, end_time, "BTCUSDT")

        assert len(result) == 2
        mock_collection.find.assert_called_once()
        # Verify query parameters
        call_args = mock_collection.find.call_args[0][0]
        assert "timestamp" in call_args
        assert "symbol" in call_args

    @patch("db.mongodb_adapter.MongoClient")
    def test_query_latest(self, mock_mongo_client):
        """Test querying latest records."""
        mock_client = Mock()
        mock_database = MagicMock()
        mock_collection = Mock()
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(
            return_value=iter([{"timestamp": datetime.now(), "symbol": "BTCUSDT"}])
        )

        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__ = Mock(return_value=mock_database)
        mock_database.__getitem__ = Mock(return_value=mock_collection)
        mock_collection.find.return_value.sort.return_value.limit.return_value = (
            mock_cursor
        )

        adapter = MongoDBAdapter("mongodb://localhost:27017/test")
        adapter.connect()

        result = adapter.query_latest("test_collection", "BTCUSDT", 5)

        assert len(result) == 1
        mock_collection.find.assert_called_once()

    @patch("db.mongodb_adapter.MongoClient")
    def test_get_record_count(self, mock_mongo_client):
        """Test getting record count."""
        mock_client = Mock()
        mock_database = MagicMock()
        mock_collection = Mock()
        mock_collection.count_documents.return_value = 100

        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__ = Mock(return_value=mock_database)
        mock_database.__getitem__ = Mock(return_value=mock_collection)

        adapter = MongoDBAdapter("mongodb://localhost:27017/test")
        adapter.connect()

        result = adapter.get_record_count("test_collection")

        assert result == 100
        mock_collection.count_documents.assert_called_once()

    @patch("db.mongodb_adapter.MongoClient")
    def test_ensure_indexes(self, mock_mongo_client):
        """Test index creation."""
        mock_client = Mock()
        mock_database = MagicMock()
        mock_collection = Mock()

        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__ = Mock(return_value=mock_database)
        mock_database.__getitem__ = Mock(return_value=mock_collection)

        adapter = MongoDBAdapter("mongodb://localhost:27017/test")
        adapter.connect()

        adapter.ensure_indexes("test_collection")

        # Should create compound index on timestamp and symbol
        mock_collection.create_index.assert_called()

    @patch("db.mongodb_adapter.MongoClient")
    def test_delete_range(self, mock_mongo_client):
        """Test deleting records within a time range."""
        mock_client = Mock()
        mock_database = MagicMock()
        mock_collection = Mock()
        mock_result = Mock()
        mock_result.deleted_count = 50

        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__ = Mock(return_value=mock_database)
        mock_database.__getitem__ = Mock(return_value=mock_collection)
        mock_collection.delete_many.return_value = mock_result

        adapter = MongoDBAdapter("mongodb://localhost:27017/test")
        adapter.connect()

        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now()

        result = adapter.delete_range(
            "test_collection", start_time, end_time, "BTCUSDT"
        )

        assert result == 50
        mock_collection.delete_many.assert_called_once()

    @pytest.mark.skip(reason="TODO: Fix mocking for new adapter implementation")
    @patch("db.mongodb_adapter.MongoClient")
    def test_find_gaps(self, mock_mongo_client):
        """Test finding gaps in data."""
        mock_client = Mock()
        mock_database = MagicMock()
        mock_collection = Mock()

        # Mock aggregation pipeline result
        mock_cursor = [
            {"_id": datetime(2023, 1, 1, 0, 0)},
            {"_id": datetime(2023, 1, 1, 0, 15)},
            # Gap here: missing 0:30
            {"_id": datetime(2023, 1, 1, 0, 45)},
        ]

        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__ = Mock(return_value=mock_database)
        mock_database.__getitem__ = Mock(return_value=mock_collection)
        mock_collection.aggregate.return_value = mock_cursor

        adapter = MongoDBAdapter("mongodb://localhost:27017/test")
        adapter.connect()

        start_time = datetime(2023, 1, 1, 0, 0)
        end_time = datetime(2023, 1, 1, 1, 0)

        gaps = adapter.find_gaps("test_collection", start_time, end_time, 15, "BTCUSDT")

        assert len(gaps) == 1
        assert gaps[0][0] == datetime(2023, 1, 1, 0, 30)
        assert gaps[0][1] == datetime(2023, 1, 1, 0, 45)


@pytest.mark.unit
class TestMySQLAdapter:
    """Test cases for MySQLAdapter."""

    @pytest.mark.skip(reason="TODO: Fix mocking for SQLAlchemy-based implementation")
    @patch("db.mysql_adapter.create_engine")
    def test_initialization(self, mock_create_engine):
        """Test MySQL adapter initialization."""
        adapter = MySQLAdapter("mysql://user:pass@localhost:3306/test")

        assert adapter.connection_string == "mysql://user:pass@localhost:3306/test"
        assert adapter.database_name == "test"
        assert adapter.engine is None

    @pytest.mark.skip(reason="TODO: Fix mocking for SQLAlchemy-based implementation")
    @patch("db.mysql_adapter.create_engine")
    def test_connection_success(self, mock_create_engine):
        """Test successful MySQL connection."""
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        adapter = MySQLAdapter("mysql://user:pass@localhost:3306/test")
        adapter.connect()

        assert adapter._connected is True
        assert adapter.engine == mock_engine
        mock_create_engine.assert_called_once()

    @patch("db.mysql_adapter.create_engine")
    def test_connection_failure(self, mock_create_engine):
        """Test MySQL connection failure."""
        mock_create_engine.side_effect = Exception("Connection failed")

        adapter = MySQLAdapter("mysql://user:pass@localhost:3306/test")

        with pytest.raises(Exception, match="Connection failed"):
            adapter.connect()

        assert adapter._connected is False

    @pytest.mark.skip(reason="TODO: Fix mocking for SQLAlchemy-based implementation")
    @patch("db.mysql_adapter.create_engine")
    def test_write_batch(self, mock_create_engine):
        """Test batch writing to MySQL."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_cursor.rowcount = 10

        mock_create_engine.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor

        adapter = MySQLAdapter("mysql://user:pass@localhost:3306/test")
        adapter.connect()

        test_models = [
            SampleTestModel(timestamp=datetime.now(), test_field=f"test{i}")
            for i in range(10)
        ]

        result = adapter.write_batch(test_models, "test_table")

        assert result == 10
        mock_cursor.executemany.assert_called()
        mock_connection.commit.assert_called()

    @pytest.mark.skip(reason="TODO: Fix mocking for SQLAlchemy-based implementation")
    @patch("db.mysql_adapter.create_engine")
    def test_query_range(self, mock_create_engine):
        """Test querying records within a time range."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_cursor.fetchall.return_value = [
            {"timestamp": datetime.now(), "symbol": "BTCUSDT"},
            {"timestamp": datetime.now(), "symbol": "ETHUSDT"},
        ]

        mock_create_engine.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor

        adapter = MySQLAdapter("mysql://user:pass@localhost:3306/test")
        adapter.connect()

        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now()

        result = adapter.query_range("test_table", start_time, end_time, "BTCUSDT")

        assert len(result) == 2
        mock_cursor.execute.assert_called()

    @pytest.mark.skip(reason="TODO: Fix mocking for SQLAlchemy-based implementation")
    @patch("db.mysql_adapter.create_engine")
    def test_get_record_count(self, mock_create_engine):
        """Test getting record count."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_cursor.fetchone.return_value = {"count": 100}

        mock_create_engine.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor

        adapter = MySQLAdapter("mysql://user:pass@localhost:3306/test")
        adapter.connect()

        result = adapter.get_record_count("test_table")

        assert result == 100
        mock_cursor.execute.assert_called()

    @pytest.mark.skip(reason="TODO: Fix mocking for SQLAlchemy-based implementation")
    @patch("db.mysql_adapter.create_engine")
    def test_transaction_rollback_on_error(self, mock_create_engine):
        """Test transaction rollback on error."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_cursor.executemany.side_effect = Exception("SQL Error")

        mock_create_engine.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor

        adapter = MySQLAdapter("mysql://user:pass@localhost:3306/test")
        adapter.connect()

        test_models = [SampleTestModel(timestamp=datetime.now(), test_field="test")]

        with pytest.raises(Exception, match="SQL Error"):
            adapter.write_batch(test_models, "test_table")

        mock_connection.rollback.assert_called()

    @pytest.mark.skip(reason="TODO: Fix mocking for SQLAlchemy-based implementation")
    @patch("db.mysql_adapter.create_engine")
    def test_ensure_indexes(self, mock_create_engine):
        """Test index creation for MySQL."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_create_engine.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor

        adapter = MySQLAdapter("mysql://user:pass@localhost:3306/test")
        adapter.connect()

        adapter.ensure_indexes("test_table")

        # Should create indexes on timestamp and symbol
        assert mock_cursor.execute.call_count >= 2


@pytest.mark.unit
class TestAdapterErrorHandling:
    """Test error handling across all adapters."""

    @pytest.mark.skip(reason="TODO: Fix mocking for new adapter implementation")
    @patch("db.mongodb_adapter.MongoClient")
    def test_mongodb_write_error_handling(self, mock_mongo_client):
        """Test MongoDB write error handling."""
        mock_client = Mock()
        mock_database = MagicMock()
        mock_collection = Mock()
        mock_collection.insert_many.side_effect = Exception("Write failed")

        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__ = Mock(return_value=mock_database)
        mock_database.__getitem__ = Mock(return_value=mock_collection)

        adapter = MongoDBAdapter("mongodb://localhost:27017/test")
        adapter.connect()

        test_models = [SampleTestModel(timestamp=datetime.now(), test_field="test")]

        with pytest.raises(Exception, match="Write failed"):
            adapter.write(test_models, "test_collection")

    @patch("db.mysql_adapter.create_engine")
    def test_mysql_connection_error_handling(self, mock_create_engine):
        """Test MySQL connection error handling."""
        mock_create_engine.side_effect = Exception("MySQL connection failed")

        adapter = MySQLAdapter("mysql://user:pass@localhost:3306/test")

        with pytest.raises(Exception, match="MySQL connection failed"):
            adapter.connect()

    def test_adapter_not_connected_error(self):
        """Test operations on unconnected adapter."""

        class TestAdapter(BaseAdapter):
            def connect(self):
                self._connected = True

            def disconnect(self):
                self._connected = False

            def write(self, model_instances, collection):
                if not self._connected:
                    raise DatabaseError("Not connected")
                return len(model_instances)

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

        adapter = TestAdapter("test_connection")
        test_models = [SampleTestModel(timestamp=datetime.now(), test_field="test")]

        with pytest.raises(DatabaseError, match="Not connected"):
            adapter.write(test_models, "test_collection")


@pytest.mark.unit
class TestAdapterPerformance:
    """Performance-related tests for adapters."""

    @pytest.mark.skip(reason="TODO: Fix mocking for new adapter implementation")
    @patch("db.mongodb_adapter.MongoClient")
    def test_large_batch_processing(self, mock_mongo_client):
        """Test processing of large batches."""
        mock_client = Mock()
        mock_database = MagicMock()
        mock_collection = Mock()
        mock_result = Mock()

        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__ = Mock(return_value=mock_database)
        mock_database.__getitem__ = Mock(return_value=mock_collection)

        adapter = MongoDBAdapter("mongodb://localhost:27017/test")
        adapter.connect()

        # Create large dataset
        large_dataset = [
            SampleTestModel(timestamp=datetime.now(), test_field=f"test{i}")
            for i in range(10000)
        ]

        # Mock successful batch inserts
        mock_result.inserted_ids = list(range(1000))  # Batch size
        mock_collection.insert_many.return_value = mock_result

        result = adapter.write_batch(large_dataset, "test_collection", batch_size=1000)

        assert result == 10000
        assert mock_collection.insert_many.call_count == 10  # 10 batches of 1000

    @pytest.mark.parametrize("batch_size", [100, 500, 1000, 2000])
    def test_batch_size_optimization(self, batch_size):
        """Test different batch sizes for optimization."""

        class TestAdapter(BaseAdapter):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.batch_calls = []

            def connect(self):
                pass

            def disconnect(self):
                pass

            def write(self, model_instances, collection):
                return len(model_instances)

            def write_batch(self, model_instances, collection, batch_size=1000):
                for i in range(0, len(model_instances), batch_size):
                    batch = model_instances[i : i + batch_size]
                    self.batch_calls.append(len(batch))
                return len(model_instances)

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

        adapter = TestAdapter("test_connection")
        test_models = [
            SampleTestModel(timestamp=datetime.now(), test_field=f"test{i}")
            for i in range(2500)  # Test with 2500 records
        ]

        result = adapter.write_batch(
            test_models, "test_collection", batch_size=batch_size
        )

        assert result == 2500
        expected_batches = (2500 + batch_size - 1) // batch_size  # Ceiling division
        assert len(adapter.batch_calls) == expected_batches
