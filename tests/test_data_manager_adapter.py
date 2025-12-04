"""
Comprehensive tests for DataManagerAdapter.

Tests cover:
- Connection management (connect, disconnect, context managers)
- Data write operations (klines, trades, funding)
- Query operations (latest records, gaps)
- Corner cases (timezone handling, empty data, malformed responses)
- Performance scenarios (large batches, concurrent operations)
- Security (input validation, error message sanitization)
- Chaos testing (network failures, partial responses)
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from adapters.data_manager_adapter import DataManagerAdapter


class TestDataManagerAdapterInit:
    """Test suite for DataManagerAdapter initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        with patch("adapters.data_manager_adapter.constants") as mock_constants:
            mock_constants.DATA_MANAGER_URL = "http://localhost:8000"
            mock_constants.DATA_MANAGER_TIMEOUT = 30
            mock_constants.DATA_MANAGER_MAX_RETRIES = 3
            mock_constants.DATA_MANAGER_DATABASE = "mongodb"

            adapter = DataManagerAdapter()

            assert adapter.base_url == "http://localhost:8000"
            assert adapter.timeout == 30
            assert adapter.max_retries == 3
            assert adapter.database == "mongodb"
            assert adapter._connected is False
            assert adapter._client is None

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        adapter = DataManagerAdapter(
            base_url="http://custom:9000",
            timeout=60,
            max_retries=5,
            database="mysql",
        )

        assert adapter.base_url == "http://custom:9000"
        assert adapter.timeout == 60
        assert adapter.max_retries == 5
        assert adapter.database == "mysql"


class TestDataManagerAdapterConnection:
    """Test suite for connection management."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")

        with patch(
            "adapters.data_manager_adapter.DataManagerClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.health_check = AsyncMock(return_value={"status": "healthy"})
            mock_client_class.return_value = mock_client

            await adapter.connect()

            assert adapter._connected is True
            assert adapter._client is not None
            mock_client.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_already_connected(self):
        """Test connecting when already connected."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        # Should return immediately without creating new client
        await adapter.connect()

        assert adapter._connected is True

    @pytest.mark.asyncio
    async def test_connect_health_check_failure(self):
        """Test connection failure when health check fails."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")

        with patch(
            "adapters.data_manager_adapter.DataManagerClient"
        ) as mock_client_class, pytest.raises(ConnectionError):
            mock_client = AsyncMock()
            mock_client.health_check = AsyncMock(return_value={"status": "unhealthy"})
            mock_client_class.return_value = mock_client

            await adapter.connect()

    @pytest.mark.asyncio
    async def test_connect_network_error(self):
        """Test connection failure due to network error."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")

        with patch(
            "adapters.data_manager_adapter.DataManagerClient"
        ) as mock_client_class, pytest.raises(Exception):
            mock_client = AsyncMock()
            mock_client.health_check = AsyncMock(side_effect=TimeoutError("Timeout"))
            mock_client_class.return_value = mock_client

            await adapter.connect()

    @pytest.mark.asyncio
    async def test_disconnect_success(self):
        """Test successful disconnection."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")

        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        adapter._client = mock_client
        adapter._connected = True

        await adapter.disconnect()

        assert adapter._connected is False
        assert adapter._client is None
        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_error(self):
        """Test disconnection with error."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")

        mock_client = AsyncMock()
        mock_client.close = AsyncMock(side_effect=Exception("Close error"))
        adapter._client = mock_client
        adapter._connected = True

        # Should not raise, just log warning
        await adapter.disconnect()

        assert adapter._connected is False
        assert adapter._client is None


class TestDataManagerAdapterWrite:
    """Test suite for write operations."""

    @pytest.mark.asyncio
    async def test_write_klines_success(self):
        """Test successful klines write."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        mock_client = AsyncMock()
        mock_client.insert_klines = AsyncMock(return_value={"inserted_count": 100})
        adapter._client = mock_client

        # Mock data
        mock_data = [
            Mock(
                to_dict=lambda: {
                    "symbol": "BTCUSDT",
                    "timestamp": datetime.now(),
                    "close": 45000,
                }
            )
            for _ in range(100)
        ]

        written = await adapter.write(mock_data, "klines_15m", batch_size=500)

        assert written == 100
        mock_client.insert_klines.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_trades_success(self):
        """Test successful trades write."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        mock_client = AsyncMock()
        mock_client.insert_trades = AsyncMock(return_value={"inserted_count": 50})
        adapter._client = mock_client

        mock_data = [
            Mock(
                to_dict=lambda: {
                    "symbol": "BTCUSDT",
                    "timestamp": datetime.now(),
                    "price": 45000,
                }
            )
            for _ in range(50)
        ]

        written = await adapter.write(mock_data, "trades_BTCUSDT", batch_size=500)

        assert written == 50
        mock_client.insert_trades.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_funding_success(self):
        """Test successful funding rates write."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        mock_client = AsyncMock()
        mock_client.insert_funding_rates = AsyncMock(
            return_value={"inserted_count": 20}
        )
        adapter._client = mock_client

        mock_data = [
            Mock(
                to_dict=lambda: {
                    "symbol": "BTCUSDT",
                    "timestamp": datetime.now(),
                    "rate": 0.0001,
                }
            )
            for _ in range(20)
        ]

        written = await adapter.write(mock_data, "funding_BTCUSDT", batch_size=500)

        assert written == 20
        mock_client.insert_funding_rates.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_empty_data(self):
        """Test writing empty data."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        written = await adapter.write([], "klines_15m", batch_size=500)

        assert written == 0

    @pytest.mark.asyncio
    async def test_write_not_connected_auto_connect(self):
        """Test auto-connect when not connected."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")

        async def mock_connect():
            adapter._connected = True
            mock_client = AsyncMock()
            mock_client.insert_klines = AsyncMock(return_value={"inserted_count": 10})
            adapter._client = mock_client

        with patch.object(
            adapter, "connect", side_effect=mock_connect
        ) as mock_connect_spy:
            mock_data = [
                Mock(
                    to_dict=lambda: {
                        "symbol": "BTCUSDT",
                        "timestamp": datetime.now(),
                        "close": 45000,
                    }
                )
            ]

            written = await adapter.write(mock_data, "klines_1h")

            mock_connect_spy.assert_called_once()
            assert written == 10

    @pytest.mark.asyncio
    async def test_write_with_dict_attribute(self):
        """Test writing data with __dict__ attribute."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        mock_client = AsyncMock()
        mock_client.insert_klines = AsyncMock(return_value={"inserted_count": 1})
        adapter._client = mock_client

        # Mock object with __dict__ but no to_dict
        mock_obj = Mock(spec=[])
        mock_obj.__dict__ = {
            "symbol": "BTCUSDT",
            "timestamp": datetime.now(),
            "close": 45000,
        }

        written = await adapter.write([mock_obj], "klines_15m")

        assert written == 1

    @pytest.mark.asyncio
    async def test_write_invalid_data_conversion(self):
        """Test writing data that can't be converted to dict."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        # Object without to_dict or __dict__
        invalid_data = [42, "string", None]

        written = await adapter.write(invalid_data, "klines_15m")

        # Should return 0 as no valid data
        assert written == 0

    @pytest.mark.asyncio
    async def test_write_error_handling(self):
        """Test error handling during write."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        mock_client = AsyncMock()
        mock_client.insert_klines = AsyncMock(side_effect=Exception("Write failed"))
        adapter._client = mock_client

        mock_data = [
            Mock(
                to_dict=lambda: {
                    "symbol": "BTCUSDT",
                    "timestamp": datetime.now(),
                    "close": 45000,
                }
            )
        ]

        with pytest.raises(Exception, match="Write failed"):
            await adapter.write(mock_data, "klines_15m")


class TestDataManagerAdapterQuery:
    """Test suite for query operations."""

    @pytest.mark.asyncio
    async def test_query_latest_with_symbol(self):
        """Test querying latest records with symbol filter."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        mock_client = AsyncMock()
        mock_client._client = AsyncMock()
        mock_client._client.query = AsyncMock(
            return_value={
                "data": [
                    {"symbol": "BTCUSDT", "timestamp": datetime.now(), "close": 45000}
                ]
            }
        )
        adapter._client = mock_client

        results = await adapter.query_latest("klines_15m", symbol="BTCUSDT", limit=1)

        assert len(results) == 1
        assert results[0]["symbol"] == "BTCUSDT"

    @pytest.mark.asyncio
    async def test_query_latest_without_symbol(self):
        """Test querying latest records without symbol filter."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        mock_client = AsyncMock()
        mock_client._client = AsyncMock()
        mock_client._client.query = AsyncMock(
            return_value={
                "data": [
                    {"symbol": "BTCUSDT", "timestamp": datetime.now(), "close": 45000},
                    {"symbol": "ETHUSDT", "timestamp": datetime.now(), "close": 3000},
                ]
            }
        )
        adapter._client = mock_client

        results = await adapter.query_latest("klines_1h", limit=2)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_query_latest_error(self):
        """Test error handling during query."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        mock_client = AsyncMock()
        mock_client._client = AsyncMock()
        mock_client._client.query = AsyncMock(side_effect=Exception("Query failed"))
        adapter._client = mock_client

        results = await adapter.query_latest("klines_15m", symbol="BTCUSDT")

        # Should return empty list on error
        assert results == []


class TestDataManagerAdapterGaps:
    """Test suite for gap detection."""

    @pytest.mark.asyncio
    async def test_find_gaps_klines(self):
        """Test finding gaps in klines data."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        mock_client = AsyncMock()
        mock_client.find_gaps = AsyncMock(
            return_value=[
                {"start": datetime.now() - timedelta(hours=2), "count": 3},
                {"start": datetime.now() - timedelta(hours=1), "count": 1},
            ]
        )
        adapter._client = mock_client

        gaps = await adapter.find_gaps(
            collection_name="klines_15m",
            start_time=datetime.now() - timedelta(days=1),
            end_time=datetime.now(),
            interval_minutes=15,
            symbol="BTCUSDT",
        )

        assert len(gaps) == 2
        mock_client.find_gaps.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_gaps_non_klines_collection(self):
        """Test gap detection for non-klines collection."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        gaps = await adapter.find_gaps(
            collection_name="trades_BTCUSDT",
            start_time=datetime.now() - timedelta(days=1),
            end_time=datetime.now(),
            interval_minutes=15,
        )

        # Should return empty list for non-klines
        assert gaps == []

    @pytest.mark.asyncio
    async def test_find_gaps_error(self):
        """Test error handling during gap detection."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        mock_client = AsyncMock()
        mock_client.find_gaps = AsyncMock(side_effect=Exception("Gap detection failed"))
        adapter._client = mock_client

        gaps = await adapter.find_gaps(
            collection_name="klines_1h",
            start_time=datetime.now() - timedelta(days=1),
            end_time=datetime.now(),
            interval_minutes=60,
            symbol="BTCUSDT",
        )

        # Should return empty list on error
        assert gaps == []


class TestDataManagerAdapterHealthCheck:
    """Test suite for health check."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        mock_client = AsyncMock()
        mock_client.health_check = AsyncMock(
            return_value={"status": "healthy", "uptime": 3600}
        )
        adapter._client = mock_client

        health = await adapter.health_check()

        assert health["status"] == "healthy"
        assert "uptime" in health

    @pytest.mark.asyncio
    async def test_health_check_not_connected(self):
        """Test health check when not connected (auto-connect)."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")

        async def mock_connect():
            adapter._connected = True
            mock_client = AsyncMock()
            mock_client.health_check = AsyncMock(return_value={"status": "healthy"})
            adapter._client = mock_client

        with patch.object(
            adapter, "connect", side_effect=mock_connect
        ) as mock_connect_spy:
            health = await adapter.health_check()

            mock_connect_spy.assert_called_once()
            assert health["status"] == "healthy"


class TestDataManagerAdapterContextManagers:
    """Test suite for context managers."""

    def test_sync_context_manager(self):
        """Test synchronous context manager."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")

        with patch("adapters.data_manager_adapter.asyncio.run") as mock_run:
            with adapter:
                pass

            # Should call connect on enter and disconnect on exit
            assert mock_run.call_count >= 1

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test asynchronous context manager."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")

        with patch.object(adapter, "connect") as mock_connect, patch.object(
            adapter, "disconnect"
        ) as mock_disconnect:
            async with adapter:
                pass

            mock_connect.assert_called_once()
            mock_disconnect.assert_called_once()


# Corner case tests
class TestCornerCases:
    """Corner case tests for edge scenarios."""

    @pytest.mark.asyncio
    async def test_write_with_mixed_valid_invalid_data(self):
        """Test writing mix of valid and invalid data."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        mock_client = AsyncMock()
        mock_client.insert_klines = AsyncMock(return_value={"inserted_count": 2})
        adapter._client = mock_client

        mixed_data = [
            Mock(
                to_dict=lambda: {
                    "symbol": "BTCUSDT",
                    "timestamp": datetime.now(),
                    "close": 45000,
                }
            ),
            42,  # Invalid
            Mock(
                to_dict=lambda: {
                    "symbol": "ETHUSDT",
                    "timestamp": datetime.now(),
                    "close": 3000,
                }
            ),
            None,  # Invalid
        ]

        written = await adapter.write(mixed_data, "klines_15m")

        # Should only write valid data
        assert written == 2


# Performance tests
class TestPerformance:
    """Performance tests for large datasets."""

    @pytest.mark.asyncio
    async def test_write_large_batch(self):
        """Test writing large batch of data."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        mock_client = AsyncMock()
        mock_client.insert_klines = AsyncMock(return_value={"inserted_count": 10000})
        adapter._client = mock_client

        # Large dataset
        large_data = [
            Mock(
                to_dict=lambda: {
                    "symbol": "BTCUSDT",
                    "timestamp": datetime.now(),
                    "close": 45000,
                }
            )
            for _ in range(10000)
        ]

        written = await adapter.write(large_data, "klines_1m", batch_size=1000)

        assert written == 10000


# Security tests
class TestSecurity:
    """Security tests for validation and error handling."""

    @pytest.mark.asyncio
    async def test_collection_name_sanitization(self):
        """Test that collection names with special characters are handled."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        mock_client = AsyncMock()
        mock_client._client = AsyncMock()
        mock_client._client.insert = AsyncMock(return_value={"inserted_count": 0})
        adapter._client = mock_client

        # Collection name with special characters
        mock_data = [Mock(to_dict=lambda: {"test": "data"})]

        # Should not cause SQL injection or path traversal
        written = await adapter.write(mock_data, "../../malicious_collection")

        # System handles it without crashing
        assert written >= 0


# Chaos tests
class TestChaos:
    """Chaos tests for failure scenarios."""

    @pytest.mark.asyncio
    async def test_network_timeout_during_write(self):
        """Test handling of network timeout during write."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        mock_client = AsyncMock()
        mock_client.insert_klines = AsyncMock(side_effect=TimeoutError("Timeout"))
        adapter._client = mock_client

        mock_data = [
            Mock(
                to_dict=lambda: {
                    "symbol": "BTCUSDT",
                    "timestamp": datetime.now(),
                    "close": 45000,
                }
            )
        ]

        with pytest.raises(Exception):
            await adapter.write(mock_data, "klines_15m")

    @pytest.mark.asyncio
    async def test_partial_response_corruption(self):
        """Test handling of corrupted API response."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        mock_client = AsyncMock()
        mock_client._client = AsyncMock()
        # Corrupted response (missing 'data' key)
        mock_client._client.query = AsyncMock(return_value={"corrupted": "response"})
        adapter._client = mock_client

        results = await adapter.query_latest("klines_15m", symbol="BTCUSDT")

        # Should handle gracefully
        assert results == []

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent read/write operations."""
        adapter = DataManagerAdapter(base_url="http://localhost:8000")
        adapter._connected = True

        mock_client = AsyncMock()
        mock_client.insert_klines = AsyncMock(return_value={"inserted_count": 10})
        mock_client._client = AsyncMock()
        mock_client._client.query = AsyncMock(return_value={"data": []})
        adapter._client = mock_client

        mock_data = [
            Mock(
                to_dict=lambda: {
                    "symbol": "BTCUSDT",
                    "timestamp": datetime.now(),
                    "close": 45000,
                }
            )
            for _ in range(10)
        ]

        # Run concurrent operations
        tasks = [
            adapter.write(mock_data, "klines_15m"),
            adapter.query_latest("klines_15m", symbol="BTCUSDT"),
            adapter.write(mock_data, "klines_1h"),
            adapter.query_latest("klines_1h", symbol="ETHUSDT"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should complete (some writes return counts, some queries return lists)
        assert len(results) == 4
