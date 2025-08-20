#!/usr/bin/env python3
"""
Simple test script to verify OpenTelemetry is working and communicating with New Relic.
"""

import logging
import os
import sys
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_telemetry():
    """Test the telemetry setup."""
    try:
        # Import our telemetry
        from utils.telemetry import get_tracer, initialize_telemetry

        logger.info("Testing OpenTelemetry setup...")

        # Initialize telemetry
        success = initialize_telemetry(
            service_name="binance-data-extractor-test",
            service_version="2.0.0",
            environment="test",
        )

        if not success:
            logger.error("Failed to initialize telemetry")
            return False

        # Get a tracer
        tracer = get_tracer("test_telemetry")
        if not tracer:
            logger.error("Failed to get tracer")
            return False

        # Create a test span
        with tracer.start_as_current_span("test_span") as span:
            span.set_attribute("test.type", "telemetry_verification")
            span.set_attribute("test.success", True)
            span.set_attribute("test.timestamp", time.time())

            # Get span context
            span_context = span.get_span_context()
            trace_id = format(span_context.trace_id, "032x")
            span_id = format(span_context.span_id, "016x")

            logger.info("✓ Test span created successfully")
            logger.info(f"  Trace ID: {trace_id}")
            logger.info(f"  Span ID: {span_id}")
            logger.info(f"  Is Valid: {span_context.is_valid}")

            # Create a child span
            with tracer.start_as_current_span("child_span") as child_span:
                child_span.set_attribute("child.test", True)
                child_span.set_attribute("parent.trace_id", trace_id)

                child_context = child_span.get_span_context()
                child_trace_id = format(child_context.trace_id, "032x")
                child_span_id = format(child_context.span_id, "016x")

                logger.info("✓ Child span created successfully")
                logger.info(f"  Child Trace ID: {child_trace_id}")
                logger.info(f"  Child Span ID: {child_span_id}")
                logger.info(f"  Trace IDs match: {trace_id == child_trace_id}")

        # Test OTLP endpoint if configured
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            logger.info(f"✓ OTLP endpoint configured: {otlp_endpoint}")

            # Create another span to test export
            with tracer.start_as_current_span("otlp_test_span") as otlp_span:
                otlp_span.set_attribute("export.test", True)
                otlp_span.set_attribute("endpoint", otlp_endpoint)

                otlp_context = otlp_span.get_span_context()
                otlp_trace_id = format(otlp_context.trace_id, "032x")

                logger.info(f"✓ OTLP test span created - Trace ID: {otlp_trace_id}")
                logger.info("  This span should be exported to New Relic")
        else:
            logger.warning(
                "⚠️ No OTLP endpoint configured - spans will only be logged locally"
            )

        return True

    except Exception as e:
        logger.error(f"Telemetry test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main test function."""
    logger.info("🚀 Starting OpenTelemetry test...")

    # Check environment variables
    logger.info("Environment check:")
    logger.info(
        f"  OTEL_EXPORTER_OTLP_ENDPOINT: {os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'Not set')}"
    )
    logger.info(f"  OTEL_SERVICE_NAME: {os.getenv('OTEL_SERVICE_NAME', 'Not set')}")
    logger.info(f"  ENABLE_OTEL: {os.getenv('ENABLE_OTEL', 'Not set')}")

    # Run the test
    success = test_telemetry()

    if success:
        logger.info("🎉 OpenTelemetry test completed successfully!")
        logger.info("💡 Check New Relic for traces (if OTLP endpoint is configured)")
        return 0
    else:
        logger.error("❌ OpenTelemetry test failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
