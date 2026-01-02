"""
Stable Audio Open adapter for SoundBox plugin system.

Wraps Stability AI's Stable Audio Open model via HuggingFace Diffusers.
Excellent for sound effects and ambient audio.
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
    model_id="stable-audio-open",
    display_name="Stable Audio Open",
    memory_gb=8.0,
    capabilities=[ModelCapability.SFX, ModelCapability.AMBIENT, ModelCapability.MUSIC],
    config={'model_name': 'stabilityai/stable-audio-open-1.0'},
    enabled=True,
    description="Stability AI's open model. Great for SFX and ambient. Up to 47s stereo at 44.1kHz.",
    license="Stability AI Community License",
    commercial_ok=True,  # Free for <$1M revenue
)
class StableAudioOpenAdapter(AudioModelBase):
    """Adapter for Stable Audio Open via HuggingFace Diffusers."""

    def __init__(self, model_name: str = 'stabilityai/stable-audio-open-1.0'):
        self._model_name = model_name
        self._pipe = None
        self._sample_rate = 44100  # Stable Audio outputs 44.1kHz

    @property
    def model_id(self) -> str:
        return "stable-audio-open"

    @property
    def display_name(self) -> str:
        return "Stable Audio Open"

    @property
    def capabilities(self) -> List[ModelCapability]:
        return [ModelCapability.SFX, ModelCapability.AMBIENT, ModelCapability.MUSIC]

    @property
    def memory_requirement_gb(self) -> float:
        return 8.0

    @property
    def max_duration_seconds(self) -> float:
        return 47.0  # Stable Audio can do up to 47 seconds

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def load(self) -> bool:
        """Load Stable Audio pipeline."""
        if self._pipe is not None:
            return True

        try:
            import torch
            from diffusers import StableAudioPipeline

            print(f"[StableAudio] Loading {self._model_name}...")

            self._pipe = StableAudioPipeline.from_pretrained(
                self._model_name,
                torch_dtype=torch.float16,
            )

            # Move to GPU if available
            if torch.cuda.is_available():
                self._pipe = self._pipe.to("cuda")
                # Enable memory efficient attention
                self._pipe.enable_model_cpu_offload()

            self._loaded = True
            self._error = None
            print(f"[StableAudio] Loaded successfully")
            return True

        except Exception as e:
            self._error = str(e)
            print(f"[StableAudio] Load failed: {e}")
            return False

    def unload(self) -> bool:
        """Unload Stable Audio pipeline."""
        if self._pipe is None:
            return True

        try:
            del self._pipe
            self._pipe = None
            self._loaded = False
            gc.collect()

            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            print(f"[StableAudio] Unloaded")
            return True

        except Exception as e:
            self._error = str(e)
            print(f"[StableAudio] Unload failed: {e}")
            return False

    def generate(
        self,
        prompt: str,
        duration: float,
        output_path: str,
        negative_prompt: str = "low quality, distorted",
        num_inference_steps: int = 100,
        **kwargs
    ) -> GenerationResult:
        """Generate audio from a text prompt."""
        if not self.is_loaded():
            raise GenerationError("Model not loaded")

        self._mark_used()

        try:
            import torch
            import soundfile as sf

            # Clamp duration
            duration = min(duration, self.max_duration_seconds)

            print(f"[StableAudio] Generating: {prompt[:50]}... ({duration}s)")

            # Generate
            audio = self._pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=num_inference_steps,
                audio_end_in_s=duration,
            ).audios[0]

            # Ensure output has .wav extension
            if not output_path.endswith('.wav'):
                output_path = output_path + '.wav'

            # Save audio - audio is numpy array of shape (channels, samples) or (samples,)
            # Transpose if needed for soundfile (expects samples, channels)
            if len(audio.shape) == 2:
                audio = audio.T

            sf.write(output_path, audio, self._sample_rate)

            return GenerationResult(
                audio_path=output_path,
                sample_rate=self._sample_rate,
                duration=duration,
                metadata={
                    'prompt': prompt,
                    'model': self.model_id,
                    'model_name': self._model_name,
                    'steps': num_inference_steps,
                }
            )

        except Exception as e:
            print(f"[StableAudio] Generation failed: {e}")
            return GenerationResult(
                audio_path="",
                sample_rate=self._sample_rate,
                duration=0,
                error=str(e)
            )
