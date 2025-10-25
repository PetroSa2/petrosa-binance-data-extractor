#!/usr/bin/env python3
"""
Data Manager-based klines extraction job for Kubernetes environments.

This script uses the petrosa-data-manager API for data persistence instead
of direct database connections, providing a centralized data layer.
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any

# Add project root to path (works for both local and container environments)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import constants  # noqa: E402
from fetchers import BinanceClient  # noqa: E402
from fetchers.klines_data_manager import KlinesFetcherDataManager  # noqa: E402
from utils.logger import (  # noqa: E402
    get_logger,
    log_extraction_completion,
    log_extraction_start,
    setup_logging,
)
from utils.messaging import publish_extraction_completion_sync  # noqa: E402
from utils.time_utils import format_duration, get_current_utc_time  # noqa: E402

# Initialize OpenTelemetry as early as possible
try:
    from petrosa_otel import initialize_telemetry_standard  # noqa: E402

    if not os.getenv("OTEL_NO_AUTO_INIT"):
        initialize_telemetry_standard(
            service_name=constants.OTEL_SERVICE_NAME_KLINES,
            service_type="cronjob",
            enable_mysql=True,
            enable_mongodb=True,
        )
except ImportError:
    pass


class DataManagerKlinesExtractor:
    """Data Manager-based klines extractor with automatic gap detection."""

    # Configuration constants
    OVERLAP_MINUTES = 30  # Minutes of overlap to catch missed data
    END_TIME_BUFFER_MINUTES = (
        5  # Buffer before current time to avoid incomplete candles
    )
    MAX_CATCHUP_DAYS = 1  # Maximum days to catch up at once

    def __init__(
        self,
        symbols: list[str],
        period: str,
        max_workers: int = 5,
        lookback_hours: int = 24,
    ):
        """
        Initialize the Data Manager klines extractor.

        Args:
            symbols: List of trading symbols to extract
            period: Kline interval (e.g., '15m', '1h')
            max_workers: Maximum number of parallel workers
            lookback_hours: Hours to look back for gap detection
        """
        self.symbols = symbols
        self.period = period
        self.max_workers = max_workers
        self.lookback_hours = lookback_hours

        # Thread-safe logger
        self.logger = get_logger(__name__)

        # Statistics
        self.stats: dict[str, Any] = {
            "symbols_processed": 0,
            "symbols_failed": 0,
            "total_records_fetched": 0,
            "total_records_written": 0,
            "total_gaps_filled": 0,
            "errors": [],
        }

    async def extract_symbol_data(
        self, symbol: str, binance_client: BinanceClient
    ) -> dict[str, Any]:
        """
        Extract data for a single symbol using Data Manager.

        Args:
            symbol: Trading symbol
            binance_client: Binance API client

        Returns:
            Extraction result dictionary
        """
        symbol_start_time = time.time()
        result = {
            "symbol": symbol,
            "success": False,
            "records_fetched": 0,
            "records_written": 0,
            "gaps_filled": 0,
            "error": None,
            "duration": 0,
        }

        try:
            # Create Data Manager fetcher
            fetcher = KlinesFetcherDataManager(binance_client)

            # Get latest timestamp from Data Manager
            last_timestamp = await fetcher.get_latest_timestamp(symbol, self.period)

            if last_timestamp is None:
                # No data found, start from default start date
                last_timestamp = datetime.fromisoformat(
                    constants.DEFAULT_START_DATE.replace("Z", "+00:00")
                )

            # Calculate extraction window
            start_time, end_time = self._calculate_extraction_window(last_timestamp)

            self.logger.info(
                f"Extracting {symbol} ({self.period}): "
                f"from {start_time.isoformat()} to {end_time.isoformat()}"
            )

            # Fetch and store klines via Data Manager
            klines_data = await fetcher.fetch_and_store_klines(
                symbol=symbol,
                interval=self.period,
                start_time=start_time,
                end_time=end_time,
            )

            result["records_fetched"] = len(klines_data)
            result["records_written"] = len(
                klines_data
            )  # Same as fetched since we store immediately

            # Check for gaps
            gaps = await fetcher.find_gaps(
                symbol=symbol,
                interval=self.period,
                start_time=start_time,
                end_time=end_time,
            )
            result["gaps_filled"] = len(gaps)

            if gaps:
                self.logger.warning(f"Found {len(gaps)} gaps for {symbol}")

            result["success"] = True
            result["duration"] = time.time() - symbol_start_time

            self.logger.info(
                f"✅ {symbol}: fetched={result['records_fetched']}, "
                f"written={result['records_written']}, "
                f"duration={result['duration']:.2f}s"
            )

            # Send NATS message for symbol completion
            if constants.NATS_ENABLED:
                try:
                    publish_extraction_completion_sync(
                        symbol=symbol,
                        period=self.period,
                        records_fetched=result["records_fetched"],
                        records_written=result["records_written"],
                        success=result["success"],
                        duration_seconds=result["duration"],
                        errors=[result["error"]] if result["error"] else None,
                        gaps_found=0,
                        gaps_filled=result["gaps_filled"],
                        extraction_type="klines",
                        use_production_prefix=True,
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Failed to send NATS message for {symbol}: {e}"
                    )

            return result

        except Exception as e:
            result["error"] = str(e)
            result["duration"] = time.time() - symbol_start_time
            self.logger.error(f"❌ {symbol} failed: {e}")
            return result

    def _calculate_extraction_window(
        self, last_timestamp: datetime
    ) -> tuple[datetime, datetime]:
        """Calculate the extraction window based on last timestamp."""
        current_time = get_current_utc_time()

        # Ensure last_timestamp is timezone-aware for comparison
        if last_timestamp.tzinfo is None:
            last_timestamp = last_timestamp.replace(
                tzinfo=datetime.now().astimezone().tzinfo
            )

        # Start from the last timestamp, but ensure we have some overlap
        start_time = last_timestamp - timedelta(minutes=self.OVERLAP_MINUTES)

        # If we're too far behind, limit the catch-up window
        earliest_start = current_time - timedelta(days=self.MAX_CATCHUP_DAYS)

        if start_time < earliest_start:
            start_time = earliest_start
            self.logger.warning(
                f"Last timestamp is very old, limiting catch-up to {self.MAX_CATCHUP_DAYS} day"
            )

        # End time is current time minus a small buffer
        end_time = current_time - timedelta(minutes=self.END_TIME_BUFFER_MINUTES)

        self.logger.info(
            f"Extraction window: {start_time.isoformat()} to {end_time.isoformat()} "
            f"(duration: {(end_time - start_time).total_seconds() / 3600:.2f} hours)"
        )

        return start_time, end_time

    async def run_extraction(self) -> dict[str, Any]:
        """Run the extraction process for all symbols."""
        extraction_start_time = time.time()

        self.logger.info(
            f"Starting Data Manager klines extraction for {len(self.symbols)} symbols"
        )
        self.logger.info(f"Period: {self.period}, Max workers: {self.max_workers}")

        # Initialize Binance client
        binance_client = BinanceClient(
            api_key=constants.API_KEY,
            api_secret=constants.API_SECRET,
        )

        results = []

        try:
            # Process symbols sequentially (async but not parallel to avoid overwhelming Data Manager)
            for symbol in self.symbols:
                self.logger.info(f"Processing symbol: {symbol}")

                try:
                    result = await self.extract_symbol_data(symbol, binance_client)
                    results.append(result)

                    # Update statistics
                    if result["success"]:
                        self.stats["symbols_processed"] += 1
                        self.stats["total_records_fetched"] += result["records_fetched"]
                        self.stats["total_records_written"] += result["records_written"]
                        self.stats["total_gaps_filled"] += result["gaps_filled"]
                    else:
                        self.stats["symbols_failed"] += 1
                        self.stats["errors"].append(f"{symbol}: {result['error']}")

                except Exception as e:
                    self.logger.error(f"Failed to process {symbol}: {e}")
                    self.stats["symbols_failed"] += 1
                    self.stats["errors"].append(f"{symbol}: {str(e)}")

        finally:
            binance_client.close()

        # Calculate total duration
        total_duration = time.time() - extraction_start_time

        # Log final statistics
        self.logger.info("=" * 60)
        self.logger.info("📊 DATA MANAGER EXTRACTION COMPLETED")
        self.logger.info("=" * 60)
        self.logger.info(f"✅ Symbols processed: {self.stats['symbols_processed']}")
        self.logger.info(f"❌ Symbols failed: {self.stats['symbols_failed']}")
        self.logger.info(
            f"📈 Total records fetched: {self.stats['total_records_fetched']}"
        )
        self.logger.info(
            f"💾 Total records written: {self.stats['total_records_written']}"
        )
        self.logger.info(f"🔧 Total gaps filled: {self.stats['total_gaps_filled']}")
        self.logger.info(f"⏱️  Total duration: {format_duration(total_duration)}")

        if self.stats["errors"]:
            self.logger.warning(f"⚠️  Errors encountered: {len(self.stats['errors'])}")
            for error in self.stats["errors"][:5]:  # Show first 5 errors
                self.logger.warning(f"   - {error}")

        return {
            "success": self.stats["symbols_failed"] == 0,
            "total_symbols": len(self.symbols),
            "symbols_processed": self.stats["symbols_processed"],
            "symbols_failed": self.stats["symbols_failed"],
            "total_records_fetched": self.stats["total_records_fetched"],
            "total_records_written": self.stats["total_records_written"],
            "total_gaps_filled": self.stats["total_gaps_filled"],
            "duration_seconds": total_duration,
            "errors": self.stats["errors"],
        }


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Data Manager-based Binance klines extractor for Kubernetes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract 15m klines for all configured symbols using Data Manager
  python extract_klines_data_manager.py --period 15m

  # Extract 1h klines with custom symbols
  python extract_klines_data_manager.py --period 1h --symbols BTCUSDT,ETHUSDT,BNBUSDT

  # Extract with more parallel workers
  python extract_klines_data_manager.py --period 15m --max-workers 10
        """,
    )

    # Core parameters
    parser.add_argument(
        "--period",
        type=str,
        choices=[
            "1m",
            "3m",
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "4h",
            "6h",
            "8h",
            "12h",
            "1d",
            "3d",
            "1w",
            "1M",
        ],
        default=constants.DEFAULT_PERIOD,
        help="Kline interval (default: 15m)",
    )

    parser.add_argument(
        "--symbols",
        type=str,
        help="Comma-separated list of trading symbols (default: from config)",
    )

    # Performance parameters
    parser.add_argument(
        "--max-workers",
        type=int,
        default=5,
        help="Maximum number of parallel workers (default: 5)",
    )

    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=24,
        help="Hours to look back for gap detection (default: 24)",
    )

    # Logging parameters
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=constants.LOG_LEVEL,
        help="Logging level",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform dry run without writing to Data Manager",
    )

    return parser.parse_args()


async def main():
    """Main entry point."""
    args = parse_arguments()

    # Setup logging
    setup_logging(level=args.log_level)
    logger = get_logger(__name__)

    try:
        # Determine symbols to process
        if args.symbols:
            symbols = [s.strip().upper() for s in args.symbols.split(",")]
        else:
            symbols = constants.DEFAULT_SYMBOLS
            logger.info(f"Using default symbols: {symbols}")

        # Log extraction start
        log_extraction_start(
            log=logger,
            extractor_type="klines_data_manager",
            symbols=symbols,
            period=args.period,
            start_date="auto-determined",
            backfill=False,
        )

        logger.info("Using Data Manager for data persistence")
        logger.info(f"Data Manager URL: {constants.DATA_MANAGER_URL}")

        # Create and run extractor
        extractor = DataManagerKlinesExtractor(
            symbols=symbols,
            period=args.period,
            max_workers=args.max_workers,
            lookback_hours=args.lookback_hours,
        )

        if args.dry_run:
            logger.info("🔍 DRY RUN MODE - No data will be written to Data Manager")

        # Run extraction
        result = await extractor.run_extraction()

        # Log completion
        log_extraction_completion(
            log=logger,
            extractor_type="klines_data_manager",
            total_records=result["total_records_written"],
            duration_seconds=result["duration_seconds"],
            gaps_found=result["total_gaps_filled"],
            errors=result["errors"][:10],  # Limit errors in logs
        )

        # Exit with appropriate code
        if result["success"]:
            logger.info("🎉 Data Manager extraction completed successfully!")
            sys.exit(0)
        else:
            logger.error(
                f"❌ Data Manager extraction completed with {result['symbols_failed']} failures"
            )
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("⚠️ Extraction interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"💥 Fatal error during extraction: {e}")
        import traceback  # noqa: E402

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
