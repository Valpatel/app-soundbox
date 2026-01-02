"""
Piper TTS adapter for SoundBox plugin system.

Wraps Piper TTS to provide a consistent AudioModel interface.
Piper is a fast, local neural text-to-speech system.
"""

import gc
import os
import wave
import time
from typing import List, Optional, Dict, Any

from ..base import (
    AudioModelBase,
    ModelCapability,
    GenerationResult,
    GenerationError,
)
from ..registry import ModelRegistry


# Default voices directory
VOICES_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'voices')


@ModelRegistry.register(
    model_id="piper-tts",
    display_name="Piper TTS",
    memory_gb=0.5,
    capabilities=[ModelCapability.TTS],
    config={'voices_dir': VOICES_DIR},
    enabled=True,
    description="Fast, local neural TTS. Multiple voices available.",
    license="MIT",
    commercial_ok=True,  # Piper itself is MIT, voices vary
)
class PiperTTSAdapter(AudioModelBase):
    """Adapter for Piper TTS."""

    def __init__(self, voices_dir: str = VOICES_DIR):
        self._voices_dir = voices_dir
        self._loaded_voices: Dict[str, Any] = {}  # Cache loaded voice models
        self._sample_rate = 22050
        self._max_voices_cached = 5  # LRU cache size

    @property
    def model_id(self) -> str:
        return "piper-tts"

    @property
    def display_name(self) -> str:
        return "Piper TTS"

    @property
    def capabilities(self) -> List[ModelCapability]:
        return [ModelCapability.TTS]

    @property
    def memory_requirement_gb(self) -> float:
        return 0.5

    @property
    def max_duration_seconds(self) -> float:
        return 300.0  # TTS can generate longer content

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def load(self) -> bool:
        """
        For Piper, 'loading' just verifies the voices directory exists.
        Voice models are loaded on-demand.
        """
        try:
            if not os.path.exists(self._voices_dir):
                self._error = f"Voices directory not found: {self._voices_dir}"
                print(f"[PiperTTS] {self._error}")
                return False

            self._loaded = True
            self._error = None
            print(f"[PiperTTS] Ready (voices dir: {self._voices_dir})")
            return True
        except Exception as e:
            self._error = str(e)
            print(f"[PiperTTS] Load failed: {e}")
            return False

    def unload(self) -> bool:
        """Unload all cached voice models."""
        try:
            self._loaded_voices.clear()
            self._loaded = False
            gc.collect()
            print(f"[PiperTTS] Unloaded all voices")
            return True
        except Exception as e:
            self._error = str(e)
            print(f"[PiperTTS] Unload failed: {e}")
            return False

    def _get_voice(self, voice_id: str):
        """Get or load a voice model."""
        if voice_id in self._loaded_voices:
            return self._loaded_voices[voice_id]

        try:
            from piper import PiperVoice
            import torch

            onnx_path = os.path.join(self._voices_dir, f"{voice_id}.onnx")
            json_path = os.path.join(self._voices_dir, f"{voice_id}.onnx.json")

            if not os.path.exists(onnx_path):
                raise FileNotFoundError(f"Voice model not found: {onnx_path}")

            print(f"[PiperTTS] Loading voice: {voice_id}")
            voice = PiperVoice.load(
                onnx_path,
                config_path=json_path if os.path.exists(json_path) else None,
                use_cuda=torch.cuda.is_available()
            )

            # LRU eviction if too many voices cached
            if len(self._loaded_voices) >= self._max_voices_cached:
                oldest = next(iter(self._loaded_voices))
                del self._loaded_voices[oldest]
                print(f"[PiperTTS] Evicted voice: {oldest}")

            self._loaded_voices[voice_id] = voice
            return voice

        except Exception as e:
            print(f"[PiperTTS] Failed to load voice {voice_id}: {e}")
            raise

    def get_available_voices(self) -> List[str]:
        """Get list of available voice IDs."""
        voices = []
        if os.path.exists(self._voices_dir):
            for f in os.listdir(self._voices_dir):
                if f.endswith('.onnx'):
                    voice_id = f.replace('.onnx', '')
                    voices.append(voice_id)
        return sorted(voices)

    def generate(
        self,
        prompt: str,
        duration: float,  # Ignored for TTS - duration is determined by text
        output_path: str,
        voice_id: str = "en_US-lessac-medium",
        **kwargs
    ) -> GenerationResult:
        """Generate speech from text."""
        if not self.is_loaded():
            raise GenerationError("Model not loaded")

        self._mark_used()

        try:
            # Get or load the voice model
            voice = self._get_voice(voice_id)

            # Generate speech
            print(f"[PiperTTS] Generating: {prompt[:50]}... (voice: {voice_id})")

            # Ensure output has .wav extension
            if not output_path.endswith('.wav'):
                output_path = output_path + '.wav'

            with wave.open(output_path, 'wb') as wav_file:
                voice.synthesize(prompt, wav_file)

            # Get actual duration from generated file
            with wave.open(output_path, 'rb') as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                actual_duration = frames / float(rate)
                self._sample_rate = rate

            return GenerationResult(
                audio_path=output_path,
                sample_rate=self._sample_rate,
                duration=actual_duration,
                metadata={
                    'prompt': prompt,
                    'model': self.model_id,
                    'voice_id': voice_id,
                    'text_length': len(prompt),
                }
            )

        except FileNotFoundError as e:
            error_msg = f"Voice not found: {voice_id}"
            print(f"[PiperTTS] {error_msg}")
            return GenerationResult(
                audio_path="",
                sample_rate=self._sample_rate,
                duration=0,
                error=error_msg
            )

        except Exception as e:
            print(f"[PiperTTS] Generation failed: {e}")
            return GenerationResult(
                audio_path="",
                sample_rate=self._sample_rate,
                duration=0,
                error=str(e)
            )
