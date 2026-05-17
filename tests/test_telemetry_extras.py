"""
Additional coverage for utils/telemetry.py aliases + flush + edge branches.
Existing test_telemetry.py covers the core TelemetryManager surface; this
hits the module-level convenience functions and defensive code paths.
"""

from unittest.mock import MagicMock, patch

import pytest

import utils.telemetry as tel


class TestModuleLevelAliases:
    def test_get_tracer_simple_delegates_to_get_tracer(self):
        with patch("utils.telemetry.get_tracer") as gt:
            gt.return_value = "tracer"
            assert tel.get_tracer_simple("svc") == "tracer"
            gt.assert_called_once_with("svc")

    def test_get_tracer_module_delegates_to_get_tracer(self):
        with patch("utils.telemetry.get_tracer") as gt:
            gt.return_value = "tracer-m"
            assert tel.get_tracer_module("svc") == "tracer-m"

    def test_get_meter_module_delegates_to_get_meter(self):
        with patch("utils.telemetry.get_meter") as gm:
            gm.return_value = "meter-m"
            assert tel.get_meter_module("svc") == "meter-m"

    def test_get_tracer_simple_module_delegates(self):
        with patch("utils.telemetry.get_tracer_simple") as gts:
            gts.return_value = "tracer-sm"
            assert tel.get_tracer_simple_module("svc") == "tracer-sm"


class TestModuleLevelGetTracer:
    def test_returns_none_when_otel_unavailable(self):
        with patch.object(tel, "OTEL_AVAILABLE", False):
            assert tel.get_tracer("anything") is None

    def test_returns_none_when_trace_module_is_none(self):
        with patch.object(tel, "trace", None):
            assert tel.get_tracer("anything") is None

    def test_logs_warning_when_get_tracer_raises(self):
        mock_trace = MagicMock()
        mock_trace.get_tracer.side_effect = RuntimeError("boom")
        with patch.object(tel, "trace", mock_trace):
            assert tel.get_tracer("svc") is None


class TestModuleLevelGetMeter:
    def test_returns_none_when_otel_unavailable(self):
        with patch.object(tel, "OTEL_AVAILABLE", False):
            assert tel.get_meter("anything") is None

    def test_returns_none_when_metrics_module_is_none(self):
        with patch.object(tel, "metrics", None):
            assert tel.get_meter("anything") is None

    def test_logs_warning_when_get_meter_raises(self):
        mock_metrics = MagicMock()
        mock_metrics.get_meter.side_effect = RuntimeError("boom")
        with patch.object(tel, "metrics", mock_metrics):
            assert tel.get_meter("svc") is None


class TestFlushTelemetry:
    def test_no_op_when_otel_unavailable(self):
        # Must return None and not raise.
        with patch.object(tel, "OTEL_AVAILABLE", False):
            assert tel.flush_telemetry() is None

    def test_calls_tracer_provider_force_flush(self):
        with patch.object(tel, "OTEL_AVAILABLE", True):
            mock_tp = MagicMock()
            mock_trace = MagicMock()
            mock_trace.get_tracer_provider.return_value = mock_tp
            with patch.object(tel, "trace", mock_trace):
                tel.flush_telemetry(timeout_ms=1000)
                mock_tp.force_flush.assert_called_once_with(timeout_millis=1000)

    def test_swallows_tracer_provider_flush_errors(self):
        with patch.object(tel, "OTEL_AVAILABLE", True):
            mock_tp = MagicMock()
            mock_tp.force_flush.side_effect = RuntimeError("flush failed")
            mock_trace = MagicMock()
            mock_trace.get_tracer_provider.return_value = mock_tp
            with patch.object(tel, "trace", mock_trace):
                # Must not raise — exceptions are collected and logged.
                result = tel.flush_telemetry()
                assert result is None
            mock_tp.force_flush.assert_called_once()


class TestParseHeaders:
    def test_empty_string_returns_empty_dict(self):
        m = tel.TelemetryManager()
        assert m._parse_headers("") == {}

    def test_none_returns_empty_dict(self):
        m = tel.TelemetryManager()
        assert m._parse_headers(None) == {}

    def test_single_header(self):
        m = tel.TelemetryManager()
        assert m._parse_headers("x-api-key=secret") == {"x-api-key": "secret"}

    def test_multiple_headers_with_whitespace(self):
        m = tel.TelemetryManager()
        headers = m._parse_headers("authorization=Bearer abc, x-trace=42")
        assert headers == {"authorization": "Bearer abc", "x-trace": "42"}

    def test_malformed_entries_are_skipped(self):
        m = tel.TelemetryManager()
        # Entry without "=" must be ignored, not raise.
        headers = m._parse_headers("good=1, bad-entry, another=2")
        assert headers == {"good": "1", "another": "2"}


class TestInitializeTelemetryHelper:
    def test_module_level_initialize_calls_manager(self):
        with patch("utils.telemetry.TelemetryManager") as M:
            instance = M.return_value
            instance.initialize_telemetry.return_value = True
            assert tel.initialize_telemetry(service_name="svc") is True
            instance.initialize_telemetry.assert_called_once_with(service_name="svc")
