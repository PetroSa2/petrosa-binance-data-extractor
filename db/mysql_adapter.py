"""
MySQL adapter implementation.

This module provides a MySQL/MariaDB implementation of the BaseAdapter interface.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from utils.time_utils import (
    binance_interval_to_table_suffix,
    table_suffix_to_binance_interval,
)

try:
    import sqlalchemy as sa
    from sqlalchemy import (
        Boolean,
        Column,
        DateTime,
        Index,
        Integer,
        MetaData,
        Numeric,
        String,
        Table,
        create_engine,
        literal_column,
    )
    from sqlalchemy.engine import Engine
    from sqlalchemy.exc import IntegrityError, SQLAlchemyError
    from sqlalchemy.sql import and_, delete, func, select

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

import constants

from .base_adapter import BaseAdapter, DatabaseError

logger = logging.getLogger(__name__)


class MySQLAdapter(BaseAdapter):
    """
    MySQL/MariaDB implementation of the BaseAdapter interface.

    Uses SQLAlchemy for database operations and provides efficient storage
    for time-series data with proper indexing.
    """

    def __init__(self, connection_string: Optional[str] = None, **kwargs):
        """
        Initialize MySQL adapter.

        Args:
            connection_string: MySQL connection string
            **kwargs: Additional SQLAlchemy engine options
        """
        if not SQLALCHEMY_AVAILABLE:
            raise ImportError(
                "SQLAlchemy and MySQL driver are required. Install with: pip"
            )

        connection_string = connection_string or constants.MYSQL_URI
        super().__init__(connection_string, **kwargs)

        # SQLAlchemy specific settings
        self.engine: Optional[Engine] = None
        self.metadata = MetaData()
        self.tables: Dict[str, Table] = {}

        # Engine options
        self.engine_options = {
            "pool_pre_ping": True,
            "pool_recycle": 3600,
            "connect_args": {"charset": "utf8mb4"},
            **kwargs,
        }

    def connect(self) -> None:
        """Establish connection to MySQL."""
        try:
            self.engine = create_engine(self.connection_string, **self.engine_options)
            # Test connection
            if self.engine is not None:
                with self.engine.connect() as conn:
                    conn.execute(sa.text("SELECT 1"))
            self._connected = True
            logger.info("Connected to MySQL database")

            # Create tables if they don't exist
            self._create_tables()

        except SQLAlchemyError as e:
            raise DatabaseError(f"Failed to connect to MySQL: {e}") from e

    def disconnect(self) -> None:
        """Close MySQL connection."""
        if self.engine:
            self.engine.dispose()
            self._connected = False
            logger.info("Disconnected from MySQL")

    def _create_tables(self) -> None:
        """Create database tables for different data types."""
        # Klines table (dynamic based on interval)
        # We'll create tables dynamically based on collection names

        # Trades table
        self.tables["trades"] = Table(
            "trades",
            self.metadata,
            Column("id", String(64), primary_key=True),
            Column("symbol", String(20), nullable=False),
            Column("timestamp", DateTime, nullable=False),
            Column("trade_id", Integer, nullable=False),
            Column("order_id", Integer, nullable=True),
            Column("price", Numeric(20, 8), nullable=False),
            Column("quantity", Numeric(20, 8), nullable=False),
            Column("quote_quantity", Numeric(20, 8), nullable=False),
            Column("is_buyer_maker", Boolean, nullable=False),
            Column("commission", Numeric(20, 8), nullable=True),
            Column("commission_asset", String(10), nullable=True),
            Column("trade_time", DateTime, nullable=False),
            Column("extracted_at", DateTime, nullable=False),
            Column("extractor_version", String(20), nullable=False),
            Column("source", String(50), nullable=False),
            Index("idx_trades_symbol_timestamp", "symbol", "timestamp"),
            Index("idx_trades_timestamp", "timestamp"),
            Index("idx_trades_trade_id", "trade_id", unique=True),
        )

        # Funding rates table
        self.tables["funding_rates"] = Table(
            "funding_rates",
            self.metadata,
            Column("id", String(64), primary_key=True),
            Column("symbol", String(20), nullable=False),
            Column("timestamp", DateTime, nullable=False),
            Column("funding_rate", Numeric(20, 8), nullable=False),
            Column("funding_time", DateTime, nullable=False),
            Column("mark_price", Numeric(20, 8), nullable=True),
            Column("index_price", Numeric(20, 8), nullable=True),
            Column("last_funding_rate", Numeric(20, 8), nullable=True),
            Column("funding_interval_hours", Integer, nullable=False, default=8),
            Column("extracted_at", DateTime, nullable=False),
            Column("extractor_version", String(20), nullable=False),
            Column("source", String(50), nullable=False),
            Index("idx_funding_rates_symbol_timestamp", "symbol", "timestamp"),
            Index("idx_funding_rates_timestamp", "timestamp"),
            Index("idx_funding_rates_funding_time", "funding_time"),
        )

        # Extraction metadata table
        self.tables["extraction_metadata"] = Table(
            "extraction_metadata",
            self.metadata,
            Column("extraction_id", String(64), primary_key=True),
            Column("period", String(10), nullable=False),
            Column("start_time", DateTime, nullable=False),
            Column("end_time", DateTime, nullable=False),
            Column("total_records", Integer, nullable=False, default=0),
            Column("gaps_detected", Integer, nullable=False, default=0),
            Column("backfill_performed", Boolean, nullable=False, default=False),
            Column(
                "extraction_duration_seconds", Numeric(10, 3), nullable=False, default=0
            ),
            Column("extracted_at", DateTime, nullable=False),
            Index("idx_extraction_metadata_period_start", "period", "start_time"),
        )

        # Create all tables
        if self.engine is not None:
            self.metadata.create_all(self.engine)

    def _create_klines_table(self, interval: str) -> Table:
        """Create a klines table for specific interval."""
        table_suffix = binance_interval_to_table_suffix(interval)
        table_name = f"klines_{table_suffix}"

        if table_name in self.tables:
            return self.tables[table_name]

        table = Table(
            table_name,
            self.metadata,
            Column("id", String(64), primary_key=True),
            Column("symbol", String(20), nullable=False),
            Column("timestamp", DateTime, nullable=False),
            Column("open_time", DateTime, nullable=False),
            Column("close_time", DateTime, nullable=False),
            Column("interval", String(10), nullable=False),
            Column("open_price", Numeric(20, 8), nullable=False),
            Column("high_price", Numeric(20, 8), nullable=False),
            Column("low_price", Numeric(20, 8), nullable=False),
            Column("close_price", Numeric(20, 8), nullable=False),
            Column("volume", Numeric(20, 8), nullable=False),
            Column("quote_asset_volume", Numeric(20, 8), nullable=False),
            Column("number_of_trades", Integer, nullable=False),
            Column("taker_buy_base_asset_volume", Numeric(20, 8), nullable=False),
            Column("taker_buy_quote_asset_volume", Numeric(20, 8), nullable=False),
            Column("price_change", Numeric(20, 8), nullable=True),
            Column("price_change_percent", Numeric(10, 4), nullable=True),
            Column("extracted_at", DateTime, nullable=False),
            Column("extractor_version", String(20), nullable=False),
            Column("source", String(50), nullable=False),
            Index(f"idx_{table_name}_symbol_timestamp", "symbol", "timestamp"),
            Index(f"idx_{table_name}_timestamp", "timestamp"),
            Index(f"idx_{table_name}_open_time", "open_time"),
        )

        self.tables[table_name] = table
        if self.engine is not None:
            table.create(self.engine, checkfirst=True)
        return table

    def _get_table(self, collection: str) -> Table:
        """Get table object for collection."""
        if collection.startswith("klines_"):
            table_suffix = collection.replace("klines_", "")
            interval = table_suffix_to_binance_interval(table_suffix)
            return self._create_klines_table(interval)
        elif collection in self.tables:
            return self.tables[collection]
        else:
            raise DatabaseError(f"Unknown collection: {collection}")

    def write(self, model_instances: List[BaseModel], collection: str) -> int:
        """Write model instances to MySQL table."""
        if not self._connected:
            raise DatabaseError("Not connected to database")

        if not model_instances:
            return 0

        try:
            table = self._get_table(collection)

            # Convert models to dictionaries
            records = []
            for instance in model_instances:
                record = instance.model_dump()
                # Create unique ID for MySQL
                if hasattr(instance, "timestamp") and hasattr(instance, "symbol"):
                    record["id"] = (
                        f"{instance.symbol}_{int(instance.timestamp.timestamp() * 1000)}"
                    )
                records.append(record)

            # Insert records
            engine = self._ensure_connected()
            with engine.connect() as conn:
                trans = conn.begin()
                try:
                    # Use INSERT IGNORE to handle duplicates
                    stmt = table.insert().prefix_with("IGNORE")
                    result = conn.execute(stmt, records)
                    trans.commit()
                    return result.rowcount
                except Exception:
                    trans.rollback()
                    raise

        except IntegrityError:
            logger.warning("Duplicate records found when writing to %s", collection)
            return 0
        except Exception as e:
            raise DatabaseError(f"Failed to write to MySQL table {collection}: {e}") from e

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
            table = self._get_table(collection)

            # Build query
            query = select(table).where(
                and_(table.c.timestamp >= start, table.c.timestamp < end)
            )

            if symbol:
                query = query.where(table.c.symbol == symbol)

            query = query.order_by(table.c.timestamp)

            engine = self._ensure_connected()
            with engine.connect() as conn:
                result = conn.execute(query)
                return [dict(row) for row in result.mappings()]

        except Exception as e:
            raise DatabaseError(f"Failed to query range from {collection}: {e}") from e

    def query_latest(
        self, collection: str, symbol: Optional[str] = None, limit: int = 1
    ) -> List[Dict[str, Any]]:
        """Query most recent records."""
        if not self._connected:
            raise DatabaseError("Not connected to database")

        try:
            table = self._get_table(collection)

            query = select(table)
            if symbol:
                query = query.where(table.c.symbol == symbol)

            query = query.order_by(table.c.timestamp.desc()).limit(limit)

            engine = self._ensure_connected()
            with engine.connect() as conn:
                result = conn.execute(query)
                return [dict(row) for row in result.mappings()]

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
        # This is a simplified implementation - for production use,
        # consider using MySQL-specific window functions for better performance
        records = self.query_range(collection, start, end, symbol)

        if not records:
            return [(start, end)]

        timestamps = []
        for record in records:
            ts = record["timestamp"]
            # Ensure timezone awareness for comparison
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            timestamps.append(ts)

        timestamps.sort()

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

            if next_timestamp > expected_next + timedelta(minutes=1):
                gaps.append((expected_next, next_timestamp))

        # Check for gap at the end
        if timestamps[-1] < end - expected_interval:
            gaps.append((timestamps[-1] + expected_interval, end))

        return gaps

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
            table = self._get_table(collection)

            query = select(func.count(literal_column('*'))).select_from(table)

            conditions = []
            if start:
                conditions.append(table.c.timestamp >= start)
            if end:
                conditions.append(table.c.timestamp < end)
            if symbol:
                conditions.append(table.c.symbol == symbol)

            if conditions:
                query = query.where(and_(*conditions))

            engine = self._ensure_connected()
            with engine.connect() as conn:
                result = conn.execute(query)
                count = result.scalar()
                return count if count is not None else 0

        except Exception as e:
            raise DatabaseError(f"Failed to count records in {collection}: {e}") from e

    def ensure_indexes(self, collection: str) -> None:
        """Ensure indexes exist (handled during table creation)."""
        # Indexes are created during table creation in MySQL adapter
        logger.info("Indexes already exist for table: %s", collection)

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
            table = self._get_table(collection)

            conditions = [table.c.timestamp >= start, table.c.timestamp < end]

            if symbol:
                conditions.append(table.c.symbol == symbol)

            stmt = delete(table).where(and_(*conditions))

            engine = self._ensure_connected()
            with engine.connect() as conn:
                trans = conn.begin()
                try:
                    result = conn.execute(stmt)
                    trans.commit()
                    return result.rowcount
                except Exception:
                    trans.rollback()
                    raise

        except Exception as e:
            raise DatabaseError(f"Failed to delete from {collection}: {e}") from e

    def _ensure_connected(self) -> Engine:
        """Ensure the database engine is connected and return it."""
        if self.engine is None:
            raise DatabaseError("Database engine is not initialized")
        if not self._connected:
            raise DatabaseError("Database is not connected")
        return self.engine
