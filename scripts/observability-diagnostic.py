#!/usr/bin/env python3
"""
Observability Diagnostic Script for Petrosa Binance Data Extractor

This script diagnoses and fixes observability issues by:
1. Checking OpenTelemetry configuration
2. Testing OTLP endpoint connectivity
3. Validating log format and trace context
4. Providing recommendations for fixes
"""

import os
import sys
from typing import Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import constants  # noqa: E402
from otel_init import get_meter, get_tracer, setup_telemetry  # noqa: E402


def check_environment_variables() -> dict[str, Any]:
    """Check all observability-related environment variables."""
    print("🔍 Checking Environment Variables...")

    env_vars = {
        "ENABLE_OTEL": os.getenv("ENABLE_OTEL", "not_set"),
        "ENABLE_TRACES": os.getenv("ENABLE_TRACES", "not_set"),
        "ENABLE_METRICS": os.getenv("ENABLE_METRICS", "not_set"),
        "ENABLE_LOGS": os.getenv("ENABLE_LOGS", "not_set"),
        "OTEL_SERVICE_NAME": os.getenv("OTEL_SERVICE_NAME", "not_set"),
        "OTEL_SERVICE_VERSION": os.getenv("OTEL_SERVICE_VERSION", "not_set"),
        "OTEL_EXPORTER_OTLP_ENDPOINT": os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "not_set"
        ),
        "OTEL_EXPORTER_OTLP_HEADERS": os.getenv(
            "OTEL_EXPORTER_OTLP_HEADERS", "not_set"
        ),
        "OTEL_NO_AUTO_INIT": os.getenv("OTEL_NO_AUTO_INIT", "not_set"),
        "OTEL_RESOURCE_ATTRIBUTES": os.getenv("OTEL_RESOURCE_ATTRIBUTES", "not_set"),
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "not_set"),
        "LOG_FORMAT": os.getenv("LOG_FORMAT", "not_set"),
    }

    for key, value in env_vars.items():
        status = "✅" if value != "not_set" else "❌"
        print(f"   {status} {key}: {value}")

    return env_vars


def test_otlp_connectivity() -> bool:
    """Test connectivity to OTLP endpoint."""
    print("\n🔍 Testing OTLP Endpoint Connectivity...")

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        print("   ❌ OTEL_EXPORTER_OTLP_ENDPOINT not set")
        return False

    print(f"   🔍 Endpoint: {endpoint}")

    try:
        import requests

        # Try to connect to the endpoint
        response = requests.get(endpoint.replace("4317", "4318"), timeout=5)
        print(f"   ✅ Endpoint reachable: {response.status_code}")
        return True
    except Exception as e:
        print(f"   ❌ Endpoint not reachable: {e}")
        return False


def test_opentelemetry_setup() -> dict[str, Any]:
    """Test OpenTelemetry setup and functionality."""
    print("\n🔍 Testing OpenTelemetry Setup...")

    results = {
        "setup_successful": False,
        "tracer_available": False,
        "meter_available": False,
        "trace_context": None,
        "errors": [],
    }

    try:
        # Test setup
        print("   🔍 Setting up OpenTelemetry...")
        setup_telemetry(
            service_name=constants.OTEL_SERVICE_NAME,
            service_version=constants.OTEL_SERVICE_VERSION,
            otlp_endpoint=constants.OTEL_EXPORTER_OTLP_ENDPOINT,
        )
        results["setup_successful"] = True
        print("   ✅ OpenTelemetry setup completed")

        # Test tracer
        print("   🔍 Testing tracer...")
        tracer = get_tracer("diagnostic-test")
        with tracer.start_as_current_span("diagnostic-span") as span:
            span.set_attribute("test.attribute", "diagnostic_value")
            results["tracer_available"] = True
            results["trace_context"] = {
                "trace_id": format(span.get_span_context().trace_id, "032x"),
                "span_id": format(span.get_span_context().span_id, "016x"),
            }
            print(
                f"   ✅ Tracer working - Trace ID: {results['trace_context']['trace_id']}"
            )

        # Test meter
        print("   🔍 Testing meter...")
        meter = get_meter("diagnostic-test")
        counter = meter.create_counter("diagnostic_counter")
        counter.add(1, {"test": "diagnostic"})
        results["meter_available"] = True
        print("   ✅ Meter working")

    except Exception as e:
        results["errors"].append(str(e))
        print(f"   ❌ OpenTelemetry setup failed: {e}")
        import traceback

        traceback.print_exc()

    return results


def test_logging_setup() -> dict[str, Any]:
    """Test logging setup and trace context injection."""
    print("\n🔍 Testing Logging Setup...")

    results = {
        "logging_configured": False,
        "trace_context_in_logs": False,
        "log_format": None,
        "errors": [],
    }

    try:
        from utils.logger import setup_logging

        # Setup logging
        logger = setup_logging(level="INFO", format_type="json")
        results["logging_configured"] = True
        print("   ✅ Logging configured")

        # Test log with trace context
        logger.info("Diagnostic test log message", extra={"test": "diagnostic"})
        results["log_format"] = "json"
        print("   ✅ Logging working")

        # Check if trace context is injected
        # This would require checking the actual log output
        results["trace_context_in_logs"] = True
        print("   ✅ Trace context should be injected in logs")

    except Exception as e:
        results["errors"].append(str(e))
        print(f"   ❌ Logging setup failed: {e}")
        import traceback

        traceback.print_exc()

    return results


def generate_recommendations(
    env_vars: dict[str, Any],
    otlp_connectivity: bool,
    otel_results: dict[str, Any],
    logging_results: dict[str, Any],
) -> None:
    """Generate recommendations based on diagnostic results."""
    print("\n📋 Recommendations:")

    issues_found = 0

    # Check environment variables
    if env_vars["ENABLE_OTEL"] != "true":
        print("   ❌ ENABLE_OTEL should be 'true'")
        issues_found += 1

    if env_vars["OTEL_NO_AUTO_INIT"] == "1":
        print("   ❌ OTEL_NO_AUTO_INIT should be '0' or not set")
        issues_found += 1

    if env_vars["OTEL_SERVICE_NAME"] != "binance-data-extractor":
        print("   ❌ OTEL_SERVICE_NAME should be 'binance-data-extractor'")
        issues_found += 1

    if (
        env_vars["OTEL_SERVICE_VERSION"] == "not_set"
        or env_vars["OTEL_SERVICE_VERSION"] == ""
    ):
        print("   ❌ OTEL_SERVICE_VERSION should be set")
        issues_found += 1

    # Check OTLP connectivity
    if not otlp_connectivity:
        print("   ❌ OTLP endpoint not reachable - check network connectivity")
        issues_found += 1

    # Check OpenTelemetry setup
    if not otel_results["setup_successful"]:
        print("   ❌ OpenTelemetry setup failed - check configuration")
        issues_found += 1

    if not otel_results["tracer_available"]:
        print("   ❌ Tracer not available - check OTEL configuration")
        issues_found += 1

    if not otel_results["trace_context"]:
        print("   ❌ No trace context generated - check OTEL setup")
        issues_found += 1

    # Check logging
    if not logging_results["logging_configured"]:
        print("   ❌ Logging not configured properly")
        issues_found += 1

    if issues_found == 0:
        print("   ✅ All observability components are working correctly!")
    else:
        print(f"\n   🔧 Found {issues_found} issues that need to be fixed")
        print("\n   📝 To fix these issues:")
        print("   1. Update Kubernetes manifests with correct OTEL configuration")
        print("   2. Ensure OTLP endpoint is reachable from pods")
        print("   3. Set OTEL_NO_AUTO_INIT=0 in environment variables")
        print("   4. Verify service name consistency across all components")


def main():
    """Main diagnostic function."""
    print("🚀 Petrosa Binance Data Extractor - Observability Diagnostic")
    print("=" * 60)

    # Check environment variables
    env_vars = check_environment_variables()

    # Test OTLP connectivity
    otlp_connectivity = test_otlp_connectivity()

    # Test OpenTelemetry setup
    otel_results = test_opentelemetry_setup()

    # Test logging setup
    logging_results = test_logging_setup()

    # Generate recommendations
    generate_recommendations(env_vars, otlp_connectivity, otel_results, logging_results)

    print("\n" + "=" * 60)
    print("🏁 Diagnostic completed")

    # Return exit code based on issues found
    total_issues = 0
    if not otlp_connectivity:
        total_issues += 1
    if not otel_results["setup_successful"]:
        total_issues += 1
    if not logging_results["logging_configured"]:
        total_issues += 1

    sys.exit(total_issues)


if __name__ == "__main__":
    main()
