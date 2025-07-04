#!/usr/bin/env python3
"""
Tests for data models.
"""

import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


from models.base import BaseSymbolModel, BaseTimestampedModel, ExtractionMetadata
from models.funding_rate import FundingRateModel
from models.kline import KlineModel
from models.trade import TradeModel


class TestBaseModels:
    """Test base model functionality."""

    def test_base_timestamped_model_timestamp_parsing(self):
        """Test timestamp parsing from various formats."""
        # Test with datetime
        dt = datetime.now(timezone.utc)
        model = BaseTimestampedModel(timestamp=dt)
        assert model.timestamp == dt

        # Test with integer milliseconds
        ms_timestamp = 1640995200000
        model = BaseTimestampedModel(timestamp=ms_timestamp)
        expected = datetime.utcfromtimestamp(ms_timestamp / 1000)
        assert model.timestamp == expected

        # Test with integer seconds
        s_timestamp = 1640995200
        model = BaseTimestampedModel(timestamp=s_timestamp)
        expected = datetime.utcfromtimestamp(s_timestamp)
        assert model.timestamp == expected

    def test_base_symbol_model_symbol_validation(self):
        """Test symbol validation (uppercase conversion)."""
        model = BaseSymbolModel(timestamp=datetime.now(timezone.utc), symbol="btcusdt")
        assert model.symbol == "BTCUSDT"


class TestKlineModel:
    """Test KlineModel functionality."""

    def test_kline_model_creation(self):
        """Test basic KlineModel creation."""
        now = datetime.now(timezone.utc)

        kline = KlineModel(
            symbol="BTCUSDT",
            timestamp=now,
            open_time=now,
            close_time=now,
            interval="15m",
            open_price=Decimal("50000.00"),
            high_price=Decimal("50100.00"),
            low_price=Decimal("49900.00"),
            close_price=Decimal("50050.00"),
            volume=Decimal("100.5"),
            quote_asset_volume=Decimal("5000000.0"),
            number_of_trades=1500,
            taker_buy_base_asset_volume=Decimal("50.25"),
            taker_buy_quote_asset_volume=Decimal("2500000.0"),
        )

        assert kline.symbol == "BTCUSDT"
        assert kline.interval == "15m"
        assert kline.open_price == Decimal("50000.00")

        # Test derived fields calculation
        assert kline.price_change == Decimal("50.00")
        assert kline.price_change_percent == Decimal("0.1000")

    def test_kline_from_binance_data(self):
        """Test creating KlineModel from Binance API data."""
        binance_data = [
            1640995200000,  # open_time
            "50000.00",  # open_price
            "50100.00",  # high_price
            "49900.00",  # low_price
            "50050.00",  # close_price
            "100.50000000",  # volume
            1640996099999,  # close_time
            "5025000.00",  # quote_asset_volume
            1500,  # number_of_trades
            "50.25000000",  # taker_buy_base_asset_volume
            "2512500.00",  # taker_buy_quote_asset_volume
            "0",  # ignore
        ]

        kline = KlineModel.from_binance_kline(binance_data, "BTCUSDT", "15m")

        assert kline.symbol == "BTCUSDT"
        assert kline.interval == "15m"
        assert kline.open_price == Decimal("50000.00")
        assert kline.close_price == Decimal("50050.00")
        assert kline.volume == Decimal("100.50000000")
        assert kline.number_of_trades == 1500

    def test_kline_collection_name(self):
        """Test collection name generation."""
        kline = KlineModel(
            symbol="BTCUSDT",
            timestamp=datetime.now(timezone.utc),
            open_time=datetime.now(timezone.utc),
            close_time=datetime.now(timezone.utc),
            interval="1h",
            open_price=Decimal("50000"),
            high_price=Decimal("50000"),
            low_price=Decimal("50000"),
            close_price=Decimal("50000"),
            volume=Decimal("0"),
            quote_asset_volume=Decimal("0"),
            number_of_trades=0,
            taker_buy_base_asset_volume=Decimal("0"),
            taker_buy_quote_asset_volume=Decimal("0"),
        )

        assert kline.collection_name == "klines_h1"


class TestTradeModel:
    """Test TradeModel functionality."""

    def test_trade_model_creation(self):
        """Test basic TradeModel creation."""
        now = datetime.now(timezone.utc)

        trade = TradeModel(
            symbol="BTCUSDT",
            timestamp=now,
            trade_id=123456,
            price=Decimal("50000.00"),
            quantity=Decimal("0.01"),
            quote_quantity=Decimal("500.00"),
            is_buyer_maker=True,
            trade_time=now,
        )

        assert trade.symbol == "BTCUSDT"
        assert trade.trade_id == 123456
        assert trade.price == Decimal("50000.00")
        assert trade.is_buyer_maker is True

    def test_trade_from_binance_data(self):
        """Test creating TradeModel from Binance API data."""
        binance_data = {
            "id": 28457,
            "price": "50000.00",
            "qty": "0.01000000",
            "quoteQty": "500.00000000",
            "time": 1640995200000,
            "isBuyerMaker": True,
        }

        trade = TradeModel.from_binance_trade(binance_data, "BTCUSDT")

        assert trade.symbol == "BTCUSDT"
        assert trade.trade_id == 28457
        assert trade.price == Decimal("50000.00")
        assert trade.quantity == Decimal("0.01000000")
        assert trade.is_buyer_maker is True

    def test_trade_collection_name(self):
        """Test collection name."""
        trade = TradeModel(
            symbol="BTCUSDT",
            timestamp=datetime.now(timezone.utc),
            trade_id=123456,
            price=Decimal("50000"),
            quantity=Decimal("0.01"),
            quote_quantity=Decimal("500"),
            is_buyer_maker=True,
            trade_time=datetime.now(timezone.utc),
        )

        assert trade.collection_name == "trades"


class TestFundingRateModel:
    """Test FundingRateModel functionality."""

    def test_funding_rate_model_creation(self):
        """Test basic FundingRateModel creation."""
        now = datetime.now(timezone.utc)

        funding_rate = FundingRateModel(
            symbol="BTCUSDT",
            timestamp=now,
            funding_rate=Decimal("0.0001"),
            funding_time=now,
            mark_price=Decimal("50000.00"),
            index_price=Decimal("49998.50"),
        )

        assert funding_rate.symbol == "BTCUSDT"
        assert funding_rate.funding_rate == Decimal("0.0001")
        assert funding_rate.mark_price == Decimal("50000.00")

    def test_funding_rate_from_binance_data(self):
        """Test creating FundingRateModel from Binance API data."""
        binance_data = {
            "symbol": "BTCUSDT",
            "fundingRate": "0.00010000",
            "fundingTime": 1640995200000,
            "markPrice": "50000.00000000",
        }

        funding_rate = FundingRateModel.from_binance_funding_rate(binance_data, "BTCUSDT")

        assert funding_rate.symbol == "BTCUSDT"
        assert funding_rate.funding_rate == Decimal("0.00010000")
        assert funding_rate.mark_price == Decimal("50000.00000000")

    def test_funding_rate_calculations(self):
        """Test funding rate calculations."""
        funding_rate = FundingRateModel(
            symbol="BTCUSDT",
            timestamp=datetime.now(timezone.utc),
            funding_rate=Decimal("0.0001"),
            funding_time=datetime.now(timezone.utc),
        )

        # Test percentage calculation
        assert funding_rate.funding_rate_percentage == Decimal("0.01")

        # Test annualized rate (assuming 8-hour intervals)
        periods_per_year = Decimal("365") * Decimal("24") / Decimal("8")  # 1095 periods
        expected_annual = Decimal("0.0001") * periods_per_year
        assert funding_rate.annualized_funding_rate == expected_annual


class TestExtractionMetadata:
    """Test ExtractionMetadata functionality."""

    def test_extraction_metadata_creation(self):
        """Test ExtractionMetadata creation."""
        now = datetime.now(timezone.utc)

        metadata = ExtractionMetadata(
            period="15m",
            start_time=now,
            end_time=now,
            total_records=1000,
            gaps_detected=2,
            backfill_performed=True,
            extraction_duration_seconds=45.5,
            errors_encountered=["API timeout", "Rate limit"],
        )

        assert metadata.period == "15m"
        assert metadata.total_records == 1000
        assert metadata.gaps_detected == 2
        assert metadata.backfill_performed is True
        assert metadata.extraction_duration_seconds == 45.5
        assert len(metadata.errors_encountered) == 2
