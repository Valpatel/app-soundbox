#!/usr/bin/env python3
"""
Bulk Audio Generation Script

Generates 50,000 audio files with proper tagging:
- 35,000 speech clips using Piper TTS
- 15,000 SFX clips using AudioGen

Features:
- Deterministic tagging (no LLM guessing)
- Resume capability via progress tracking
- Multi-speaker VCTK support with accurate gender tagging
- Rate-limited to prevent system overload

Usage:
    python scripts/generate_bulk_library.py [--speech-only] [--sfx-only] [--test N]
"""

import os
import sys
import json
import time
import wave
import uuid
import random
import signal
import argparse
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'prompt_libraries'))

# Import local modules
import database as db
from speech_templates import get_all_prompts as get_speech_prompts, CATEGORY_DISTRIBUTION as SPEECH_CATEGORIES
from sfx_templates import get_all_sfx_prompts, CATEGORY_DISTRIBUTION as SFX_CATEGORIES
from voice_metadata import (
    VOICE_METADATA, get_vctk_gender, get_voice_tags,
    VCTK_FEMALE_SPEAKERS, VCTK_MALE_SPEAKERS
)

# Try to import Piper TTS
try:
    from piper import PiperVoice
    from piper.config import SynthesisConfig
    import torch
    HAS_PIPER = True
except ImportError:
    print("Warning: Piper TTS not available. Speech generation disabled.")
    HAS_PIPER = False

# Configuration
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'generated')
VOICES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'voices')
PROGRESS_FILE = os.path.join(os.path.dirname(__file__), 'generation_progress.json')

# Global progress reference for signal handlers
_current_progress = None


def _signal_handler(signum, frame):
    """Save progress on interrupt signals."""
    global _current_progress
    print(f"\n\nReceived signal {signum}, saving progress...")
    if _current_progress is not None:
        save_progress(_current_progress)
        print(f"Progress saved: {_current_progress.get('speech_generated', 0)} speech clips")
    sys.exit(0)


# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# Voice configurations for generation
VOICE_CONFIGS = [
    {
        'voice_id': 'en_GB-jenny_dioco-medium',
        'speaker_id': None,
        'gender': 'female',
        'accent': 'british',
        'name': 'Jenny Dioco',
        'weight': 12,  # Relative generation weight
    },
    {
        'voice_id': 'en_US-sam-medium',
        'speaker_id': None,
        'gender': 'male',
        'accent': 'american',
        'name': 'Sam',
        'weight': 12,
    },
    {
        'voice_id': 'en_US-kusal-medium',
        'speaker_id': None,
        'gender': 'male',
        'accent': 'american',
        'name': 'Kusal',
        'weight': 11,
    },
    # VCTK female speakers (British)
    {
        'voice_id': 'en_GB-vctk-medium',
        'speaker_id': 0,  # p239 - female
        'gender': 'female',
        'accent': 'british',
        'name': 'VCTK-p239',
        'weight': 2,
    },
    {
        'voice_id': 'en_GB-vctk-medium',
        'speaker_id': 1,  # p236 - female
        'gender': 'female',
        'accent': 'british',
        'name': 'VCTK-p236',
        'weight': 2,
    },
    {
        'voice_id': 'en_GB-vctk-medium',
        'speaker_id': 14,  # p277 - female
        'gender': 'female',
        'accent': 'british',
        'name': 'VCTK-p277',
        'weight': 2,
    },
    # VCTK male speakers (British)
    {
        'voice_id': 'en_GB-vctk-medium',
        'speaker_id': 4,  # p259 - male
        'gender': 'male',
        'accent': 'british',
        'name': 'VCTK-p259',
        'weight': 2,
    },
    {
        'voice_id': 'en_GB-vctk-medium',
        'speaker_id': 7,  # p263 - male
        'gender': 'male',
        'accent': 'british',
        'name': 'VCTK-p263',
        'weight': 2,
    },
    {
        'voice_id': 'en_GB-vctk-medium',
        'speaker_id': 8,  # p283 - male
        'gender': 'male',
        'accent': 'british',
        'name': 'VCTK-p283',
        'weight': 2,
    },
]

# Voice model cache
_voice_models = {}


def get_voice_model(voice_id):
    """Load and cache a Piper voice model."""
    if voice_id in _voice_models:
        return _voice_models[voice_id]

    onnx_path = os.path.join(VOICES_DIR, f"{voice_id}.onnx")
    json_path = os.path.join(VOICES_DIR, f"{voice_id}.onnx.json")

    if not os.path.exists(onnx_path):
        print(f"Voice model not found: {onnx_path}")
        return None

    try:
        use_cuda = torch.cuda.is_available()
        print(f"Loading voice: {voice_id} (CUDA: {use_cuda})")
        voice = PiperVoice.load(onnx_path, config_path=json_path, use_cuda=use_cuda)
        _voice_models[voice_id] = voice
        return voice
    except Exception as e:
        print(f"Failed to load voice {voice_id}: {e}")
        return None


def load_progress():
    """Load generation progress from file."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        'speech_generated': 0,
        'sfx_generated': 0,
        'generated_hashes': [],  # Track generated prompts to avoid duplicates
        'started_at': datetime.now().isoformat(),
        'last_update': datetime.now().isoformat(),
    }


def save_progress(progress):
    """Save generation progress to file."""
    progress['last_update'] = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def get_prompt_hash(text, voice_id, speaker_id):
    """Create a hash for tracking generated prompts."""
    import hashlib
    key = f"{text}|{voice_id}|{speaker_id}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


def check_db_duplicate(text, voice_id, speaker_id=None):
    """Check if this prompt+voice+speaker combination already exists in the database.

    For multi-speaker voices like VCTK, we need to check speaker_id too.
    We store speaker_id in the category JSON for tracking.
    """
    try:
        with db.get_db() as conn:
            if speaker_id is not None:
                # For multi-speaker voices, check the category JSON for speaker info
                cursor = conn.execute(
                    """SELECT COUNT(*) FROM generations
                       WHERE prompt = ? AND voice_id = ? AND model = 'voice'
                       AND category LIKE ?""",
                    (text[:200], voice_id, f'%"speaker_{speaker_id}"%')
                )
            else:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM generations WHERE prompt = ? AND voice_id = ? AND model = 'voice'",
                    (text[:200], voice_id)
                )
            count = cursor.fetchone()[0]
            return count > 0
    except Exception as e:
        print(f"Error checking duplicate: {e}")
        return False


def generate_speech_clip(voice, voice_config, prompt_data, progress):
    """Generate a single speech clip."""
    text = prompt_data['text']
    category = prompt_data['category']
    voice_id = voice_config['voice_id']
    speaker_id = voice_config['speaker_id']
    gender = voice_config['gender']
    accent = voice_config['accent']
    voice_name = voice_config['name']

    # Check if already generated (progress file)
    prompt_hash = get_prompt_hash(text, voice_id, speaker_id)
    if prompt_hash in progress['generated_hashes']:
        return None

    # Also check the database for duplicates (prevents re-generation after progress file reset)
    if check_db_duplicate(text, voice_id, speaker_id):
        # Add to progress hashes to avoid repeated DB checks
        progress['generated_hashes'].append(prompt_hash)
        return None

    # Generate unique ID and filename
    gen_id = uuid.uuid4().hex
    filename = f"tts_{gen_id}.wav"
    filepath = os.path.join(OUTPUT_DIR, filename)

    try:
        # Generate audio using synthesize_wav
        # Create SynthesisConfig for multi-speaker voices
        syn_config = SynthesisConfig(speaker_id=speaker_id) if speaker_id is not None else None

        with wave.open(filepath, 'wb') as wav_file:
            voice.synthesize_wav(text, wav_file, syn_config=syn_config)

        # Get duration
        import scipy.io.wavfile as wav_reader
        sample_rate, audio_data = wav_reader.read(filepath)
        duration = len(audio_data) / sample_rate

        # Build deterministic tags (no auto-categorization)
        tags = [gender, accent, category]
        if 'vctk' in voice_id.lower():
            tags.append('vctk')
        # Add speaker_id to tags for multi-speaker voices (enables proper duplicate detection)
        if speaker_id is not None:
            tags.append(f'speaker_{speaker_id}')

        # Insert directly to bypass auto-categorization
        # This ensures we only use our deterministic tags
        import json as json_module
        category_json = json_module.dumps(tags)

        with db.get_db() as conn:
            conn.execute("""
                INSERT INTO generations
                (id, filename, prompt, model, duration, is_loop, quality_score, spectrogram, user_id, category, is_public, admin_reviewed, voice_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (gen_id, filename, text[:200], 'voice', duration, False, None, None, None, category_json, True, True, voice_id))
            conn.commit()

        # Update progress
        progress['generated_hashes'].append(prompt_hash)
        progress['speech_generated'] += 1

        return {
            'gen_id': gen_id,
            'filename': filename,
            'duration': duration,
            'category': category,
            'voice': voice_name,
            'gender': gender,
        }

    except Exception as e:
        # Clean up partial file
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        print(f"Error generating speech: {e}")
        return None


def generate_speech_batch(target_count=35000, test_mode=None, verbose=False):
    """
    Generate speech clips in batch.

    Strategy: Generate each prompt with MULTIPLE voices to maximize coverage.
    Each category gets clips from every voice for better variety.
    """
    if not HAS_PIPER:
        print("Piper TTS not available. Skipping speech generation.")
        return

    print(f"\n{'='*60}")
    print(f"SPEECH GENERATION - Target: {target_count} clips")
    print(f"{'='*60}\n")

    # Load progress and set global reference for signal handlers
    global _current_progress
    progress = load_progress()
    _current_progress = progress
    start_count = progress['speech_generated']

    if test_mode:
        # In test mode, generate N new clips from current position
        target_count = start_count + test_mode
        print(f"TEST MODE: Generating {test_mode} new clips (target: {target_count})")

    # Get prompts grouped by category
    prompts = get_speech_prompts()

    # Group prompts by category for balanced distribution
    prompts_by_category = {}
    for p in prompts:
        cat = p['category']
        if cat not in prompts_by_category:
            prompts_by_category[cat] = []
        prompts_by_category[cat].append(p)

    categories = list(prompts_by_category.keys())
    print(f"Categories: {len(categories)}")

    # Pre-load all voice models
    print("\nLoading voice models...")
    loaded_voices = {}
    voice_configs_loaded = []
    for vc in VOICE_CONFIGS:
        vid = vc['voice_id']
        if vid not in loaded_voices:
            voice = get_voice_model(vid)
            if voice:
                loaded_voices[vid] = voice
                print(f"  Loaded: {vid}")
            else:
                print(f"  FAILED: {vid}")
        if vid in loaded_voices:
            voice_configs_loaded.append(vc)

    if not loaded_voices:
        print("No voices loaded. Aborting.")
        return

    print(f"\nVoices available: {len(voice_configs_loaded)}")

    # Generate clips - round robin through categories and voices
    generated = 0
    errors = 0
    skipped = 0
    start_time = time.time()
    last_progress_count = progress['speech_generated']
    stall_iterations = 0
    max_stall_iterations = len(prompts) * len(voice_configs_loaded) * 2  # Allow 2 full cycles before giving up

    print(f"\nStarting generation (resuming from {start_count})...\n")

    # Create a generator that cycles through all category+voice combinations
    category_indices = {cat: 0 for cat in categories}
    voice_idx = 0

    while progress['speech_generated'] < target_count:
        # Cycle through categories
        for cat in categories:
            if progress['speech_generated'] >= target_count:
                break

            # Get next prompt from this category
            cat_prompts = prompts_by_category[cat]
            prompt_idx = category_indices[cat]

            if prompt_idx >= len(cat_prompts):
                # Restart category from beginning with next voice
                prompt_idx = 0

            prompt = cat_prompts[prompt_idx]
            category_indices[cat] = prompt_idx + 1

            # Select voice (rotate through all voices)
            voice_config = voice_configs_loaded[voice_idx % len(voice_configs_loaded)]
            voice_idx += 1

            voice_id = voice_config['voice_id']
            voice = loaded_voices[voice_id]

            result = generate_speech_clip(voice, voice_config, prompt, progress)

            if result:
                generated += 1
                # Save progress frequently (every 25 clips) to minimize loss on crash
                if generated % 25 == 0:
                    save_progress(progress)
                # Print status every 100 clips
                if generated % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = generated / elapsed if elapsed > 0 else 0
                    remaining = target_count - progress['speech_generated']
                    eta = remaining / rate if rate > 0 else 0
                    print(f"[{progress['speech_generated']:,}/{target_count:,}] "
                          f"Rate: {rate:.1f}/s, ETA: {eta/3600:.1f}h - "
                          f"Last: {result['voice']} ({result['gender']}) - {result['category']}")
            else:
                # Check why it failed
                prompt_hash = get_prompt_hash(prompt['text'], voice_id, voice_config['speaker_id'])
                if prompt_hash in progress['generated_hashes']:
                    skipped += 1
                else:
                    errors += 1
                    if verbose and errors <= 10:
                        print(f"  Error on: {prompt['text'][:50]}... with {voice_config['name']}")

            # Brief pause every 50 to prevent overload
            if (generated + errors + skipped) % 50 == 0:
                time.sleep(0.01)

            # Track stall detection - if no progress in many iterations, break
            stall_iterations += 1

        # Safety check: if we've cycled through all combinations without progress, break
        current_progress = progress['speech_generated']
        if current_progress > last_progress_count:
            # Made progress, reset stall counter
            stall_iterations = 0
            last_progress_count = current_progress
        elif stall_iterations >= max_stall_iterations:
            print(f"\nWARNING: No new clips generated in {stall_iterations} iterations.")
            print(f"All {current_progress} unique prompt+voice combinations exhausted.")
            print("To generate more clips, add more prompts or voice configurations.")
            break

    # Final save
    save_progress(progress)

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"SPEECH GENERATION COMPLETE")
    print(f"Generated: {generated} clips")
    print(f"Skipped (already exists): {skipped}")
    print(f"Errors: {errors}")
    print(f"Total in library: {progress['speech_generated']}")
    print(f"Time: {elapsed/3600:.2f} hours")
    print(f"{'='*60}\n")


def generate_sfx_clip(model, prompt_data, progress, sample_rate=16000):
    """Generate a single SFX clip using AudioGen."""
    import numpy as np
    import scipy.io.wavfile as wavfile

    text = prompt_data['text']
    category = prompt_data['category']

    # Check if already generated
    prompt_hash = get_prompt_hash(text, 'audiogen', None)
    if prompt_hash in progress.get('sfx_hashes', []):
        return None

    # Generate unique ID and filename
    gen_id = uuid.uuid4().hex
    filename = f"sfx_{gen_id}.wav"
    filepath = os.path.join(OUTPUT_DIR, filename)

    try:
        # Generate audio with AudioGen
        model.set_generation_params(duration=5.0)  # 5 second clips
        wav = model.generate([text])
        audio_out = wav[0]

        # Convert to numpy and save using scipy (avoids TorchCodec dependency)
        audio_np = audio_out.cpu().numpy()
        # Normalize to int16 range for WAV
        if audio_np.max() > 1.0 or audio_np.min() < -1.0:
            audio_np = audio_np / max(abs(audio_np.max()), abs(audio_np.min()))
        audio_int16 = (audio_np * 32767).astype(np.int16)
        # Handle mono vs stereo
        if len(audio_int16.shape) == 2 and audio_int16.shape[0] == 1:
            audio_int16 = audio_int16[0]  # Squeeze to mono
        wavfile.write(filepath, sample_rate, audio_int16)

        # Get actual duration
        duration = audio_out.shape[-1] / sample_rate

        # Build deterministic tags
        tags = [category]

        # Insert directly to bypass auto-categorization
        import json as json_module
        category_json = json_module.dumps(tags)

        with db.get_db() as conn:
            conn.execute("""
                INSERT INTO generations
                (id, filename, prompt, model, duration, is_loop, quality_score, spectrogram, user_id, category, is_public, admin_reviewed, voice_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (gen_id, filename, text[:200], 'audio', duration, False, None, None, None, category_json, True, True, None))
            conn.commit()

        # Update progress
        if 'sfx_hashes' not in progress:
            progress['sfx_hashes'] = []
        progress['sfx_hashes'].append(prompt_hash)
        progress['sfx_generated'] += 1

        return {
            'gen_id': gen_id,
            'filename': filename,
            'duration': duration,
            'category': category,
        }

    except Exception as e:
        # Clean up partial file
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        print(f"Error generating SFX: {e}")
        return None


def generate_sfx_batch(target_count=15000, test_mode=None):
    """Generate SFX clips in batch using AudioGen."""
    print(f"\n{'='*60}")
    print(f"SFX GENERATION - Target: {target_count} clips")
    print(f"{'='*60}\n")

    # Try to import AudioGen
    try:
        from audiocraft.models import AudioGen
        import torchaudio
    except ImportError:
        print("AudioGen not available. Install with: pip install audiocraft")
        print("Skipping SFX generation.\n")
        return

    # Load progress and set global reference for signal handlers
    global _current_progress
    progress = load_progress()
    _current_progress = progress
    start_count = progress['sfx_generated']

    if test_mode:
        # In test mode, generate N new clips from current position
        target_count = start_count + test_mode
        print(f"TEST MODE: Generating {test_mode} new clips (target: {target_count})")

    # Load AudioGen model
    print("Loading AudioGen model...")
    try:
        model = AudioGen.get_pretrained('facebook/audiogen-medium')
        sample_rate = model.sample_rate
        print(f"  AudioGen loaded! (sample_rate: {sample_rate})")
    except Exception as e:
        print(f"  Failed to load AudioGen: {e}")
        return

    # Get prompts
    prompts = get_all_sfx_prompts()
    random.shuffle(prompts)

    # Generate clips
    generated = 0
    errors = 0
    start_time = time.time()

    print(f"\nStarting SFX generation (resuming from {start_count})...\n")

    for i, prompt in enumerate(prompts):
        if progress['sfx_generated'] >= target_count:
            break

        result = generate_sfx_clip(model, prompt, progress, sample_rate)

        if result:
            generated += 1
            if generated % 10 == 0:  # AudioGen is slower, report every 10
                elapsed = time.time() - start_time
                rate = generated / elapsed if elapsed > 0 else 0
                eta = (target_count - progress['sfx_generated']) / rate if rate > 0 else 0
                print(f"[{progress['sfx_generated']:,}/{target_count:,}] "
                      f"Rate: {rate:.2f}/s, ETA: {eta/3600:.1f}h - "
                      f"Category: {result['category']}")
                save_progress(progress)
        else:
            errors += 1

    # Final save
    save_progress(progress)

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"SFX GENERATION COMPLETE")
    print(f"Generated: {generated} clips")
    print(f"Errors: {errors}")
    print(f"Total in library: {progress['sfx_generated']}")
    print(f"Time: {elapsed/3600:.2f} hours")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description='Bulk audio generation')
    parser.add_argument('--speech-only', action='store_true', help='Only generate speech')
    parser.add_argument('--sfx-only', action='store_true', help='Only generate SFX')
    parser.add_argument('--test', type=int, metavar='N', help='Test mode: generate N clips only')
    parser.add_argument('--reset', action='store_true', help='Reset progress and start fresh')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose error output')
    args = parser.parse_args()

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Initialize database
    db.init_db()

    # Reset progress if requested
    if args.reset and os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        print("Progress reset.")

    print(f"\n{'#'*60}")
    print(f"# BULK AUDIO GENERATION")
    print(f"# Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")

    # Load and display progress
    progress = load_progress()
    print(f"\nCurrent progress:")
    print(f"  Speech: {progress['speech_generated']:,} clips")
    print(f"  SFX: {progress['sfx_generated']:,} clips")

    # Generate
    if not args.sfx_only:
        generate_speech_batch(target_count=35000, test_mode=args.test, verbose=args.verbose)
        # Clear GPU memory after speech generation
        if torch.cuda.is_available():
            _voice_models.clear()
            torch.cuda.empty_cache()
            print("\nCleared GPU memory for SFX generation.")

    if not args.speech_only:
        generate_sfx_batch(target_count=15000, test_mode=args.test)

    print(f"\n{'#'*60}")
    print(f"# GENERATION COMPLETE")
    print(f"# Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}\n")


if __name__ == '__main__':
    main()
