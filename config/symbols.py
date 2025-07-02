# Production Symbol Configuration
# This file defines the symbols to extract in production environments

from typing import List

# Top 20 cryptocurrency futures symbols by volume
PRODUCTION_SYMBOLS = [
    # Major cryptocurrencies
    "BTCUSDT",    # Bitcoin
    "ETHUSDT",    # Ethereum
    "BNBUSDT",    # Binance Coin
    "XRPUSDT",    # Ripple
    "ADAUSDT",    # Cardano
    "SOLUSDT",    # Solana
    "DOTUSDT",    # Polkadot
    "AVAXUSDT",   # Avalanche
    "MATICUSDT",  # Polygon
    "LINKUSDT",   # Chainlink

    # DeFi tokens
    "UNIUSDT",    # Uniswap
    "AAVEUSDT",   # Aave
    "SUSHIUSDT",  # SushiSwap
    "COMPUSDT",   # Compound

    # Layer 1 blockchains
    "NEARUSDT",   # Near Protocol
    "ALGOUSDT",   # Algorand
    "ATOMUSDT",   # Cosmos
    "FTMUSDT",    # Fantom

    # Meme coins (high volume)
    "DOGEUSDT",   # Dogecoin
]

# Development/testing symbols (smaller list)
DEVELOPMENT_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "ADAUSDT",
    "SOLUSDT"
]

# Get symbols based on environment


def get_symbols_for_environment(environment: str = "production") -> List[str]:
    """
    Get symbols list based on environment.

    Args:
        environment: "production" or "development"

    Returns:
        List of symbol strings
    """
    env = str(environment).lower() if environment else ""
    if env == "production":
        return PRODUCTION_SYMBOLS
    else:
        return DEVELOPMENT_SYMBOLS
