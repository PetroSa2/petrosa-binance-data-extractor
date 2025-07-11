"""
Database adapters package.
"""

from typing import Dict, Optional, Type

from .base_adapter import BaseAdapter, DatabaseError
from .mongodb_adapter import MongoDBAdapter
from .mysql_adapter import MySQLAdapter

# Adapter registry
ADAPTERS: Dict[str, Type[BaseAdapter]] = {
    "mongodb": MongoDBAdapter,
    "mysql": MySQLAdapter,
    "mariadb": MySQLAdapter,  # MariaDB uses same adapter as MySQL
}


def get_adapter(adapter_type: str, connection_string: Optional[str] = None, **kwargs) -> BaseAdapter:
    """
    Factory function to get the appropriate database adapter.

    Args:
        adapter_type: Type of adapter ('mongodb', 'mysql', 'postgresql')
        connection_string: Database connection string
        **kwargs: Additional adapter-specific options

    Returns:
        BaseAdapter instance

    Raises:
        ValueError: If adapter type is not supported
    """
    if adapter_type not in ADAPTERS:
        raise ValueError(f"Unsupported adapter type: {adapter_type}. Available: {list(ADAPTERS.keys())}")

    if connection_string is None:
        raise ValueError("connection_string is required")

    adapter_class = ADAPTERS[adapter_type]
    return adapter_class(connection_string, **kwargs)


__all__ = [
    "BaseAdapter",
    "DatabaseError",
    "MongoDBAdapter",
    "MySQLAdapter",
    "get_adapter",
    "ADAPTERS",
]
