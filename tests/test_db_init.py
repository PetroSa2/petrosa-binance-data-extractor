import pytest

from db import ADAPTERS, get_adapter


def test_only_data_manager_adapter_is_registered():
    assert set(ADAPTERS) == {"data_manager"}


def test_legacy_adapter_is_rejected():
    with pytest.raises(ValueError):
        get_adapter("mysql", "x")
