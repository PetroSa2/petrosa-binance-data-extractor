from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fetchers.klines_data_manager import KlinesFetcherDataManager
from models.kline import KlineModel


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
async def test_initialization(klines_fetcher, mock_binance_client):
    """Test that the fetcher is initialized correctly."""
    assert klines_fetcher.client == mock_binance_client
    assert klines_fetcher.data_adapter is not None


@pytest.mark.asyncio
@pytest.mark.skip(reason="Test has infinite loop bug - mock returns same klines repeatedly causing timeout. See issue #159")
async def test_fetch_and_store_klines_success(klines_fetcher, mock_binance_client):
    """Test successful fetching and storing of klines."""
    start_time = datetime(2023, 1, 1, tzinfo=UTC)
    end_time = start_time + timedelta(minutes=5)
    symbol = "BTCUSDT"
    interval = "1m"

    mock_kline_data = [
        [
            1672531200000,
            "100",
            "110",
            "90",
            "105",
            "1000",
            1672531259999,
            "105000",
            100,
            "500",
            "52500",
            "0",
        ],
        [
            1672531260000,
            "105",
            "115",
            "95",
            "110",
            "1100",
            1672531319999,
            "115500",
            110,
            "550",
            "57750",
            "0",
        ],
    ]
    mock_binance_client.get_klines.return_value = mock_kline_data

    result = await klines_fetcher.fetch_and_store_klines(
        symbol, interval, start_time, end_time
    )

    assert len(result) == 2
    assert isinstance(result[0], KlineModel)
    klines_fetcher.data_adapter.write.assert_called_once()
    assert (
        klines_fetcher.data_adapter.write.call_args[1]["collection_name"]
        == f"klines_{interval}"
    )


@pytest.mark.asyncio
async def test_get_latest_timestamp_found(klines_fetcher):
    """Test get_latest_timestamp when a timestamp is found."""
    symbol = "BTCUSDT"
    interval = "1m"
    timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
    klines_fetcher.data_adapter.query_latest.return_value = [
        {"close_time": timestamp.isoformat()}
    ]

    result = await klines_fetcher.get_latest_timestamp(symbol, interval)

    assert result == timestamp
    klines_fetcher.data_adapter.query_latest.assert_called_once_with(
        collection_name=f"klines_{interval}", symbol=symbol, limit=1
    )


@pytest.mark.asyncio
async def test_get_latest_timestamp_not_found(klines_fetcher):
    """Test get_latest_timestamp when no timestamp is found."""
    symbol = "BTCUSDT"
    interval = "1m"
    klines_fetcher.data_adapter.query_latest.return_value = []

    result = await klines_fetcher.get_latest_timestamp(symbol, interval)

    assert result is None


@pytest.mark.asyncio
async def test_find_gaps_found(klines_fetcher):
    """Test find_gaps when gaps are found."""
    symbol = "BTCUSDT"
    interval = "1m"
    start_time = datetime(2023, 1, 1, tzinfo=UTC)
    end_time = start_time + timedelta(hours=1)
    gaps = [{"gap_start": "2023-01-01T00:10:00", "gap_end": "2023-01-01T00:20:00"}]
    klines_fetcher.data_adapter.find_gaps.return_value = gaps

    result = await klines_fetcher.find_gaps(symbol, interval, start_time, end_time)

    assert result == gaps
    klines_fetcher.data_adapter.find_gaps.assert_called_once()


@pytest.mark.asyncio
async def test_health_check_healthy(klines_fetcher, mock_binance_client):
    """Test health_check when all services are healthy."""
    mock_binance_client.get_server_time.return_value = {}  # Simulate success

    result = await klines_fetcher.health_check()

    assert result["overall"] == "healthy"
    assert result["data_manager"]["status"] == "healthy"
    assert result["binance_api"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_check_data_manager_unhealthy(klines_fetcher, mock_binance_client):
    """Test health_check when Data Manager is unhealthy."""
    mock_binance_client.get_server_time.return_value = {}  # Simulate success
    klines_fetcher.data_adapter.health_check.return_value = {"status": "unhealthy"}

    result = await klines_fetcher.health_check()

    assert result["overall"] == "unhealthy"
    assert result["data_manager"]["status"] == "unhealthy"
    assert result["binance_api"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_check_binance_unhealthy(klines_fetcher, mock_binance_client):
    """Test health_check when Binance API is unhealthy."""
    mock_binance_client.get_server_time.side_effect = Exception("Binance API is down")

    result = await klines_fetcher.health_check()

    assert result["overall"] == "unhealthy"
    assert result["data_manager"]["status"] == "healthy"
    assert result["binance_api"]["status"] == "unhealthy"
