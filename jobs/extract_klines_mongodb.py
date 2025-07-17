#!/usr/bin/env python3
"""
MongoDB-specific klines extraction job with timeseries collections.

This script is optimized for MongoDB timeseries collections to provide
efficient storage and querying for time-series data while preventing duplicates.
Designed for 512MB memory constraint with ~400MB storage limit.
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from typing import List

# Add project root to path (works for both local and container environments)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import constants

# Initialize OpenTelemetry as early as possible
try:
    from otel_init import setup_telemetry
    if not os.getenv("OTEL_NO_AUTO_INIT"):
        setup_telemetry(service_name=constants.OTEL_SERVICE_NAME_KLINES)
except ImportError:
    pass

from db.mongodb_adapter import MongoDBAdapter
from fetchers import BinanceClient, KlinesFetcher
from utils.logger import log_extraction_completion, log_extraction_start, setup_logging
from utils.messaging import publish_extraction_completion_sync
from utils.time_utils import (
    format_duration,
    get_current_utc_time,
    parse_datetime_string,
    binance_interval_to_table_suffix,
)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract klines data from Binance Futures API to MongoDB timeseries collections",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract 15m klines for BTCUSDT from 2023-01-01
  python extract_klines_mongodb.py --symbol BTCUSDT --period 15m --start-date 2023-01-01T00:00:00Z

  # Extract multiple symbols with backfill
  python extract_klines_mongodb.py --symbols BTCUSDT,ETHUSDT --period 1h --backfill

  # Incremental extraction (from last timestamp)
  python extract_klines_mongodb.py --symbols BTCUSDT --period 15m --incremental
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
        default=500,  # Reduced for memory constraints
        help="Database batch size (default: 500)",
    )

    # MongoDB specific settings
    parser.add_argument(
        "--mongodb-uri",
        type=str,
        help="MongoDB connection string (overrides MONGODB_URI env var)",
    )
    parser.add_argument(
        "--database-name",
        type=str,
        default="binance",
        help="MongoDB database name (default: binance)",
    )

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


def get_mongodb_connection_string(args) -> str:
    """Get MongoDB connection string."""
    if args.mongodb_uri:
        return args.mongodb_uri

    # Try to get from Kubernetes secret
    try:
        import subprocess
        result = subprocess.run([
            "kubectl", "get", "secret", "petrosa-sensitive-credentials",
            "-n", "petrosa-apps", "-o", "jsonpath='{.data.mongodb-connection-string}'",
            "--insecure-skip-tls-verify"
        ], capture_output=True, text=True, check=True)

        if result.stdout.strip():
            import base64
            connection_string = base64.b64decode(result.stdout.strip().strip("'")).decode()
            return connection_string
    except Exception as e:
        print(f"Warning: Could not get MongoDB connection from Kubernetes secret: {e}")

    return constants.MONGODB_URI


def create_timeseries_collection(db_adapter: MongoDBAdapter, collection_name: str, period: str):
    """Create MongoDB timeseries collection with proper indexes."""
    try:
        db = db_adapter._get_database()

        # Check if collection exists
        if collection_name in db.list_collection_names():
            return

        # Create timeseries collection
        db.create_collection(
            collection_name,
            timeseries={
                "timeField": "timestamp",
                "metaField": "symbol",
                "granularity": "minutes" if period in ["1m", "3m", "5m", "15m", "30m"] else "hours"
            }
        )

        # Create indexes for efficient querying
        collection = db[collection_name]
        collection.create_index([("symbol", 1), ("timestamp", 1)], unique=True)
        collection.create_index([("timestamp", 1)])

        print(f"Created timeseries collection: {collection_name}")

    except Exception as e:
        print(f"Warning: Could not create timeseries collection {collection_name}: {e}")


def extract_klines_for_symbol(
    symbol: str,
    period: str,
    start_date: datetime,
    end_date: datetime,
    fetcher: KlinesFetcher,
    db_adapter: MongoDBAdapter,
    args,
    logger,
) -> dict:
    """Extract klines for a single symbol with MongoDB timeseries optimization."""
    symbol_start_time = time.time()

    try:
        # Get collection name with proper financial market naming
        table_suffix = binance_interval_to_table_suffix(period)
        collection_name = f"klines_{table_suffix}"

        # Create timeseries collection if it doesn't exist
        create_timeseries_collection(db_adapter, collection_name, period)

        # Check if incremental extraction
        if args.incremental:
            # Get last timestamp from database
            latest_records = db_adapter.query_latest(collection_name, symbol=symbol, limit=1)
            if latest_records:
                last_timestamp = latest_records[0]["timestamp"]
                logger.info(f"Last timestamp for {symbol}: {last_timestamp}")

                # Start from next interval
                if period.endswith('m'):
                    start_date = last_timestamp + timedelta(minutes=int(period[:-1]))
                elif period.endswith('h'):
                    start_date = last_timestamp + timedelta(hours=int(period[:-1]))
                elif period.endswith('d'):
                    start_date = last_timestamp + timedelta(days=int(period[:-1]))
                else:
                    # Default to minutes
                    start_date = last_timestamp + timedelta(minutes=1)

        # Fetch klines data
        logger.info(f"Fetching klines for {symbol} from {start_date} to {end_date}")
        kline_models = fetcher.fetch_klines(
            symbol=symbol,
            interval=period,
            start_time=start_date,
            end_time=end_date,
            limit=args.limit
        )

        if not kline_models:
            logger.warning(f"No klines data found for {symbol}")
            return {
                "symbol": symbol,
                "records_written": 0,
                "duration": time.time() - symbol_start_time,
                "status": "no_data"
            }

        # Write to database in batches
        total_written = 0
        if not args.dry_run:
            # Cast to List[BaseModel] for type compatibility
            from pydantic import BaseModel
            kline_models_cast: List[BaseModel] = kline_models  # type: ignore
            total_written = db_adapter.write_batch(
                kline_models_cast,
                collection_name,
                batch_size=args.batch_size
            )
            logger.info(f"Written {total_written} records for {symbol} to {collection_name}")
        else:
            logger.info(f"DRY RUN: Would write {len(kline_models)} records for {symbol}")

        duration = time.time() - symbol_start_time
        logger.info(f"Completed extraction for {symbol}: {total_written} records in {format_duration(duration)}")

        return {
            "symbol": symbol,
            "records_written": total_written,
            "duration": duration,
            "status": "success"
        }

    except Exception as e:
        duration = time.time() - symbol_start_time
        logger.error(f"Error extracting klines for {symbol}: {e}")
        return {
            "symbol": symbol,
            "records_written": 0,
            "duration": duration,
            "status": "error",
            "error": str(e)
        }


def main():
    """Main entry point for MongoDB klines extraction."""
    args = parse_arguments()

    # Setup logging
    logger = setup_logging(level=args.log_level)

    # Get symbols list
    symbols = get_symbols_list(args)

    # Parse dates
    start_date = parse_datetime_string(args.start_date)
    end_date = parse_datetime_string(args.end_date) if args.end_date else get_current_utc_time()

    # Get MongoDB connection string
    mongodb_uri = get_mongodb_connection_string(args)

    # Initialize MongoDB adapter
    db_adapter = MongoDBAdapter(
        connection_string=mongodb_uri,
        database_name=args.database_name,
        max_pool_size=10  # Reduced for memory constraints
    )

    # Initialize Binance client and fetcher
    client = BinanceClient()
    fetcher = KlinesFetcher(client)

    # Log extraction start
    log_extraction_start(
        log=logger,
        extractor_type="klines_mongodb",
        symbols=symbols,
        period=args.period,
        start_date=start_date.isoformat(),
        backfill=args.backfill,
    )

    extraction_start_time = time.time()
    total_records_written = 0
    results = []

    try:
        # Connect to database
        db_adapter.connect()

        # Extract klines for each symbol
        for symbol in symbols:
            result = extract_klines_for_symbol(
                symbol=symbol,
                period=args.period,
                start_date=start_date,
                end_date=end_date,
                fetcher=fetcher,
                db_adapter=db_adapter,
                args=args,
                logger=logger
            )
            results.append(result)
            total_records_written += result["records_written"]

        # Log extraction completion
        extraction_duration = time.time() - extraction_start_time
        log_extraction_completion(
            log=logger,
            extractor_type="klines_mongodb",
            total_records=total_records_written,
            duration_seconds=extraction_duration,
        )

        # Publish completion message
        publish_extraction_completion_sync(
            extractor_type="klines_mongodb",
            total_records=total_records_written,
            duration_seconds=extraction_duration,
            symbols=symbols,
            period=args.period
        )

        logger.info(f"Extraction completed: {total_records_written} records in {format_duration(extraction_duration)}")

    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        sys.exit(1)

    finally:
        # Clean up
        fetcher.close()
        db_adapter.close()

    sys.exit(0)


if __name__ == "__main__":
    main()
