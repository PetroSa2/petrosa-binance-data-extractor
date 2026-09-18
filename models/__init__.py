"""
Models package for Binance data structures.
"""

from .base import BaseSymbolModel, BaseTimestampedModel, ExtractionMetadata
from .candle import CandleModel, candle_collection_name
from .funding_rate import FundingRateModel
from .kline import KlineModel

__all__ = [
    "BaseTimestampedModel",
    "BaseSymbolModel",
    "ExtractionMetadata",
    "KlineModel",
    "FundingRateModel",
    "CandleModel",
    "candle_collection_name",
]
