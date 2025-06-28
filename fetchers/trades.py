"""
Trades data fetcher for Binance Futures.
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta

from models.trade import TradeModel
from models.base import ExtractionMetadata
from fetchers.client import BinanceClient, BinanceAPIError
from utils.time_utils import get_current_utc_time
from utils.logger import get_logger
import constants

logger = get_logger(__name__)


class TradesFetcher:
    """
    Fetcher for Binance Futures trades data.

    Handles recent trades and historical trades extraction.
    """

    def __init__(self, client: Optional[BinanceClient] = None):
        """
        Initialize trades fetcher.

        Args:
            client: BinanceClient instance
        """
        self.client = client or BinanceClient()
        self.max_trades_per_request = 1000  # Binance limit

    def fetch_recent_trades(self, symbol: str, limit: int = 1000) -> List[TradeModel]:
        """
        Fetch recent trades for a symbol.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            limit: Maximum number of trades to fetch (max 1000)

        Returns:
            List of TradeModel instances

        Raises:
            BinanceAPIError: If API request fails
        """
        symbol = symbol.upper()
        limit = min(limit, self.max_trades_per_request)

        logger.info(f"Fetching {limit} recent trades for {symbol}")

        try:
            trades_data = self.client.get_recent_trades(symbol=symbol, limit=limit)

            trades = []
            for trade_data in trades_data:
                try:
                    trade = TradeModel.from_binance_trade(trade_data, symbol)
                    trades.append(trade)
                except Exception as e:
                    logger.warning(
                        f"Failed to parse trade data: {e}, data: {trade_data}"
                    )
                    continue

            logger.info(f"Fetched {len(trades)} recent trades for {symbol}")
            return trades

        except BinanceAPIError as e:
            logger.error(f"API error fetching recent trades for {symbol}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching recent trades for {symbol}: {e}")
            raise

    def fetch_historical_trades(
        self, symbol: str, from_id: Optional[int] = None, limit: int = 1000
    ) -> List[TradeModel]:
        """
        Fetch historical trades for a symbol.

        Note: This requires API key permissions.

        Args:
            symbol: Trading symbol
            from_id: Trade ID to start from (optional)
            limit: Maximum number of trades to fetch

        Returns:
            List of TradeModel instances

        Raises:
            BinanceAPIError: If API request fails or API key missing
        """
        symbol = symbol.upper()
        limit = min(limit, self.max_trades_per_request)

        logger.info(
            f"Fetching historical trades for {symbol}"
            + (f" from ID {from_id}" if from_id else "")
        )

        try:
            trades_data = self.client.get_historical_trades(
                symbol=symbol, from_id=from_id, limit=limit
            )

            trades = []
            for trade_data in trades_data:
                try:
                    trade = TradeModel.from_binance_trade(trade_data, symbol)
                    trades.append(trade)
                except Exception as e:
                    logger.warning(
                        f"Failed to parse trade data: {e}, data: {trade_data}"
                    )
                    continue

            logger.info(f"Fetched {len(trades)} historical trades for {symbol}")
            return trades

        except BinanceAPIError as e:
            logger.error(f"API error fetching historical trades for {symbol}: {e}")
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error fetching historical trades for {symbol}: {e}"
            )
            raise

    def fetch_trades_batch(
        self, symbol: str, start_id: int, batch_size: int = 1000, max_batches: int = 10
    ) -> List[TradeModel]:
        """
        Fetch multiple batches of historical trades.

        Args:
            symbol: Trading symbol
            start_id: Starting trade ID
            batch_size: Number of trades per batch
            max_batches: Maximum number of batches to fetch

        Returns:
            List of TradeModel instances from all batches
        """
        all_trades = []
        current_id = start_id
        batch_count = 0

        logger.info(f"Fetching trades batch for {symbol} starting from ID {start_id}")

        while batch_count < max_batches:
            try:
                batch_trades = self.fetch_historical_trades(
                    symbol=symbol, from_id=current_id, limit=batch_size
                )

                if not batch_trades:
                    logger.info(f"No more trades available for {symbol}")
                    break

                all_trades.extend(batch_trades)
                batch_count += 1

                # Update current_id for next batch
                current_id = max(trade.trade_id for trade in batch_trades) + 1

                logger.debug(
                    f"Fetched batch {batch_count}: {len(batch_trades)} trades, "
                    f"next ID: {current_id}"
                )

                # Small delay to be nice to the API
                if constants.REQUEST_DELAY_SECONDS > 0:
                    import time

                    time.sleep(constants.REQUEST_DELAY_SECONDS)

            except BinanceAPIError as e:
                if e.status_code == 429:  # Rate limit
                    logger.warning("Rate limit hit, waiting...")
                    import time

                    time.sleep(60)
                    continue
                else:
                    logger.error(f"API error in batch {batch_count}: {e}")
                    break
            except Exception as e:
                logger.error(f"Unexpected error in batch {batch_count}: {e}")
                break

        logger.info(
            f"Fetched total of {len(all_trades)} trades in {batch_count} batches"
        )
        return all_trades

    def fetch_multiple_symbols(
        self, symbols: List[str], limit: int = 1000, use_historical: bool = False
    ) -> dict:
        """
        Fetch trades for multiple symbols.

        Args:
            symbols: List of trading symbols
            limit: Number of trades per symbol
            use_historical: Whether to use historical trades endpoint

        Returns:
            Dictionary mapping symbol to list of TradeModel instances
        """
        results = {}
        total_symbols = len(symbols)

        for i, symbol in enumerate(symbols, 1):
            logger.info(f"Processing symbol {i}/{total_symbols}: {symbol}")

            try:
                if use_historical:
                    trades = self.fetch_historical_trades(symbol=symbol, limit=limit)
                else:
                    trades = self.fetch_recent_trades(symbol=symbol, limit=limit)

                results[symbol] = trades

            except Exception as e:
                logger.error(f"Failed to fetch trades for {symbol}: {e}")
                results[symbol] = []  # Empty list for failed symbols
                continue

        total_trades = sum(len(trades) for trades in results.values())
        logger.info(
            f"Fetched total of {total_trades} trades across {len(symbols)} symbols"
        )

        return results

    def get_latest_trade_id(self, symbol: str) -> Optional[int]:
        """
        Get the latest trade ID for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Latest trade ID or None if no trades found
        """
        try:
            recent_trades = self.fetch_recent_trades(symbol=symbol, limit=1)
            if recent_trades:
                return recent_trades[0].trade_id
            return None
        except Exception as e:
            logger.error(f"Failed to get latest trade ID for {symbol}: {e}")
            return None

    def fetch_trades_since_id(
        self, symbol: str, since_id: int, max_records: int = 10000
    ) -> List[TradeModel]:
        """
        Fetch all trades since a specific trade ID.

        Args:
            symbol: Trading symbol
            since_id: Trade ID to start from
            max_records: Maximum number of records to fetch

        Returns:
            List of TradeModel instances
        """
        batch_size = min(1000, max_records)
        max_batches = (max_records + batch_size - 1) // batch_size  # Ceiling division

        return self.fetch_trades_batch(
            symbol=symbol,
            start_id=since_id,
            batch_size=batch_size,
            max_batches=max_batches,
        )

    def create_extraction_metadata(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        total_records: int,
        duration_seconds: float = 0.0,
        errors: Optional[List[str]] = None,
    ) -> ExtractionMetadata:
        """
        Create extraction metadata for tracking.

        Args:
            symbol: Trading symbol
            start_time: Start time of extraction
            end_time: End time of extraction
            total_records: Total records extracted
            duration_seconds: Extraction duration
            errors: List of errors encountered

        Returns:
            ExtractionMetadata instance
        """
        return ExtractionMetadata(
            period="trades",  # Special period for trades
            start_time=start_time,
            end_time=end_time,
            total_records=total_records,
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
