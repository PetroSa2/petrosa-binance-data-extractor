"""
MongoDB adapter implementation.

This module provides a MongoDB implementation of the BaseAdapter interface.
"""

import decimal
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from pydantic import BaseModel

try:
    from pymongo import ASCENDING, DESCENDING, MongoClient
    from pymongo.collection import Collection
    from pymongo.database import Database
    from pymongo.errors import BulkWriteError, ConnectionFailure, DuplicateKeyError
    from pymongo.operations import InsertOne

    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False

import constants
from db.base_adapter import BaseAdapter, DatabaseError
from utils.circuit_breaker import DatabaseCircuitBreaker
from utils.error_classifier import classify_database_error, should_retry_operation

logger = logging.getLogger(__name__)


class MongoDBAdapter(BaseAdapter):
    """
    MongoDB implementation of the BaseAdapter interface.

    Provides efficient storage and querying for time-series data using MongoDB.
    """

    @staticmethod
    def _convert_decimals(obj):
        """Recursively convert Decimal objects to float in dicts/lists."""
        if isinstance(obj, list):
            return [MongoDBAdapter._convert_decimals(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: MongoDBAdapter._convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, decimal.Decimal):
            return float(obj)
        else:
            return obj

    def __init__(self, connection_string: Optional[str] = None, **kwargs):
        """
        Initialize MongoDB adapter.

        Args:
            connection_string: MongoDB connection string
            **kwargs: Additional MongoDB client options
        """
        if not PYMONGO_AVAILABLE:
            raise ImportError(
                "pymongo is required for MongoDB adapter. Install with: pip install pymongo"
            )

        connection_string = connection_string or constants.MONGODB_URI
        super().__init__(connection_string, **kwargs)

        # MongoDB specific settings
        self.client: Optional[MongoClient] = None
        self.database: Optional[Database] = None

        # Extract database name from connection string or use default
        self.database_name = kwargs.get("database_name", "binance")
        if "/" in connection_string and connection_string.split("/")[-1]:
            # Extract database name from connection string
            db_name = connection_string.split("/")[-1].split("?")[0]
            if db_name:
                self.database_name = db_name

        # Circuit breaker for reliability
        self.circuit_breaker = DatabaseCircuitBreaker("mongodb")

        # Connection options (remove database_name from client options)
        client_kwargs = {k: v for k, v in kwargs.items() if k != "database_name"}
        self.client_options = {
            "serverSelectionTimeoutMS": 5000,  # Faster timeout
            "connectTimeoutMS": 5000,
            "maxPoolSize": kwargs.get("max_pool_size", 5),  # Conservative for free tier
            "minPoolSize": 1,
            "maxIdleTimeMS": 30000,  # Close idle connections quickly
            "waitQueueTimeoutMS": 10000,  # Timeout for connection acquisition
            "retryWrites": True,
            "retryReads": True,
            **client_kwargs,
        }

    def connect(self) -> None:
        """Establish connection to MongoDB."""
        try:
            self.client = MongoClient(self.connection_string, **self.client_options)
            # Test connection
            self.client.admin.command("ping")
            self.database = self.client[self.database_name]
            self._connected = True
            logger.info("Connected to MongoDB database: %s", self.database_name)
        except ConnectionFailure as e:
            raise DatabaseError(f"Failed to connect to MongoDB: {e}") from e

    def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self._connected = False
            logger.info("Disconnected from MongoDB")

    def write(self, model_instances: list[BaseModel], collection: str) -> int:
        """Write model instances to MongoDB collection with circuit breaker protection, using upserts for uniqueness on (symbol, timestamp)."""
        if not self._connected:
            raise DatabaseError("Not connected to database")

        if not model_instances:
            return 0

        def _write_operation():
            try:
                db = self._get_database()
                coll: Collection = db[collection]
                operations = []

                for instance in model_instances:
                    doc = instance.model_dump()
                    # For timeseries collections, use insertOne instead of upsert
                    doc = MongoDBAdapter._convert_decimals(doc)
                    operations.append(InsertOne(doc))

                if not operations:
                    return 0

                result = coll.bulk_write(operations, ordered=False)
                # Count inserted documents
                return result.inserted_count

            except BulkWriteError as e:
                # Count successful inserts
                inserted = e.details.get("nInserted", 0)
                logger.warning("Bulk write error: %s", e.details.get("writeErrors", []))
                return inserted
            except Exception as e:
                error_classification = classify_database_error(e)
                should_retry, retry_strategy = should_retry_operation(e)
                logger.warning(f"MongoDB write error ({error_classification}): {e}")
                if not should_retry:
                    raise DatabaseError(
                        f"Non-retryable error in MongoDB write: {e}"
                    ) from e
                else:
                    raise e

        # Use circuit breaker for write operation
        return self.circuit_breaker.call(_write_operation)

    def write_batch(
        self, model_instances: list[BaseModel], collection: str, batch_size: int = 1000
    ) -> int:
        """Write model instances in batches."""
        total_written = 0

        for i in range(0, len(model_instances), batch_size):
            batch = model_instances[i : i + batch_size]
            written = self.write(batch, collection)
            total_written += written

            if i + batch_size < len(model_instances):
                logger.debug(
                    "Written batch %d: %d records to %s",
                    i // batch_size + 1,
                    written,
                    collection,
                )

        return total_written

    def query_range(
        self,
        collection: str,
        start: datetime,
        end: datetime,
        symbol: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Query records within time range."""
        if not self._connected:
            raise DatabaseError("Not connected to database")

        try:
            db = self._get_database()
            coll: Collection = db[collection]

            # Build query filter
            query: dict[str, Any] = {"timestamp": {"$gte": start, "$lt": end}}

            if symbol:
                query["symbol"] = symbol

            # Sort by timestamp
            cursor = coll.find(query).sort("timestamp", ASCENDING)
            return list(cursor)

        except Exception as e:
            raise DatabaseError(f"Failed to query range from {collection}: {e}") from e

    def query_latest(
        self, collection: str, symbol: Optional[str] = None, limit: int = 1
    ) -> list[dict[str, Any]]:
        """Query most recent records."""
        if not self._connected:
            raise DatabaseError("Not connected to database")

        try:
            db = self._get_database()
            coll: Collection = db[collection]

            query: dict[str, Any] = {}
            if symbol:
                query["symbol"] = symbol

            cursor = coll.find(query).sort("timestamp", DESCENDING).limit(limit)
            return list(cursor)

        except Exception as e:
            raise DatabaseError(f"Failed to query latest from {collection}: {e}") from e

    def find_gaps(
        self,
        collection: str,
        start: datetime,
        end: datetime,
        interval_minutes: int,
        symbol: Optional[str] = None,
    ) -> list[tuple[datetime, datetime]]:
        """Find gaps in time series data."""
        if not self._connected:
            raise DatabaseError("Not connected to database")

        try:
            # Get all timestamps in range
            query: dict[str, Any] = {"timestamp": {"$gte": start, "$lt": end}}
            if symbol:
                query["symbol"] = symbol

            db = self._get_database()
            coll: Collection = db[collection]
            cursor = coll.find(query, {"timestamp": 1}).sort("timestamp", ASCENDING)
            timestamps = [doc["timestamp"] for doc in cursor]

            if not timestamps:
                return [(start, end)]

            gaps = []
            expected_interval = timedelta(minutes=interval_minutes)

            # Check for gap at the beginning
            if timestamps[0] > start + expected_interval:
                gaps.append((start, timestamps[0]))

            # Check for gaps between timestamps
            for i in range(len(timestamps) - 1):
                current = timestamps[i]
                next_timestamp = timestamps[i + 1]
                expected_next = current + expected_interval

                if next_timestamp > expected_next + timedelta(
                    minutes=1
                ):  # Allow 1-minute tolerance
                    gaps.append((expected_next, next_timestamp))

            # Check for gap at the end
            if timestamps[-1] < end - expected_interval:
                gaps.append((timestamps[-1] + expected_interval, end))

            return gaps

        except Exception as e:
            raise DatabaseError(f"Failed to find gaps in {collection}: {e}") from e

    def get_record_count(
        self,
        collection: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        symbol: Optional[str] = None,
    ) -> int:
        """Get count of records matching criteria."""
        if not self._connected:
            raise DatabaseError("Not connected to database")

        try:
            db = self._get_database()
            coll: Collection = db[collection]

            query: dict[str, Any] = {}
            if start or end:
                timestamp_filter = {}
                if start:
                    timestamp_filter["$gte"] = start
                if end:
                    timestamp_filter["$lt"] = end
                query["timestamp"] = timestamp_filter

            if symbol:
                query["symbol"] = symbol

            return coll.count_documents(query)

        except (ConnectionFailure, BulkWriteError, DuplicateKeyError) as e:
            raise DatabaseError(f"Failed to count records in {collection}: {e}") from e

    def ensure_indexes(self, collection: str) -> None:
        """Create indexes for optimal query performance."""
        if not self._connected:
            raise DatabaseError("Not connected to database")

        try:
            db = self._get_database()
            coll: Collection = db[collection]

            # Compound index on symbol and timestamp for efficient range queries
            coll.create_index([("symbol", ASCENDING), ("timestamp", ASCENDING)])

            # Index on timestamp for time-based queries
            coll.create_index([("timestamp", ASCENDING)])

            # For klines, add index on interval
            if "klines" in collection:
                coll.create_index(
                    [
                        ("symbol", ASCENDING),
                        ("interval", ASCENDING),
                        ("timestamp", ASCENDING),
                    ]
                )

            # For trades, add index on trade_id
            if collection == "trades":
                coll.create_index([("trade_id", ASCENDING)], unique=True, sparse=True)

            # Create indexes for better query performance
            coll.create_index([("symbol", 1), ("timestamp", -1)])
            coll.create_index([("timestamp", -1)])
            coll.create_index([("symbol", 1), ("interval", 1), ("timestamp", -1)])

            logger.info("Ensured indexes for collection: %s", collection)

        except Exception as e:
            logger.warning("Failed to create indexes for %s: %s", collection, e)

    def delete_range(
        self,
        collection: str,
        start: datetime,
        end: datetime,
        symbol: Optional[str] = None,
    ) -> int:
        """Delete records within time range."""
        if not self._connected:
            raise DatabaseError("Not connected to database")

        try:
            db = self._get_database()
            coll: Collection = db[collection]

            query: dict[str, Any] = {"timestamp": {"$gte": start, "$lt": end}}

            if symbol:
                query["symbol"] = symbol

            result = coll.delete_many(query)
            return result.deleted_count

        except (ConnectionFailure, BulkWriteError, DuplicateKeyError) as e:
            raise DatabaseError(f"Failed to delete from {collection}: {e}") from e

    def get_collection_names(self) -> list[str]:
        """Get list of all collection names."""
        if not self._connected:
            raise DatabaseError("Not connected to database")

        try:
            db = self._get_database()
            return db.list_collection_names()
        except Exception as e:
            raise DatabaseError(f"Failed to get collection names: {e}") from e

    def drop_collection(self, collection: str) -> None:
        """Drop a collection (use with caution)."""
        if not self._connected:
            raise DatabaseError("Not connected to database")

        db = self._get_database()
        db[collection].drop()
        logger.warning("Dropped collection: %s", collection)

    def get_database_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        if not self._connected:
            raise DatabaseError("Not connected to database")

        db = self._get_database()
        return db.command("dbStats")

    def _ensure_connected(self) -> "Database":
        """Ensure the database is connected and return it."""
        if self.database is None:
            raise DatabaseError("Database is not connected")
        return self.database

    def _get_database(self) -> "Database":
        """Get database connection with safety check."""
        if self.database is None:
            raise DatabaseError("Database connection is None. Call connect() first.")
        return self.database
