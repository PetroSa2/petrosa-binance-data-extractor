#!/usr/bin/env python3
"""
Extract funding rates from Binance Futures API.
"""

import argparse
import os
import sys
import time

# Add project root to path (works for both local and container environments)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Project imports (after path setup)
import constants  # noqa: E402
from db import get_adapter  # noqa: E402
from fetchers import BinanceClient, FundingRatesFetcher  # noqa: E402
from utils.logger import (  # noqa: E402
    log_extraction_completion,
    log_extraction_start,
    setup_logging,
)
from utils.time_utils import format_duration, parse_datetime_string  # noqa: E402

# OpenTelemetry will be initialized in main() following standardized pattern


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract funding rates from Binance Futures API"
    )
    parser.add_argument("--symbol", type=str, help="Single trading symbol")
    parser.add_argument("--symbols", type=str, help="Comma-separated trading symbols")
    parser.add_argument("--start-date", type=str, help="Start date for historical data")
    parser.add_argument("--end-date", type=str, help="End date for historical data")
    parser.add_argument(
        "--limit", type=int, default=1000, help="Records limit per symbol"
    )
    parser.add_argument(
        "--current-only", action="store_true", help="Fetch current rates only"
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

    # 1. Setup OpenTelemetry FIRST (before any logging configuration)
    try:
        from petrosa_otel import attach_logging_handler, initialize_telemetry_standard

        initialize_telemetry_standard(
            service_name=constants.OTEL_SERVICE_NAME_FUNDING,
            service_type="cronjob",
            enable_mysql=True,
            enable_mongodb=True,
        )
    except ImportError:
        pass  # Continue without OpenTelemetry if not available

    # 2. Setup logging (may call basicConfig)
    logger = setup_logging(level=args.log_level)

    # 3. Attach OTel logging handler LAST (after logging is configured)
    try:
        from petrosa_otel import attach_logging_handler

        attach_logging_handler()
    except ImportError:
        pass  # Continue without OpenTelemetry if not available

    logger.info("Starting Binance funding rates extraction job")
    start_date = None
    end_date = None
    if args.start_date:
        start_date = parse_datetime_string(args.start_date)
    if args.end_date:
        end_date = parse_datetime_string(args.end_date)
    if args.symbol:
        symbols = [args.symbol.upper()]
    elif args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
    else:
        symbols = constants.DEFAULT_SYMBOLS
    log_extraction_start(
        logger=logger,
        extractor_type="funding_rates",
        symbols=symbols,
        period="funding_rates",
        start_date=start_date.isoformat() if start_date else "N/A",
    )
    extraction_start_time = time.time()
    total_records = 0
    errors = []
    try:
        db_uri = args.db_uri or (
            constants.MONGODB_URI
            if args.db_adapter == "mongodb"
            else constants.MYSQL_URI
        )
        db_adapter = get_adapter(args.db_adapter, db_uri)
        client = BinanceClient()
        fetcher = FundingRatesFetcher(client)
        with db_adapter:
            collection_name = "funding_rates"
            db_adapter.ensure_indexes(collection_name)
            if args.current_only:
                logger.info("Fetching current funding rates")
                try:
                    current_rates = fetcher.fetch_current_funding_rates(symbols)
                    if not args.dry_run and current_rates:
                        written = db_adapter.write_batch(
                            current_rates, collection_name, args.batch_size
                        )
                        total_records += written
                        logger.info("Wrote %d current funding rates", written)
                    else:
                        total_records += len(current_rates)
                        logger.info(
                            "Fetched %d current funding rates (dry run)",
                            len(current_rates),
                        )
                except Exception as e:
                    logger.error("Failed to fetch current funding rates: %s", e)
                    errors.append(str(e))
            else:
                for symbol in symbols:
                    logger.info("Processing symbol: %s", symbol)
                    try:
                        if start_date and end_date:
                            rates = fetcher.fetch_funding_rates_batch(
                                symbol, start_date, end_date
                            )
                        else:
                            rates = fetcher.fetch_funding_rate_history(
                                symbol, start_date, end_date, args.limit
                            )
                        if not args.dry_run and rates:
                            written = db_adapter.write_batch(
                                rates, collection_name, args.batch_size
                            )
                            total_records += written
                            logger.info(
                                "Wrote %d funding rates for %s", written, symbol
                            )
                        else:
                            total_records += len(rates)
                            logger.info(
                                "Fetched %d funding rates for %s (dry run)",
                                len(rates),
                                symbol,
                            )
                    except Exception as e:
                        logger.error("Failed to process %s: %s", symbol, e)
                        errors.append(str(e))
        fetcher.close()
    except Exception as e:
        logger.error("Extraction failed: %s", e)
        errors.append(str(e))
        sys.exit(1)
    extraction_duration = time.time() - extraction_start_time
    log_extraction_completion(
        logger=logger,
        extractor_type="funding_rates",
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
