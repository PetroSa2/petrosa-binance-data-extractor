"""
HTTP client wrapper for Binance API with retry and rate limiting.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import constants
from utils.retry import RateLimiter, with_retries_and_rate_limit
from utils.time_utils import get_current_utc_time

# Try to import requests
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry  # type: ignore[import]

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)


class BinanceAPIError(Exception):
    """Custom exception for Binance API errors."""

    def __init__(
        self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class BinanceClient:
    """
    HTTP client for Binance Futures API with built-in retry and rate limiting.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        """
        Initialize Binance client.

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            base_url: Base URL for API
            rate_limiter: Custom rate limiter instance
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError(
                "requests library is required. Install with: pip install requests"
            )

        self.api_key = api_key or constants.API_KEY
        self.api_secret = api_secret or constants.API_SECRET
        self.base_url = base_url or constants.BINANCE_API_URL

        # Set up rate limiter
        self.rate_limiter = rate_limiter or RateLimiter(
            max_calls=constants.API_RATE_LIMIT_PER_MINUTE, time_window=60
        )

        # Set up session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Default headers
        self.session.headers.update(
            {
                "User-Agent": f"BinanceExtractor/{constants.OTEL_SERVICE_VERSION}",
                "Content-Type": "application/json",
            }
        )

        if self.api_key:
            self.session.headers.update({"X-MBX-APIKEY": self.api_key})

        logger.info("Binance client initialized")

    def _build_url(self, endpoint: str) -> str:
        """Build full URL for endpoint."""
        return f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    def _log_request(self, method: str, url: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Log API request details."""
        logger.debug(
            "API Request: %s %s",
            method,
            url,
            extra={
                "method": method,
                "url": url,
                "params": params or {},
                "timestamp": get_current_utc_time().isoformat(),
            },
        )

    def _log_response(self, response: "requests.Response", duration: float) -> None:
        """Log API response details."""
        logger.debug(
            "API Response: %s in %.3fs",
            response.status_code,
            duration,
            extra={
                "status_code": response.status_code,
                "duration_seconds": duration,
                "response_size": len(response.content) if response.content else 0,
                "timestamp": get_current_utc_time().isoformat(),
            },
        )

    @with_retries_and_rate_limit
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make GET request to Binance API.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            Response data as dictionary

        Raises:
            BinanceAPIError: If API request fails
        """
        url = self._build_url(endpoint)
        params = params or {}

        # Apply rate limiting
        self.rate_limiter.wait_if_needed()

        self._log_request("GET", url, params)

        try:
            start_time = get_current_utc_time()
            response = self.session.get(url, params=params, timeout=30)
            duration = (get_current_utc_time() - start_time).total_seconds()

            self._log_response(response, duration)

            # Handle different response codes
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                # Rate limit exceeded
                retry_after = response.headers.get("Retry-After", "60")
                raise BinanceAPIError(
                    f"Rate limit exceeded. Retry after {retry_after} seconds",
                    status_code=response.status_code,
                    response_data=response.json() if response.content else {},
                )
            else:
                # Other errors
                error_data = {}
                try:
                    error_data = response.json()
                except (json.JSONDecodeError, ValueError):
                    error_data = {"msg": response.text}

                raise BinanceAPIError(
                    f"API request failed: {error_data.get('msg', 'Unknown error')}",
                    status_code=response.status_code,
                    response_data=error_data,
                )

        except requests.exceptions.RequestException as e:
            raise BinanceAPIError(f"Network error: {str(e)}") from e

    def get_server_time(self) -> datetime:
        """Get Binance server time."""
        try:
            response = self.get("/fapi/v1/time")
            timestamp = response["serverTime"]
            return datetime.utcfromtimestamp(timestamp / 1000)
        except requests.exceptions.RequestException as e:
            logger.warning("Failed to get server time: %s, using local time", e)
            return get_current_utc_time()

    def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange information."""
        return self.get("/fapi/v1/exchangeInfo")

    def ping(self) -> bool:
        """Ping the API to check connectivity."""
        try:
            self.get("/fapi/v1/ping")
            return True
        except BinanceAPIError as e:
            logger.error("API ping failed: %s", e)
            return False

    def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1500,
    ) -> List[List]:
        """
        Get kline/candlestick data.

        Args:
            symbol: Trading symbol
            interval: Kline interval
            start_time: Start time
            end_time: End time
            limit: Number of records to return (max 1500)

        Returns:
            List of kline data arrays
        """
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": min(limit, 1500),  # Binance limit
        }

        if start_time:
            params["startTime"] = int(start_time.timestamp() * 1000)

        if end_time:
            params["endTime"] = int(end_time.timestamp() * 1000)

        return self.get("/fapi/v1/klines", params)

    def get_recent_trades(self, symbol: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get recent trades.

        Args:
            symbol: Trading symbol
            limit: Number of trades to return (max 1000)

        Returns:
            List of trade data
        """
        params = {"symbol": symbol.upper(), "limit": min(limit, 1000)}

        return self.get("/fapi/v1/trades", params)

    def get_historical_trades(
        self, symbol: str, from_id: Optional[int] = None, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get historical trades (requires API key).

        Args:
            symbol: Trading symbol
            from_id: Trade ID to start from
            limit: Number of trades to return

        Returns:
            List of trade data
        """
        if not self.api_key:
            raise BinanceAPIError("API key required for historical trades")

        params = {"symbol": symbol.upper(), "limit": min(limit, 1000)}

        if from_id:
            params["fromId"] = from_id

        return self.get("/fapi/v1/historicalTrades", params)

    def get_funding_rate(
        self, symbol: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get funding rate history.

        Args:
            symbol: Trading symbol (optional, if None returns all symbols)
            limit: Number of records to return

        Returns:
            List of funding rate data
        """
        params: Dict[str, Any] = {"limit": min(limit, 1000)}

        if symbol:
            params["symbol"] = symbol.upper()

        return self.get("/fapi/v1/fundingRate", params)

    def get_premium_index(
        self, symbol: Optional[str] = None
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Get mark price and funding rate.

        Args:
            symbol: Trading symbol (optional)

        Returns:
            Premium index data
        """
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()

        return self.get("/fapi/v1/premiumIndex", params)

    def close(self) -> None:
        """Close the client session."""
        if self.session:
            self.session.close()
            logger.info("Binance client session closed")

    def __enter__(self) -> "BinanceClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
