#!/usr/bin/env python3
"""
Comprehensive Pipeline Runner for Petrosa Binance Data Extractor

This script provides a unified interface to run all data extraction jobs
with proper error handling, logging, and configuration management.

Usage:
    python run_pipeline.py --help
    python run_pipeline.py --job klines --period 15m
    python run_pipeline.py --job funding
    python run_pipeline.py --job trades
    python run_pipeline.py --job gap-filler
    python run_pipeline.py --all
"""

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import constants  # noqa: E402
from utils.logger import get_logger, setup_logging  # noqa: E402
from utils.telemetry import TelemetryManager  # noqa: E402


class PipelineRunner:
    """Main pipeline runner class for orchestrating data extraction jobs."""

    def __init__(self, log_level: str = "INFO"):
        """Initialize the pipeline runner."""
        self.log_level = log_level
        self.logger: Any | None = None
        self.telemetry_manager: Any | None = None
        self.start_time: datetime | None = None

        # Job configurations
        self.job_configs = {
            "klines": {
                "script": "jobs/extract_klines_production.py",
                "description": "Extract klines data from Binance",
                "default_period": "15m",
                "default_symbols": constants.DEFAULT_SYMBOLS,
            },
            "funding": {
                "script": "jobs/extract_funding.py",
                "description": "Extract funding rates from Binance",
                "default_period": None,
                "default_symbols": constants.DEFAULT_SYMBOLS,
            },
            "trades": {
                "script": "jobs/extract_trades.py",
                "description": "Extract recent trades from Binance",
                "default_period": None,
                "default_symbols": constants.DEFAULT_SYMBOLS,
            },
            "gap-filler": {
                "script": "jobs/extract_klines_gap_filler.py",
                "description": "Detect and fill gaps in klines data",
                "default_period": "15m",
                "default_symbols": constants.DEFAULT_SYMBOLS,
            },
        }

    def setup_logging_and_telemetry(self) -> None:
        """Setup logging and telemetry for the pipeline."""
        setup_logging(level=self.log_level)
        self.logger = get_logger(__name__)

        # Initialize telemetry if enabled
        if constants.ENABLE_OTEL:
            try:
                self.telemetry_manager = TelemetryManager()
                # Note: TelemetryManager doesn't have setup method in this implementation
                if self.logger:
                    self.logger.info("Telemetry setup completed")
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Failed to setup telemetry: {e}")

        return None

    def run_job(self, job_name: str, **kwargs) -> dict[str, Any]:
        """Run a specific job with the given parameters."""
        if job_name not in self.job_configs:
            raise ValueError(f"Unknown job: {job_name}")

        job_config = self.job_configs[job_name]
        script_path = job_config["script"]  # type: ignore

        if self.logger:
            self.logger.info(f"Starting {job_name} job: {job_config['description']}")  # type: ignore
            self.logger.info(f"Script: {script_path}")

        # Import and run the job
        try:
            if job_name == "klines":
                from jobs.extract_klines_production import main as klines_main

                return self._run_klines_job(klines_main, **kwargs)
            elif job_name == "funding":
                from jobs.extract_funding import main as funding_main

                return self._run_funding_job(funding_main, **kwargs)
            elif job_name == "trades":
                from jobs.extract_trades import main as trades_main

                return self._run_trades_job(trades_main, **kwargs)
            elif job_name == "gap-filler":
                from jobs.extract_klines_gap_filler import main as gap_filler_main

                return self._run_gap_filler_job(gap_filler_main, **kwargs)
        except ImportError as e:
            if self.logger:
                self.logger.error(f"Failed to import job module: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to run {job_name} job: {e}")
            return {"success": False, "error": str(e)}
        # Add a fallback return to satisfy type checking
        return {"success": False, "error": "Unknown error in run_job"}

    def _run_klines_job(self, main_func, **kwargs) -> dict[str, Any]:
        """Run the klines extraction job."""
        # Set up sys.argv for the job
        original_argv = sys.argv.copy()

        # Build command line arguments
        args = ["extract_klines_production.py"]

        if kwargs.get("period"):
            args.extend(["--period", kwargs["period"]])

        if kwargs.get("symbols"):
            if isinstance(kwargs["symbols"], list):
                args.extend(["--symbols"] + kwargs["symbols"])
            else:
                args.extend(["--symbols", kwargs["symbols"]])

        if kwargs.get("max_workers"):
            args.extend(["--max-workers", str(kwargs["max_workers"])])

        if kwargs.get("lookback_hours"):
            args.extend(["--lookback-hours", str(kwargs["lookback_hours"])])

        if kwargs.get("batch_size"):
            args.extend(["--batch-size", str(kwargs["batch_size"])])

        if kwargs.get("db_adapter"):
            args.extend(["--db-adapter", kwargs["db_adapter"]])

        if kwargs.get("db_uri"):
            args.extend(["--db-uri", kwargs["db_uri"]])

        if kwargs.get("log_level"):
            args.extend(["--log-level", kwargs["log_level"]])

        if kwargs.get("dry_run"):
            args.append("--dry-run")

        sys.argv = args

        try:
            # Run the job
            main_func()
            return {"success": True, "job": "klines"}
        except SystemExit as e:
            if e.code == 0:
                return {"success": True, "job": "klines"}
            else:
                return {"success": False, "job": "klines", "exit_code": e.code}
        finally:
            sys.argv = original_argv

    def _run_funding_job(self, main_func, **kwargs) -> dict[str, Any]:
        """Run the funding rates extraction job."""
        original_argv = sys.argv.copy()

        args = ["extract_funding.py"]

        if kwargs.get("symbols"):
            if isinstance(kwargs["symbols"], list):
                args.extend(["--symbols"] + kwargs["symbols"])
            else:
                args.extend(["--symbols", kwargs["symbols"]])

        if kwargs.get("db_adapter"):
            args.extend(["--db-adapter", kwargs["db_adapter"]])

        if kwargs.get("db_uri"):
            args.extend(["--db-uri", kwargs["db_uri"]])

        if kwargs.get("log_level"):
            args.extend(["--log-level", kwargs["log_level"]])

        if kwargs.get("dry_run"):
            args.append("--dry-run")

        sys.argv = args

        try:
            main_func()
            return {"success": True, "job": "funding"}
        except SystemExit as e:
            if e.code == 0:
                return {"success": True, "job": "funding"}
            else:
                return {"success": False, "job": "funding", "exit_code": e.code}
        finally:
            sys.argv = original_argv

    def _run_trades_job(self, main_func, **kwargs) -> dict[str, Any]:
        """Run the trades extraction job."""
        original_argv = sys.argv.copy()

        args = ["extract_trades.py"]

        if kwargs.get("symbols"):
            if isinstance(kwargs["symbols"], list):
                args.extend(["--symbols"] + kwargs["symbols"])
            else:
                args.extend(["--symbols", kwargs["symbols"]])

        if kwargs.get("limit"):
            args.extend(["--limit", str(kwargs["limit"])])

        if kwargs.get("db_adapter"):
            args.extend(["--db-adapter", kwargs["db_adapter"]])

        if kwargs.get("db_uri"):
            args.extend(["--db-uri", kwargs["db_uri"]])

        if kwargs.get("log_level"):
            args.extend(["--log-level", kwargs["log_level"]])

        if kwargs.get("dry_run"):
            args.append("--dry-run")

        sys.argv = args

        try:
            main_func()
            return {"success": True, "job": "trades"}
        except SystemExit as e:
            if e.code == 0:
                return {"success": True, "job": "trades"}
            else:
                return {"success": False, "job": "trades", "exit_code": e.code}
        finally:
            sys.argv = original_argv

    def _run_gap_filler_job(self, main_func, **kwargs) -> dict[str, Any]:
        """Run the gap filler job."""
        original_argv = sys.argv.copy()

        args = ["extract_klines_gap_filler.py"]

        if kwargs.get("period"):
            args.extend(["--period", kwargs["period"]])

        if kwargs.get("symbols"):
            if isinstance(kwargs["symbols"], list):
                args.extend(["--symbols"] + kwargs["symbols"])
            else:
                args.extend(["--symbols", kwargs["symbols"]])

        if kwargs.get("max_workers"):
            args.extend(["--max-workers", str(kwargs["max_workers"])])

        if kwargs.get("db_adapter"):
            args.extend(["--db-adapter", kwargs["db_adapter"]])

        if kwargs.get("db_uri"):
            args.extend(["--db-uri", kwargs["db_uri"]])

        if kwargs.get("log_level"):
            args.extend(["--log-level", kwargs["log_level"]])

        if kwargs.get("dry_run"):
            args.append("--dry-run")

        sys.argv = args

        try:
            main_func()
            return {"success": True, "job": "gap-filler"}
        except SystemExit as e:
            if e.code == 0:
                return {"success": True, "job": "gap-filler"}
            else:
                return {"success": False, "job": "gap-filler", "exit_code": e.code}
        finally:
            sys.argv = original_argv

    def run_all_jobs(self, **kwargs) -> dict[str, Any]:
        """Run all jobs in sequence."""
        if self.logger:
            self.logger.info("Starting pipeline run for all jobs")

        results = {}
        overall_success = True

        # Run jobs in order: klines, funding, trades, gap-filler
        job_order = ["klines", "funding", "trades", "gap-filler"]

        for job_name in job_order:
            if self.logger:
                self.logger.info(f"Running {job_name} job...")
            job_start = time.time()

            try:
                result = self.run_job(job_name, **kwargs)
                job_duration = time.time() - job_start

                results[job_name] = {
                    **result,
                    "duration_seconds": job_duration,
                    "start_time": datetime.now(UTC).isoformat(),
                }

                if not result.get("success", False):
                    overall_success = False
                    if self.logger:
                        self.logger.error(f"{job_name} job failed")
                else:
                    if self.logger:
                        self.logger.info(
                            f"{job_name} job completed successfully in {job_duration:.2f}s"
                        )

            except Exception as e:
                job_duration = time.time() - job_start
                results[job_name] = {
                    "success": False,
                    "error": str(e),
                    "duration_seconds": job_duration,
                    "start_time": datetime.now(UTC).isoformat(),
                }
                overall_success = False
                if self.logger:
                    self.logger.error(f"{job_name} job failed with exception: {e}")

        start_time = self.start_time or datetime.now(UTC)
        return {
            "success": overall_success,
            "jobs": results,
            "total_duration": time.time() - start_time.timestamp(),
            "start_time": start_time.isoformat(),
            "end_time": datetime.now(UTC).isoformat(),
        }

    def run(
        self, job_name: str | None = None, run_all: bool = False, **kwargs
    ) -> dict[str, Any]:
        """Main run method for the pipeline."""
        self.start_time = datetime.now(UTC)
        self.setup_logging_and_telemetry()

        if self.logger:
            self.logger.info("=" * 60)
            self.logger.info("Petrosa Binance Data Extractor Pipeline")
            self.logger.info("=" * 60)
            self.logger.info(f"Start time: {self.start_time}")
            self.logger.info(f"Log level: {self.log_level}")

        try:
            if run_all:
                return self.run_all_jobs(**kwargs)
            elif job_name:
                return self.run_job(job_name, **kwargs)
            else:
                raise ValueError("Must specify either --job or --all")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Pipeline failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "start_time": self.start_time.isoformat(),
                "end_time": datetime.now(UTC).isoformat(),
            }

        finally:
            if self.telemetry_manager:
                self.telemetry_manager.shutdown()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Petrosa Binance Data Extractor Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py --job klines --period 15m
  python run_pipeline.py --job funding --symbols BTCUSDT ETHUSDT
  python run_pipeline.py --job trades --limit 1000
  python run_pipeline.py --job gap-filler --period 1h
  python run_pipeline.py --all --dry-run
        """,
    )

    # Job selection
    job_group = parser.add_mutually_exclusive_group(required=True)
    job_group.add_argument(
        "--job",
        choices=["klines", "funding", "trades", "gap-filler"],
        help="Specific job to run",
    )
    job_group.add_argument(
        "--all", action="store_true", help="Run all jobs in sequence"
    )

    # Common parameters
    parser.add_argument(
        "--symbols", nargs="+", help="Symbols to process (default: all from constants)"
    )
    parser.add_argument(
        "--period", help="Time period for klines/gap-filler (default: 15m)"
    )
    parser.add_argument(
        "--max-workers", type=int, help="Maximum number of worker threads"
    )
    parser.add_argument(
        "--lookback-hours", type=int, help="Lookback period in hours for klines"
    )
    parser.add_argument(
        "--batch-size", type=int, help="Batch size for database operations"
    )
    parser.add_argument("--limit", type=int, help="Limit for trades extraction")
    parser.add_argument(
        "--db-adapter",
        choices=["mongodb", "mysql", "postgresql"],
        help="Database adapter to use",
    )
    parser.add_argument("--db-uri", help="Database connection URI")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no actual data extraction)",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()

    # Create pipeline runner
    runner = PipelineRunner(log_level=args.log_level)

    # Prepare job parameters
    job_params = {}

    if args.symbols:
        job_params["symbols"] = args.symbols

    if args.period:
        job_params["period"] = args.period

    if args.max_workers:
        job_params["max_workers"] = args.max_workers

    if args.lookback_hours:
        job_params["lookback_hours"] = args.lookback_hours

    if args.batch_size:
        job_params["batch_size"] = args.batch_size

    if args.limit:
        job_params["limit"] = args.limit

    if args.db_adapter:
        job_params["db_adapter"] = args.db_adapter

    if args.db_uri:
        job_params["db_uri"] = args.db_uri

    if args.log_level:
        job_params["log_level"] = args.log_level

    if args.dry_run:
        job_params["dry_run"] = True

    # Run the pipeline
    try:
        if args.all:
            result = runner.run(run_all=True, **job_params)
        else:
            result = runner.run(job_name=args.job, **job_params)

        # Print summary
        print("\n" + "=" * 60)
        print("Pipeline Summary")
        print("=" * 60)

        if result.get("success"):
            print("✅ Pipeline completed successfully")
        else:
            print("❌ Pipeline failed")
            if "error" in result:
                print(f"Error: {result['error']}")

        if "jobs" in result:
            print(f"\nJobs executed: {len(result['jobs'])}")
            for job_name, job_result in result["jobs"].items():
                status = "✅" if job_result.get("success") else "❌"
                duration = job_result.get("duration_seconds", 0)
                print(f"  {status} {job_name}: {duration:.2f}s")

        if "total_duration" in result:
            print(f"\nTotal duration: {result['total_duration']:.2f}s")

        # Exit with appropriate code
        sys.exit(0 if result.get("success") else 1)

    except KeyboardInterrupt:
        print("\n⚠️  Pipeline interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Pipeline failed with exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
