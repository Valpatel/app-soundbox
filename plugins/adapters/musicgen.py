"""
MusicGen adapter for SoundBox plugin system.

Wraps Meta's MusicGen model to provide a consistent AudioModel interface.
"""

import gc
import os
import time
from typing import List, Optional, Any

from ..base import (
    AudioModelBase,
    ModelCapability,
    GenerationResult,
    ModelStatus,
    ModelLoadError,
    GenerationError,
)
from ..registry import ModelRegistry


@ModelRegistry.register(
    model_id="musicgen-small",
    display_name="MusicGen Small",
    memory_gb=4.0,
    capabilities=[ModelCapability.MUSIC],
    config={'model_name': 'facebook/musicgen-small'},
    enabled=True,
    description="Meta's MusicGen small model (300M params). Fast music generation.",
    license="CC-BY-NC 4.0",
    commercial_ok=False,  # Weights are non-commercial
)
class MusicGenSmallAdapter(AudioModelBase):
    """Adapter for Meta's MusicGen Small model."""

    def __init__(self, model_name: str = 'facebook/musicgen-small'):
        self._model_name = model_name
        self._model = None
        self._sample_rate = 32000

    @property
    def model_id(self) -> str:
        return "musicgen-small"

    @property
    def display_name(self) -> str:
        return "MusicGen Small"

    @property
    def capabilities(self) -> List[ModelCapability]:
        return [ModelCapability.MUSIC]

    @property
    def memory_requirement_gb(self) -> float:
        return 4.0

    @property
    def max_duration_seconds(self) -> float:
        return 30.0

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def load(self) -> bool:
        """Load MusicGen model into GPU memory."""
        if self._model is not None:
            return True

        try:
            from audiocraft.models import MusicGen
            print(f"[MusicGen] Loading {self._model_name}...")
            self._model = MusicGen.get_pretrained(self._model_name)
            self._loaded = True
            self._error = None
            print(f"[MusicGen] Loaded successfully")
            return True
        except Exception as e:
            self._error = str(e)
            print(f"[MusicGen] Load failed: {e}")
            return False

    def unload(self) -> bool:
        """Unload MusicGen model from memory."""
        if self._model is None:
            return True

        try:
            del self._model
            self._model = None
            self._loaded = False
            gc.collect()

            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            print(f"[MusicGen] Unloaded")
            return True
        except Exception as e:
            self._error = str(e)
            print(f"[MusicGen] Unload failed: {e}")
            return False

    def generate(
        self,
        prompt: str,
        duration: float,
        output_path: str,
        **kwargs
    ) -> GenerationResult:
        """Generate music from a text prompt."""
        if not self.is_loaded():
            raise GenerationError("Model not loaded")

        self._mark_used()

        try:
            import torch
            from audiocraft.data.audio import audio_write

            # Clamp duration
            duration = min(duration, self.max_duration_seconds)

            # Set generation parameters
            self._model.set_generation_params(duration=duration)

            # Generate
            print(f"[MusicGen] Generating: {prompt[:50]}... ({duration}s)")
            wav = self._model.generate([prompt])

            # Get output tensor (remove batch dimension)
            audio_out = wav[0]

            # Save to file (audio_write adds .wav extension)
            output_base = output_path.replace('.wav', '')
            audio_write(
                output_base,
                audio_out.cpu(),
                self._sample_rate,
                strategy="loudness"
            )

            # Ensure .wav extension
            final_path = output_base + '.wav'
            if not os.path.exists(final_path):
                final_path = output_path

            return GenerationResult(
                audio_path=final_path,
                sample_rate=self._sample_rate,
                duration=duration,
                metadata={
                    'prompt': prompt,
                    'model': self.model_id,
                    'model_name': self._model_name,
                }
            )

        except Exception as e:
            print(f"[MusicGen] Generation failed: {e}")
            return GenerationResult(
                audio_path="",
                sample_rate=self._sample_rate,
                duration=0,
                error=str(e)
            )


@ModelRegistry.register(
    model_id="musicgen-medium",
    display_name="MusicGen Medium",
    memory_gb=7.0,
    capabilities=[ModelCapability.MUSIC],
    config={'model_name': 'facebook/musicgen-medium'},
    enabled=True,
    description="Meta's MusicGen medium model (1.5B params). Higher quality music.",
    license="CC-BY-NC 4.0",
    commercial_ok=False,
)
class MusicGenMediumAdapter(MusicGenSmallAdapter):
    """Adapter for MusicGen Medium - higher quality, more VRAM."""

    def __init__(self, model_name: str = 'facebook/musicgen-medium'):
        super().__init__(model_name)

    @property
    def model_id(self) -> str:
        return "musicgen-medium"

    @property
    def display_name(self) -> str:
        return "MusicGen Medium"

    @property
    def memory_requirement_gb(self) -> float:
        return 7.0


@ModelRegistry.register(
    model_id="musicgen-large",
    display_name="MusicGen Large",
    memory_gb=12.0,
    capabilities=[ModelCapability.MUSIC],
    config={'model_name': 'facebook/musicgen-large'},
    enabled=False,  # Disabled by default due to high VRAM
    description="Meta's MusicGen large model (3.3B params). Highest quality, requires 12GB+ VRAM.",
    license="CC-BY-NC 4.0",
    commercial_ok=False,
)
class MusicGenLargeAdapter(MusicGenSmallAdapter):
    """Adapter for MusicGen Large - highest quality, most VRAM."""

    def __init__(self, model_name: str = 'facebook/musicgen-large'):
        super().__init__(model_name)

    @property
    def model_id(self) -> str:
        return "musicgen-large"

    @property
    def display_name(self) -> str:
        return "MusicGen Large"

    @property
    def memory_requirement_gb(self) -> float:
        return 12.0
