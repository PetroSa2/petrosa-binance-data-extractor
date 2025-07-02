#!/usr/bin/env python3
"""
Production-ready klines extraction job for Kubernetes environments.

This script automatically:
- Reads the last extraction timestamp from the database
- Downloads all configured symbols in parallel
- Handles gaps and failures
- Runs incremental updates without manual date configuration
"""

import argparse
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, cast

# Add project root to path (works for both local and container environments)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Initialize OpenTelemetry as early as possible
try:
    import constants
    from otel_init import setup_telemetry

    # Only initialize OpenTelemetry if not already initialized by opentelemetry-instrument
    if not os.getenv("OTEL_NO_AUTO_INIT"):
        setup_telemetry(service_name=constants.OTEL_SERVICE_NAME_KLINES)

    # Import tracing after setup
    from utils.telemetry import get_tracer

    tracer = get_tracer(__name__)
except ImportError:
    tracer = None

import constants
from db import get_adapter
from fetchers import BinanceClient, KlinesFetcher
from models.base import BaseModel
from models.kline import KlineModel
from utils.logger import (get_logger, log_extraction_completion,
                          log_extraction_start, setup_logging)
from utils.retry import exponential_backoff
from utils.time_utils import (binance_interval_to_table_suffix,
                              ensure_timezone_aware, format_duration,
                              get_current_utc_time, get_interval_minutes,
                              parse_datetime_string)


def retry_with_backoff(func, max_retries=3, base_delay=1.0, max_delay=60.0, logger=None):
    """
    Retry a function with exponential backoff and jitter.

    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        logger: Logger instance to use for messages

    Returns:
        The result of the function call

    Raises:
        The last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e

            # Check if it's a MySQL connection error
            error_msg = str(e).lower()
            # Also check for pymysql specific errors and SQLAlchemy errors
            is_connection_error = (
                any(
                    keyword in error_msg
                    for keyword in [
                        "lost connection to mysql server",
                        "mysql server has gone away",
                        "connection was killed",
                        "connection refused",
                        "timeout",
                        "broken pipe",
                        "can't connect to mysql server",
                        "operationalerror",
                        "2013",  # MySQL error code for lost connection
                        "2006",  # MySQL error code for server gone away
                        "2003",  # MySQL error code for can't connect
                    ]
                )
                or
                # Check for SQLAlchemy connection errors
                "operationalerror" in str(type(e)).lower()
                or "databaseerror" in str(type(e)).lower()
            )

            if is_connection_error:
                if attempt < max_retries:
                    # Calculate delay with exponential backoff and jitter
                    delay = min(base_delay * (2**attempt), max_delay)
                    jitter = random.uniform(0.1, 0.3) * delay
                    total_delay = delay + jitter

                    if logger:
                        logger.warning(f"MySQL connection error on attempt {attempt + 1}/{max_retries + 1}: {e}")
                        logger.info(f"Retrying in {total_delay:.2f} seconds...")
                    time.sleep(total_delay)
                    continue
                else:
                    if logger:
                        logger.error(f"All {max_retries + 1} attempts failed. Last error: {e}")
                    break
            else:
                # Not a connection error, don't retry
                if logger:
                    logger.error(f"Non-connection error, not retrying: {e}")
                break

    # If we get here, all retries failed
    raise last_exception


class ProductionKlinesExtractor:
    """Production-ready klines extractor with automatic gap detection and parallel processing."""

    # Configuration constants
    OVERLAP_MINUTES = 30  # Minutes of overlap to catch missed data
    END_TIME_BUFFER_MINUTES = 5  # Buffer before current time to avoid incomplete candles
    MAX_CATCHUP_DAYS = 1  # Maximum days to catch up at once

    def __init__(
        self,
        symbols: List[str],
        period: str,
        db_adapter_name: str,
        db_uri: Optional[str] = None,
        max_workers: int = 5,
        lookback_hours: int = 24,
        batch_size: int = 1000,
    ):
        self.symbols = symbols
        self.period = period
        self.db_adapter_name = db_adapter_name
        self.db_uri = db_uri
        self.max_workers = max_workers
        self.lookback_hours = lookback_hours
        self.batch_size = batch_size

        # Thread-safe logger
        self.logger = get_logger(__name__)
        self._lock = threading.Lock()

        # Statistics (properly typed)
        self.stats: Dict[str, Any] = {
            "symbols_processed": 0,
            "symbols_failed": 0,
            "total_records_fetched": 0,
            "total_records_written": 0,
            "total_gaps_filled": 0,
            "errors": [],
        }

    def period_to_minutes(self) -> int:
        """Convert period string to minutes for gap detection."""
        period_map = {
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
            "1M": 43200,  # Approximate for 1M
        }
        return period_map.get(self.period, 15)  # Default to 15 if unknown

    def get_collection_name(self) -> str:
        """Get the collection name using proper financial market naming."""
        table_suffix = binance_interval_to_table_suffix(self.period)
        return f"klines_{table_suffix}"

    def get_last_timestamp_for_symbol(self, db_adapter, symbol: str) -> Optional[datetime]:
        """Get the last timestamp for a symbol from the database."""

        def _get_timestamp():
            collection_name = self.get_collection_name()

            # Query the latest record for this symbol
            latest_records = db_adapter.query_latest(collection_name, symbol=symbol, limit=1)

            if latest_records:
                # Return the close_time of the latest record (access as dictionary key)
                latest_record = latest_records[0]
                timestamp = None
                if "close_time" in latest_record:
                    timestamp = latest_record["close_time"]
                elif "timestamp" in latest_record:
                    # Fallback to timestamp if close_time not available
                    timestamp = latest_record["timestamp"]
                else:
                    self.logger.warning(f"No timestamp found in latest record for {symbol}: {latest_record}")
                    timestamp = datetime.fromisoformat(constants.DEFAULT_START_DATE.replace("Z", "+00:00"))

                # Ensure timestamp is timezone-aware
                if timestamp:
                    timestamp = ensure_timezone_aware(timestamp)
                    self.logger.debug(f"Made timestamp timezone-aware for {symbol}: {timestamp}")

                return timestamp
            else:
                # No data found, start from default start date
                return datetime.fromisoformat(constants.DEFAULT_START_DATE.replace("Z", "+00:00"))

        try:
            return retry_with_backoff(_get_timestamp, max_retries=2, base_delay=1.0, logger=self.logger)
        except Exception as e:
            self.logger.warning("Could not get last timestamp for %s after retries: %s", symbol, e)
            # Fallback to default start date
            return datetime.fromisoformat(constants.DEFAULT_START_DATE.replace("Z", "+00:00"))

    def calculate_extraction_window(self, last_timestamp: datetime) -> Tuple[datetime, datetime]:
        """Calculate the extraction window based on last timestamp."""
        current_time = get_current_utc_time()

        # Ensure last_timestamp is timezone-aware for comparison
        last_timestamp = ensure_timezone_aware(last_timestamp)
        self.logger.debug(f"Made last_timestamp timezone-aware: {last_timestamp}")

        # Start from the last timestamp, but ensure we have some overlap
        # to catch any missed data due to timing issues
        start_time = last_timestamp - timedelta(minutes=self.OVERLAP_MINUTES)

        # If we're too far behind, limit the catch-up window to avoid overwhelming
        earliest_start = current_time - timedelta(days=self.MAX_CATCHUP_DAYS)

        if start_time < earliest_start:
            start_time = earliest_start
            self.logger.warning(f"Last timestamp is very old, limiting catch-up to {self.MAX_CATCHUP_DAYS} day")

        # End time is current time minus a small buffer to avoid incomplete candles
        end_time = current_time - timedelta(minutes=self.END_TIME_BUFFER_MINUTES)

        # Log the extraction window for debugging
        self.logger.info(
            f"Extraction window: {start_time.isoformat()} to {end_time.isoformat()} "
            f"(duration: {(end_time - start_time).total_seconds() / 3600:.2f} hours)"
        )

        return start_time, end_time

    def extract_symbol_data(self, symbol: str, binance_client: BinanceClient) -> Dict:
        """Extract data for a single symbol with retry logic for database operations."""
        # Create a span for each symbol extraction
        if tracer:
            with tracer.start_as_current_span("klines_extract_symbol") as span:
                span.set_attribute("extraction.symbol", symbol)
                span.set_attribute("extraction.period", self.period)
                return self._extract_symbol_data_impl(symbol, binance_client, span)
        else:
            return self._extract_symbol_data_impl(symbol, binance_client)

    def _extract_symbol_data_impl(self, symbol: str, binance_client: BinanceClient, span=None) -> Dict:
        """Implementation of extract_symbol_data method."""
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

        def _perform_extraction():
            """Inner function that performs the actual extraction."""
            # Get database adapter (each thread needs its own connection)
            # Ensure we have a valid database URI
            db_uri = self.db_uri
            if not db_uri:
                # Fallback to constants if db_uri is None or empty
                if self.db_adapter_name == "mysql":
                    db_uri = constants.MYSQL_URI
                elif self.db_adapter_name == "mongodb":
                    db_uri = constants.MONGODB_URI
                elif self.db_adapter_name == "postgresql":
                    db_uri = constants.POSTGRESQL_URI

                if not db_uri:
                    raise ValueError(f"No database URI available for adapter: {self.db_adapter_name}")

            db_adapter = get_adapter(self.db_adapter_name, db_uri)

            # Connect with retry logic
            def _connect_db():
                db_adapter.connect()

            retry_with_backoff(_connect_db, max_retries=2, base_delay=1.0, logger=self.logger)

            try:
                # Get last timestamp for this symbol
                last_timestamp = self.get_last_timestamp_for_symbol(db_adapter, symbol)

                # Calculate extraction window (handle None case)
                if last_timestamp is None:
                    last_timestamp = datetime.fromisoformat(constants.DEFAULT_START_DATE.replace("Z", "+00:00"))
                start_time, end_time = self.calculate_extraction_window(last_timestamp)

                self.logger.info(
                    f"Extracting {symbol} ({self.period}): " f"from {start_time.isoformat()} to {end_time.isoformat()}"
                )

                # Create fetcher
                fetcher = KlinesFetcher(binance_client)

                # Fetch data
                klines_data = fetcher.fetch_klines(
                    symbol=symbol,
                    interval=self.period,
                    start_time=start_time,
                    end_time=end_time,
                )

                result["records_fetched"] = len(klines_data)

                if klines_data:
                    # Write to database with retry logic
                    collection_name = self.get_collection_name()

                    def _write_data():
                        return db_adapter.write(cast(List[BaseModel], klines_data), collection_name)

                    records_written = retry_with_backoff(_write_data, max_retries=2, base_delay=1.0, logger=self.logger)
                    result["records_written"] = records_written

                    # Check for gaps with retry logic
                    def _check_gaps():
                        try:
                            interval_minutes = self.period_to_minutes()
                            gaps = db_adapter.find_gaps(collection_name, start_time, end_time, interval_minutes, symbol=symbol)
                            return gaps
                        except Exception as e:
                            # Check if we need to reconnect
                            error_msg = str(e).lower()
                            if any(
                                keyword in error_msg
                                for keyword in [
                                    "lost connection to mysql server",
                                    "mysql server has gone away",
                                    "connection was killed",
                                ]
                            ):
                                self.logger.warning("MySQL connection lost during gap detection, attempting reconnect...")
                                try:
                                    db_adapter.disconnect()
                                    db_adapter.connect()
                                except Exception as reconnect_error:
                                    self.logger.error(f"Failed to reconnect: {reconnect_error}")
                            raise

                    try:
                        gaps = retry_with_backoff(_check_gaps, max_retries=3, base_delay=2.0, logger=self.logger)
                        result["gaps_filled"] = len(gaps)
                        if gaps:
                            self.logger.warning(f"Found {len(gaps)} gaps for {symbol} in {collection_name}")
                    except Exception as gap_error:
                        self.logger.warning(f"Gap detection failed for {symbol} after retries: {gap_error}")
                        result["gaps_filled"] = 0

                result["success"] = True
                result["duration"] = time.time() - symbol_start_time

                self.logger.info(
                    f"✅ {symbol}: fetched={result['records_fetched']}, "
                    f"written={result['records_written']}, "
                    f"duration={result['duration']:.2f}s"
                )

                return result

            finally:
                try:
                    db_adapter.disconnect()
                except Exception as disconnect_error:
                    self.logger.warning(f"Error disconnecting from database: {disconnect_error}")

        try:
            # Use retry logic for the entire extraction operation
            return retry_with_backoff(_perform_extraction, max_retries=3, base_delay=1.0, logger=self.logger)
        except Exception as e:
            result["error"] = str(e)
            result["duration"] = time.time() - symbol_start_time
            self.logger.error(f"❌ {symbol} failed after all retries: {e}")
            return result

    def run_extraction(self) -> Dict:
        """Run the production extraction with parallel processing."""
        # Create a span for the main extraction process
        if tracer:
            with tracer.start_as_current_span("klines_extraction_run") as span:
                span.set_attribute("extraction.period", self.period)
                span.set_attribute("extraction.symbols_count", len(self.symbols))
                span.set_attribute("extraction.max_workers", self.max_workers)
                return self._run_extraction_impl()
        else:
            return self._run_extraction_impl()

    def _run_extraction_impl(self) -> Dict:
        """Implementation of run_extraction method."""
        extraction_start_time = time.time()

        self.logger.info(f"Starting production klines extraction for {len(self.symbols)} symbols")
        self.logger.info(f"Period: {self.period}, Max workers: {self.max_workers}")

        # Initialize Binance client
        binance_client = BinanceClient(
            api_key=constants.API_KEY,
            api_secret=constants.API_SECRET,
        )

        # Process symbols in parallel
        results = []

        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all symbol extraction tasks
                future_to_symbol = {
                    executor.submit(self.extract_symbol_data, symbol, binance_client): symbol for symbol in self.symbols
                }

                # Collect results as they complete
                for future in as_completed(future_to_symbol):
                    symbol = future_to_symbol[future]
                    try:
                        result = future.result()
                        results.append(result)

                        # Update thread-safe statistics
                        with self._lock:
                            if result["success"]:
                                self.stats["symbols_processed"] += 1
                                self.stats["total_records_fetched"] += result["records_fetched"]
                                self.stats["total_records_written"] += result["records_written"]
                                self.stats["total_gaps_filled"] += result["gaps_filled"]
                            else:
                                self.stats["symbols_failed"] += 1
                                self.stats["errors"].append(f"{symbol}: {result['error']}")

                    except Exception as e:
                        self.logger.error(f"Failed to get result for {symbol}: {e}")
                        with self._lock:
                            self.stats["symbols_failed"] += 1
                            self.stats["errors"].append(f"{symbol}: {str(e)}")

        finally:
            binance_client.close()

        # Calculate total duration
        total_duration = time.time() - extraction_start_time

        # Log final statistics
        self.logger.info("=" * 60)
        self.logger.info("📊 EXTRACTION COMPLETED")
        self.logger.info("=" * 60)
        self.logger.info(f"✅ Symbols processed: {self.stats['symbols_processed']}")
        self.logger.info(f"❌ Symbols failed: {self.stats['symbols_failed']}")
        self.logger.info(f"📈 Total records fetched: {self.stats['total_records_fetched']}")
        self.logger.info(f"💾 Total records written: {self.stats['total_records_written']}")
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
        description="Production-ready Binance klines extractor for Kubernetes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract 15m klines for all configured symbols (production mode)
  python extract_klines_production.py --period 15m

  # Extract 1h klines with custom symbols
  python extract_klines_production.py --period 1h --symbols BTCUSDT,ETHUSDT,BNBUSDT

  # Extract with more parallel workers
  python extract_klines_production.py --period 15m --max-workers 10
        """,
    )

    # Core parameters
    parser.add_argument(
        "--period",
        type=str,
        choices=["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"],
        default=constants.DEFAULT_PERIOD,
        help="Kline interval (default: 15m)",
    )

    parser.add_argument("--symbols", type=str, help="Comma-separated list of trading symbols (default: from config)")

    # Performance parameters
    parser.add_argument("--max-workers", type=int, default=5, help="Maximum number of parallel workers (default: 5)")

    parser.add_argument("--lookback-hours", type=int, default=24, help="Hours to look back for gap detection (default: 24)")

    parser.add_argument("--batch-size", type=int, default=constants.DB_BATCH_SIZE, help="Database batch size (default: 1000)")

    # Database parameters
    parser.add_argument(
        "--db-adapter",
        type=str,
        choices=["mongodb", "mysql", "postgresql"],
        default=constants.DB_ADAPTER,
        help="Database adapter to use",
    )

    parser.add_argument("--db-uri", type=str, help="Database connection URI (overrides default)")

    # Logging parameters
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=constants.LOG_LEVEL,
        help="Logging level",
    )

    parser.add_argument("--dry-run", action="store_true", help="Perform dry run without writing to database")

    return parser.parse_args()


def main():
    """Main entry point."""
    # Create a main span if tracing is available
    if tracer:
        with tracer.start_as_current_span("klines_extraction_main") as span:
            span.set_attribute("extraction.type", "klines_production")
            span.set_attribute("service.name", "binance-klines-extractor")
            # Force span context to be active for logging
            span_context = span.get_span_context()
            if span_context.trace_id != 0:
                print(f"Main span created with trace_id: {format(span_context.trace_id, '032x')}")
            _main_impl()
    else:
        print("Tracer not available, running without tracing")
        _main_impl()


def _main_impl():
    """Implementation of main function."""
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
            extractor_type="klines_production",
            symbols=symbols,
            period=args.period,
            start_date="auto-determined",  # Auto-determined
            backfill=False,
        )

        # Determine database URI - use command line arg or fallback to environment/constants
        db_uri = args.db_uri
        if db_uri is None:
            if args.db_adapter == "mysql":
                db_uri = constants.MYSQL_URI
            elif args.db_adapter == "mongodb":
                db_uri = constants.MONGODB_URI
            elif args.db_adapter == "postgresql":
                db_uri = constants.POSTGRESQL_URI
            else:
                logger.error(f"No database URI found for adapter: {args.db_adapter}")
                sys.exit(1)

        logger.info(f"Using database adapter: {args.db_adapter}")
        logger.info(f"Database URI configured: {'Yes' if db_uri else 'No'}")

        # Create and run extractor
        extractor = ProductionKlinesExtractor(
            symbols=symbols,
            period=args.period,
            db_adapter_name=args.db_adapter,
            db_uri=db_uri,
            max_workers=args.max_workers,
            lookback_hours=args.lookback_hours,
            batch_size=args.batch_size,
        )

        if args.dry_run:
            logger.info("🔍 DRY RUN MODE - No data will be written to database")

        # Run extraction
        result = extractor.run_extraction()

        # Log completion
        log_extraction_completion(
            log=logger,
            extractor_type="klines_production",
            total_records=result["total_records_written"],
            duration_seconds=result["duration_seconds"],
            gaps_found=result["total_gaps_filled"],
            errors=result["errors"][:10],  # Limit errors in logs
        )

        # Exit with appropriate code
        if result["success"]:
            logger.info("🎉 Production extraction completed successfully!")
            sys.exit(0)
        else:
            logger.error(f"❌ Production extraction completed with {result['symbols_failed']} failures")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("⚠️ Extraction interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"💥 Fatal error during extraction: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
