"""
FastAPI application entry point for Data Extractor Configuration API.

Provides runtime configuration management for data extraction CronJobs.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Optional OpenTelemetry imports
try:
    from petrosa_otel import (
        attach_logging_handler,
        setup_telemetry,
    )
except ImportError:
    setup_telemetry = None
    attach_logging_handler = None

from api.routes import config, jobs
from utils.logger import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # 1. Setup OpenTelemetry
    if (
        os.getenv("ENABLE_OTEL", "true").lower() in ("true", "1", "yes")
        and setup_telemetry
        and os.getenv("OTEL_NO_AUTO_INIT", "").lower() not in ("1", "true", "yes", "on")
    ):
        try:
            setup_telemetry(
                service_name=os.getenv(
                    "OTEL_SERVICE_NAME", "petrosa-data-extractor-api"
                ),
                service_type="fastapi",
                enable_fastapi=True,
                enable_http=True,
                auto_attach_logging=False,  # We attach manually below
            )
        except Exception as e:
            # Can't use logger yet as it's not configured
            print(f"Failed to initialize OpenTelemetry: {e}")

    # 2. Setup logging (may call basicConfig and configure structlog)
    # This should happen AFTER setup_telemetry but BEFORE attach_logging_handler
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_format = os.getenv("LOG_FORMAT", "json")
    setup_logging(level=log_level, format_type=log_format)

    logger.info("Starting Data Extractor Configuration API")

    # Start health evaluator (publishes evaluator.data-extractor.verdict).
    # Read-only — subscribes to binance.extraction.> completion events.
    # Optional: skipped if petrosa-otel lacks the evaluators framework or
    # if NATS is disabled. Stored on app.state for shutdown.
    app.state.health_evaluator = None
    try:
        from evaluators import build_data_extractor_health_evaluator

        _evaluator = build_data_extractor_health_evaluator(
            nats_servers=os.getenv("NATS_URL") or os.getenv("NATS_SERVERS")
        )
        if _evaluator is not None:
            await _evaluator.start()
            app.state.health_evaluator = _evaluator
            logger.info("✅ Data-extractor health evaluator started")
    except ImportError:
        logger.warning("petrosa_otel.evaluators unavailable; health evaluator disabled")

    # 3. Attach OTel logging handler LAST (after logging is configured)
    if (
        os.getenv("ENABLE_OTEL", "true").lower() in ("true", "1", "yes")
        and attach_logging_handler
        and os.getenv("OTEL_NO_AUTO_INIT", "").lower() not in ("1", "true", "yes", "on")
    ):
        try:
            success = attach_logging_handler()
            if success:
                logger.info(
                    "✅ OpenTelemetry logging handler attached - logs will be exported to Grafana"
                )
        except Exception as e:
            logger.error(f"Failed to attach OTel logging handler: {e}")

    yield
    # Shutdown
    logger.info("Shutting down Data Extractor Configuration API")
    if getattr(app.state, "health_evaluator", None) is not None:
        try:
            await app.state.health_evaluator.stop()
            logger.info("✅ Data-extractor health evaluator stopped")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Health evaluator stop error: {exc}")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Petrosa Data Extractor Configuration API",
        description="Runtime configuration for data extraction CronJobs",
        version="1.1.32",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(config.router, prefix="/api/v1", tags=["Configuration"])
    app.include_router(jobs.router, prefix="/api/v1", tags=["Jobs"])

    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "service": "Data Extractor Configuration API",
            "version": "1.1.32",
            "endpoints": [
                "/api/v1/config/cronjobs",
                "/api/v1/config/symbols",
                "/api/v1/config/rate-limits",
                "/api/v1/config/validate",
                "/api/v1/jobs/trigger",
                "/docs",
            ],
        }

    @app.get("/healthz")
    async def healthz():
        """Liveness probe endpoint."""
        return {"status": "healthy"}

    @app.get("/ready")
    async def ready():
        """Readiness probe endpoint."""
        return {"status": "ready"}

    return app


# Create app instance
app = create_app()
