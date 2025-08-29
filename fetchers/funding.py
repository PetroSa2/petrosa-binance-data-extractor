"""
Funding rates data fetcher for Binance Futures.
"""

import time
from datetime import datetime, timedelta
from typing import Any

import constants
from fetchers.client import BinanceAPIError, BinanceClient
from models.base import ExtractionMetadata
from models.funding_rate import FundingRateModel
from utils.logger import get_logger

logger = get_logger(__name__)


class FundingRatesFetcher:
    """
    Fetcher for Binance Futures funding rates data.

    Handles funding rate history and current funding rates.
    """

    def __init__(self, client: BinanceClient | None = None):
        """
        Initialize funding rates fetcher.

        Args:
            client: BinanceClient instance
        """
        self.client = client or BinanceClient()
        self.max_records_per_request = 1000  # Binance limit

    def fetch_funding_rate_history(
        self,
        symbol: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[FundingRateModel]:
        """
        Fetch funding rate history for a symbol.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            start_time: Start datetime (optional)
            end_time: End datetime (optional)
            limit: Maximum number of records to fetch

        Returns:
            List of FundingRateModel instances

        Raises:
            BinanceAPIError: If API request fails
        """
        symbol = symbol.upper()
        limit = min(limit, self.max_records_per_request)

        logger.info("Fetching funding rate history for %s", symbol)

        try:
            # Get funding rate history
            funding_data = self.client.get_funding_rate(symbol=symbol, limit=limit)

            funding_rates = []
            for rate_data in funding_data:
                try:
                    funding_rate = FundingRateModel.from_binance_funding_rate(
                        rate_data, symbol
                    )

                    # Apply time filters if specified
                    if start_time and funding_rate.funding_time < start_time:
                        continue
                    if end_time and funding_rate.funding_time > end_time:
                        continue

                    funding_rates.append(funding_rate)

                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(
                        "Failed to parse funding rate data: %s, data: %s", e, rate_data
                    )
                    continue

            logger.info(
                "Fetched %d funding rate records for %s", len(funding_rates), symbol
            )
            return funding_rates

        except BinanceAPIError as e:
            logger.error("API error fetching funding rates for %s: %s", symbol, e)
            raise
        except Exception as e:
            logger.error(
                "Unexpected error fetching funding rates for %s: %s", symbol, e
            )
            raise

    def fetch_current_funding_rates(
        self, symbols: list[str] | None = None
    ) -> list[FundingRateModel]:
        """
        Fetch current funding rates for symbols.

        Args:
            symbols: List of trading symbols (optional, if None fetches all)

        Returns:
            List of FundingRateModel instances with current rates
        """
        if symbols:
            logger.info("Fetching current funding rates for %d symbols", len(symbols))
        else:
            logger.info("Fetching current funding rates for all symbols")

        try:
            funding_rates = []

            if symbols:
                # Fetch for specific symbols
                for symbol in symbols:
                    try:
                        # Get premium index which includes current funding info
                        premium_data = self.client.get_premium_index(
                            symbol=symbol.upper()
                        )

                        # Handle both single symbol and list responses
                        if isinstance(premium_data, list):
                            premium_data = premium_data[0] if premium_data else {}

                        if premium_data:
                            funding_rate = FundingRateModel.from_binance_premium_index(
                                premium_data, symbol
                            )
                            funding_rates.append(funding_rate)

                    except BinanceAPIError as e:
                        logger.warning(
                            "Failed to fetch current funding rate for %s: %s", symbol, e
                        )
                        continue
            else:
                # Fetch for all symbols
                premium_data = self.client.get_premium_index()

                if isinstance(premium_data, list):
                    for item in premium_data:
                        try:
                            symbol = item.get("symbol", "")
                            if symbol:
                                funding_rate = (
                                    FundingRateModel.from_binance_premium_index(
                                        item, symbol
                                    )
                                )
                                funding_rates.append(funding_rate)
                        except (KeyError, ValueError, TypeError) as e:
                            logger.warning(
                                "Failed to parse funding rate data: %s, data: %s",
                                e,
                                item,
                            )
                            continue

            logger.info("Fetched %d current funding rates", len(funding_rates))
            return funding_rates

        except BinanceAPIError as e:
            logger.error("API error fetching current funding rates: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error fetching current funding rates: %s", e)
            raise

    def fetch_funding_rates_batch(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        batch_hours: int = 24 * 30,
    ) -> list[FundingRateModel]:
        """
        Fetch funding rates in time-based batches.

        Args:
            symbol: Trading symbol
            start_time: Start datetime
            end_time: End datetime
            batch_hours: Hours per batch (default 30 days)

        Returns:
            List of FundingRateModel instances
        """
        all_rates = []
        current_start = start_time
        batch_delta = timedelta(hours=batch_hours)

        logger.info(
            "Fetching funding rates for %s from %s to %s", symbol, start_time, end_time
        )

        while current_start < end_time:
            batch_end = min(current_start + batch_delta, end_time)

            try:
                batch_rates = self.fetch_funding_rate_history(
                    symbol=symbol,
                    start_time=current_start,
                    end_time=batch_end,
                    limit=self.max_records_per_request,
                )

                all_rates.extend(batch_rates)

                logger.debug(
                    "Fetched %d funding rates for %s from %s to %s",
                    len(batch_rates),
                    symbol,
                    current_start,
                    batch_end,
                )

                current_start = batch_end

                # Small delay to be nice to the API
                if constants.REQUEST_DELAY_SECONDS > 0:
                    time.sleep(constants.REQUEST_DELAY_SECONDS)

            except BinanceAPIError as e:
                if e.status_code == 429:  # Rate limit
                    logger.warning("Rate limit hit, waiting...")
                    time.sleep(60)
                    continue
                else:
                    logger.error("API error in batch: %s", e)
                    raise
            except Exception as e:
                logger.error("Unexpected error in batch: %s", e)
                raise

        logger.info("Fetched total of %d funding rates for %s", len(all_rates), symbol)
        return all_rates

    def fetch_multiple_symbols(
        self,
        symbols: list[str],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> dict[str, list[FundingRateModel]]:
        """
        Fetch funding rates for multiple symbols.

        Args:
            symbols: List of trading symbols
            start_time: Start datetime (optional)
            end_time: End datetime (optional)
            limit: Maximum records per symbol

        Returns:
            Dictionary mapping symbol to list of FundingRateModel instances
        """
        results = {}
        total_symbols = len(symbols)

        for i, symbol in enumerate(symbols, 1):
            logger.info("Processing symbol %d/%d: %s", i, total_symbols, symbol)

            try:
                if start_time and end_time:
                    # Use batch fetching for time ranges
                    rates = self.fetch_funding_rates_batch(
                        symbol=symbol, start_time=start_time, end_time=end_time
                    )
                else:
                    # Fetch recent history
                    rates = self.fetch_funding_rate_history(
                        symbol=symbol,
                        start_time=start_time,
                        end_time=end_time,
                        limit=limit,
                    )

                results[symbol] = rates

            except (KeyError, ValueError, TypeError, BinanceAPIError) as e:
                logger.error("Failed to fetch funding rates for %s: %s", symbol, e)
                results[symbol] = []  # Empty list for failed symbols
                continue

        total_rates = sum(len(rates) for rates in results.values())
        logger.info(
            "Fetched total of %d funding rates across %d symbols",
            total_rates,
            len(symbols),
        )

        return results

    def fetch_latest_funding_rates(
        self, symbols: list[str], limit: int = 10
    ) -> dict[str, list[FundingRateModel]]:
        """
        Fetch the most recent funding rates for symbols.

        Args:
            symbols: List of trading symbols
            limit: Number of latest rates per symbol

        Returns:
            Dictionary mapping symbol to list of recent FundingRateModel instances
        """
        results = {}

        for symbol in symbols:
            try:
                rates = self.fetch_funding_rate_history(symbol=symbol, limit=limit)

                # Sort by funding time (most recent first)
                rates.sort(key=lambda x: x.funding_time, reverse=True)
                results[symbol] = rates

            except (KeyError, ValueError, TypeError, BinanceAPIError) as e:
                logger.error(
                    "Failed to fetch latest funding rates for %s: %s", symbol, e
                )
                results[symbol] = []
                continue

        return results

    def get_funding_schedule(self, symbol: str) -> dict[str, Any]:
        """
        Get funding schedule information for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Dictionary with funding schedule info
        """
        try:
            # Get current funding info
            premium_data = self.client.get_premium_index(symbol=symbol.upper())

            if isinstance(premium_data, list):
                premium_data = premium_data[0] if premium_data else {}

            if not premium_data:
                return {}

            next_funding_time = datetime.utcfromtimestamp(
                int(premium_data["nextFundingTime"]) / 1000
            )

            return {
                "symbol": symbol.upper(),
                "next_funding_time": next_funding_time,
                "current_funding_rate": premium_data.get("lastFundingRate", "0"),
                "mark_price": premium_data.get("markPrice", "0"),
                "index_price": premium_data.get("indexPrice", "0"),
                "funding_interval_hours": 8,  # Default for most symbols
            }

        except (KeyError, ValueError, TypeError, BinanceAPIError) as e:
            logger.error("Failed to get funding schedule for %s: %s", symbol, e)
            return {}

    def create_extraction_metadata(
        self,
        start_time: datetime,
        end_time: datetime,
        total_records: int,
        duration_seconds: float = 0.0,
        errors: list | None = None,
    ) -> ExtractionMetadata:
        """
        Create extraction metadata for tracking.

        Args:
            start_time: Start time of extraction
            end_time: End time of extraction
            total_records: Total records extracted
            duration_seconds: Extraction duration
            errors: List of errors encountered

        Returns:
            ExtractionMetadata instance
        """
        return ExtractionMetadata(
            period="funding_rates",  # Special period for funding rates
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
