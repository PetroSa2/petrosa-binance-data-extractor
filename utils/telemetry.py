"""
OpenTelemetry initialization and configuration for the Binance data extractor.

This module provides comprehensive auto-instrumentation setup for observability
with New Relic and other OTLP-compatible backends.
"""

import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, Optional

from opentelemetry.sdk.trace.export import ConsoleSpanExporter

import constants

# OpenTelemetry Core
try:
    from opentelemetry import metrics, trace

    # Exporters
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.instrumentation.pymongo import PymongoInstrumentor

    # Auto-instrumentation
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.semconv.resource import ResourceAttributes

    # Optional instrumentors
    try:
        from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor

        URLLIB3_AVAILABLE = True
    except ImportError:
        URLLIB3_AVAILABLE = False

    # Resource detection
    try:
        from opentelemetry.resourcedetector.gcp import GoogleCloudResourceDetector

        GCP_AVAILABLE = True
    except ImportError:
        GCP_AVAILABLE = False

    try:
        from opentelemetry.resourcedetector.aws import (
            AwsEc2ResourceDetector,
            AwsEcsResourceDetector,
            AwsEksResourceDetector,
            AwsLambdaResourceDetector,
        )

        AWS_AVAILABLE = True
    except ImportError:
        AWS_AVAILABLE = False

    OTEL_AVAILABLE = True

except ImportError as e:
    logging.getLogger(__name__).warning("OpenTelemetry not available: %s", str(e))
    OTEL_AVAILABLE = False
    GCP_AVAILABLE = False
    AWS_AVAILABLE = False
    URLLIB3_AVAILABLE = False


class TelemetryManager:
    """Manages OpenTelemetry initialization and configuration."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.initialized = False
        self.tracer_provider = None
        self.meter_provider = None

    def initialize_telemetry(
        self,
        service_name: Optional[str] = None,
        service_version: Optional[str] = None,
        environment: Optional[str] = None,
        enable_auto_instrumentation: bool = True,
    ) -> bool:
        """
        Initialize OpenTelemetry with auto-instrumentation.

        Args:
            service_name: Name of the service (defaults to OTEL_SERVICE_NAME from constants)
            service_version: Version of the service (defaults to OTEL_SERVICE_VERSION)
            environment: Environment name (defaults to ENVIRONMENT env var)
            enable_auto_instrumentation: Whether to enable auto-instrumentation

        Returns:
            bool: True if initialization was successful, False otherwise
        """
        if not OTEL_AVAILABLE:
            self.logger.warning("OpenTelemetry not available, skipping initialization")
            return False

        if self.initialized:
            self.logger.info("OpenTelemetry already initialized")
            return True

        try:
            # Create resource
            resource = self._create_resource(service_name, service_version, environment)

            # Initialize tracing
            self._setup_tracing(resource)

            # Initialize metrics
            self._setup_metrics(resource)

            # Enable auto-instrumentation
            if enable_auto_instrumentation:
                self._setup_auto_instrumentation()

            self.initialized = True

            self.logger.info(
                "OpenTelemetry initialized successfully for service: %s",
                service_name or constants.OTEL_SERVICE_NAME,
                extra={
                    "service_name": service_name or constants.OTEL_SERVICE_NAME,
                    "service_version": service_version
                    or constants.OTEL_SERVICE_VERSION,
                    "environment": environment or os.getenv("ENVIRONMENT", "unknown"),
                    "otel_endpoint": constants.OTEL_EXPORTER_OTLP_ENDPOINT or "default",
                    "auto_instrumentation": enable_auto_instrumentation,
                    "tracer_provider_set": trace.get_tracer_provider() is not None,
                },
            )
            return True

        except ImportError as e:
            self.logger.error(
                "Failed to initialize OpenTelemetry: %s", str(e), exc_info=True
            )
            return False

    def _create_resource(
        self,
        service_name: Optional[str] = None,
        service_version: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> Resource:
        """Create OpenTelemetry resource with auto-detection."""

        # Base attributes
        attributes: Dict[str, Any] = {
            SERVICE_NAME: service_name or constants.OTEL_SERVICE_NAME,
            SERVICE_VERSION: service_version or constants.OTEL_SERVICE_VERSION,
            ResourceAttributes.SERVICE_INSTANCE_ID: os.getenv("HOSTNAME", "unknown"),
        }

        # Add environment if provided
        if environment:
            attributes[ResourceAttributes.DEPLOYMENT_ENVIRONMENT] = environment
        elif os.getenv("ENVIRONMENT"):
            env_val = os.getenv("ENVIRONMENT")
            if env_val:
                attributes[ResourceAttributes.DEPLOYMENT_ENVIRONMENT] = env_val

        # Add Kubernetes attributes if available
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            attributes.update(
                {
                    ResourceAttributes.K8S_CLUSTER_NAME: os.getenv(
                        "K8S_CLUSTER_NAME", "unknown"
                    ),
                    ResourceAttributes.K8S_NAMESPACE_NAME: os.getenv(
                        "K8S_NAMESPACE", "default"
                    ),
                    ResourceAttributes.K8S_POD_NAME: os.getenv(
                        "K8S_POD_NAME", os.getenv("HOSTNAME", "unknown")
                    ),
                    ResourceAttributes.K8S_CONTAINER_NAME: os.getenv(
                        "K8S_CONTAINER_NAME", "binance-extractor"
                    ),
                    ResourceAttributes.K8S_DEPLOYMENT_NAME: os.getenv(
                        "K8S_DEPLOYMENT_NAME", "binance-extractor"
                    ),
                }
            )

        # Add custom resource attributes from environment
        if constants.OTEL_RESOURCE_ATTRIBUTES:
            custom_attrs = {}
            for pair in constants.OTEL_RESOURCE_ATTRIBUTES.split(","):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    custom_attrs[key.strip()] = value.strip()
            attributes.update(custom_attrs)

        # Create resource with auto-detection
        detectors = []

        # Add cloud resource detectors
        if GCP_AVAILABLE:
            try:
                detectors.append(GoogleCloudResourceDetector())
            except ImportError:
                self.logger.debug("GCP resource detector not available")

        if AWS_AVAILABLE:
            try:
                detectors.extend(
                    [
                        AwsEcsResourceDetector(),
                        AwsEc2ResourceDetector(),
                        AwsEksResourceDetector(),
                        AwsLambdaResourceDetector(),
                    ]
                )
            except ImportError:
                self.logger.debug("AWS resource detectors not available")

        resource = Resource.create(attributes)

        # Merge with detected resources
        for detector in detectors:
            try:
                detected_resource = detector.detect()
                resource = resource.merge(detected_resource)
            except ImportError as e:
                self.logger.debug(
                    "Resource detection failed for %s: %s", detector, str(e)
                )

        return resource

    def _setup_tracing(self, resource: Resource):
        """Setup tracing with OTLP exporter."""
        # Create tracer provider
        self.tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(self.tracer_provider)

        # Always add a console exporter for debugging
        try:

            console_processor = BatchSpanProcessor(ConsoleSpanExporter())
            self.tracer_provider.add_span_processor(console_processor)
            self.logger.info("Console span exporter added for debugging")
        except ImportError:
            self.logger.debug("Console exporter not available")

        # Setup OTLP span exporter if endpoint is configured
        if constants.OTEL_EXPORTER_OTLP_ENDPOINT:
            headers = self._parse_headers(constants.OTEL_EXPORTER_OTLP_HEADERS or "")

            # Determine if we should use insecure connection
            is_https = constants.OTEL_EXPORTER_OTLP_ENDPOINT.startswith("https://")

            # Log configuration for debugging (don't log actual headers for security)
            self.logger.info(
                "Configuring OTLP span exporter: endpoint=%s, headers_count=%d, secure=%s",
                constants.OTEL_EXPORTER_OTLP_ENDPOINT,
                len(headers),
                is_https,
            )

            try:
                # Create OTLP exporter with proper configuration
                otlp_exporter = OTLPSpanExporter(
                    endpoint=getattr(
                        constants, "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", None
                    )
                    or constants.OTEL_EXPORTER_OTLP_ENDPOINT,
                    headers=headers,
                    insecure=not is_https,
                    timeout=30,  # 30 second timeout
                )

                # Add batch span processor with optimized settings
                span_processor = BatchSpanProcessor(
                    otlp_exporter,
                    max_queue_size=512,
                    export_timeout_millis=30000,  # 30 seconds
                    max_export_batch_size=512,
                )
                self.tracer_provider.add_span_processor(span_processor)

                self.logger.info(
                    "✓ OTLP span exporter configured successfully: %s",
                    constants.OTEL_EXPORTER_OTLP_ENDPOINT,
                )

                # Test the exporter by trying to export a test span
                test_tracer = self.tracer_provider.get_tracer("connection_test")
                try:
                    # Defensive: ensure start_as_current_span is a context manager
                    span_cm = test_tracer.start_as_current_span("exporter_test")
                    if not (
                        hasattr(span_cm, "__enter__") and hasattr(span_cm, "__exit__")
                    ):
                        raise TypeError(
                            "start_as_current_span did not return a context manager"
                        )
                    # Defensive: ensure start_as_current_span is a context manager
                    if not (
                        hasattr(span_cm, "__enter__") and hasattr(span_cm, "__exit__")
                    ):

                        @contextmanager
                        def span_context_manager():
                            span = next(span_cm)
                            try:
                                yield span
                            finally:
                                try:
                                    next(span_cm)
                                except StopIteration:
                                    pass

                        context_manager = span_context_manager()
                    else:
                        context_manager = span_cm

                    with context_manager as test_span:
                        test_span.set_attribute("test.connection", "otlp_exporter")
                        self.logger.info(
                            "Test span created for OTLP exporter validation"
                        )
                except (TypeError, AttributeError) as test_e:
                    self.logger.warning(
                        "Could not create test span for OTLP exporter: %s", str(test_e)
                    )

            except RuntimeError as e:
                self.logger.error(
                    "✗ Failed to configure OTLP span exporter: %s", str(e)
                )
                self.logger.info(
                    "Continuing with console tracing only (no remote export)"
                )
        else:
            self.logger.warning(
                "OTEL_EXPORTER_OTLP_ENDPOINT not configured, tracing will be local only (no export)"
            )

        # Verify tracer provider is working
        test_tracer = self.tracer_provider.get_tracer("telemetry_test")
        try:
            span_cm = test_tracer.start_as_current_span("initialization_test")
            # Use the same span_context_manager as above if needed
            if not (hasattr(span_cm, "__enter__") and hasattr(span_cm, "__exit__")):

                context_manager = span_context_manager()
            else:
                context_manager = span_cm

            with context_manager as span:
                span.set_attribute("test", "initialization")
                span_context = span.get_span_context()
                self.logger.info(
                    "Tracer provider test - trace_id=%s, span_id=%s, is_valid=%s",
                    format(span_context.trace_id, "032x"),
                    format(span_context.span_id, "016x"),
                    span_context.is_valid,
                )
                if span_context.trace_id != 0 and span_context.is_valid:
                    self.logger.info(
                        "✓ Tracer provider test successful - spans will be generated properly"
                    )
                else:
                    self.logger.error(
                        "✗ Tracer provider test failed - trace_id=%s, span_id=%s, is_valid=%s",
                        format(span_context.trace_id, "032x"),
                        format(span_context.span_id, "016x"),
                        span_context.is_valid,
                    )
        except (TypeError, AttributeError, RuntimeError) as e:
            self.logger.error("Error during tracer provider test: %s", str(e))

    def _setup_metrics(self, _resource: Resource):
        """Setup metrics with OTLP exporter."""
        self.logger.info(
            "Skipping metrics setup temporarily to focus on tracing issues"
        )
        # Temporarily disable metrics to isolate tracing issues
        # Will re-enable once tracing is working properly
        return

    def _setup_auto_instrumentation(self):
        """Setup auto-instrumentation for common libraries."""
        instrumentors = []

        # HTTP requests instrumentation
        try:
            RequestsInstrumentor().instrument()
            instrumentors.append("requests")
        except ImportError as e:
            self.logger.warning("Failed to instrument requests: %s", str(e))

        # urllib3 instrumentation
        if URLLIB3_AVAILABLE:
            try:
                URLLib3Instrumentor().instrument()
                instrumentors.append("urllib3")
            except ImportError as e:
                self.logger.warning("Failed to instrument urllib3: %s", str(e))

        # Database instrumentation
        try:
            PymongoInstrumentor().instrument()
            instrumentors.append("pymongo")
        except ImportError as e:
            self.logger.warning("Failed to instrument pymongo: %s", str(e))

        try:
            SQLAlchemyInstrumentor().instrument()
            instrumentors.append("sqlalchemy")
        except ImportError as e:
            self.logger.warning("Failed to instrument sqlalchemy: %s", str(e))

        # Logging instrumentation
        try:
            LoggingInstrumentor().instrument(set_logging_format=True)
            instrumentors.append("logging")
        except ImportError as e:
            self.logger.warning("Failed to instrument logging: %s", str(e))

        self.logger.info(
            "Auto-instrumentation enabled for: %s", ", ".join(instrumentors)
        )

    def _parse_headers(self, headers_str: str) -> Dict[str, str]:
        """Parse OTLP headers string into dictionary."""
        headers = {}
        if headers_str:
            for header in headers_str.split(","):
                if "=" in header:
                    key, value = header.split("=", 1)
                    headers[key.strip()] = value.strip()
        return headers

    def get_tracer(self, name: str):
        """Get a tracer instance."""
        if not OTEL_AVAILABLE or not self.initialized:
            return None
        return trace.get_tracer(name)

    def get_meter(self, name: str):
        """Get a meter instance."""
        if not OTEL_AVAILABLE or not self.initialized:
            return None
        return metrics.get_meter(name)


# Global telemetry manager instance
telemetry_manager = TelemetryManager()


def initialize_telemetry(**kwargs) -> bool:
    """Initialize OpenTelemetry with the global manager."""
    return telemetry_manager.initialize_telemetry(**kwargs)


def get_tracer(name: str):
    """Get a tracer instance from the global manager."""
    return telemetry_manager.get_tracer(name)


def get_meter(name: str):
    """Get a meter instance from the global manager."""
    return telemetry_manager.get_meter(name)
