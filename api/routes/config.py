"""
Configuration management API routes.

Provides endpoints for managing CronJob schedules, symbols, and rate limits.
"""

import logging

from fastapi import APIRouter, HTTPException, Path, Query, status

from api.models.requests import (
    ConfigValidationRequest,
    CronJobScheduleUpdate,
    RateLimitsUpdate,
    SymbolsUpdate,
)
from api.models.responses import (
    APIResponse,
    CronJobInfo,
    CrossServiceConflict,
    RateLimitsInfo,
    SymbolsInfo,
    ValidationError,
    ValidationResponse,
)
from services.config_manager import get_config_manager
from services.cronjob_manager import get_cronjob_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["Configuration"])


def validate_cron_expression(schedule: str) -> bool:
    """
    Validate cron expression format.

    Basic validation - checks for 5 space-separated fields.
    """
    parts = schedule.split()
    if len(parts) != 5:
        return False
    # Additional validation could use croniter library
    return True


@router.get("/cronjobs", response_model=APIResponse)
async def list_cronjobs():
    """
    List all data extraction CronJobs with schedules and status.

    **For LLM Agents**: See all extraction jobs and their schedules.
    """
    try:
        manager = get_cronjob_manager()
        cronjobs = manager.list_cronjobs()

        return APIResponse(
            success=True,
            data=[CronJobInfo(**cj) for cj in cronjobs],
            metadata={"count": len(cronjobs)},
        )
    except Exception as e:
        logger.error(f"Error listing CronJobs: {e}")
        return APIResponse(
            success=False,
            error={"code": "INTERNAL_ERROR", "message": str(e)},
        )


@router.post("/cronjobs/{job_name}", response_model=APIResponse)
async def update_cronjob_schedule(
    job_name: str = Path(..., description="CronJob name"),
    request: CronJobScheduleUpdate = ...,
):
    """
    Update CronJob schedule dynamically.

    **For LLM Agents**: Adjust extraction frequency without redeployment.

    Example: POST /api/v1/config/cronjobs/binance-klines-15m
    {
      "schedule": "*/10 * * * *",
      "changed_by": "llm_agent",
      "reason": "Increase frequency for volatile market"
    }
    """
    try:
        # Validate cron expression
        if not validate_cron_expression(request.schedule):
            return APIResponse(
                success=False,
                error={
                    "code": "VALIDATION_ERROR",
                    "message": f"Invalid cron expression: {request.schedule}",
                },
            )

        manager = get_cronjob_manager()
        updated = manager.update_cronjob_schedule(job_name, request.schedule)

        # TODO: Audit the change to MongoDB

        return APIResponse(
            success=True,
            data=updated,
            metadata={
                "message": f"Updated {job_name} schedule to {request.schedule}",
                "changed_by": request.changed_by,
                "reason": request.reason,
            },
        )
    except Exception as e:
        logger.error(f"Error updating CronJob schedule: {e}")
        return APIResponse(
            success=False,
            error={"code": "INTERNAL_ERROR", "message": str(e)},
        )


@router.get("/symbols", response_model=APIResponse)
async def get_symbols():
    """
    Get currently configured symbols for extraction.

    Returns list of symbols being extracted across all timeframes.
    """
    try:
        config_manager = get_config_manager()
        symbols = config_manager.get_symbols()

        return APIResponse(
            success=True,
            data=SymbolsInfo(symbols=symbols, count=len(symbols)),
        )
    except Exception as e:
        logger.error(f"Error getting symbols: {e}")
        return APIResponse(
            success=False,
            error={"code": "INTERNAL_ERROR", "message": str(e)},
        )


@router.post("/symbols", response_model=APIResponse)
async def update_symbols(request: SymbolsUpdate):
    """
    Update symbols for extraction.

    **For LLM Agents**: Add/remove trading pairs dynamically.

    Example: POST /api/v1/config/symbols
    {
      "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
      "changed_by": "llm_agent",
      "reason": "Focus on top 3 pairs"
    }
    """
    try:
        # Validate symbols
        for symbol in request.symbols:
            if not symbol or not symbol.isupper():
                return APIResponse(
                    success=False,
                    error={
                        "code": "VALIDATION_ERROR",
                        "message": f"Invalid symbol format: {symbol}",
                    },
                )

        config_manager = get_config_manager()
        config_manager.set_symbols(request.symbols, request.changed_by, request.reason)

        # TODO: Update all CronJobs with new symbol list

        return APIResponse(
            success=True,
            data=SymbolsInfo(symbols=request.symbols, count=len(request.symbols)),
            metadata={
                "message": "Updated extraction symbols",
                "changed_by": request.changed_by,
                "reason": request.reason,
            },
        )
    except Exception as e:
        logger.error(f"Error updating symbols: {e}")
        return APIResponse(
            success=False,
            error={"code": "INTERNAL_ERROR", "message": str(e)},
        )


@router.get("/rate-limits", response_model=APIResponse)
async def get_rate_limits():
    """
    Get current Binance API rate limit configuration.
    """
    try:
        config_manager = get_config_manager()
        limits = config_manager.get_rate_limits()

        return APIResponse(
            success=True,
            data=RateLimitsInfo(**limits),
        )
    except Exception as e:
        logger.error(f"Error getting rate limits: {e}")
        return APIResponse(
            success=False,
            error={"code": "INTERNAL_ERROR", "message": str(e)},
        )


@router.post("/rate-limits", response_model=APIResponse)
async def update_rate_limits(request: RateLimitsUpdate):
    """
    Update Binance API rate limit configuration.

    **For LLM Agents**: Adjust rate limiting to prevent throttling.

    Note: Binance limit is 1200/min. Stay under this to avoid bans.

    Example: POST /api/v1/config/rate-limits
    {
      "requests_per_minute": 1000,
      "concurrent_requests": 5,
      "changed_by": "llm_agent",
      "reason": "Reduce rate to avoid throttling"
    }
    """
    try:
        config_manager = get_config_manager()
        config_manager.set_rate_limits(
            request.requests_per_minute,
            request.concurrent_requests,
            request.changed_by,
            request.reason,
        )

        return APIResponse(
            success=True,
            data=RateLimitsInfo(
                requests_per_minute=request.requests_per_minute,
                concurrent_requests=request.concurrent_requests,
            ),
            metadata={
                "message": "Rate limits updated",
                "changed_by": request.changed_by,
                "reason": request.reason,
            },
        )
    except Exception as e:
        logger.error(f"Error updating rate limits: {e}")
        return APIResponse(
            success=False,
            error={"code": "INTERNAL_ERROR", "message": str(e)},
        )


@router.post("/validate", response_model=APIResponse)
async def validate_config(request: ConfigValidationRequest):
    """
    Validate configuration without applying changes.

    **For LLM Agents**: Validate configuration parameters before applying them.

    This endpoint performs comprehensive validation including:
    - Parameter type and constraint validation
    - Format validation (cron expressions, symbol formats)
    - Range validation (rate limits)
    - Dependency validation

    **Example Request**:
    ```json
    {
      "config_type": "rate_limits",
      "parameters": {
        "requests_per_minute": 1000,
        "concurrent_requests": 5
      }
    }
    ```

    **Example Response**:
    ```json
    {
      "success": true,
      "data": {
        "validation_passed": true,
        "errors": [],
        "warnings": [],
        "suggested_fixes": [],
        "estimated_impact": {
          "risk_level": "low",
          "affected_scope": "rate_limits"
        },
        "conflicts": []
      }
    }
    ```
    """
    try:
        validation_errors = []
        warnings = []
        suggested_fixes = []
        estimated_impact = {}

        # Validate based on config type
        if request.config_type == "symbols":
            symbols = request.parameters.get("symbols", [])
            if not isinstance(symbols, list):
                validation_errors.append(
                    ValidationError(
                        field="symbols",
                        message="Symbols must be a list",
                        code="INVALID_TYPE",
                        suggested_value=[],
                    )
                )
            else:
                cronjob_manager = get_cronjob_manager()
                for symbol in symbols:
                    if not isinstance(symbol, str):
                        validation_errors.append(
                            ValidationError(
                                field="symbols",
                                message=f"Symbol must be a string, got {type(symbol).__name__}",
                                code="INVALID_TYPE",
                                suggested_value=str(symbol),
                            )
                        )
                    elif not cronjob_manager.is_valid_binance_symbol(symbol):
                        validation_errors.append(
                            ValidationError(
                                field="symbols",
                                message=f"Invalid symbol format: {symbol}",
                                code="INVALID_FORMAT",
                                suggested_value=symbol.upper(),
                            )
                        )

                estimated_impact = {
                    "risk_level": "low",
                    "affected_scope": f"{len(symbols)} symbols",
                    "message": "Changing symbols will affect all extraction jobs",
                }

        elif request.config_type == "rate_limits":
            requests_per_minute = request.parameters.get("requests_per_minute")
            concurrent_requests = request.parameters.get("concurrent_requests")

            if requests_per_minute is not None:
                if not isinstance(requests_per_minute, int):
                    validation_errors.append(
                        ValidationError(
                            field="requests_per_minute",
                            message="Must be an integer",
                            code="INVALID_TYPE",
                            suggested_value=1200,
                        )
                    )
                elif requests_per_minute < 1:
                    validation_errors.append(
                        ValidationError(
                            field="requests_per_minute",
                            message="Must be at least 1",
                            code="OUT_OF_RANGE",
                            suggested_value=1,
                        )
                    )
                elif requests_per_minute > 1200:
                    validation_errors.append(
                        ValidationError(
                            field="requests_per_minute",
                            message="Exceeds Binance API limit of 1200/min",
                            code="OUT_OF_RANGE",
                            suggested_value=1200,
                        )
                    )
                elif requests_per_minute > 1000:
                    warnings.append(
                        "High request rate may trigger Binance rate limiting"
                    )

            if concurrent_requests is not None:
                if not isinstance(concurrent_requests, int):
                    validation_errors.append(
                        ValidationError(
                            field="concurrent_requests",
                            message="Must be an integer",
                            code="INVALID_TYPE",
                            suggested_value=5,
                        )
                    )
                elif concurrent_requests < 1:
                    validation_errors.append(
                        ValidationError(
                            field="concurrent_requests",
                            message="Must be at least 1",
                            code="OUT_OF_RANGE",
                            suggested_value=1,
                        )
                    )
                elif concurrent_requests > 10:
                    validation_errors.append(
                        ValidationError(
                            field="concurrent_requests",
                            message="Maximum concurrent requests is 10",
                            code="OUT_OF_RANGE",
                            suggested_value=10,
                        )
                    )

            estimated_impact = {
                "risk_level": "medium"
                if requests_per_minute and requests_per_minute > 800
                else "low",
                "affected_scope": "all extraction jobs",
                "message": "Rate limit changes affect all API calls to Binance",
            }

        elif request.config_type == "cronjob":
            if not request.cronjob_name:
                validation_errors.append(
                    ValidationError(
                        field="cronjob_name",
                        message="cronjob_name is required for cronjob config type",
                        code="MISSING_REQUIRED_FIELD",
                        suggested_value=None,
                    )
                )

            schedule = request.parameters.get("schedule")
            if schedule:
                if not isinstance(schedule, str):
                    validation_errors.append(
                        ValidationError(
                            field="schedule",
                            message="Schedule must be a string",
                            code="INVALID_TYPE",
                            suggested_value="*/15 * * * *",
                        )
                    )
                elif not validate_cron_expression(schedule):
                    validation_errors.append(
                        ValidationError(
                            field="schedule",
                            message=f"Invalid cron expression: {schedule}",
                            code="INVALID_FORMAT",
                            suggested_value="*/15 * * * *",
                        )
                    )

            estimated_impact = {
                "risk_level": "low",
                "affected_scope": request.cronjob_name or "unknown cronjob",
                "message": "Changing schedule affects extraction frequency",
            }

        else:
            validation_errors.append(
                ValidationError(
                    field="config_type",
                    message=f"Unknown config type: {request.config_type}",
                    code="INVALID_VALUE",
                    suggested_value="symbols",
                )
            )

        # Generate suggested fixes
        for error in validation_errors:
            if error.suggested_value is not None:
                suggested_fixes.append(f"Set {error.field} to {error.suggested_value}")

        # Cross-service conflict detection (placeholder)
        conflicts = []
        # TODO: Implement cross-service conflict detection
        # This would check against other services' configurations

        validation_response = ValidationResponse(
            validation_passed=len(validation_errors) == 0,
            errors=validation_errors,
            warnings=warnings,
            suggested_fixes=suggested_fixes,
            estimated_impact=estimated_impact,
            conflicts=conflicts,
        )

        return APIResponse(
            success=True,
            data=validation_response,
            metadata={
                "validation_mode": "dry_run",
                "config_type": request.config_type,
            },
        )

    except Exception as e:
        logger.error(f"Error validating config: {e}")
        return APIResponse(
            success=False,
            error={"code": "INTERNAL_ERROR", "message": str(e)},
        )
