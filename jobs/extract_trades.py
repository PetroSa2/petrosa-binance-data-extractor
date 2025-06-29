#!/usr/bin/env python3
"""
CLI entry point for trades extraction job.
"""

import argparse
import os
import sys
import time

# Add project root to path (works for both local and container environments)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Initialize OpenTelemetry as early as possible
try:
    from otel_init import setup_telemetry
    import constants
    setup_telemetry(service_name=constants.OTEL_SERVICE_NAME_TRADES)
except ImportError:
    pass

import constants
from utils.logger import setup_logging, log_extraction_start, log_extraction_completion
from utils.time_utils import (
    parse_datetime_string,
    format_duration,
)
from fetchers import TradesFetcher, BinanceClient
from db import get_adapter


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract trades data from Binance Futures API"
    )

    parser.add_argument("--symbol", type=str, help="Single trading symbol")
    parser.add_argument("--symbols", type=str, help="Comma-separated trading symbols")
    parser.add_argument(
        "--limit", type=int, default=1000, help="Number of trades per symbol"
    )
    parser.add_argument(
        "--historical", action="store_true", help="Use historical trades endpoint"
    )
    parser.add_argument(
        "--from-id", type=int, help="Starting trade ID for historical trades"
    )
    parser.add_argument(
        "--db-adapter",
        type=str,
        default=constants.DB_ADAPTER,
        choices=["mongodb", "mysql"],
    )
    parser.add_argument("--db-uri", type=str, help="Database connection URI")
    parser.add_argument("--batch-size", type=int, default=constants.DB_BATCH_SIZE)
    parser.add_argument("--log-level", type=str, default=constants.LOG_LEVEL)
    parser.add_argument(
        "--dry-run", action="store_true", help="Dry run without database writes"
    )

    return parser.parse_args()


def main():
    """Main extraction function."""
    args = parse_arguments()

    # Set up logging
    logger = setup_logging(level=args.log_level)
    logger.info("Starting Binance trades extraction job")

    # Get symbols
    if args.symbol:
        symbols = [args.symbol.upper()]
    elif args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
    else:
        symbols = constants.DEFAULT_SYMBOLS

    # Log extraction start
    log_extraction_start(
        logger=logger,
        extractor_type="trades",
        symbols=symbols,
        period="trades",
        start_date="N/A",
    )

    extraction_start_time = time.time()
    total_records = 0
    errors = []

    try:
        # Initialize components
        db_uri = args.db_uri or (
            constants.MONGODB_URI
            if args.db_adapter == "mongodb"
            else constants.MYSQL_URI
        )
        db_adapter = get_adapter(args.db_adapter, db_uri)
        client = BinanceClient()
        fetcher = TradesFetcher(client)

        with db_adapter:
            collection_name = "trades"
            db_adapter.ensure_indexes(collection_name)

            for symbol in symbols:
                logger.info("Processing symbol: %s", symbol)

                try:
                    if args.historical and args.from_id:
                        trades = fetcher.fetch_trades_since_id(
                            symbol, args.from_id, args.limit
                        )
                    elif args.historical:
                        trades = fetcher.fetch_historical_trades(
                            symbol, limit=args.limit
                        )
                    else:
                        trades = fetcher.fetch_recent_trades(symbol, limit=args.limit)

                    if not args.dry_run and trades:
                        written = db_adapter.write_batch(
                            trades, collection_name, args.batch_size
                        )
                        total_records += written
                        logger.info("Wrote %d trades for %s", written, symbol)
                    else:
                        total_records += len(trades)
                        logger.info(
                            "Fetched %d trades for %s (dry run)", len(trades), symbol
                        )

                except Exception as e:
                    logger.error("Failed to process %s: %s", symbol, e)
                    errors.append(str(e))

        fetcher.close()

    except Exception as e:
        logger.error("Extraction failed: %s", e)
        errors.append(str(e))
        sys.exit(1)

    # Log completion
    extraction_duration = time.time() - extraction_start_time

    log_extraction_completion(
        logger=logger,
        extractor_type="trades",
        total_records=total_records,
        duration_seconds=extraction_duration,
        errors=errors,
    )

    logger.info(
        "Extraction completed: %d records in %s",
        total_records,
        format_duration(extraction_duration),
    )

    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    main()
