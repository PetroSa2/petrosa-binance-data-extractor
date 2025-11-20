"""
Pydantic request models for API endpoints.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class CronJobScheduleUpdate(BaseModel):
    """Request model for updating CronJob schedule."""

    schedule: str = Field(
        ..., description="Cron schedule expression (e.g., '*/15 * * * *')"
    )
    changed_by: str = Field(..., description="Who is making this change")
    reason: Optional[str] = Field(None, description="Reason for the change")


class SymbolsUpdate(BaseModel):
    """Request model for updating extraction symbols."""

    symbols: list[str] = Field(
        ..., description="List of trading symbols (e.g., BTCUSDT)"
    )
    changed_by: str = Field(..., description="Who is making this change")
    reason: Optional[str] = Field(None, description="Reason for the change")


class RateLimitsUpdate(BaseModel):
    """Request model for updating rate limits."""

    requests_per_minute: int = Field(
        ..., ge=1, le=1200, description="Requests per minute (Binance limit: 1200)"
    )
    concurrent_requests: int = Field(
        ..., ge=1, le=10, description="Maximum concurrent requests"
    )
    changed_by: str = Field(..., description="Who is making this change")
    reason: Optional[str] = Field(None, description="Reason for the change")


class JobTriggerRequest(BaseModel):
    """Request model for manually triggering extraction jobs."""

    timeframe: str = Field(..., description="Timeframe: 1m, 5m, 15m, 1h, 4h, 1d")
    symbol: Optional[str] = Field(None, description="Specific symbol or None for all")
    reason: str = Field(..., description="Reason for manual trigger")


class ConfigValidationRequest(BaseModel):
    """Request model for configuration validation."""

    config_type: Literal["symbols", "rate_limits", "cronjob"] = Field(
        ..., description="Type of configuration to validate"
    )
    parameters: dict[str, Any] = Field(
        ..., description="Configuration parameters to validate"
    )
    cronjob_name: Optional[str] = Field(
        None, description="CronJob name (required for cronjob config type)"
    )
