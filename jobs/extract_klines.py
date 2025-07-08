#!/usr/bin/env python3
"""
CLI entry point for klines extraction job.

This script serves as the main entry point for Kubernetes jobs that extract
klines (candlestick) data from Binance Futures API.
"""

import argparse
import os
import sys
import time
from datetime import datetime
from typing import List

# Add project root to path (works for both local and container environments)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import constants first
import constants

# Initialize OpenTelemetry as early as possible
try:
    from otel_init import setup_telemetry

    # Only initialize OpenTelemetry if not already initialized by opentelemetry-instrument
    if not os.getenv("OTEL_NO_AUTO_INIT"):
        setup_telemetry(service_name=constants.OTEL_SERVICE_NAME_KLINES)
except ImportError:
    pass
from db import get_adapter
from fetchers import BinanceClient, KlinesFetcher
from utils.logger import log_extraction_completion, log_extraction_start, setup_logging
from utils.messaging import publish_extraction_completion_sync
from utils.time_utils import (
    format_duration,
    get_current_utc_time,
    parse_datetime_string,
)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract klines data from Binance Futures API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract 15m klines for BTCUSDT from 2023-01-01
  python extract_klines.py --symbol BTCUSDT --period 15m --start-date 2023-01-01T00:00:00Z

  # Extract multiple symbols with backfill
  python extract_klines.py --symbols BTCUSDT,ETHUSDT --period 1h --backfill

  # Incremental extraction (from last timestamp)
  python extract_klines.py --symbols BTCUSDT --period 15m --incremental
        """,
    )

    # Core parameters
    parser.add_argument("--symbol", type=str, help="Single trading symbol to extract (e.g., BTCUSDT)")

    parser.add_argument(
        "--symbols",
        type=str,
        help="Comma-separated list of trading symbols (e.g., BTCUSDT,ETHUSDT)",
    )

    parser.add_argument(
        "--period",
        type=str,
        default=constants.DEFAULT_PERIOD,
        choices=constants.SUPPORTED_INTERVALS,
        help=f"Kline interval (default: {constants.DEFAULT_PERIOD})",
    )

    parser.add_argument(
        "--start-date",
        type=str,
        default=constants.DEFAULT_START_DATE,
        help=f"Start date in ISO format (default: {constants.DEFAULT_START_DATE})",
    )

    parser.add_argument("--end-date", type=str, help="End date in ISO format (default: current time)")

    # Extraction modes
    parser.add_argument(
        "--backfill",
        action="store_true",
        default=constants.BACKFILL,
        help="Perform backfill from start date",
    )

    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Perform incremental extraction from last timestamp",
    )

    # Limits and batching
    parser.add_argument("--limit", type=int, help="Maximum number of klines to extract per symbol")

    parser.add_argument(
        "--batch-size",
        type=int,
        default=constants.DB_BATCH_SIZE,
        help=f"Database batch size (default: {constants.DB_BATCH_SIZE})",
    )

    # Database options
    parser.add_argument(
        "--db-adapter",
        type=str,
        default=constants.DB_ADAPTER,
        choices=["mongodb", "mysql", "postgresql"],
        help=f"Database adapter to use (default: {constants.DB_ADAPTER})",
    )

    parser.add_argument("--db-uri", type=str, help="Database connection URI (overrides default)")

    # Logging and monitoring
    parser.add_argument(
        "--log-level",
        type=str,
        default=constants.LOG_LEVEL,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help=f"Logging level (default: {constants.LOG_LEVEL})",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform dry run without writing to database",
    )

    parser.add_argument(
        "--check-gaps",
        action="store_true",
        default=constants.GAP_CHECK_ENABLED,
        help="Check for data gaps after extraction",
    )

    return parser.parse_args()


def get_symbols_list(args) -> List[str]:
    """Get list of symbols from arguments."""
    if args.symbol:
        return [args.symbol.upper()]
    elif args.symbols:
        return [s.strip().upper() for s in args.symbols.split(",")]
    else:
        # Use default symbols
        return constants.DEFAULT_SYMBOLS


def get_database_connection_string(args) -> str:
    """Get database connection string based on adapter type."""
    if args.db_uri:
        return args.db_uri

    adapter_uris = {
        "mongodb": constants.MONGODB_URI,
        "mysql": constants.MYSQL_URI,
        "postgresql": constants.POSTGRESQL_URI,
    }

    return adapter_uris.get(args.db_adapter, constants.MONGODB_URI)


def extract_klines_for_symbol(
    symbol: str,
    period: str,
    start_date: datetime,
    end_date: datetime,
    fetcher: KlinesFetcher,
    db_adapter,
    args,
    logger,
) -> dict:
    """Extract klines for a single symbol."""
    symbol_start_time = time.time()

    try:
        # Get collection name with proper financial market naming
        from utils.time_utils import binance_interval_to_table_suffix

        table_suffix = binance_interval_to_table_suffix(period)
        collection_name = f"klines_{table_suffix}"

        # Check if incremental extraction
        if args.incremental:
            # Get last timestamp from database
            latest_records = db_adapter.query_latest(collection_name, symbol=symbol, limit=1)
            if latest_records:
                last_timestamp = latest_records[0]["timestamp"]
                logger.info(f"Last timestamp for {symbol}: {last_timestamp}")

                # Fetch incremental data
                klines = fetcher.fetch_incremental(
                    symbol=symbol,
                    interval=period,
                    last_timestamp=last_timestamp,
                    max_records=args.limit,
                )
            else:
                logger.info(f"No existing data for {symbol}, performing full extraction")
                klines = fetcher.fetch_klines(
                    symbol=symbol,
                    interval=period,
                    start_time=start_date,
                    end_time=end_date,
                    limit=args.limit,
                )
        else:
            # Full extraction
            klines = fetcher.fetch_klines(
                symbol=symbol,
                interval=period,
                start_time=start_date,
                end_time=end_date,
                limit=args.limit,
            )

        # Write to database (unless dry run)
        written_count = 0
        if not args.dry_run and klines:
            db_adapter.ensure_indexes(collection_name)
            written_count = db_adapter.write_batch(klines, collection_name, args.batch_size)

        # Check for gaps if requested
        gaps_found = 0
        if args.check_gaps and klines:
            from utils.time_utils import get_interval_minutes

            interval_minutes = get_interval_minutes(period)

            gaps = db_adapter.find_gaps(collection_name, start_date, end_date, interval_minutes, symbol=symbol)
            gaps_found = len(gaps)

            if gaps:
                logger.warning(f"Found {gaps_found} gaps in {symbol} data")
                for gap_start, gap_end in gaps:
                    logger.warning(f"Gap: {gap_start} to {gap_end}")

        duration = time.time() - symbol_start_time

        return {
            "symbol": symbol,
            "success": True,
            "records_fetched": len(klines),
            "records_written": written_count,
            "gaps_found": gaps_found,
            "duration_seconds": duration,
            "errors": [],
        }

    except Exception as e:
        duration = time.time() - symbol_start_time
        logger.error(f"Failed to extract klines for {symbol}: {e}")

        return {
            "symbol": symbol,
            "success": False,
            "records_fetched": 0,
            "records_written": 0,
            "gaps_found": 0,
            "duration_seconds": duration,
            "errors": [str(e)],
        }


def main():
    """Main extraction function."""
    args = parse_arguments()

    # Set up logging
    logger = setup_logging(level=args.log_level)
    logger.info("Starting Binance klines extraction job")

    # Parse dates
    try:
        start_date = parse_datetime_string(args.start_date)
        end_date = parse_datetime_string(args.end_date) if args.end_date else get_current_utc_time()
    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        sys.exit(1)
        return  # Prevent UnboundLocalError if sys.exit is patched in tests

    # Get symbols list
    symbols = get_symbols_list(args)

    # Log extraction start
    log_extraction_start(
        log=logger,
        extractor_type="klines",
        symbols=symbols,
        period=args.period,
        start_date=start_date.isoformat(),
        backfill=args.backfill,
    )

    # Initialize components
    extraction_start_time = time.time()
    total_records_fetched = 0
    total_records_written = 0
    total_gaps_found = 0
    extraction_errors = []

    try:
        # Initialize database adapter
        db_uri = get_database_connection_string(args)
        db_adapter = get_adapter(args.db_adapter, db_uri)

        # Initialize fetcher
        client = BinanceClient()
        fetcher = KlinesFetcher(client)

        # Test connectivity
        if not client.ping():
            logger.error("Failed to connect to Binance API")
            sys.exit(1)

        with db_adapter:
            logger.info(f"Connected to {args.db_adapter} database")

            # Process each symbol
            for i, symbol in enumerate(symbols, 1):
                logger.info(f"Processing symbol {i}/{len(symbols)}: {symbol}")

                result = extract_klines_for_symbol(
                    symbol=symbol,
                    period=args.period,
                    start_date=start_date,
                    end_date=end_date,
                    fetcher=fetcher,
                    db_adapter=db_adapter,
                    args=args,
                    logger=logger,
                )

                # Aggregate results
                total_records_fetched += result["records_fetched"]
                total_records_written += result["records_written"]
                total_gaps_found += result["gaps_found"]
                extraction_errors.extend(result["errors"])

                logger.info(
                    f"Completed {symbol}: "
                    f"fetched={result['records_fetched']}, "
                    f"written={result['records_written']}, "
                    f"duration={format_duration(result['duration_seconds'])}"
                )

                # Send NATS message for symbol completion
                if constants.NATS_ENABLED:
                    try:
                        publish_extraction_completion_sync(
                            symbol=symbol,
                            period=args.period,
                            records_fetched=result["records_fetched"],
                            records_written=result["records_written"],
                            success=result["success"],
                            duration_seconds=result["duration_seconds"],
                            errors=result["errors"],
                            gaps_found=result["gaps_found"],
                            extraction_type="klines",
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send NATS message for {symbol}: {e}")

        # Close resources
        fetcher.close()

    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        extraction_errors.append(str(e))
        sys.exit(1)

    # Log completion
    extraction_duration = time.time() - extraction_start_time

    log_extraction_completion(
        log=logger,
        extractor_type="klines",
        total_records=total_records_written,
        duration_seconds=extraction_duration,
        gaps_found=total_gaps_found,
        errors=extraction_errors,
    )

    # Summary
    logger.info("Extraction completed successfully:")
    logger.info(f"  Symbols processed: {len(symbols)}")
    logger.info(f"  Records fetched: {total_records_fetched}")
    logger.info(f"  Records written: {total_records_written}")
    logger.info(f"  Gaps found: {total_gaps_found}")
    logger.info(f"  Duration: {format_duration(extraction_duration)}")

    if extraction_errors:
        logger.warning(f"Errors encountered: {len(extraction_errors)}")
        for error in extraction_errors:
            logger.warning(f"  - {error}")

    # Exit code based on success
    sys.exit(0 if not extraction_errors else 1)


if __name__ == "__main__":
    main()
