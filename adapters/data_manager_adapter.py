"""
Data Manager adapter for petrosa-binance-data-extractor.

This adapter replaces direct database connections with calls to the
petrosa-data-manager API for data persistence.
"""

import asyncio
from datetime import datetime
from typing import Any

import constants
from clients.data_manager_client import DataManagerClient
from models.base import BaseModel
from utils.logger import get_logger

logger = get_logger(__name__)


class DataManagerAdapter:
    """
    Adapter for persisting data through the Data Manager API.

    Replaces direct database connections with API calls to petrosa-data-manager.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int = 30,
        max_retries: int = 3,
        database: str = "mongodb",
    ):
        """
        Initialize the Data Manager adapter.

        Args:
            base_url: Data Manager API base URL
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            database: Target database for data operations
        """
        self.base_url = base_url or constants.DATA_MANAGER_URL
        self.timeout = timeout or constants.DATA_MANAGER_TIMEOUT
        self.max_retries = max_retries or constants.DATA_MANAGER_MAX_RETRIES
        self.database = database or constants.DATA_MANAGER_DATABASE

        self._client: DataManagerClient | None = None
        self._connected = False

        logger.info(f"Initialized Data Manager adapter: {self.base_url}")

    async def connect(self):
        """Connect to the Data Manager service."""
        if self._connected:
            return

        try:
            self._client = DataManagerClient(
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )

            # Test connection with health check
            health = await self._client.health_check()
            if health.get("status") != "healthy":
                raise ConnectionError(f"Data Manager health check failed: {health}")

            self._connected = True
            logger.info("Connected to Data Manager service")

        except Exception as e:
            logger.error(f"Failed to connect to Data Manager: {e}")
            raise

    async def disconnect(self):
        """Disconnect from the Data Manager service."""
        if self._client:
            try:
                await self._client.close()
                logger.info("Disconnected from Data Manager service")
            except Exception as e:
                logger.warning(f"Error disconnecting from Data Manager: {e}")
            finally:
                self._client = None
                self._connected = False

    async def write(
        self,
        data: list[BaseModel],
        collection_name: str,
        batch_size: int | None = None,
    ) -> int:
        """
        Write data to the Data Manager.

        Args:
            data: List of BaseModel instances to write
            collection_name: Name of the collection/table
            batch_size: Batch size for writing (optional)

        Returns:
            Number of records written
        """
        if not self._connected:
            await self.connect()

        if not data:
            logger.warning("No data to write")
            return 0

        try:
            # Convert BaseModel instances to dictionaries
            data_dicts = []
            for item in data:
                if hasattr(item, "to_dict"):
                    data_dicts.append(item.to_dict())
                elif hasattr(item, "__dict__"):
                    data_dicts.append(item.__dict__)
                else:
                    logger.warning(f"Unable to convert item to dict: {type(item)}")
                    continue

            if not data_dicts:
                logger.warning("No valid data to write after conversion")
                return 0

            # Determine the appropriate insert method based on collection name
            if collection_name.startswith("klines_"):
                # Extract symbol and interval from data
                symbol = data_dicts[0].get("symbol", "UNKNOWN")
                interval = collection_name.replace("klines_", "")

                result = await self._client.insert_klines(
                    symbol=symbol,
                    interval=interval,
                    klines_data=data_dicts,
                    database=self.database,
                )

            elif collection_name.startswith("trades_"):
                symbol = collection_name.replace("trades_", "")

                result = await self._client.insert_trades(
                    symbol=symbol,
                    trades_data=data_dicts,
                    database=self.database,
                )

            elif collection_name.startswith("funding_"):
                symbol = collection_name.replace("funding_", "")

                result = await self._client.insert_funding_rates(
                    symbol=symbol,
                    funding_data=data_dicts,
                    database=self.database,
                )

            else:
                # Generic insert for other collection types
                result = await self._client._client.insert(
                    database=self.database,
                    collection=collection_name,
                    data=data_dicts,
                    validate=True,
                )

            written_count = result.get("inserted_count", 0)
            logger.info(f"Wrote {written_count} records to {collection_name}")
            return written_count

        except Exception as e:
            logger.error(f"Error writing data to {collection_name}: {e}")
            raise

    async def query_latest(
        self,
        collection_name: str,
        symbol: str | None = None,
        limit: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Query the latest records from a collection.

        Args:
            collection_name: Name of the collection
            symbol: Symbol to filter by (optional)
            limit: Maximum number of records to return

        Returns:
            List of latest records
        """
        if not self._connected:
            await self.connect()

        try:
            # Build filter
            filter_dict = {}
            if symbol:
                filter_dict["symbol"] = symbol

            # Query for latest records
            result = await self._client._client.query(
                database=self.database,
                collection=collection_name,
                filter=filter_dict,
                sort={"close_time": -1}
                if "klines" in collection_name
                else {"timestamp": -1},
                limit=limit,
            )

            return result.get("data", [])

        except Exception as e:
            logger.error(f"Error querying latest records from {collection_name}: {e}")
            return []

    async def find_gaps(
        self,
        collection_name: str,
        start_time: datetime,
        end_time: datetime,
        interval_minutes: int,
        symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Find gaps in the data.

        Args:
            collection_name: Name of the collection
            start_time: Start time for gap detection
            end_time: End time for gap detection
            interval_minutes: Interval in minutes
            symbol: Symbol to check gaps for (optional)

        Returns:
            List of gap records
        """
        if not self._connected:
            await self.connect()

        try:
            # Extract interval from collection name if it's a klines collection
            if collection_name.startswith("klines_"):
                interval = collection_name.replace("klines_", "")
                gaps = await self._client.find_gaps(
                    symbol=symbol or "UNKNOWN",
                    interval=interval,
                    start_time=start_time,
                    end_time=end_time,
                    database=self.database,
                )
                return gaps
            else:
                # For non-klines collections, return empty list
                logger.info(
                    f"Gap detection not implemented for collection: {collection_name}"
                )
                return []

        except Exception as e:
            logger.error(f"Error finding gaps in {collection_name}: {e}")
            return []

    async def health_check(self) -> dict[str, Any]:
        """
        Check the health of the Data Manager service.

        Returns:
            Health status information
        """
        if not self._connected:
            await self.connect()

        return await self._client.health_check()

    def __enter__(self):
        """Synchronous context manager entry."""
        # Start event loop if not already running
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, we can't use asyncio.run()
                # This is a limitation of the sync context manager
                logger.warning(
                    "Event loop is already running, async operations may not work properly"
                )
            else:
                asyncio.run(self.connect())
        except RuntimeError:
            # No event loop running, create one
            asyncio.run(self.connect())

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Synchronous context manager exit."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule the disconnect
                asyncio.create_task(self.disconnect())
            else:
                asyncio.run(self.disconnect())
        except RuntimeError:
            # No event loop running, create one
            asyncio.run(self.disconnect())

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
