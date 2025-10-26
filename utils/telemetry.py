"""
OpenTelemetry initialization and configuration for the Binance data extractor.

This module provides a simple, reliable OpenTelemetry setup for observability
with New Relic and other OTLP-compatible backends.
"""

import logging
import os

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

    # Custom span processor to filter invalid attributes
    class AttributeFilterSpanProcessor(BatchSpanProcessor):
        """
        Custom span processor that filters out invalid attribute values before export.

        OpenTelemetry only allows primitive types (str, int, float, bool, bytes) or None
        as attribute values. This processor filters out dict and list values.
        """

        def on_start(self, span, parent_context=None):
            """Clean attributes when span starts."""
            super().on_start(span, parent_context)
            self._clean_attributes(span)

        def on_end(self, span):
            """Clean attributes when span ends."""
            self._clean_attributes(span)
            super().on_end(span)

        def _clean_attributes(self, span):
            """Remove invalid attribute values from span."""
            if not hasattr(span, "_attributes") or not span._attributes:
                return

            # Identify invalid attributes
            invalid_keys = []
            for key, value in span._attributes.items():
                if isinstance(value, dict | list):
                    invalid_keys.append(key)

            # Remove invalid attributes
            for key in invalid_keys:
                del span._attributes[key]

    OTEL_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning("OpenTelemetry not available: %s", str(e))
    OTEL_AVAILABLE = False

    # No-op span processor when OpenTelemetry is unavailable
    class AttributeFilterSpanProcessor:
        """No-op span processor when OpenTelemetry is unavailable."""

        def __init__(self, *args, **kwargs):
            """Initialize no-op processor."""
            pass

        def on_start(self, *args, **kwargs):
            """No-op on_start."""
            pass

        def on_end(self, *args, **kwargs):
            """No-op on_end."""
            pass

        def shutdown(self):
            """No-op shutdown."""
            pass

        def force_flush(self, timeout_millis=None):
            """No-op force_flush."""
            return True


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

# Metrics
try:
    from opentelemetry import metrics
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter as GRPCMetricExporter,
    )
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    metrics = None  # type: ignore
    GRPCMetricExporter = None  # type: ignore
    MeterProvider = None  # type: ignore
    PeriodicExportingMetricReader = None  # type: ignore


# Global tracer provider
_tracer_provider = None
_initialized = False


def initialize_telemetry(
    service_name: str | None = None,
    service_version: str | None = None,
    environment: str | None = None,
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
        logging.getLogger(__name__).warning(
            "OpenTelemetry not available, skipping initialization"
        )
        return False

    if _initialized:
        logging.getLogger(__name__).info("OpenTelemetry already initialized")
        return True

    try:
        # Get configuration from environment or use defaults
        service_name = service_name or os.getenv(
            "OTEL_SERVICE_NAME", "binance-data-extractor"
        )
        service_version = service_version or os.getenv("OTEL_SERVICE_VERSION", "2.0.0")
        environment = environment or os.getenv("ENVIRONMENT", "production")

        # Create resource
        resource = Resource.create(
            {
                "service.name": service_name or "binance-data-extractor",
                "service.version": service_version or "2.0.0",
                "deployment.environment": environment or "production",
                "service.instance.id": os.getenv("HOSTNAME", "unknown"),
            }
        )

        # Create tracer provider
        _tracer_provider = TracerProvider(resource=resource)

        # Add span processors
        span_processors = []

        # Always add console exporter for debugging
        console_exporter = ConsoleSpanExporter()
        span_processors.append(AttributeFilterSpanProcessor(console_exporter))

        # Add OTLP exporter if endpoint is configured and not in testing environment
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint and environment != "testing":
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
                    endpoint=otlp_endpoint, headers=headers
                )
                span_processors.append(AttributeFilterSpanProcessor(otlp_exporter))
                logging.getLogger(__name__).info(
                    f"OTLP exporter configured for endpoint: {otlp_endpoint}"
                )
            except Exception as e:
                logging.getLogger(__name__).error(
                    f"Failed to configure OTLP exporter: {e}"
                )

        # Add all span processors to the provider
        for processor in span_processors:
            _tracer_provider.add_span_processor(processor)

        # Set the global tracer provider
        trace.set_tracer_provider(_tracer_provider)

        # Setup metrics
        if METRICS_AVAILABLE and MeterProvider is not None:
            try:
                # Create metric exporter
                if otlp_endpoint and GRPCMetricExporter is not None:
                    metric_exporter = GRPCMetricExporter(
                        endpoint=otlp_endpoint, headers=headers
                    )
                    metric_reader = PeriodicExportingMetricReader(
                        metric_exporter, export_interval_millis=60000
                    )
                    meter_provider = MeterProvider(
                        resource=resource, metric_readers=[metric_reader]
                    )
                    metrics.set_meter_provider(meter_provider)
                    logging.getLogger(__name__).info(
                        "Metrics configured with OTLP exporter"
                    )
            except Exception as e:
                logging.getLogger(__name__).warning(f"Failed to setup metrics: {e}")

        # Enable auto-instrumentation
        try:
            RequestsInstrumentor().instrument()
            SQLAlchemyInstrumentor().instrument()

            # Add PyMySQL instrumentation for MySQL query tracing
            try:
                from opentelemetry.instrumentation.pymysql import PyMySQLInstrumentor

                PyMySQLInstrumentor().instrument()
                logging.getLogger(__name__).info("PyMySQL instrumentation enabled")
            except ImportError:
                logging.getLogger(__name__).warning(
                    "PyMySQL instrumentation not available - install with: "
                    "pip install opentelemetry-instrumentation-pymysql"
                )

            LoggingInstrumentor().instrument(
                set_logging_format=True, log_level=logging.NOTSET
            )
            logging.getLogger(__name__).info("Auto-instrumentation enabled")
        except Exception as e:
            logging.getLogger(__name__).warning(
                f"Failed to enable auto-instrumentation: {e}"
            )

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
    """
    Get a meter instance.

    Args:
        name: Name of the meter

    Returns:
        Meter instance or None if OpenTelemetry is not available
    """
    if not METRICS_AVAILABLE or metrics is None:
        return None

    try:
        # If telemetry not initialized, try to initialize
        if not _initialized:
            initialize_telemetry()

        return metrics.get_meter(name)
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to get meter: {e}")
        return None


# Telemetry is initialized by the application, not on module import.


# Module-level exports for backward compatibility and tests
def get_meter_module(name: str):
    """Get a meter instance at module level."""
    return get_meter(name)


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

    def _create_resource(
        self,
        service_name: str | None = None,
        service_version: str | None = None,
        environment: str | None = None,
    ):
        """Create OpenTelemetry resource."""
        if not OTEL_AVAILABLE or Resource is None:
            return None

        try:
            # Get configuration from environment or use defaults
            service_name = service_name or os.getenv(
                "OTEL_SERVICE_NAME", "binance-data-extractor"
            )
            service_version = service_version or os.getenv(
                "OTEL_SERVICE_VERSION", "2.0.0"
            )
            environment = environment or os.getenv("ENVIRONMENT", "production")

            # Create resource
            resource = Resource.create(
                {
                    "service.name": service_name or "binance-data-extractor",
                    "service.version": service_version or "2.0.0",
                    "deployment.environment": environment or "production",
                    "service.instance.id": os.getenv("HOSTNAME", "unknown"),
                }
            )

            return resource
        except Exception as e:
            self.logger.error(f"Failed to create resource: {e}")
            return None

    def _setup_tracing(self, resource):
        """Setup tracing with span processors."""
        if not OTEL_AVAILABLE or TracerProvider is None:
            return

        try:
            # Create tracer provider
            self.tracer_provider = TracerProvider(resource=resource)
        except Exception as e:
            self.logger.error(f"Failed to create tracer provider: {e}")
            return

        # Add span processors
        span_processors = []

        # Always add console exporter for debugging
        console_exporter = ConsoleSpanExporter()
        span_processors.append(AttributeFilterSpanProcessor(console_exporter))

        # Add OTLP exporter if endpoint is configured
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        print(f"DEBUG: OTLP endpoint = {otlp_endpoint}")
        if otlp_endpoint:
            print(f"DEBUG: Creating OTLP exporter for endpoint: {otlp_endpoint}")
            try:
                headers = self._parse_headers(
                    os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
                )
                print("DEBUG: About to create GRPCSpanExporter")
                otlp_exporter = GRPCSpanExporter(
                    endpoint=otlp_endpoint, headers=headers
                )
                print("DEBUG: GRPCSpanExporter created successfully")
                span_processors.append(AttributeFilterSpanProcessor(otlp_exporter))
                self.logger.info(
                    f"OTLP exporter configured for endpoint: {otlp_endpoint}"
                )
            except Exception as e:
                print(f"DEBUG: Exception caught: {e}")
                self.logger.error(f"Failed to configure OTLP exporter: {e}")
        else:
            print("DEBUG: No OTLP endpoint configured")

        # Add all span processors to the provider
        for processor in span_processors:
            self.tracer_provider.add_span_processor(processor)

        # Set the global tracer provider
        trace.set_tracer_provider(self.tracer_provider)

    def _setup_metrics(self, resource):
        """Setup metrics with OTLP exporter."""
        if not METRICS_AVAILABLE or MeterProvider is None:
            self.logger.warning("Metrics not available, skipping setup")
            return

        try:
            # Get OTLP endpoint
            otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
            if not otlp_endpoint:
                self.logger.warning("No OTLP endpoint configured for metrics")
                return

            # Parse headers
            headers = self._parse_headers(os.getenv("OTEL_EXPORTER_OTLP_HEADERS", ""))

            # Create metric exporter
            metric_exporter = GRPCMetricExporter(
                endpoint=otlp_endpoint, headers=headers
            )

            # Create metric reader with 60-second export interval
            metric_reader = PeriodicExportingMetricReader(
                metric_exporter, export_interval_millis=60000
            )

            # Create meter provider
            self.meter_provider = MeterProvider(
                resource=resource, metric_readers=[metric_reader]
            )

            # Set global meter provider
            metrics.set_meter_provider(self.meter_provider)

            self.logger.info("Metrics configured with OTLP exporter")

        except Exception as e:
            self.logger.error(f"Failed to setup metrics: {e}")

    def _setup_auto_instrumentation(self):
        """Setup auto-instrumentation for various libraries."""
        if not OTEL_AVAILABLE:
            return

        try:
            # Core instrumentors - check they're not None first
            if RequestsInstrumentor is not None:
                RequestsInstrumentor().instrument()
            if SQLAlchemyInstrumentor is not None:
                SQLAlchemyInstrumentor().instrument()
            if LoggingInstrumentor is not None:
                LoggingInstrumentor().instrument(
                    set_logging_format=True, log_level=logging.NOTSET
                )

            # Additional instrumentors if available
            if URLLIB3_AVAILABLE and URLLib3Instrumentor is not None:
                URLLib3Instrumentor().instrument()

            if PYMONGO_AVAILABLE and PymongoInstrumentor is not None:
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
        if not METRICS_AVAILABLE or metrics is None:
            return None

        try:
            # If not initialized, try to initialize first
            if not self.initialized:
                if not self.initialize_telemetry():
                    return None

            # Get meter from the current provider
            return metrics.get_meter(name)

        except Exception as e:
            self.logger.warning(f"Failed to get meter: {e}")
            return None
