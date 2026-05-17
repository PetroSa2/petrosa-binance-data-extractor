"""Cover the interval/suffix conversion branches in utils/time_utils."""

import pytest

from utils.time_utils import (
    binance_interval_to_table_suffix,
    table_suffix_to_binance_interval,
)


class TestBinanceIntervalToTableSuffix:
    @pytest.mark.parametrize(
        "interval,expected",
        [
            # Existing minute path
            ("15m", "m15"),
            ("1m", "m1"),
            # Hour path
            ("1h", "h1"),
            ("4h", "h4"),
            # Day path
            ("1d", "d1"),
            # Week path
            ("1w", "w1"),
            # Month path
            ("1M", "M1"),
            ("3M", "M3"),
        ],
    )
    def test_known_intervals(self, interval, expected):
        assert binance_interval_to_table_suffix(interval) == expected

    def test_unknown_suffix_returns_input_unchanged(self):
        # Fallback branch — return-as-is.
        assert binance_interval_to_table_suffix("zzz") == "zzz"


class TestTableSuffixToBinanceInterval:
    @pytest.mark.parametrize(
        "suffix,expected",
        [
            ("m15", "15m"),
            ("m1", "1m"),
            ("h1", "1h"),
            ("h4", "4h"),
            ("d1", "1d"),
            ("w1", "1w"),
            ("M1", "1M"),
            ("M3", "3M"),
        ],
    )
    def test_known_suffixes(self, suffix, expected):
        assert table_suffix_to_binance_interval(suffix) == expected

    def test_unknown_suffix_returns_input_unchanged(self):
        assert table_suffix_to_binance_interval("xyz") == "xyz"


class TestRoundTrip:
    @pytest.mark.parametrize("interval", ["15m", "1h", "4h", "1d", "1w", "1M"])
    def test_round_trip_preserves_value(self, interval):
        assert (
            table_suffix_to_binance_interval(binance_interval_to_table_suffix(interval))
            == interval
        )
