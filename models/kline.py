"""
Pydantic model for Binance Futures Kline (candlestick) data.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from .base import BaseSymbolModel


class KlineModel(BaseSymbolModel):
    """
    Model for Binance Futures Kline (candlestick) data.

    Represents OHLCV data for a specific time interval.
    """

    # Kline timing
    open_time: datetime = Field(..., description="Kline open time")
    close_time: datetime = Field(..., description="Kline close time")
    interval: str = Field(..., description="Kline interval (e.g., 1m, 5m, 15m, 1h)")

    # OHLCV data
    open_price: Decimal = Field(..., description="Open price")
    high_price: Decimal = Field(..., description="High price")
    low_price: Decimal = Field(..., description="Low price")
    close_price: Decimal = Field(..., description="Close price")
    volume: Decimal = Field(..., description="Volume")

    # Additional Binance-specific fields
    quote_asset_volume: Decimal = Field(..., description="Quote asset volume")
    number_of_trades: int = Field(..., description="Number of trades in this kline")
    taker_buy_base_asset_volume: Decimal = Field(
        ..., description="Taker buy base asset volume"
    )
    taker_buy_quote_asset_volume: Decimal = Field(
        ..., description="Taker buy quote asset volume"
    )

    # Derived fields
    price_change: Decimal | None = Field(
        None, description="Price change (close - open)"
    )
    price_change_percent: Decimal | None = Field(
        None, description="Price change percentage"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbol": "BTCUSDT",
                "timestamp": "2023-01-01T00:00:00Z",
                "open_time": "2023-01-01T00:00:00Z",
                "close_time": "2023-01-01T00:14:59.999Z",
                "interval": "15m",
                "open_price": "16500.50",
                "high_price": "16520.75",
                "low_price": "16485.25",
                "close_price": "16510.00",
                "volume": "1234.56789",
                "quote_asset_volume": "20375000.123",
                "number_of_trades": 1500,
                "taker_buy_base_asset_volume": "617.28394",
                "taker_buy_quote_asset_volume": "10187500.061",
            }
        }
    )

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate trading symbol format."""
        return v.upper()

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, v: str) -> str:
        """Validate interval format."""
        from constants import SUPPORTED_INTERVALS

        if v not in SUPPORTED_INTERVALS:
            raise ValueError(f"Unsupported interval: {v}")
        return v

    @model_validator(mode="after")
    def calculate_derived_fields(self) -> "KlineModel":
        """Calculate derived fields after all fields are set."""
        if self.price_change is None:
            self.price_change = self.close_price - self.open_price

        if self.price_change_percent is None and self.open_price != 0:
            # Calculate percentage and round to 4 decimal places
            percentage = (self.price_change / self.open_price) * Decimal("100")
            self.price_change_percent = percentage.quantize(Decimal("0.0001"))

        return self

    @classmethod
    def from_binance_kline(
        cls, kline_data: list[Any], symbol: str, interval: str
    ) -> "KlineModel":
        """
        Create KlineModel from Binance API kline data array.

        Binance returns klines as arrays with the following structure:
        [
            open_time,           # 0
            open_price,          # 1
            high_price,          # 2
            low_price,           # 3
            close_price,         # 4
            volume,              # 5
            close_time,          # 6
            quote_asset_volume,  # 7
            number_of_trades,    # 8
            taker_buy_base_asset_volume,  # 9
            taker_buy_quote_asset_volume, # 10
            ignore               # 11
        ]
        """
        open_time = datetime.fromtimestamp(int(kline_data[0]) / 1000, tz=UTC)
        close_time = datetime.fromtimestamp(int(kline_data[6]) / 1000, tz=UTC)

        # Calculate derived fields
        open_price = Decimal(kline_data[1])
        close_price = Decimal(kline_data[4])
        price_change = close_price - open_price
        price_change_percent = (
            (price_change / open_price * 100) if open_price != 0 else Decimal(0)
        )
        # Quantize to 4 decimal places to match field constraints
        price_change_percent = price_change_percent.quantize(Decimal("0.0001"))

        return cls(
            symbol=symbol,
            interval=interval,
            timestamp=open_time,  # Use open_time as primary timestamp
            open_time=open_time,
            close_time=close_time,
            open_price=open_price,
            high_price=Decimal(kline_data[2]),
            low_price=Decimal(kline_data[3]),
            close_price=close_price,
            volume=Decimal(kline_data[5]),
            quote_asset_volume=Decimal(kline_data[7]),
            number_of_trades=int(kline_data[8]),
            taker_buy_base_asset_volume=Decimal(kline_data[9]),
            taker_buy_quote_asset_volume=Decimal(kline_data[10]),
            price_change=price_change,
            price_change_percent=price_change_percent,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return self.model_dump(exclude={"id"})  # Exclude UUID for storage

    @property
    def collection_name(self) -> str:
        """Return the database collection name for this model."""
        from utils.time_utils import binance_interval_to_table_suffix

        table_suffix = binance_interval_to_table_suffix(self.interval)
        return f"klines_{table_suffix}"
