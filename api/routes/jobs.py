"""
Job management API routes.

Provides endpoints for manually triggering extraction jobs.
"""

import logging

from fastapi import APIRouter, HTTPException, Path, status

from api.models.requests import JobTriggerRequest
from api.models.responses import APIResponse
from services.cronjob_manager import get_cronjob_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("/trigger", response_model=APIResponse)
async def trigger_extraction_job(request: JobTriggerRequest):
    """
    Manually trigger an extraction job.

    **For LLM Agents**: Force immediate data extraction for specific timeframe.

    Useful for:
    - Filling detected gaps immediately
    - Testing configuration changes
    - Backfilling after downtime

    Example: POST /api/v1/jobs/trigger
    {
      "timeframe": "15m",
      "symbol": "BTCUSDT",
      "reason": "Fill gap detected in 15m data"
    }
    """
    try:
        # Validate timeframe
        valid_timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
        if request.timeframe not in valid_timeframes:
            return APIResponse(
                success=False,
                error={
                    "code": "VALIDATION_ERROR",
                    "message": f"Invalid timeframe: {request.timeframe}. Must be one of {valid_timeframes}",
                },
            )

        # Find corresponding CronJob
        manager = get_cronjob_manager()
        cronjobs = manager.list_cronjobs()

        # Find CronJob for this timeframe
        cronjob_name = None
        for cj in cronjobs:
            if cj.get("timeframe") == request.timeframe:
                cronjob_name = cj.get("name")
                break

        if not cronjob_name:
            # Try to construct name
            cronjob_name = f"binance-klines-{request.timeframe.replace('m', 'm').replace('h', 'h')}-production"

        # Create manual job
        job_info = manager.create_job_from_cronjob(
            cronjob_name, request.timeframe, request.symbol
        )

        return APIResponse(
            success=True,
            data=job_info,
            metadata={
                "message": f"Triggered extraction job for {request.timeframe}",
                "reason": request.reason,
            },
        )
    except Exception as e:
        logger.error(f"Error triggering extraction job: {e}")
        return APIResponse(
            success=False,
            error={"code": "INTERNAL_ERROR", "message": str(e)},
        )
