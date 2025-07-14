#!/usr/bin/env python3
"""
Gap filler job to detect and fill missing klines data.
"""

import argparse
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, cast

# Add project root to path (works for both local and container environments)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import constants

# Initialize OpenTelemetry as early as possible
try:
    from utils.telemetry import initialize_telemetry
    if not os.getenv("OTEL_NO_AUTO_INIT"):
        service_name = os.getenv("OTEL_SERVICE_NAME_KLINES", constants.OTEL_SERVICE_NAME_KLINES)
        initialize_telemetry(service_name=service_name, environment="production")
except ImportError:
    pass

from db import get_adapter
from fetchers import BinanceClient, KlinesFetcher
from models.base import BaseModel
from utils.logger import (
    get_logger,
    log_extraction_completion,
    log_extraction_start,
    setup_logging,
)
from utils.messaging import publish_extraction_completion_sync
from utils.telemetry import get_tracer
from utils.time_utils import (
    binance_interval_to_table_suffix,
    format_duration,
    get_current_utc_time,
)


def retry_with_backoff(
    func, max_retries=5, base_delay=1.0, max_delay=300.0, logger=None, retry_on_all_errors=False, operation_name="operation"
):
    """
    Retry a function with exponential backoff and jitter.

    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts (default: 5)
        base_delay: Base delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 300.0 = 5 minutes)
        logger: Logger instance to use for messages
        retry_on_all_errors: Whether to retry on all errors or just connection errors
        operation_name: Name of the operation for logging
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e
            error_msg = str(e).lower()

            # Check for various types of retryable errors
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
                        "databaseerror",
                        "2013",
                        "2006",
                        "2003",  # MySQL error codes
                        "connection pool exhausted",
                        "connection reset by peer",
                        "network is unreachable",
                        "no route to host",
                        "host is unreachable",
                    ]
                )
                or "operationalerror" in str(type(e)).lower()
                or "databaseerror" in str(type(e)).lower()
            )

            # Check for API rate limiting and temporary errors
            is_api_error = any(
                keyword in error_msg
                for keyword in [
                    "rate limit",
                    "too many requests",
                    "429",
                    "503",
                    "502",
                    "504",
                    "service unavailable",
                    "bad gateway",
                    "gateway timeout",
                    "internal server error",
                    "temporary failure",
                    "temporary error",
                ]
            )

            # Check for temporary network issues
            is_network_error = any(
                keyword in error_msg
                for keyword in [
                    "dns resolution failed",
                    "name resolution failed",
                    "ssl certificate",
                    "certificate verify failed",
                    "tls handshake",
                    "connection aborted",
                    "connection reset",
                    "socket timeout",
                    "read timeout",
                    "write timeout",
                ]
            )

            should_retry = retry_on_all_errors or is_connection_error or is_api_error or is_network_error

            if should_retry and attempt < max_retries:
                # Exponential backoff with jitter
                delay = min(base_delay * (2**attempt), max_delay)
                jitter = random.uniform(0.1, 0.3) * delay
                total_delay = delay + jitter

                # Additional delay for API rate limiting
                if is_api_error:
                    api_delay = random.uniform(30.0, 60.0)  # 30-60 seconds for rate limits
                    total_delay += api_delay

                if logger:
                    error_type = (
                        "API rate limit"
                        if is_api_error
                        else "Connection" if is_connection_error else "Network" if is_network_error else "General"
                    )
                    logger.warning(f"{error_type} error on {operation_name} attempt {attempt + 1}/{max_retries + 1}: {e}")
                    logger.info(f"Retrying {operation_name} in {total_delay:.2f} seconds...")

                time.sleep(total_delay)
                continue
            else:
                if logger:
                    if not should_retry:
                        logger.error(f"Non-retryable error in {operation_name}: {e}")
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {operation_name}. Last error: {e}")
                break

    raise last_exception


class GapFillerExtractor:
    """Gap detection and filling extractor with weekly request splitting."""

    def __init__(
        self,
        symbols: List[str],
        period: str,
        db_adapter_name: str,
        db_uri: Optional[str] = None,
        max_workers: int = 3,
        batch_size: int = 1000,
        weekly_chunk_days: int = 7,
        max_gap_size_days: int = 365,
    ):
        self.symbols = symbols
        self.period = period
        self.db_adapter_name = db_adapter_name
        self.db_uri = db_uri
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.weekly_chunk_days = weekly_chunk_days
        self.max_gap_size_days = max_gap_size_days

        self.logger = get_logger(__name__)
        self._lock = threading.Lock()

        self.stats: Dict[str, Any] = {
            "symbols_processed": 0,
            "symbols_failed": 0,
            "total_gaps_found": 0,
            "total_gaps_filled": 0,
            "total_records_fetched": 0,
            "total_records_written": 0,
            "total_weekly_chunks_processed": 0,
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
            "1M": 43200,
        }
        return period_map.get(self.period, 15)

    def get_collection_name(self) -> str:
        """Get the collection name using proper financial market naming."""
        table_suffix = binance_interval_to_table_suffix(self.period)
        return f"klines_{table_suffix}"

    def get_start_date(self) -> datetime:
        """Get the start date from constants."""
        return datetime.fromisoformat(constants.DEFAULT_START_DATE.replace("Z", "+00:00"))

    def get_end_date(self) -> datetime:
        """Get the current time as end date."""
        return get_current_utc_time() - timedelta(minutes=5)

    def split_weekly_chunks(self, start_date: datetime, end_date: datetime) -> List[Tuple[datetime, datetime]]:
        """Split a date range into weekly chunks."""
        chunks = []
        current_start = start_date

        while current_start < end_date:
            current_end = min(current_start + timedelta(days=self.weekly_chunk_days), end_date)
            chunks.append((current_start, current_end))
            current_start = current_end

        return chunks

    def detect_gaps_for_symbol(self, symbol: str, db_adapter) -> List[Tuple[datetime, datetime]]:
        """Detect gaps for a single symbol."""

        def _detect_gaps():
            collection_name = self.get_collection_name()
            start_date = self.get_start_date()
            end_date = self.get_end_date()
            interval_minutes = self.period_to_minutes()

            self.logger.info(f"Detecting gaps for {symbol} from {start_date} to {end_date}")

            gaps = db_adapter.find_gaps(collection_name, start_date, end_date, interval_minutes, symbol=symbol)

            # Filter out gaps that are too large
            filtered_gaps = []
            for gap_start, gap_end in gaps:
                gap_duration = gap_end - gap_start
                if gap_duration <= timedelta(days=self.max_gap_size_days):
                    filtered_gaps.append((gap_start, gap_end))
                else:
                    self.logger.warning(
                        f"Skipping large gap for {symbol}: {gap_start} to {gap_end} " f"(duration: {gap_duration.days} days)"
                    )

            return filtered_gaps

        try:
            return retry_with_backoff(
                _detect_gaps,
                max_retries=5,
                base_delay=2.0,
                max_delay=120.0,
                logger=self.logger,
                operation_name=f"gap detection for {symbol}",
            )
        except Exception as e:
            self.logger.error(f"Failed to detect gaps for {symbol} after all retries: {e}")
            return []

    def fill_gap_chunk(
        self, symbol: str, gap_start: datetime, gap_end: datetime, binance_client: BinanceClient, db_adapter
    ) -> Dict:
        """Fill a single gap chunk with data."""
        chunk_start_time = time.time()
        result = {
            "symbol": symbol,
            "gap_start": gap_start,
            "gap_end": gap_end,
            "success": False,
            "records_fetched": 0,
            "records_written": 0,
            "error": None,
            "duration": 0,
        }

        def _fill_chunk():
            fetcher = KlinesFetcher(binance_client)

            # Retry the data fetching operation specifically
            def _fetch_data():
                return fetcher.fetch_klines(
                    symbol=symbol,
                    interval=self.period,
                    start_time=gap_start,
                    end_time=gap_end,
                )

            klines_data = retry_with_backoff(
                _fetch_data,
                max_retries=5,
                base_delay=2.0,
                max_delay=180.0,
                logger=self.logger,
                retry_on_all_errors=True,
                operation_name=f"data fetching for {symbol} gap",
            )

            result["records_fetched"] = len(klines_data)

            if klines_data:
                collection_name = self.get_collection_name()

                def _write_data():
                    return db_adapter.write(cast(List[BaseModel], klines_data), collection_name)

                records_written = retry_with_backoff(
                    _write_data,
                    max_retries=5,
                    base_delay=2.0,
                    max_delay=180.0,
                    logger=self.logger,
                    operation_name=f"database write for {symbol} gap",
                )
                result["records_written"] = records_written

            result["success"] = True
            result["duration"] = time.time() - chunk_start_time

            self.logger.info(
                f"✅ Filled gap for {symbol}: {gap_start.isoformat()} to {gap_end.isoformat()}, "
                f"fetched={result['records_fetched']}, written={result['records_written']}, "
                f"duration={result['duration']:.2f}s"
            )

            return result

        try:
            return retry_with_backoff(
                _fill_chunk,
                max_retries=7,
                base_delay=3.0,
                max_delay=300.0,
                logger=self.logger,
                retry_on_all_errors=True,  # Retry on all errors for data fetching
                operation_name=f"gap filling for {symbol}",
            )
        except Exception as e:
            result["error"] = str(e)
            result["duration"] = time.time() - chunk_start_time
            self.logger.error(f"❌ Failed to fill gap for {symbol}: {e}")
            return result

    def process_symbol_gaps(self, symbol: str, binance_client: BinanceClient) -> Dict:
        """Process all gaps for a single symbol."""
        symbol_start_time = time.time()
        result = {
            "symbol": symbol,
            "success": False,
            "gaps_found": 0,
            "gaps_filled": 0,
            "total_records_fetched": 0,
            "total_records_written": 0,
            "weekly_chunks_processed": 0,
            "error": None,
            "duration": 0,
        }

        def _process_symbol():
            db_uri = self.db_uri
            if not db_uri:
                if self.db_adapter_name == "mysql":
                    db_uri = constants.MYSQL_URI
                elif self.db_adapter_name == "mongodb":
                    db_uri = constants.MONGODB_URI
                elif self.db_adapter_name == "postgresql":
                    db_uri = constants.POSTGRESQL_URI

                if not db_uri:
                    raise ValueError(f"No database URI available for adapter: {self.db_adapter_name}")

            db_adapter = get_adapter(self.db_adapter_name, db_uri)

            def _connect_db():
                db_adapter.connect()

            retry_with_backoff(
                _connect_db,
                max_retries=5,
                base_delay=2.0,
                max_delay=120.0,
                logger=self.logger,
                operation_name=f"database connection for {symbol}",
            )

            try:
                # Retry gap detection with more specific error handling
                gaps = self.detect_gaps_for_symbol(symbol, db_adapter)
                result["gaps_found"] = len(gaps)

                if not gaps:
                    self.logger.info(f"No gaps found for {symbol}")
                    result["success"] = True
                    return result

                self.logger.info(f"Found {len(gaps)} gaps for {symbol}")

                # Add additional validation for gaps
                if len(gaps) > 100:  # Sanity check for too many gaps
                    self.logger.warning(f"Found {len(gaps)} gaps for {symbol}, this seems excessive. Limiting to first 50.")
                    gaps = gaps[:50]

                for gap_start, gap_end in gaps:
                    weekly_chunks = self.split_weekly_chunks(gap_start, gap_end)

                    for chunk_start, chunk_end in weekly_chunks:
                        if result["weekly_chunks_processed"] > 0:
                            delay = random.uniform(2.0, 5.0)
                            time.sleep(delay)

                        try:
                            chunk_result = self.fill_gap_chunk(symbol, chunk_start, chunk_end, binance_client, db_adapter)

                            result["weekly_chunks_processed"] += 1
                            result["total_records_fetched"] += chunk_result["records_fetched"]
                            result["total_records_written"] += chunk_result["records_written"]

                            if chunk_result["success"]:
                                result["gaps_filled"] += 1
                            else:
                                self.logger.warning(
                                    f"Failed to fill chunk for {symbol}: {chunk_result.get('error', 'Unknown error')}"
                                )

                        except Exception as chunk_error:
                            self.logger.error(f"Exception during chunk processing for {symbol}: {chunk_error}")
                            result["weekly_chunks_processed"] += 1
                            # Continue with next chunk instead of failing entire symbol

                        time.sleep(random.uniform(1.0, 3.0))

                result["success"] = True
                result["duration"] = time.time() - symbol_start_time

                self.logger.info(
                    f"✅ Completed {symbol}: gaps_found={result['gaps_found']}, "
                    f"gaps_filled={result['gaps_filled']}, "
                    f"records_fetched={result['total_records_fetched']}, "
                    f"duration={result['duration']:.2f}s"
                )

                # Send NATS message for symbol completion
                if constants.NATS_ENABLED:
                    try:
                        publish_extraction_completion_sync(
                            symbol=symbol,
                            period=self.period,
                            records_fetched=result["total_records_fetched"],
                            records_written=result["total_records_written"],
                            success=result["success"],
                            duration_seconds=result["duration"],
                            errors=[result["error"]] if result["error"] else None,
                            gaps_found=result["gaps_found"],
                            gaps_filled=result["gaps_filled"],
                            extraction_type="klines_gap_filling",
                        )
                    except Exception as e:
                        self.logger.warning(f"Failed to send NATS message for {symbol}: {e}")

                return result

            finally:
                try:
                    db_adapter.disconnect()
                except Exception as disconnect_error:
                    self.logger.warning(f"Error disconnecting from database: {disconnect_error}")

        try:
            return retry_with_backoff(
                _process_symbol,
                max_retries=5,
                base_delay=3.0,
                max_delay=240.0,
                logger=self.logger,
                retry_on_all_errors=True,  # Retry on all errors for symbol processing
                operation_name=f"symbol processing for {symbol}",
            )
        except Exception as e:
            result["error"] = str(e)
            result["duration"] = time.time() - symbol_start_time
            self.logger.error(f"❌ {symbol} failed after all retries: {e}")
            return result

    def run_gap_filling(self) -> Dict:
        """Run the gap detection and filling process."""
        try:
            current_tracer = get_tracer("jobs.extract_klines_gap_filler")
            if current_tracer:
                with current_tracer.start_as_current_span("klines_gap_filling_run") as span:
                    span.set_attribute("extraction.period", self.period)
                    span.set_attribute("extraction.symbols_count", len(self.symbols))
                    span.set_attribute("extraction.max_workers", self.max_workers)
                    return self._run_gap_filling_impl()
            else:
                return self._run_gap_filling_impl()
        except Exception as e:
            self.logger.warning(f"Tracing setup failed: {e}, running without tracing")
            return self._run_gap_filling_impl()

    def _run_gap_filling_impl(self) -> Dict:
        """Implementation of run_gap_filling method."""
        extraction_start_time = time.time()

        self.logger.info(f"Starting gap detection and filling for {len(self.symbols)} symbols")
        self.logger.info(f"Period: {self.period}, Max workers: {self.max_workers}")
        self.logger.info(f"Weekly chunk days: {self.weekly_chunk_days}, Max gap size: {self.max_gap_size_days} days")

        # Initialize Binance client with retry logic
        def _init_binance_client():
            client = BinanceClient(
                api_key=constants.API_KEY,
                api_secret=constants.API_SECRET,
            )
            # Test connectivity
            if not client.ping():
                raise Exception("Failed to connect to Binance API")
            return client

        try:
            binance_client = retry_with_backoff(
                _init_binance_client,
                max_retries=5,
                base_delay=5.0,
                max_delay=120.0,
                logger=self.logger,
                operation_name="Binance client initialization",
            )
            self.logger.info("✅ Successfully connected to Binance API")
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Binance client after all retries: {e}")
            return {
                "success": False,
                "total_symbols": len(self.symbols),
                "symbols_processed": 0,
                "symbols_failed": len(self.symbols),
                "total_gaps_found": 0,
                "total_gaps_filled": 0,
                "total_records_fetched": 0,
                "total_records_written": 0,
                "total_weekly_chunks_processed": 0,
                "duration_seconds": time.time() - extraction_start_time,
                "errors": [f"Binance client initialization failed: {e}"],
            }

        results = []

        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_symbol = {
                    executor.submit(self.process_symbol_gaps, symbol, binance_client): symbol for symbol in self.symbols
                }

                for future in as_completed(future_to_symbol):
                    symbol = future_to_symbol[future]
                    try:
                        result = future.result()
                        results.append(result)

                        with self._lock:
                            if result["success"]:
                                self.stats["symbols_processed"] += 1
                                self.stats["total_gaps_found"] += result["gaps_found"]
                                self.stats["total_gaps_filled"] += result["gaps_filled"]
                                self.stats["total_records_fetched"] += result["total_records_fetched"]
                                self.stats["total_records_written"] += result["total_records_written"]
                                self.stats["total_weekly_chunks_processed"] += result["weekly_chunks_processed"]
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

        total_duration = time.time() - extraction_start_time

        self.logger.info("=" * 60)
        self.logger.info("🔧 GAP FILLING COMPLETED")
        self.logger.info("=" * 60)
        self.logger.info(f"✅ Symbols processed: {self.stats['symbols_processed']}")
        self.logger.info(f"❌ Symbols failed: {self.stats['symbols_failed']}")
        self.logger.info(f"🔍 Total gaps found: {self.stats['total_gaps_found']}")
        self.logger.info(f"🔧 Total gaps filled: {self.stats['total_gaps_filled']}")
        self.logger.info(f"📈 Total records fetched: {self.stats['total_records_fetched']}")
        self.logger.info(f"💾 Total records written: {self.stats['total_records_written']}")
        self.logger.info(f"📅 Weekly chunks processed: {self.stats['total_weekly_chunks_processed']}")
        self.logger.info(f"⏱️  Total duration: {format_duration(total_duration)}")

        if self.stats["errors"]:
            self.logger.warning(f"⚠️  Errors encountered: {len(self.stats['errors'])}")
            for error in self.stats["errors"][:5]:
                self.logger.warning(f"   - {error}")

        return {
            "success": self.stats["symbols_failed"] == 0,
            "total_symbols": len(self.symbols),
            "symbols_processed": self.stats["symbols_processed"],
            "symbols_failed": self.stats["symbols_failed"],
            "total_gaps_found": self.stats["total_gaps_found"],
            "total_gaps_filled": self.stats["total_gaps_filled"],
            "total_records_fetched": self.stats["total_records_fetched"],
            "total_records_written": self.stats["total_records_written"],
            "total_weekly_chunks_processed": self.stats["total_weekly_chunks_processed"],
            "duration_seconds": total_duration,
            "errors": self.stats["errors"],
        }


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Gap detection and filling job for klines data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fill gaps for all configured symbols (15m period)
  python extract_klines_gap_filler.py --period 15m

  # Fill gaps with custom symbols and more workers
  python extract_klines_gap_filler.py --period 1h --symbols BTCUSDT,ETHUSDT --max-workers 5

  # Fill gaps with custom weekly chunk size
  python extract_klines_gap_filler.py --period 15m --weekly-chunk-days 5
        """,
    )

    parser.add_argument(
        "--period",
        type=str,
        choices=[
            "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"
        ],
        default=constants.DEFAULT_PERIOD,
        help="Kline interval (default: 15m)",
    )

    parser.add_argument("--symbols", type=str, help="Comma-separated list of trading symbols (default: from config)")

    parser.add_argument(
        "--max-workers",
        type=int,
        default=3,
        help="Maximum number of parallel workers (default: 3, lower to avoid rate limiting)",
    )

    parser.add_argument("--batch-size", type=int, default=constants.DB_BATCH_SIZE, help="Database batch size (default: 1000)")

    parser.add_argument("--weekly-chunk-days", type=int, default=7, help="Number of days per weekly chunk (default: 7)")

    parser.add_argument("--max-gap-size-days", type=int, default=365, help="Maximum gap size in days to process (default: 365)")

    parser.add_argument(
        "--db-adapter",
        type=str,
        choices=["mongodb", "mysql", "postgresql"],
        default=constants.DB_ADAPTER,
        help="Database adapter to use",
    )

    parser.add_argument("--db-uri", type=str, help="Database connection URI (overrides default)")

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
    # Use simple tracer approach like production job
    try:
        # Use the module name instead of __name__ to get the correct tracer
        current_tracer = get_tracer("jobs.extract_klines_gap_filler")

        if current_tracer:
            with current_tracer.start_as_current_span("klines_gap_filling_main") as span:
                span.set_attribute("extraction.type", "klines_gap_filling")
                span.set_attribute("service.name", "binance-klines-gap-filler")
                # Force span context to be active for logging
                span_context = span.get_span_context()
                if span_context.trace_id != 0:
                    print(f"Main span created with trace_id: {format(span_context.trace_id, '032x')}")
                _main_impl()
        else:
            print("Tracer not available, running without tracing")
            _main_impl()
    except Exception as e:
        print(f"Tracing setup failed: {e}, running without tracing")
        _main_impl()


def _main_impl():
    """Implementation of main function."""
    args = parse_arguments()

    setup_logging(level=args.log_level)
    logger = get_logger(__name__)

    try:
        if args.symbols:
            symbols = [s.strip().upper() for s in args.symbols.split(",")]
        else:
            symbols = constants.DEFAULT_SYMBOLS
            logger.info(f"Using default symbols: {symbols}")

        log_extraction_start(
            log=logger,
            extractor_type="klines_gap_filling",
            symbols=symbols,
            period=args.period,
            start_date=constants.DEFAULT_START_DATE,
            backfill=True,
        )

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

        gap_filler = GapFillerExtractor(
            symbols=symbols,
            period=args.period,
            db_adapter_name=args.db_adapter,
            db_uri=db_uri,
            max_workers=args.max_workers,
            batch_size=args.batch_size,
            weekly_chunk_days=args.weekly_chunk_days,
            max_gap_size_days=args.max_gap_size_days,
        )

        if args.dry_run:
            logger.info("🔍 DRY RUN MODE - No data will be written to database")

        result = gap_filler.run_gap_filling()

        log_extraction_completion(
            log=logger,
            extractor_type="klines_gap_filling",
            total_records=result["total_records_written"],
            duration_seconds=result["duration_seconds"],
            gaps_found=result["total_gaps_found"],
            errors=result["errors"][:10],
        )

        if result["success"]:
            logger.info("🎉 Gap filling completed successfully!")
            sys.exit(0)
        else:
            logger.error(f"❌ Gap filling completed with {result['symbols_failed']} failures")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("⚠️ Gap filling interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"💥 Fatal error during gap filling: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
