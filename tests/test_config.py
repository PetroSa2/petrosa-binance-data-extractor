#!/usr/bin/env python3
"""
Tests for config module.

This module tests the functionality of config/symbols.py.
"""

import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import pytest

from config.symbols import (DEVELOPMENT_SYMBOLS, PRODUCTION_SYMBOLS,
                            get_symbols_for_environment)


class TestSymbolsConfig:
    """Test cases for symbols configuration."""

    def test_production_symbols_defined(self):
        """Test that production symbols are properly defined."""
        assert isinstance(PRODUCTION_SYMBOLS, list)
        assert len(PRODUCTION_SYMBOLS) > 0
        assert all(isinstance(symbol, str) for symbol in PRODUCTION_SYMBOLS)

        # Check for specific expected symbols
        assert "BTCUSDT" in PRODUCTION_SYMBOLS
        assert "ETHUSDT" in PRODUCTION_SYMBOLS
        assert "BNBUSDT" in PRODUCTION_SYMBOLS

    def test_development_symbols_defined(self):
        """Test that development symbols are properly defined."""
        assert isinstance(DEVELOPMENT_SYMBOLS, list)
        assert len(DEVELOPMENT_SYMBOLS) > 0
        assert all(isinstance(symbol, str) for symbol in DEVELOPMENT_SYMBOLS)

        # Check for specific expected symbols
        assert "BTCUSDT" in DEVELOPMENT_SYMBOLS
        assert "ETHUSDT" in DEVELOPMENT_SYMBOLS
        assert "BNBUSDT" in DEVELOPMENT_SYMBOLS

    def test_development_symbols_subset_of_production(self):
        """Test that development symbols are a subset of production symbols."""
        for dev_symbol in DEVELOPMENT_SYMBOLS:
            assert dev_symbol in PRODUCTION_SYMBOLS

    def test_symbols_format(self):
        """Test that all symbols follow the expected format."""
        all_symbols = PRODUCTION_SYMBOLS + DEVELOPMENT_SYMBOLS
        for symbol in all_symbols:
            # Check format: should end with USDT
            assert symbol.endswith("USDT")
            # Should be uppercase
            assert symbol.isupper()
            # Should not be empty
            assert len(symbol) > 4

    def test_get_symbols_for_environment_production(self):
        """Test getting symbols for production environment."""
        symbols = get_symbols_for_environment("production")
        assert symbols == PRODUCTION_SYMBOLS

    def test_get_symbols_for_environment_production_uppercase(self):
        """Test getting symbols for production environment with uppercase."""
        symbols = get_symbols_for_environment("PRODUCTION")
        assert symbols == PRODUCTION_SYMBOLS

    def test_get_symbols_for_environment_development(self):
        """Test getting symbols for development environment."""
        symbols = get_symbols_for_environment("development")
        assert symbols == DEVELOPMENT_SYMBOLS

    def test_get_symbols_for_environment_development_uppercase(self):
        """Test getting symbols for development environment with uppercase."""
        symbols = get_symbols_for_environment("DEVELOPMENT")
        assert symbols == DEVELOPMENT_SYMBOLS

    def test_get_symbols_for_environment_default(self):
        """Test getting symbols with default environment (should be production)."""
        symbols = get_symbols_for_environment()
        assert symbols == PRODUCTION_SYMBOLS

    def test_get_symbols_for_environment_unknown(self):
        """Test getting symbols for unknown environment (should default to development)."""
        symbols = get_symbols_for_environment("unknown")
        assert symbols == DEVELOPMENT_SYMBOLS

    def test_get_symbols_for_environment_empty_string(self):
        """Test getting symbols for empty string environment (should default to development)."""
        symbols = get_symbols_for_environment("")
        assert symbols == DEVELOPMENT_SYMBOLS

    def test_get_symbols_for_environment_none(self):
        """Test getting symbols for None environment (should default to development)."""
        symbols = get_symbols_for_environment(None)
        assert symbols == DEVELOPMENT_SYMBOLS

    def test_symbols_uniqueness(self):
        """Test that all symbols are unique."""
        assert len(PRODUCTION_SYMBOLS) == len(set(PRODUCTION_SYMBOLS))
        assert len(DEVELOPMENT_SYMBOLS) == len(set(DEVELOPMENT_SYMBOLS))

    def test_symbols_content(self):
        """Test specific content of symbol lists."""
        # Production should have more symbols than development
        assert len(PRODUCTION_SYMBOLS) > len(DEVELOPMENT_SYMBOLS)

        # Development should have at least 5 symbols
        assert len(DEVELOPMENT_SYMBOLS) >= 5

        # Production should have at least 19 symbols
        assert len(PRODUCTION_SYMBOLS) >= 19
