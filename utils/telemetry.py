"""
Thin telemetry shim for the Binance data extractor.

Delegates to the internal `petrosa-otel` package for all OpenTelemetry setup.
Exposes the same public API (`get_tracer`, `get_meter`) that the rest of the
codebase expects, so no call-site changes are required.

NOTE: Do NOT add module-level hard imports of optional instrumentation libs here.
      Each optional dependency is guarded in its own try/except block.
"""

import logging
import os

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Core OTEL availability check (no optional instrumentor imports at module level)
# ---------------------------------------------------------------------------
try:
    from opentelemetry import trace, metrics  # noqa: F401

    OTEL_AVAILABLE = True
except ImportError as e:
    logger.warning("OpenTelemetry core not available: %s", e)
    OTEL_AVAILABLE = False
    trace = None  # type: ignore
    metrics = None  # type: ignore

# ---------------------------------------------------------------------------
# Optional instrumentors — each in its own guard so one missing package
# cannot poison the whole telemetry setup.
# ---------------------------------------------------------------------------
try:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor  # noqa: F401

    SQLALCHEMY_INSTR_AVAILABLE = True
except ImportError:
    SQLALCHEMY_INSTR_AVAILABLE = False

try:
    from opentelemetry.instrumentation.pymongo import PymongoInstrumentor  # noqa: F401

    PYMONGO_INSTR_AVAILABLE = True
except ImportError:
    PYMONGO_INSTR_AVAILABLE = False

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_tracer(name: str):
    """
    Get a tracer instance.

    Returns the OTel tracer if available, otherwise None. Callers should
    guard with `if tracer:` before use.
    """
    if not OTEL_AVAILABLE:
        return None
    try:
        from opentelemetry import trace as _trace  # already imported at module level if OTEL_AVAILABLE
        return _trace.get_tracer(name)
    except Exception as exc:
        logger.warning("Failed to get tracer %s: %s", name, exc)
        return None


def get_meter(name: str):
    """
    Get a meter instance.

    Returns the OTel meter if available, otherwise None.
    """
    if not OTEL_AVAILABLE:
        return None
    try:
        from opentelemetry import metrics as _metrics
        return _metrics.get_meter(name)
    except Exception as exc:
        logger.warning("Failed to get meter %s: %s", name, exc)
        return None


def flush_telemetry(timeout_ms: int = 5000) -> None:
    """
    Force-flush all OTel providers.

    Call this before process exit in short-lived CronJobs to ensure all
    buffered spans and logs are exported before the container terminates.

    Args:
        timeout_ms: Maximum time in milliseconds to wait for flush.
    """
    if not OTEL_AVAILABLE:
        return

    flushed = []
    errors = []

    # Flush tracer provider
    try:
        from opentelemetry import trace as _trace
        tp = _trace.get_tracer_provider()
        if hasattr(tp, "force_flush"):
            tp.force_flush(timeout_millis=timeout_ms)
            flushed.append("TracerProvider")
    except Exception as exc:
        errors.append(f"TracerProvider: {exc}")

    # Flush logger provider
    try:
        from opentelemetry._logs import get_logger_provider
        lp = get_logger_provider()
        if hasattr(lp, "force_flush"):
            lp.force_flush(timeout_millis=timeout_ms)
            flushed.append("LoggerProvider")
    except Exception as exc:
        errors.append(f"LoggerProvider: {exc}")

    # Flush meter provider
    try:
        from opentelemetry import metrics as _metrics
        mp = _metrics.get_meter_provider()
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
# Backward-compat aliases kept for any tests that import these directly
# ---------------------------------------------------------------------------
METRICS_AVAILABLE = OTEL_AVAILABLE

# Lazy no-op class for test compatibility
class AttributeFilterSpanProcessor:
    """No-op shim retained for backward compatibility with existing tests."""

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
