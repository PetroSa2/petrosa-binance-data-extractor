"""
NATS messaging utilities for the Binance data extractor.

This module provides functionality to send messages to NATS when kline extraction
operations are completed.
"""

import asyncio
import json
import os
from datetime import datetime

import nats
from nats.aio.client import Client as NATSClient

from utils.logger import get_logger

logger = get_logger(__name__)


class NATSMessenger:
    """NATS messaging client for sending extraction completion messages."""

    def __init__(self, nats_url: str | None = None):
        """
        Initialize NATS messenger.

        Args:
            nats_url: NATS server URL. Defaults to environment variable NATS_URL
                     or "nats://localhost:4222"
        """
        self.nats_url = nats_url or os.getenv("NATS_URL", "nats://localhost:4222")
        self.client: NATSClient | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Connect to NATS server."""
        try:
            if self.client is None or self.client.is_closed:
                # Ensure nats_url is not None before passing to nats.connect
                if self.nats_url is None:
                    raise ValueError("NATS URL is not configured")
                self.client = await nats.connect(self.nats_url)
                logger.info(f"Connected to NATS server at {self.nats_url}")
        except Exception as e:
            logger.error(f"Failed to connect to NATS server: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from NATS server."""
        if self.client and not self.client.is_closed:
            await self.client.close()
            logger.info("Disconnected from NATS server")

    async def publish_extraction_completion(
        self,
        symbol: str,
        period: str,
        records_fetched: int,
        records_written: int,
        success: bool,
        duration_seconds: float,
        errors: list | None = None,
        gaps_found: int = 0,
        gaps_filled: int = 0,
        extraction_type: str = "klines",
    ) -> None:
        """
        Publish a message when kline extraction is completed.

        Args:
            symbol: Trading symbol (e.g., BTCUSDT)
            period: Kline interval (e.g., 15m, 1h)
            records_fetched: Number of records fetched from API
            records_written: Number of records written to database
            success: Whether the extraction was successful
            duration_seconds: Duration of the extraction in seconds
            errors: List of errors encountered during extraction
            gaps_found: Number of gaps found in data
            gaps_filled: Number of gaps filled
            extraction_type: Type of extraction (klines, trades, funding)
        """
        if self.client is None or self.client.is_closed:
            await self.connect()

        # Ensure client is connected before publishing
        if self.client is None:
            logger.error("Failed to connect to NATS server")
            return

        message = {
            "event_type": "extraction_completed",
            "extraction_type": extraction_type,
            "symbol": symbol,
            "period": period,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "success": success,
            "metrics": {
                "records_fetched": records_fetched,
                "records_written": records_written,
                "duration_seconds": duration_seconds,
                "gaps_found": gaps_found,
                "gaps_filled": gaps_filled,
            },
            "errors": errors or [],
        }

        # Get subject prefix from environment variable
        subject_prefix = os.getenv("NATS_SUBJECT_PREFIX", "binance.extraction")
        subject = f"{subject_prefix}.{extraction_type}.{symbol}.{period}"

        try:
            await self.client.publish(subject, json.dumps(message).encode())
            logger.info(
                f"Published extraction completion message for {symbol} to {subject}"
            )
        except Exception as e:
            logger.error(f"Failed to publish extraction completion message: {e}")

    async def publish_batch_extraction_completion(
        self,
        symbols: list,
        period: str,
        total_records_fetched: int,
        total_records_written: int,
        success: bool,
        duration_seconds: float,
        errors: list | None = None,
        total_gaps_found: int = 0,
        total_gaps_filled: int = 0,
        extraction_type: str = "klines",
    ) -> None:
        """
        Publish a message when batch kline extraction is completed.

        Args:
            symbols: List of trading symbols processed
            period: Kline interval (e.g., 15m, 1h)
            total_records_fetched: Total number of records fetched from API
            total_records_written: Total number of records written to database
            success: Whether the extraction was successful
            duration_seconds: Duration of the extraction in seconds
            errors: List of errors encountered during extraction
            total_gaps_found: Total number of gaps found in data
            total_gaps_filled: Total number of gaps filled
            extraction_type: Type of extraction (klines, trades, funding)
        """
        if self.client is None or self.client.is_closed:
            await self.connect()

        # Ensure client is connected before publishing
        if self.client is None:
            logger.error("Failed to connect to NATS server")
            return

        message = {
            "event_type": "batch_extraction_completed",
            "extraction_type": extraction_type,
            "symbols": symbols,
            "period": period,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "success": success,
            "metrics": {
                "total_records_fetched": total_records_fetched,
                "total_records_written": total_records_written,
                "duration_seconds": duration_seconds,
                "total_gaps_found": total_gaps_found,
                "total_gaps_filled": total_gaps_filled,
                "symbols_processed": len(symbols),
            },
            "errors": errors or [],
        }

        # Get subject prefix from environment variable
        subject_prefix = os.getenv("NATS_SUBJECT_PREFIX", "binance.extraction")
        subject = f"{subject_prefix}.{extraction_type}.batch.{period}"

        try:
            await self.client.publish(subject, json.dumps(message).encode())
            logger.info(
                f"Published batch extraction completion message for {len(symbols)} symbols to {subject}"
            )
        except Exception as e:
            logger.error(f"Failed to publish batch extraction completion message: {e}")


# Global messenger instance
_messenger: NATSMessenger | None = None


def get_messenger() -> NATSMessenger:
    """Get the global NATS messenger instance."""
    global _messenger
    if _messenger is None:
        _messenger = NATSMessenger()
    return _messenger


def publish_extraction_completion_sync(
    symbol: str,
    period: str,
    records_fetched: int,
    records_written: int,
    success: bool,
    duration_seconds: float,
    errors: list | None = None,
    gaps_found: int = 0,
    gaps_filled: int = 0,
    extraction_type: str = "klines",
    use_production_prefix: bool = False,
    use_gap_filler_prefix: bool = False,
) -> None:
    """
    Synchronous wrapper for publishing extraction completion messages.

    This function runs the async publish function in a new event loop.
    """
    messenger = get_messenger()

    async def _publish():
        # Use production or gap filler prefix if requested
        original_prefix = None
        if use_production_prefix:
            # Override the subject prefix for production messages
            original_prefix = os.getenv("NATS_SUBJECT_PREFIX")
            os.environ["NATS_SUBJECT_PREFIX"] = os.getenv(
                "NATS_SUBJECT_PREFIX_PRODUCTION", "binance.extraction.production"
            )
        elif use_gap_filler_prefix:
            # Override the subject prefix for gap filler messages
            original_prefix = os.getenv("NATS_SUBJECT_PREFIX")
            os.environ["NATS_SUBJECT_PREFIX"] = os.getenv(
                "NATS_SUBJECT_PREFIX_GAP_FILLER", "binance.extraction.gap-filler"
            )

        try:
            await messenger.publish_extraction_completion(
                symbol=symbol,
                period=period,
                records_fetched=records_fetched,
                records_written=records_written,
                success=success,
                duration_seconds=duration_seconds,
                errors=errors,
                gaps_found=gaps_found,
                gaps_filled=gaps_filled,
                extraction_type=extraction_type,
            )
        finally:
            # Restore original prefix if it was changed
            if original_prefix:
                os.environ["NATS_SUBJECT_PREFIX"] = original_prefix
            await messenger.disconnect()

    try:
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_publish())
    except Exception as e:
        logger.error(f"Failed to publish extraction completion message: {e}")
    finally:
        loop.close()


def publish_batch_extraction_completion_sync(
    symbols: list,
    period: str,
    total_records_fetched: int,
    total_records_written: int,
    success: bool,
    duration_seconds: float,
    errors: list | None = None,
    total_gaps_found: int = 0,
    total_gaps_filled: int = 0,
    extraction_type: str = "klines",
) -> None:
    """
    Synchronous wrapper for publishing batch extraction completion messages.

    This function runs the async publish function in a new event loop.
    """
    messenger = get_messenger()

    async def _publish():
        await messenger.publish_batch_extraction_completion(
            symbols=symbols,
            period=period,
            total_records_fetched=total_records_fetched,
            total_records_written=total_records_written,
            success=success,
            duration_seconds=duration_seconds,
            errors=errors,
            total_gaps_found=total_gaps_found,
            total_gaps_filled=total_gaps_filled,
            extraction_type=extraction_type,
        )
        await messenger.disconnect()

    try:
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_publish())
    except Exception as e:
        logger.error(f"Failed to publish batch extraction completion message: {e}")
    finally:
        loop.close()
