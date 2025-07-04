#!/usr/bin/env python3
"""
OpenTelemetry initialization script for the Binance data extractor.
This script is designed to be called by opentelemetry-instrument to properly
initialize OpenTelemetry before the main application starts.
"""

import logging
import os
import sys
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_opentelemetry():
    """Setup OpenTelemetry with proper configuration."""
    try:
        # Import OpenTelemetry components
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter as GRPCSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )

        # Create resource with service information
        resource = Resource.create({
            "service.name": "binance-data-extractor",
            "service.version": "1.0.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "production")
        })

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Add span processors based on environment
        if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
            # Use OTLP exporter if endpoint is configured
            otlp_exporter = GRPCSpanExporter(
                endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
                headers=os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
            )
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("OTLP exporter configured")
        else:
            # Use console exporter for local development
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            logger.info("Console exporter configured")

        # Set the global tracer provider
        trace.set_tracer_provider(provider)

        # Create a test tracer to verify setup
        test_tracer = trace.get_tracer("otel_init")
        with test_tracer.start_as_current_span("initialization_test") as span:
            span.set_attribute("init.success", True)
            logger.info("OpenTelemetry initialization successful")

        return True

    except Exception as e:
        logger.error(f"Failed to setup OpenTelemetry: {e}")
        return False

def setup_telemetry(service_name: Optional[str] = None, service_version: Optional[str] = None, environment: Optional[str] = None):
    """Alias for setup_opentelemetry for backward compatibility."""
    # Update environment variables if provided
    if service_name:
        os.environ["OTEL_SERVICE_NAME"] = service_name
    if service_version:
        os.environ["OTEL_SERVICE_VERSION"] = service_version
    if environment:
        os.environ["ENVIRONMENT"] = environment

    return setup_opentelemetry()

def main():
    """Main entry point for OpenTelemetry initialization."""
    logger.info("Starting OpenTelemetry initialization...")

    if setup_opentelemetry():
        logger.info("OpenTelemetry setup completed successfully")
        return 0
    else:
        logger.error("OpenTelemetry setup failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
