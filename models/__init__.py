"""
Models package for Binance data structures.
"""

from .base import BaseSymbolModel, BaseTimestampedModel, ExtractionMetadata
from .funding_rate import FundingRateModel
from .kline import KlineModel
from .trade import TradeModel

__all__ = [
    'BaseTimestampedModel',
    'BaseSymbolModel',
    'ExtractionMetadata',
    'KlineModel',
    'TradeModel',
    'FundingRateModel'
]
