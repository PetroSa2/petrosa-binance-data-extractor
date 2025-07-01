"""
MongoDB adapter implementation.

This module provides a MongoDB implementation of the BaseAdapter interface.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

try:
    from pymongo import ASCENDING, DESCENDING, MongoClient
    from pymongo.collection import Collection
    from pymongo.database import Database
    from pymongo.errors import BulkWriteError, ConnectionFailure, DuplicateKeyError

    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False

import constants
from db.base_adapter import BaseAdapter, DatabaseError

logger = logging.getLogger(__name__)


class MongoDBAdapter(BaseAdapter):
    """
    MongoDB implementation of the BaseAdapter interface.

    Provides efficient storage and querying for time-series data using MongoDB.
    """

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
        self.database_name = kwargs.get("database_name", "binance")

        # Connection options
        self.client_options = {
            "serverSelectionTimeoutMS": constants.DB_CONNECTION_TIMEOUT * 1000,
            "connectTimeoutMS": constants.DB_CONNECTION_TIMEOUT * 1000,
            "maxPoolSize": kwargs.get("max_pool_size", 100),
            **kwargs,
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

    def write(self, model_instances: List[BaseModel], collection: str) -> int:
        """Write model instances to MongoDB collection."""
        if not self._connected:
            raise DatabaseError("Not connected to database")

        if not model_instances:
            return 0

        try:
            db = self._get_database()
            coll: Collection = db[collection]
            documents = []

            for instance in model_instances:
                doc = instance.model_dump()
                # Use timestamp as MongoDB _id for better performance and uniqueness
                if hasattr(instance, "timestamp") and hasattr(instance, "symbol"):
                    doc["_id"] = (
                        f"{instance.symbol}_{int(instance.timestamp.timestamp() * 1000)}"
                    )
                documents.append(doc)

            # Use ordered=False for better performance with duplicates
            result = coll.insert_many(documents, ordered=False)
            return len(result.inserted_ids)

        except DuplicateKeyError:
            # Handle duplicates gracefully
            logger.warning("Duplicate records found when writing to %s", collection)
            return 0
        except BulkWriteError as e:
            # Count successful writes even if some failed
            successful_writes = e.details.get("nInserted", 0)
            logger.warning("Bulk write error: %s", e.details.get('writeErrors', []))
            return successful_writes
        except Exception as e:
            raise DatabaseError(
                f"Failed to write to MongoDB collection {collection}: {e}"
            ) from e

    def write_batch(
        self, model_instances: List[BaseModel], collection: str, batch_size: int = 1000
    ) -> int:
        """Write model instances in batches."""
        total_written = 0

        for i in range(0, len(model_instances), batch_size):
            batch = model_instances[i : i + batch_size]
            written = self.write(batch, collection)
            total_written += written

            if i + batch_size < len(model_instances):
                logger.debug(
                    "Written batch %d: %d records to %s", i // batch_size + 1, written, collection
                )

        return total_written

    def query_range(
        self,
        collection: str,
        start: datetime,
        end: datetime,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query records within time range."""
        if not self._connected:
            raise DatabaseError("Not connected to database")

        try:
            db = self._get_database()
            coll: Collection = db[collection]

            # Build query filter
            query: Dict[str, Any] = {"timestamp": {"$gte": start, "$lt": end}}

            if symbol:
                query["symbol"] = symbol

            # Sort by timestamp
            cursor = coll.find(query).sort("timestamp", ASCENDING)
            return list(cursor)

        except Exception as e:
            raise DatabaseError(f"Failed to query range from {collection}: {e}") from e

    def query_latest(
        self, collection: str, symbol: Optional[str] = None, limit: int = 1
    ) -> List[Dict[str, Any]]:
        """Query most recent records."""
        if not self._connected:
            raise DatabaseError("Not connected to database")

        try:
            db = self._get_database()
            coll: Collection = db[collection]

            query: Dict[str, Any] = {}
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
    ) -> List[Tuple[datetime, datetime]]:
        """Find gaps in time series data."""
        if not self._connected:
            raise DatabaseError("Not connected to database")

        try:
            # Get all timestamps in range
            query: Dict[str, Any] = {"timestamp": {"$gte": start, "$lt": end}}
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

            query: Dict[str, Any] = {}
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

            query: Dict[str, Any] = {"timestamp": {"$gte": start, "$lt": end}}

            if symbol:
                query["symbol"] = symbol

            result = coll.delete_many(query)
            return result.deleted_count

        except (ConnectionFailure, BulkWriteError, DuplicateKeyError) as e:
            raise DatabaseError(f"Failed to delete from {collection}: {e}") from e

    def get_collection_names(self) -> List[str]:
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

    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        if not self._connected:
            raise DatabaseError("Not connected to database")

        db = self._get_database()
        return db.command("dbStats")

    def _ensure_connected(self) -> Database:
        """Ensure the database is connected and return it."""
        if self.database is None:
            raise DatabaseError("Database is not connected")
        return self.database

    def _get_database(self) -> "Database[Any]":
        """Get database connection with safety check."""
        if self.database is None:
            raise DatabaseError("Database connection is None. Call connect() first.")
        return self.database
