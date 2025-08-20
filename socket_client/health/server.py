"""
Health check server for the Socket Client service.

This module provides HTTP endpoints for Kubernetes health checks
and service monitoring.
"""

import time
from datetime import datetime
from typing import Optional

from aiohttp import web
from structlog import get_logger

from socket_client.models.message import HealthMessage

logger = get_logger(__name__)


class HealthServer:
    """HTTP server for health checks and monitoring."""

    def __init__(self, port: int = 8080, logger=None):
        """
        Initialize the health server.

        Args:
            port: Server port
            logger: Logger instance
        """
        self.port = port
        self.logger = logger or get_logger(__name__)
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.start_time = time.time()

        # Setup routes
        self.app.router.add_get("/healthz", self.health_check)
        self.app.router.add_get("/ready", self.ready_check)
        self.app.router.add_get("/metrics", self.metrics)
        self.app.router.add_get("/", self.root)

        self.logger.info(f"Health server initialized on port {port}")

    async def start(self):
        """Start the health server."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()

            self.site = web.TCPSite(self.runner, "0.0.0.0", self.port)
            await self.site.start()

            self.logger.info(f"Health server started on port {self.port}")

        except Exception as e:
            self.logger.error(f"Failed to start health server: {e}")
            raise

    async def stop(self):
        """Stop the health server."""
        if self.site:
            await self.site.stop()

        if self.runner:
            await self.runner.cleanup()

        self.logger.info("Health server stopped")

    async def health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint for Kubernetes liveness probe."""
        try:
            uptime = time.time() - self.start_time

            health_data = HealthMessage(
                status="healthy",
                uptime=uptime,
                service="socket-client",
                version="1.0.0",
                metrics={
                    "uptime_seconds": uptime,
                    "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
                },
            )

            return web.json_response(
                health_data.dict(),
                status=200,
                headers={"Content-Type": "application/json"},
            )

        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return web.json_response(
                {"status": "unhealthy", "error": str(e)},
                status=503,
                headers={"Content-Type": "application/json"},
            )

    async def ready_check(self, request: web.Request) -> web.Response:
        """Readiness check endpoint for Kubernetes readiness probe."""
        try:
            # Check if service is ready to receive traffic
            # This could include checks for:
            # - WebSocket connection status
            # - NATS connection status
            # - Message queue health

            ready_data = {
                "status": "ready",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "service": "socket-client",
                "checks": {
                    "websocket": "connected",  # This would be dynamic
                    "nats": "connected",  # This would be dynamic
                    "queue": "healthy",  # This would be dynamic
                },
            }

            return web.json_response(
                ready_data, status=200, headers={"Content-Type": "application/json"}
            )

        except Exception as e:
            self.logger.error(f"Ready check failed: {e}")
            return web.json_response(
                {"status": "not_ready", "error": str(e)},
                status=503,
                headers={"Content-Type": "application/json"},
            )

    async def metrics(self, request: web.Request) -> web.Response:
        """Metrics endpoint for monitoring."""
        try:
            uptime = time.time() - self.start_time

            metrics_data = {
                "service": "socket-client",
                "version": "1.0.0",
                "uptime_seconds": uptime,
                "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
                "current_time": datetime.utcnow().isoformat() + "Z",
                "memory_usage_mb": self._get_memory_usage(),
                "cpu_usage_percent": self._get_cpu_usage(),
                "websocket_metrics": {
                    "is_connected": False,  # This would be dynamic
                    "reconnect_attempts": 0,  # This would be dynamic
                    "processed_messages": 0,  # This would be dynamic
                    "dropped_messages": 0,  # This would be dynamic
                },
                "nats_metrics": {
                    "is_connected": False,  # This would be dynamic
                    "published_messages": 0,  # This would be dynamic
                },
            }

            return web.json_response(
                metrics_data, status=200, headers={"Content-Type": "application/json"}
            )

        except Exception as e:
            self.logger.error(f"Metrics endpoint failed: {e}")
            return web.json_response(
                {"error": str(e)},
                status=500,
                headers={"Content-Type": "application/json"},
            )

    async def root(self, request: web.Request) -> web.Response:
        """Root endpoint with service information."""
        try:
            info_data = {
                "service": "Petrosa Socket Client",
                "version": "1.0.0",
                "description": "Binance WebSocket client for real-time data streaming",
                "endpoints": {
                    "health": "/healthz",
                    "ready": "/ready",
                    "metrics": "/metrics",
                },
                "documentation": "https://github.com/petrosa/petrosa-socket-client",
            }

            return web.json_response(
                info_data, status=200, headers={"Content-Type": "application/json"}
            )

        except Exception as e:
            self.logger.error(f"Root endpoint failed: {e}")
            return web.json_response(
                {"error": str(e)},
                status=500,
                headers={"Content-Type": "application/json"},
            )

    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil

            process = psutil.Process()
            memory_info = process.memory_info()
            return memory_info.rss / 1024 / 1024  # Convert to MB
        except ImportError:
            return 0.0
        except Exception:
            return 0.0

    def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        try:
            import psutil

            process = psutil.Process()
            return process.cpu_percent()
        except ImportError:
            return 0.0
        except Exception:
            return 0.0

    def update_websocket_metrics(self, metrics: dict):
        """Update WebSocket metrics (called by main service)."""
        # This method would be called by the main service to update
        # the metrics with real-time data
        pass

    def update_nats_metrics(self, metrics: dict):
        """Update NATS metrics (called by main service)."""
        # This method would be called by the main service to update
        # the metrics with real-time data
        pass
