"""
OpenTelemetry initialization and configuration for the Binance data extractor.

This module provides a simple, reliable OpenTelemetry setup for observability
with New Relic and other OTLP-compatible backends.
"""

import logging
import os
from typing import Optional

# OpenTelemetry Core
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GRPCSpanExporter
    
    # Auto-instrumentation
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    
    OTEL_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning("OpenTelemetry not available: %s", str(e))
    OTEL_AVAILABLE = False


# Global tracer provider
_tracer_provider = None
_initialized = False


def initialize_telemetry(
    service_name: Optional[str] = None,
    service_version: Optional[str] = None,
    environment: Optional[str] = None,
) -> bool:
    """
    Initialize OpenTelemetry with a simple, reliable setup.
    
    Args:
        service_name: Name of the service
        service_version: Version of the service
        environment: Environment name
        
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    global _tracer_provider, _initialized
    
    if not OTEL_AVAILABLE:
        logging.getLogger(__name__).warning("OpenTelemetry not available, skipping initialization")
        return False
    
    if _initialized:
        logging.getLogger(__name__).info("OpenTelemetry already initialized")
        return True
    
    try:
        # Get configuration from environment or use defaults
        service_name = service_name or os.getenv("OTEL_SERVICE_NAME", "binance-data-extractor")
        service_version = service_version or os.getenv("OTEL_SERVICE_VERSION", "2.0.0")
        environment = environment or os.getenv("ENVIRONMENT", "production")
        
        # Create resource
        resource = Resource.create({
            "service.name": service_name or "binance-data-extractor",
            "service.version": service_version or "2.0.0",
            "deployment.environment": environment or "production",
            "service.instance.id": os.getenv("HOSTNAME", "unknown"),
        })
        
        # Create tracer provider
        _tracer_provider = TracerProvider(resource=resource)
        
        # Add span processors
        span_processors = []
        
        # Always add console exporter for debugging
        console_exporter = ConsoleSpanExporter()
        span_processors.append(BatchSpanProcessor(console_exporter))
        
        # Add OTLP exporter if endpoint is configured
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            try:
                # Parse headers
                headers_str = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
                headers = {}
                if headers_str:
                    for header in headers_str.split(","):
                        if "=" in header:
                            key, value = header.split("=", 1)
                            headers[key.strip()] = value.strip()
                
                otlp_exporter = GRPCSpanExporter(
                    endpoint=otlp_endpoint,
                    headers=headers
                )
                span_processors.append(BatchSpanProcessor(otlp_exporter))
                logging.getLogger(__name__).info(f"OTLP exporter configured for endpoint: {otlp_endpoint}")
            except Exception as e:
                logging.getLogger(__name__).warning(f"Failed to configure OTLP exporter: {e}")
        
        # Add all span processors to the provider
        for processor in span_processors:
            _tracer_provider.add_span_processor(processor)
        
        # Set the global tracer provider
        trace.set_tracer_provider(_tracer_provider)
        
        # Enable auto-instrumentation
        try:
            RequestsInstrumentor().instrument()
            SQLAlchemyInstrumentor().instrument()
            LoggingInstrumentor().instrument(set_logging_format=True)
            logging.getLogger(__name__).info("Auto-instrumentation enabled")
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to enable auto-instrumentation: {e}")
        
        # Test the setup
        test_tracer = trace.get_tracer("telemetry_init")
        with test_tracer.start_as_current_span("initialization_test") as span:
            span.set_attribute("init.success", True)
            span_context = span.get_span_context()
            logging.getLogger(__name__).info(
                f"OpenTelemetry initialized successfully - trace_id: {format(span_context.trace_id, '032x')}"
            )
        
        _initialized = True
        return True
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to initialize OpenTelemetry: {e}")
        return False


def get_tracer(name: str):
    """
    Get a tracer instance.
    
    Args:
        name: Name of the tracer
        
    Returns:
        Tracer instance or None if OpenTelemetry is not available
    """
    if not OTEL_AVAILABLE:
        return None
    
    try:
        # If not initialized, try to initialize first
        if not _initialized:
            if not initialize_telemetry():
                return None
        
        # Get tracer from the current provider
        return trace.get_tracer(name)
        
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to get tracer: {e}")
        return None


def get_tracer_simple(name: str):
    """
    Get a tracer instance directly from OpenTelemetry.
    
    Args:
        name: Name of the tracer
        
    Returns:
        Tracer instance or None if OpenTelemetry is not available
    """
    if not OTEL_AVAILABLE:
        return None
    
    try:
        return trace.get_tracer(name)
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to get tracer: {e}")
        return None


# Legacy functions for backward compatibility
def get_meter(name: str):
    """Get a meter instance (not implemented)."""
    return None


# Initialize telemetry on module import if environment variable is set
if os.getenv("ENABLE_OTEL", "true").lower() in ("true", "1", "yes"):
    initialize_telemetry()


class TelemetryManager:
    """Simple telemetry manager for backward compatibility."""
    
    def __init__(self):
        """Initialize the telemetry manager."""
        self.initialized = initialize_telemetry()
    
    def get_tracer(self, name: str):
        """Get a tracer instance."""
        return get_tracer(name)
    
    def get_tracer_simple(self, name: str):
        """Get a tracer instance directly."""
        return get_tracer_simple(name)
