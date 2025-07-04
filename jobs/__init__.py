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

# Note: We don't import job classes here to avoid circular imports
# when running modules with python -m jobs.extract_klines_production
# Import them directly in your code when needed:
# from jobs.extract_klines_production import ProductionKlinesExtractor
# from jobs.extract_klines_gap_filler import GapFillerExtractor

__all__ = [
    # Empty list to avoid automatic imports
]
