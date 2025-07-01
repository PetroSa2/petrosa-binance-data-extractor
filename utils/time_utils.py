"""
Time utility functions for date parsing, timezone conversion, and gap detection.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple, Union

import constants


def parse_binance_timestamp(timestamp: Union[int, str, datetime]) -> datetime:
    """
    Parse Binance timestamp to datetime object.

    Args:
        timestamp: Timestamp in various formats (int, str, datetime)

    Returns:
        UTC datetime object
    """
    if isinstance(timestamp, datetime):
        return (
            timestamp.replace(tzinfo=timezone.utc)
            if timestamp.tzinfo is None
            else timestamp.astimezone(timezone.utc)
        )

    if isinstance(timestamp, str):
        # Try to parse as ISO format first
        try:
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(
                timezone.utc
            )
        except ValueError:
            # Try to parse as timestamp string
            timestamp_float = float(timestamp)
            # Binance uses milliseconds, convert to seconds if needed
            if timestamp_float > 1e10:  # Milliseconds
                return datetime.fromtimestamp(timestamp_float / 1000, tz=timezone.utc)
            else:  # Seconds
                return datetime.fromtimestamp(timestamp_float, tz=timezone.utc)

    if isinstance(timestamp, (int, float)):
        # Binance uses milliseconds, convert to seconds if needed
        if timestamp > 1e10:  # Milliseconds
            return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
        else:  # Seconds
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    raise ValueError(f"Unable to parse timestamp: {timestamp}")


def parse_datetime_string(date_string: str) -> datetime:
    """
    Parse datetime string in various formats.

    Args:
        date_string: Date string in ISO format or other common formats

    Returns:
        UTC datetime object
    """
    # Remove timezone info if present for parsing
    date_string = date_string.strip()

    # Handle ISO format with Z
    if date_string.endswith("Z"):
        date_string = date_string[:-1] + "+00:00"

    # Try different formats
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",  # ISO with timezone
        "%Y-%m-%dT%H:%M:%S",  # ISO without timezone
        "%Y-%m-%d %H:%M:%S",  # Space separated
        "%Y-%m-%d",  # Date only
        "%Y/%m/%d",  # Alternative date format
        "%d/%m/%Y",  # DD/MM/YYYY
        "%m/%d/%Y",  # MM/DD/YYYY
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_string, fmt)
            # Assume UTC if no timezone info
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue

    raise ValueError(f"Unable to parse date string: {date_string}")


def get_interval_timedelta(interval: str) -> timedelta:
    """
    Convert Binance interval string to Python timedelta.

    Args:
        interval: Binance interval (e.g., '1m', '5m', '1h', '1d')

    Returns:
        timedelta object
    """
    # Parse interval string
    match = re.match(r"(\d+)([mhdwM])", interval)
    if not match:
        raise ValueError(f"Invalid interval format: {interval}")

    value, unit = match.groups()
    value = int(value)

    unit_map = {
        "m": "minutes",
        "h": "hours",
        "d": "days",
        "w": "weeks",
        "M": "days",  # Approximate months as 30 days
    }

    if unit == "M":
        # Handle months specially (approximate)
        return timedelta(days=value * 30)

    if unit not in unit_map:
        raise ValueError(f"Unsupported interval unit: {unit}")

    kwargs = {unit_map[unit]: value}
    return timedelta(**kwargs)


def get_interval_minutes(interval: str) -> int:
    """
    Get interval in minutes.

    Args:
        interval: Binance interval string

    Returns:
        Interval in minutes
    """
    delta = get_interval_timedelta(interval)
    return int(delta.total_seconds() / 60)


def generate_time_range(
    start: datetime, end: datetime, interval: str
) -> List[datetime]:
    """
    Generate list of timestamps for the given time range and interval.

    Args:
        start: Start datetime
        end: End datetime
        interval: Binance interval string

    Returns:
        List of datetime objects
    """
    delta = get_interval_timedelta(interval)
    timestamps = []
    current = start

    while current < end:
        timestamps.append(current)
        current += delta

    return timestamps


def align_timestamp_to_interval(timestamp: datetime, interval: str) -> datetime:
    """
    Align timestamp to interval boundary.

    For example, align 10:37:23 to 10:30:00 for 30m interval.

    Args:
        timestamp: Timestamp to align
        interval: Binance interval string

    Returns:
        Aligned timestamp
    """
    minutes = get_interval_minutes(interval)

    # Round down to the nearest interval
    total_minutes = timestamp.hour * 60 + timestamp.minute
    aligned_minutes = (total_minutes // minutes) * minutes

    aligned_hour = aligned_minutes // 60
    aligned_minute = aligned_minutes % 60

    aligned_timestamp = timestamp.replace(
        hour=aligned_hour, minute=aligned_minute, second=0, microsecond=0
    )

    # Preserve timezone if original timestamp had one
    if timestamp.tzinfo is not None and aligned_timestamp.tzinfo is None:
        aligned_timestamp = aligned_timestamp.replace(tzinfo=timestamp.tzinfo)

    return aligned_timestamp


def find_time_gaps(
    timestamps: List[datetime],
    interval: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> List[Tuple[datetime, datetime]]:
    """
    Find gaps in a list of timestamps.

    Args:
        timestamps: List of timestamps (should be sorted)
        interval: Expected interval between timestamps
        start_time: Expected start time (optional)
        end_time: Expected end time (optional)

    Returns:
        List of tuples representing gap start and end times
    """
    if not timestamps:
        if start_time and end_time:
            return [(start_time, end_time)]
        return []

    # Sort timestamps
    timestamps = sorted(timestamps)
    gaps = []

    expected_delta = get_interval_timedelta(interval)
    tolerance = timedelta(minutes=1)  # Allow 1-minute tolerance

    # Check for gap at the beginning
    if start_time and timestamps[0] > start_time + expected_delta:
        gaps.append((start_time, timestamps[0]))

    # Check for gaps between timestamps
    for i in range(len(timestamps) - 1):
        current = timestamps[i]
        next_timestamp = timestamps[i + 1]
        expected_next = current + expected_delta

        # Check if there's a significant gap
        if next_timestamp > expected_next + tolerance:
            gaps.append((expected_next, next_timestamp))

    # Check for gap at the end
    if end_time and timestamps[-1] < end_time - expected_delta:
        gaps.append((timestamps[-1] + expected_delta, end_time))

    return gaps


def is_market_open(timestamp: datetime) -> bool:
    """
    Check if crypto market is open (always true for crypto).

    Args:
        timestamp: Timestamp to check

    Returns:
        Always True for crypto markets
    """
    # Crypto markets are always open
    return True


def get_current_utc_time() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def get_binance_server_time() -> datetime:
    """
    Get Binance server time (placeholder - would need actual API call).

    Returns:
        Current UTC time (placeholder implementation)
    """
    # In a real implementation, this would make an API call to get server time
    # For now, return current UTC time
    return get_current_utc_time()


def validate_time_range(start: datetime, end: datetime, max_days: int = 1000) -> None:
    """
    Validate time range parameters.

    Args:
        start: Start datetime
        end: End datetime
        max_days: Maximum allowed range in days

    Raises:
        ValueError: If time range is invalid
    """
    if start >= end:
        raise ValueError("Start time must be before end time")

    duration = end - start
    if duration.days > max_days:
        raise ValueError(
            f"Time range too large: {duration.days} days (max: {max_days})"
        )

    # Check if start time is too far in the future
    now = get_current_utc_time()
    if start > now:
        raise ValueError("Start time cannot be in the future")


def get_default_start_time(interval: str) -> datetime:
    """
    Get default start time based on interval.

    Args:
        interval: Binance interval string

    Returns:
        Default start datetime
    """
    try:
        return parse_datetime_string(constants.DEFAULT_START_DATE)
    except (ValueError, AttributeError):
        # Fallback to 30 days ago
        return get_current_utc_time() - timedelta(days=30)


def chunk_time_range(
    start: datetime, end: datetime, chunk_hours: int = 24
) -> List[Tuple[datetime, datetime]]:
    """
    Split time range into smaller chunks for API requests.

    Args:
        start: Start datetime
        end: End datetime
        chunk_hours: Size of each chunk in hours

    Returns:
        List of (start, end) tuples for each chunk
    """
    chunks = []
    current_start = start
    chunk_delta = timedelta(hours=chunk_hours)

    while current_start < end:
        current_end = min(current_start + chunk_delta, end)
        chunks.append((current_start, current_end))
        current_start = current_end

    return chunks


def binance_interval_to_table_suffix(interval: str) -> str:
    """
    Convert Binance interval format to proper financial market table naming convention.

    Binance format: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
    Financial format: m1, m3, m5, m15, m30, h1, h2, h4, h6, h8, h12, d1, d3, w1, M1

    Args:
        interval: Binance interval format (e.g., "15m", "1h", "1d")

    Returns:
        Financial market format (e.g., "m15", "h1", "d1")
    """
    # Handle minute intervals
    if interval.endswith("m"):
        minutes = interval[:-1]
        return f"m{minutes}"

    # Handle hour intervals
    elif interval.endswith("h"):
        hours = interval[:-1]
        return f"h{hours}"

    # Handle day intervals
    elif interval.endswith("d"):
        days = interval[:-1]
        return f"d{days}"

    # Handle week intervals
    elif interval.endswith("w"):
        weeks = interval[:-1]
        return f"w{weeks}"

    # Handle month intervals
    elif interval.endswith("M"):
        months = interval[:-1]
        return f"M{months}"

    # Fallback - return as is
    else:
        return interval


def table_suffix_to_binance_interval(suffix: str) -> str:
    """
    Convert financial market table suffix back to Binance interval format.

    Args:
        suffix: Financial market format (e.g., "m15", "h1", "d1")

    Returns:
        Binance interval format (e.g., "15m", "1h", "1d")
    """
    # Handle minute intervals
    if suffix.startswith("m"):
        minutes = suffix[1:]
        return f"{minutes}m"

    # Handle hour intervals
    elif suffix.startswith("h"):
        hours = suffix[1:]
        return f"{hours}h"

    # Handle day intervals
    elif suffix.startswith("d"):
        days = suffix[1:]
        return f"{days}d"

    # Handle week intervals
    elif suffix.startswith("w"):
        weeks = suffix[1:]
        return f"{weeks}w"

    # Handle month intervals
    elif suffix.startswith("M"):
        months = suffix[1:]
        return f"{months}M"

    # Fallback - return as is
    else:
        return suffix
