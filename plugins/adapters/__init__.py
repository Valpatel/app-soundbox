# Model Adapters for SoundBox
# Each adapter wraps an AI model to provide a consistent interface

# Import adapters to trigger registration with ModelRegistry
# Adapters use the @ModelRegistry.register decorator

# Meta AudioCraft models (CC-BY-NC weights)
from . import musicgen
from . import audiogen
from . import magnet

# Alternative models (various licenses)
from . import stable_audio   # Stability AI Community License
from . import bark_audio     # MIT - fully commercial safe

# TTS models
from . import piper_tts      # MIT
from . import kokoro_tts     # Apache 2.0

__all__ = [
    # AudioCraft
    'musicgen',
    'audiogen',
    'magnet',
    # Alternatives
    'stable_audio',
    'bark_audio',
    # TTS
    'piper_tts',
    'kokoro_tts',
]
