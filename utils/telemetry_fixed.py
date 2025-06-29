"""
OpenTelemetry initialization and configuration for the Binance data extractor.

This module provides comprehensive auto-instrumentation setup for observability
with New Relic and other OTLP-compatible backends.
"""

import logging
import os
from typing import Dict, Optional, Union, Any

import constants

# OpenTelemetry Core
try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
    from opentelemetry.semconv.resource import ResourceAttributes
    
    # Exporters
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    
    # Auto-instrumentation
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    
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
            AwsEcsResourceDetector,
            AwsEc2ResourceDetector, 
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
    
    def initialize_telemetry(self, 
                           service_name: Optional[str] = None,
                           service_version: Optional[str] = None,
                           environment: Optional[str] = None,
                           enable_auto_instrumentation: bool = True) -> bool:
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
                    "service_version": service_version or constants.OTEL_SERVICE_VERSION,
                    "environment": environment or os.getenv('ENVIRONMENT', 'unknown'),
                    "otel_endpoint": constants.OTEL_EXPORTER_OTLP_ENDPOINT or "default",
                    "auto_instrumentation": enable_auto_instrumentation
                }
            )
            return True
            
        except ImportError as e:
            self.logger.error("Failed to initialize OpenTelemetry: %s", str(e), exc_info=True)
            return False
    
    def _create_resource(self, 
                        service_name: Optional[str] = None,
                        service_version: Optional[str] = None,
                        environment: Optional[str] = None) -> Resource:
        """Create OpenTelemetry resource with auto-detection."""
        
        # Base attributes
        attributes: Dict[str, Union[str, bool, int, float]] = {
            SERVICE_NAME: service_name or constants.OTEL_SERVICE_NAME,
            SERVICE_VERSION: service_version or constants.OTEL_SERVICE_VERSION,
            ResourceAttributes.SERVICE_INSTANCE_ID: os.getenv('HOSTNAME', 'unknown'),
        }
        
        # Add environment if provided
        if environment:
            attributes[ResourceAttributes.DEPLOYMENT_ENVIRONMENT] = environment
        elif os.getenv('ENVIRONMENT'):
            env_val = os.getenv('ENVIRONMENT')
            if env_val:
                attributes[ResourceAttributes.DEPLOYMENT_ENVIRONMENT] = env_val
            
        # Add Kubernetes attributes if available
        if os.getenv('KUBERNETES_SERVICE_HOST'):
            attributes.update({
                ResourceAttributes.K8S_CLUSTER_NAME: os.getenv('K8S_CLUSTER_NAME', 'unknown'),
                ResourceAttributes.K8S_NAMESPACE_NAME: os.getenv('K8S_NAMESPACE', 'default'),
                ResourceAttributes.K8S_POD_NAME: os.getenv('K8S_POD_NAME', os.getenv('HOSTNAME', 'unknown')),
                ResourceAttributes.K8S_CONTAINER_NAME: os.getenv('K8S_CONTAINER_NAME', 'binance-extractor'),
                ResourceAttributes.K8S_DEPLOYMENT_NAME: os.getenv('K8S_DEPLOYMENT_NAME', 'binance-extractor'),
            })
            
        # Add custom resource attributes from environment
        if constants.OTEL_RESOURCE_ATTRIBUTES:
            custom_attrs = {}
            for pair in constants.OTEL_RESOURCE_ATTRIBUTES.split(','):
                if '=' in pair:
                    key, value = pair.split('=', 1)
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
                detectors.extend([
                    AwsEcsResourceDetector(),
                    AwsEc2ResourceDetector(),
                    AwsEksResourceDetector(),
                    AwsLambdaResourceDetector(),
                ])
            except ImportError:
                self.logger.debug("AWS resource detectors not available")
            
        resource = Resource.create(attributes)
        
        # Merge with detected resources
        for detector in detectors:
            try:
                detected_resource = detector.detect()
                resource = resource.merge(detected_resource)
            except ImportError as e:
                self.logger.debug("Resource detection failed for %s: %s", detector, str(e))
                
        return resource
    
    def _setup_tracing(self, resource: Resource):
        """Setup tracing with OTLP exporter."""
        # Create tracer provider
        self.tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(self.tracer_provider)
        
        # Setup OTLP span exporter
        if constants.OTEL_EXPORTER_OTLP_ENDPOINT:
            headers = self._parse_headers(constants.OTEL_EXPORTER_OTLP_HEADERS or "")
            
            otlp_exporter = OTLPSpanExporter(
                endpoint=constants.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT or constants.OTEL_EXPORTER_OTLP_ENDPOINT,
                headers=headers,
                insecure=not constants.OTEL_EXPORTER_OTLP_ENDPOINT.startswith('https://') if constants.OTEL_EXPORTER_OTLP_ENDPOINT else True
            )
            
            # Add batch span processor
            span_processor = BatchSpanProcessor(otlp_exporter)
            self.tracer_provider.add_span_processor(span_processor)
            
            self.logger.debug("OTLP span exporter configured: %s", constants.OTEL_EXPORTER_OTLP_ENDPOINT)
    
    def _setup_metrics(self, resource: Resource):
        """Setup metrics with OTLP exporter."""
        if not constants.OTEL_EXPORTER_OTLP_ENDPOINT:
            return
            
        # Setup OTLP metric exporter
        headers = self._parse_headers(constants.OTEL_EXPORTER_OTLP_HEADERS or "")
        
        otlp_metric_exporter = OTLPMetricExporter(
            endpoint=constants.OTEL_EXPORTER_OTLP_METRICS_ENDPOINT or constants.OTEL_EXPORTER_OTLP_ENDPOINT,
            headers=headers,
            insecure=not constants.OTEL_EXPORTER_OTLP_ENDPOINT.startswith('https://') if constants.OTEL_EXPORTER_OTLP_ENDPOINT else True
        )
        
        # Create metric reader
        metric_reader = PeriodicExportingMetricReader(
            exporter=otlp_metric_exporter,
            export_interval_millis=30000  # 30 seconds
        )
        
        # Create meter provider
        self.meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader]
        )
        metrics.set_meter_provider(self.meter_provider)
        
        self.logger.debug("OTLP metric exporter configured: %s", constants.OTEL_EXPORTER_OTLP_ENDPOINT)
    
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
        
        self.logger.info("Auto-instrumentation enabled for: %s", ", ".join(instrumentors))
    
    def _parse_headers(self, headers_str: str) -> Dict[str, str]:
        """Parse OTLP headers string into dictionary."""
        headers = {}
        if headers_str:
            for header in headers_str.split(','):
                if '=' in header:
                    key, value = header.split('=', 1)
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
