"""
Klines (candlestick) data fetcher for Binance Futures.
"""

import time
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import constants
from fetchers.client import BinanceAPIError, BinanceClient
from models.base import ExtractionMetadata
from models.kline import KlineModel
from utils.logger import get_logger
from utils.time_utils import (
    align_timestamp_to_interval,
    find_time_gaps,
    get_current_utc_time,
    get_interval_timedelta,
    validate_time_range,
)

logger = get_logger(__name__)


class KlinesFetcher:
    """
    Fetcher for Binance Futures klines (candlestick) data.

    Handles both incremental extraction and backfill operations.
    """

    def __init__(self, client: Optional[BinanceClient] = None):
        """
        Initialize klines fetcher.

        Args:
            client: BinanceClient instance
        """
        self.client = client or BinanceClient()
        self.max_klines_per_request = 1500  # Binance limit

    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[KlineModel]:
        """
        Fetch klines for a symbol and time range.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            interval: Kline interval (e.g., '15m', '1h')
            start_time: Start datetime
            end_time: End datetime (optional, defaults to now)
            limit: Maximum number of klines to fetch

        Returns:
            List of KlineModel instances

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
            "Fetching klines for %s (%s) from %s to %s",
            symbol,
            interval,
            start_time,
            end_time,
        )

        all_klines: List[KlineModel] = []
        current_start = start_time
        interval_delta = get_interval_timedelta(interval)

        # Calculate chunks based on API limits
        max_range = interval_delta * self.max_klines_per_request

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
                    limit - len(all_klines) if limit else self.max_klines_per_request,
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
                        kline = KlineModel.from_binance_kline(kline_data, symbol, interval)
                        chunk_klines.append(kline)
                    except (ValueError, TypeError) as e:
                        logger.warning("Failed to parse kline data: %s, data: %s", e, kline_data)
                        continue

                all_klines.extend(chunk_klines)

                # Update progress
                if chunk_klines:
                    last_kline_time = chunk_klines[-1].close_time
                    logger.debug(
                        "Fetched %d klines for %s, last: %s",
                        len(chunk_klines),
                        symbol,
                        last_kline_time,
                    )
                    current_start = last_kline_time + timedelta(seconds=1)
                else:
                    # No more data available
                    break

                # Small delay to be nice to the API
                if constants.REQUEST_DELAY_SECONDS > 0:

                    time.sleep(constants.REQUEST_DELAY_SECONDS)

            except BinanceAPIError as e:
                logger.error("API error fetching klines for %s: %s", symbol, e)
                if e.status_code == 429:  # Rate limit
                    # Wait longer and retry

                    time.sleep(60)
                    continue
                else:
                    raise
            except Exception as e:
                logger.error("Unexpected error fetching klines for %s: %s", symbol, e)
                raise

        logger.info("Fetched %d klines for %s (%s)", len(all_klines), symbol, interval)
        return all_klines

    def fetch_latest_klines(self, symbol: str, interval: str, count: int = 100) -> List[KlineModel]:
        """
        Fetch the most recent klines.

        Args:
            symbol: Trading symbol
            interval: Kline interval
            count: Number of latest klines to fetch

        Returns:
            List of KlineModel instances
        """
        try:
            klines_data = self.client.get_klines(
                symbol=symbol.upper(),
                interval=interval,
                limit=min(count, self.max_klines_per_request),
            )

            klines = []
            for kline_data in klines_data:
                try:
                    kline = KlineModel.from_binance_kline(kline_data, symbol, interval)
                    klines.append(kline)
                except (ValueError, TypeError) as e:
                    logger.warning("Failed to parse kline data: %s", e)
                    continue

            logger.info("Fetched %d latest klines for %s (%s)", len(klines), symbol, interval)
            return klines

        except Exception as e:
            logger.error("Error fetching latest klines for %s: %s", symbol, e)
            raise

    def fetch_incremental(
        self,
        symbol: str,
        interval: str,
        last_timestamp: datetime,
        max_records: int = 10000,
    ) -> List[KlineModel]:
        """
        Fetch klines incrementally from last timestamp.

        Args:
            symbol: Trading symbol
            interval: Kline interval
            last_timestamp: Last known timestamp
            max_records: Maximum number of records to fetch

        Returns:
            List of new KlineModel instances
        """
        # Start from next interval after last timestamp
        interval_delta = get_interval_timedelta(interval)
        start_time = last_timestamp + interval_delta
        end_time = get_current_utc_time()

        if start_time >= end_time:
            logger.info("No new data available for %s (%s)", symbol, interval)
            return []

        logger.info("Fetching incremental klines for %s from %s", symbol, start_time)

        return self.fetch_klines(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            limit=max_records,
        )

    def fetch_multiple_symbols(
        self,
        symbols: List[str],
        interval: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
    ) -> dict:
        """
        Fetch klines for multiple symbols.

        Args:
            symbols: List of trading symbols
            interval: Kline interval
            start_time: Start datetime
            end_time: End datetime (optional)

        Returns:
            Dictionary mapping symbol to list of KlineModel instances
        """
        results = {}
        total_symbols = len(symbols)

        for i, symbol in enumerate(symbols, 1):
            logger.info("Processing symbol %d/%d: %s", i, total_symbols, symbol)

            try:
                klines = self.fetch_klines(
                    symbol=symbol,
                    interval=interval,
                    start_time=start_time,
                    end_time=end_time,
                )
                results[symbol] = klines

            except BinanceAPIError as e:
                logger.error("Binance API error fetching klines for %s: %s", symbol, e)
                results[symbol] = []  # Empty list for failed symbols
                continue
            except ValueError as e:
                logger.error("Value error fetching klines for %s: %s", symbol, e)
                results[symbol] = []
                continue
            except TypeError as e:
                logger.error("Type error fetching klines for %s: %s", symbol, e)
                results[symbol] = []
                continue

        total_klines = sum(len(klines) for klines in results.values())
        logger.info(f"Fetched total of {total_klines} klines across {len(symbols)} symbols")

        return results

    def get_missing_intervals(
        self,
        existing_timestamps: List[datetime],
        start_time: datetime,
        end_time: datetime,
        interval: str,
    ) -> List[Tuple[datetime, datetime]]:
        """
        Find missing intervals in existing data.

        Args:
            existing_timestamps: List of existing timestamps
            start_time: Expected start time
            end_time: Expected end time
            interval: Kline interval

        Returns:
            List of (start, end) tuples representing missing ranges
        """

        return find_time_gaps(
            timestamps=existing_timestamps,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
        )

    def create_extraction_metadata(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        total_records: int,
        gaps_detected: int = 0,
        duration_seconds: float = 0.0,
        errors: Optional[list] = None,
    ) -> ExtractionMetadata:
        """
        Create extraction metadata for tracking.

        Args:
            symbol: Trading symbol
            interval: Kline interval
            start_time: Start time of extraction
            end_time: End time of extraction
            total_records: Total records extracted
            gaps_detected: Number of gaps found
            duration_seconds: Extraction duration
            errors: List of errors encountered

        Returns:
            ExtractionMetadata instance
        """
        return ExtractionMetadata(
            period=interval,
            start_time=start_time,
            end_time=end_time,
            total_records=total_records,
            gaps_detected=gaps_detected,
            extraction_duration_seconds=duration_seconds,
            errors_encountered=errors or [],
        )

    def close(self):
        """Close the fetcher and its client."""
        if hasattr(self.client, "close"):
            self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
