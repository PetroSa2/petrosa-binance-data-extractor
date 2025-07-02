"""
Fetchers package for Binance API clients.
"""

from .client import BinanceAPIError, BinanceClient
from .funding import FundingRatesFetcher
from .klines import KlinesFetcher
from .trades import TradesFetcher

__all__ = ["BinanceClient", "BinanceAPIError", "KlinesFetcher", "TradesFetcher", "FundingRatesFetcher"]
