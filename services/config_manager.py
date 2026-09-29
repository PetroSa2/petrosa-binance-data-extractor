"""Configuration manager for data extractor settings."""

import logging
from typing import Any

import httpx

import constants

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manage runtime configuration through data-manager."""

    SERVICE = "binance-data-extractor"

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=constants.DATA_MANAGER_URL,
            timeout=5.0,
            headers=constants.get_data_manager_headers(),
        )

    async def _get_value(self, key: str, default: Any) -> Any:
        try:
            async with self._client() as client:
                response = await client.get(
                    f"/api/v1/config/services/{self.SERVICE}/keys/{key}"
                )
            if response.status_code == 404:
                return default
            response.raise_for_status()
            return response.json().get("value", default)
        except httpx.RequestError as exc:
            logger.error("Data-manager unavailable while reading %s: %s", key, exc)
            return default

    async def _set_value(
        self, key: str, value: Any, changed_by: str, reason: str | None
    ) -> None:
        async with self._client() as client:
            response = await client.put(
                f"/api/v1/config/services/{self.SERVICE}/keys/{key}",
                json={"value": value, "changed_by": changed_by, "reason": reason},
            )
        response.raise_for_status()

    async def get_symbols(self) -> list[str]:
        """Get configured symbols, falling back safely when unavailable."""
        return await self._get_value("symbols", constants.DEFAULT_SYMBOLS)

    async def set_symbols(
        self, symbols: list[str], changed_by: str, reason: str | None = None
    ) -> None:
        """Update symbols through data-manager with an audit record."""
        await self._set_value("symbols", symbols, changed_by, reason)

    async def get_rate_limits(self) -> dict[str, Any]:
        """Get configured rate limits, falling back to service defaults."""
        defaults = {
            "requests_per_minute": constants.API_RATE_LIMIT_PER_MINUTE,
            "concurrent_requests": constants.MAX_WORKERS,
        }
        return await self._get_value("rate_limits", defaults)

    async def set_rate_limits(
        self,
        requests_per_minute: int,
        concurrent_requests: int,
        changed_by: str,
        reason: str | None = None,
    ) -> None:
        """Update rate limits through data-manager with an audit record."""
        await self._set_value(
            "rate_limits",
            {
                "requests_per_minute": requests_per_minute,
                "concurrent_requests": concurrent_requests,
            },
            changed_by,
            reason,
        )


_config_manager: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    """Get the global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def set_config_manager(manager: ConfigManager) -> None:
    """Set the global config manager instance, primarily for tests."""
    global _config_manager
    _config_manager = manager
