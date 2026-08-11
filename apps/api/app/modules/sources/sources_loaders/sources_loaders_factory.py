"""
File Loader Factory Registry Strategy Pattern
"""

from typing import Any, Dict, List, Optional, Type
from app.modules.sources.sources_loaders.sources_loaders_base import BaseFileLoader


class FileLoaderFactory:
    """Registry Factory that dynamically creates File Loader strategy instances."""

    _loaders: Dict[str, Type[BaseFileLoader]] = {}

    @classmethod
    def register(cls, file_type: str):
        """Decorator to register a loader class under a specific file extension key."""
        def decorator(loader_cls: Type[BaseFileLoader]):
            cls._loaders[file_type.lower().strip()] = loader_cls
            return loader_cls
        return decorator

    @classmethod
    def create(
        cls, file_type: str, file_path: str, options: Optional[Dict[str, Any]] = None
    ) -> BaseFileLoader:
        """Instantiate registered file loader strategy for the given file format."""
        key = file_type.lower().strip()
        if key not in cls._loaders:
            raise ValueError(
                f"Unsupported file loader format '{file_type}'. "
                f"Available file loaders: {cls.available_types()}"
            )
        return cls._loaders[key](file_path=file_path, options=options)

    @classmethod
    def available_types(cls) -> List[str]:
        """Return list of registered file loader format keys."""
        return sorted(list(cls._loaders.keys()))
