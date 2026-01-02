"""
AudioGen adapter for SoundBox plugin system.

Wraps Meta's AudioGen model to provide a consistent AudioModel interface.
AudioGen specializes in sound effects and environmental audio.
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
    model_id="audiogen-medium",
    display_name="AudioGen Medium",
    memory_gb=5.0,
    capabilities=[ModelCapability.SFX, ModelCapability.AMBIENT],
    config={'model_name': 'facebook/audiogen-medium'},
    enabled=True,
    description="Meta's AudioGen model. Optimized for sound effects and ambient audio.",
    license="CC-BY-NC 4.0",
    commercial_ok=False,  # Weights are non-commercial
)
class AudioGenMediumAdapter(AudioModelBase):
    """Adapter for Meta's AudioGen Medium model."""

    def __init__(self, model_name: str = 'facebook/audiogen-medium'):
        self._model_name = model_name
        self._model = None
        self._sample_rate = 16000  # AudioGen outputs 16kHz

    @property
    def model_id(self) -> str:
        return "audiogen-medium"

    @property
    def display_name(self) -> str:
        return "AudioGen Medium"

    @property
    def capabilities(self) -> List[ModelCapability]:
        return [ModelCapability.SFX, ModelCapability.AMBIENT]

    @property
    def memory_requirement_gb(self) -> float:
        return 5.0

    @property
    def max_duration_seconds(self) -> float:
        return 10.0  # AudioGen works best with shorter clips

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def load(self) -> bool:
        """Load AudioGen model into GPU memory."""
        if self._model is not None:
            return True

        try:
            from audiocraft.models import AudioGen
            print(f"[AudioGen] Loading {self._model_name}...")
            self._model = AudioGen.get_pretrained(self._model_name)
            self._loaded = True
            self._error = None
            print(f"[AudioGen] Loaded successfully")
            return True
        except Exception as e:
            self._error = str(e)
            print(f"[AudioGen] Load failed: {e}")
            return False

    def unload(self) -> bool:
        """Unload AudioGen model from memory."""
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

            print(f"[AudioGen] Unloaded")
            return True
        except Exception as e:
            self._error = str(e)
            print(f"[AudioGen] Unload failed: {e}")
            return False

    def generate(
        self,
        prompt: str,
        duration: float,
        output_path: str,
        **kwargs
    ) -> GenerationResult:
        """Generate sound effects from a text prompt."""
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
            print(f"[AudioGen] Generating: {prompt[:50]}... ({duration}s)")
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
            print(f"[AudioGen] Generation failed: {e}")
            return GenerationResult(
                audio_path="",
                sample_rate=self._sample_rate,
                duration=0,
                error=str(e)
            )
