"""
OpenTelemetry initialization and configuration for the Binance data extractor.

This module provides comprehensive auto-instrumentation setup for observabilit        # Add cloud resource detectors
        detectors = []
        
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
                self.logger.debug("AWS resource detectors not available")ic and other OTLP-compatible backends.
"""

import logging
import os
from typing import Dict, Optional

import constants

# OpenTelemetry Core
try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
    
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
        )
        from opentelemetry.sdk.extension.aws.resource import (
            AwsLambdaResourceDetector,
        )
        AWS_AVAILABLE = True
    except ImportError:
        AWS_AVAILABLE = False
    
    # Semantic conventions
    from opentelemetry.semconv.resource import ResourceAttributes
    
    OTEL_AVAILABLE = True
except ImportError as e:
    logging.warning("OpenTelemetry not available: %s", e)
    OTEL_AVAILABLE = False


class TelemetryManager:
    """Manages OpenTelemetry initialization and instrumentation."""
    
    def __init__(self):
        self.initialized = False
        self.logger = logging.getLogger(__name__)
        
    def initialize_telemetry(self, 
                           service_name: Optional[str] = None,
                           service_version: Optional[str] = None,
                           environment: Optional[str] = None) -> bool:
        """
        Initialize OpenTelemetry with comprehensive auto-instrumentation.
        
        Args:
            service_name: Override service name
            service_version: Override service version
            environment: Environment name (production, staging, development)
            
        Returns:
            True if initialization successful, False otherwise
        """
        if not OTEL_AVAILABLE:
            self.logger.warning("OpenTelemetry not available, skipping telemetry setup")
            return False
            
        if self.initialized:
            self.logger.warning("Telemetry already initialized")
            return True
            
        if not constants.ENABLE_OTEL:
            self.logger.info("OpenTelemetry disabled via configuration")
            return False
            
        try:
            # Create resource with auto-detection
            resource = self._create_resource(service_name, service_version, environment)
            
            # Initialize tracing
            self._setup_tracing(resource)
            
            # Initialize metrics
            self._setup_metrics(resource)
            
            # Setup auto-instrumentation
            self._setup_auto_instrumentation()
            
            self.initialized = True
            self.logger.info(
                "OpenTelemetry initialized successfully",
                extra={
                    "service_name": resource.attributes.get(SERVICE_NAME),
                    "service_version": resource.attributes.get(SERVICE_VERSION),
                    "endpoint": constants.OTEL_EXPORTER_OTLP_ENDPOINT,
                }
            )
            return True
            
        except ImportError:
            self.logger.error("Failed to initialize OpenTelemetry: %s", str(e), exc_info=True)
            return False
    
    def _create_resource(self, 
                        service_name: Optional[str] = None,
                        service_version: Optional[str] = None,
                        environment: Optional[str] = None) -> Resource:
        """Create OpenTelemetry resource with auto-detection."""
        
        # Base attributes
        attributes = {
            SERVICE_NAME: service_name or constants.OTEL_SERVICE_NAME,
            SERVICE_VERSION: service_version or constants.OTEL_SERVICE_VERSION,
            ResourceAttributes.SERVICE_INSTANCE_ID: os.getenv('HOSTNAME', 'unknown'),
        }
        
        # Add environment if provided
        if environment:
            attributes[ResourceAttributes.DEPLOYMENT_ENVIRONMENT] = environment
        elif os.getenv('ENVIRONMENT'):
            attributes[ResourceAttributes.DEPLOYMENT_ENVIRONMENT] = os.getenv('ENVIRONMENT')
            
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
        try:
            detectors.extend([
                GoogleCloudResourceDetector(),
                AwsEcsResourceDetector(),
                AwsEc2ResourceDetector(),
                AwsEksResourceDetector(),
                AwsLambdaResourceDetector(),
            ])
        except Exception as e:
            self.logger.debug(f"Some resource detectors not available: {e}")
            
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
        """Setup OpenTelemetry tracing."""
        # Create tracer provider
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)
        
        # Setup OTLP exporter if endpoint is configured
        if constants.OTEL_EXPORTER_OTLP_ENDPOINT:
            headers = self._parse_headers(constants.OTEL_EXPORTER_OTLP_HEADERS)
            
            span_exporter = OTLPSpanExporter(
                endpoint=constants.OTEL_EXPORTER_OTLP_ENDPOINT,
                headers=headers,
                insecure=not constants.OTEL_EXPORTER_OTLP_ENDPOINT.startswith('https'),
            )
            
            span_processor = BatchSpanProcessor(
                span_exporter,
                max_queue_size=2048,
                max_export_batch_size=512,
                export_timeout_millis=30000,
                schedule_delay_millis=5000,
            )
            
            tracer_provider.add_span_processor(span_processor)
            self.logger.info("Tracing exporter configured: %s", constants.OTEL_EXPORTER_OTLP_ENDPOINT)
    
    def _setup_metrics(self, resource: Resource):
        """Setup OpenTelemetry metrics."""
        if not constants.OTEL_EXPORTER_OTLP_ENDPOINT:
            return
            
        headers = self._parse_headers(constants.OTEL_EXPORTER_OTLP_HEADERS)
        
        metric_exporter = OTLPMetricExporter(
            endpoint=constants.OTEL_EXPORTER_OTLP_ENDPOINT,
            headers=headers,
            insecure=not constants.OTEL_EXPORTER_OTLP_ENDPOINT.startswith('https'),
        )
        
        metric_reader = PeriodicExportingMetricReader(
            exporter=metric_exporter,
            export_interval_millis=60000,  # 60 seconds
            export_timeout_millis=30000,   # 30 seconds
        )
        
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader]
        )
        
        metrics.set_meter_provider(meter_provider)
        self.logger.info("Metrics exporter configured")
    
    def _setup_auto_instrumentation(self):
        """Setup auto-instrumentation for various libraries."""
        instrumentors = []
        
        try:
            # HTTP libraries
            RequestsInstrumentor().instrument()
            instrumentors.append("requests")
            
            if URLLIB3_AVAILABLE:
                URLLib3Instrumentor().instrument()
                instrumentors.append("urllib3")
            
        except ImportError as e:
            self.logger.warning("Failed to instrument HTTP libraries: %s", str(e))
        
        try:
            # Database libraries
            PymongoInstrumentor().instrument()
            instrumentors.append("pymongo")
            
            SQLAlchemyInstrumentor().instrument()
            instrumentors.append("sqlalchemy")
            
        except ImportError as e:
            self.logger.warning("Failed to instrument database libraries: %s", str(e))
        
        try:
            # Logging
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
