#!/usr/bin/env python3
"""
Demo script for SoundBox Plugin System

This script demonstrates the plugin system working with real models.
Run with: python demo_plugins.py
"""

import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)

def print_section(text):
    print(f"\n--- {text} ---")

def main():
    print_header("SoundBox Plugin System Demo")

    # Import the plugin system
    print_section("1. Importing Plugin System")
    from plugins import ModelRegistry, ModelManager, ModelCapability
    print("✓ Plugin system imported successfully")

    # Show registered models
    print_section("2. Registered Models")
    all_models = ModelRegistry.list_all()
    print(f"Found {len(all_models)} registered models:\n")

    for model_id in all_models:
        info = ModelRegistry.get(model_id)
        status = "✓" if info.enabled else "✗"
        commercial = "💰" if info.commercial_ok else "🔒"
        caps = ", ".join(c.value for c in info.capabilities)
        print(f"  {status} {model_id}")
        print(f"      Display: {info.display_name}")
        print(f"      Memory: {info.memory_gb}GB | License: {info.license} {commercial}")
        print(f"      Capabilities: [{caps}]")
        print()

    # Filter by capability
    print_section("3. Filter by Capability")

    music_models = ModelRegistry.list_by_capability(ModelCapability.MUSIC)
    print(f"Music models: {music_models}")

    sfx_models = ModelRegistry.list_by_capability(ModelCapability.SFX)
    print(f"SFX models: {sfx_models}")

    tts_models = ModelRegistry.list_by_capability(ModelCapability.TTS)
    print(f"TTS models: {tts_models}")

    # Commercial-safe models
    print_section("4. Commercial-Safe Models")
    safe_models = ModelRegistry.list_commercial_safe()
    print(f"Safe for commercial use: {safe_models}")
    if not safe_models:
        print("(Note: Current models use CC-BY-NC weights)")

    # Create model manager
    print_section("5. Model Manager Status")
    manager = ModelManager(
        min_free_memory_gb=2.0,
        idle_timeout_seconds=300,
        max_loaded_models=2,
    )

    status = manager.get_status()
    print(f"Free GPU memory: {status['free_memory_gb']} GB")
    print(f"Loaded models: {status['loaded']}")
    print(f"Available models: {len(status['available'])}")

    # Try to load a real model
    print_section("6. Loading a Real Model")

    # Try MusicGen small first (most likely to fit in memory)
    model_to_load = "musicgen-small"
    print(f"Attempting to load: {model_to_load}")
    print("This may take a minute on first run (downloading weights)...")

    start = time.time()
    model = manager.get_model(model_to_load, wait_for_memory=True, timeout=300)
    elapsed = time.time() - start

    if model:
        print(f"✓ Model loaded in {elapsed:.1f}s")
        print(f"  Model ID: {model.model_id}")
        print(f"  Display Name: {model.display_name}")
        print(f"  Sample Rate: {model.sample_rate} Hz")
        print(f"  Max Duration: {model.max_duration_seconds}s")

        # Show updated status
        status = manager.get_status()
        print(f"\nManager status after load:")
        print(f"  Loaded models: {list(status['loaded'].keys())}")
        print(f"  Free GPU memory: {status['free_memory_gb']} GB")

        # Generate audio!
        print_section("7. Generating Audio")

        output_dir = "generated"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "plugin_demo_output.wav")

        prompt = "peaceful ambient piano music with soft pads"
        duration = 5.0

        print(f"Prompt: '{prompt}'")
        print(f"Duration: {duration}s")
        print("Generating...")

        start = time.time()
        result = model.generate(
            prompt=prompt,
            duration=duration,
            output_path=output_path,
        )
        elapsed = time.time() - start

        if result.success:
            print(f"\n✓ Generation successful!")
            print(f"  Output: {result.audio_path}")
            print(f"  Duration: {result.duration}s")
            print(f"  Sample Rate: {result.sample_rate} Hz")
            print(f"  Generation Time: {elapsed:.1f}s")
            print(f"  Metadata: {result.metadata}")

            # Check file exists
            if os.path.exists(result.audio_path):
                size = os.path.getsize(result.audio_path)
                print(f"  File Size: {size:,} bytes")

        else:
            print(f"\n✗ Generation failed: {result.error}")

        # Unload model
        print_section("8. Unloading Model")
        manager.unload_model(model_to_load)
        print(f"✓ Model unloaded")

        status = manager.get_status()
        print(f"Free GPU memory after unload: {status['free_memory_gb']} GB")

    else:
        print(f"✗ Failed to load model (insufficient GPU memory or model unavailable)")
        print("Try running on a machine with more VRAM or check CUDA setup")

    # Cleanup
    print_section("9. Shutdown")
    manager.shutdown()
    print("✓ Manager shutdown complete")

    print_header("Demo Complete!")

    if model and result.success:
        print(f"\n🎵 Generated audio saved to: {result.audio_path}")
        print("   Play it with: aplay " + result.audio_path)

if __name__ == "__main__":
    main()
