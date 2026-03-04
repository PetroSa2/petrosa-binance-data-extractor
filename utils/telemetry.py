"""
Thin telemetry shim for the Binance data extractor.

Delegates to the internal `petrosa-otel` package for all OpenTelemetry setup.
Exposes the same public API (get_tracer, get_meter, TelemetryManager, etc.)
that the rest of the codebase and existing tests expect.

NOTE: Each optional instrumentor is guarded in its own try/except block so
      a single missing package cannot disable all telemetry.
"""

import logging
import os


class _MockConstants:
    """Mock constants for tests when the real constants module is missing."""

    OTEL_EXPORTER_OTLP_ENDPOINT = ""
    OTEL_RESOURCE_ATTRIBUTES = ""


# Import constants for tests
try:
    import constants
except ImportError:
    constants = _MockConstants()  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Core OTEL availability — each block is independent
# ---------------------------------------------------------------------------
try:
    from opentelemetry import metrics, trace  # noqa: F401
    from opentelemetry.instrumentation.logging import LoggingInstrumentor  # noqa: F401
    from opentelemetry.instrumentation.requests import (
        RequestsInstrumentor,  # noqa: F401
    )
    from opentelemetry.sdk.resources import Resource  # noqa: F401
    from opentelemetry.sdk.trace import TracerProvider  # noqa: F401
    from opentelemetry.sdk.trace.export import (  # noqa: F401
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )

    OTEL_AVAILABLE = True
except ImportError as _e:
    logger.warning("OpenTelemetry core not available: %s", _e)
    OTEL_AVAILABLE = False
    trace = None  # type: ignore
    metrics = None  # type: ignore
    Resource = None  # type: ignore
    TracerProvider = None  # type: ignore
    BatchSpanProcessor = None  # type: ignore
    ConsoleSpanExporter = None  # type: ignore
    LoggingInstrumentor = None  # type: ignore
    RequestsInstrumentor = None  # type: ignore

# Independent guards for exporters
try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter as GRPCSpanExporter,  # noqa: F401
    )
except ImportError:
    GRPCSpanExporter = None  # type: ignore

try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter as HTTPSpanExporter,  # noqa: F401
    )
except ImportError:
    HTTPSpanExporter = None  # type: ignore

# Alias used by existing tests that patch utils.telemetry.OTLPSpanExporter
# Default to HTTP if available, otherwise fallback to GRPC
OTLPSpanExporter = HTTPSpanExporter or GRPCSpanExporter  # noqa: F401


# ---------------------------------------------------------------------------
# Optional instrumentors — each in its own guard
# ---------------------------------------------------------------------------
try:
    from opentelemetry.instrumentation.sqlalchemy import (
        SQLAlchemyInstrumentor,  # noqa: F401
    )

    SQLALCHEMY_INSTR_AVAILABLE = True
except ImportError:
    SQLALCHEMY_INSTR_AVAILABLE = False
    SQLAlchemyInstrumentor = None  # type: ignore

try:
    from opentelemetry.instrumentation.pymongo import PymongoInstrumentor  # noqa: F401

    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    PymongoInstrumentor = None  # type: ignore

try:
    from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor  # noqa: F401

    URLLIB3_AVAILABLE = True
except ImportError:
    URLLIB3_AVAILABLE = False
    URLLib3Instrumentor = None  # type: ignore

# Cloud detector flags (lightweight — just checks Resource presence)
GCP_AVAILABLE = OTEL_AVAILABLE
AWS_AVAILABLE = OTEL_AVAILABLE

# Metrics alias
METRICS_AVAILABLE = OTEL_AVAILABLE

# ---------------------------------------------------------------------------
# AttributeFilterSpanProcessor — backward-compat shim for tests
# ---------------------------------------------------------------------------
if OTEL_AVAILABLE and BatchSpanProcessor is not None:

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
            invalid_keys = [
                key
                for key, value in span._attributes.items()
                if isinstance(value, (dict, list))
            ]
            for key in invalid_keys:
                del span._attributes[key]
else:

    class AttributeFilterSpanProcessor:  # type: ignore
        """No-op shim when OpenTelemetry is unavailable."""

        def __init__(self, *args, **kwargs):
            pass

        def on_start(self, *args, **kwargs):
            pass

        def on_end(self, *args, **kwargs):
            pass

        def shutdown(self):
            pass

        def force_flush(self, timeout_millis=None):
            return True


# ---------------------------------------------------------------------------
# TelemetryManager — backward-compat class used by existing tests
# ---------------------------------------------------------------------------
class TelemetryManager:
    """Telemetry manager for OpenTelemetry setup and management."""

    logger = logging.getLogger(__name__)

    def __init__(self):
        """Initialize the telemetry manager."""
        self.initialized = False
        self.tracer_provider = None
        self.meter_provider = None
        self.logger = self.__class__.logger

    def initialize_telemetry(self, *args, **kwargs) -> bool:
        """Initialize OpenTelemetry with proper configuration."""
        if not OTEL_AVAILABLE:
            self.logger.warning("OpenTelemetry not available, skipping initialization")
            return False

        if self.initialized:
            self.logger.info("OpenTelemetry already initialized")
            return True

        # Map legacy arguments to environment variables for backward compatibility
        if "service_name" in kwargs:
            os.environ.setdefault("OTEL_SERVICE_NAME", kwargs["service_name"])
        if "service_version" in kwargs:
            os.environ.setdefault("OTEL_SERVICE_VERSION", kwargs["service_version"])
        if "environment" in kwargs:
            os.environ.setdefault("ENVIRONMENT", kwargs["environment"])

        try:
            from petrosa_otel import setup_telemetry as petrosa_setup_telemetry

            ok = petrosa_setup_telemetry(
                service_name=os.getenv("OTEL_SERVICE_NAME", "binance-data-extractor"),
                service_version=os.getenv("OTEL_SERVICE_VERSION", "2.0.0"),
                service_type="cronjob",
                otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
                protocol=os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf"),
                enable_mysql=True,
                enable_mongodb=True,
                auto_attach_logging=False,
            )
            if ok:
                self.initialized = True
                self.logger.info("OpenTelemetry initialized via petrosa-otel")
                return True
        except Exception as e:
            self.logger.warning("petrosa-otel setup failed, using legacy shim: %s", e)

        try:
            resource = self._create_resource()
            self._setup_tracing(resource)
            self._setup_metrics(resource)
            self._setup_auto_instrumentation()
            self.initialized = True
            self.logger.info("OpenTelemetry initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenTelemetry: {e}")
            return False

    def _create_resource(
        self, service_name=None, service_version=None, environment=None
    ):
        """Create OpenTelemetry resource."""
        if not OTEL_AVAILABLE or Resource is None:
            return None

        service_name = service_name or os.getenv(
            "OTEL_SERVICE_NAME", "binance-data-extractor"
        )
        service_version = service_version or os.getenv("OTEL_SERVICE_VERSION", "2.0.0")
        environment = environment or os.getenv("ENVIRONMENT", "production")

        try:
            attrs = {
                "service.name": service_name,
                "service.version": service_version,
                "deployment.environment": environment,
                "service.instance.id": os.getenv("HOSTNAME", "unknown"),
            }

            # Merge any custom resource attributes from constants
            try:
                custom_attrs_str = getattr(
                    constants, "OTEL_RESOURCE_ATTRIBUTES", ""
                ) or os.getenv("OTEL_RESOURCE_ATTRIBUTES", "")
                if custom_attrs_str:
                    for attr in custom_attrs_str.split(","):
                        if "=" in attr:
                            k, v = attr.split("=", 1)
                            attrs[k.strip()] = v.strip()
            except Exception:
                pass

            resource = Resource.create(attrs)
            return resource
        except Exception as e:
            self.logger.error(f"Failed to create resource: {e}")
            return None

    def _setup_tracing(self, resource):
        """Setup tracing with span processors."""
        if not OTEL_AVAILABLE or TracerProvider is None:
            return

        try:
            self.tracer_provider = TracerProvider(resource=resource)
        except Exception as e:
            self.logger.error(f"Failed to create tracer provider: {e}")
            return

        span_processors = []

        # Conditionally add console exporter to prevent production log flooding
        if ConsoleSpanExporter is not None and os.getenv(
            "OTEL_CONSOLE_EXPORTER", "false"
        ).lower() == "true":
            console_exporter = ConsoleSpanExporter()
            span_processors.append(AttributeFilterSpanProcessor(console_exporter))

        # Add OTLP exporter if endpoint is configured
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or getattr(
            constants, "OTEL_EXPORTER_OTLP_ENDPOINT", ""
        )
        exporter_protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "").lower()

        # Determine which exporter class to use
        exporter_cls = None
        if exporter_protocol in ("http/protobuf", "http", "otlp/http"):
            exporter_cls = HTTPSpanExporter or GRPCSpanExporter
        elif exporter_protocol in ("grpc", "otlp/grpc"):
            exporter_cls = GRPCSpanExporter or HTTPSpanExporter
        else:
            # Auto-detect or default
            exporter_cls = HTTPSpanExporter or GRPCSpanExporter

        if otlp_endpoint and exporter_cls is not None:
            try:
                headers = self._parse_headers(
                    os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
                )
                otlp_exporter = exporter_cls(endpoint=otlp_endpoint, headers=headers)
                span_processors.append(AttributeFilterSpanProcessor(otlp_exporter))
                self.logger.info(
                    "OTLP exporter configured for endpoint: %s (%s)",
                    otlp_endpoint,
                    exporter_protocol,
                )
            except Exception as e:
                self.logger.error(f"Failed to configure OTLP exporter: {e}")

        for processor in span_processors:
            self.tracer_provider.add_span_processor(processor)

        if trace is not None:
            trace.set_tracer_provider(self.tracer_provider)

    def _setup_metrics(self, resource):
        """
        Setup metrics — placeholder, returns None.

        NOTE: Metrics setup is intentionally deferred as it is not yet used
        in the current implementation.
        """
        # TODO: Implement metrics setup when OTel metrics are adopted project-wide.
        return None

    def _setup_auto_instrumentation(self):
        """Setup auto-instrumentation for various libraries."""
        if not OTEL_AVAILABLE:
            return

        # Map of instrumentor names to their classes and availability flags
        instrumentors = [
            ("Requests", RequestsInstrumentor),
            ("SQLAlchemy", SQLAlchemyInstrumentor),
            ("Logging", LoggingInstrumentor),
            ("URLLib3", URLLib3Instrumentor if URLLIB3_AVAILABLE else None),
            ("Pymongo", PymongoInstrumentor if PYMONGO_AVAILABLE else None),
        ]

        for name, instr_cls in instrumentors:
            if instr_cls is not None:
                try:
                    if name == "Logging":
                        instr_cls().instrument(
                            set_logging_format=True, log_level=logging.NOTSET
                        )
                    else:
                        instr_cls().instrument()
                    self.logger.debug(f"{name} instrumentor enabled")
                except Exception as e:
                    # Downgraded from warning to debug to reduce log noise
                    self.logger.debug(f"Skipped optional {name} instrumentor: {e}")

        self.logger.info("Auto-instrumentation setup complete")

    def _parse_headers(self, headers_str) -> dict:
        """Parse headers string into dictionary."""
        if not headers_str:
            return {}
        headers = {}
        for header in headers_str.split(","):
            if "=" in header:
                key, value = header.split("=", 1)
                headers[key.strip()] = value.strip()
        return headers

    def get_tracer(self, name: str):
        """Get a tracer instance."""
        if not OTEL_AVAILABLE or trace is None:
            return None
        try:
            if not self.initialized:
                if not self.initialize_telemetry():
                    return None
            return trace.get_tracer(name)
        except Exception as e:
            self.logger.warning(f"Failed to get tracer: {e}")
            return None

    def get_meter(self, name: str):
        """Get a meter instance."""
        if not OTEL_AVAILABLE or metrics is None:
            return None
        try:
            if not self.initialized:
                if not self.initialize_telemetry():
                    return None
            return metrics.get_meter(name)
        except Exception as e:
            self.logger.warning(f"Failed to get meter: {e}")
            return None


# ---------------------------------------------------------------------------
# Module-level convenience functions (used by job scripts)
# ---------------------------------------------------------------------------


def get_tracer(name: str):
    """Get a tracer instance. Returns None if OTEL not available."""
    if not OTEL_AVAILABLE or trace is None:
        return None
    try:
        return trace.get_tracer(name)
    except Exception as exc:
        logger.warning("Failed to get tracer %s: %s", name, exc)
        return None


def get_meter(name: str):
    """Get a meter instance. Returns None if OTEL not available."""
    if not OTEL_AVAILABLE or metrics is None:
        return None
    try:
        return metrics.get_meter(name)
    except Exception as exc:
        logger.warning("Failed to get meter %s: %s", name, exc)
        return None


def initialize_telemetry(*args, **kwargs) -> bool:
    """Initialize telemetry via TelemetryManager wrapper."""
    manager = TelemetryManager()
    return manager.initialize_telemetry(*args, **kwargs)


def flush_telemetry(timeout_ms: int = 5000) -> None:
    """
    Force-flush all OTel providers before process exit.

    Critical for short-lived CronJobs: the BatchLogRecordProcessor buffers
    logs and only flushes on a timer. Explicit flush ensures nothing is lost.

    Args:
        timeout_ms: Maximum milliseconds to wait for each provider flush.
    """
    if not OTEL_AVAILABLE:
        return

    flushed = []
    errors = []

    try:
        tp = trace.get_tracer_provider() if trace is not None else None
        if hasattr(tp, "force_flush"):
            tp.force_flush(timeout_millis=timeout_ms)
            flushed.append("TracerProvider")
    except Exception as exc:
        errors.append(f"TracerProvider: {exc}")

    try:
        # opentelemetry._logs is internal but needed for manual flush
        from opentelemetry._logs import get_logger_provider

        lp = get_logger_provider()
        if hasattr(lp, "force_flush"):
            lp.force_flush(timeout_millis=timeout_ms)
            flushed.append("LoggerProvider")
    except Exception as exc:
        errors.append(f"LoggerProvider: {exc}")

    try:
        mp = metrics.get_meter_provider() if metrics is not None else None
        if hasattr(mp, "force_flush"):
            mp.force_flush(timeout_millis=timeout_ms)
            flushed.append("MeterProvider")
    except Exception as exc:
        errors.append(f"MeterProvider: {exc}")

    if flushed:
        logger.debug("Telemetry flushed: %s", ", ".join(flushed))
    if errors:
        logger.warning("Telemetry flush errors: %s", "; ".join(errors))


# ---------------------------------------------------------------------------
# Legacy module-level aliases for test backward compatibility
#
# These exist strictly for backward compatibility with existing tests
# that patch these symbols directly (e.g. mock.patch("utils.telemetry.get_tracer")).
# ---------------------------------------------------------------------------
def get_tracer_simple(name: str):
    """Alias for get_tracer."""
    return get_tracer(name)


def get_tracer_module(name: str):
    """Module-level alias for get_tracer."""
    return get_tracer(name)


def get_meter_module(name: str):
    """Module-level alias for get_meter."""
    return get_meter(name)


def get_tracer_simple_module(name: str):
    """Module-level alias for get_tracer_simple."""
    return get_tracer_simple(name)
