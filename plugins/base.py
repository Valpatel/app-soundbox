"""
Base classes and protocols for the SoundBox plugin system.

This module defines the core interfaces that all audio generation models must implement.
Uses Python's Protocol for structural subtyping (duck typing) combined with runtime checks.
"""

from typing import Protocol, runtime_checkable, Optional, Any, Dict, List
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import time


class ModelCapability(Enum):
    """Capabilities that models can support."""
    MUSIC = "music"           # Music generation (MusicGen, ACE-Step, etc.)
    SFX = "sfx"               # Sound effects (AudioGen, Stable Audio, etc.)
    AMBIENT = "ambient"       # Ambient/background audio
    TTS = "tts"               # Text-to-speech (Piper, Chatterbox, etc.)
    VOICE_CLONE = "voice_clone"  # Voice cloning capability
    SINGING = "singing"       # Singing/vocal synthesis
    LOOP = "loop"             # Seamless loop generation


@dataclass
class GenerationResult:
    """Result from audio generation."""
    audio_path: str                      # Path to generated audio file
    sample_rate: int                     # Audio sample rate (Hz)
    duration: float                      # Duration in seconds
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None          # Error message if generation failed

    @property
    def success(self) -> bool:
        """Whether generation was successful."""
        return self.error is None and bool(self.audio_path)


@dataclass
class ModelStatus:
    """Current status of a model."""
    model_id: str
    display_name: str
    loaded: bool
    loading: bool = False
    error: Optional[str] = None
    memory_used_gb: float = 0.0
    last_used: Optional[float] = None
    capabilities: List[ModelCapability] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'model_id': self.model_id,
            'display_name': self.display_name,
            'loaded': self.loaded,
            'loading': self.loading,
            'error': self.error,
            'memory_used_gb': self.memory_used_gb,
            'last_used': self.last_used,
            'capabilities': [c.value for c in self.capabilities],
        }


# Exception hierarchy
class PluginError(Exception):
    """Base exception for plugin errors."""
    pass


class ModelLoadError(PluginError):
    """Model failed to load."""
    pass


class GenerationError(PluginError):
    """Generation failed."""
    pass


class GPUMemoryError(PluginError):
    """Insufficient GPU memory."""
    pass


class ModelNotFoundError(PluginError):
    """Requested model not found in registry."""
    pass


class ModelDisabledError(PluginError):
    """Model is disabled in configuration."""
    pass


@runtime_checkable
class AudioModel(Protocol):
    """
    Protocol defining the interface for audio generation models.

    Any class implementing these methods/properties is automatically
    compatible without explicit inheritance (structural subtyping).

    Use @runtime_checkable to allow isinstance() checks at runtime.
    """

    @property
    def model_id(self) -> str:
        """Unique identifier for this model (e.g., 'musicgen-small')."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable name for UI display."""
        ...

    @property
    def capabilities(self) -> List[ModelCapability]:
        """List of capabilities this model supports."""
        ...

    @property
    def memory_requirement_gb(self) -> float:
        """Estimated GPU memory requirement in GB."""
        ...

    @property
    def max_duration_seconds(self) -> float:
        """Maximum generation duration supported."""
        ...

    @property
    def sample_rate(self) -> int:
        """Output sample rate in Hz."""
        ...

    def load(self) -> bool:
        """
        Load model into GPU memory.

        Returns:
            True if loaded successfully, False otherwise.
        """
        ...

    def unload(self) -> bool:
        """
        Unload model from memory.

        Returns:
            True if unloaded successfully, False otherwise.
        """
        ...

    def is_loaded(self) -> bool:
        """Check if model is currently loaded in memory."""
        ...

    def generate(
        self,
        prompt: str,
        duration: float,
        output_path: str,
        **kwargs
    ) -> GenerationResult:
        """
        Generate audio from a text prompt.

        Args:
            prompt: Text description of desired audio
            duration: Desired duration in seconds
            output_path: Path to save generated audio
            **kwargs: Model-specific parameters

        Returns:
            GenerationResult with audio path and metadata
        """
        ...

    def get_status(self) -> ModelStatus:
        """Get current model status."""
        ...


class AudioModelBase(ABC):
    """
    Abstract base class providing common functionality for audio models.

    Inherit from this for shared implementation code.
    Subclasses must implement the abstract methods.
    """

    _loaded: bool = False
    _last_used: Optional[float] = None
    _error: Optional[str] = None

    @property
    @abstractmethod
    def model_id(self) -> str:
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        pass

    @property
    @abstractmethod
    def capabilities(self) -> List[ModelCapability]:
        pass

    @property
    @abstractmethod
    def memory_requirement_gb(self) -> float:
        pass

    @property
    def max_duration_seconds(self) -> float:
        """Default max duration. Override in subclass if different."""
        return 30.0

    @property
    def sample_rate(self) -> int:
        """Default sample rate. Override in subclass if different."""
        return 32000

    def is_loaded(self) -> bool:
        return self._loaded

    def get_status(self) -> ModelStatus:
        return ModelStatus(
            model_id=self.model_id,
            display_name=self.display_name,
            loaded=self._loaded,
            loading=False,
            error=self._error,
            memory_used_gb=self.memory_requirement_gb if self._loaded else 0.0,
            last_used=self._last_used,
            capabilities=self.capabilities,
        )

    def _mark_used(self) -> None:
        """Update last used timestamp."""
        self._last_used = time.time()

    @abstractmethod
    def load(self) -> bool:
        pass

    @abstractmethod
    def unload(self) -> bool:
        pass

    @abstractmethod
    def generate(
        self,
        prompt: str,
        duration: float,
        output_path: str,
        **kwargs
    ) -> GenerationResult:
        pass
