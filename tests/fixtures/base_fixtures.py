"""
Comprehensive base fixtures for Petrosa Binance Data Extractor tests.

This module provides standardized fixtures following the Petrosa testing standards
with realistic market data, comprehensive mocking, and proper async handling.
"""

import asyncio
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest
from pydantic import ValidationError

from models.base import ExtractionMetadata
from models.funding_rate import FundingRate
from models.kline import Kline
from models.trade import Trade


class TestingConstants:
    """Constants for testing."""

    DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT"]
    DEFAULT_INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"]
    BASE_TIMESTAMP = 1672531200000  # 2023-01-01 00:00:00 UTC


@pytest.fixture(scope="session")
def test_constants():
    """Provide testing constants."""
    return TestingConstants


@pytest.fixture(autouse=True)
def mock_environment_variables():
    """Set up test environment variables automatically for all tests."""
    test_env = {
        "ENVIRONMENT": "testing",
        "LOG_LEVEL": "DEBUG",
        "OTEL_NO_AUTO_INIT": "1",
        "MONGODB_URI": "mongodb://localhost:27017/test_petrosa",
        "MYSQL_HOST": "localhost",
        "MYSQL_PORT": "3306",
        "MYSQL_USER": "test_user",
        "MYSQL_PASSWORD": "test_password",
        "MYSQL_DATABASE": "test_petrosa",
        "BINANCE_API_KEY": "test-api-key-12345",
        "BINANCE_API_SECRET": "test-api-secret-67890",
        "BINANCE_BASE_URL": "https://fapi.binance.com",
        "NATS_URL": "nats://localhost:4222",
        "NATS_ENABLED": "false",
        "RATE_LIMIT_REQUESTS_PER_MINUTE": "1200",
        "BATCH_SIZE": "1000",
        "MAX_WORKERS": "4",
    }

    with patch.dict(os.environ, test_env, clear=False):
        yield test_env


@pytest.fixture
def realistic_klines_data() -> list[dict[str, Any]]:
    """Generate realistic OHLCV data matching Binance API format."""
    base_price = 50000.0
    num_candles = 100

    # Generate realistic price movements
    np.random.seed(42)  # For reproducible tests
    price_changes = np.random.normal(0, 0.02, num_candles)  # 2% volatility
    volumes = np.random.lognormal(7, 1, num_candles)  # Log-normal volume distribution

    data = []
    current_time = TestingConstants.BASE_TIMESTAMP
    current_price = base_price

    for i in range(num_candles):
        # Calculate price movement
        price_change = price_changes[i]
        new_price = current_price * (1 + price_change)

        # Generate realistic OHLC
        volatility = abs(price_change) * 2
        high = max(current_price, new_price) * (1 + abs(volatility))
        low = min(current_price, new_price) * (1 - abs(volatility))
        open_price = current_price
        close_price = new_price
        volume = volumes[i]

        # Calculate derived values
        quote_volume = (high + low + open_price + close_price) / 4 * volume
        trades = int(volume / 10)  # Approximate trades
        taker_buy_volume = volume * np.random.uniform(0.4, 0.6)
        taker_buy_quote = taker_buy_volume * ((high + low) / 2)

        data.append(
            {
                "openTime": current_time,
                "open": f"{open_price:.8f}",
                "high": f"{high:.8f}",
                "low": f"{low:.8f}",
                "close": f"{close_price:.8f}",
                "volume": f"{volume:.8f}",
                "closeTime": current_time + 59999,  # 1 minute interval
                "quoteAssetVolume": f"{quote_volume:.8f}",
                "numberOfTrades": trades,
                "takerBuyBaseAssetVolume": f"{taker_buy_volume:.8f}",
                "takerBuyQuoteAssetVolume": f"{taker_buy_quote:.8f}",
            }
        )

        current_time += 60000  # 1 minute
        current_price = new_price

    return data


@pytest.fixture
def realistic_funding_data() -> list[dict[str, Any]]:
    """Generate realistic funding rate data."""
    symbols = TestingConstants.DEFAULT_SYMBOLS
    base_time = TestingConstants.BASE_TIMESTAMP

    data = []
    for i, symbol in enumerate(symbols):
        # Generate realistic funding rates (-0.1% to +0.1%)
        funding_rate = np.random.uniform(-0.001, 0.001)
        funding_time = base_time + (i * 28800000)  # 8 hours apart

        data.append(
            {
                "symbol": symbol,
                "fundingRate": f"{funding_rate:.8f}",
                "fundingTime": funding_time,
                "nextFundingTime": funding_time + 28800000,
            }
        )

    return data


@pytest.fixture
def realistic_trades_data() -> list[dict[str, Any]]:
    """Generate realistic trade data."""
    base_price = 50000.0
    base_time = TestingConstants.BASE_TIMESTAMP

    data = []
    for i in range(50):
        price_variation = np.random.uniform(0.95, 1.05)
        price = base_price * price_variation
        quantity = np.random.lognormal(0, 1)  # Log-normal quantity

        data.append(
            {
                "id": 1000000 + i,
                "price": f"{price:.8f}",
                "qty": f"{quantity:.8f}",
                "quoteQty": f"{price * quantity:.8f}",
                "time": base_time + (i * 1000),  # 1 second apart
                "isBuyerMaker": np.random.choice([True, False]),
                "isBestMatch": np.random.choice([True, False], p=[0.8, 0.2]),
            }
        )

    return data


@pytest.fixture
def sample_kline_models(realistic_klines_data) -> list[Kline]:
    """Create sample Kline model instances."""
    models = []
    for data in realistic_klines_data[:10]:  # Use first 10 for testing
        models.append(
            Kline(
                symbol="BTCUSDT",
                interval="1m",
                open_time=datetime.utcfromtimestamp(data["openTime"] / 1000),
                close_time=datetime.utcfromtimestamp(data["closeTime"] / 1000),
                open_price=Decimal(data["open"]),
                high_price=Decimal(data["high"]),
                low_price=Decimal(data["low"]),
                close_price=Decimal(data["close"]),
                volume=Decimal(data["volume"]),
                quote_asset_volume=Decimal(data["quoteAssetVolume"]),
                number_of_trades=data["numberOfTrades"],
                taker_buy_base_asset_volume=Decimal(data["takerBuyBaseAssetVolume"]),
                taker_buy_quote_asset_volume=Decimal(data["takerBuyQuoteAssetVolume"]),
                timestamp=datetime.utcfromtimestamp(data["openTime"] / 1000),
            )
        )
    return models


@pytest.fixture
def sample_funding_models(realistic_funding_data) -> list[FundingRate]:
    """Create sample FundingRate model instances."""
    models = []
    for data in realistic_funding_data:
        models.append(
            FundingRate(
                symbol=data["symbol"],
                funding_rate=Decimal(data["fundingRate"]),
                funding_time=datetime.utcfromtimestamp(data["fundingTime"] / 1000),
                next_funding_time=datetime.utcfromtimestamp(
                    data["nextFundingTime"] / 1000
                ),
                timestamp=datetime.utcfromtimestamp(data["fundingTime"] / 1000),
            )
        )
    return models


@pytest.fixture
def sample_trade_models(realistic_trades_data) -> list[Trade]:
    """Create sample Trade model instances."""
    models = []
    for data in realistic_trades_data:
        models.append(
            Trade(
                symbol="BTCUSDT",
                trade_id=data["id"],
                price=Decimal(data["price"]),
                quantity=Decimal(data["qty"]),
                quote_quantity=Decimal(data["quoteQty"]),
                trade_time=datetime.utcfromtimestamp(data["time"] / 1000),
                is_buyer_maker=data["isBuyerMaker"],
                is_best_match=data["isBestMatch"],
                timestamp=datetime.utcfromtimestamp(data["time"] / 1000),
            )
        )
    return models


@pytest.fixture
def sample_extraction_metadata() -> ExtractionMetadata:
    """Create sample extraction metadata."""
    return ExtractionMetadata(
        period="15m",
        start_time=datetime.utcfromtimestamp(TestingConstants.BASE_TIMESTAMP / 1000),
        end_time=datetime.utcfromtimestamp(TestingConstants.BASE_TIMESTAMP / 1000)
        + timedelta(hours=24),
        total_records=1000,
        gaps_detected=2,
        backfill_performed=True,
        extraction_duration_seconds=45.5,
        errors_encountered=["Rate limit hit at 14:30", "Connection timeout at 15:45"],
    )


@pytest.fixture
def mock_binance_client():
    """Mock Binance API client with realistic responses."""
    client = Mock()

    # Mock successful responses
    client.get_klines = Mock()
    client.get_funding_rate = Mock()
    client.get_trades = Mock()
    client.get_exchange_info = Mock(
        return_value={
            "symbols": [
                {"symbol": "BTCUSDT", "status": "TRADING"},
                {"symbol": "ETHUSDT", "status": "TRADING"},
            ]
        }
    )

    # Mock rate limiting
    client.rate_limiter = Mock()
    client.rate_limiter.acquire = Mock()

    return client


@pytest.fixture
def mock_database_adapter():
    """Mock database adapter with realistic behavior."""
    adapter = Mock()

    # Mock connection methods
    adapter.connect = Mock()
    adapter.disconnect = Mock()
    adapter.is_connected = Mock(return_value=True)

    # Mock write operations
    adapter.write = Mock(return_value=10)
    adapter.write_batch = Mock(return_value=100)

    # Mock query operations
    adapter.query_range = Mock(return_value=[])
    adapter.query_latest = Mock(return_value=[])
    adapter.get_record_count = Mock(return_value=0)
    adapter.find_gaps = Mock(return_value=[])

    # Mock maintenance operations
    adapter.ensure_indexes = Mock()
    adapter.delete_range = Mock(return_value=0)

    return adapter


@pytest.fixture
async def mock_async_database_adapter():
    """Mock async database adapter."""
    adapter = AsyncMock()

    # Mock async methods
    adapter.connect = AsyncMock()
    adapter.disconnect = AsyncMock()
    adapter.write_batch_async = AsyncMock(return_value=100)
    adapter.query_range_async = AsyncMock(return_value=[])

    return adapter


@pytest.fixture
def mock_requests_session():
    """Mock requests session with realistic HTTP responses."""
    session = Mock()

    # Create mock response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json = Mock(return_value={"data": []})
    mock_response.headers = {"X-MBX-USED-WEIGHT-1M": "10"}
    mock_response.raise_for_status = Mock()

    # Mock session methods
    session.get = Mock(return_value=mock_response)
    session.post = Mock(return_value=mock_response)
    session.request = Mock(return_value=mock_response)

    return session


@pytest.fixture
def mock_pymongo_client():
    """Mock PyMongo client with realistic MongoDB behavior."""
    client = Mock()
    database = Mock()
    collection = Mock()

    # Mock collection operations
    collection.insert_many = Mock(return_value=Mock(inserted_ids=[1, 2, 3]))
    collection.find = Mock(return_value=[])
    collection.count_documents = Mock(return_value=0)
    collection.create_index = Mock()
    collection.delete_many = Mock(return_value=Mock(deleted_count=0))

    # Mock database and client hierarchy
    database.__getitem__ = Mock(return_value=collection)
    client.__getitem__ = Mock(return_value=database)
    client.close = Mock()

    return client


@pytest.fixture
def mock_pymysql_connection():
    """Mock PyMySQL connection with realistic MySQL behavior."""
    connection = Mock()
    cursor = Mock()

    # Mock cursor operations
    cursor.execute = Mock()
    cursor.executemany = Mock()
    cursor.fetchall = Mock(return_value=[])
    cursor.fetchone = Mock(return_value=None)
    cursor.rowcount = 0
    cursor.close = Mock()

    # Mock connection context manager
    cursor_context = Mock()
    cursor_context.__enter__ = Mock(return_value=cursor)
    cursor_context.__exit__ = Mock(return_value=None)
    connection.cursor = Mock(return_value=cursor_context)
    connection.commit = Mock()
    connection.rollback = Mock()
    connection.close = Mock()

    return connection


@pytest.fixture
def error_scenarios():
    """Provide common error scenarios for testing."""
    return {
        "connection_error": ConnectionError("Failed to connect to database"),
        "timeout_error": TimeoutError("Request timed out"),
        "rate_limit_error": Exception("Rate limit exceeded"),
        "validation_error": ValidationError("Invalid data format", Mock),
        "api_error": Exception("API returned error 400"),
        "network_error": Exception("Network unreachable"),
    }


@pytest.fixture
def performance_thresholds():
    """Define performance thresholds for testing."""
    return {
        "max_processing_time": 30.0,  # seconds
        "max_memory_increase": 100,  # MB
        "min_throughput": 1000,  # records/second
        "max_error_rate": 0.01,  # 1%
    }


@pytest.fixture(scope="function")
def event_loop():
    """Create a new event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_telemetry():
    """Mock OpenTelemetry components."""
    with patch("otel_init.initialize_telemetry"):
        yield


@pytest.fixture
def test_data_generator():
    """Utility class for generating test data."""

    class TestDataGenerator:
        @staticmethod
        def generate_price_series(
            start_price: float = 50000.0,
            length: int = 100,
            volatility: float = 0.02,
            trend: float = 0.0,
        ) -> list[float]:
            """Generate realistic price series."""
            np.random.seed(42)
            changes = np.random.normal(trend, volatility, length)
            prices = [start_price]

            for change in changes[1:]:
                prices.append(prices[-1] * (1 + change))

            return prices

        @staticmethod
        def generate_gaps(
            start_time: datetime,
            end_time: datetime,
            interval_minutes: int = 15,
            gap_probability: float = 0.05,
        ) -> list[tuple[datetime, datetime]]:
            """Generate realistic data gaps."""
            gaps = []
            current = start_time

            while current < end_time:
                if np.random.random() < gap_probability:
                    gap_duration = np.random.choice([1, 2, 3, 5]) * interval_minutes
                    gap_end = current + timedelta(minutes=gap_duration)
                    gaps.append((current, gap_end))
                    current = gap_end
                else:
                    current += timedelta(minutes=interval_minutes)

            return gaps

    return TestDataGenerator()


# Parameterized test fixtures
@pytest.fixture(params=TestingConstants.DEFAULT_SYMBOLS)
def symbol(request):
    """Parameterized symbol fixture."""
    return request.param


@pytest.fixture(params=TestingConstants.DEFAULT_INTERVALS)
def interval(request):
    """Parameterized interval fixture."""
    return request.param


@pytest.fixture(params=[10, 100, 1000])
def batch_size(request):
    """Parameterized batch size fixture."""
    return request.param


@pytest.fixture(params=[1, 2, 4, 8])
def worker_count(request):
    """Parameterized worker count fixture."""
    return request.param
