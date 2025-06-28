"""
Unit tests for fetchers.
"""

import os
import sys
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from decimal import Decimal

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from fetchers.client import BinanceClient, BinanceAPIError
from fetchers.klines import KlinesFetcher
from fetchers.trades import TradesFetcher
from fetchers.funding import FundingRatesFetcher


class TestBinanceClient:
    """Test BinanceClient functionality."""

    @patch("fetchers.client.requests.Session")
    def test_client_initialization(self, mock_session_class):
        """Test client initialization."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        client = BinanceClient(api_key="test_key", api_secret="test_secret")

        assert client.api_key == "test_key"
        assert client.api_secret == "test_secret"
        assert client.base_url == "https://fapi.binance.com"
        mock_session_class.assert_called_once()

    @patch("fetchers.client.requests.Session")
    def test_client_get_request_success(self, mock_session_class):
        """Test successful GET request."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"serverTime": 1640995200000}
        mock_response.content = b'{"serverTime": 1640995200000}'
        mock_session.get.return_value = mock_response

        client = BinanceClient()
        result = client.get("/fapi/v1/time")

        assert result == {"serverTime": 1640995200000}
        mock_session.get.assert_called_once()

    @patch("fetchers.client.requests.Session")
    def test_client_get_request_error(self, mock_session_class):
        """Test GET request with API error."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"code": -1000, "msg": "Invalid request"}
        mock_response.content = b'{"code": -1000, "msg": "Invalid request"}'
        mock_session.get.return_value = mock_response

        client = BinanceClient()

        with pytest.raises(BinanceAPIError) as exc_info:
            client.get("/fapi/v1/invalid")

        assert "Invalid request" in str(exc_info.value)
        assert exc_info.value.status_code == 400

    @patch("fetchers.client.requests.Session")
    def test_client_rate_limit_error(self, mock_session_class):
        """Test rate limit error handling."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock rate limit response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_response.json.return_value = {"code": -1003, "msg": "Too many requests"}
        mock_response.content = b'{"code": -1003, "msg": "Too many requests"}'
        mock_session.get.return_value = mock_response

        client = BinanceClient()

        with pytest.raises(BinanceAPIError) as exc_info:
            client.get("/fapi/v1/klines")

        assert "Rate limit exceeded" in str(exc_info.value)
        assert exc_info.value.status_code == 429


class TestKlinesFetcher:
    """Test KlinesFetcher functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = Mock(spec=BinanceClient)
        self.fetcher = KlinesFetcher(self.mock_client)

    def test_klines_fetcher_initialization(self):
        """Test KlinesFetcher initialization."""
        fetcher = KlinesFetcher()
        assert fetcher.client is not None
        assert fetcher.max_klines_per_request == 1500

    def test_fetch_klines_success(self):
        """Test successful klines fetching."""
        # Mock Binance API response
        mock_klines_data = [
            [
                1640995200000,  # open_time
                "50000.00",  # open_price
                "50100.00",  # high_price
                "49900.00",  # low_price
                "50050.00",  # close_price
                "100.50",  # volume
                1640996099999,  # close_time
                "5025000.00",  # quote_asset_volume
                1500,  # number_of_trades
                "50.25",  # taker_buy_base_asset_volume
                "2512500.00",  # taker_buy_quote_asset_volume
                "0",  # ignore
            ],
            [
                1640996100000,  # Next 15m candle
                "50050.00",
                "50150.00",
                "49950.00",
                "50100.00",
                "120.75",
                1640996999999,
                "6030000.00",
                1800,
                "60.30",
                "3015000.00",
                "0",
            ],
        ]

        # Mock the client to return data on first call, empty on subsequent calls
        call_count = 0
        def mock_get_klines(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_klines_data
            else:
                return []  # No more data
        
        self.mock_client.get_klines.side_effect = mock_get_klines

        start_time = datetime(2022, 1, 1, tzinfo=timezone.utc)
        end_time = datetime(2022, 1, 1, 1, tzinfo=timezone.utc)

        klines = self.fetcher.fetch_klines("BTCUSDT", "15m", start_time, end_time)

        assert len(klines) == 2
        assert klines[0].symbol == "BTCUSDT"
        assert klines[0].interval == "15m"
        assert klines[0].open_price == Decimal("50000.00")
        assert klines[1].close_price == Decimal("50100.00")

        self.mock_client.get_klines.assert_called()

    def test_fetch_latest_klines(self):
        """Test fetching latest klines."""
        mock_klines_data = [
            [
                1640995200000,
                "50000.00",
                "50100.00",
                "49900.00",
                "50050.00",
                "100.50",
                1640996099999,
                "5025000.00",
                1500,
                "50.25",
                "2512500.00",
                "0",
            ]
        ]

        self.mock_client.get_klines.return_value = mock_klines_data

        klines = self.fetcher.fetch_latest_klines("BTCUSDT", "15m", 100)

        assert len(klines) == 1
        assert klines[0].symbol == "BTCUSDT"

        self.mock_client.get_klines.assert_called_with(
            symbol="BTCUSDT", interval="15m", limit=100
        )

    @patch("fetchers.klines.get_current_utc_time")
    def test_fetch_incremental(self, mock_current_time):
        """Test incremental fetching."""
        # Mock current time to be just a short time after the last timestamp
        last_timestamp = datetime(2022, 1, 1, tzinfo=timezone.utc)
        mock_current_time.return_value = datetime(2022, 1, 1, 1, tzinfo=timezone.utc)

        mock_klines_data = [
            [
                1640995200000,
                "50000.00",
                "50100.00",
                "49900.00",
                "50050.00",
                "100.50",
                1640996099999,
                "5025000.00",
                1500,
                "50.25",
                "2512500.00",
                "0",
            ]
        ]

        # Mock the client to return data on first call, empty on subsequent calls
        call_count = 0
        def mock_get_klines_incremental(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_klines_data
            else:
                return []  # No more data
        
        self.mock_client.get_klines.side_effect = mock_get_klines_incremental

        klines = self.fetcher.fetch_incremental("BTCUSDT", "15m", last_timestamp)

        assert len(klines) == 1
        self.mock_client.get_klines.assert_called()

    def test_fetch_multiple_symbols(self):
        """Test fetching multiple symbols."""
        mock_klines_data = [
            [
                1640995200000,
                "50000.00",
                "50100.00",
                "49900.00",
                "50050.00",
                "100.50",
                1640996099999,
                "5025000.00",
                1500,
                "50.25",
                "2512500.00",
                "0",
            ]
        ]

        # Mock the client to return data on first call per symbol, empty on subsequent calls
        call_count = 0
        def mock_get_klines_multiple(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Return data for the first call for each symbol (2 symbols total)
            # After that, return empty to prevent infinite loops
            if call_count <= 2:
                return mock_klines_data
            else:
                return []  # No more data
        
        self.mock_client.get_klines.side_effect = mock_get_klines_multiple

        symbols = ["BTCUSDT", "ETHUSDT"]
        start_time = datetime(2022, 1, 1, tzinfo=timezone.utc)
        end_time = datetime(2022, 1, 1, 0, 15, tzinfo=timezone.utc)  # Match mock data range

        results = self.fetcher.fetch_multiple_symbols(
            symbols, "15m", start_time, end_time
        )

        assert len(results) == 2
        assert "BTCUSDT" in results
        assert "ETHUSDT" in results
        assert len(results["BTCUSDT"]) == 1
        assert len(results["ETHUSDT"]) == 1


class TestTradesFetcher:
    """Test TradesFetcher functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = Mock(spec=BinanceClient)
        self.fetcher = TradesFetcher(self.mock_client)

    def test_trades_fetcher_initialization(self):
        """Test TradesFetcher initialization."""
        fetcher = TradesFetcher()
        assert fetcher.client is not None
        assert fetcher.max_trades_per_request == 1000

    def test_fetch_recent_trades(self):
        """Test fetching recent trades."""
        mock_trades_data = [
            {
                "id": 28457,
                "price": "50000.00",
                "qty": "0.01000000",
                "quoteQty": "500.00000000",
                "time": 1640995200000,
                "isBuyerMaker": True,
            },
            {
                "id": 28458,
                "price": "50050.00",
                "qty": "0.02000000",
                "quoteQty": "1001.00000000",
                "time": 1640995210000,
                "isBuyerMaker": False,
            },
        ]

        self.mock_client.get_recent_trades.return_value = mock_trades_data

        trades = self.fetcher.fetch_recent_trades("BTCUSDT", 1000)

        assert len(trades) == 2
        assert trades[0].symbol == "BTCUSDT"
        assert trades[0].trade_id == 28457
        assert trades[0].price == Decimal("50000.00")
        assert trades[0].is_buyer_maker is True
        assert trades[1].trade_id == 28458
        assert trades[1].is_buyer_maker is False

        self.mock_client.get_recent_trades.assert_called_with(
            symbol="BTCUSDT", limit=1000
        )

    def test_fetch_historical_trades(self):
        """Test fetching historical trades."""
        mock_trades_data = [
            {
                "id": 28457,
                "price": "50000.00",
                "qty": "0.01000000",
                "quoteQty": "500.00000000",
                "time": 1640995200000,
                "isBuyerMaker": True,
            }
        ]

        self.mock_client.get_historical_trades.return_value = mock_trades_data

        trades = self.fetcher.fetch_historical_trades(
            "BTCUSDT", from_id=28457, limit=1000
        )

        assert len(trades) == 1
        assert trades[0].trade_id == 28457

        self.mock_client.get_historical_trades.assert_called_with(
            symbol="BTCUSDT", from_id=28457, limit=1000
        )


class TestFundingRatesFetcher:
    """Test FundingRatesFetcher functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = Mock(spec=BinanceClient)
        self.fetcher = FundingRatesFetcher(self.mock_client)

    def test_funding_rates_fetcher_initialization(self):
        """Test FundingRatesFetcher initialization."""
        fetcher = FundingRatesFetcher()
        assert fetcher.client is not None
        assert fetcher.max_records_per_request == 1000

    def test_fetch_funding_rate_history(self):
        """Test fetching funding rate history."""
        mock_funding_data = [
            {
                "symbol": "BTCUSDT",
                "fundingRate": "0.00010000",
                "fundingTime": 1640995200000,
                "markPrice": "50000.00000000",
            },
            {
                "symbol": "BTCUSDT",
                "fundingRate": "0.00015000",
                "fundingTime": 1641024000000,
                "markPrice": "50500.00000000",
            },
        ]

        self.mock_client.get_funding_rate.return_value = mock_funding_data

        rates = self.fetcher.fetch_funding_rate_history("BTCUSDT", limit=1000)

        assert len(rates) == 2
        assert rates[0].symbol == "BTCUSDT"
        assert rates[0].funding_rate == Decimal("0.00010000")
        assert rates[0].mark_price == Decimal("50000.00000000")
        assert rates[1].funding_rate == Decimal("0.00015000")

        self.mock_client.get_funding_rate.assert_called_with(
            symbol="BTCUSDT", limit=1000
        )

    def test_fetch_current_funding_rates_single_symbol(self):
        """Test fetching current funding rates for single symbol."""
        mock_premium_data = {
            "symbol": "BTCUSDT",
            "markPrice": "50000.00000000",
            "indexPrice": "49998.12345678",
            "estimatedSettlePrice": "50000.00000000",
            "lastFundingRate": "0.00010000",
            "nextFundingTime": 1640995200000,
            "interestRate": "0.00010000",
            "time": 1640995100000,
        }

        self.mock_client.get_premium_index.return_value = mock_premium_data

        rates = self.fetcher.fetch_current_funding_rates(["BTCUSDT"])

        assert len(rates) == 1
        assert rates[0].symbol == "BTCUSDT"
        assert rates[0].funding_rate == Decimal("0.00010000")
        assert rates[0].mark_price == Decimal("50000.00000000")
        assert rates[0].index_price == Decimal("49998.12345678")

        self.mock_client.get_premium_index.assert_called_with(symbol="BTCUSDT")

    def test_fetch_current_funding_rates_all_symbols(self):
        """Test fetching current funding rates for all symbols."""
        mock_premium_data = [
            {
                "symbol": "BTCUSDT",
                "markPrice": "50000.00000000",
                "indexPrice": "49998.12345678",
                "lastFundingRate": "0.00010000",
                "nextFundingTime": 1640995200000,
                "time": 1640995100000,
            },
            {
                "symbol": "ETHUSDT",
                "markPrice": "3000.00000000",
                "indexPrice": "2998.12345678",
                "lastFundingRate": "0.00005000",
                "nextFundingTime": 1640995200000,
                "time": 1640995100000,
            },
        ]

        self.mock_client.get_premium_index.return_value = mock_premium_data

        rates = self.fetcher.fetch_current_funding_rates()

        assert len(rates) == 2
        assert rates[0].symbol == "BTCUSDT"
        assert rates[1].symbol == "ETHUSDT"
        assert rates[0].funding_rate == Decimal("0.00010000")
        assert rates[1].funding_rate == Decimal("0.00005000")

        self.mock_client.get_premium_index.assert_called_with()

    def test_get_funding_schedule(self):
        """Test getting funding schedule."""
        mock_premium_data = {
            "symbol": "BTCUSDT",
            "markPrice": "50000.00000000",
            "indexPrice": "49998.12345678",
            "lastFundingRate": "0.00010000",
            "nextFundingTime": 1640995200000,
            "time": 1640995100000,
        }

        self.mock_client.get_premium_index.return_value = mock_premium_data

        schedule = self.fetcher.get_funding_schedule("BTCUSDT")

        assert schedule["symbol"] == "BTCUSDT"
        assert schedule["current_funding_rate"] == "0.00010000"
        assert schedule["mark_price"] == "50000.00000000"
        assert schedule["funding_interval_hours"] == 8
        assert isinstance(schedule["next_funding_time"], datetime)

        self.mock_client.get_premium_index.assert_called_with(symbol="BTCUSDT")
