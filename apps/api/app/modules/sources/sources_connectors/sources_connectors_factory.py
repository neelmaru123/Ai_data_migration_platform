"""
Database Connector Factory Registry (Strategy Pattern)
"""

from typing import Any, Dict, List, Type
from app.modules.sources.sources_connectors.sources_connectors_base import BaseConnector


class ConnectorFactory:
    """Registry Factory that dynamically creates DB Connector strategy instances."""

    _connectors: Dict[str, Type[BaseConnector]] = {}

    @classmethod
    def register(cls, type_name: str):
        """Decorator to register a connector class under a specific DB type key."""
        def decorator(connector_cls: Type[BaseConnector]):
            cls._connectors[type_name.lower().strip()] = connector_cls
            return connector_cls
        return decorator

    @classmethod
    def create(cls, type_name: str, config: Dict[str, Any]) -> BaseConnector:
        """Instantiate registered connector strategy for the given DB type."""
        key = type_name.lower().strip()
        if key not in cls._connectors:
            raise ValueError(
                f"Unsupported database connector type '{type_name}'. "
                f"Available connectors: {cls.available_types()}"
            )
        return cls._connectors[key](config=config)

    @classmethod
    def available_types(cls) -> List[str]:
        """Return list of registered connector keys."""
        return sorted(list(cls._connectors.keys()))
