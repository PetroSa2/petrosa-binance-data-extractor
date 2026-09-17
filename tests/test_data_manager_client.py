"""
Comprehensive tests for clients/data_manager_client.py.

Tests cover:
- Client initialization and configuration
- Insert/query operations
- Error handling (timeouts, connection errors, API errors)
- Retry logic
- Corner cases (empty data, malformed responses)
- Performance (large batches)
- Security (input validation)
- Chaos testing (network failures)
"""

from datetime import datetime, timedelta

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone

    UTC = timezone.utc  # noqa: UP017
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import requests

from clients.data_manager_client import (
    APIError,
    BaseDataManagerClient,
    ConnectionError,
    DataManagerClient,
    TimeoutError,
)


class TestBaseDataManagerClient:
    """Test suite for BaseDataManagerClient."""

    def test_init_with_defaults(self):
        """Test client initialization with defaults."""
        client = BaseDataManagerClient(base_url="http://localhost:8000")

        assert client.base_url == "http://localhost:8000"
        assert client.timeout == 30
        assert client.session is not None

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped from base_url."""
        client = BaseDataManagerClient(base_url="http://localhost:8000/")

        assert client.base_url == "http://localhost:8000"

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        client = BaseDataManagerClient(
            base_url="http://custom:9000", timeout=60, max_retries=5
        )

        assert client.base_url == "http://custom:9000"
        assert client.timeout == 60

    def test_insert_success(self):
        """Test successful insert operation."""
        client = BaseDataManagerClient(base_url="http://localhost:8000")

        with patch.object(client.session, "post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {"inserted_count": 10}
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            records = [{"id": 1, "value": "test"}]
            result = client.insert("mongodb", "test_collection", records)

            assert result["inserted_count"] == 10
            mock_post.assert_called_once()

    def test_insert_timeout_error(self):
        """Test insert with timeout error."""
        client = BaseDataManagerClient(base_url="http://localhost:8000")

        with patch.object(
            client.session, "post", side_effect=requests.exceptions.Timeout("Timeout")
        ):
            with pytest.raises(TimeoutError, match="Request timed out") as exc_info:
                client.insert("mongodb", "test_collection", [{"id": 1}])
            assert exc_info.value is not None

    def test_insert_connection_error(self):
        """Test insert with connection error."""
        client = BaseDataManagerClient(base_url="http://localhost:8000")

        with patch.object(
            client.session,
            "post",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with pytest.raises(ConnectionError, match="Connection failed") as exc_info:
                client.insert("mongodb", "test_collection", [{"id": 1}])
            assert exc_info.value is not None

    def test_insert_http_error(self):
        """Test insert with HTTP error."""
        client = BaseDataManagerClient(base_url="http://localhost:8000")

        with patch.object(client.session, "post") as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
                "500 Server Error"
            )
            mock_post.return_value = mock_response

            with pytest.raises(APIError, match="API error") as exc_info:
                client.insert("mongodb", "test_collection", [{"id": 1}])
            assert exc_info.value is not None

    def test_query_success(self):
        """Test successful query operation uses GET /api/v1/{database}/{collection}."""
        client = BaseDataManagerClient(base_url="http://localhost:8000")

        with patch.object(client.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                "data": [{"id": 1, "value": "test"}],
                "count": 1,
            }
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = client.query("mongodb", "test_collection", {"filter": {"id": 1}})

            assert result["count"] == 1
            assert len(result["data"]) == 1
            mock_get.assert_called_once()
            # Verify URL uses the correct endpoint
            call_url = mock_get.call_args[0][0]
            assert call_url == "http://localhost:8000/api/v1/mongodb/test_collection"
            # Verify filter is passed as JSON-encoded query param
            call_params = mock_get.call_args[1]["params"]
            assert "filter" in call_params
            assert '"id": 1' in call_params["filter"]

    def test_query_timeout_error(self):
        """Test query with timeout error."""
        client = BaseDataManagerClient(base_url="http://localhost:8000")

        with patch.object(
            client.session, "get", side_effect=requests.exceptions.Timeout("Timeout")
        ):
            with pytest.raises(TimeoutError) as exc_info:
                client.query("mongodb", "test_collection", {"filter": {}})
            assert exc_info.value is not None

    def test_query_connection_error(self):
        """Test query with connection error."""
        client = BaseDataManagerClient(base_url="http://localhost:8000")

        with patch.object(
            client.session,
            "get",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with pytest.raises(ConnectionError) as exc_info:
                client.query("mongodb", "test_collection", {"filter": {}})
            assert exc_info.value is not None

    def test_insert_one_calls_insert(self):
        """Test insert_one delegates to insert."""
        client = BaseDataManagerClient(base_url="http://localhost:8000")

        with patch.object(client, "insert") as mock_insert:
            mock_insert.return_value = {"inserted_count": 1}

            result = client.insert_one("mongodb", "test_collection", {"id": 1})

            mock_insert.assert_called_once_with(
                "mongodb", "test_collection", [{"id": 1}]
            )
            assert result["inserted_count"] == 1


class TestDataManagerClient:
    """Test suite for DataManagerClient."""

    def test_init_with_defaults(self):
        """Test initialization with defaults."""
        with patch("clients.data_manager_client.os.getenv") as mock_getenv:
            mock_getenv.return_value = "http://default:8000"

            client = DataManagerClient()

            assert client.base_url == "http://default:8000"
            assert client.timeout == 30
            assert client._client is not None

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        client = DataManagerClient(
            base_url="http://custom:9000", timeout=60, max_retries=5
        )

        assert client.base_url == "http://custom:9000"
        assert client.timeout == 60
        assert client.max_retries == 5

    def test_interval_to_minutes(self):
        """Test interval conversion to minutes."""
        client = DataManagerClient(base_url="http://localhost:8000")

        # Test various intervals
        assert client._interval_to_minutes("1m") == 1
        assert client._interval_to_minutes("15m") == 15
        assert client._interval_to_minutes("1h") == 60
        assert client._interval_to_minutes("4h") == 240
        assert client._interval_to_minutes("1d") == 1440


# Corner case tests
class TestCornerCases:
    """Corner case tests for edge scenarios."""

    def test_empty_records_insert(self):
        """Test inserting empty records list."""
        client = BaseDataManagerClient(base_url="http://localhost:8000")

        with patch.object(client.session, "post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {"inserted_count": 0}
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            result = client.insert("mongodb", "test_collection", [])

            assert result["inserted_count"] == 0

    def test_malformed_json_response(self):
        """Test handling of malformed JSON response."""
        client = BaseDataManagerClient(base_url="http://localhost:8000")

        with patch.object(client.session, "post") as mock_post:
            mock_response = Mock()
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            with pytest.raises(ValueError) as exc_info:
                client.insert("mongodb", "test_collection", [{"id": 1}])
            assert exc_info.value is not None

    def test_unicode_in_records(self):
        """Test handling of Unicode characters in records."""
        client = BaseDataManagerClient(base_url="http://localhost:8000")

        with patch.object(client.session, "post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {"inserted_count": 1}
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            records = [{"symbol": "BTC€USDT", "note": "测试数据"}]
            result = client.insert("mongodb", "test_collection", records)

            assert result["inserted_count"] == 1


# Performance tests
class TestPerformance:
    """Performance tests for large operations."""

    def test_insert_large_batch(self):
        """Test inserting large batch of records."""
        client = BaseDataManagerClient(base_url="http://localhost:8000")

        with patch.object(client.session, "post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {"inserted_count": 10000}
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            large_batch = [{"id": i, "value": f"test_{i}"} for i in range(10000)]
            result = client.insert("mongodb", "test_collection", large_batch)

            assert result["inserted_count"] == 10000

    def test_query_with_large_result_set(self):
        """Test querying large result set."""
        client = BaseDataManagerClient(base_url="http://localhost:8000")

        with patch.object(client.session, "get") as mock_get:
            mock_response = Mock()
            large_result = [{"id": i, "value": f"test_{i}"} for i in range(5000)]
            mock_response.json.return_value = {"data": large_result, "count": 5000}
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = client.query("mongodb", "test_collection", {"filter": {}})

            assert result["count"] == 5000
            assert len(result["data"]) == 5000


# Security tests
class TestSecurity:
    """Security tests for input validation."""

    def test_sql_injection_attempt(self):
        """Test handling of SQL injection attempt."""
        client = BaseDataManagerClient(base_url="http://localhost:8000")

        with patch.object(client.session, "post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {"inserted_count": 0}
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            # Malicious payload
            records = [{"id": "1'; DROP TABLE users;--"}]
            result = client.insert("mongodb", "test_collection", records)

            # Should be handled by API, not crash client
            assert "inserted_count" in result


# Chaos tests
class TestChaos:
    """Chaos tests for failure scenarios."""

    def test_retry_configuration(self):
        """Test that retry strategy is configured properly."""
        client = BaseDataManagerClient(base_url="http://localhost:8000", max_retries=5)

        # Verify session has adapters mounted
        assert "http://" in client.session.adapters
        assert "https://" in client.session.adapters

    def test_slow_response(self):
        """Test handling of slow API response."""
        client = BaseDataManagerClient(base_url="http://localhost:8000", timeout=1)

        with patch.object(
            client.session, "post", side_effect=requests.exceptions.Timeout("Timeout")
        ):
            with pytest.raises(TimeoutError) as exc_info:
                client.insert("mongodb", "test_collection", [{"id": 1}])
            assert exc_info.value is not None

    def test_partial_response(self):
        """Test handling of partial/corrupted response."""
        client = BaseDataManagerClient(base_url="http://localhost:8000")

        with patch.object(client.session, "post") as mock_post:
            mock_response = Mock()
            # Missing expected fields
            mock_response.json.return_value = {"status": "error"}
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            result = client.insert("mongodb", "test_collection", [{"id": 1}])

            # Should return the response even if unexpected
            assert result["status"] == "error"


class TestDataManagerClientFindGaps:
    """Tests for DataManagerClient.find_gaps (k8s-extractor#298).

    Data Manager's generic GET endpoint rejects operator-valued filters
    (e.g. ``{"close_time": {"$gte": ..., "$lte": ...}}``) with
    400 Bad Request — the filter must be a flat equality match. These
    tests assert find_gaps() never sends an operator-shaped filter, and
    that a seeded gap is still correctly detected from the windowed,
    client-side-filtered response.
    """

    @pytest.mark.asyncio
    async def test_find_gaps_sends_flat_equality_filter_only(self):
        """The request filter must be exactly {'symbol': symbol} — no
        $gte/$lte operators, which Data Manager rejects with 400."""
        client = DataManagerClient(base_url="http://localhost:8000")

        start_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        end_time = datetime(2026, 1, 1, 1, 0, tzinfo=UTC)

        with patch.object(client._client, "query") as mock_query:
            mock_query.return_value = {"data": []}

            await client.find_gaps(
                symbol="BTCUSDT",
                interval="5m",
                start_time=start_time,
                end_time=end_time,
            )

            mock_query.assert_called_once()
            call_kwargs = mock_query.call_args.kwargs
            filter_sent = call_kwargs["params"]["filter"]

            # Flat equality only — no dict-valued (operator) entries.
            assert filter_sent == {"symbol": "BTCUSDT"}
            for value in filter_sent.values():
                assert not isinstance(value, dict)
            assert call_kwargs["params"]["sort"] == {"close_time": -1}
            assert "limit" in call_kwargs["params"]

    @pytest.mark.asyncio
    async def test_find_gaps_detects_seeded_gap_from_windowed_response(self):
        """A gap seeded in the mocked (unfiltered-by-server) response is
        still detected after client-side windowing to [start, end]."""
        client = DataManagerClient(base_url="http://localhost:8000")

        start_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        end_time = datetime(2026, 1, 1, 0, 45, tzinfo=UTC)

        # Data Manager returns the most recent N records for the symbol
        # (descending), including one record outside the requested window
        # (which must be excluded) and a seeded 25-minute gap between
        # 00:15 and 00:45 for a 5m interval.
        server_records = [
            {"close_time": "2026-01-01T00:45:00+00:00"},
            # gap: 00:20 - 00:40 missing for 5m interval
            {"close_time": "2026-01-01T00:15:00+00:00"},
            {"close_time": "2026-01-01T00:10:00+00:00"},
            {"close_time": "2026-01-01T00:05:00+00:00"},
            {"close_time": "2026-01-01T00:00:00+00:00"},
            {"close_time": "2025-12-31T23:55:00+00:00"},  # outside window
        ]

        with patch.object(client._client, "query") as mock_query:
            mock_query.return_value = {"data": server_records}

            gaps = await client.find_gaps(
                symbol="BTCUSDT",
                interval="5m",
                start_time=start_time,
                end_time=end_time,
            )

        assert len(gaps) == 1
        assert gaps[0]["symbol"] == "BTCUSDT"
        assert gaps[0]["interval"] == "5m"
        assert gaps[0]["start_time"] == datetime(2026, 1, 1, 0, 20, tzinfo=UTC)
        assert gaps[0]["end_time"] == datetime(2026, 1, 1, 0, 45, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_find_gaps_query_limit_scales_with_window(self):
        """A wider window requests a larger (but still bounded) limit."""
        client = DataManagerClient(base_url="http://localhost:8000")

        with patch.object(client._client, "query") as mock_query:
            mock_query.return_value = {"data": []}

            await client.find_gaps(
                symbol="BTCUSDT",
                interval="5m",
                start_time=datetime(2026, 1, 1, tzinfo=UTC),
                end_time=datetime(2026, 1, 8, tzinfo=UTC),  # 1 week
            )

        limit_sent = mock_query.call_args.kwargs["params"]["limit"]
        assert 50 <= limit_sent <= 5000

    @pytest.mark.asyncio
    async def test_find_gaps_no_gap_when_contiguous(self):
        """No gap reported when all expected candles are present."""
        client = DataManagerClient(base_url="http://localhost:8000")

        start_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        end_time = datetime(2026, 1, 1, 0, 20, tzinfo=UTC)

        server_records = [
            {"close_time": "2026-01-01T00:20:00+00:00"},
            {"close_time": "2026-01-01T00:15:00+00:00"},
            {"close_time": "2026-01-01T00:10:00+00:00"},
            {"close_time": "2026-01-01T00:05:00+00:00"},
            {"close_time": "2026-01-01T00:00:00+00:00"},
        ]

        with patch.object(client._client, "query") as mock_query:
            mock_query.return_value = {"data": server_records}

            gaps = await client.find_gaps(
                symbol="BTCUSDT",
                interval="5m",
                start_time=start_time,
                end_time=end_time,
            )

        assert gaps == []
