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
            logger.info("Initializing OpenTelemetry for Data Extractor API")
            setup_telemetry(
                service_name="binance-data-extractor-api",
                service_type="fastapi",
                enable_fastapi=True,
                enable_http=True,
            )
        except Exception as e:
            logger.warning(f"Failed to initialize OpenTelemetry: {e}")

    # Startup
    logger.info("Starting Data Extractor Configuration API")

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
