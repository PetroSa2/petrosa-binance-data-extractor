"""
Models package for Binance data structures.
"""

from .base import BaseTimestampedModel, BaseSymbolModel, ExtractionMetadata
from .kline import KlineModel
from .trade import TradeModel
from .funding_rate import FundingRateModel

__all__ = [
    'BaseTimestampedModel',
    'BaseSymbolModel',
    'ExtractionMetadata',
    'KlineModel',
    'TradeModel',
    'FundingRateModel'
]
