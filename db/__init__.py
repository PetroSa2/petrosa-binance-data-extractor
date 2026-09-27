"""
Database adapters package.
"""

from typing import Any

from .base_adapter import BaseAdapter, DatabaseError

# Import Data Manager adapter
try:
    from adapters.data_manager_adapter import DataManagerAdapter

    DATA_MANAGER_AVAILABLE = True
except ImportError:
    DATA_MANAGER_AVAILABLE = False
    DataManagerAdapter = None

# Adapter registry
ADAPTERS: dict[str, type[Any]] = {}

# Add Data Manager adapter if available
if DATA_MANAGER_AVAILABLE:
    ADAPTERS["data_manager"] = DataManagerAdapter


def get_adapter(
    adapter_type: str, connection_string: str | None = None, **kwargs
) -> Any:
    """
    Factory function to get the appropriate database adapter.

    Args:
        adapter_type: Type of adapter (only 'data_manager')
        connection_string: Database connection string
        **kwargs: Additional adapter-specific options

    Returns:
        BaseAdapter instance

    Raises:
        ValueError: If adapter type is not supported
    """
    if adapter_type not in ADAPTERS:
        raise ValueError(
            f"Unsupported adapter type: {adapter_type}. Available: {list(ADAPTERS.keys())}"
        )

    if connection_string is None:
        raise ValueError("connection_string is required")

    adapter_class = ADAPTERS[adapter_type]
    return adapter_class(connection_string, **kwargs)


__all__ = [
    "BaseAdapter",
    "DatabaseError",
    "get_adapter",
    "ADAPTERS",
]
