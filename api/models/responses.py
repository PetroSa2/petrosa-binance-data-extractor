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


class ValidationError(BaseModel):
    """Standardized validation error format."""

    field: str = Field(..., description="Parameter name that failed validation")
    message: str = Field(..., description="Human-readable error message")
    code: str = Field(
        ..., description="Error code (e.g., 'INVALID_TYPE', 'OUT_OF_RANGE')"
    )
    suggested_value: Optional[Any] = Field(
        None, description="Suggested correct value if applicable"
    )


class CrossServiceConflict(BaseModel):
    """Cross-service configuration conflict."""

    service: str = Field(..., description="Service name with conflicting configuration")
    conflict_type: str = Field(
        ..., description="Type of conflict (e.g., 'PARAMETER_CONFLICT')"
    )
    description: str = Field(..., description="Description of the conflict")
    resolution: Optional[str] = Field(
        None, description="Suggested resolution for the conflict"
    )


class ValidationResponse(BaseModel):
    """Standardized validation response across all services."""

    validation_passed: bool = Field(..., description="Whether validation passed")
    errors: list[ValidationError] = Field(
        default_factory=list, description="List of validation errors"
    )
    warnings: list[str] = Field(
        default_factory=list, description="List of validation warnings"
    )
    suggested_fixes: list[str] = Field(
        default_factory=list, description="Suggested fixes for validation errors"
    )
    estimated_impact: dict[str, Any] = Field(
        default_factory=dict, description="Estimated impact of the configuration change"
    )
    conflicts: list[CrossServiceConflict] = Field(
        default_factory=list, description="Cross-service configuration conflicts"
    )
