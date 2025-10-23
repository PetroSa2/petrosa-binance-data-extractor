"""
Data Manager Client wrapper for petrosa-binance-data-extractor.

This module provides a simplified interface for the data extractor to interact
with the petrosa-data-manager API for data persistence.
"""

import os
from datetime import datetime, timedelta
from typing import Any

from data_manager_client import DataManagerClient as BaseDataManagerClient
from data_manager_client.exceptions import APIError, ConnectionError, TimeoutError

from utils.logger import get_logger

logger = get_logger(__name__)


class DataManagerClient:
    """
    Simplified Data Manager client for the data extractor.

    Provides methods specifically tailored for klines, trades, and funding data.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        Initialize the Data Manager client.

        Args:
            base_url: Data Manager API base URL
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.base_url = base_url or os.getenv(
            "DATA_MANAGER_URL", "http://petrosa-data-manager:8000"
        )
        self.timeout = timeout
        self.max_retries = max_retries

        # Initialize the base client
        self._client = BaseDataManagerClient(
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

        logger.info(f"Initialized Data Manager client: {self.base_url}")

    async def insert_klines(
        self,
        symbol: str,
        interval: str,
        klines_data: list[dict[str, Any]],
        database: str = "mongodb",
    ) -> dict[str, Any]:
        """
        Insert klines data into the data manager.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            interval: Kline interval (e.g., '15m', '1h')
            klines_data: List of kline records to insert
            database: Target database ('mongodb' or 'mysql')

        Returns:
            Insert result with count of inserted records

        Raises:
            APIError: If the API request fails
            ConnectionError: If connection to data manager fails
            TimeoutError: If request times out
        """
        if not klines_data:
            logger.warning(f"No klines data to insert for {symbol}")
            return {"inserted_count": 0, "success": True}

        # Determine collection name based on interval
        collection_name = f"klines_{interval}"

        try:
            logger.info(
                f"Inserting {len(klines_data)} klines for {symbol} ({interval})"
            )

            result = await self._client.insert(
                database=database,
                collection=collection_name,
                data=klines_data,
                validate=True,  # Enable schema validation
            )

            logger.info(
                f"Successfully inserted {result.get('inserted_count', 0)} klines for {symbol}"
            )
            return result

        except APIError as e:
            logger.error(f"API error inserting klines for {symbol}: {e}")
            raise
        except ConnectionError as e:
            logger.error(f"Connection error inserting klines for {symbol}: {e}")
            raise
        except TimeoutError as e:
            logger.error(f"Timeout error inserting klines for {symbol}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error inserting klines for {symbol}: {e}")
            raise

    async def insert_trades(
        self,
        symbol: str,
        trades_data: list[dict[str, Any]],
        database: str = "mongodb",
    ) -> dict[str, Any]:
        """
        Insert trades data into the data manager.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            trades_data: List of trade records to insert
            database: Target database ('mongodb' or 'mysql')

        Returns:
            Insert result with count of inserted records
        """
        if not trades_data:
            logger.warning(f"No trades data to insert for {symbol}")
            return {"inserted_count": 0, "success": True}

        collection_name = f"trades_{symbol}"

        try:
            logger.info(f"Inserting {len(trades_data)} trades for {symbol}")

            result = await self._client.insert(
                database=database,
                collection=collection_name,
                data=trades_data,
                validate=True,
            )

            logger.info(
                f"Successfully inserted {result.get('inserted_count', 0)} trades for {symbol}"
            )
            return result

        except Exception as e:
            logger.error(f"Error inserting trades for {symbol}: {e}")
            raise

    async def insert_funding_rates(
        self,
        symbol: str,
        funding_data: list[dict[str, Any]],
        database: str = "mongodb",
    ) -> dict[str, Any]:
        """
        Insert funding rates data into the data manager.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            funding_data: List of funding rate records to insert
            database: Target database ('mongodb' or 'mysql')

        Returns:
            Insert result with count of inserted records
        """
        if not funding_data:
            logger.warning(f"No funding data to insert for {symbol}")
            return {"inserted_count": 0, "success": True}

        collection_name = f"funding_{symbol}"

        try:
            logger.info(f"Inserting {len(funding_data)} funding rates for {symbol}")

            result = await self._client.insert(
                database=database,
                collection=collection_name,
                data=funding_data,
                validate=True,
            )

            logger.info(
                f"Successfully inserted {result.get('inserted_count', 0)} funding rates for {symbol}"
            )
            return result

        except Exception as e:
            logger.error(f"Error inserting funding rates for {symbol}: {e}")
            raise

    async def get_latest_timestamp(
        self,
        symbol: str,
        interval: str,
        database: str = "mongodb",
    ) -> datetime | None:
        """
        Get the latest timestamp for a symbol and interval.

        Args:
            symbol: Trading symbol
            interval: Kline interval
            database: Source database

        Returns:
            Latest timestamp or None if no data found
        """
        collection_name = f"klines_{interval}"

        try:
            # Query for the latest record
            result = await self._client.query(
                database=database,
                collection=collection_name,
                filter={"symbol": symbol},
                sort={"close_time": -1},
                limit=1,
            )

            if result.get("data") and len(result["data"]) > 0:
                latest_record = result["data"][0]
                timestamp = latest_record.get("close_time") or latest_record.get(
                    "timestamp"
                )

                if timestamp:
                    # Ensure timestamp is timezone-aware
                    if isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00")
                        )
                    return timestamp

            return None

        except Exception as e:
            logger.warning(
                f"Error getting latest timestamp for {symbol} ({interval}): {e}"
            )
            return None

    async def find_gaps(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        database: str = "mongodb",
    ) -> list[dict[str, Any]]:
        """
        Find gaps in klines data for a symbol and time range.

        Args:
            symbol: Trading symbol
            interval: Kline interval
            start_time: Start time for gap detection
            end_time: End time for gap detection
            database: Source database

        Returns:
            List of gap records
        """
        collection_name = f"klines_{interval}"

        try:
            # Query for existing timestamps in the range
            result = await self._client.query(
                database=database,
                collection=collection_name,
                filter={
                    "symbol": symbol,
                    "close_time": {
                        "$gte": start_time.isoformat(),
                        "$lte": end_time.isoformat(),
                    },
                },
                sort={"close_time": 1},
                fields=["close_time"],
            )

            # Extract timestamps
            existing_timestamps = []
            for record in result.get("data", []):
                timestamp = record.get("close_time")
                if timestamp:
                    if isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00")
                        )
                    existing_timestamps.append(timestamp)

            # Find gaps (simplified implementation)
            gaps = []
            if existing_timestamps:
                # Sort timestamps
                existing_timestamps.sort()

                # Check for gaps between consecutive timestamps
                for i in range(len(existing_timestamps) - 1):
                    current = existing_timestamps[i]
                    next_timestamp = existing_timestamps[i + 1]

                    # Calculate expected next timestamp based on interval
                    interval_minutes = self._interval_to_minutes(interval)
                    expected_next = current + timedelta(minutes=interval_minutes)

                    # If there's a gap, add it to the list
                    if next_timestamp > expected_next:
                        gaps.append(
                            {
                                "start_time": expected_next,
                                "end_time": next_timestamp,
                                "symbol": symbol,
                                "interval": interval,
                            }
                        )

            logger.info(f"Found {len(gaps)} gaps for {symbol} ({interval})")
            return gaps

        except Exception as e:
            logger.warning(f"Error finding gaps for {symbol} ({interval}): {e}")
            return []

    def _interval_to_minutes(self, interval: str) -> int:
        """Convert interval string to minutes."""
        interval_map = {
            "1m": 1,
            "3m": 3,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "2h": 120,
            "4h": 240,
            "6h": 360,
            "8h": 480,
            "12h": 720,
            "1d": 1440,
            "3d": 4320,
            "1w": 10080,
            "1M": 43200,
        }
        return interval_map.get(interval, 15)

    async def health_check(self) -> dict[str, Any]:
        """
        Check the health of the data manager service.

        Returns:
            Health status information
        """
        try:
            health = await self._client.health()
            logger.info(f"Data Manager health check: {health.get('status', 'unknown')}")
            return health
        except Exception as e:
            logger.error(f"Data Manager health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    async def close(self):
        """Close the client connection."""
        try:
            await self._client.close()
            logger.info("Data Manager client closed")
        except Exception as e:
            logger.warning(f"Error closing Data Manager client: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
