"""
Configuration management API routes.

Provides endpoints for managing CronJob schedules, symbols, and rate limits.
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, Path, Query, status

from api.models.requests import CronJobScheduleUpdate, RateLimitsUpdate, SymbolsUpdate
from api.models.responses import APIResponse, CronJobInfo, RateLimitsInfo, SymbolsInfo
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
