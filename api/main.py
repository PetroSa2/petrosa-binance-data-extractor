"""
FastAPI application entry point for Data Extractor Configuration API.

Provides runtime configuration management for data extraction CronJobs.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import config, jobs, metrics

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Data Extractor Configuration API")
    yield
    # Shutdown
    logger.info("Shutting down Data Extractor Configuration API")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Petrosa Data Extractor Configuration API",
        description="Runtime configuration for data extraction CronJobs",
        version="1.0.0",
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
    app.include_router(metrics.router, tags=["Performance Metrics"])

    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "service": "Data Extractor Configuration API",
            "version": "1.0.0",
            "endpoints": [
                "/api/v1/config/cronjobs",
                "/api/v1/config/symbols",
                "/api/v1/config/rate-limits",
                "/api/v1/config/validate",
                "/api/v1/jobs/trigger",
                "/api/v1/metrics/performance",
                "/api/v1/metrics/success-rates",
                "/api/v1/metrics/resource-usage",
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
