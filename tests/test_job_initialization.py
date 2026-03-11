import os
import sys
from unittest.mock import patch
import importlib
import pytest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

@pytest.fixture
def clean_env():
    """Temporarily clear OTEL_NO_AUTO_INIT to test initialization logic."""
    old_val = os.environ.get("OTEL_NO_AUTO_INIT")
    if "OTEL_NO_AUTO_INIT" in os.environ:
        del os.environ["OTEL_NO_AUTO_INIT"]
    yield
    if old_val is not None:
        os.environ["OTEL_NO_AUTO_INIT"] = old_val

@pytest.mark.parametrize("job_module_name", [
    "jobs.extract_funding",
    "jobs.extract_trades",
    "jobs.extract_klines",
    "jobs.extract_klines_production",
    "jobs.extract_klines_data_manager"
])
def test_job_telemetry_initialization(clean_env, job_module_name):
    """Verify that each job initializes telemetry correctly when not explicitly disabled."""
    # Mock petrosa_otel before importing/reloading the job module
    with patch("petrosa_otel.setup_telemetry") as mock_setup:
        # Reload the module to trigger the top-level code
        if job_module_name in sys.modules:
            module = sys.modules[job_module_name]
            importlib.reload(module)
        else:
            importlib.import_module(job_module_name)
        
        # Verify setup_telemetry was called
        assert mock_setup.called, f"setup_telemetry not called in {job_module_name}"
        
        # Check specific arguments
        args, kwargs = mock_setup.call_args
        assert kwargs.get("auto_attach_logging") is True
        assert "otlp_endpoint" in kwargs
        assert "protocol" in kwargs
        assert kwargs.get("protocol") == "grpc"
