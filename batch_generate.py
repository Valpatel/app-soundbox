#!/usr/bin/env python3
"""
Batch Content Generator for Sound Box
Generates content for empty categories using parallel SFX/Music generation.

Usage:
    python batch_generate.py                    # Run with defaults (fills empty categories)
    python batch_generate.py --sfx-only         # Generate only SFX
    python batch_generate.py --music-only       # Generate only music
    python batch_generate.py --category jazz    # Generate for specific category
    python batch_generate.py --count 100        # Generate 100 items per category
    python batch_generate.py --parallel         # Run SFX and Music in parallel (default)
    python batch_generate.py --sequential       # Alternate 20 SFX then 1 music

The script uses the /generate API endpoint and can run both models in parallel
since MusicGen and AudioGen use different model weights.
"""

import argparse
import requests
import time
import random
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Import our prompts
from prompts import MUSIC_PROMPTS, SFX_PROMPTS, get_category_stats

# Configuration
API_BASE = "http://localhost:5309"
DEFAULT_MUSIC_DURATION = 30  # seconds
DEFAULT_SFX_DURATION = 5     # seconds
MAX_RETRIES = 3
POLL_INTERVAL = 2  # seconds between status checks


class BatchGenerator:
    def __init__(self, base_url=API_BASE):
        self.base_url = base_url
        self.stats = {
            'music_generated': 0,
            'sfx_generated': 0,
            'music_failed': 0,
            'sfx_failed': 0,
            'start_time': None,
            'end_time': None
        }
        self.lock = threading.Lock()

    def check_server(self):
        """Verify server is running and models are loaded."""
        try:
            resp = requests.get(f"{self.base_url}/api/library/counts", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                print(f"[OK] Server is running. Library: {data['total']} items "
                      f"({data['music']} music, {data['audio']} SFX)")
                return True
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Cannot connect to server: {e}")
            return False
        return False

    def generate_one(self, prompt, model, duration, priority='standard'):
        """Generate a single audio file and wait for completion."""
        try:
            # Submit generation request
            resp = requests.post(
                f"{self.base_url}/generate",
                json={
                    'prompt': prompt,
                    'duration': duration,
                    'model': model,
                    'loop': model == 'music',  # Loop music, not SFX
                    'priority': priority
                },
                timeout=30
            )

            if resp.status_code != 200:
                print(f"[FAIL] API error: {resp.status_code}")
                return None

            data = resp.json()
            job_id = data.get('job_id')

            if not job_id:
                print(f"[FAIL] No job_id returned")
                return None

            # Poll for completion using /job/{job_id} endpoint
            max_wait = duration * 4 + 120  # Allow 4x duration + 2 min buffer
            waited = 0

            while waited < max_wait:
                try:
                    status_resp = requests.get(
                        f"{self.base_url}/job/{job_id}",
                        timeout=10
                    )
                    if status_resp.status_code == 200:
                        status = status_resp.json()
                        job_status = status.get('status', '')

                        if job_status == 'completed':
                            return status.get('filename')
                        elif job_status == 'failed':
                            print(f"[FAIL] Generation failed: {status.get('error', 'Unknown')}")
                            return None
                        # Still processing (queued, processing, etc.)

                except requests.exceptions.RequestException:
                    pass  # Ignore transient errors

                time.sleep(POLL_INTERVAL)
                waited += POLL_INTERVAL

            print(f"[TIMEOUT] Generation timed out after {max_wait}s")
            return None

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Request failed: {e}")
            return None

    def generate_for_category(self, category, prompts, model, duration, count=None):
        """Generate content for a single category."""
        model_type = 'music' if model == 'music' else 'sfx'

        if count is None:
            count = len(prompts)
        else:
            count = min(count, len(prompts))

        # Shuffle prompts for variety
        selected = random.sample(prompts, count)

        print(f"\n[{model_type.upper()}] Generating {count} items for '{category}'")

        success = 0
        for i, prompt in enumerate(selected, 1):
            short_prompt = prompt[:50] + "..." if len(prompt) > 50 else prompt
            print(f"  [{i}/{count}] {short_prompt}")

            result = self.generate_one(prompt, model, duration)

            if result:
                success += 1
                with self.lock:
                    if model == 'music':
                        self.stats['music_generated'] += 1
                    else:
                        self.stats['sfx_generated'] += 1
                print(f"    ✓ Generated: {result}")
            else:
                with self.lock:
                    if model == 'music':
                        self.stats['music_failed'] += 1
                    else:
                        self.stats['sfx_failed'] += 1
                print(f"    ✗ Failed")

            # Small delay between requests
            time.sleep(0.5)

        return success

    def run_parallel(self, music_categories=None, sfx_categories=None,
                     count_per_category=20, music_duration=DEFAULT_MUSIC_DURATION,
                     sfx_duration=DEFAULT_SFX_DURATION):
        """
        Run music and SFX generation in parallel using separate threads.
        Since MusicGen and AudioGen use different models, they can run concurrently.
        """
        self.stats['start_time'] = datetime.now()

        if music_categories is None:
            music_categories = list(MUSIC_PROMPTS.keys())
        if sfx_categories is None:
            sfx_categories = list(SFX_PROMPTS.keys())

        print(f"\n{'='*60}")
        print("PARALLEL BATCH GENERATION")
        print(f"{'='*60}")
        print(f"Music categories: {len(music_categories)}")
        print(f"SFX categories: {len(sfx_categories)}")
        print(f"Items per category: {count_per_category}")
        print(f"Music duration: {music_duration}s, SFX duration: {sfx_duration}s")
        print(f"{'='*60}\n")

        def music_worker():
            """Generate all music content."""
            for category in music_categories:
                prompts = MUSIC_PROMPTS.get(category, [])
                if prompts:
                    self.generate_for_category(
                        category, prompts, 'music',
                        music_duration, count_per_category
                    )

        def sfx_worker():
            """Generate all SFX content."""
            for category in sfx_categories:
                prompts = SFX_PROMPTS.get(category, [])
                if prompts:
                    self.generate_for_category(
                        category, prompts, 'audio',
                        sfx_duration, count_per_category
                    )

        # Start both workers in parallel
        music_thread = threading.Thread(target=music_worker, name='MusicWorker')
        sfx_thread = threading.Thread(target=sfx_worker, name='SFXWorker')

        music_thread.start()
        sfx_thread.start()

        # Wait for both to complete
        music_thread.join()
        sfx_thread.join()

        self.stats['end_time'] = datetime.now()
        self.print_summary()

    def run_sequential(self, music_categories=None, sfx_categories=None,
                       count_per_category=20, sfx_batch_size=20,
                       music_duration=DEFAULT_MUSIC_DURATION,
                       sfx_duration=DEFAULT_SFX_DURATION):
        """
        Run generation in alternating pattern: 20 SFX, then 1 music.
        This prioritizes lower CPU usage (SFX is faster).
        """
        self.stats['start_time'] = datetime.now()

        if music_categories is None:
            music_categories = list(MUSIC_PROMPTS.keys())
        if sfx_categories is None:
            sfx_categories = list(SFX_PROMPTS.keys())

        print(f"\n{'='*60}")
        print("SEQUENTIAL BATCH GENERATION (20 SFX : 1 Music)")
        print(f"{'='*60}")
        print(f"Music categories: {len(music_categories)}")
        print(f"SFX categories: {len(sfx_categories)}")
        print(f"Items per category: {count_per_category}")
        print(f"{'='*60}\n")

        # Build queues of work
        sfx_queue = []
        for cat in sfx_categories:
            prompts = SFX_PROMPTS.get(cat, [])
            selected = random.sample(prompts, min(count_per_category, len(prompts)))
            for prompt in selected:
                sfx_queue.append((cat, prompt))

        music_queue = []
        for cat in music_categories:
            prompts = MUSIC_PROMPTS.get(cat, [])
            selected = random.sample(prompts, min(count_per_category, len(prompts)))
            for prompt in selected:
                music_queue.append((cat, prompt))

        random.shuffle(sfx_queue)
        random.shuffle(music_queue)

        print(f"Total SFX to generate: {len(sfx_queue)}")
        print(f"Total Music to generate: {len(music_queue)}")

        sfx_idx = 0
        music_idx = 0
        batch_count = 0

        while sfx_idx < len(sfx_queue) or music_idx < len(music_queue):
            # Generate batch of SFX
            sfx_batch_done = 0
            while sfx_batch_done < sfx_batch_size and sfx_idx < len(sfx_queue):
                cat, prompt = sfx_queue[sfx_idx]
                short_prompt = prompt[:40] + "..." if len(prompt) > 40 else prompt
                print(f"[SFX {sfx_idx+1}/{len(sfx_queue)}] {cat}: {short_prompt}")

                result = self.generate_one(prompt, 'audio', sfx_duration)
                if result:
                    self.stats['sfx_generated'] += 1
                    print(f"  ✓ {result}")
                else:
                    self.stats['sfx_failed'] += 1
                    print(f"  ✗ Failed")

                sfx_idx += 1
                sfx_batch_done += 1
                time.sleep(0.3)

            # Generate one music track
            if music_idx < len(music_queue):
                cat, prompt = music_queue[music_idx]
                short_prompt = prompt[:40] + "..." if len(prompt) > 40 else prompt
                print(f"\n[MUSIC {music_idx+1}/{len(music_queue)}] {cat}: {short_prompt}")

                result = self.generate_one(prompt, 'music', music_duration)
                if result:
                    self.stats['music_generated'] += 1
                    print(f"  ✓ {result}")
                else:
                    self.stats['music_failed'] += 1
                    print(f"  ✗ Failed")

                music_idx += 1
                print()

            batch_count += 1

        self.stats['end_time'] = datetime.now()
        self.print_summary()

    def print_summary(self):
        """Print generation summary."""
        duration = self.stats['end_time'] - self.stats['start_time']

        print(f"\n{'='*60}")
        print("GENERATION COMPLETE")
        print(f"{'='*60}")
        print(f"Duration: {duration}")
        print(f"\nMusic:")
        print(f"  Generated: {self.stats['music_generated']}")
        print(f"  Failed: {self.stats['music_failed']}")
        print(f"\nSFX:")
        print(f"  Generated: {self.stats['sfx_generated']}")
        print(f"  Failed: {self.stats['sfx_failed']}")
        print(f"\nTotal: {self.stats['music_generated'] + self.stats['sfx_generated']} generated, "
              f"{self.stats['music_failed'] + self.stats['sfx_failed']} failed")
        print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Batch generate content for Sound Box',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python batch_generate.py                     # Fill all empty categories (parallel)
  python batch_generate.py --sequential        # Alternate 20 SFX then 1 music
  python batch_generate.py --sfx-only          # Generate only SFX
  python batch_generate.py --music-only        # Generate only music
  python batch_generate.py --category jazz     # Generate for specific category
  python batch_generate.py --count 50          # 50 items per category
  python batch_generate.py --dry-run           # Show what would be generated
        """
    )

    parser.add_argument('--parallel', action='store_true', default=True,
                        help='Run SFX and Music generation in parallel (default)')
    parser.add_argument('--sequential', action='store_true',
                        help='Alternate 20 SFX then 1 music track')
    parser.add_argument('--sfx-only', action='store_true',
                        help='Generate only SFX content')
    parser.add_argument('--music-only', action='store_true',
                        help='Generate only music content')
    parser.add_argument('--category', type=str,
                        help='Generate for a specific category only')
    parser.add_argument('--count', type=int, default=20,
                        help='Number of items per category (default: 20)')
    parser.add_argument('--music-duration', type=int, default=30,
                        help='Duration for music tracks in seconds (default: 30)')
    parser.add_argument('--sfx-duration', type=int, default=5,
                        help='Duration for SFX in seconds (default: 5)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be generated without actually generating')
    parser.add_argument('--url', type=str, default=API_BASE,
                        help=f'API base URL (default: {API_BASE})')

    args = parser.parse_args()

    # Determine categories to process
    music_categories = list(MUSIC_PROMPTS.keys()) if not args.sfx_only else []
    sfx_categories = list(SFX_PROMPTS.keys()) if not args.music_only else []

    if args.category:
        if args.category in MUSIC_PROMPTS:
            music_categories = [args.category]
            sfx_categories = []
        elif args.category in SFX_PROMPTS:
            sfx_categories = [args.category]
            music_categories = []
        else:
            print(f"[ERROR] Unknown category: {args.category}")
            print(f"\nAvailable music categories: {', '.join(MUSIC_PROMPTS.keys())}")
            print(f"Available SFX categories: {', '.join(SFX_PROMPTS.keys())}")
            return 1

    # Dry run - show what would be generated
    if args.dry_run:
        stats = get_category_stats()
        print("\n=== DRY RUN - Generation Plan ===\n")

        if music_categories:
            print("MUSIC CATEGORIES:")
            total_music = 0
            for cat in music_categories:
                count = min(args.count, len(MUSIC_PROMPTS[cat]))
                total_music += count
                print(f"  {cat}: {count} tracks @ {args.music_duration}s each")
            print(f"  TOTAL: {total_music} music tracks\n")

        if sfx_categories:
            print("SFX CATEGORIES:")
            total_sfx = 0
            for cat in sfx_categories:
                count = min(args.count, len(SFX_PROMPTS[cat]))
                total_sfx += count
                print(f"  {cat}: {count} sounds @ {args.sfx_duration}s each")
            print(f"  TOTAL: {total_sfx} SFX\n")

        # Estimate time
        music_time = total_music * (args.music_duration * 1.5 + 10) if music_categories else 0
        sfx_time = total_sfx * (args.sfx_duration * 0.5 + 5) if sfx_categories else 0

        if args.sequential:
            total_time = music_time + sfx_time
            print(f"Mode: SEQUENTIAL (20 SFX : 1 Music)")
        else:
            total_time = max(music_time, sfx_time)
            print(f"Mode: PARALLEL (SFX and Music run simultaneously)")

        hours = int(total_time // 3600)
        minutes = int((total_time % 3600) // 60)
        print(f"Estimated time: {hours}h {minutes}m\n")

        return 0

    # Initialize generator
    generator = BatchGenerator(args.url)

    # Check server
    if not generator.check_server():
        print("\n[ERROR] Server is not available. Start it with: ./venv/bin/python3 app.py")
        return 1

    # Run generation
    if args.sequential:
        generator.run_sequential(
            music_categories=music_categories,
            sfx_categories=sfx_categories,
            count_per_category=args.count,
            music_duration=args.music_duration,
            sfx_duration=args.sfx_duration
        )
    else:
        generator.run_parallel(
            music_categories=music_categories,
            sfx_categories=sfx_categories,
            count_per_category=args.count,
            music_duration=args.music_duration,
            sfx_duration=args.sfx_duration
        )

    return 0


if __name__ == '__main__':
    exit(main())
