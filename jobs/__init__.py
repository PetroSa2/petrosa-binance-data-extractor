"""
Jobs package for Binance data extraction.

This package contains various data extraction jobs:
- extract_klines_production.py: Production-ready klines extractor for Kubernetes
- extract_klines_gap_filler.py: Gap detection and filling job
- extract_klines.py: Manual klines extraction with explicit date ranges
- extract_funding.py: Funding rates extraction
- extract_trades.py: Trades data extraction
"""

__version__ = "2.0.0"
__author__ = "Petrosa Team"

# Import main job classes for easier access
try:
    from .extract_klines_gap_filler import GapFillerExtractor
    from .extract_klines_production import ProductionKlinesExtractor
except ImportError:
    # Allow partial imports for testing
    pass

__all__ = [
    "ProductionKlinesExtractor",
    "GapFillerExtractor",
]
