"""
Pydantic model for Binance Futures Funding Rate data.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import ConfigDict, Field, field_validator

from .base import BaseSymbolModel


class FundingRateModel(BaseSymbolModel):
    """
    Model for Binance Futures Funding Rate data.

    Represents funding rate information for perpetual contracts.
    """

    # Funding rate details
    funding_rate: Decimal = Field(
        ..., description="Current funding rate", decimal_places=8
    )
    funding_time: datetime = Field(..., description="Next funding time")
    mark_price: Optional[Decimal] = Field(
        None, description="Current mark price", decimal_places=8
    )
    index_price: Optional[Decimal] = Field(
        None, description="Current index price", decimal_places=8
    )

    # Historical funding rate (if available)
    last_funding_rate: Optional[Decimal] = Field(
        None, description="Previous funding rate", decimal_places=8
    )

    # Funding interval (usually 8 hours for most symbols)
    funding_interval_hours: int = Field(
        default=8, description="Funding interval in hours"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbol": "BTCUSDT",
                "timestamp": "2023-01-01T08:00:00Z",
                "funding_rate": "0.00010000",
                "funding_time": "2023-01-01T16:00:00Z",
                "mark_price": "16500.50",
                "index_price": "16498.75",
                "funding_interval_hours": 8,
            }
        }
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def set_timestamp_from_funding_time(cls, v: Any) -> Any:
        """Use funding_time as the primary timestamp if not provided."""
        # Note: Cross-field validation handled differently in Pydantic v2
        return v

    @classmethod
    def from_binance_funding_rate(
        cls, funding_data: Dict[str, Any], symbol: str
    ) -> "FundingRateModel":
        """
        Create FundingRateModel from Binance API funding rate data.

        Binance funding rate structure:
        {
            "symbol": "BTCUSDT",
            "fundingRate": "0.00010000",
            "fundingTime": 1640995200000,
            "markPrice": "46600.00000000"
        }
        """
        funding_time = datetime.fromtimestamp(
            int(funding_data["fundingTime"]) / 1000, tz=timezone.utc
        )
        return cls(
            symbol=symbol,
            timestamp=funding_time,  # Use funding_time as primary timestamp
            funding_rate=Decimal(funding_data["fundingRate"]),
            funding_time=funding_time,
            mark_price=(
                Decimal(funding_data.get("markPrice", "0"))
                if funding_data.get("markPrice")
                else None
            ),
            index_price=None,  # Not provided in funding rate history
            last_funding_rate=None,  # Not provided in funding rate history
        )

    @classmethod
    def from_binance_premium_index(
        cls, premium_data: Dict[str, Any], symbol: str
    ) -> "FundingRateModel":
        """
        Create FundingRateModel from Binance premium index data.

        Premium index structure includes more detailed information:
        {
            "symbol": "BTCUSDT",
            "markPrice": "46600.00000000",
            "indexPrice": "46598.12345678",
            "estimatedSettlePrice": "46600.00000000",
            "lastFundingRate": "0.00010000",
            "nextFundingTime": 1640995200000,
            "interestRate": "0.00010000",
            "time": 1640995100000
        }
        """
        return cls(
            symbol=symbol,
            funding_rate=Decimal(premium_data.get("lastFundingRate", "0")),
            funding_time=datetime.fromtimestamp(
                int(premium_data["nextFundingTime"]) / 1000, tz=timezone.utc
            ),
            mark_price=(
                Decimal(premium_data["markPrice"])
                if premium_data.get("markPrice")
                else None
            ),
            index_price=(
                Decimal(premium_data["indexPrice"])
                if premium_data.get("indexPrice")
                else None
            ),
            last_funding_rate=(
                Decimal(premium_data.get("lastFundingRate", "0"))
                if premium_data.get("lastFundingRate")
                else None
            ),
            timestamp=datetime.fromtimestamp(
                int(premium_data["time"]) / 1000, tz=timezone.utc
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return self.model_dump(exclude={"id"})

    @property
    def collection_name(self) -> str:
        """Return the database collection name for this model."""
        return "funding_rates"

    @property
    def funding_rate_percentage(self) -> Decimal:
        """Return funding rate as percentage."""
        return self.funding_rate * Decimal("100")

    @property
    def annualized_funding_rate(self) -> Decimal:
        """Calculate annualized funding rate based on interval."""
        periods_per_year = (
            Decimal("365") * Decimal("24") / Decimal(str(self.funding_interval_hours))
        )
        return self.funding_rate * periods_per_year
