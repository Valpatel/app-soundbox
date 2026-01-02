# Model Adapters for SoundBox
# Each adapter wraps an AI model to provide a consistent interface

# Import adapters to trigger registration with ModelRegistry
# Adapters use the @ModelRegistry.register decorator

from . import musicgen
from . import audiogen
from . import magnet
from . import piper_tts

__all__ = [
    'musicgen',
    'audiogen',
    'magnet',
    'piper_tts',
]
