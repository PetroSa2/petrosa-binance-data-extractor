"""
Comprehensive unit tests for base Pydantic models.

Tests cover validation, serialization, field validation, error handling,
and edge cases for all base model classes.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from models.base import BaseSymbolModel, BaseTimestampedModel, ExtractionMetadata


@pytest.mark.unit
class TestBaseTimestampedModel:
    """Test cases for BaseTimestampedModel."""

    def test_initialization_with_required_fields(self):
        """Test model initialization with only required fields."""
        timestamp = datetime.now(UTC)
        model = BaseTimestampedModel(timestamp=timestamp)

        assert model.timestamp == timestamp
        assert isinstance(model.extracted_at, datetime)
        assert model.extractor_version == "1.0.0"
        assert model.source == "binance-futures"
        assert model.id is not None
        assert isinstance(model.id, str)

    def test_initialization_with_all_fields(self):
        """Test model initialization with all fields provided."""
        timestamp = datetime.now(UTC)
        extracted_at = datetime.now(UTC)
        test_id = str(uuid.uuid4())

        model = BaseTimestampedModel(
            timestamp=timestamp,
            extracted_at=extracted_at,
            extractor_version="2.0.0",
            source="test-source",
            id=test_id,
        )

        assert model.timestamp == timestamp
        assert model.extracted_at == extracted_at
        assert model.extractor_version == "2.0.0"
        assert model.source == "test-source"
        assert model.id == test_id

    @pytest.mark.parametrize(
        "timestamp_input,expected_type",
        [
            (1672531200000, datetime),  # Milliseconds timestamp
            (1672531200, datetime),  # Seconds timestamp
            ("2023-01-01T00:00:00Z", datetime),  # ISO format with Z
            ("2023-01-01T00:00:00+00:00", datetime),  # ISO format with timezone
        ],
    )
    def test_timestamp_parsing(self, timestamp_input, expected_type):
        """Test timestamp parsing from various formats."""
        model = BaseTimestampedModel(timestamp=timestamp_input)
        assert isinstance(model.timestamp, expected_type)

    def test_timestamp_parsing_milliseconds(self):
        """Test timestamp parsing from milliseconds."""
        ms_timestamp = 1672531200000  # 2023-01-01 00:00:00 UTC
        model = BaseTimestampedModel(timestamp=ms_timestamp)

        expected = datetime.utcfromtimestamp(ms_timestamp / 1000)
        assert model.timestamp == expected

    def test_timestamp_parsing_seconds(self):
        """Test timestamp parsing from seconds."""
        sec_timestamp = 1672531200  # 2023-01-01 00:00:00 UTC
        model = BaseTimestampedModel(timestamp=sec_timestamp)

        expected = datetime.utcfromtimestamp(sec_timestamp)
        assert model.timestamp == expected

    def test_timestamp_parsing_iso_string(self):
        """Test timestamp parsing from ISO string."""
        iso_string = "2023-01-01T00:00:00Z"
        model = BaseTimestampedModel(timestamp=iso_string)

        expected = datetime.fromisoformat("2023-01-01T00:00:00+00:00")
        assert model.timestamp == expected

    def test_timestamp_parsing_invalid_string(self):
        """Test timestamp parsing from invalid string falls back to float parsing."""
        # This should be parsed as a timestamp string
        timestamp_str = "1672531200"
        model = BaseTimestampedModel(timestamp=timestamp_str)

        expected = datetime.utcfromtimestamp(1672531200)
        assert model.timestamp == expected

    def test_json_serialization(self):
        """Test JSON serialization with datetime encoding."""
        timestamp = datetime(2023, 1, 1, 0, 0, 0)
        model = BaseTimestampedModel(timestamp=timestamp)

        json_str = model.model_dump_json()
        data = json.loads(json_str)

        # Check that timestamp is properly encoded
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)

    def test_model_validation_assignment(self):
        """Test that validation occurs on assignment."""
        model = BaseTimestampedModel(timestamp=datetime.now())

        # Should validate on assignment
        model.timestamp = 1672531200000
        assert isinstance(model.timestamp, datetime)

    def test_extra_fields_allowed(self):
        """Test that extra fields are allowed in the model."""
        model = BaseTimestampedModel(
            timestamp=datetime.now(), custom_field="custom_value", another_field=123
        )

        assert hasattr(model, "custom_field")
        assert model.custom_field == "custom_value"
        assert hasattr(model, "another_field")
        assert model.another_field == 123

    def test_id_generation_uniqueness(self):
        """Test that generated IDs are unique."""
        model1 = BaseTimestampedModel(timestamp=datetime.now())
        model2 = BaseTimestampedModel(timestamp=datetime.now())

        assert model1.id != model2.id
        assert len(model1.id) == 36  # UUID4 length
        assert len(model2.id) == 36

    def test_missing_required_field_raises_validation_error(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BaseTimestampedModel()

        assert "timestamp" in str(exc_info.value)

    def test_invalid_timestamp_type_raises_validation_error(self):
        """Test that invalid timestamp types raise ValidationError."""
        with pytest.raises(ValidationError):
            BaseTimestampedModel(timestamp="invalid-timestamp")


@pytest.mark.unit
class TestBaseSymbolModel:
    """Test cases for BaseSymbolModel."""

    def test_initialization_with_symbol(self):
        """Test model initialization with symbol."""
        timestamp = datetime.now(UTC)
        model = BaseSymbolModel(timestamp=timestamp, symbol="BTCUSDT")

        assert model.symbol == "BTCUSDT"
        assert model.timestamp == timestamp

    def test_symbol_uppercase_validation(self):
        """Test that symbol is converted to uppercase."""
        timestamp = datetime.now()
        model = BaseSymbolModel(timestamp=timestamp, symbol="btcusdt")

        assert model.symbol == "BTCUSDT"

    def test_symbol_empty_string_handling(self):
        """Test handling of empty symbol string."""
        timestamp = datetime.now()
        model = BaseSymbolModel(timestamp=timestamp, symbol="")

        assert model.symbol == ""

    def test_symbol_none_handling(self):
        """Test handling of None symbol (should raise validation error)."""
        timestamp = datetime.now()

        with pytest.raises(ValidationError):
            BaseSymbolModel(timestamp=timestamp, symbol=None)

    def test_inheritance_from_base_timestamped_model(self):
        """Test that BaseSymbolModel inherits from BaseTimestampedModel."""
        timestamp = datetime.now()
        model = BaseSymbolModel(timestamp=timestamp, symbol="ETHUSDT")

        # Should have all BaseTimestampedModel fields
        assert hasattr(model, "extracted_at")
        assert hasattr(model, "extractor_version")
        assert hasattr(model, "source")
        assert hasattr(model, "id")

    @pytest.mark.parametrize(
        "symbol_input,expected_output",
        [
            ("btcusdt", "BTCUSDT"),
            ("BTCUSDT", "BTCUSDT"),
            ("BtCuSdT", "BTCUSDT"),
            ("eth_usdt", "ETH_USDT"),
            ("1000SHIBUSDT", "1000SHIBUSDT"),
        ],
    )
    def test_symbol_case_conversion(self, symbol_input, expected_output):
        """Test symbol case conversion with various inputs."""
        timestamp = datetime.now()
        model = BaseSymbolModel(timestamp=timestamp, symbol=symbol_input)

        assert model.symbol == expected_output

    def test_json_serialization_includes_symbol(self):
        """Test JSON serialization includes symbol field."""
        timestamp = datetime.now()
        model = BaseSymbolModel(timestamp=timestamp, symbol="ADAUSDT")

        json_str = model.model_dump_json()
        data = json.loads(json_str)

        assert "symbol" in data
        assert data["symbol"] == "ADAUSDT"

    def test_missing_symbol_raises_validation_error(self):
        """Test that missing symbol field raises ValidationError."""
        timestamp = datetime.now()

        with pytest.raises(ValidationError) as exc_info:
            BaseSymbolModel(timestamp=timestamp)

        assert "symbol" in str(exc_info.value)


@pytest.mark.unit
class TestExtractionMetadata:
    """Test cases for ExtractionMetadata."""

    def test_initialization_with_required_fields(self):
        """Test model initialization with required fields."""
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=1)

        metadata = ExtractionMetadata(
            period="15m", start_time=start_time, end_time=end_time
        )

        assert metadata.period == "15m"
        assert metadata.start_time == start_time
        assert metadata.end_time == end_time
        assert metadata.total_records == 0
        assert metadata.gaps_detected == 0
        assert metadata.backfill_performed is False
        assert metadata.extraction_duration_seconds == 0.0
        assert metadata.errors_encountered == []
        assert isinstance(metadata.extraction_id, str)

    def test_initialization_with_all_fields(self):
        """Test model initialization with all fields."""
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=1)
        extraction_id = str(uuid.uuid4())
        errors = ["Error 1", "Error 2"]

        metadata = ExtractionMetadata(
            extraction_id=extraction_id,
            period="1h",
            start_time=start_time,
            end_time=end_time,
            total_records=1000,
            gaps_detected=5,
            backfill_performed=True,
            extraction_duration_seconds=45.5,
            errors_encountered=errors,
        )

        assert metadata.extraction_id == extraction_id
        assert metadata.period == "1h"
        assert metadata.total_records == 1000
        assert metadata.gaps_detected == 5
        assert metadata.backfill_performed is True
        assert metadata.extraction_duration_seconds == 45.5
        assert metadata.errors_encountered == errors

    def test_extraction_id_generation(self):
        """Test that extraction_id is auto-generated when not provided."""
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=1)

        metadata1 = ExtractionMetadata(
            period="5m", start_time=start_time, end_time=end_time
        )

        metadata2 = ExtractionMetadata(
            period="5m", start_time=start_time, end_time=end_time
        )

        assert metadata1.extraction_id != metadata2.extraction_id
        assert len(metadata1.extraction_id) == 36  # UUID4 length

    def test_json_serialization_datetime_encoding(self):
        """Test JSON serialization with proper datetime encoding."""
        start_time = datetime(2023, 1, 1, 0, 0, 0)
        end_time = datetime(2023, 1, 1, 1, 0, 0)

        metadata = ExtractionMetadata(
            period="15m", start_time=start_time, end_time=end_time
        )

        json_str = metadata.model_dump_json()
        data = json.loads(json_str)

        assert "start_time" in data
        assert "end_time" in data
        assert data["start_time"].endswith("Z")
        assert data["end_time"].endswith("Z")

    @pytest.mark.parametrize(
        "field_name,invalid_value",
        [
            ("period", None),
            ("start_time", None),
            ("end_time", None),
            ("total_records", "invalid"),
            ("gaps_detected", -1),
            ("extraction_duration_seconds", "invalid"),
        ],
    )
    def test_field_validation_errors(self, field_name, invalid_value):
        """Test validation errors for invalid field values."""
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=1)

        valid_data = {"period": "15m", "start_time": start_time, "end_time": end_time}

        # Replace the field with invalid value
        valid_data[field_name] = invalid_value

        with pytest.raises(ValidationError):
            ExtractionMetadata(**valid_data)

    def test_errors_encountered_list_handling(self):
        """Test that errors_encountered properly handles list operations."""
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=1)

        metadata = ExtractionMetadata(
            period="15m", start_time=start_time, end_time=end_time
        )

        # Should start with empty list
        assert metadata.errors_encountered == []

        # Should be able to append errors
        metadata.errors_encountered.append("New error")
        assert len(metadata.errors_encountered) == 1
        assert metadata.errors_encountered[0] == "New error"

    def test_model_dump_excludes_none_values(self):
        """Test that model dump handles optional fields correctly."""
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=1)

        metadata = ExtractionMetadata(
            period="15m", start_time=start_time, end_time=end_time
        )

        data = metadata.model_dump()

        # All fields should be present with default values
        assert "total_records" in data
        assert "gaps_detected" in data
        assert "backfill_performed" in data
        assert data["total_records"] == 0
        assert data["gaps_detected"] == 0
        assert data["backfill_performed"] is False

    def test_time_range_validation(self):
        """Test logical validation of time ranges."""
        start_time = datetime.now()
        end_time = start_time - timedelta(hours=1)  # End before start

        # Note: The model doesn't enforce this validation by default
        # This test documents the current behavior
        metadata = ExtractionMetadata(
            period="15m", start_time=start_time, end_time=end_time
        )

        assert metadata.start_time == start_time
        assert metadata.end_time == end_time
        # In a real implementation, you might want to add validation
        # to ensure end_time > start_time


# Integration tests combining multiple models
@pytest.mark.unit
class TestModelIntegration:
    """Integration tests for model interactions."""

    def test_model_inheritance_chain(self):
        """Test that inheritance chain works correctly."""
        timestamp = datetime.now()
        symbol_model = BaseSymbolModel(timestamp=timestamp, symbol="BTCUSDT")

        # Should have all BaseTimestampedModel methods
        assert hasattr(symbol_model, "model_dump")
        assert hasattr(symbol_model, "model_dump_json")

        # Should be instance of both classes
        assert isinstance(symbol_model, BaseSymbolModel)
        assert isinstance(symbol_model, BaseTimestampedModel)

    def test_multiple_models_serialization(self):
        """Test serialization of multiple model instances."""
        timestamp = datetime.now()

        models = [
            BaseSymbolModel(timestamp=timestamp, symbol=f"BTC{i}USDT") for i in range(5)
        ]

        serialized = [model.model_dump() for model in models]

        assert len(serialized) == 5
        for i, data in enumerate(serialized):
            assert data["symbol"] == f"BTC{i}USDT"
            assert "timestamp" in data
            assert "id" in data

    def test_model_field_access_patterns(self):
        """Test common field access patterns."""
        timestamp = datetime.now()
        model = BaseSymbolModel(timestamp=timestamp, symbol="ETHUSDT")

        # Test dict-like access
        data = model.model_dump()
        assert data["symbol"] == "ETHUSDT"

        # Test attribute access
        assert model.symbol == "ETHUSDT"
        assert model.timestamp == timestamp

        # Test field iteration
        field_names = list(model.model_fields.keys())
        assert "timestamp" in field_names
        assert "symbol" in field_names
