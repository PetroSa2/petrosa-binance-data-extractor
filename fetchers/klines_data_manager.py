"""
Klines fetcher with Data Manager integration.

This module provides a klines fetcher that uses the Data Manager API
for data persistence instead of direct database connections.
"""

import time
from datetime import datetime, timedelta

import constants
from adapters.data_manager_adapter import DataManagerAdapter
from fetchers.client import BinanceAPIError, BinanceClient
from models.kline import KlineModel
from utils.logger import get_logger
from utils.time_utils import (
    align_timestamp_to_interval,
    get_current_utc_time,
    get_interval_timedelta,
    validate_time_range,
)

logger = get_logger(__name__)


class KlinesFetcherDataManager:
    """
    Klines fetcher that uses Data Manager for data persistence.

    This fetcher replaces direct database connections with API calls
    to the petrosa-data-manager service.
    """

    def __init__(self, client: BinanceClient | None = None):
        """
        Initialize klines fetcher with Data Manager integration.

        Args:
            client: BinanceClient instance
        """
        self.client = client or BinanceClient()
        self.max_klines_per_request = 1500  # Binance limit

        # Initialize Data Manager adapter
        self.data_adapter = DataManagerAdapter(
            base_url=constants.DATA_MANAGER_URL,
            timeout=constants.DATA_MANAGER_TIMEOUT,
            max_retries=constants.DATA_MANAGER_MAX_RETRIES,
            database=constants.DATA_MANAGER_DATABASE,
        )

    async def fetch_and_store_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> list[KlineModel]:
        """
        Fetch klines and store them via Data Manager.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            interval: Kline interval (e.g., '15m', '1h')
            start_time: Start datetime
            end_time: End datetime (optional, defaults to now)
            limit: Maximum number of klines to fetch

        Returns:
            List of KlineModel instances that were stored

        Raises:
            ValueError: If parameters are invalid
            BinanceAPIError: If API request fails
        """
        # Validate inputs
        if interval not in constants.SUPPORTED_INTERVALS:
            raise ValueError(f"Unsupported interval: {interval}")

        symbol = symbol.upper()
        end_time = end_time or get_current_utc_time()

        # Align timestamps to interval boundaries
        start_time = align_timestamp_to_interval(start_time, interval)
        end_time = align_timestamp_to_interval(end_time, interval)

        # Validate time range
        validate_time_range(start_time, end_time)

        logger.info(
            "Fetching and storing klines",
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
        )

        all_klines: list[KlineModel] = []
        current_start = start_time
        interval_delta = get_interval_timedelta(interval)

        # Calculate chunks based on API limits
        max_range = interval_delta * self.max_klines_per_request

        try:
            # Connect to Data Manager
            await self.data_adapter.connect()

            while current_start < end_time:
                # Calculate chunk end time
                chunk_end = min(current_start + max_range, end_time)

                # Check if we've reached the limit
                if limit and len(all_klines) >= limit:
                    break

                try:
                    # Fetch klines for this chunk
                    chunk_limit = min(
                        self.max_klines_per_request,
                        limit - len(all_klines)
                        if limit
                        else self.max_klines_per_request,
                    )

                    klines_data = self.client.get_klines(
                        symbol=symbol,
                        interval=interval,
                        start_time=current_start,
                        end_time=chunk_end,
                        limit=chunk_limit,
                    )

                    # Convert to KlineModel instances
                    chunk_klines = []
                    for kline_data in klines_data:
                        try:
                            kline = KlineModel.from_binance_kline(
                                kline_data, symbol, interval
                            )
                            chunk_klines.append(kline)
                        except (ValueError, TypeError) as e:
                            logger.warning(
                                "Failed to parse kline data",
                                error=str(e),
                                data=kline_data,
                            )
                            continue

                    if chunk_klines:
                        # Store klines via Data Manager
                        collection_name = f"klines_{interval}"
                        records_written = await self.data_adapter.write(
                            data=chunk_klines,
                            collection_name=collection_name,
                        )

                        logger.info(
                            "Stored klines via Data Manager",
                            records_written=records_written,
                            symbol=symbol,
                            interval=interval,
                        )

                        all_klines.extend(chunk_klines)

                        # Update progress
                        last_kline_time = chunk_klines[-1].close_time
                        logger.debug(
                            "Fetched klines chunk",
                            klines_count=len(chunk_klines),
                            symbol=symbol,
                            last_time=last_kline_time,
                        )
                        current_start = last_kline_time + timedelta(seconds=1)
                    else:
                        # No more data available
                        break

                    # Small delay to be nice to the API
                    if constants.REQUEST_DELAY_SECONDS > 0:
                        time.sleep(constants.REQUEST_DELAY_SECONDS)

                except BinanceAPIError as e:
                    logger.error("API error fetching klines", symbol=symbol, error=str(e))
                    if e.status_code == 429:  # Rate limit
                        # Wait longer and retry
                        time.sleep(60)
                        continue
                    else:
                        raise
                except Exception as e:
                    logger.error(
                        "Unexpected error fetching klines", symbol=symbol, error=str(e)
                    )
                    raise

        finally:
            # Disconnect from Data Manager
            await self.data_adapter.disconnect()

        logger.info(
            "Fetched and stored klines",
            klines_count=len(all_klines),
            symbol=symbol,
            interval=interval,
        )
        return all_klines

    async def get_latest_timestamp(
        self,
        symbol: str,
        interval: str,
    ) -> datetime | None:
        """
        Get the latest timestamp for a symbol and interval from Data Manager.

        Args:
            symbol: Trading symbol
            interval: Kline interval

        Returns:
            Latest timestamp or None if no data found
        """
        try:
            await self.data_adapter.connect()

            collection_name = f"klines_{interval}"
            latest_records = await self.data_adapter.query_latest(
                collection_name=collection_name,
                symbol=symbol,
                limit=1,
            )

            if latest_records:
                latest_record = latest_records[0]
                timestamp = latest_record.get("close_time") or latest_record.get(
                    "timestamp"
                )

                if timestamp:
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
        finally:
            await self.data_adapter.disconnect()

    async def find_gaps(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict]:
        """
        Find gaps in klines data for a symbol and time range.

        Args:
            symbol: Trading symbol
            interval: Kline interval
            start_time: Start time for gap detection
            end_time: End time for gap detection

        Returns:
            List of gap records
        """
        try:
            await self.data_adapter.connect()

            collection_name = f"klines_{interval}"
            gaps = await self.data_adapter.find_gaps(
                collection_name=collection_name,
                start_time=start_time,
                end_time=end_time,
                interval_minutes=self._interval_to_minutes(interval),
                symbol=symbol,
            )

            return gaps

        except Exception as e:
            logger.warning(f"Error finding gaps for {symbol} ({interval}): {e}")
            return []
        finally:
            await self.data_adapter.disconnect()

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

    async def health_check(self) -> dict:
        """
        Check the health of both Binance API and Data Manager.

        Returns:
            Health status information
        """
        try:
            # Check Data Manager health
            dm_health = await self.data_adapter.health_check()

            # Check Binance API (simple test)
            try:
                self.client.get_server_time()
                binance_health = {"status": "healthy"}
            except Exception as e:
                binance_health = {"status": "unhealthy", "error": str(e)}

            return {
                "data_manager": dm_health,
                "binance_api": binance_health,
                "overall": "healthy"
                if dm_health.get("status") == "healthy"
                and binance_health.get("status") == "healthy"
                else "unhealthy",
            }

        except Exception as e:
            return {
                "data_manager": {"status": "unhealthy", "error": str(e)},
                "binance_api": {"status": "unknown"},
                "overall": "unhealthy",
            }

    def close(self):
        """Close the fetcher and its connections."""
        if hasattr(self.client, "close"):
            self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.close()
