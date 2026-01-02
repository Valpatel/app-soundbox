"""
Model Registry for the SoundBox plugin system.

Provides centralized registration, discovery, and instantiation of audio models.
Uses decorator pattern for clean registration syntax.
"""

from typing import Type, Dict, Optional, Callable, Any, List
from dataclasses import dataclass, field
import threading

from .base import (
    AudioModel,
    ModelCapability,
    ModelNotFoundError,
    ModelDisabledError,
)


@dataclass
class ModelInfo:
    """Metadata about a registered model."""
    model_id: str
    cls: Type
    display_name: str
    memory_gb: float
    capabilities: List[ModelCapability]
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    description: str = ""
    license: str = "Unknown"
    commercial_ok: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'model_id': self.model_id,
            'display_name': self.display_name,
            'memory_gb': self.memory_gb,
            'capabilities': [c.value for c in self.capabilities],
            'enabled': self.enabled,
            'description': self.description,
            'license': self.license,
            'commercial_ok': self.commercial_ok,
        }


class ModelRegistry:
    """
    Central registry for audio generation models.

    Singleton pattern ensures one global registry.
    Thread-safe for concurrent access.

    Usage:
        @ModelRegistry.register(
            model_id="musicgen-small",
            display_name="MusicGen Small",
            memory_gb=4.0,
            capabilities=[ModelCapability.MUSIC],
        )
        class MusicGenSmallAdapter:
            ...

        # Or register manually:
        ModelRegistry.register_class(
            "my-model",
            MyModelClass,
            display_name="My Model",
            ...
        )
    """

    _models: Dict[str, ModelInfo] = {}
    _lock = threading.RLock()

    @classmethod
    def register(
        cls,
        model_id: str,
        display_name: Optional[str] = None,
        memory_gb: float = 4.0,
        capabilities: Optional[List[ModelCapability]] = None,
        config: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
        description: str = "",
        license: str = "Unknown",
        commercial_ok: bool = False,
    ) -> Callable[[Type], Type]:
        """
        Decorator to register a model class.

        Args:
            model_id: Unique identifier for this model
            display_name: Human-readable name (defaults to model_id)
            memory_gb: Estimated GPU memory requirement
            capabilities: List of model capabilities
            config: Default configuration for the model
            enabled: Whether model is enabled by default
            description: Brief description of the model
            license: License type (e.g., "MIT", "Apache 2.0", "CC-BY-NC")
            commercial_ok: Whether commercial use is permitted

        Returns:
            Decorator function
        """
        def decorator(model_cls: Type) -> Type:
            cls.register_class(
                model_id=model_id,
                model_cls=model_cls,
                display_name=display_name,
                memory_gb=memory_gb,
                capabilities=capabilities,
                config=config,
                enabled=enabled,
                description=description,
                license=license,
                commercial_ok=commercial_ok,
            )
            return model_cls
        return decorator

    @classmethod
    def register_class(
        cls,
        model_id: str,
        model_cls: Type,
        display_name: Optional[str] = None,
        memory_gb: float = 4.0,
        capabilities: Optional[List[ModelCapability]] = None,
        config: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
        description: str = "",
        license: str = "Unknown",
        commercial_ok: bool = False,
    ) -> None:
        """
        Register a model class directly (non-decorator version).
        """
        with cls._lock:
            info = ModelInfo(
                model_id=model_id,
                cls=model_cls,
                display_name=display_name or model_id,
                memory_gb=memory_gb,
                capabilities=capabilities or [ModelCapability.MUSIC],
                config=config or {},
                enabled=enabled,
                description=description,
                license=license,
                commercial_ok=commercial_ok,
            )
            cls._models[model_id] = info
            print(f"[Registry] Registered model: {model_id} ({info.display_name})")

    @classmethod
    def unregister(cls, model_id: str) -> bool:
        """
        Unregister a model.

        Returns:
            True if model was unregistered, False if not found
        """
        with cls._lock:
            if model_id in cls._models:
                del cls._models[model_id]
                print(f"[Registry] Unregistered model: {model_id}")
                return True
            return False

    @classmethod
    def get(cls, model_id: str) -> Optional[ModelInfo]:
        """Get model info by ID. Returns None if not found."""
        with cls._lock:
            return cls._models.get(model_id)

    @classmethod
    def get_or_raise(cls, model_id: str) -> ModelInfo:
        """Get model info by ID. Raises if not found."""
        info = cls.get(model_id)
        if info is None:
            raise ModelNotFoundError(f"Model not found: {model_id}")
        return info

    @classmethod
    def list_all(cls) -> List[str]:
        """List all registered model IDs."""
        with cls._lock:
            return list(cls._models.keys())

    @classmethod
    def list_enabled(cls) -> List[str]:
        """List enabled model IDs only."""
        with cls._lock:
            return [
                mid for mid, info in cls._models.items()
                if info.enabled
            ]

    @classmethod
    def list_by_capability(
        cls,
        capability: ModelCapability,
        enabled_only: bool = True
    ) -> List[str]:
        """
        List models with a specific capability.

        Args:
            capability: Required capability
            enabled_only: If True, only return enabled models

        Returns:
            List of model IDs
        """
        with cls._lock:
            results = []
            for mid, info in cls._models.items():
                if capability in info.capabilities:
                    if not enabled_only or info.enabled:
                        results.append(mid)
            return results

    @classmethod
    def list_commercial_safe(cls, enabled_only: bool = True) -> List[str]:
        """List models that are safe for commercial use."""
        with cls._lock:
            results = []
            for mid, info in cls._models.items():
                if info.commercial_ok:
                    if not enabled_only or info.enabled:
                        results.append(mid)
            return results

    @classmethod
    def create_instance(cls, model_id: str, **kwargs) -> AudioModel:
        """
        Create a new model instance.

        Args:
            model_id: ID of model to create
            **kwargs: Additional arguments passed to model constructor

        Returns:
            New model instance

        Raises:
            ModelNotFoundError: If model not found
            ModelDisabledError: If model is disabled
        """
        info = cls.get_or_raise(model_id)

        if not info.enabled:
            raise ModelDisabledError(f"Model is disabled: {model_id}")

        # Merge registered config with runtime kwargs
        merged_config = {**info.config, **kwargs}
        return info.cls(**merged_config)

    @classmethod
    def set_enabled(cls, model_id: str, enabled: bool) -> bool:
        """
        Enable or disable a model.

        Returns:
            True if state was changed, False if model not found
        """
        with cls._lock:
            if model_id in cls._models:
                cls._models[model_id].enabled = enabled
                return True
            return False

    @classmethod
    def get_info_dict(cls, model_id: str) -> Optional[Dict[str, Any]]:
        """Get model info as a dictionary."""
        info = cls.get(model_id)
        return info.to_dict() if info else None

    @classmethod
    def get_all_info(cls, enabled_only: bool = False) -> Dict[str, Dict[str, Any]]:
        """Get info for all models as a dictionary."""
        with cls._lock:
            return {
                mid: info.to_dict()
                for mid, info in cls._models.items()
                if not enabled_only or info.enabled
            }

    @classmethod
    def clear(cls) -> None:
        """Clear all registered models. Mainly for testing."""
        with cls._lock:
            cls._models.clear()
            print("[Registry] Cleared all models")
