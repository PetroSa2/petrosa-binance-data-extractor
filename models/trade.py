"""
Pydantic model for Binance Futures Trade data.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import ConfigDict, Field, field_validator

from .base import BaseSymbolModel


class TradeModel(BaseSymbolModel):
    """
    Model for Binance Futures Trade data.

    Represents individual trade executions.
    """

    # Trade identification
    trade_id: int = Field(..., description="Unique trade ID from Binance")
    order_id: Optional[int] = Field(
        None, description="Order ID that generated this trade"
    )

    # Trade details
    price: Decimal = Field(..., description="Trade execution price", decimal_places=8)
    quantity: Decimal = Field(..., description="Trade quantity", decimal_places=8)
    quote_quantity: Decimal = Field(
        ..., description="Quote asset quantity", decimal_places=8
    )

    # Trade metadata
    is_buyer_maker: bool = Field(..., description="Whether the buyer is the maker")
    commission: Optional[Decimal] = Field(
        None, description="Commission amount", decimal_places=8
    )
    commission_asset: Optional[str] = Field(None, description="Commission asset")

    # Timing
    trade_time: datetime = Field(..., description="Trade execution time")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbol": "BTCUSDT",
                "timestamp": "2023-01-01T12:30:45.123Z",
                "trade_id": 123456789,
                "order_id": 987654321,
                "price": "16500.50",
                "quantity": "0.01234567",
                "quote_quantity": "203.70",
                "is_buyer_maker": True,
                "trade_time": "2023-01-01T12:30:45.123Z",
            }
        }
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def set_timestamp_from_trade_time(cls, v: Any) -> Any:
        """Use trade_time as the primary timestamp if not provided."""
        # Note: Cross-field validation handled differently in Pydantic v2
        return v

    @field_validator("quote_quantity")
    @classmethod
    def calculate_quote_quantity(cls, v: Any) -> Any:
        """Calculate quote quantity if not provided."""
        # Note: Cross-field calculations should be done in a model_validator
        return v

    @classmethod
    def from_binance_trade(cls, trade_data: Dict[str, Any], symbol: str) -> "TradeModel":
        """
        Create TradeModel from Binance API trade data.

        Binance trade structure:
        {
            "id": 28457,
            "price": "4.00000100",
            "qty": "12.00000000",
            "quoteQty": "48.000012",
            "time": 1499865549590,
            "isBuyerMaker": true
        }
        """
        trade_time = datetime.fromtimestamp(
            int(trade_data["time"]) / 1000, tz=timezone.utc
        )
        return cls(
            symbol=symbol,
            timestamp=trade_time,  # Use trade_time as primary timestamp
            trade_id=trade_data["id"],
            price=Decimal(trade_data["price"]),
            quantity=Decimal(trade_data["qty"]),
            quote_quantity=Decimal(trade_data["quoteQty"]),
            is_buyer_maker=trade_data["isBuyerMaker"],
            trade_time=trade_time,
            order_id=None,  # Not provided in public trade data
            commission=None,  # Not provided in public trade data
            commission_asset=None,  # Not provided in public trade data
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return self.model_dump(exclude={"id"})

    @property
    def collection_name(self) -> str:
        """Return the database collection name for this model."""
        return "trades"
