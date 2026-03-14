"""
Tests for telemetry shims and Kubernetes manifest validation.
"""

import os
import sys
from unittest.mock import Mock, call, patch

import pytest
import yaml

# Add project root to path
# We need both the subproject root and the workspace root
subproject_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, subproject_root)

from utils import telemetry  # noqa: E402


def test_mock_constants_fallback():
    """Verify _MockConstants fallback when real constants module is absent."""
    # The class is defined in utils.telemetry
    from utils.telemetry import _MockConstants

    mock = _MockConstants()
    assert hasattr(mock, "OTEL_EXPORTER_OTLP_ENDPOINT")
    assert mock.OTEL_EXPORTER_OTLP_ENDPOINT == ""
    assert hasattr(mock, "OTEL_RESOURCE_ATTRIBUTES")
    assert mock.OTEL_RESOURCE_ATTRIBUTES == ""


def test_setup_metrics_no_op_awareness():
    """Assert TelemetryManager()._setup_metrics returns None."""
    manager = telemetry.TelemetryManager()
    assert manager._setup_metrics(Mock()) is None


@pytest.mark.skip(reason="Manifests moved to petrosa_k8s monorepo")
def test_k8s_manifest_resources():
    """Assert m15 CronJob container limits are 1Gi / 800m."""
    manifests = [
        "k8s/klines-data-manager-production.yaml",
        "k8s/klines-mongodb-production.yaml",
        "k8s/klines-all-timeframes-cronjobs.yaml",
    ]

    # All listed manifests are required for this test; fail fast if any are missing.
    missing_manifests = [
        manifest_path
        for manifest_path in manifests
        if not os.path.exists(os.path.join(subproject_root, manifest_path))
    ]
    assert (
        not missing_manifests
    ), f"Expected Kubernetes manifest files are missing: {missing_manifests}"

    for manifest_path in manifests:
        full_path = os.path.join(subproject_root, manifest_path)
        with open(full_path) as f:
            docs = list(yaml.safe_load_all(f))

        m15_found = False
        for doc in docs:
            if not doc or doc.get("kind") != "CronJob":
                continue
            if "m15" in doc["metadata"]["name"]:
                m15_found = True
                container = doc["spec"]["jobTemplate"]["spec"]["template"]["spec"][
                    "containers"
                ][0]
                resources = container["resources"]
                assert (
                    resources["requests"]["memory"] == "512Mi"
                ), f"Wrong memory request in {manifest_path}"
                assert (
                    resources["requests"]["cpu"] == "300m"
                ), f"Wrong cpu request in {manifest_path}"
                assert (
                    resources["limits"]["memory"] == "1Gi"
                ), f"Wrong memory limit in {manifest_path}"
                assert (
                    resources["limits"]["cpu"] == "800m"
                ), f"Wrong cpu limit in {manifest_path}"
        assert m15_found, f"m15 CronJob not found in {manifest_path}"


@pytest.mark.skip(reason="Manifests moved to petrosa_k8s monorepo")
def test_k8s_manifest_no_duplicate_env():
    """Assert no duplicate env.name keys per container in all k8s/*.yaml files."""
    k8s_dir = os.path.join(subproject_root, "k8s")
    for filename in os.listdir(k8s_dir):
        if not filename.endswith(".yaml"):
            continue

        full_path = os.path.join(k8s_dir, filename)
        with open(full_path) as f:
            try:
                docs = list(yaml.safe_load_all(f))
            except yaml.YAMLError:
                continue

        for doc in docs:
            if not doc or "spec" not in doc:
                continue

            # Helper to check containers
            def check_containers(containers, source_file):
                for container in containers:
                    if "env" in container:
                        env_names = [e["name"] for e in container["env"] if "name" in e]
                        duplicates = [
                            name for name in env_names if env_names.count(name) > 1
                        ]
                        assert not duplicates, f"Duplicate env vars {set(duplicates)} in {source_file}, container {container['name']}"

            # Check PodSpec
            if doc["kind"] == "CronJob":
                check_containers(
                    doc["spec"]["jobTemplate"]["spec"]["template"]["spec"][
                        "containers"
                    ],
                    filename,
                )
            elif doc["kind"] in ["Deployment", "StatefulSet", "Job"]:
                check_containers(
                    doc["spec"]["template"]["spec"]["containers"], filename
                )
            elif doc["kind"] == "Pod":
                check_containers(doc["spec"]["containers"], filename)


def test_console_exporter_guard():
    """Verify ConsoleSpanExporter is only added when OTEL_CONSOLE_EXPORTER is true."""
    manager = telemetry.TelemetryManager()
    with patch("utils.telemetry.OTEL_AVAILABLE", True):
        with patch("utils.telemetry.ConsoleSpanExporter") as mock_console_cls:
            with patch("utils.telemetry.TracerProvider") as mock_tp_cls:
                mock_tp = Mock()
                mock_tp_cls.return_value = mock_tp

                # Test with false
                with patch.dict(os.environ, {"OTEL_CONSOLE_EXPORTER": "false"}):
                    manager._setup_tracing(Mock())
                    mock_console_cls.assert_not_called()

                # Test with true
                with patch.dict(os.environ, {"OTEL_CONSOLE_EXPORTER": "true"}):
                    manager._setup_tracing(Mock())
                    mock_console_cls.assert_called()


def test_optional_instrumentors_debug_logging():
    """Verify optional instrumentors use debug logging for failures."""
    manager = telemetry.TelemetryManager()
    with patch("utils.telemetry.OTEL_AVAILABLE", True):
        # Mock an instrumentor to fail
        mock_instr = Mock()
        mock_instr.return_value.instrument.side_effect = Exception(
            "Instrumentation failed"
        )

        with patch("utils.telemetry.RequestsInstrumentor", mock_instr):
            with patch.object(manager.logger, "debug") as mock_debug:
                manager._setup_auto_instrumentation()
                # Verify debug was called with "Skipped optional Requests instrumentor"
                debug_calls = [
                    c.args[0] if c.args else "" for c in mock_debug.call_args_list
                ]
                assert any(
                    "Skipped optional Requests instrumentor" in str(msg)
                    for msg in debug_calls
                )
