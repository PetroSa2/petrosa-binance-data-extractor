"""
Message models for WebSocket data.

This module defines the data structures for WebSocket messages
with validation using Pydantic.
"""

from datetime import datetime
from typing import Any, Optional

import orjson
from pydantic import BaseModel, Field, validator


class WebSocketMessage(BaseModel):
    """Base model for WebSocket messages."""

    stream: str = Field(..., description="Stream name")
    data: dict[str, Any] = Field(..., description="Message data")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Message timestamp"
    )
    message_id: Optional[str] = Field(None, description="Unique message ID")

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat() + "Z"}
        use_enum_values = True

    @validator("timestamp", pre=True)
    def parse_timestamp(cls, v):
        """Parse timestamp from various formats."""
        if isinstance(v, str):
            # Remove Z suffix if present and parse
            if v.endswith("Z"):
                v = v[:-1]
            return datetime.fromisoformat(v)
        return v

    def to_nats_message(self) -> dict[str, Any]:
        """Convert to NATS message format."""
        return {
            "stream": self.stream,
            "data": self.data,
            "timestamp": self.timestamp.isoformat() + "Z",
            "message_id": self.message_id,
            "source": "binance-websocket",
            "version": "1.0",
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return orjson.dumps(self.to_nats_message()).decode("utf-8")


class TradeMessage(WebSocketMessage):
    """Model for trade messages."""

    class Config:
        """Pydantic configuration."""

        schema_extra = {
            "example": {
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
        }


class TickerMessage(WebSocketMessage):
    """Model for ticker messages."""

    class Config:
        """Pydantic configuration."""

        schema_extra = {
            "example": {
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
        }


class DepthMessage(WebSocketMessage):
    """Model for order book depth messages."""

    class Config:
        """Pydantic configuration."""

        schema_extra = {
            "example": {
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
        }


class HealthMessage(BaseModel):
    """Model for health check messages."""

    status: str = Field(..., description="Health status")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Health check timestamp"
    )
    service: str = Field("socket-client", description="Service name")
    version: str = Field("1.0.0", description="Service version")
    uptime: Optional[float] = Field(None, description="Service uptime in seconds")
    metrics: Optional[dict[str, Any]] = Field(None, description="Service metrics")

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat() + "Z"}


def create_message(
    stream: str, data: dict[str, Any], message_id: Optional[str] = None
) -> WebSocketMessage:
    """
    Create a WebSocket message based on stream type.

    Args:
        stream: Stream name
        data: Message data
        message_id: Optional message ID

    Returns:
        WebSocket message instance
    """
    if "@trade" in stream:
        return TradeMessage(stream=stream, data=data, message_id=message_id)
    elif "@ticker" in stream:
        return TickerMessage(stream=stream, data=data, message_id=message_id)
    elif "@depth" in stream:
        return DepthMessage(stream=stream, data=data, message_id=message_id)
    else:
        return WebSocketMessage(stream=stream, data=data, message_id=message_id)


def validate_message(message_dict: dict[str, Any]) -> WebSocketMessage:
    """
    Validate and create a message from dictionary.

    Args:
        message_dict: Message dictionary

    Returns:
        Validated WebSocket message

    Raises:
        ValueError: If message is invalid
    """
    try:
        return create_message(
            stream=message_dict["stream"],
            data=message_dict["data"],
            message_id=message_dict.get("message_id"),
        )
    except KeyError as e:
        raise ValueError(f"Missing required field: {e}")
    except Exception as e:
        raise ValueError(f"Invalid message format: {e}")
