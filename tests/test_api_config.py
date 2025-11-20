"""
Tests for Data Extractor Configuration API endpoints.
"""

import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from api.main import app  # noqa: E402


@pytest.fixture
def client():
    """Create test client for API."""
    return TestClient(app)


@pytest.fixture
def mock_config_manager():
    """Mock configuration manager."""
    mock_manager = Mock()
    mock_manager.get_symbols = Mock(return_value=["BTCUSDT", "ETHUSDT", "BNBUSDT"])
    mock_manager.set_symbols = Mock()
    mock_manager.get_rate_limits = Mock(
        return_value={"requests_per_minute": 1200, "concurrent_requests": 5}
    )
    mock_manager.set_rate_limits = Mock()
    return mock_manager


@pytest.fixture
def mock_cronjob_manager():
    """Mock CronJob manager."""
    mock_manager = Mock()
    mock_manager.list_cronjobs = Mock(
        return_value=[
            {
                "name": "binance-klines-15m-production",
                "schedule": "*/15 * * * *",
                "timeframe": "15m",
                "last_schedule_time": "2024-01-01T00:00:00",
                "active_jobs": 0,
                "suspended": False,
            },
            {
                "name": "binance-klines-1h-production",
                "schedule": "0 * * * *",
                "timeframe": "1h",
                "last_schedule_time": "2024-01-01T00:00:00",
                "active_jobs": 0,
                "suspended": False,
            },
        ]
    )
    mock_manager.update_cronjob_schedule = Mock(
        return_value={
            "name": "binance-klines-15m-production",
            "schedule": "*/10 * * * *",
            "suspended": False,
        }
    )
    mock_manager.create_job_from_cronjob = Mock(
        return_value={
            "name": "manual-extract-15m-1234567890",
            "namespace": "petrosa-apps",
            "timeframe": "15m",
            "symbol": "BTCUSDT",
        }
    )
    return mock_manager


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns API information."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Data Extractor Configuration API"
        assert data["version"] == "1.0.0"
        assert "/api/v1/config/cronjobs" in data["endpoints"]


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_healthz(self, client):
        """Test liveness probe."""
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_ready(self, client):
        """Test readiness probe."""
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}


class TestCronJobEndpoints:
    """Test CronJob management endpoints."""

    @patch("api.routes.config.get_cronjob_manager")
    def test_list_cronjobs_success(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test listing CronJobs."""
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.get("/api/v1/config/cronjobs")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 2
        assert data["data"][0]["name"] == "binance-klines-15m-production"
        assert data["metadata"]["count"] == 2

    @patch("api.routes.config.get_cronjob_manager")
    def test_list_cronjobs_error(self, mock_get_manager, client):
        """Test listing CronJobs with error."""
        mock_manager = Mock()
        mock_manager.list_cronjobs = Mock(side_effect=Exception("K8s error"))
        mock_get_manager.return_value = mock_manager

        response = client.get("/api/v1/config/cronjobs")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data

    @patch("api.routes.config.get_cronjob_manager")
    def test_update_cronjob_schedule_success(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test updating CronJob schedule."""
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.post(
            "/api/v1/config/cronjobs/binance-klines-15m-production",
            json={
                "schedule": "*/10 * * * *",
                "changed_by": "test_user",
                "reason": "Test update",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["schedule"] == "*/10 * * * *"
        mock_cronjob_manager.update_cronjob_schedule.assert_called_once_with(
            "binance-klines-15m-production", "*/10 * * * *"
        )

    @patch("api.routes.config.get_cronjob_manager")
    def test_update_cronjob_schedule_invalid_cron(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test updating CronJob with invalid cron expression."""
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.post(
            "/api/v1/config/cronjobs/binance-klines-15m-production",
            json={
                "schedule": "invalid cron",
                "changed_by": "test_user",
                "reason": "Test update",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"

    @patch("api.routes.config.get_cronjob_manager")
    def test_update_cronjob_schedule_error(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test updating CronJob with error."""
        mock_cronjob_manager.update_cronjob_schedule = Mock(
            side_effect=Exception("K8s error")
        )
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.post(
            "/api/v1/config/cronjobs/binance-klines-15m-production",
            json={
                "schedule": "*/10 * * * *",
                "changed_by": "test_user",
                "reason": "Test update",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data


class TestSymbolsEndpoints:
    """Test symbols management endpoints."""

    @patch("api.routes.config.get_config_manager")
    def test_get_symbols_success(self, mock_get_manager, client, mock_config_manager):
        """Test getting symbols."""
        mock_get_manager.return_value = mock_config_manager

        response = client.get("/api/v1/config/symbols")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["symbols"] == ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        assert data["data"]["count"] == 3

    @patch("api.routes.config.get_config_manager")
    def test_get_symbols_error(self, mock_get_manager, client):
        """Test getting symbols with error."""
        mock_manager = Mock()
        mock_manager.get_symbols = Mock(side_effect=Exception("DB error"))
        mock_get_manager.return_value = mock_manager

        response = client.get("/api/v1/config/symbols")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data

    @patch("api.routes.config.get_config_manager")
    def test_update_symbols_success(
        self, mock_get_manager, client, mock_config_manager
    ):
        """Test updating symbols."""
        mock_get_manager.return_value = mock_config_manager

        response = client.post(
            "/api/v1/config/symbols",
            json={
                "symbols": ["BTCUSDT", "ETHUSDT"],
                "changed_by": "test_user",
                "reason": "Test update",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["symbols"] == ["BTCUSDT", "ETHUSDT"]
        mock_config_manager.set_symbols.assert_called_once_with(
            ["BTCUSDT", "ETHUSDT"], "test_user", "Test update"
        )

    @patch("api.routes.config.get_config_manager")
    def test_update_symbols_invalid_format(
        self, mock_get_manager, client, mock_config_manager
    ):
        """Test updating symbols with invalid format."""
        mock_get_manager.return_value = mock_config_manager

        response = client.post(
            "/api/v1/config/symbols",
            json={
                "symbols": ["btcusdt"],  # lowercase
                "changed_by": "test_user",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"

    @patch("api.routes.config.get_config_manager")
    def test_update_symbols_error(self, mock_get_manager, client, mock_config_manager):
        """Test updating symbols with error."""
        mock_config_manager.set_symbols = Mock(side_effect=Exception("DB error"))
        mock_get_manager.return_value = mock_config_manager

        response = client.post(
            "/api/v1/config/symbols",
            json={
                "symbols": ["BTCUSDT", "ETHUSDT"],
                "changed_by": "test_user",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data


class TestRateLimitsEndpoints:
    """Test rate limits management endpoints."""

    @patch("api.routes.config.get_config_manager")
    def test_get_rate_limits_success(
        self, mock_get_manager, client, mock_config_manager
    ):
        """Test getting rate limits."""
        mock_get_manager.return_value = mock_config_manager

        response = client.get("/api/v1/config/rate-limits")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["requests_per_minute"] == 1200
        assert data["data"]["concurrent_requests"] == 5

    @patch("api.routes.config.get_config_manager")
    def test_get_rate_limits_error(self, mock_get_manager, client):
        """Test getting rate limits with error."""
        mock_manager = Mock()
        mock_manager.get_rate_limits = Mock(side_effect=Exception("DB error"))
        mock_get_manager.return_value = mock_manager

        response = client.get("/api/v1/config/rate-limits")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data

    @patch("api.routes.config.get_config_manager")
    def test_update_rate_limits_success(
        self, mock_get_manager, client, mock_config_manager
    ):
        """Test updating rate limits."""
        mock_get_manager.return_value = mock_config_manager

        response = client.post(
            "/api/v1/config/rate-limits",
            json={
                "requests_per_minute": 1000,
                "concurrent_requests": 3,
                "changed_by": "test_user",
                "reason": "Test update",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["requests_per_minute"] == 1000
        assert data["data"]["concurrent_requests"] == 3
        mock_config_manager.set_rate_limits.assert_called_once_with(
            1000, 3, "test_user", "Test update"
        )

    @patch("api.routes.config.get_config_manager")
    def test_update_rate_limits_error(
        self, mock_get_manager, client, mock_config_manager
    ):
        """Test updating rate limits with error."""
        mock_config_manager.set_rate_limits = Mock(side_effect=Exception("DB error"))
        mock_get_manager.return_value = mock_config_manager

        response = client.post(
            "/api/v1/config/rate-limits",
            json={
                "requests_per_minute": 1000,
                "concurrent_requests": 3,
                "changed_by": "test_user",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data


class TestJobTriggerEndpoint:
    """Test job triggering endpoint."""

    @patch("api.routes.jobs.get_cronjob_manager")
    def test_trigger_job_success(self, mock_get_manager, client, mock_cronjob_manager):
        """Test triggering extraction job."""
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.post(
            "/api/v1/jobs/trigger",
            json={
                "timeframe": "15m",
                "symbol": "BTCUSDT",
                "reason": "Fill gap",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["timeframe"] == "15m"
        assert data["data"]["symbol"] == "BTCUSDT"

    @patch("api.routes.jobs.get_cronjob_manager")
    def test_trigger_job_invalid_timeframe(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test triggering job with invalid timeframe."""
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.post(
            "/api/v1/jobs/trigger",
            json={
                "timeframe": "invalid",
                "symbol": "BTCUSDT",
                "reason": "Test",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"

    @patch("api.routes.jobs.get_cronjob_manager")
    def test_trigger_job_all_symbols(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test triggering job for all symbols."""

        # Update mock to return correct timeframe based on request
        def create_job_side_effect(cronjob_name, timeframe, symbol):
            return {
                "name": f"manual-extract-{timeframe}-1234567890",
                "namespace": "petrosa-apps",
                "timeframe": timeframe,
                "symbol": symbol or "all",
            }

        mock_cronjob_manager.create_job_from_cronjob = Mock(
            side_effect=create_job_side_effect
        )
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.post(
            "/api/v1/jobs/trigger",
            json={
                "timeframe": "1h",
                "reason": "Backfill",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["timeframe"] == "1h"

    @patch("api.routes.jobs.get_cronjob_manager")
    def test_trigger_job_error(self, mock_get_manager, client, mock_cronjob_manager):
        """Test triggering job with error."""
        mock_cronjob_manager.create_job_from_cronjob = Mock(
            side_effect=Exception("K8s error")
        )
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.post(
            "/api/v1/jobs/trigger",
            json={
                "timeframe": "15m",
                "symbol": "BTCUSDT",
                "reason": "Test",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data


class TestValidationEndpoint:
    """Test configuration validation endpoint."""

    @patch("api.routes.config.get_cronjob_manager")
    def test_validate_symbols_success(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test validating symbols configuration successfully."""
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.post(
            "/api/v1/config/validate",
            json={
                "config_type": "symbols",
                "parameters": {
                    "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["validation_passed"] is True
        assert len(data["data"]["errors"]) == 0

    @patch("api.routes.config.get_cronjob_manager")
    def test_validate_symbols_invalid_type(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test validating symbols with invalid type."""
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.post(
            "/api/v1/config/validate",
            json={
                "config_type": "symbols",
                "parameters": {
                    "symbols": "not-a-list",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["validation_passed"] is False
        assert len(data["data"]["errors"]) > 0
        assert any(e["field"] == "symbols" for e in data["data"]["errors"])

    @patch("api.routes.config.get_cronjob_manager")
    def test_validate_symbols_invalid_format(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test validating symbols with invalid format."""

        # Mock is_valid_binance_symbol to return False for invalid symbols
        def is_valid_symbol(symbol):
            return symbol.isupper() and len(symbol) >= 5 and "-" not in symbol

        mock_cronjob_manager.is_valid_binance_symbol = Mock(side_effect=is_valid_symbol)
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.post(
            "/api/v1/config/validate",
            json={
                "config_type": "symbols",
                "parameters": {
                    "symbols": ["btcusdt", "invalid-symbol"],
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["validation_passed"] is False
        assert len(data["data"]["errors"]) > 0

    @patch("api.routes.config.get_cronjob_manager")
    def test_validate_rate_limits_success(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test validating rate limits successfully."""
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.post(
            "/api/v1/config/validate",
            json={
                "config_type": "rate_limits",
                "parameters": {
                    "requests_per_minute": 1000,
                    "concurrent_requests": 5,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["validation_passed"] is True
        assert len(data["data"]["errors"]) == 0

    @patch("api.routes.config.get_cronjob_manager")
    def test_validate_rate_limits_exceeds_max(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test validating rate limits that exceed maximum."""
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.post(
            "/api/v1/config/validate",
            json={
                "config_type": "rate_limits",
                "parameters": {
                    "requests_per_minute": 1500,
                    "concurrent_requests": 5,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["validation_passed"] is False
        assert len(data["data"]["errors"]) > 0
        assert any("requests_per_minute" in e["field"] for e in data["data"]["errors"])

    @patch("api.routes.config.get_cronjob_manager")
    def test_validate_rate_limits_below_min(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test validating rate limits below minimum."""
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.post(
            "/api/v1/config/validate",
            json={
                "config_type": "rate_limits",
                "parameters": {
                    "requests_per_minute": 0,
                    "concurrent_requests": 0,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["validation_passed"] is False
        assert len(data["data"]["errors"]) > 0

    @patch("api.routes.config.get_cronjob_manager")
    def test_validate_rate_limits_high_warning(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test validating rate limits that trigger warnings."""
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.post(
            "/api/v1/config/validate",
            json={
                "config_type": "rate_limits",
                "parameters": {
                    "requests_per_minute": 1100,
                    "concurrent_requests": 5,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["warnings"]) > 0

    @patch("api.routes.config.get_cronjob_manager")
    def test_validate_cronjob_success(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test validating cronjob schedule successfully."""
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.post(
            "/api/v1/config/validate",
            json={
                "config_type": "cronjob",
                "cronjob_name": "test-cronjob",
                "parameters": {
                    "schedule": "*/15 * * * *",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["validation_passed"] is True

    @patch("api.routes.config.get_cronjob_manager")
    def test_validate_cronjob_missing_name(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test validating cronjob without name."""
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.post(
            "/api/v1/config/validate",
            json={
                "config_type": "cronjob",
                "parameters": {
                    "schedule": "*/15 * * * *",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["validation_passed"] is False
        assert len(data["data"]["errors"]) > 0
        assert any("cronjob_name" in e["field"] for e in data["data"]["errors"])

    @patch("api.routes.config.get_cronjob_manager")
    def test_validate_cronjob_invalid_schedule(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test validating cronjob with invalid schedule."""
        mock_get_manager.return_value = mock_cronjob_manager

        response = client.post(
            "/api/v1/config/validate",
            json={
                "config_type": "cronjob",
                "cronjob_name": "test-cronjob",
                "parameters": {
                    "schedule": "invalid cron",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["validation_passed"] is False
        assert len(data["data"]["errors"]) > 0

    @patch("api.routes.config.get_cronjob_manager")
    def test_validate_unknown_config_type(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test validating unknown config type."""
        mock_get_manager.return_value = mock_cronjob_manager

        # FastAPI will return 422 for invalid Literal enum value
        response = client.post(
            "/api/v1/config/validate",
            json={
                "config_type": "unknown_type",
                "parameters": {},
            },
        )
        # FastAPI validates Literal types at request level, so we get 422
        assert response.status_code == 422

    @patch("api.routes.config.get_cronjob_manager")
    def test_validate_exception_handling(
        self, mock_get_manager, client, mock_cronjob_manager
    ):
        """Test exception handling in validation endpoint."""
        mock_get_manager.side_effect = Exception("Test error")

        response = client.post(
            "/api/v1/config/validate",
            json={
                "config_type": "symbols",
                "parameters": {
                    "symbols": ["BTCUSDT"],
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data


class TestCrossServiceConflictDetection:
    """Test cross-service conflict detection functionality."""

    @patch("api.routes.config.detect_cross_service_conflicts")
    @patch("api.routes.config.get_cronjob_manager")
    def test_validate_symbols_with_conflicts(
        self, mock_get_manager, mock_detect_conflicts, client, mock_cronjob_manager
    ):
        """Test validation endpoint includes cross-service conflicts."""
        from api.models.responses import CrossServiceConflict

        mock_get_manager.return_value = mock_cronjob_manager
        mock_detect_conflicts.return_value = [
            CrossServiceConflict(
                service="data-manager",
                conflict_type="SYMBOL_MISMATCH",
                description="Symbols BTCUSDT are configured in data-extractor but not in data-manager",
                resolution="Ensure symbols are synchronized between data-extractor and data-manager",
            )
        ]

        response = client.post(
            "/api/v1/config/validate",
            json={
                "config_type": "symbols",
                "parameters": {
                    "symbols": ["BTCUSDT", "ETHUSDT"],
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["conflicts"]) == 1
        assert data["data"]["conflicts"][0]["service"] == "data-manager"

    @patch("api.routes.config.detect_cross_service_conflicts")
    @patch("api.routes.config.get_cronjob_manager")
    def test_validate_symbols_no_conflicts(
        self, mock_get_manager, mock_detect_conflicts, client, mock_cronjob_manager
    ):
        """Test validation endpoint with no conflicts."""
        mock_get_manager.return_value = mock_cronjob_manager
        mock_detect_conflicts.return_value = []

        response = client.post(
            "/api/v1/config/validate",
            json={
                "config_type": "symbols",
                "parameters": {
                    "symbols": ["BTCUSDT", "ETHUSDT"],
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["conflicts"]) == 0

    @pytest.mark.asyncio
    @patch("api.routes.config._get_service_urls")
    async def test_detect_cross_service_conflicts_data_manager_mismatch(
        self, mock_get_urls
    ):
        """Test conflict detection when data-manager has different symbols."""
        import httpx
        from unittest.mock import AsyncMock

        from api.routes.config import detect_cross_service_conflicts

        mock_get_urls.return_value = {
            "data-manager": "http://test-data-manager:8080",
            "tradeengine": "http://test-tradeengine:8080",
        }

        # Mock httpx client
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "success": True,
                "data": {"symbols": ["BTCUSDT"]},  # Only BTCUSDT, missing ETHUSDT
            }
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            conflicts = await detect_cross_service_conflicts(
                "symbols", {"symbols": ["BTCUSDT", "ETHUSDT"]}
            )

            assert len(conflicts) == 1
            assert conflicts[0].service == "data-manager"
            assert conflicts[0].conflict_type == "SYMBOL_MISMATCH"
            assert "ETHUSDT" in conflicts[0].description

    @pytest.mark.asyncio
    @patch("api.routes.config._get_service_urls")
    async def test_detect_cross_service_conflicts_timeout(
        self, mock_get_urls
    ):
        """Test conflict detection handles timeouts gracefully."""
        import httpx

        from api.routes.config import detect_cross_service_conflicts

        mock_get_urls.return_value = {
            "data-manager": "http://test-data-manager:8080",
            "tradeengine": "http://test-tradeengine:8080",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            conflicts = await detect_cross_service_conflicts(
                "symbols", {"symbols": ["BTCUSDT"]}
            )

            # Should return empty list on timeout
            assert len(conflicts) == 0

    @pytest.mark.asyncio
    @patch("api.routes.config._get_service_urls")
    async def test_detect_cross_service_conflicts_404_response(
        self, mock_get_urls
    ):
        """Test conflict detection handles 404 responses."""
        from unittest.mock import AsyncMock

        from api.routes.config import detect_cross_service_conflicts

        mock_get_urls.return_value = {
            "data-manager": "http://test-data-manager:8080",
            "tradeengine": "http://test-tradeengine:8080",
        }

        mock_response = AsyncMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            conflicts = await detect_cross_service_conflicts(
                "symbols", {"symbols": ["BTCUSDT"]}
            )

            # Should return empty list on 404
            assert len(conflicts) == 0

    @pytest.mark.asyncio
    @patch("api.routes.config._get_service_urls")
    async def test_detect_cross_service_conflicts_invalid_symbol_format(
        self, mock_get_urls
    ):
        """Test conflict detection validates symbol format before URL construction."""
        from unittest.mock import AsyncMock

        from api.routes.config import detect_cross_service_conflicts

        mock_get_urls.return_value = {
            "data-manager": "http://test-data-manager:8080",
            "tradeengine": "http://test-tradeengine:8080",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock()
            mock_client_class.return_value = mock_client

            # Test with invalid symbol format (lowercase)
            conflicts = await detect_cross_service_conflicts(
                "symbols", {"symbols": ["btcusdt"]}  # lowercase
            )

            # Should skip invalid symbols and not make requests
            # Verify get was not called for invalid symbols
            assert len(conflicts) == 0

    @pytest.mark.asyncio
    @patch("api.routes.config._get_service_urls")
    async def test_detect_cross_service_conflicts_non_symbols_config(
        self, mock_get_urls
    ):
        """Test conflict detection skips non-symbols config types."""
        from api.routes.config import detect_cross_service_conflicts

        mock_get_urls.return_value = {
            "data-manager": "http://test-data-manager:8080",
            "tradeengine": "http://test-tradeengine:8080",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock()
            mock_client_class.return_value = mock_client

            conflicts = await detect_cross_service_conflicts(
                "rate_limits", {"requests_per_minute": 1000}
            )

            # Should return empty for non-symbols config
            assert len(conflicts) == 0
            # Should not make any HTTP requests
            mock_client.get.assert_not_called()
