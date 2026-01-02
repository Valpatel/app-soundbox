"""
Kokoro TTS adapter for SoundBox plugin system.

Wraps Kokoro-82M, an extremely fast and lightweight TTS model.
Runs on CPU with excellent quality despite only 82M parameters.
"""

import gc
import os
import wave
import time
from typing import List, Optional, Dict

from ..base import (
    AudioModelBase,
    ModelCapability,
    GenerationResult,
    GenerationError,
)
from ..registry import ModelRegistry


# Available Kokoro voices
KOKORO_VOICES = {
    # American English
    'af_heart': 'American Female - Heart',
    'af_bella': 'American Female - Bella',
    'af_nicole': 'American Female - Nicole',
    'af_sarah': 'American Female - Sarah',
    'af_sky': 'American Female - Sky',
    'am_adam': 'American Male - Adam',
    'am_michael': 'American Male - Michael',
    # British English
    'bf_emma': 'British Female - Emma',
    'bf_isabella': 'British Female - Isabella',
    'bm_george': 'British Male - George',
    'bm_lewis': 'British Male - Lewis',
}


@ModelRegistry.register(
    model_id="kokoro-tts",
    display_name="Kokoro TTS (Fast)",
    memory_gb=0.3,
    capabilities=[ModelCapability.TTS],
    config={},
    enabled=True,
    description="Ultra-fast 82M param TTS. Runs on CPU. Best for high-volume, low-latency use.",
    license="Apache 2.0",
    commercial_ok=True,
)
class KokoroTTSAdapter(AudioModelBase):
    """Adapter for Kokoro-82M TTS."""

    def __init__(self):
        self._kokoro = None
        self._sample_rate = 24000  # Kokoro outputs 24kHz

    @property
    def model_id(self) -> str:
        return "kokoro-tts"

    @property
    def display_name(self) -> str:
        return "Kokoro TTS (Fast)"

    @property
    def capabilities(self) -> List[ModelCapability]:
        return [ModelCapability.TTS]

    @property
    def memory_requirement_gb(self) -> float:
        return 0.3  # Very lightweight

    @property
    def max_duration_seconds(self) -> float:
        return 300.0  # TTS can generate longer content

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def load(self) -> bool:
        """Load Kokoro model."""
        if self._kokoro is not None:
            return True

        try:
            from kokoro_onnx import Kokoro

            # Find model files
            models_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'kokoro')
            onnx_path = os.path.join(models_dir, "kokoro-v1.0.onnx")
            voices_path = os.path.join(models_dir, "voices-v1.0.bin")

            if not os.path.exists(onnx_path) or not os.path.exists(voices_path):
                raise FileNotFoundError(
                    f"Kokoro model files not found in {models_dir}. "
                    "Download from: https://github.com/thewh1teagle/kokoro-onnx/releases"
                )

            print(f"[KokoroTTS] Loading model from {models_dir}...")
            self._kokoro = Kokoro(onnx_path, voices_path)

            self._loaded = True
            self._error = None
            print(f"[KokoroTTS] Loaded successfully")
            return True

        except Exception as e:
            self._error = str(e)
            print(f"[KokoroTTS] Load failed: {e}")
            return False

    def unload(self) -> bool:
        """Unload Kokoro model."""
        if self._kokoro is None:
            return True

        try:
            del self._kokoro
            self._kokoro = None
            self._loaded = False
            gc.collect()
            print(f"[KokoroTTS] Unloaded")
            return True

        except Exception as e:
            self._error = str(e)
            print(f"[KokoroTTS] Unload failed: {e}")
            return False

    def get_available_voices(self) -> Dict[str, str]:
        """Get available voice IDs and their descriptions."""
        return KOKORO_VOICES.copy()

    def generate(
        self,
        prompt: str,
        duration: float,  # Ignored for TTS
        output_path: str,
        voice: str = "af_heart",
        speed: float = 1.0,
        **kwargs
    ) -> GenerationResult:
        """Generate speech from text."""
        if not self.is_loaded():
            raise GenerationError("Model not loaded")

        self._mark_used()

        try:
            import soundfile as sf
            import numpy as np

            # Validate voice
            if voice not in KOKORO_VOICES and not voice.startswith(('af_', 'am_', 'bf_', 'bm_')):
                voice = "af_heart"  # Default

            print(f"[KokoroTTS] Generating: {prompt[:50]}... (voice: {voice})")

            # Generate audio
            samples, sample_rate = self._kokoro.create(
                prompt,
                voice=voice,
                speed=speed,
            )

            self._sample_rate = sample_rate

            # Ensure output has .wav extension
            if not output_path.endswith('.wav'):
                output_path = output_path + '.wav'

            # Save audio
            sf.write(output_path, samples, sample_rate)

            # Calculate duration
            actual_duration = len(samples) / sample_rate

            return GenerationResult(
                audio_path=output_path,
                sample_rate=sample_rate,
                duration=actual_duration,
                metadata={
                    'prompt': prompt,
                    'model': self.model_id,
                    'voice': voice,
                    'speed': speed,
                    'text_length': len(prompt),
                }
            )

        except Exception as e:
            print(f"[KokoroTTS] Generation failed: {e}")
            return GenerationResult(
                audio_path="",
                sample_rate=self._sample_rate,
                duration=0,
                error=str(e)
            )
