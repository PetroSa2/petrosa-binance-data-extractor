"""
Candle model for the MongoDB ``candles_{SYMBOL}_{timeframe}`` namespace (#300).

This is the *execution* view of a kline. It is deliberately a different shape
from :class:`models.kline.KlineModel`:

- ``KlineModel`` is the Binance-faithful record persisted to the MySQL
  ``klines_*`` tables (open_time/close_time, taker volumes, derived price
  change fields).
- ``CandleModel`` is the canonical OHLCV document that
  ``petrosa-data-manager`` serves to strategy consumers from the Mongo
  ``candles_*`` collections. Its field names mirror
  ``data_manager.models.market_data.Candle`` exactly so a document written by
  this extractor is indistinguishable from one written by
  ``data_manager/maintenance/candle_warmup_backfill.py``.

Idempotency note: ``petrosa-data-manager``'s MongoDB adapter derives
``_id = f"{symbol}_{timestamp_ms}"`` on write and inserts with
``ordered=False``, so re-mirroring an already-present candle is a no-op rather
than a duplicate. That is why this model keeps ``symbol`` and ``timestamp`` as
top-level fields and does not invent its own primary key.
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict, Field, field_validator

import constants
from models.base import BaseSymbolModel

if TYPE_CHECKING:  # pragma: no cover - typing only
    from models.kline import KlineModel


def candle_collection_name(symbol: str, timeframe: str) -> str:
    """Return the Mongo collection holding candles for ``symbol``/``timeframe``.

    Mirrors ``data_manager.db.repositories.candle_repository.
    mongo_collection_name`` — the two MUST stay in lockstep, otherwise the gap
    filler writes into a namespace nothing reads from.
    """
    return f"{constants.CANDLES_COLLECTION_PREFIX}_{symbol.upper()}_{timeframe}"


class CandleModel(BaseSymbolModel):
    """Canonical OHLCV candle document for the Mongo ``candles_*`` namespace."""

    open: Decimal = Field(..., description="Open price")
    high: Decimal = Field(..., description="High price")
    low: Decimal = Field(..., description="Low price")
    close: Decimal = Field(..., description="Close price")
    volume: Decimal = Field(..., description="Base asset volume")
    quote_volume: Decimal | None = Field(None, description="Quote asset volume")
    trades_count: int | None = Field(None, description="Number of trades")
    timeframe: str = Field(..., description="Timeframe (e.g. '5m', '1h')")

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        json_schema_extra={
            "example": {
                "symbol": "BTCUSDT",
                "timestamp": "2026-09-01T00:00:00Z",
                "open": "16500.50",
                "high": "16520.75",
                "low": "16485.25",
                "close": "16510.00",
                "volume": "1234.56789",
                "quote_volume": "20375000.123",
                "trades_count": 1500,
                "timeframe": "5m",
            }
        },
    )

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        """Reject timeframes the extractor does not support."""
        if v not in constants.SUPPORTED_INTERVALS:
            raise ValueError(f"Unsupported timeframe: {v}")
        return v

    @classmethod
    def from_kline(cls, kline: "KlineModel") -> "CandleModel":
        """Project a :class:`models.kline.KlineModel` onto the candle shape.

        ``timestamp`` is taken from the kline's ``open_time`` (falling back to
        its ``timestamp``), which is the same bucket key the data-manager
        warm-up backfill uses. Using ``close_time`` here would shift every
        candle by one interval and silently duplicate every document.
        """
        timestamp = getattr(kline, "open_time", None) or kline.timestamp
        return cls(
            symbol=kline.symbol,
            timestamp=timestamp,
            open=kline.open_price,
            high=kline.high_price,
            low=kline.low_price,
            close=kline.close_price,
            volume=kline.volume,
            quote_volume=kline.quote_asset_volume,
            trades_count=kline.number_of_trades,
            timeframe=kline.interval,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary for database storage."""
        return self.model_dump(exclude={"id"}, mode="json")

    @property
    def collection_name(self) -> str:
        """Return the Mongo collection name for this candle."""
        return candle_collection_name(self.symbol, self.timeframe)
