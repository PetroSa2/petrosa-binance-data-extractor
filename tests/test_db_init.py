"""Tests for db.get_adapter factory and the adapter registry."""

import pytest

import db
from db import ADAPTERS, MongoDBAdapter, MySQLAdapter, get_adapter


class TestAdapterRegistry:
    def test_mongodb_in_registry(self):
        assert ADAPTERS["mongodb"] is MongoDBAdapter

    def test_mysql_in_registry(self):
        assert ADAPTERS["mysql"] is MySQLAdapter

    def test_mariadb_aliases_mysql(self):
        assert ADAPTERS["mariadb"] is MySQLAdapter


class TestGetAdapter:
    def test_unknown_adapter_raises(self):
        with pytest.raises(ValueError, match="Unsupported adapter type") as exc_info:
            get_adapter("redis", connection_string="redis://localhost")
        assert "redis" in str(exc_info.value)

    def test_missing_connection_string_raises(self):
        with pytest.raises(
            ValueError, match="connection_string is required"
        ) as exc_info:
            get_adapter("mongodb")
        assert "connection_string" in str(exc_info.value)

    def test_returns_mongodb_adapter_instance(self):
        # No connection actually attempted in __init__ — just instantiation.
        adapter = get_adapter("mongodb", connection_string="mongodb://localhost")
        assert isinstance(adapter, MongoDBAdapter)

    def test_returns_mysql_adapter_instance(self):
        adapter = get_adapter("mysql", connection_string="mysql://localhost")
        assert isinstance(adapter, MySQLAdapter)


class TestDataManagerAvailability:
    def test_data_manager_flag_is_boolean(self):
        # The flag must be a bool whether the optional adapter is present or not.
        assert isinstance(db.DATA_MANAGER_AVAILABLE, bool)

    def test_data_manager_registered_when_available(self):
        if db.DATA_MANAGER_AVAILABLE:
            assert "data_manager" in ADAPTERS
        else:
            assert "data_manager" not in ADAPTERS
