# SoundBox Plugin System
# Modular architecture for swappable AI audio generation models

from .base import (
    AudioModel,
    ModelCapability,
    GenerationResult,
    ModelStatus,
    PluginError,
    ModelLoadError,
    GenerationError,
    GPUMemoryError,
)
from .registry import ModelRegistry
from .manager import ModelManager

__all__ = [
    # Protocols and types
    'AudioModel',
    'ModelCapability',
    'GenerationResult',
    'ModelStatus',
    # Errors
    'PluginError',
    'ModelLoadError',
    'GenerationError',
    'GPUMemoryError',
    # Core classes
    'ModelRegistry',
    'ModelManager',
]

# Auto-discover and register adapters when this package is imported
def _discover_adapters():
    """Auto-import all adapter modules to trigger registration."""
    import importlib
    import pkgutil
    from pathlib import Path

    adapters_path = Path(__file__).parent / 'adapters'
    if not adapters_path.exists():
        return

    for finder, name, ispkg in pkgutil.iter_modules([str(adapters_path)]):
        if not name.startswith('_'):
            try:
                importlib.import_module(f'.adapters.{name}', package='plugins')
            except Exception as e:
                print(f"[Plugins] Failed to load adapter '{name}': {e}")

_discover_adapters()
