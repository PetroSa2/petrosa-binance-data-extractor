"""
Base Pydantic models and shared fields for all Binance data models.
"""

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BaseTimestampedModel(BaseModel):
    """Base model with common timestamp and metadata fields."""

    # Primary timestamp (when the data point occurred)
    timestamp: datetime = Field(..., description="Event timestamp in UTC")

    # Metadata fields
    extracted_at: datetime = Field(
        default_factory=datetime.utcnow, description="When this record was extracted"
    )
    extractor_version: str = Field(
        default="1.0.0", description="Version of the extractor that created this record"
    )
    source: str = Field(default="binance-futures", description="Data source identifier")

    # Optional unique identifier
    id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique record identifier",
    )

    # Pydantic v2 configuration
    model_config = ConfigDict(
        extra="allow",
        use_enum_values=True,
        validate_assignment=True,
        json_encoders={datetime: lambda v: v.isoformat() + "Z" if v else None},
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v: Any) -> datetime:
        """Parse timestamp from various formats."""
        if isinstance(v, int):
            # Assume milliseconds if > 1e10, otherwise seconds
            if v > 1e10:
                return datetime.utcfromtimestamp(v / 1000)
            else:
                return datetime.utcfromtimestamp(v)
        elif isinstance(v, str):
            # Try to parse ISO format
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                # Try timestamp string
                return datetime.utcfromtimestamp(
                    float(v) / 1000 if float(v) > 1e10 else float(v)
                )
        return v


class BaseSymbolModel(BaseTimestampedModel):
    """Base model for symbol-specific data."""

    symbol: str = Field(..., description="Trading pair symbol (e.g., BTCUSDT)")

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Ensure symbol is uppercase."""
        return v.upper() if v else v


class ExtractionMetadata(BaseModel):
    """Metadata about the extraction process."""

    extraction_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique extraction run ID",
    )
    period: str = Field(
        ..., description="Time period for the extraction (e.g., 15m, 1h)"
    )
    start_time: datetime = Field(..., description="Start time of extraction range")
    end_time: datetime = Field(..., description="End time of extraction range")
    total_records: int = Field(
        default=0, description="Total number of records extracted"
    )
    gaps_detected: int = Field(
        default=0, description="Number of gaps detected in the data"
    )
    backfill_performed: bool = Field(
        default=False, description="Whether backfill was performed"
    )
    extraction_duration_seconds: float = Field(
        default=0.0, description="Total extraction time in seconds"
    )
    errors_encountered: List[str] = Field(
        default_factory=list, description="List of errors encountered during extraction"
    )

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat() + "Z" if v else None}
    )
