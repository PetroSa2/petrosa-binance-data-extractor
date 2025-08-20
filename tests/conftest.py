"""
Pytest configuration and fixtures for the Socket Client service.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from socket_client.core.client import BinanceWebSocketClient


@pytest.fixture
def sample_trade_message() -> dict:
    """Sample trade message from Binance WebSocket."""
    return {
        "stream": "btcusdt@trade",
        "data": {
            "e": "trade",
            "E": 123456789,
            "s": "BTCUSDT",
            "t": 12345,
            "p": "0.001",
            "q": "100",
            "b": 88,
            "a": 50,
            "T": 123456785,
            "m": True,
            "M": True,
        },
    }


@pytest.fixture
def sample_ticker_message() -> dict:
    """Sample ticker message from Binance WebSocket."""
    return {
        "stream": "btcusdt@ticker",
        "data": {
            "e": "24hrTicker",
            "E": 123456789,
            "s": "BTCUSDT",
            "p": "0.0015",
            "P": "250.00",
            "w": "0.0018",
            "x": "0.0009",
            "c": "0.0025",
            "Q": "10",
            "b": "4.00000000",
            "B": "431.00000000",
            "a": "4.00000200",
            "A": "12.00000000",
            "o": "0.00150000",
            "h": "0.00250000",
            "l": "0.00100000",
            "v": "10000.00000000",
            "q": "18.00000000",
            "O": 0,
            "C": 86400000,
            "F": 0,
            "L": 18150,
            "n": 18151,
        },
    }


@pytest.fixture
def sample_depth_message() -> dict:
    """Sample depth message from Binance WebSocket."""
    return {
        "stream": "btcusdt@depth20@100ms",
        "data": {
            "e": "depthUpdate",
            "E": 123456789,
            "s": "BTCUSDT",
            "U": 1,
            "u": 2,
            "b": [["0.0024", "10"], ["0.0022", "5"]],
            "a": [["0.0026", "100"], ["0.0028", "50"]],
        },
    }


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    mock_ws = AsyncMock()
    mock_ws.closed = False
    mock_ws.send = AsyncMock()
    mock_ws.close = AsyncMock()
    return mock_ws


@pytest.fixture
def mock_nats_client():
    """Mock NATS client."""
    mock_nats = AsyncMock()
    mock_nats.is_closed = False
    mock_nats.publish = AsyncMock()
    mock_nats.close = AsyncMock()
    return mock_nats


@pytest.fixture
def websocket_client(mock_websocket, mock_nats_client):
    """WebSocket client with mocked dependencies."""
    client = BinanceWebSocketClient(
        ws_url="wss://test.binance.com",
        streams=["btcusdt@trade"],
        nats_url="nats://localhost:4222",
        nats_topic="test.topic",
    )

    # Mock the connections
    client.websocket = mock_websocket
    client.nats_client = mock_nats_client

    return client


@pytest.fixture
def test_streams() -> list[str]:
    """Test streams for WebSocket client."""
    return ["btcusdt@trade", "btcusdt@ticker", "ethusdt@trade"]


@pytest.fixture
def test_config() -> dict:
    """Test configuration."""
    return {
        "ws_url": "wss://test.binance.com",
        "nats_url": "nats://localhost:4222",
        "nats_topic": "test.topic",
        "streams": ["btcusdt@trade"],
        "max_reconnect_attempts": 3,
        "reconnect_delay": 1,
    }


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_websockets_connect(monkeypatch):
    """Mock websockets.connect."""
    mock_connect = AsyncMock()
    monkeypatch.setattr("websockets.connect", mock_connect)
    return mock_connect


@pytest.fixture
def mock_nats_connect(monkeypatch):
    """Mock nats.connect."""
    mock_connect = AsyncMock()
    monkeypatch.setattr("nats.connect", mock_connect)
    return mock_connect


@pytest.fixture
def mock_aiohttp_client_session(monkeypatch):
    """Mock aiohttp ClientSession."""
    mock_session = AsyncMock()
    mock_session.get = AsyncMock()
    mock_session.post = AsyncMock()
    mock_session.close = AsyncMock()

    mock_client_session = AsyncMock()
    mock_client_session.__aenter__.return_value = mock_session
    mock_client_session.__aexit__.return_value = None

    monkeypatch.setattr("aiohttp.ClientSession", mock_client_session)
    return mock_session
