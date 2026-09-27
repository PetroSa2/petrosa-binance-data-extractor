import pytest

from db import ADAPTERS, get_adapter


def test_only_data_manager_adapter_is_registered():
    assert set(ADAPTERS) == {"data_manager"}


def test_legacy_adapter_is_rejected():
    with pytest.raises(ValueError) as exc_info:
        get_adapter("mysql", "x")
    assert "Unsupported adapter type" in str(exc_info.value)
