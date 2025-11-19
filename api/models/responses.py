"""
Pydantic response models for API endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    """Standard API response wrapper."""

    success: bool = Field(..., description="Whether operation succeeded")
    data: Optional[Any] = Field(None, description="Response data")
    error: Optional[dict[str, Any]] = Field(None, description="Error details if failed")
    metadata: Optional[dict[str, Any]] = Field(None, description="Additional metadata")


class CronJobInfo(BaseModel):
    """CronJob information model."""

    name: str = Field(..., description="CronJob name")
    schedule: str = Field(..., description="Current schedule (cron expression)")
    timeframe: Optional[str] = Field(None, description="Extraction timeframe")
    last_schedule_time: Optional[datetime] = Field(
        None, description="Last scheduled run time"
    )
    active_jobs: int = Field(0, description="Number of active jobs")
    suspended: bool = Field(False, description="Whether CronJob is suspended")


class SymbolsInfo(BaseModel):
    """Symbols configuration information."""

    symbols: list[str] = Field(..., description="List of configured symbols")
    count: int = Field(..., description="Number of symbols")
    last_updated: Optional[datetime] = Field(None, description="Last update timestamp")


class RateLimitsInfo(BaseModel):
    """Rate limits configuration information."""

    requests_per_minute: int = Field(..., description="Requests per minute limit")
    concurrent_requests: int = Field(..., description="Maximum concurrent requests")
    last_updated: Optional[datetime] = Field(None, description="Last update timestamp")
