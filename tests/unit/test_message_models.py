"""
Unit tests for message models.
"""

from datetime import datetime

import pytest

from socket_client.models.message import (
    DepthMessage,
    TickerMessage,
    TradeMessage,
    WebSocketMessage,
    create_message,
    validate_message,
)


class TestWebSocketMessage:
    """Test WebSocket message model."""

    def test_create_websocket_message(self):
        """Test creating a basic WebSocket message."""
        message = WebSocketMessage(
            stream="btcusdt@trade", data={"price": "50000", "quantity": "1.0"}
        )

        assert message.stream == "btcusdt@trade"
        assert message.data == {"price": "50000", "quantity": "1.0"}
        assert isinstance(message.timestamp, datetime)
        assert message.message_id is None

    def test_create_message_with_id(self):
        """Test creating a message with custom ID."""
        message = WebSocketMessage(
            stream="btcusdt@trade", data={"price": "50000"}, message_id="test-123"
        )

        assert message.message_id == "test-123"

    def test_to_nats_message(self):
        """Test converting to NATS message format."""
        message = WebSocketMessage(stream="btcusdt@trade", data={"price": "50000"})

        nats_message = message.to_nats_message()

        assert nats_message["stream"] == "btcusdt@trade"
        assert nats_message["data"] == {"price": "50000"}
        assert "timestamp" in nats_message
        assert nats_message["source"] == "binance-websocket"
        assert nats_message["version"] == "1.0"

    def test_to_json(self):
        """Test converting to JSON string."""
        message = WebSocketMessage(stream="btcusdt@trade", data={"price": "50000"})

        json_str = message.to_json()
        assert isinstance(json_str, str)

        # Parse back to verify
        import json

        parsed = json.loads(json_str)
        assert parsed["stream"] == "btcusdt@trade"
        assert parsed["data"] == {"price": "50000"}


class TestTradeMessage:
    """Test trade message model."""

    def test_create_trade_message(self):
        """Test creating a trade message."""
        trade_data = {
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
        }

        message = TradeMessage(stream="btcusdt@trade", data=trade_data)

        assert message.stream == "btcusdt@trade"
        assert message.data == trade_data
        assert message.data["e"] == "trade"


class TestTickerMessage:
    """Test ticker message model."""

    def test_create_ticker_message(self):
        """Test creating a ticker message."""
        ticker_data = {
            "e": "24hrTicker",
            "E": 123456789,
            "s": "BTCUSDT",
            "p": "0.0015",
            "P": "250.00",
        }

        message = TickerMessage(stream="btcusdt@ticker", data=ticker_data)

        assert message.stream == "btcusdt@ticker"
        assert message.data == ticker_data
        assert message.data["e"] == "24hrTicker"


class TestDepthMessage:
    """Test depth message model."""

    def test_create_depth_message(self):
        """Test creating a depth message."""
        depth_data = {
            "e": "depthUpdate",
            "E": 123456789,
            "s": "BTCUSDT",
            "U": 1,
            "u": 2,
            "b": [["0.0024", "10"]],
            "a": [["0.0026", "100"]],
        }

        message = DepthMessage(stream="btcusdt@depth20@100ms", data=depth_data)

        assert message.stream == "btcusdt@depth20@100ms"
        assert message.data == depth_data
        assert message.data["e"] == "depthUpdate"


class TestCreateMessage:
    """Test message creation factory function."""

    def test_create_trade_message(self):
        """Test creating a trade message via factory."""
        data = {"e": "trade", "s": "BTCUSDT"}
        message = create_message("btcusdt@trade", data)

        assert isinstance(message, TradeMessage)
        assert message.stream == "btcusdt@trade"

    def test_create_ticker_message(self):
        """Test creating a ticker message via factory."""
        data = {"e": "24hrTicker", "s": "BTCUSDT"}
        message = create_message("btcusdt@ticker", data)

        assert isinstance(message, TickerMessage)
        assert message.stream == "btcusdt@ticker"

    def test_create_depth_message(self):
        """Test creating a depth message via factory."""
        data = {"e": "depthUpdate", "s": "BTCUSDT"}
        message = create_message("btcusdt@depth20@100ms", data)

        assert isinstance(message, DepthMessage)
        assert message.stream == "btcusdt@depth20@100ms"

    def test_create_generic_message(self):
        """Test creating a generic message for unknown stream."""
        data = {"test": "data"}
        message = create_message("unknown@stream", data)

        assert isinstance(message, WebSocketMessage)
        assert message.stream == "unknown@stream"


class TestValidateMessage:
    """Test message validation."""

    def test_validate_valid_message(self):
        """Test validating a valid message."""
        message_dict = {
            "stream": "btcusdt@trade",
            "data": {"e": "trade", "s": "BTCUSDT"},
        }

        message = validate_message(message_dict)
        assert isinstance(message, TradeMessage)
        assert message.stream == "btcusdt@trade"

    def test_validate_message_missing_stream(self):
        """Test validating message with missing stream."""
        message_dict = {"data": {"e": "trade"}}

        with pytest.raises(ValueError, match="Missing required field"):
            validate_message(message_dict)

    def test_validate_message_missing_data(self):
        """Test validating message with missing data."""
        message_dict = {"stream": "btcusdt@trade"}

        with pytest.raises(ValueError, match="Missing required field"):
            validate_message(message_dict)

    def test_validate_message_invalid_format(self):
        """Test validating message with invalid format."""
        message_dict = "invalid"

        with pytest.raises(ValueError, match="Invalid message format"):
            validate_message(message_dict)
