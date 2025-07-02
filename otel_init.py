"""
OpenTelemetry startup initialization for Binance data extractor.

This module should be imported before any other application code to ensure
proper auto-instrumentation of all libraries.
"""

import logging
import os
from typing import Optional


# Initialize OpenTelemetry as early as possible
def init_otel_early():
    """Initialize OpenTelemetry before importing other modules."""
    # Set environment variables for auto-instrumentation if not already set
    if not os.getenv("OTEL_PYTHON_DISABLED_INSTRUMENTATIONS"):
        # Disable problematic instrumentations that might not be available
        os.environ["OTEL_PYTHON_DISABLED_INSTRUMENTATIONS"] = (
            "asyncio,threading,system-metrics,psutil,aiohttp-client,runtime-metrics"
        )

    # Set default propagators if not specified
    if not os.getenv("OTEL_PROPAGATORS"):
        os.environ["OTEL_PROPAGATORS"] = "tracecontext,baggage"

    # Set default resource attributes for Kubernetes environments
    if os.getenv("KUBERNETES_SERVICE_HOST") and not os.getenv("OTEL_RESOURCE_ATTRIBUTES"):
        k8s_attrs = []

        # Pod information
        if os.getenv("HOSTNAME"):
            k8s_attrs.append(f"k8s.pod.name={os.getenv('HOSTNAME')}")
        if os.getenv("K8S_NAMESPACE"):
            k8s_attrs.append(f"k8s.namespace.name={os.getenv('K8S_NAMESPACE')}")
        if os.getenv("K8S_CLUSTER_NAME"):
            k8s_attrs.append(f"k8s.cluster.name={os.getenv('K8S_CLUSTER_NAME')}")
        if os.getenv("K8S_DEPLOYMENT_NAME"):
            k8s_attrs.append(f"k8s.deployment.name={os.getenv('K8S_DEPLOYMENT_NAME')}")
        if os.getenv("ENVIRONMENT"):
            k8s_attrs.append(f"deployment.environment={os.getenv('ENVIRONMENT')}")

        if k8s_attrs:
            os.environ["OTEL_RESOURCE_ATTRIBUTES"] = ",".join(k8s_attrs)


# Call initialization immediately when module is imported
init_otel_early()

# Now import and initialize the telemetry manager
try:
    from utils.telemetry import initialize_telemetry

    def setup_telemetry(service_name: Optional[str] = None, environment: Optional[str] = None) -> bool:
        """
        Setup OpenTelemetry for the application.

        Args:
            service_name: Override service name
            environment: Environment (production, staging, development)

        Returns:
            True if setup successful, False otherwise
        """
        # Get environment from various sources
        if not environment:
            environment = (
                os.getenv("ENVIRONMENT")
                or os.getenv("DEPLOYMENT_ENVIRONMENT")
                or os.getenv("K8S_ENVIRONMENT")
                or "development"
            )

        return initialize_telemetry(service_name=service_name, environment=environment)

except ImportError as e:
    logging.warning("Could not import telemetry manager: %s", e)

    def setup_telemetry(service_name: Optional[str] = None, environment: Optional[str] = None) -> bool:
        """Fallback function when telemetry is not available."""
        # Unused parameters for API compatibility
        _ = service_name, environment
        logging.info("OpenTelemetry not available, skipping telemetry setup")
        return False
