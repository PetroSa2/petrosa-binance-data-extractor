"""
OpenTelemetry initialization and configuration for the Binance data extractor.

This module provides a simple, reliable OpenTelemetry setup for observability
with New Relic and other OTLP-compatible backends.
"""

import logging
import os
from typing import Optional

# Import constants for tests
try:
    import constants
except ImportError:
    # Create a mock constants module for tests
    class MockConstants:
        OTEL_EXPORTER_OTLP_ENDPOINT = ""
        OTEL_RESOURCE_ATTRIBUTES = ""

    constants = MockConstants()  # type: ignore

# OpenTelemetry Core
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter as GRPCSpanExporter,
    )
    from opentelemetry.instrumentation.logging import LoggingInstrumentor

    # Auto-instrumentation
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    OTEL_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning("OpenTelemetry not available: %s", str(e))
    OTEL_AVAILABLE = False

# Additional imports for tests
try:
    from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False

try:
    from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
    URLLIB3_AVAILABLE = True
except ImportError:
    URLLIB3_AVAILABLE = False

# Cloud resource detectors
try:
    from opentelemetry.sdk.resources import Resource
    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False

try:
    from opentelemetry.sdk.resources import Resource
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

# Metrics (placeholder for tests)
try:
    from opentelemetry import metrics
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    metrics = None  # type: ignore


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
                logging.getLogger(__name__).error(f"Failed to configure OTLP exporter: {e}")

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

# Module-level exports for backward compatibility and tests
def get_meter_module(name: str):
    """Get a meter instance at module level (not implemented)."""
    return None

# Export TelemetryManager methods at module level for tests
def get_tracer_module(name: str):
    """Get a tracer instance at module level."""
    return get_tracer(name)

def get_tracer_simple_module(name: str):
    """Get a tracer instance directly at module level."""
    return get_tracer_simple(name)

# Export OpenTelemetry classes for test patching
if OTEL_AVAILABLE:
    # Export classes that tests need to patch
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
else:
    # Mock classes for when OpenTelemetry is not available
    TracerProvider = None  # type: ignore
    BatchSpanProcessor = None  # type: ignore
    ConsoleSpanExporter = None  # type: ignore
    Resource = None  # type: ignore
    OTLPSpanExporter = None  # type: ignore
    RequestsInstrumentor = None  # type: ignore
    SQLAlchemyInstrumentor = None  # type: ignore
    LoggingInstrumentor = None  # type: ignore
    PymongoInstrumentor = None  # type: ignore
    URLLib3Instrumentor = None  # type: ignore


class TelemetryManager:
    """Telemetry manager for OpenTelemetry setup and management."""
    logger = logging.getLogger(__name__)

    def __init__(self):
        """Initialize the telemetry manager."""
        self.initialized = False
        self.tracer_provider = None
        self.meter_provider = None
        # Use class-level logger
        self.logger = self.__class__.logger

    def initialize_telemetry(self) -> bool:
        """Initialize OpenTelemetry with proper configuration."""
        if not OTEL_AVAILABLE:
            self.logger.warning("OpenTelemetry not available, skipping initialization")
            return False

        if self.initialized:
            self.logger.info("OpenTelemetry already initialized")
            return True

        try:
            # Create resource
            resource = self._create_resource()

            # Setup tracing
            self._setup_tracing(resource)

            # Setup metrics (placeholder)
            self._setup_metrics(resource)

            # Setup auto-instrumentation
            self._setup_auto_instrumentation()

            self.initialized = True
            self.logger.info("OpenTelemetry initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize OpenTelemetry: {e}")
            return False

    def _create_resource(self, service_name: Optional[str] = None, service_version: Optional[str] = None, environment: Optional[str] = None):
        """Create OpenTelemetry resource."""
        if not OTEL_AVAILABLE:
            return None

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

        return resource

    def _setup_tracing(self, resource):
        """Setup tracing with span processors."""
        if not OTEL_AVAILABLE:
            return

        # Create tracer provider
        self.tracer_provider = TracerProvider(resource=resource)

        # Add span processors
        span_processors = []

        # Always add console exporter for debugging
        console_exporter = ConsoleSpanExporter()
        span_processors.append(BatchSpanProcessor(console_exporter))

        # Add OTLP exporter if endpoint is configured
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        print(f"DEBUG: OTLP endpoint = {otlp_endpoint}")
        if otlp_endpoint:
            print(f"DEBUG: Creating OTLP exporter for endpoint: {otlp_endpoint}")
            try:
                headers = self._parse_headers(os.getenv("OTEL_EXPORTER_OTLP_HEADERS", ""))
                print(f"DEBUG: About to create GRPCSpanExporter")
                otlp_exporter = GRPCSpanExporter(
                    endpoint=otlp_endpoint,
                    headers=headers
                )
                print(f"DEBUG: GRPCSpanExporter created successfully")
                span_processors.append(BatchSpanProcessor(otlp_exporter))
                self.logger.info(f"OTLP exporter configured for endpoint: {otlp_endpoint}")
            except Exception as e:
                print(f"DEBUG: Exception caught: {e}")
                self.logger.error(f"Failed to configure OTLP exporter: {e}")
        else:
            print(f"DEBUG: No OTLP endpoint configured")

        # Add all span processors to the provider
        for processor in span_processors:
            self.tracer_provider.add_span_processor(processor)

        # Set the global tracer provider
        trace.set_tracer_provider(self.tracer_provider)

    def _setup_metrics(self, resource):
        """Setup metrics (placeholder for future implementation)."""
        # Metrics setup is not implemented yet

    def _setup_auto_instrumentation(self):
        """Setup auto-instrumentation for various libraries."""
        if not OTEL_AVAILABLE:
            return

        try:
            # Core instrumentors
            RequestsInstrumentor().instrument()
            SQLAlchemyInstrumentor().instrument()
            LoggingInstrumentor().instrument(set_logging_format=True)

            # Additional instrumentors if available
            if URLLIB3_AVAILABLE:
                URLLib3Instrumentor().instrument()

            if PYMONGO_AVAILABLE:
                PymongoInstrumentor().instrument()

            self.logger.info("Auto-instrumentation enabled")
        except Exception as e:
            self.logger.warning(f"Failed to enable auto-instrumentation: {e}")

    def _parse_headers(self, headers_str: str) -> dict:
        """Parse headers string into dictionary."""
        headers = {}
        if headers_str:
            for header in headers_str.split(","):
                if "=" in header:
                    key, value = header.split("=", 1)
                    headers[key.strip()] = value.strip()
        return headers

    def get_tracer(self, name: str):
        """Get a tracer instance."""
        if not OTEL_AVAILABLE:
            return None

        try:
            # If not initialized, try to initialize first
            if not self.initialized:
                if not self.initialize_telemetry():
                    return None

            # Get tracer from the current provider
            return trace.get_tracer(name)

        except Exception as e:
            self.logger.warning(f"Failed to get tracer: {e}")
            return None

    def get_tracer_simple(self, name: str):
        """Get a tracer instance directly from OpenTelemetry."""
        if not OTEL_AVAILABLE:
            return None

        try:
            return trace.get_tracer(name)
        except Exception as e:
            self.logger.warning(f"Failed to get tracer: {e}")
            return None

    def get_meter(self, name: str):
        """Get a meter instance."""
        if not self.initialized or not METRICS_AVAILABLE:
            return None
        try:
            return metrics.get_meter(name)
        except Exception:
            return None
