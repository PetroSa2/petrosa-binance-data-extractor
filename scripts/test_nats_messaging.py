#!/usr/bin/env python3
"""
Test script for NATS messaging functionality.

This script tests the NATS messaging integration by sending test messages
to verify the messaging system works correctly.
"""

import os
import sys
import time

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import constants  # noqa: E402
from utils.logger import get_logger, setup_logging  # noqa: E402
from utils.messaging import (  # noqa: E402
    publish_batch_extraction_completion_sync,
    publish_extraction_completion_sync,
)


def test_single_symbol_messaging():
    """Test sending a single symbol extraction completion message."""
    logger = get_logger(__name__)
    logger.info("Testing single symbol NATS messaging...")

    try:
        publish_extraction_completion_sync(
            symbol="BTCUSDT",
            period="15m",
            records_fetched=150,
            records_written=150,
            success=True,
            duration_seconds=3.5,
            errors=[],
            gaps_found=0,
            gaps_filled=0,
            extraction_type="klines",
        )
        logger.info("✅ Single symbol message sent successfully")
        assert True  # Message sent successfully
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send single symbol message: {e}")
        raise AssertionError(f"Failed to send single symbol message: {e}")
        return False


def test_batch_messaging():
    """Test sending a batch extraction completion message."""
    logger = get_logger(__name__)
    logger.info("Testing batch NATS messaging...")

    try:
        publish_batch_extraction_completion_sync(
            symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
            period="15m",
            total_records_fetched=450,
            total_records_written=450,
            success=True,
            duration_seconds=12.5,
            errors=[],
            total_gaps_found=0,
            total_gaps_filled=0,
            extraction_type="klines",
        )
        logger.info("✅ Batch message sent successfully")
        assert True  # Batch message sent successfully
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send batch message: {e}")
        raise AssertionError(f"Failed to send batch message: {e}")
        return False


def test_error_messaging():
    """Test sending a message with errors."""
    logger = get_logger(__name__)
    logger.info("Testing error NATS messaging...")

    try:
        publish_extraction_completion_sync(
            symbol="INVALIDUSDT",
            period="15m",
            records_fetched=0,
            records_written=0,
            success=False,
            duration_seconds=1.2,
            errors=["API rate limit exceeded", "Connection timeout"],
            gaps_found=0,
            gaps_filled=0,
            extraction_type="klines",
        )
        logger.info("✅ Error message sent successfully")
        assert True  # Error message sent successfully
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send error message: {e}")
        raise AssertionError(f"Failed to send error message: {e}")
        return False


def test_gap_filling_messaging():
    """Test sending a gap filling completion message."""
    logger = get_logger(__name__)
    logger.info("Testing gap filling NATS messaging...")

    try:
        publish_extraction_completion_sync(
            symbol="BTCUSDT",
            period="15m",
            records_fetched=50,
            records_written=50,
            success=True,
            duration_seconds=8.7,
            errors=[],
            gaps_found=3,
            gaps_filled=3,
            extraction_type="klines_gap_filling",
        )
        logger.info("✅ Gap filling message sent successfully")
        assert True  # Gap filling message sent successfully
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send gap filling message: {e}")
        raise AssertionError(f"Failed to send gap filling message: {e}")
        return False


def main():
    """Main test function."""
    # Setup logging
    setup_logging(level="INFO")
    logger = get_logger(__name__)

    logger.info("🚀 Starting NATS messaging tests...")
    logger.info(f"NATS URL: {constants.NATS_URL}")
    logger.info(f"NATS Enabled: {constants.NATS_ENABLED}")

    if not constants.NATS_ENABLED:
        logger.warning("⚠️ NATS messaging is disabled. Set NATS_ENABLED=true to enable.")
        return

    # Run tests
    tests = [
        ("Single Symbol", test_single_symbol_messaging),
        ("Batch", test_batch_messaging),
        ("Error", test_error_messaging),
        ("Gap Filling", test_gap_filling_messaging),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        logger.info(f"\n📋 Running {test_name} test...")
        if test_func():
            passed += 1
            logger.info(f"✅ {test_name} test passed")
        else:
            logger.error(f"❌ {test_name} test failed")

        # Small delay between tests
        time.sleep(1)

    # Summary
    logger.info(f"\n📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        logger.info("🎉 All NATS messaging tests passed!")
        return 0
    else:
        logger.error(f"💥 {total - passed} tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
