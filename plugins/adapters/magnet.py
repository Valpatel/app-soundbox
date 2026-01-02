"""
MAGNeT adapter for SoundBox plugin system.

Wraps Meta's MAGNeT model (Masked Audio Generation using a single Non-autoregressive Transformer).
MAGNeT is faster than MusicGen/AudioGen but may have different quality characteristics.
"""

import gc
import os
import time
from typing import List, Optional

from ..base import (
    AudioModelBase,
    ModelCapability,
    GenerationResult,
    GenerationError,
)
from ..registry import ModelRegistry


@ModelRegistry.register(
    model_id="magnet-music-small",
    display_name="MAGNeT Music Small",
    memory_gb=6.0,
    capabilities=[ModelCapability.MUSIC],
    config={'model_name': 'facebook/magnet-small-10secs'},
    enabled=True,
    description="Meta's MAGNeT music model. Faster than MusicGen, 10-second clips.",
    license="CC-BY-NC 4.0",
    commercial_ok=False,
)
class MagnetMusicAdapter(AudioModelBase):
    """Adapter for Meta's MAGNeT music model."""

    def __init__(self, model_name: str = 'facebook/magnet-small-10secs'):
        self._model_name = model_name
        self._model = None
        self._sample_rate = 32000

    @property
    def model_id(self) -> str:
        return "magnet-music-small"

    @property
    def display_name(self) -> str:
        return "MAGNeT Music Small"

    @property
    def capabilities(self) -> List[ModelCapability]:
        return [ModelCapability.MUSIC]

    @property
    def memory_requirement_gb(self) -> float:
        return 6.0

    @property
    def max_duration_seconds(self) -> float:
        return 10.0  # MAGNeT small is optimized for 10-second clips

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def load(self) -> bool:
        """Load MAGNeT model into GPU memory."""
        if self._model is not None:
            return True

        try:
            from audiocraft.models import MAGNeT
            print(f"[MAGNeT] Loading {self._model_name}...")
            self._model = MAGNeT.get_pretrained(self._model_name)
            self._loaded = True
            self._error = None
            print(f"[MAGNeT] Loaded successfully")
            return True
        except Exception as e:
            self._error = str(e)
            print(f"[MAGNeT] Load failed: {e}")
            return False

    def unload(self) -> bool:
        """Unload MAGNeT model from memory."""
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

            print(f"[MAGNeT] Unloaded")
            return True
        except Exception as e:
            self._error = str(e)
            print(f"[MAGNeT] Unload failed: {e}")
            return False

    def generate(
        self,
        prompt: str,
        duration: float,
        output_path: str,
        **kwargs
    ) -> GenerationResult:
        """Generate music from a text prompt using MAGNeT."""
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
            print(f"[MAGNeT] Generating: {prompt[:50]}... ({duration}s)")
            wav = self._model.generate([prompt])

            # Get output tensor
            audio_out = wav[0]

            # Save to file
            output_base = output_path.replace('.wav', '')
            audio_write(
                output_base,
                audio_out.cpu(),
                self._sample_rate,
                strategy="loudness"
            )

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
            print(f"[MAGNeT] Generation failed: {e}")
            return GenerationResult(
                audio_path="",
                sample_rate=self._sample_rate,
                duration=0,
                error=str(e)
            )


@ModelRegistry.register(
    model_id="magnet-audio-small",
    display_name="MAGNeT Audio Small",
    memory_gb=6.0,
    capabilities=[ModelCapability.SFX, ModelCapability.AMBIENT],
    config={'model_name': 'facebook/audio-magnet-small'},
    enabled=True,
    description="Meta's MAGNeT audio/SFX model. Faster generation for sound effects.",
    license="CC-BY-NC 4.0",
    commercial_ok=False,
)
class MagnetAudioAdapter(MagnetMusicAdapter):
    """Adapter for Meta's MAGNeT audio/SFX model."""

    def __init__(self, model_name: str = 'facebook/audio-magnet-small'):
        super().__init__(model_name)
        self._sample_rate = 16000  # Audio MAGNeT outputs 16kHz

    @property
    def model_id(self) -> str:
        return "magnet-audio-small"

    @property
    def display_name(self) -> str:
        return "MAGNeT Audio Small"

    @property
    def capabilities(self) -> List[ModelCapability]:
        return [ModelCapability.SFX, ModelCapability.AMBIENT]

    @property
    def sample_rate(self) -> int:
        return 16000
