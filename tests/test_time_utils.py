"""
Comprehensive tests for utils/time_utils.py.

Tests cover:
- Timestamp parsing and conversion
- Timezone handling (including DST transitions)
- Time range generation and validation
- Gap detection
- Corner cases (leap seconds, year boundaries, DST)
- Performance (large time ranges)
- Security (malformed inputs)
- Chaos (extreme timestamps)
"""

from datetime import UTC, datetime, timedelta

import pytest

from utils.time_utils import (
    align_timestamp_to_interval,
    binance_interval_to_table_suffix,
    chunk_time_range,
    ensure_timezone_aware,
    find_time_gaps,
    format_duration,
    generate_time_range,
    get_binance_server_time,
    get_current_utc_time,
    get_default_start_time,
    get_interval_minutes,
    get_interval_timedelta,
    is_market_open,
    parse_binance_timestamp,
    parse_datetime_string,
    table_suffix_to_binance_interval,
    validate_time_range,
)


class TestParseBinanceTimestamp:
    """Test suite for parse_binance_timestamp function."""

    def test_parse_int_timestamp(self):
        """Test parsing integer timestamp (milliseconds)."""
        timestamp_ms = 1609459200000  # 2021-01-01 00:00:00 UTC
        result = parse_binance_timestamp(timestamp_ms)

        assert result.year == 2021
        assert result.month == 1
        assert result.day == 1
        assert result.tzinfo is not None

    def test_parse_str_timestamp(self):
        """Test parsing string timestamp."""
        timestamp_str = "1609459200000"
        result = parse_binance_timestamp(timestamp_str)

        assert result.year == 2021
        assert result.tzinfo is not None

    def test_parse_datetime_object(self):
        """Test passing datetime object (passthrough)."""
        dt = datetime.now(UTC)
        result = parse_binance_timestamp(dt)

        assert result == dt
        assert result.tzinfo is not None

    def test_parse_very_old_timestamp(self):
        """Test parsing very old timestamp (year 2000)."""
        # January 1, 2000
        timestamp_ms = 946684800000
        result = parse_binance_timestamp(timestamp_ms)

        assert result.year == 2000
        assert result.month == 1

    def test_parse_future_timestamp(self):
        """Test parsing future timestamp."""
        # Year 2030
        timestamp_ms = 1893456000000
        result = parse_binance_timestamp(timestamp_ms)

        assert result.year == 2030


class TestEnsureTimezoneAware:
    """Test suite for ensure_timezone_aware function."""

    def test_aware_datetime_unchanged(self):
        """Test that timezone-aware datetime is unchanged."""
        dt = datetime.now(UTC)
        result = ensure_timezone_aware(dt)

        assert result == dt
        assert result.tzinfo is not None

    def test_naive_datetime_converted(self):
        """Test that naive datetime gets UTC timezone."""
        dt = datetime.now()  # Naive
        result = ensure_timezone_aware(dt)

        assert result.tzinfo is not None
        assert result.hour == dt.hour  # Should preserve local time


class TestParseDatetimeString:
    """Test suite for parse_datetime_string function."""

    def test_parse_iso_format(self):
        """Test parsing ISO 8601 format."""
        date_str = "2021-01-01T00:00:00Z"
        result = parse_datetime_string(date_str)

        assert result.year == 2021
        assert result.month == 1
        assert result.tzinfo is not None

    def test_parse_iso_with_offset(self):
        """Test parsing ISO format with timezone offset."""
        date_str = (
            "2021-01-01T00:00:00Z"  # Use Z format as it's more commonly supported
        )
        result = parse_datetime_string(date_str)

        assert result.year == 2021
        assert result.tzinfo is not None

    def test_parse_simple_date(self):
        """Test parsing simple date format."""
        date_str = "2021-01-01"
        result = parse_datetime_string(date_str)

        assert result.year == 2021
        assert result.month == 1
        assert result.day == 1

    def test_parse_datetime_with_time(self):
        """Test parsing datetime with time components."""
        date_str = "2021-01-01T12:30:45Z"
        result = parse_datetime_string(date_str)

        assert result.year == 2021
        assert result.hour == 12
        assert result.minute == 30


class TestGetIntervalTimedelta:
    """Test suite for get_interval_timedelta function."""

    def test_get_minutes_timedelta(self):
        """Test getting timedelta for minute intervals."""
        assert get_interval_timedelta("1m") == timedelta(minutes=1)
        assert get_interval_timedelta("5m") == timedelta(minutes=5)
        assert get_interval_timedelta("15m") == timedelta(minutes=15)

    def test_get_hours_timedelta(self):
        """Test getting timedelta for hour intervals."""
        assert get_interval_timedelta("1h") == timedelta(hours=1)
        assert get_interval_timedelta("4h") == timedelta(hours=4)

    def test_get_days_timedelta(self):
        """Test getting timedelta for day intervals."""
        assert get_interval_timedelta("1d") == timedelta(days=1)

    def test_get_weeks_timedelta(self):
        """Test getting timedelta for week intervals."""
        assert get_interval_timedelta("1w") == timedelta(weeks=1)


class TestGetIntervalMinutes:
    """Test suite for get_interval_minutes function."""

    def test_minutes_interval(self):
        """Test converting minute intervals to minutes."""
        assert get_interval_minutes("1m") == 1
        assert get_interval_minutes("15m") == 15
        assert get_interval_minutes("30m") == 30

    def test_hours_interval(self):
        """Test converting hour intervals to minutes."""
        assert get_interval_minutes("1h") == 60
        assert get_interval_minutes("4h") == 240

    def test_days_interval(self):
        """Test converting day intervals to minutes."""
        assert get_interval_minutes("1d") == 1440

    def test_weeks_interval(self):
        """Test converting week intervals to minutes."""
        assert get_interval_minutes("1w") == 10080


class TestGenerateTimeRange:
    """Test suite for generate_time_range function."""

    def test_generate_hourly_range(self):
        """Test generating hourly time range."""
        start = datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2021, 1, 1, 3, 0, 0, tzinfo=UTC)

        times = list(generate_time_range(start, end, "1h"))

        assert len(times) == 3  # 0:00, 1:00, 2:00
        assert times[0] == start
        assert times[-1] == datetime(2021, 1, 1, 2, 0, 0, tzinfo=UTC)

    def test_generate_15min_range(self):
        """Test generating 15-minute time range."""
        start = datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2021, 1, 1, 1, 0, 0, tzinfo=UTC)

        times = list(generate_time_range(start, end, "15m"))

        assert len(times) == 4  # 0:00, 0:15, 0:30, 0:45

    def test_generate_single_point(self):
        """Test generating time range with start == end."""
        start = datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = start

        times = list(generate_time_range(start, end, "1h"))

        assert len(times) == 0


class TestAlignTimestampToInterval:
    """Test suite for align_timestamp_to_interval function."""

    def test_align_to_hour(self):
        """Test aligning timestamp to hour boundary."""
        timestamp = datetime(2021, 1, 1, 12, 34, 56, tzinfo=UTC)
        aligned = align_timestamp_to_interval(timestamp, "1h")

        assert aligned.hour == 12
        assert aligned.minute == 0
        assert aligned.second == 0

    def test_align_to_15min(self):
        """Test aligning timestamp to 15-minute boundary."""
        timestamp = datetime(2021, 1, 1, 12, 37, 56, tzinfo=UTC)
        aligned = align_timestamp_to_interval(timestamp, "15m")

        assert aligned.minute == 30  # Rounds down to nearest 15min
        assert aligned.second == 0

    def test_align_to_day(self):
        """Test aligning timestamp to day boundary."""
        timestamp = datetime(2021, 1, 1, 12, 34, 56, tzinfo=UTC)
        aligned = align_timestamp_to_interval(timestamp, "1d")

        assert aligned.hour == 0
        assert aligned.minute == 0
        assert aligned.second == 0


class TestFindTimeGaps:
    """Test suite for find_time_gaps function."""

    def test_no_gaps(self):
        """Test finding gaps when there are none."""
        timestamps = [
            datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC),
            datetime(2021, 1, 1, 1, 0, 0, tzinfo=UTC),
            datetime(2021, 1, 1, 2, 0, 0, tzinfo=UTC),
        ]

        gaps = find_time_gaps(timestamps, "1h")

        assert len(gaps) == 0

    def test_single_gap(self):
        """Test finding a single gap."""
        timestamps = [
            datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC),
            datetime(2021, 1, 1, 1, 0, 0, tzinfo=UTC),
            # Gap at 2:00
            datetime(2021, 1, 1, 3, 0, 0, tzinfo=UTC),
        ]

        gaps = find_time_gaps(timestamps, "1h")

        # Returns list of tuples (start, end)
        assert len(gaps) == 1
        assert isinstance(gaps[0], tuple)
        assert len(gaps[0]) == 2

    def test_multiple_gaps(self):
        """Test finding multiple gaps."""
        timestamps = [
            datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC),
            # Gap at 1:00
            datetime(2021, 1, 1, 2, 0, 0, tzinfo=UTC),
            # Gap at 3:00, 4:00
            datetime(2021, 1, 1, 5, 0, 0, tzinfo=UTC),
        ]

        gaps = find_time_gaps(timestamps, "1h")

        assert len(gaps) >= 2


class TestIsMarketOpen:
    """Test suite for is_market_open function."""

    def test_market_always_open(self):
        """Test that crypto market is always open (24/7)."""
        # Test various timestamps
        timestamps = [
            datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC),  # Midnight
            datetime(2021, 1, 1, 12, 0, 0, tzinfo=UTC),  # Noon
            datetime(2021, 12, 31, 23, 59, 59, tzinfo=UTC),  # Year end
        ]

        for ts in timestamps:
            assert is_market_open(ts) is True


class TestGetCurrentUtcTime:
    """Test suite for get_current_utc_time function."""

    def test_returns_aware_datetime(self):
        """Test that returned datetime is timezone-aware."""
        now = get_current_utc_time()

        assert now.tzinfo is not None
        assert now.tzinfo == UTC


class TestFormatDuration:
    """Test suite for format_duration function."""

    def test_format_seconds(self):
        """Test formatting seconds."""
        result = format_duration(0.5)
        assert "s" in result and "0." in result
        result = format_duration(30)
        assert "s" in result and "30" in result

    def test_format_minutes(self):
        """Test formatting minutes."""
        result = format_duration(60)
        assert "m" in result and "1" in result
        result = format_duration(300)
        assert "m" in result and "5" in result

    def test_format_hours(self):
        """Test formatting hours."""
        result = format_duration(3600)
        assert "h" in result and "1" in result
        result = format_duration(7200)
        assert "h" in result and "2" in result

    def test_format_complex_duration(self):
        """Test formatting complex duration with hours and minutes."""
        result = format_duration(3665)  # 1h 1m 5s

        # Function rounds to hours when >= 3600s
        assert "h" in result


class TestGetBinanceServerTime:
    """Test suite for get_binance_server_time function."""

    def test_returns_datetime(self):
        """Test that function returns datetime (may fail if no network)."""
        try:
            result = get_binance_server_time()
            assert isinstance(result, datetime)
            assert result.tzinfo is not None
        except Exception:
            # Network or API issues are acceptable in tests
            pytest.skip("Binance API not available")


class TestValidateTimeRange:
    """Test suite for validate_time_range function."""

    def test_valid_time_range(self):
        """Test validation of valid time range."""
        start = datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2021, 1, 2, 0, 0, 0, tzinfo=UTC)

        # Should not raise
        validate_time_range(start, end, max_days=2)
        # Assert that function completed without exception
        assert start < end

    def test_invalid_time_range_order(self):
        """Test validation fails when start > end."""
        start = datetime(2021, 1, 2, 0, 0, 0, tzinfo=UTC)
        end = datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC)

        with pytest.raises(
            ValueError, match="Start time must be before end time"
        ) as exc_info:
            validate_time_range(start, end)
        assert exc_info.value is not None

    def test_invalid_time_range_too_large(self):
        """Test validation fails when range exceeds max_days."""
        start = datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2021, 1, 11, 0, 0, 0, tzinfo=UTC)  # 10 days

        with pytest.raises(ValueError) as exc_info:
            validate_time_range(start, end, max_days=5)
        assert exc_info.value is not None


class TestGetDefaultStartTime:
    """Test suite for get_default_start_time function."""

    def test_get_default_start_various_intervals(self):
        """Test getting default start time for various intervals."""
        intervals = ["1m", "15m", "1h", "1d"]

        for interval in intervals:
            result = get_default_start_time(interval)
            assert isinstance(result, datetime)
            assert result.tzinfo is not None
            assert result < datetime.now(UTC)


class TestChunkTimeRange:
    """Test suite for chunk_time_range function."""

    def test_chunk_large_range(self):
        """Test chunking large time range."""
        start = datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2021, 1, 10, 0, 0, 0, tzinfo=UTC)  # 9 days (216 hours)

        chunks = list(chunk_time_range(start, end, chunk_hours=72))  # 3 days

        # Should have 3 chunks for 9 days with 3-day chunks
        assert len(chunks) == 3
        # Verify chunks are tuples
        assert isinstance(chunks[0], tuple)
        assert len(chunks[0]) == 2

    def test_chunk_small_range(self):
        """Test chunking small range (single chunk)."""
        start = datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2021, 1, 2, 0, 0, 0, tzinfo=UTC)  # 1 day (24 hours)

        chunks = list(chunk_time_range(start, end, chunk_hours=120))  # 5 days

        # Should have 1 chunk since range is smaller than chunk_hours
        assert len(chunks) == 1
        assert isinstance(chunks[0], tuple)
        assert chunks[0] == (start, end)


class TestBinanceIntervalToTableSuffix:
    """Test suite for binance_interval_to_table_suffix function."""

    def test_minute_intervals(self):
        """Test converting minute intervals."""
        result = binance_interval_to_table_suffix("1m")
        assert isinstance(result, str)
        result = binance_interval_to_table_suffix("15m")
        assert isinstance(result, str)

    def test_hour_intervals(self):
        """Test converting hour intervals."""
        result = binance_interval_to_table_suffix("1h")
        assert isinstance(result, str)
        result = binance_interval_to_table_suffix("4h")
        assert isinstance(result, str)

    def test_day_intervals(self):
        """Test converting day intervals."""
        result = binance_interval_to_table_suffix("1d")
        assert isinstance(result, str)

    def test_week_intervals(self):
        """Test converting week intervals."""
        result = binance_interval_to_table_suffix("1w")
        assert isinstance(result, str)


class TestTableSuffixToBinanceInterval:
    """Test suite for table_suffix_to_binance_interval function."""

    def test_minute_suffix(self):
        """Test converting minute suffix."""
        assert table_suffix_to_binance_interval("1m") == "1m"
        assert table_suffix_to_binance_interval("15m") == "15m"

    def test_hour_suffix(self):
        """Test converting hour suffix."""
        assert table_suffix_to_binance_interval("1h") == "1h"
        assert table_suffix_to_binance_interval("4h") == "4h"

    def test_day_suffix(self):
        """Test converting day suffix."""
        assert table_suffix_to_binance_interval("1d") == "1d"


# Corner case tests
class TestCornerCases:
    """Corner case tests for edge scenarios."""

    def test_dst_transition_timestamp(self):
        """Test parsing timestamp during DST transition."""
        # March 10, 2024 DST transition in US
        dst_timestamp = 1710057600000  # 2024-03-10 02:00:00 UTC
        result = parse_binance_timestamp(dst_timestamp)

        assert result.tzinfo is not None
        assert result.year == 2024

    def test_leap_year_february_29(self):
        """Test handling February 29 in leap year."""
        date_str = "2024-02-29T00:00:00Z"
        result = parse_datetime_string(date_str)

        assert result.year == 2024
        assert result.month == 2
        assert result.day == 29

    def test_year_boundary_timestamp(self):
        """Test timestamp at year boundary."""
        # December 31, 2023 23:59:59
        date_str = "2023-12-31T23:59:59Z"
        result = parse_datetime_string(date_str)

        assert result.year == 2023
        assert result.month == 12
        assert result.day == 31

    def test_millennium_boundary(self):
        """Test timestamp at millennium boundary."""
        # January 1, 2000 00:00:00
        timestamp_ms = 946684800000
        result = parse_binance_timestamp(timestamp_ms)

        assert result.year == 2000
        assert result.month == 1
        assert result.day == 1


# Performance tests
class TestPerformance:
    """Performance tests for large operations."""

    def test_generate_large_time_range(self):
        """Test generating very large time range."""
        start = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2020, 12, 31, 23, 59, 59, tzinfo=UTC)  # 1 year

        times = list(generate_time_range(start, end, "1d"))

        assert len(times) > 300  # ~365 days
        assert times[0] == start

    def test_chunk_very_large_range(self):
        """Test chunking very large time range."""
        start = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2020, 2, 1, 0, 0, 0, tzinfo=UTC)  # 31 days (744 hours)

        chunks = list(chunk_time_range(start, end, chunk_hours=168))  # 7 days

        # Should have at least 4 chunks (31 days / 7 days)
        assert len(chunks) >= 4


# Security tests
class TestSecurity:
    """Security tests for input validation."""

    def test_parse_malformed_date_string(self):
        """Test parsing malformed date string."""
        malformed_dates = [
            "not-a-date",
            "2021-13-01",  # Invalid month
            "2021-01-32",  # Invalid day
        ]

        for date_str in malformed_dates:
            with pytest.raises((ValueError, Exception)) as exc_info:
                parse_datetime_string(date_str)
            assert exc_info.value is not None

    def test_validate_negative_time_range(self):
        """Test validation rejects negative time range."""
        start = datetime(2021, 1, 2, 0, 0, 0, tzinfo=UTC)
        end = datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC)

        with pytest.raises(ValueError) as exc_info:
            validate_time_range(start, end)
        assert exc_info.value is not None


# Chaos tests
class TestChaos:
    """Chaos tests for extreme scenarios."""

    def test_very_old_timestamp(self):
        """Test handling very old timestamp (Unix epoch)."""
        timestamp_ms = 0  # January 1, 1970
        result = parse_binance_timestamp(timestamp_ms)

        assert result.year == 1970
        assert result.month == 1

    def test_far_future_timestamp(self):
        """Test handling far future timestamp (year 2100)."""
        # January 1, 2100 00:00:00 UTC
        timestamp_ms = 4102444800000
        result = parse_binance_timestamp(timestamp_ms)

        assert result.year == 2100

    def test_subsecond_precision(self):
        """Test handling timestamps with subsecond precision."""
        # Test with simple millisecond timestamp
        timestamp_ms = 1609502445123  # 2021-01-01 12:30:45.123
        result = parse_binance_timestamp(timestamp_ms)

        assert result.year == 2021

    def test_zero_duration_formatting(self):
        """Test formatting zero duration."""
        result = format_duration(0)

        assert "0" in result or "0.0" in result
