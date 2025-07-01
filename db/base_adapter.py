"""
Base database adapter interface.

This module defines the abstract base class that all database adapters must implement.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from models.base import ExtractionMetadata


class BaseAdapter(ABC):
    """
    Abstract base class for database adapters.

    All database implementations must inherit from this class and implement
    the required methods to provide a consistent interface.
    """

    def __init__(self, connection_string: str, **kwargs):
        """
        Initialize the adapter with connection parameters.

        Args:
            connection_string: Database connection string
            **kwargs: Additional connection parameters
        """
        self.connection_string = connection_string
        self.connection_params = kwargs
        self._connected = False

    @abstractmethod
    def connect(self) -> None:
        """
        Establish connection to the database.

        Raises:
            ConnectionError: If connection cannot be established
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Close the database connection."""

    @abstractmethod
    def write(self, model_instances: List[BaseModel], collection: str) -> int:
        """
        Write model instances to the specified collection.

        Args:
            model_instances: List of Pydantic model instances to write
            collection: Name of the collection/table to write to

        Returns:
            Number of records successfully written

        Raises:
            DatabaseError: If write operation fails
        """

    @abstractmethod
    def write_batch(
        self, model_instances: List[BaseModel], collection: str, batch_size: int = 1000
    ) -> int:
        """
        Write model instances in batches for better performance.

        Args:
            model_instances: List of Pydantic model instances to write
            collection: Name of the collection/table to write to
            batch_size: Number of records per batch

        Returns:
            Total number of records successfully written
        """

    @abstractmethod
    def query_range(
        self,
        collection: str,
        start: datetime,
        end: datetime,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query records within a time range.

        Args:
            collection: Name of the collection/table to query
            start: Start datetime (inclusive)
            end: End datetime (exclusive)
            symbol: Optional symbol filter

        Returns:
            List of records as dictionaries
        """

    @abstractmethod
    def query_latest(
        self, collection: str, symbol: Optional[str] = None, limit: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Query the most recent records.

        Args:
            collection: Name of the collection/table to query
            symbol: Optional symbol filter
            limit: Maximum number of records to return

        Returns:
            List of records as dictionaries, ordered by timestamp desc
        """

    @abstractmethod
    def find_gaps(
        self,
        collection: str,
        start: datetime,
        end: datetime,
        interval_minutes: int,
        symbol: Optional[str] = None,
    ) -> List[Tuple[datetime, datetime]]:
        """
        Find gaps in the data within the specified time range.

        Args:
            collection: Name of the collection/table to check
            start: Start datetime
            end: End datetime
            interval_minutes: Expected interval between records in minutes
            symbol: Optional symbol filter

        Returns:
            List of tuples representing gap start and end times
        """

    @abstractmethod
    def get_record_count(
        self,
        collection: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        symbol: Optional[str] = None,
    ) -> int:
        """
        Get count of records matching the criteria.

        Args:
            collection: Name of the collection/table
            start: Optional start datetime filter
            end: Optional end datetime filter
            symbol: Optional symbol filter

        Returns:
            Number of matching records
        """

    @abstractmethod
    def ensure_indexes(self, collection: str) -> None:
        """
        Ensure required indexes exist for optimal query performance.

        Args:
            collection: Name of the collection/table
        """

    @abstractmethod
    def delete_range(
        self,
        collection: str,
        start: datetime,
        end: datetime,
        symbol: Optional[str] = None,
    ) -> int:
        """
        Delete records within a time range.

        Args:
            collection: Name of the collection/table
            start: Start datetime (inclusive)
            end: End datetime (exclusive)
            symbol: Optional symbol filter

        Returns:
            Number of records deleted
        """

    def write_extraction_metadata(self, metadata: ExtractionMetadata) -> None:
        """
        Write extraction metadata to track extraction runs.

        Args:
            metadata: ExtractionMetadata instance
        """
        self.write([metadata], "extraction_metadata")

    def is_connected(self) -> bool:
        """Check if adapter is connected to database."""
        return self._connected

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


class DatabaseError(Exception):
    """Custom exception for database operations."""

