#!/usr/bin/env python3
"""
MySQL klines retention/pruning job (#282).

`db/mysql_adapter.py` implements `delete_range` but, before this job existed,
had zero call sites anywhere in this repo — MySQL klines tables grew
unbounded. The MongoDB path is separately pruned by petrosa-data-manager's
`klines-retention` CronJob (see
`petrosa_k8s/k8s/data-extractor/klines-retention-cronjob.yaml`), but that job
only ever targeted `MONGODB_URL`; it has no MySQL counterpart.

This script is that counterpart. It deletes klines rows older than a
configurable retention window, per interval/table, using the existing
`BaseAdapter.delete_range` contract so it works against any adapter that
implements it (currently MySQL/MariaDB; `DataManagerAdapter` does not
implement `delete_range` yet — that gap is tracked separately, not by this
ticket).

Wiring this into a scheduled k8s CronJob is a follow-up change in
`petrosa_k8s` (this repo does not own cluster manifests or cluster-admin
operations). Until that lands, run manually or via any external scheduler:

    python -m jobs.klines_retention --retention-days 180
    python -m jobs.klines_retention --periods 1m,5m,15m --retention-days 90 --dry-run
"""

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

# Add project root to path (works for both local and container environments)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import constants  # noqa: E402
from db import get_adapter  # noqa: E402
from utils.logger import get_logger, setup_logging  # noqa: E402
from utils.telemetry import flush_telemetry  # noqa: E402
from utils.time_utils import binance_interval_to_table_suffix  # noqa: E402

# Initialize OpenTelemetry as early as possible using the standard petrosa-otel package.
try:
    from petrosa_otel import setup_telemetry  # noqa: E402

    if os.getenv("OTEL_NO_AUTO_INIT", "").lower() not in ("1", "true", "yes", "on"):
        setup_telemetry(
            service_name=os.getenv(
                "OTEL_SERVICE_NAME_KLINES_RETENTION",
                "binance-data-extractor-klines-retention",
            ),
            service_type="cronjob",
            enable_mysql=True,
            auto_attach_logging=True,
        )
except ImportError:
    pass

# Lower bound used for the delete/count range. MySQL's DATETIME floor is
# year 1000; datetime.min (year 1) is unsafe on some drivers/collations, so
# the Unix epoch is used instead — far older than any real klines row.
_EPOCH_START = datetime(1970, 1, 1, tzinfo=UTC)

DEFAULT_RETENTION_DAYS = int(os.getenv("KLINES_RETENTION_DAYS", "180"))


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Prune MySQL klines tables older than a retention window (#282)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Prune all supported periods, keep 180 days
  python -m jobs.klines_retention --retention-days 180

  # Dry run for a subset of periods
  python -m jobs.klines_retention --periods 1m,5m --retention-days 90 --dry-run
        """,
    )

    parser.add_argument(
        "--periods",
        type=str,
        help="Comma-separated list of kline intervals to prune (default: all SUPPORTED_INTERVALS)",
    )

    parser.add_argument(
        "--retention-days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help=f"Number of days of klines history to keep (default: {DEFAULT_RETENTION_DAYS})",
    )

    parser.add_argument(
        "--db-adapter",
        type=str,
        choices=["mysql", "mariadb"],
        default="mysql",
        help="Database adapter to use (retention currently supports MySQL/MariaDB only)",
    )

    parser.add_argument(
        "--db-uri", type=str, help="Database connection URI (overrides default)"
    )

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
        help="Report what would be deleted without deleting anything",
    )

    return parser.parse_args()


def prune_table(
    adapter: Any, table: str, cutoff: datetime, dry_run: bool, logger: Any
) -> int:
    """Delete (or, in dry-run mode, count) klines rows older than `cutoff` in `table`."""
    if dry_run:
        count = adapter.get_record_count(table, start=_EPOCH_START, end=cutoff)
        logger.info(
            f"[dry-run] {table}: {count} record(s) older than {cutoff.isoformat()} would be deleted"
        )
        return count

    deleted = adapter.delete_range(table, start=_EPOCH_START, end=cutoff)
    logger.info(f"{table}: deleted {deleted} record(s) older than {cutoff.isoformat()}")
    return deleted


def run_retention(
    periods: list[str],
    retention_days: int,
    db_adapter_name: str,
    db_uri: str,
    dry_run: bool,
    logger: Any,
) -> dict:
    """Run the retention sweep across all requested periods/tables."""
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    adapter = get_adapter(db_adapter_name, db_uri)
    adapter.connect()

    results: dict[str, int] = {}
    errors: list[str] = []
    try:
        for period in periods:
            table = f"klines_{binance_interval_to_table_suffix(period)}"
            try:
                results[table] = prune_table(adapter, table, cutoff, dry_run, logger)
            except Exception as e:  # noqa: BLE001 - one bad table must not abort the run
                logger.error(f"Failed to prune {table}: {e}")
                errors.append(f"{table}: {e}")
    finally:
        adapter.disconnect()

    return {
        "cutoff": cutoff.isoformat(),
        "retention_days": retention_days,
        "tables": results,
        "total_deleted": sum(results.values()),
        "errors": errors,
        "success": not errors,
    }


def main() -> None:
    """Main entry point."""
    args = parse_arguments()

    setup_logging(level=args.log_level)
    logger = get_logger(__name__)

    periods = (
        [p.strip() for p in args.periods.split(",") if p.strip()]
        if args.periods
        else list(constants.SUPPORTED_INTERVALS)
    )

    db_uri = args.db_uri or constants.MYSQL_URI

    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - no data will be deleted")

    logger.info(
        f"Starting klines retention: periods={periods}, "
        f"retention_days={args.retention_days}, dry_run={args.dry_run}"
    )

    try:
        result = run_retention(
            periods=periods,
            retention_days=args.retention_days,
            db_adapter_name=args.db_adapter,
            db_uri=db_uri,
            dry_run=args.dry_run,
            logger=logger,
        )
    except Exception as e:
        logger.error(f"💥 Fatal error during klines retention: {e}")
        flush_telemetry()
        sys.exit(1)

    if result["success"]:
        logger.info(
            f"🎉 Klines retention completed: {result['total_deleted']} record(s) "
            f"{'would be ' if args.dry_run else ''}pruned across {len(result['tables'])} table(s)"
        )
        flush_telemetry()
        sys.exit(0)
    else:
        logger.error(f"❌ Klines retention completed with errors: {result['errors']}")
        flush_telemetry()
        sys.exit(1)


if __name__ == "__main__":
    main()
