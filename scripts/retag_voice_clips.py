#!/usr/bin/env python3
"""
Migration script to re-tag existing voice clips with proper categories and voice_id.

This script:
1. Adds voice_id to existing voice clips (defaulting to en_GB-vctk-medium)
2. Re-categorizes them using SPEECH_CATEGORIES
3. Adds gender/accent tags based on voice metadata

Usage:
    python scripts/retag_voice_clips.py [--voice-id en_GB-vctk-medium] [--dry-run]
"""

import sys
import os
import json
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database as db

# Voice metadata for tagging
VOICE_METADATA = {
    'en_GB-vctk-medium': {'gender': 'female', 'accent': 'british', 'style': 'natural'},
    'en_US-lessac-medium': {'gender': 'female', 'accent': 'american', 'style': 'natural'},
    'en_US-ljspeech-medium': {'gender': 'female', 'accent': 'american', 'style': 'natural'},
    'en_US-ryan-medium': {'gender': 'male', 'accent': 'american', 'style': 'natural'},
    'en_GB-cori-medium': {'gender': 'female', 'accent': 'british', 'style': 'natural'},
    'en_US-amy-medium': {'gender': 'female', 'accent': 'american', 'style': 'natural'},
    'en_US-joe-medium': {'gender': 'male', 'accent': 'american', 'style': 'natural'},
    'en_GB-alan-medium': {'gender': 'male', 'accent': 'british', 'style': 'natural'},
    'en_GB-alba-medium': {'gender': 'female', 'accent': 'british', 'style': 'natural'},
    'en_GB-jenny_dioco-medium': {'gender': 'female', 'accent': 'british', 'style': 'natural'},
}


def get_voice_tags(voice_id):
    """Get category tags for a voice based on its metadata."""
    tags = []
    meta = VOICE_METADATA.get(voice_id, {})

    if meta.get('gender'):
        tags.append(meta['gender'])
    if meta.get('accent'):
        tags.append(meta['accent'])
    if meta.get('style'):
        tags.append(meta['style'])

    return tags


def retag_voice_clips(default_voice_id='en_GB-vctk-medium', dry_run=False):
    """Re-tag all voice clips with proper categories and voice_id."""

    print(f"[Migration] Re-tagging voice clips with voice_id={default_voice_id}")
    print(f"[Migration] Dry run: {dry_run}")
    print()

    voice_tags = get_voice_tags(default_voice_id)
    print(f"[Migration] Voice tags: {voice_tags}")

    with db.get_db() as conn:
        # Get all voice clips
        rows = conn.execute("""
            SELECT id, prompt, category, voice_id
            FROM generations
            WHERE model = 'voice'
        """).fetchall()

        print(f"[Migration] Found {len(rows)} voice clips")

        updated = 0
        for row in rows:
            gen_id = row['id']
            prompt = row['prompt']
            current_category = row['category']
            current_voice_id = row['voice_id']

            # Parse existing categories
            try:
                existing_cats = json.loads(current_category) if current_category else []
            except json.JSONDecodeError:
                existing_cats = []

            # Re-categorize using SPEECH_CATEGORIES
            auto_cats = db.categorize_prompt(prompt, 'voice')

            # Merge: existing + auto + voice tags
            all_cats = list(set(existing_cats + auto_cats + voice_tags))

            # Determine voice_id to use
            new_voice_id = current_voice_id if current_voice_id else default_voice_id

            # Check if update needed
            category_json = json.dumps(all_cats)
            if category_json != current_category or new_voice_id != current_voice_id:
                if not dry_run:
                    conn.execute("""
                        UPDATE generations
                        SET category = ?, voice_id = ?
                        WHERE id = ?
                    """, (category_json, new_voice_id, gen_id))
                updated += 1

                if updated <= 10:  # Show first 10 examples
                    print(f"  [{gen_id[:8]}] {prompt[:40]}...")
                    print(f"    Categories: {all_cats[:5]}...")
                    print(f"    Voice ID: {new_voice_id}")

        if not dry_run:
            conn.commit()

        print()
        print(f"[Migration] Updated {updated} of {len(rows)} voice clips")

    return updated


def main():
    parser = argparse.ArgumentParser(description='Re-tag existing voice clips')
    parser.add_argument('--voice-id', default='en_GB-vctk-medium',
                        help='Default voice_id to assign to clips without one')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without modifying database')
    args = parser.parse_args()

    # Initialize database (runs migrations)
    db.init_db()

    # Run re-tagging
    retag_voice_clips(args.voice_id, args.dry_run)


if __name__ == '__main__':
    main()
