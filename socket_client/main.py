#!/usr/bin/env python3
"""
Main entry point for the Petrosa Socket Client.

This module handles the startup, configuration, and graceful shutdown
of the WebSocket client service.
"""

import asyncio
import os
import signal
import sys
from typing import Optional

import typer
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import constants  # noqa: E402
from socket_client.core.client import BinanceWebSocketClient  # noqa: E402
from socket_client.health.server import HealthServer  # noqa: E402
from socket_client.utils.logger import setup_logging  # noqa: E402

# Initialize OpenTelemetry as early as possible
try:
    from otel_init import setup_telemetry  # noqa: E402

    if not os.getenv("OTEL_NO_AUTO_INIT"):
        setup_telemetry(service_name=constants.OTEL_SERVICE_NAME)
except ImportError:
    pass

# Load environment variables
load_dotenv()

app = typer.Typer(help="Petrosa Socket Client - Binance WebSocket client")


class SocketClientService:
    """Main service class for the Socket Client."""

    def __init__(self):
        """Initialize the service."""
        self.logger = setup_logging(level=constants.LOG_LEVEL)
        self.websocket_client: Optional[BinanceWebSocketClient] = None
        self.health_server: Optional[HealthServer] = None
        self.shutdown_event = asyncio.Event()

    async def start(self):
        """Start the service."""
        self.logger.info("Starting Petrosa Socket Client service")

        try:
            # Start health server
            self.health_server = HealthServer(
                port=constants.HEALTH_CHECK_PORT, logger=self.logger
            )
            await self.health_server.start()
            self.logger.info(
                f"Health server started on port {constants.HEALTH_CHECK_PORT}"
            )

            # Start WebSocket client
            self.websocket_client = BinanceWebSocketClient(
                ws_url=constants.BINANCE_WS_URL,
                streams=constants.get_streams(),
                nats_url=constants.NATS_URL,
                nats_topic=constants.NATS_TOPIC,
                logger=self.logger,
            )
            await self.websocket_client.start()
            self.logger.info("WebSocket client started successfully")

            # Wait for shutdown signal
            await self.shutdown_event.wait()

        except Exception as e:
            self.logger.error(f"Error starting service: {e}")
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Stop the service gracefully."""
        self.logger.info("Stopping Petrosa Socket Client service")

        # Stop WebSocket client
        if self.websocket_client:
            await self.websocket_client.stop()
            self.logger.info("WebSocket client stopped")

        # Stop health server
        if self.health_server:
            await self.health_server.stop()
            self.logger.info("Health server stopped")

        self.logger.info("Service stopped gracefully")


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print(f"\nReceived signal {signum}, shutting down gracefully...")
    if hasattr(signal_handler, "service"):
        asyncio.create_task(signal_handler.service.shutdown_event.set())


@app.command()
def run(
    ws_url: Optional[str] = typer.Option(
        None, "--ws-url", help="Binance WebSocket URL"
    ),
    streams: Optional[str] = typer.Option(
        None, "--streams", help="Comma-separated list of streams"
    ),
    nats_url: Optional[str] = typer.Option(None, "--nats-url", help="NATS server URL"),
    nats_topic: Optional[str] = typer.Option(
        None, "--nats-topic", help="NATS topic for publishing"
    ),
    log_level: str = typer.Option(
        constants.LOG_LEVEL, "--log-level", help="Logging level"
    ),
):
    """Run the Socket Client service."""
    # Override constants with command line arguments
    if ws_url:
        os.environ["BINANCE_WS_URL"] = ws_url
    if streams:
        os.environ["BINANCE_STREAMS"] = streams
    if nats_url:
        os.environ["NATS_URL"] = nats_url
    if nats_topic:
        os.environ["NATS_TOPIC"] = nats_topic
    if log_level:
        os.environ["LOG_LEVEL"] = log_level

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create and run service
    service = SocketClientService()
    signal_handler.service = service

    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Service failed: {e}")
        sys.exit(1)


@app.command()
def health():
    """Check service health."""
    import requests

    try:
        response = requests.get(
            f"http://localhost:{constants.HEALTH_CHECK_PORT}/healthz", timeout=5
        )
        if response.status_code == 200:
            print("✅ Service is healthy")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Service is unhealthy: {response.status_code}")
            sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check failed: {e}")
        sys.exit(1)


@app.command()
def version():
    """Show version information."""
    from socket_client import __version__

    print(f"Petrosa Socket Client v{__version__}")


if __name__ == "__main__":
    app()
