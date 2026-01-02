"""
Bark adapter for SoundBox plugin system.

Wraps Suno's Bark model - a fully MIT-licensed text-to-audio model.
Can generate speech, music, and sound effects.
"""

# Fix PyTorch 2.6+ compatibility - monkey patch torch.load
# Bark's checkpoint files use numpy scalars which aren't in the default safe list
import torch
import numpy as np

_original_torch_load = torch.load

def _patched_torch_load(*args, **kwargs):
    """Patch torch.load to use weights_only=False for Bark compatibility."""
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)

torch.load = _patched_torch_load

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


# Bark speaker presets for different voices/styles
BARK_SPEAKERS = {
    # English speakers
    'v2/en_speaker_0': 'English Male 1',
    'v2/en_speaker_1': 'English Male 2',
    'v2/en_speaker_2': 'English Male 3',
    'v2/en_speaker_3': 'English Female 1',
    'v2/en_speaker_4': 'English Female 2',
    'v2/en_speaker_5': 'English Female 3',
    'v2/en_speaker_6': 'English Male 4',
    'v2/en_speaker_7': 'English Male 5',
    'v2/en_speaker_8': 'English Female 4',
    'v2/en_speaker_9': 'English Female 5',
}


@ModelRegistry.register(
    model_id="bark",
    display_name="Bark (MIT)",
    memory_gb=5.0,
    capabilities=[ModelCapability.TTS, ModelCapability.SFX, ModelCapability.MUSIC],
    config={'use_small': False},
    enabled=True,
    description="Suno's MIT-licensed model. Speech, music, and sound effects. Fully commercial-safe.",
    license="MIT",
    commercial_ok=True,
)
class BarkAdapter(AudioModelBase):
    """Adapter for Suno's Bark model."""

    def __init__(self, use_small: bool = False):
        self._use_small = use_small
        self._model_loaded = False
        self._sample_rate = 24000

    @property
    def model_id(self) -> str:
        return "bark"

    @property
    def display_name(self) -> str:
        return "Bark (MIT)"

    @property
    def capabilities(self) -> List[ModelCapability]:
        return [ModelCapability.TTS, ModelCapability.SFX, ModelCapability.MUSIC]

    @property
    def memory_requirement_gb(self) -> float:
        return 2.0 if self._use_small else 5.0

    @property
    def max_duration_seconds(self) -> float:
        return 14.0  # Bark generates ~13-14 seconds per segment

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def load(self) -> bool:
        """Load Bark model - actually preloads models on first generation."""
        if self._model_loaded:
            return True

        try:
            # Set environment for small models if requested
            if self._use_small:
                os.environ["SUNO_USE_SMALL_MODELS"] = "True"

            # Fix PyTorch 2.6+ compatibility - allow numpy globals for Bark weights
            import torch
            import numpy as np
            torch.serialization.add_safe_globals([np.core.multiarray.scalar])

            # Import bark to trigger model download/caching
            from bark import SAMPLE_RATE
            self._sample_rate = SAMPLE_RATE

            self._loaded = True
            self._model_loaded = True
            self._error = None
            print(f"[Bark] Ready (small={self._use_small})")
            return True

        except Exception as e:
            self._error = str(e)
            print(f"[Bark] Load failed: {e}")
            return False

    def unload(self) -> bool:
        """Unload Bark model."""
        try:
            self._model_loaded = False
            self._loaded = False
            gc.collect()

            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            print(f"[Bark] Unloaded")
            return True

        except Exception as e:
            self._error = str(e)
            print(f"[Bark] Unload failed: {e}")
            return False

    def generate(
        self,
        prompt: str,
        duration: float,  # Note: Bark ignores this, generates full segment
        output_path: str,
        speaker: str = "v2/en_speaker_6",
        **kwargs
    ) -> GenerationResult:
        """
        Generate audio from text.

        Special Bark syntax:
        - [laughter] - Add laughter
        - [sighs] - Add sighing
        - [music] - Generate music
        - [gasps] - Add gasping
        - ♪ text ♪ - Sing the text
        - CAPITALIZED - Emphasize words
        - ... - Add pauses
        """
        if not self.is_loaded():
            raise GenerationError("Model not loaded")

        self._mark_used()

        try:
            from bark import generate_audio, SAMPLE_RATE
            from scipy.io.wavfile import write as write_wav
            import numpy as np

            print(f"[Bark] Generating: {prompt[:50]}...")

            # Generate audio
            audio_array = generate_audio(
                prompt,
                history_prompt=speaker if speaker in BARK_SPEAKERS else None,
            )

            # Ensure output has .wav extension
            if not output_path.endswith('.wav'):
                output_path = output_path + '.wav'

            # Save audio
            write_wav(output_path, SAMPLE_RATE, audio_array)

            # Calculate duration
            actual_duration = len(audio_array) / SAMPLE_RATE

            return GenerationResult(
                audio_path=output_path,
                sample_rate=SAMPLE_RATE,
                duration=actual_duration,
                metadata={
                    'prompt': prompt,
                    'model': self.model_id,
                    'speaker': speaker,
                }
            )

        except Exception as e:
            print(f"[Bark] Generation failed: {e}")
            return GenerationResult(
                audio_path="",
                sample_rate=self._sample_rate,
                duration=0,
                error=str(e)
            )


@ModelRegistry.register(
    model_id="bark-small",
    display_name="Bark Small (MIT)",
    memory_gb=2.0,
    capabilities=[ModelCapability.TTS, ModelCapability.SFX],
    config={'use_small': True},
    enabled=True,
    description="Bark small variant. Lower VRAM, still MIT-licensed.",
    license="MIT",
    commercial_ok=True,
)
class BarkSmallAdapter(BarkAdapter):
    """Adapter for Bark small model variant."""

    def __init__(self, use_small: bool = True):
        super().__init__(use_small=True)

    @property
    def model_id(self) -> str:
        return "bark-small"

    @property
    def display_name(self) -> str:
        return "Bark Small (MIT)"
