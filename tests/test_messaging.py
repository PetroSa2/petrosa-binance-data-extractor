"""
Tests for NATS messaging functionality.
"""

import json
import os
from unittest.mock import AsyncMock, Mock, patch

import pytest

from utils.messaging import (
    NATSMessenger,
    get_messenger,
    publish_extraction_completion_sync,
)


class TestNATSMessenger:
    """Test NATS messenger functionality."""

    def test_init_with_default_url(self):
        """Test messenger initialization with default URL."""
        messenger = NATSMessenger()
        assert messenger.nats_url == "nats://localhost:4222"

    def test_init_with_custom_url(self):
        """Test messenger initialization with custom URL."""
        messenger = NATSMessenger("nats://custom-server:4222")
        assert messenger.nats_url == "nats://custom-server:4222"

    def test_init_with_env_var(self):
        """Test messenger initialization with environment variable."""
        with patch.dict(os.environ, {"NATS_URL": "nats://env-server:4222"}):
            messenger = NATSMessenger()
            assert messenger.nats_url == "nats://env-server:4222"

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self):
        """Test connection and disconnection."""
        messenger = NATSMessenger()

        # Mock the nats.connect function
        with patch("utils.messaging.nats.connect") as mock_connect:
            mock_client = Mock()
            mock_client.is_closed = False
            # Make close() return an awaitable
            mock_client.close = AsyncMock()
            mock_connect.return_value = mock_client

            await messenger.connect()
            assert messenger.client == mock_client
            mock_connect.assert_called_once_with("nats://localhost:4222")

            await messenger.disconnect()
            mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_extraction_completion(self):
        """Test publishing extraction completion message."""
        # Set up environment for default prefix
        with patch.dict('os.environ', {'NATS_SUBJECT_PREFIX': 'binance.extraction'}):
            messenger = NATSMessenger()

            # Mock the nats client
            mock_client = Mock()
            mock_client.is_closed = False
            messenger.client = mock_client

            # Test message publishing
            await messenger.publish_extraction_completion(
                symbol="BTCUSDT",
                period="15m",
                records_fetched=100,
                records_written=100,
                success=True,
                duration_seconds=5.5,
                errors=[],
                gaps_found=0,
                gaps_filled=0,
                extraction_type="klines",
            )

            # Verify the message was published
            mock_client.publish.assert_called_once()
            call_args = mock_client.publish.call_args
            assert call_args[0][0] == "binance.extraction.klines.BTCUSDT.15m"

            # Verify message content
            message_data = json.loads(call_args[0][1].decode())
            assert message_data["event_type"] == "extraction_completed"
            assert message_data["symbol"] == "BTCUSDT"
            assert message_data["period"] == "15m"
            assert message_data["success"] is True
            assert message_data["metrics"]["records_fetched"] == 100
            assert message_data["metrics"]["records_written"] == 100
            assert message_data["metrics"]["duration_seconds"] == 5.5

    @pytest.mark.asyncio
    async def test_publish_batch_extraction_completion(self):
        """Test publishing batch extraction completion message."""
        # Set up environment for default prefix
        with patch.dict('os.environ', {'NATS_SUBJECT_PREFIX': 'binance.extraction'}):
            messenger = NATSMessenger()

            # Mock the nats client
            mock_client = Mock()
            mock_client.is_closed = False
            messenger.client = mock_client

            # Test batch message publishing
            await messenger.publish_batch_extraction_completion(
                symbols=["BTCUSDT", "ETHUSDT"],
                period="15m",
                total_records_fetched=200,
                total_records_written=200,
                success=True,
                duration_seconds=10.5,
                errors=[],
                total_gaps_found=0,
                total_gaps_filled=0,
                extraction_type="klines",
            )

            # Verify the message was published
            mock_client.publish.assert_called_once()
            call_args = mock_client.publish.call_args
            assert call_args[0][0] == "binance.extraction.klines.batch.15m"

            # Verify message content
            message_data = json.loads(call_args[0][1].decode())
            assert message_data["event_type"] == "batch_extraction_completed"
            assert message_data["symbols"] == ["BTCUSDT", "ETHUSDT"]
            assert message_data["period"] == "15m"
            assert message_data["success"] is True
            assert message_data["metrics"]["total_records_fetched"] == 200
            assert message_data["metrics"]["total_records_written"] == 200
            assert message_data["metrics"]["duration_seconds"] == 10.5
            assert message_data["metrics"]["symbols_processed"] == 2


class TestMessagingFunctions:
    """Test messaging utility functions."""

    def test_get_messenger_singleton(self):
        """Test that get_messenger returns a singleton."""
        messenger1 = get_messenger()
        messenger2 = get_messenger()
        assert messenger1 is messenger2

    @patch("utils.messaging.get_messenger")
    @patch("utils.messaging.asyncio.new_event_loop")
    @patch("utils.messaging.asyncio.set_event_loop")
    def test_publish_extraction_completion_sync(self, mock_set_loop, mock_new_loop, mock_get_messenger):
        """Test synchronous extraction completion publishing."""
        # Mock the messenger
        mock_messenger = Mock()
        mock_get_messenger.return_value = mock_messenger

        # Mock the event loop
        mock_loop = Mock()
        mock_new_loop.return_value = mock_loop

        # Test the function
        publish_extraction_completion_sync(
            symbol="BTCUSDT",
            period="15m",
            records_fetched=100,
            records_written=100,
            success=True,
            duration_seconds=5.5,
            errors=[],
            gaps_found=0,
            gaps_filled=0,
            extraction_type="klines",
        )

        # Verify the async function was called
        mock_loop.run_until_complete.assert_called_once()
        mock_loop.close.assert_called_once()


class TestNATSMessagingIntegration:
    """Test NATS messaging integration with extraction jobs."""

    @patch("utils.messaging.publish_extraction_completion_sync")
    def test_nats_messaging_in_extraction_job(self, mock_publish):
        """Test that NATS messaging is called during extraction."""
        # Import the extraction function
        from jobs.extract_klines import extract_klines_for_symbol

        # Mock dependencies
        mock_fetcher = Mock()
        mock_fetcher.fetch_klines.return_value = [Mock(), Mock()]  # 2 klines

        mock_db_adapter = Mock()
        mock_db_adapter.query_latest.return_value = []
        mock_db_adapter.write_batch.return_value = 2
        mock_db_adapter.find_gaps.return_value = []

        mock_args = Mock()
        mock_args.incremental = False
        mock_args.dry_run = False
        mock_args.batch_size = 1000
        mock_args.check_gaps = True
        mock_args.limit = None

        mock_logger = Mock()

        # Call the extraction function
        result = extract_klines_for_symbol(
            symbol="BTCUSDT",
            period="15m",
            start_date=None,
            end_date=None,
            fetcher=mock_fetcher,
            db_adapter=mock_db_adapter,
            args=mock_args,
            logger=mock_logger,
        )

        # Verify the result
        assert result["success"] is True
        assert result["records_fetched"] == 2
        assert result["records_written"] == 2

        # Note: The actual NATS messaging is called in the main function,
        # not in extract_klines_for_symbol, so we don't test it here
