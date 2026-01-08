#!/usr/bin/env python3
"""
Clean SFX Generator

Generates clean, isolated sound effects using AudioGen with carefully crafted prompts.
All sounds are designed to be:
- Isolated (no background noise)
- Dry (no reverb)
- Single sounds (not layered)
- Studio quality

Usage:
    python scripts/generate_clean_sfx.py [--category CATEGORY] [--count COUNT] [--dry-run]

Examples:
    python scripts/generate_clean_sfx.py                    # Generate all categories
    python scripts/generate_clean_sfx.py --category dog     # Just dogs
    python scripts/generate_clean_sfx.py --dry-run          # Preview without generating
"""

import os
import sys
import json
import time
import random
import argparse
import hashlib
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sfx_prompts_clean import ALL_SFX_PROMPTS, TARGET_COUNTS, QUALITY_SUFFIXES

# Progress file for resumable generation
PROGRESS_FILE = Path(__file__).parent / "sfx_generation_progress.json"
AUDIO_OUTPUT_DIR = Path(__file__).parent.parent / "generated_audio"


def load_progress() -> dict:
    """Load generation progress from file."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"completed": {}, "failed": [], "started_at": None}


def save_progress(progress: dict):
    """Save generation progress to file."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def get_prompt_id(category: str, prompt: str) -> str:
    """Generate a unique ID for a prompt."""
    content = f"{category}:{prompt}"
    return hashlib.md5(content.encode()).hexdigest()[:12]


def enhance_prompt(prompt: str) -> str:
    """Add quality suffix to ensure clean output."""
    # Don't add if already has quality markers
    quality_markers = ["isolated", "clean", "studio", "no background", "no reverb"]
    if any(marker in prompt.lower() for marker in quality_markers):
        return prompt

    # Add a random quality suffix
    suffix = random.choice(QUALITY_SUFFIXES)
    return prompt + suffix


def generate_sfx_batch(
    category: str,
    prompts: list,
    duration: float = 3.0,
    dry_run: bool = False,
    progress: dict = None
) -> tuple:
    """
    Generate a batch of SFX for a category.

    Returns: (success_count, fail_count)
    """
    if progress is None:
        progress = load_progress()

    completed_key = f"{category}"
    if completed_key not in progress["completed"]:
        progress["completed"][completed_key] = []

    success_count = 0
    fail_count = 0

    for i, base_prompt in enumerate(prompts):
        prompt_id = get_prompt_id(category, base_prompt)

        # Skip if already completed
        if prompt_id in progress["completed"][completed_key]:
            print(f"  [{i+1}/{len(prompts)}] Skipping (already done): {base_prompt[:50]}...")
            success_count += 1
            continue

        # Enhance prompt for quality
        enhanced_prompt = enhance_prompt(base_prompt)

        if dry_run:
            print(f"  [{i+1}/{len(prompts)}] Would generate: {enhanced_prompt[:60]}...")
            success_count += 1
            continue

        try:
            # Import here to avoid loading models if just doing dry run
            from app import generate_audio_internal, save_generation_to_db

            print(f"  [{i+1}/{len(prompts)}] Generating: {enhanced_prompt[:50]}...")

            # Generate audio
            result = generate_audio_internal(
                prompt=enhanced_prompt,
                duration=duration,
                model="audio",  # AudioGen for SFX
                temperature=0.8,  # Slight variation
            )

            if result and result.get("filename"):
                # Save to database with category tags
                save_generation_to_db(
                    filename=result["filename"],
                    prompt=base_prompt,  # Store original prompt, not enhanced
                    model="audio",
                    duration=duration,
                    category=json.dumps([category]),  # Tag with category
                    is_loop=False,
                )

                progress["completed"][completed_key].append(prompt_id)
                save_progress(progress)
                success_count += 1
                print(f"    -> Saved: {result['filename']}")
            else:
                fail_count += 1
                progress["failed"].append({
                    "category": category,
                    "prompt": base_prompt,
                    "error": "No output",
                    "time": datetime.now().isoformat()
                })
                save_progress(progress)
                print(f"    -> Failed: No output")

        except Exception as e:
            fail_count += 1
            progress["failed"].append({
                "category": category,
                "prompt": base_prompt,
                "error": str(e),
                "time": datetime.now().isoformat()
            })
            save_progress(progress)
            print(f"    -> Error: {e}")

        # Small delay to avoid overwhelming GPU
        time.sleep(0.5)

    return success_count, fail_count


def main():
    parser = argparse.ArgumentParser(description="Generate clean SFX library")
    parser.add_argument(
        "--category", "-c",
        type=str,
        help="Generate only this category (e.g., 'dog', 'riser')"
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        help="Override target count per category"
    )
    parser.add_argument(
        "--duration", "-d",
        type=float,
        default=3.0,
        help="Duration in seconds (default: 3.0)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview prompts without generating"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset progress and start fresh"
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List all available categories"
    )

    args = parser.parse_args()

    if args.list_categories:
        print("\nAvailable SFX Categories:")
        print("=" * 50)
        for cat, prompts in sorted(ALL_SFX_PROMPTS.items()):
            target = TARGET_COUNTS.get(cat, 50)
            print(f"  {cat:15s}: {len(prompts):3d} prompts -> {target:3d} target")
        print()
        return

    # Reset progress if requested
    if args.reset:
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()
        print("Progress reset.")

    # Load or initialize progress
    progress = load_progress()
    if not progress.get("started_at"):
        progress["started_at"] = datetime.now().isoformat()
        save_progress(progress)

    # Determine categories to process
    if args.category:
        if args.category not in ALL_SFX_PROMPTS:
            print(f"Error: Unknown category '{args.category}'")
            print(f"Available: {', '.join(sorted(ALL_SFX_PROMPTS.keys()))}")
            return 1
        categories = [args.category]
    else:
        categories = list(ALL_SFX_PROMPTS.keys())

    print("\n" + "=" * 60)
    print("CLEAN SFX GENERATOR")
    print("=" * 60)
    print(f"Categories: {len(categories)}")
    print(f"Duration: {args.duration}s")
    print(f"Dry run: {args.dry_run}")
    print("=" * 60 + "\n")

    total_success = 0
    total_fail = 0

    for category in categories:
        base_prompts = ALL_SFX_PROMPTS[category]
        target = args.count or TARGET_COUNTS.get(category, 50)

        # Build prompt list to reach target
        prompts = []
        for i in range(target):
            prompt = base_prompts[i % len(base_prompts)]
            if i >= len(base_prompts):
                # Add variation marker for repeated prompts
                variation = i // len(base_prompts)
                prompt = f"{prompt}, take {variation + 1}"
            prompts.append(prompt)

        print(f"\n[{category.upper()}] Generating {len(prompts)} clips...")
        print("-" * 40)

        success, fail = generate_sfx_batch(
            category=category,
            prompts=prompts,
            duration=args.duration,
            dry_run=args.dry_run,
            progress=progress
        )

        total_success += success
        total_fail += fail

        print(f"  Complete: {success} success, {fail} failed")

    # Final summary
    print("\n" + "=" * 60)
    print("GENERATION COMPLETE")
    print("=" * 60)
    print(f"Total success: {total_success}")
    print(f"Total failed:  {total_fail}")

    if total_fail > 0:
        print(f"\nFailed prompts saved to: {PROGRESS_FILE}")

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
