#!/usr/bin/env python3
"""
Demo: Capability-based model selection

Shows how to get models by capability without knowing specific model IDs.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from plugins import ModelManager, ModelCapability

def main():
    print("\n" + "="*60)
    print("  Capability-Based Model Selection Demo")
    print("="*60)

    manager = ModelManager(min_free_memory_gb=2.0)

    try:
        # Test 1: Get a music model (any)
        print("\n--- Test 1: Request any MUSIC model ---")
        print("Calling: manager.get_model_for_capability(ModelCapability.MUSIC)")

        start = time.time()
        music_model = manager.get_model_for_capability(ModelCapability.MUSIC)

        if music_model:
            print(f"✓ Got: {music_model.model_id} ({music_model.display_name})")
            print(f"  Load time: {time.time() - start:.1f}s")

            # Generate
            output = "generated/demo_music.wav"
            result = music_model.generate(
                "upbeat electronic dance music",
                duration=5.0,
                output_path=output,
            )
            if result.success:
                print(f"✓ Generated: {result.audio_path} ({result.duration}s)")

        # Test 2: Get an SFX model
        print("\n--- Test 2: Request any SFX model ---")
        print("Calling: manager.get_model_for_capability(ModelCapability.SFX)")

        # First unload music to free memory
        manager.unload_all()
        print("(Unloaded previous models)")

        start = time.time()
        sfx_model = manager.get_model_for_capability(ModelCapability.SFX)

        if sfx_model:
            print(f"✓ Got: {sfx_model.model_id} ({sfx_model.display_name})")
            print(f"  Load time: {time.time() - start:.1f}s")

            # Generate SFX
            output = "generated/demo_sfx.wav"
            result = sfx_model.generate(
                "thunder rumbling in the distance with rain",
                duration=5.0,
                output_path=output,
            )
            if result.success:
                print(f"✓ Generated: {result.audio_path} ({result.duration}s)")

        # Test 3: Get TTS model (commercial safe)
        print("\n--- Test 3: Request any TTS model (prefer commercial) ---")
        print("Calling: manager.get_model_for_capability(ModelCapability.TTS, prefer_commercial=True)")

        manager.unload_all()

        start = time.time()
        tts_model = manager.get_model_for_capability(
            ModelCapability.TTS,
            prefer_commercial=True
        )

        if tts_model:
            print(f"✓ Got: {tts_model.model_id} ({tts_model.display_name})")
            print(f"  Load time: {time.time() - start:.1f}s")

            # List available voices
            if hasattr(tts_model, 'get_available_voices'):
                voices = tts_model.get_available_voices()
                print(f"  Available voices: {voices[:5]}..." if len(voices) > 5 else f"  Available voices: {voices}")

        # Show final status
        print("\n--- Final Status ---")
        status = manager.get_status()
        print(f"Models loaded: {list(status['loaded'].keys())}")
        print(f"Free GPU memory: {status['free_memory_gb']} GB")

    finally:
        manager.shutdown()
        print("\n✓ Demo complete!")

if __name__ == "__main__":
    main()
