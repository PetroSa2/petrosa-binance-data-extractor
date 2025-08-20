"""
Binance WebSocket client implementation.

This module provides the main WebSocket client that connects to Binance
and forwards messages to NATS with proper error handling and reconnection logic.
"""

import asyncio
import json
import time
import uuid
from typing import Optional

import nats
import websockets
from nats.aio.client import Client as NATSClient
from structlog import get_logger

import constants
from socket_client.models.message import create_message
from socket_client.utils.circuit_breaker import (
    nats_circuit_breaker,
    websocket_circuit_breaker,
)

logger = get_logger(__name__)


class BinanceWebSocketClient:
    """Binance WebSocket client with NATS integration."""

    def __init__(
        self,
        ws_url: str,
        streams: list[str],
        nats_url: str,
        nats_topic: str,
        logger=None,
        max_reconnect_attempts: int = None,
        reconnect_delay: int = None,
        ping_interval: int = None,
        ping_timeout: int = None,
    ):
        """
        Initialize the WebSocket client.

        Args:
            ws_url: Binance WebSocket URL
            streams: List of streams to subscribe to
            nats_url: NATS server URL
            nats_topic: NATS topic for publishing messages
            logger: Logger instance
            max_reconnect_attempts: Maximum reconnection attempts
            reconnect_delay: Reconnection delay in seconds
            ping_interval: WebSocket ping interval
            ping_timeout: WebSocket ping timeout
        """
        self.ws_url = ws_url
        self.streams = streams
        self.nats_url = nats_url
        self.nats_topic = nats_topic
        self.logger = logger or get_logger(__name__)

        # Connection settings
        self.max_reconnect_attempts = (
            max_reconnect_attempts or constants.WEBSOCKET_MAX_RECONNECT_ATTEMPTS
        )
        self.reconnect_delay = reconnect_delay or constants.WEBSOCKET_RECONNECT_DELAY
        self.ping_interval = ping_interval or constants.WEBSOCKET_PING_INTERVAL
        self.ping_timeout = ping_timeout or constants.WEBSOCKET_PING_TIMEOUT

        # Connection state
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.nats_client: Optional[NATSClient] = None
        self.is_connected = False
        self.is_running = False
        self.reconnect_attempts = 0
        self.last_ping = 0

        # Message processing
        self.message_queue = asyncio.Queue(maxsize=constants.MAX_QUEUE_SIZE)
        self.processed_messages = 0
        self.dropped_messages = 0
        self.last_message_time = 0

        # Tasks
        self.websocket_task: Optional[asyncio.Task] = None
        self.nats_task: Optional[asyncio.Task] = None
        self.processor_task: Optional[asyncio.Task] = None
        self.ping_task: Optional[asyncio.Task] = None

        self.logger.info(
            "WebSocket client initialized",
            ws_url=ws_url,
            streams=streams,
            nats_url=nats_url,
            nats_topic=nats_topic,
        )

    async def start(self):
        """Start the WebSocket client."""
        self.logger.info("Starting WebSocket client")
        self.is_running = True

        try:
            # Start NATS connection
            await self._connect_nats()

            # Start message processor
            self.processor_task = asyncio.create_task(self._process_messages())

            # Start WebSocket connection
            await self._connect_websocket()

            # Start ping task
            self.ping_task = asyncio.create_task(self._ping_loop())

            self.logger.info("WebSocket client started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start WebSocket client: {e}")
            await self.stop()
            raise

    async def stop(self):
        """Stop the WebSocket client gracefully."""
        self.logger.info("Stopping WebSocket client")
        self.is_running = False

        # Cancel tasks
        for task in [
            self.websocket_task,
            self.nats_task,
            self.processor_task,
            self.ping_task,
        ]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close connections
        if self.websocket:
            await self.websocket.close()

        if self.nats_client:
            await self.nats_client.close()

        self.is_connected = False
        self.logger.info("WebSocket client stopped")

    async def _connect_websocket(self):
        """Connect to Binance WebSocket."""
        try:
            # Build subscription message
            subscribe_message = {
                "method": "SUBSCRIBE",
                "params": self.streams,
                "id": int(time.time() * 1000),
            }

            # Connect with circuit breaker protection
            self.websocket = await websocket_circuit_breaker.call(
                websockets.connect,
                self.ws_url,
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout,
                close_timeout=constants.WEBSOCKET_CLOSE_TIMEOUT,
            )

            # Send subscription message
            await self.websocket.send(json.dumps(subscribe_message))

            # Start WebSocket listener
            self.websocket_task = asyncio.create_task(self._websocket_listener())

            self.is_connected = True
            self.reconnect_attempts = 0

            self.logger.info(
                "Connected to Binance WebSocket", streams=self.streams, url=self.ws_url
            )

        except Exception as e:
            self.logger.error(f"Failed to connect to WebSocket: {e}")
            self.is_connected = False
            raise

    async def _connect_nats(self):
        """Connect to NATS server."""
        try:
            self.nats_client = await nats_circuit_breaker.call(
                nats.connect, self.nats_url, name=constants.NATS_CLIENT_NAME
            )

            self.logger.info(f"Connected to NATS server: {self.nats_url}")

        except Exception as e:
            self.logger.error(f"Failed to connect to NATS: {e}")
            raise

    async def _websocket_listener(self):
        """Listen for WebSocket messages."""
        try:
            async for message in self.websocket:
                if not self.is_running:
                    break

                try:
                    # Parse message
                    data = json.loads(message)

                    # Update last message time
                    self.last_message_time = time.time()

                    # Add to processing queue
                    try:
                        self.message_queue.put_nowait(data)
                    except asyncio.QueueFull:
                        self.dropped_messages += 1
                        self.logger.warning(
                            "Message queue full, dropping message",
                            dropped_count=self.dropped_messages,
                        )

                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse WebSocket message: {e}")
                except Exception as e:
                    self.logger.error(f"Error processing WebSocket message: {e}")

        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("WebSocket connection closed")
        except Exception as e:
            self.logger.error(f"WebSocket listener error: {e}")
        finally:
            self.is_connected = False
            await self._handle_disconnection()

    async def _process_messages(self):
        """Process messages from the queue and publish to NATS."""
        while self.is_running:
            try:
                # Get message from queue with timeout
                try:
                    data = await asyncio.wait_for(
                        self.message_queue.get(),
                        timeout=constants.MESSAGE_BATCH_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    continue

                # Process message
                await self._process_single_message(data)

                # Mark as done
                self.message_queue.task_done()

            except Exception as e:
                self.logger.error(f"Error processing message: {e}")

    async def _process_single_message(self, data: dict):
        """Process a single message."""
        try:
            # Validate message format
            if not isinstance(data, dict) or "stream" not in data or "data" not in data:
                self.logger.warning("Invalid message format", data=data)
                return

            # Create message object
            message = create_message(
                stream=data["stream"], data=data["data"], message_id=str(uuid.uuid4())
            )

            # Publish to NATS
            if self.nats_client and not self.nats_client.is_closed:
                try:
                    await self.nats_client.publish(
                        self.nats_topic, message.to_json().encode("utf-8")
                    )

                    self.processed_messages += 1

                    if self.processed_messages % 100 == 0:
                        self.logger.info(
                            "Message processing stats",
                            processed=self.processed_messages,
                            dropped=self.dropped_messages,
                        )

                except Exception as e:
                    self.logger.error(f"Failed to publish to NATS: {e}")
            else:
                self.logger.warning("NATS client not connected, dropping message")
                self.dropped_messages += 1

        except Exception as e:
            self.logger.error(f"Error processing single message: {e}")

    async def _ping_loop(self):
        """Send periodic pings to keep connection alive."""
        while self.is_running and self.is_connected:
            try:
                await asyncio.sleep(self.ping_interval)

                if self.websocket and not self.websocket.closed:
                    await self.websocket.ping()
                    self.last_ping = time.time()

            except Exception as e:
                self.logger.error(f"Ping error: {e}")
                break

    async def _handle_disconnection(self):
        """Handle WebSocket disconnection with reconnection logic."""
        if not self.is_running:
            return

        self.logger.warning("WebSocket disconnected, attempting reconnection")

        while self.is_running and self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                await asyncio.sleep(self.reconnect_delay * (2**self.reconnect_attempts))

                self.logger.info(
                    f"Attempting reconnection {self.reconnect_attempts + 1}/{self.max_reconnect_attempts}"
                )

                await self._connect_websocket()
                break

            except Exception as e:
                self.reconnect_attempts += 1
                self.logger.error(
                    f"Reconnection attempt {self.reconnect_attempts} failed: {e}"
                )

        if self.reconnect_attempts >= self.max_reconnect_attempts:
            self.logger.error("Max reconnection attempts reached, stopping client")
            self.is_running = False

    def get_metrics(self) -> dict:
        """Get client metrics."""
        return {
            "is_connected": self.is_connected,
            "is_running": self.is_running,
            "reconnect_attempts": self.reconnect_attempts,
            "processed_messages": self.processed_messages,
            "dropped_messages": self.dropped_messages,
            "queue_size": self.message_queue.qsize(),
            "last_message_time": self.last_message_time,
            "last_ping": self.last_ping,
            "websocket_state": "connected"
            if self.websocket and not self.websocket.closed
            else "disconnected",
            "nats_state": "connected"
            if self.nats_client and not self.nats_client.is_closed
            else "disconnected",
        }
