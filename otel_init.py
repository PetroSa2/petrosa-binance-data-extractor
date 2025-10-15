"""
OpenTelemetry initialization for the Binance Data Extractor service.

This module sets up OpenTelemetry instrumentation for observability
and monitoring of the data extraction jobs.
"""

import logging
import os

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Global logger provider for attaching handlers
_global_logger_provider = None
_otlp_logging_handler = None


def setup_telemetry(
    service_name: str = "socket-client",
    service_version: str | None = None,
    otlp_endpoint: str | None = None,
    enable_metrics: bool = True,
    enable_traces: bool = True,
    enable_logs: bool = True,
) -> None:
    """
    Set up OpenTelemetry instrumentation.

    Args:
        service_name: Name of the service
        service_version: Version of the service
        otlp_endpoint: OTLP endpoint URL
        enable_metrics: Whether to enable metrics
        enable_traces: Whether to enable traces
        enable_logs: Whether to enable logs
    """
    # Early return if OTEL disabled
    if os.getenv("ENABLE_OTEL", "true").lower() not in ("true", "1", "yes"):
        return

    # Get configuration from environment variables
    service_version = service_version or os.getenv("OTEL_SERVICE_VERSION", "1.0.0")
    otlp_endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    enable_metrics = enable_metrics and os.getenv("ENABLE_METRICS", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    enable_traces = enable_traces and os.getenv("ENABLE_TRACES", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    enable_logs = enable_logs and os.getenv("ENABLE_LOGS", "true").lower() in (
        "true",
        "1",
        "yes",
    )

    # Create resource attributes
    resource_attributes = {
        "service.name": service_name,
        "service.version": service_version,
        "service.instance.id": os.getenv("HOSTNAME", "unknown"),
        "deployment.environment": os.getenv("ENVIRONMENT", "production"),
    }

    # Add custom resource attributes if provided
    custom_attributes = os.getenv("OTEL_RESOURCE_ATTRIBUTES")
    if custom_attributes:
        for attr in custom_attributes.split(","):
            if "=" in attr:
                key, value = attr.split("=", 1)
                resource_attributes[key.strip()] = value.strip()

    resource = Resource.create(resource_attributes)

    # Set up tracing if enabled
    if enable_traces and otlp_endpoint:
        try:
            # Create tracer provider
            tracer_provider = TracerProvider(resource=resource)

            # Create OTLP exporter
            headers_env = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")
            span_headers: dict[str, str] | None = None
            if headers_env:
                # Parse headers as "key1=value1,key2=value2" format
                headers_list = [
                    tuple(h.split("=", 1)) for h in headers_env.split(",") if "=" in h
                ]
                span_headers = dict(headers_list)
            otlp_exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint,
                headers=span_headers,
            )

            # Add batch processor
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

            # Set global tracer provider
            trace.set_tracer_provider(tracer_provider)

            print(f"✅ OpenTelemetry tracing enabled for {service_name}")

        except Exception as e:
            print(f"⚠️  Failed to set up OpenTelemetry tracing: {e}")

    # Set up metrics if enabled
    if enable_metrics and otlp_endpoint:
        try:
            # Create metric reader
            metric_headers_env = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")
            metric_headers: dict[str, str] | None = None
            if metric_headers_env:
                # Parse headers as "key1=value1,key2=value2" format
                metric_headers_list = [
                    tuple(h.split("=", 1))
                    for h in metric_headers_env.split(",")
                    if "=" in h
                ]
                metric_headers = dict(metric_headers_list)
            metric_reader = PeriodicExportingMetricReader(
                OTLPMetricExporter(
                    endpoint=otlp_endpoint,
                    headers=metric_headers,
                ),
                export_interval_millis=int(
                    os.getenv("OTEL_METRIC_EXPORT_INTERVAL", "60000")
                ),
            )

            # Create meter provider
            meter_provider = MeterProvider(
                resource=resource, metric_readers=[metric_reader]
            )

            # Set global meter provider
            metrics.set_meter_provider(meter_provider)

            print(f"✅ OpenTelemetry metrics enabled for {service_name}")

        except Exception as e:
            print(f"⚠️  Failed to set up OpenTelemetry metrics: {e}")

    # Set up logging export via OTLP if enabled
    if enable_logs and otlp_endpoint:
        global _global_logger_provider
        try:
            # Enrich logs with trace context
            # set_logging_format=False to avoid clearing existing handlers
            LoggingInstrumentor().instrument(set_logging_format=False)

            # Parse log headers
            log_headers_env = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")
            log_headers: dict[str, str] | None = None
            if log_headers_env:
                log_headers_list = [
                    tuple(h.split("=", 1))
                    for h in log_headers_env.split(",")
                    if "=" in h
                ]
                log_headers = dict(log_headers_list)

            log_exporter = OTLPLogExporter(
                endpoint=otlp_endpoint,
                headers=log_headers,
            )

            logger_provider = LoggerProvider(resource=resource)
            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(log_exporter)
            )
            _global_logger_provider = logger_provider

            print(f"✅ OpenTelemetry logging export configured for {service_name}")

            # For CLI jobs, attach handler immediately after setup
            attach_logging_handler_simple()

        except Exception as e:
            print(f"⚠️  Failed to set up OpenTelemetry logging export: {e}")

    # Set up HTTP instrumentation
    try:
        RequestsInstrumentor().instrument()
        URLLib3Instrumentor().instrument()
        print(f"✅ OpenTelemetry HTTP instrumentation enabled for {service_name}")

    except Exception as e:
        print(f"⚠️  Failed to set up OpenTelemetry HTTP instrumentation: {e}")

    print(f"🚀 OpenTelemetry setup completed for {service_name} v{service_version}")


def attach_logging_handler_simple():
    """
    Attach OTLP logging handler to root logger.

    For CLI/CronJob scripts and async services without Uvicorn.
    This attaches the OTLP handler to the root logger only.
    """
    global _global_logger_provider, _otlp_logging_handler

    if _global_logger_provider is None:
        print("⚠️  Logger provider not configured - logging export not available")
        return False

    try:
        root_logger = logging.getLogger()

        # Check if handler already attached
        if _otlp_logging_handler is not None:
            if _otlp_logging_handler in root_logger.handlers:
                print("✅ OTLP logging handler already attached")
                return True

        # Create and attach handler
        handler = LoggingHandler(
            level=logging.NOTSET,
            logger_provider=_global_logger_provider,
        )

        root_logger.addHandler(handler)
        _otlp_logging_handler = handler

        print("✅ OTLP logging handler attached to root logger")
        print(f"   Total handlers: {len(root_logger.handlers)}")

        return True

    except Exception as e:
        print(f"⚠️  Failed to attach logging handler: {e}")
        return False


def get_tracer(name: str = None) -> trace.Tracer:
    """
    Get a tracer instance.

    Args:
        name: Tracer name

    Returns:
        Tracer instance
    """
    return trace.get_tracer(name or "binance-data-extractor")


def get_meter(name: str = None) -> metrics.Meter:
    """
    Get a meter instance.

    Args:
        name: Meter name

    Returns:
        Meter instance
    """
    return metrics.get_meter(name or "binance-data-extractor")


# Auto-setup if environment variable is set and not disabled
if os.getenv("ENABLE_OTEL", "true").lower() in ("true", "1", "yes"):
    if not os.getenv("OTEL_NO_AUTO_INIT"):
        if os.getenv("OTEL_AUTO_SETUP", "true").lower() in ("true", "1", "yes"):
            setup_telemetry()
