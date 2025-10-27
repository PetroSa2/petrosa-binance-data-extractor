"""Tests for error handling in klines_data_manager.py."""

import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fetchers.klines_data_manager import KlinesFetcherDataManager
from fetchers.client import BinanceAPIError


@pytest.fixture
def mock_binance_client():
    """Fixture for a mocked BinanceClient."""
    return MagicMock()


@pytest.fixture
def mock_data_manager_adapter():
    """Fixture for a mocked DataManagerAdapter."""
    mock = MagicMock()
    mock.connect = AsyncMock()
    mock.disconnect = AsyncMock()
    mock.write = AsyncMock(return_value=1)
    mock.query_latest = AsyncMock(return_value=[])
    mock.find_gaps = AsyncMock(return_value=[])
    mock.health_check = AsyncMock(return_value={"status": "healthy"})
    return mock


@pytest.fixture
@patch("fetchers.klines_data_manager.DataManagerAdapter")
def klines_fetcher(
    MockDataManagerAdapter, mock_binance_client, mock_data_manager_adapter
):
    """Fixture for a KlinesFetcherDataManager with mocked dependencies."""
    MockDataManagerAdapter.return_value = mock_data_manager_adapter
    fetcher = KlinesFetcherDataManager(client=mock_binance_client)
    fetcher.data_adapter = mock_data_manager_adapter
    return fetcher


@pytest.mark.asyncio
async def test_fetch_and_store_api_error_rate_limit(klines_fetcher):
    """Test handling of rate limit errors (429) during fetch."""
    symbol = "BTCUSDT"
    interval = "1m"
    start_time = datetime(2023, 1, 1, tzinfo=UTC)
    end_time = start_time + timedelta(minutes=2)

    # Simulate rate limit error then success
    rate_limit_error = BinanceAPIError("Rate limit exceeded", 429)
    klines_fetcher.client.get_klines.side_effect = [
        rate_limit_error,  # First call hits rate limit
        [],  # After wait, returns empty (no more data)
    ]

    with patch("time.sleep"):  # Mock sleep to avoid actual delay
        result = await klines_fetcher.fetch_and_store_klines(
            symbol, interval, start_time, end_time
        )

    # Should handle rate limit gracefully and retry
    assert isinstance(result, list)
    assert klines_fetcher.client.get_klines.call_count == 2


@pytest.mark.asyncio
async def test_fetch_and_store_api_error_non_rate_limit(klines_fetcher):
    """Test handling of non-rate-limit API errors."""
    symbol = "BTCUSDT"
    interval = "1m"
    start_time = datetime(2023, 1, 1, tzinfo=UTC)
    end_time = start_time + timedelta(minutes=2)

    # Simulate non-rate-limit API error (should raise)
    api_error = BinanceAPIError("Server error", 500)
    klines_fetcher.client.get_klines.side_effect = api_error

    with pytest.raises(BinanceAPIError) as exc_info:
        await klines_fetcher.fetch_and_store_klines(
            symbol, interval, start_time, end_time
        )

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_fetch_and_store_unexpected_error(klines_fetcher):
    """Test handling of unexpected errors during fetch."""
    symbol = "BTCUSDT"
    interval = "1m"
    start_time = datetime(2023, 1, 1, tzinfo=UTC)
    end_time = start_time + timedelta(minutes=2)

    # Simulate unexpected error
    klines_fetcher.client.get_klines.side_effect = ValueError("Unexpected error")

    with pytest.raises(ValueError) as exc_info:
        await klines_fetcher.fetch_and_store_klines(
            symbol, interval, start_time, end_time
        )

    assert "Unexpected error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_and_store_parse_error_handling(klines_fetcher):
    """Test that parse errors are logged but don't stop processing."""
    symbol = "BTCUSDT"
    interval = "1m"
    start_time = datetime(2023, 1, 1, tzinfo=UTC)
    end_time = start_time + timedelta(minutes=2)

    # Mock data with one invalid kline that will fail parsing
    valid_kline = [
        1672531200000, "100", "110", "90", "105", "1000",
        1672531259999, "105000", 100, "500", "52500", "0"
    ]
    
    # First call returns valid data, second returns invalid, third returns empty
    klines_fetcher.client.get_klines.side_effect = [
        [valid_kline],
        ["invalid_data"],  # This will fail parsing
        [],  # No more data
    ]

    # Mock the KlineModel.from_binance_kline to raise error on invalid data
    with patch("fetchers.klines_data_manager.KlineModel.from_binance_kline") as mock_parse:
        mock_parse.side_effect = [
            MagicMock(close_time=datetime(2023, 1, 1, 0, 0, 59, 999000, tzinfo=UTC)),  # Valid
            ValueError("Invalid kline data"),  # Invalid - should be caught and logged
        ]
        
        # Should complete successfully despite parse error
        result = await klines_fetcher.fetch_and_store_klines(
            symbol, interval, start_time, end_time
        )

    # Should have processed the valid kline
    assert len(result) >= 1

