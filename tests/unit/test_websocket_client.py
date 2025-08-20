"""
Unit tests for WebSocket client.
"""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from socket_client.core.client import BinanceWebSocketClient


class TestBinanceWebSocketClient:
    """Test WebSocket client functionality."""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initialization."""
        client = BinanceWebSocketClient(
            ws_url="wss://test.binance.com",
            streams=["btcusdt@trade"],
            nats_url="nats://localhost:4222",
            nats_topic="test.topic",
        )

        assert client.ws_url == "wss://test.binance.com"
        assert client.streams == ["btcusdt@trade"]
        assert client.nats_url == "nats://localhost:4222"
        assert client.nats_topic == "test.topic"
        assert not client.is_connected
        assert not client.is_running

    @pytest.mark.asyncio
    async def test_connect_nats(self, mock_nats_connect):
        """Test NATS connection."""
        client = BinanceWebSocketClient(
            ws_url="wss://test.binance.com",
            streams=["btcusdt@trade"],
            nats_url="nats://localhost:4222",
            nats_topic="test.topic",
        )

        mock_nats_connect.return_value = AsyncMock()

        await client._connect_nats()

        assert client.nats_client is not None
        mock_nats_connect.assert_called_once_with(
            "nats://localhost:4222", name="petrosa-socket-client"
        )

    @pytest.mark.asyncio
    async def test_connect_websocket(self, mock_websockets_connect):
        """Test WebSocket connection."""
        client = BinanceWebSocketClient(
            ws_url="wss://test.binance.com",
            streams=["btcusdt@trade"],
            nats_url="nats://localhost:4222",
            nats_topic="test.topic",
        )

        mock_ws = AsyncMock()
        mock_websockets_connect.return_value = mock_ws

        await client._connect_websocket()

        assert client.websocket is not None
        assert client.is_connected
        assert client.reconnect_attempts == 0

        # Verify subscription message was sent
        mock_ws.send.assert_called_once()
        call_args = mock_ws.send.call_args[0][0]
        subscription = json.loads(call_args)
        assert subscription["method"] == "SUBSCRIBE"
        assert subscription["params"] == ["btcusdt@trade"]

    @pytest.mark.asyncio
    async def test_process_single_message(self, websocket_client, sample_trade_message):
        """Test processing a single message."""
        # Mock NATS publish
        websocket_client.nats_client.publish = AsyncMock()

        await websocket_client._process_single_message(sample_trade_message)

        # Verify NATS publish was called
        websocket_client.nats_client.publish.assert_called_once()
        assert websocket_client.processed_messages == 1

    @pytest.mark.asyncio
    async def test_process_invalid_message(self, websocket_client):
        """Test processing an invalid message."""
        invalid_message = {"invalid": "format"}

        await websocket_client._process_single_message(invalid_message)

        # Should not publish to NATS
        websocket_client.nats_client.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_nats_disconnected(
        self, websocket_client, sample_trade_message
    ):
        """Test processing message when NATS is disconnected."""
        websocket_client.nats_client.is_closed = True

        await websocket_client._process_single_message(sample_trade_message)

        # Should increment dropped messages
        assert websocket_client.dropped_messages == 1

    @pytest.mark.asyncio
    async def test_websocket_listener(self, websocket_client, sample_trade_message):
        """Test WebSocket message listener."""

        # Mock the websocket to return a message
        async def mock_iter():
            yield json.dumps(sample_trade_message)

        websocket_client.websocket.__aiter__ = mock_iter
        websocket_client.nats_client.publish = AsyncMock()

        # Start listener
        task = asyncio.create_task(websocket_client._websocket_listener())

        # Wait a bit for processing
        await asyncio.sleep(0.1)

        # Cancel task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify message was processed
        websocket_client.nats_client.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_listener_invalid_json(self, websocket_client):
        """Test WebSocket listener with invalid JSON."""

        # Mock the websocket to return invalid JSON
        async def mock_iter():
            yield "invalid json"

        websocket_client.websocket.__aiter__ = mock_iter

        # Start listener
        task = asyncio.create_task(websocket_client._websocket_listener())

        # Wait a bit for processing
        await asyncio.sleep(0.1)

        # Cancel task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should not publish to NATS
        websocket_client.nats_client.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_ping_loop(self, websocket_client):
        """Test ping loop functionality."""
        websocket_client.is_running = True
        websocket_client.is_connected = True

        # Start ping loop
        task = asyncio.create_task(websocket_client._ping_loop())

        # Wait for ping
        await asyncio.sleep(0.1)

        # Cancel task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify ping was sent
        websocket_client.websocket.ping.assert_called()

    @pytest.mark.asyncio
    async def test_handle_disconnection(
        self, websocket_client, mock_websockets_connect
    ):
        """Test handling WebSocket disconnection."""
        websocket_client.is_running = True
        websocket_client.max_reconnect_attempts = 2

        # Mock successful reconnection
        mock_ws = AsyncMock()
        mock_websockets_connect.return_value = mock_ws

        # Start disconnection handler
        task = asyncio.create_task(websocket_client._handle_disconnection())

        # Wait for reconnection attempt
        await asyncio.sleep(0.1)

        # Cancel task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify reconnection was attempted
        mock_websockets_connect.assert_called()

    @pytest.mark.asyncio
    async def test_start_and_stop(self, mock_websockets_connect, mock_nats_connect):
        """Test starting and stopping the client."""
        client = BinanceWebSocketClient(
            ws_url="wss://test.binance.com",
            streams=["btcusdt@trade"],
            nats_url="nats://localhost:4222",
            nats_topic="test.topic",
        )

        # Mock connections
        mock_ws = AsyncMock()
        mock_nats = AsyncMock()
        mock_websockets_connect.return_value = mock_ws
        mock_nats_connect.return_value = mock_nats

        # Start client
        start_task = asyncio.create_task(client.start())

        # Wait a bit for startup
        await asyncio.sleep(0.1)

        # Stop client
        await client.stop()

        # Cancel start task
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

        # Verify connections were closed
        mock_ws.close.assert_called()
        mock_nats.close.assert_called()

    def test_get_metrics(self, websocket_client):
        """Test getting client metrics."""
        metrics = websocket_client.get_metrics()

        assert "is_connected" in metrics
        assert "is_running" in metrics
        assert "processed_messages" in metrics
        assert "dropped_messages" in metrics
        assert "queue_size" in metrics
        assert "websocket_state" in metrics
        assert "nats_state" in metrics
