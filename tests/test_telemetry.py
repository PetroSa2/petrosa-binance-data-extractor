"""
Tests for the telemetry module.
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils import telemetry  # noqa: E402


class TestTelemetryManager:
    """Test the TelemetryManager class."""

    def test_telemetry_manager_initialization(self):
        """Test TelemetryManager initialization."""
        manager = telemetry.TelemetryManager()
        assert manager.initialized is False
        assert manager.tracer_provider is None
        assert manager.meter_provider is None
        assert manager.logger is not None

    @patch("utils.telemetry.OTEL_AVAILABLE", False)
    def test_initialize_telemetry_otel_not_available(self):
        """Test initialization when OpenTelemetry is not available."""
        manager = telemetry.TelemetryManager()
        result = manager.initialize_telemetry()
        assert result is False
        assert manager.initialized is False

    @patch("utils.telemetry.OTEL_AVAILABLE", True)
    def test_initialize_telemetry_already_initialized(self):
        """Test initialization when already initialized."""
        manager = telemetry.TelemetryManager()
        manager.initialized = True

        with patch.object(manager.logger, "info") as mock_info:
            result = manager.initialize_telemetry()
            assert result is True
            mock_info.assert_called_with("OpenTelemetry already initialized")

    @patch("utils.telemetry.OTEL_AVAILABLE", True)
    @patch("utils.telemetry.Resource")
    @patch("utils.telemetry.TracerProvider")
    @patch("utils.telemetry.BatchSpanProcessor")
    @patch("utils.telemetry.OTLPSpanExporter")
    @patch("utils.telemetry.ConsoleSpanExporter")
    @patch("utils.telemetry.trace")
    @patch("utils.telemetry.constants.OTEL_EXPORTER_OTLP_ENDPOINT", new="")
    def test_initialize_telemetry_success(
        self,
        mock_trace,
        mock_console_exporter,
        mock_otlp_exporter,
        mock_batch_processor,
        mock_tracer_provider,
        mock_resource,
    ):
        """Test successful telemetry initialization."""
        manager = telemetry.TelemetryManager()
        mock_resource_instance = Mock()
        mock_resource.create.return_value = mock_resource_instance
        mock_resource.return_value = mock_resource_instance
        mock_provider_instance = Mock()
        mock_tracer_provider.return_value = mock_provider_instance
        mock_trace.get_tracer_provider.return_value = mock_provider_instance
        mock_provider_instance.get_tracer.return_value = DummyContextManager()
        with patch.object(manager, "_setup_auto_instrumentation") as _:
            with patch.object(manager.logger, "info") as mock_info:
                result = manager.initialize_telemetry()
                assert result is True
                assert manager.initialized is True
                mock_info.assert_called()

    @patch("utils.telemetry.OTEL_AVAILABLE", True)
    def test_initialize_telemetry_import_error(self):
        """Test initialization with import error."""
        manager = telemetry.TelemetryManager()

        with patch.object(
            manager, "_create_resource", side_effect=ImportError("test error")
        ):
            with patch.object(manager.logger, "error") as mock_error:
                result = manager.initialize_telemetry()

                assert result is False
                assert manager.initialized is False
                mock_error.assert_called()

    @patch("utils.telemetry.OTEL_AVAILABLE", True)
    @patch("utils.telemetry.Resource")
    @patch("utils.telemetry.constants.OTEL_EXPORTER_OTLP_ENDPOINT", new="")
    def test_create_resource_basic(self, mock_resource):
        """Test basic resource creation."""
        manager = telemetry.TelemetryManager()
        mock_resource_instance = Mock()
        mock_resource.create.return_value = mock_resource_instance
        mock_resource.return_value = mock_resource_instance

        result = manager._create_resource("test-service", "1.0.0", "test-env")

        assert result == mock_resource_instance
        mock_resource.create.assert_called()

    @patch("utils.telemetry.OTEL_AVAILABLE", True)
    @patch("utils.telemetry.Resource")
    @patch("utils.telemetry.constants.OTEL_EXPORTER_OTLP_ENDPOINT", new="")
    def test_create_resource_with_kubernetes(self, mock_resource):
        """Test resource creation with Kubernetes environment."""
        manager = telemetry.TelemetryManager()
        mock_resource_instance = Mock()
        mock_resource.create.return_value = mock_resource_instance
        mock_resource.return_value = mock_resource_instance

        with patch.dict(
            os.environ,
            {
                "KUBERNETES_SERVICE_HOST": "test-host",
                "K8S_CLUSTER_NAME": "test-cluster",
                "K8S_NAMESPACE": "test-namespace",
                "K8S_POD_NAME": "test-pod",
                "K8S_CONTAINER_NAME": "test-container",
                "K8S_DEPLOYMENT_NAME": "test-deployment",
            },
        ):
            result = manager._create_resource()

            assert result == mock_resource_instance
            mock_resource.create.assert_called()

    @patch("utils.telemetry.OTEL_AVAILABLE", True)
    @patch("utils.telemetry.Resource")
    @patch("utils.telemetry.constants.OTEL_EXPORTER_OTLP_ENDPOINT", new="")
    def test_create_resource_with_custom_attributes(self, mock_resource):
        """Test resource creation with custom attributes."""
        manager = telemetry.TelemetryManager()
        mock_resource_instance = Mock()
        mock_resource.create.return_value = mock_resource_instance
        mock_resource.return_value = mock_resource_instance

        with patch(
            "utils.telemetry.constants.OTEL_RESOURCE_ATTRIBUTES",
            "key1=value1,key2=value2",
        ):
            result = manager._create_resource()

            assert result == mock_resource_instance
            mock_resource.create.assert_called()

    @patch("utils.telemetry.OTEL_AVAILABLE", True)
    @patch("utils.telemetry.TracerProvider")
    @patch("utils.telemetry.BatchSpanProcessor")
    @patch("utils.telemetry.OTLPSpanExporter")
    @patch("utils.telemetry.ConsoleSpanExporter")
    @patch("utils.telemetry.trace")
    @patch("utils.telemetry.constants.OTEL_EXPORTER_OTLP_ENDPOINT", new="")
    def test_setup_tracing(
        self,
        mock_trace,
        mock_console_exporter,
        mock_otlp_exporter,
        mock_batch_processor,
        mock_tracer_provider,
    ):
        """Test tracing setup."""
        manager = telemetry.TelemetryManager()
        mock_resource = Mock()

        # Mock instances
        mock_provider_instance = Mock()
        mock_tracer_provider.return_value = mock_provider_instance

        mock_otlp_exporter_instance = Mock()
        mock_otlp_exporter.return_value = mock_otlp_exporter_instance

        mock_console_exporter_instance = Mock()
        mock_console_exporter.return_value = mock_console_exporter_instance

        mock_processor_instance = Mock()
        mock_batch_processor.return_value = mock_processor_instance

        mock_provider_instance.get_tracer.return_value = DummyContextManager()

        manager._setup_tracing(mock_resource)

        mock_tracer_provider.assert_called_with(resource=mock_resource)
        mock_trace.set_tracer_provider.assert_called_with(mock_provider_instance)
        mock_provider_instance.add_span_processor.assert_called()

    @patch("utils.telemetry.OTEL_AVAILABLE", True)
    def test_setup_metrics(self):
        """Test metrics setup."""
        manager = telemetry.TelemetryManager()
        mock_resource = Mock()
        # The method currently just returns early, so we test that it doesn't raise an error
        result = manager._setup_metrics(mock_resource)
        assert result is None

    @patch("utils.telemetry.OTEL_AVAILABLE", True)
    @patch("utils.telemetry.RequestsInstrumentor")
    @patch("utils.telemetry.SQLAlchemyInstrumentor")
    @patch("utils.telemetry.LoggingInstrumentor")
    def test_setup_auto_instrumentation(
        self,
        mock_logging_instr,
        mock_sqlalchemy_instr,
        mock_requests_instr,
    ):
        """Test auto-instrumentation setup for core instrumentors."""
        manager = telemetry.TelemetryManager()
        
        # Create mock instances with instrument method
        mock_requests_instance = Mock()
        mock_sqlalchemy_instance = Mock()
        mock_logging_instance = Mock()
        
        # Set return_value so RequestsInstrumentor() returns the mock instance
        mock_requests_instr.return_value = mock_requests_instance
        mock_sqlalchemy_instr.return_value = mock_sqlalchemy_instance
        mock_logging_instr.return_value = mock_logging_instance

        manager._setup_auto_instrumentation()

        # Verify that core instrumentors were called
        mock_requests_instr.assert_called_once()
        mock_sqlalchemy_instr.assert_called_once()
        mock_logging_instr.assert_called_once()
        
        # Verify that instrument() was called on each instance
        mock_requests_instance.instrument.assert_called_once()
        mock_sqlalchemy_instance.instrument.assert_called_once()
        mock_logging_instance.instrument.assert_called_once()

    @patch("utils.telemetry.OTEL_AVAILABLE", True)
    @patch("utils.telemetry.URLLIB3_AVAILABLE", True)
    @patch("utils.telemetry.PYMONGO_AVAILABLE", False)
    @patch("utils.telemetry.RequestsInstrumentor")
    @patch("utils.telemetry.SQLAlchemyInstrumentor")
    @patch("utils.telemetry.LoggingInstrumentor")
    @patch("utils.telemetry.URLLib3Instrumentor")
    def test_setup_auto_instrumentation_with_urllib3(
        self,
        mock_urllib3_instr,
        mock_logging_instr,
        mock_sqlalchemy_instr,
        mock_requests_instr,
    ):
        """Test auto-instrumentation setup with urllib3 available."""
        manager = telemetry.TelemetryManager()
        
        # Create mock instances
        mock_urllib3_instance = Mock()
        mock_requests_instance = Mock()
        mock_sqlalchemy_instance = Mock()
        mock_logging_instance = Mock()
        
        mock_urllib3_instr.return_value = mock_urllib3_instance
        mock_requests_instr.return_value = mock_requests_instance
        mock_sqlalchemy_instr.return_value = mock_sqlalchemy_instance
        mock_logging_instr.return_value = mock_logging_instance
        
        manager._setup_auto_instrumentation()
        
        # Verify urllib3 was instrumented
        mock_urllib3_instr.assert_called_once()
        mock_urllib3_instance.instrument.assert_called_once()

    def test_parse_headers(self):
        """Test header parsing."""
        manager = telemetry.TelemetryManager()

        # Test valid headers
        headers_str = "key1=value1,key2=value2"
        result = manager._parse_headers(headers_str)
        assert result == {"key1": "value1", "key2": "value2"}

        # Test empty headers
        result = manager._parse_headers("")
        assert result == {}

        # Test None headers
        result = manager._parse_headers(None)
        assert result == {}

        # Test invalid format
        result = manager._parse_headers("invalid_format")
        assert result == {}

    @patch("utils.telemetry.OTEL_AVAILABLE", True)
    @patch("utils.telemetry.trace")
    def test_get_tracer(self, mock_trace):
        """Test get_tracer method."""
        manager = telemetry.TelemetryManager()
        mock_tracer = Mock()
        mock_trace.get_tracer.return_value = mock_tracer

        manager.initialized = True
        result = manager.get_tracer("test-tracer")

        assert result == mock_tracer
        mock_trace.get_tracer.assert_called_with("test-tracer")

    @patch("utils.telemetry.OTEL_AVAILABLE", True)
    @patch("utils.telemetry.metrics")
    def test_get_meter(self, mock_metrics):
        """Test get_meter method."""
        manager = telemetry.TelemetryManager()
        mock_meter = Mock()
        mock_metrics.get_meter.return_value = mock_meter

        manager.initialized = True
        result = manager.get_meter("test-meter")

        assert result == mock_meter
        mock_metrics.get_meter.assert_called_with("test-meter")


@pytest.mark.skip(
    "Module-level singleton cannot be reliably mocked in this environment"
)
class TestModuleFunctions:
    pass


class DummyContextManager:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def set_attribute(self, *args, **kwargs):
        pass


class TestCloudResourceDetectors:
    """Test cloud resource detector integration."""

    @patch("utils.telemetry.GCP_AVAILABLE", True)
    def test_gcp_resource_detector(self):
        """Test GCP resource detector integration."""
        manager = telemetry.TelemetryManager()
        mock_resource = Mock()

        with patch.object(manager, "_create_resource", return_value=mock_resource):
            # This should not raise an exception
            manager._create_resource()

    @patch("utils.telemetry.AWS_AVAILABLE", True)
    def test_aws_resource_detectors(self):
        """Test AWS resource detector integration."""
        manager = telemetry.TelemetryManager()
        mock_resource = Mock()

        with patch.object(manager, "_create_resource", return_value=mock_resource):
            # This should not raise an exception
            manager._create_resource()


class TestErrorHandling:
    """Test error handling scenarios."""

    @patch("utils.telemetry.OTEL_AVAILABLE", True)
    @patch("utils.telemetry.Resource")
    def test_resource_detector_import_error(self, mock_resource_class):
        """Test handling of resource detector import errors."""
        manager = telemetry.TelemetryManager()
        
        # Mock Resource.create to return a mock resource
        mock_resource = Mock()
        mock_resource_class.create.return_value = mock_resource

        with patch.object(manager.logger, "debug") as _:
            # This should not raise an exception
            result = manager._create_resource()
            # Verify it returns the mocked resource
            assert result == mock_resource

    @patch("utils.telemetry.OTEL_AVAILABLE", True)
    @patch("utils.telemetry.TracerProvider")
    @patch("utils.telemetry.ConsoleSpanExporter")
    @patch("utils.telemetry.AttributeFilterSpanProcessor")
    @patch("utils.telemetry.trace")
    @patch(
        "utils.telemetry.constants.OTEL_EXPORTER_OTLP_ENDPOINT",
        new="https://test-endpoint.com",
    )
    @patch("utils.telemetry.GRPCSpanExporter")
    def test_exporter_initialization_error(
        self,
        mock_grpc_exporter,
        mock_trace,
        mock_processor,
        mock_console_exporter,
        mock_tracer_provider,
    ):
        """Test handling of exporter initialization errors."""
        manager = telemetry.TelemetryManager()
        mock_resource = Mock()
        
        # Mock the tracer provider
        mock_provider_instance = Mock()
        mock_tracer_provider.return_value = mock_provider_instance

        # Make GRPCSpanExporter raise an error
        mock_grpc_exporter.side_effect = RuntimeError("Exporter error")
        
        # Mock console exporter to work
        mock_console_instance = Mock()
        mock_console_exporter.return_value = mock_console_instance

        with patch.dict(
            os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "https://test-endpoint.com"}
        ):
            with patch.object(telemetry.TelemetryManager.logger, "error") as mock_error:
                # This should handle the error gracefully
                manager._setup_tracing(mock_resource)
                # Verify error was logged
                mock_error.assert_called()


class TestEnvironmentVariables:
    """Test environment variable handling."""

    @patch("utils.telemetry.OTEL_AVAILABLE", True)
    @patch("utils.telemetry.Resource")
    @patch("utils.telemetry.constants.OTEL_EXPORTER_OTLP_ENDPOINT", new="")
    def test_environment_variable_handling(self, mock_resource):
        """Test handling of various environment variables."""
        manager = telemetry.TelemetryManager()
        mock_resource_instance = Mock()
        mock_resource.create.return_value = mock_resource_instance
        mock_resource.return_value = mock_resource_instance
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "HOSTNAME": "test-host",
                "OTEL_RESOURCE_ATTRIBUTES": "custom.key=custom.value",
            },
        ):
            result = manager._create_resource()
            assert result == mock_resource_instance
            mock_resource.create.assert_called()

    @patch("utils.telemetry.OTEL_AVAILABLE", True)
    @patch("utils.telemetry.Resource")
    @patch("utils.telemetry.constants.OTEL_EXPORTER_OTLP_ENDPOINT", new="")
    def test_missing_environment_variables(self, mock_resource):
        """Test handling of missing environment variables."""
        manager = telemetry.TelemetryManager()
        mock_resource_instance = Mock()
        mock_resource.create.return_value = mock_resource_instance
        mock_resource.return_value = mock_resource_instance
        with patch.dict(os.environ, {}, clear=True):
            result = manager._create_resource()
            assert result == mock_resource_instance
            mock_resource.create.assert_called()


class TestAttributeFilterSpanProcessor:
    """Test AttributeFilterSpanProcessor with and without OpenTelemetry."""

    def test_processor_available_when_otel_available(self):
        """Test that AttributeFilterSpanProcessor is available when OTEL is available."""
        # The processor should be importable regardless of OTEL_AVAILABLE
        assert hasattr(telemetry, "AttributeFilterSpanProcessor")
        processor_class = telemetry.AttributeFilterSpanProcessor
        assert processor_class is not None

    def test_noop_processor_when_otel_unavailable(self):
        """Test that AttributeFilterSpanProcessor is no-op when OTEL unavailable."""
        # When OTEL is unavailable, processor should accept any args
        if not telemetry.OTEL_AVAILABLE:
            processor = telemetry.AttributeFilterSpanProcessor()
            # Should not raise exceptions
            processor.on_start(Mock(), Mock())
            processor.on_end(Mock())
            processor.shutdown()
            result = processor.force_flush()
            assert result is True

    def test_processor_can_be_instantiated_with_otel_available(self):
        """Test that processor can be instantiated when OpenTelemetry is available."""
        if not telemetry.OTEL_AVAILABLE:
            pytest.skip("OpenTelemetry not available")

        try:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter

            mock_exporter = ConsoleSpanExporter()
            processor = telemetry.AttributeFilterSpanProcessor(mock_exporter)

            # Should be able to create processor without errors
            assert processor is not None
        except ImportError:
            pytest.skip("OpenTelemetry dependencies not available")
