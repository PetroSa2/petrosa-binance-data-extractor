"""Tests for the data-manager backed configuration manager."""

import json
from unittest.mock import patch

import httpx
import pytest

import constants
from services.config_manager import ConfigManager

RealAsyncClient = httpx.AsyncClient


def client_for(handler):
    transport = httpx.MockTransport(handler)
    return RealAsyncClient(
        transport=transport, base_url=constants.DATA_MANAGER_URL, timeout=5.0
    )


@pytest.mark.asyncio
async def test_get_symbols_returns_stored_value():
    def handler(request):
        return httpx.Response(200, json={"value": ["BTCUSDT"]})

    with patch("services.config_manager.httpx.AsyncClient", lambda **_: client_for(handler)):
        assert await ConfigManager().get_symbols() == ["BTCUSDT"]


@pytest.mark.asyncio
async def test_get_symbols_404_returns_default():
    with patch(
        "services.config_manager.httpx.AsyncClient",
        lambda **_: client_for(lambda request: httpx.Response(404)),
    ):
        assert await ConfigManager().get_symbols() == constants.DEFAULT_SYMBOLS


@pytest.mark.asyncio
async def test_get_symbols_unreachable_logs_and_returns_default(caplog):
    def handler(request):
        raise httpx.ConnectError("data-manager down", request=request)

    with patch("services.config_manager.httpx.AsyncClient", lambda **_: client_for(handler)):
        with caplog.at_level("ERROR"):
            result = await ConfigManager().get_symbols()
    assert result == constants.DEFAULT_SYMBOLS
    assert "unavailable" in caplog.text


@pytest.mark.asyncio
async def test_set_symbols_sends_audited_value():
    def handler(request):
        assert request.method == "PUT"
        assert request.url.path.endswith("/binance-data-extractor/keys/symbols")
        assert json.loads(request.content) == {
            "value": ["BTCUSDT"],
            "changed_by": "tester",
            "reason": "why",
        }
        return httpx.Response(200, json={"value": ["BTCUSDT"]})

    with patch("services.config_manager.httpx.AsyncClient", lambda **_: client_for(handler)):
        await ConfigManager().set_symbols(["BTCUSDT"], "tester", "why")


@pytest.mark.asyncio
async def test_rate_limits_defaults_and_setter():
    calls = []

    def handler(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(404)
        assert json.loads(request.content) == {
            "value": {"requests_per_minute": 900, "concurrent_requests": 4},
            "changed_by": "tester",
            "reason": "why",
        }
        return httpx.Response(200, json={})

    with patch("services.config_manager.httpx.AsyncClient", lambda **_: client_for(handler)):
        manager = ConfigManager()
        assert await manager.get_rate_limits() == {
            "requests_per_minute": constants.API_RATE_LIMIT_PER_MINUTE,
            "concurrent_requests": constants.MAX_WORKERS,
        }
        await manager.set_rate_limits(900, 4, "tester", "why")
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_setter_raises_on_http_error():
    with patch(
        "services.config_manager.httpx.AsyncClient",
        lambda **_: client_for(lambda request: httpx.Response(500)),
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await ConfigManager().set_symbols(["BTCUSDT"], "tester", "why")
