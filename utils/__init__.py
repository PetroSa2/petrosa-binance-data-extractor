"""
Utilities package.
"""

from .logger import setup_logging, get_logger
from .time_utils import (
    parse_binance_timestamp,
    parse_datetime_string,
    get_interval_timedelta,
    get_interval_minutes,
    generate_time_range,
    align_timestamp_to_interval,
    find_time_gaps,
    get_current_utc_time,
    format_duration,
    validate_time_range,
    chunk_time_range,
)
from .retry import (
    exponential_backoff,
    simple_retry,
    RateLimiter,
    rate_limited,
    retry_on_failure,
    rate_limit_api_calls,
    with_retries_and_rate_limit,
    retry_on_http_errors,
)

__all__ = [
    # Logger
    "setup_logging",
    "get_logger",
    # Time utils
    "parse_binance_timestamp",
    "parse_datetime_string",
    "get_interval_timedelta",
    "get_interval_minutes",
    "generate_time_range",
    "align_timestamp_to_interval",
    "find_time_gaps",
    "get_current_utc_time",
    "format_duration",
    "validate_time_range",
    "chunk_time_range",
    # Retry utils
    "exponential_backoff",
    "simple_retry",
    "RateLimiter",
    "rate_limited",
    "retry_on_failure",
    "rate_limit_api_calls",
    "with_retries_and_rate_limit",
    "retry_on_http_errors",
]
