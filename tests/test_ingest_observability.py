"""Tests for the bounded ingest observability contract."""

from unittest.mock import Mock, patch

from utils.ingest_observability import (
    INGEST_EVENT_LABELS,
    INGEST_LATENCY_LABELS,
    IngestObservability,
)


def fake_meter() -> Mock:
    meter = Mock()
    meter.create_counter.return_value = Mock()
    meter.create_histogram.return_value = Mock()
    return meter


def test_metric_names_and_allowlisted_labels() -> None:
    meter = fake_meter()
    with patch("utils.ingest_observability.get_meter", return_value=meter):
        IngestObservability()

    assert (
        meter.create_counter.call_args.kwargs["name"] == "petrosa_ingest_events_total"
    )
    assert (
        meter.create_histogram.call_args.kwargs["name"]
        == "petrosa_ingest_latency_seconds"
    )
    assert INGEST_EVENT_LABELS == ("source", "outcome", "interval")
    assert INGEST_LATENCY_LABELS == ("source", "interval")


def test_event_uses_only_bounded_labels_and_summary_shape() -> None:
    meter = fake_meter()
    with patch("utils.ingest_observability.get_meter", return_value=meter):
        observability = IngestObservability()
        observability.record_event(
            source="binance", outcome="success", interval="1m", latency_seconds=0.018
        )
        summary = observability.shutdown()

    assert summary is not None
    assert summary["event"] == "SUMMARY"
    assert summary["window_seconds"] == 300
    assert summary["service"] == "petrosa-binance-data-extractor"
    assert summary["outcomes"] == {"success": 1}
    assert set(meter.create_counter.return_value.add.call_args.args[1]) == set(
        INGEST_EVENT_LABELS
    )
    assert set(meter.create_histogram.return_value.record.call_args.args[1]) == set(
        INGEST_LATENCY_LABELS
    )
