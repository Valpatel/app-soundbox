#!/usr/bin/env python3
"""
Tag existing SFX for Byk3s Game

Finds relevant sounds and adds byk3s-specific tags for:
- byk3s_weapon: Guns, lasers, missiles, energy weapons
- byk3s_vehicle: Motorcycles, jets, helicopters, tanks
- byk3s_explosion: Explosions, blasts, impacts
- byk3s_enemy: Enemy sounds, aliens, monsters, robots
- byk3s_ui: Game UI, alerts, notifications, power-ups
- byk3s_ambient: Environment, combat ambience
- byk3s_impact: Hits, crashes, collisions
"""

import sqlite3
import json
import sys
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent.parent / "soundbox.db"

# Tagging rules: keyword -> byk3s tag
# More specific phrases to avoid false positives
TAGGING_RULES = {
    # Weapons - specific weapon terms only
    "byk3s_weapon": [
        "laser", "gunshot", "gunfire", "gun shot", "shooting", "weapon",
        "missile", "rocket launcher", "bullet", "blaster", "zap", "beam weapon",
        "projectile", "cannon", "turret", "rifle", "pistol", "shotgun",
        "plasma gun", "railgun", "gatling", "machine gun", "sniper",
        "photon", "phaser", "disruptor", "artillery"
    ],

    # Vehicles - specific vehicle terms
    "byk3s_vehicle": [
        "motorcycle", "motorbike", "engine rev", "engine start", "engine idle",
        "helicopter", "chopper", "jet engine", "fighter jet", "aircraft",
        "tank engine", "tank treads", "vehicle engine", "hover", "hovercraft",
        "spacecraft", "spaceship", "thrust", "rotor", "turbine", "afterburner",
        "exhaust", "throttle", "acceleration", "car engine"
    ],

    # Explosions - explosion-specific
    "byk3s_explosion": [
        "explosion", "explode", "exploding", "blast", "boom", "detonate",
        "detonation", "bomb", "grenade", "mine explode", "destruction",
        "shockwave", "debris", "kaboom"
    ],

    # Enemies - creature/enemy sounds
    "byk3s_enemy": [
        "monster", "creature roar", "alien", "robot voice", "mech",
        "enemy drone", "growl", "roar", "screech", "hiss", "snarl",
        "enemy", "boss", "aggressive", "menacing", "demon", "zombie",
        "predator", "beast"
    ],

    # UI/Power-ups - game UI sounds
    "byk3s_ui": [
        "notification", "alert sound", "alarm", "beep", "ui click",
        "button click", "select", "power up", "powerup", "level up",
        "collect", "pickup", "coin", "success", "fail", "error sound",
        "menu", "confirm", "game over", "health pickup", "ammo pickup",
        "reload", "charge up", "ready"
    ],

    # Ambient/Environment - atmospheric
    "byk3s_ambient": [
        "wind howl", "rain storm", "thunder", "electricity", "electric spark",
        "static", "hum", "drone ambient", "rumble", "atmosphere",
        "environment", "industrial ambient", "mechanical hum", "city ambient",
        "space ambient", "battle ambient"
    ],

    # Impacts - combat impacts
    "byk3s_impact": [
        "punch", "kick", "crash", "collision", "smash", "slam",
        "thud", "clang", "metal hit", "metal impact", "strike",
        "body hit", "body impact"
    ],

    # Sci-Fi/Futuristic - sci-fi specific
    "byk3s_scifi": [
        "futuristic", "sci-fi", "scifi", "space", "teleport", "warp",
        "hologram", "cyber", "energy beam", "force field", "shield",
        "cloak", "stealth", "scan", "radar", "targeting", "hyperdrive",
        "stasis", "cryogenic"
    ],
}


def get_db():
    return sqlite3.connect(DB_PATH)


def tag_sound(cursor, gen_id: str, new_tag: str, dry_run: bool = False):
    """Add a tag to a sound's category array."""
    cursor.execute("SELECT category FROM generations WHERE id = ?", (gen_id,))
    row = cursor.fetchone()
    if not row:
        return False

    try:
        current = json.loads(row[0]) if row[0] else []
    except:
        current = []

    if new_tag in current:
        return False  # Already tagged

    current.append(new_tag)

    if not dry_run:
        cursor.execute(
            "UPDATE generations SET category = ? WHERE id = ?",
            (json.dumps(current), gen_id)
        )

    return True


def find_and_tag_sounds(dry_run: bool = False, verbose: bool = False):
    """Find relevant sounds and tag them for Byk3s."""
    conn = get_db()
    cursor = conn.cursor()

    stats = {tag: 0 for tag in TAGGING_RULES.keys()}
    total_tagged = 0

    print("=" * 60)
    print("BYK3S SFX TAGGING")
    print("=" * 60)
    print(f"Dry run: {dry_run}")
    print()

    # Get all SFX (non-voice)
    cursor.execute("""
        SELECT id, prompt, category FROM generations
        WHERE model = 'audio'
    """)
    all_sfx = cursor.fetchall()
    print(f"Total SFX to analyze: {len(all_sfx)}")
    print()

    for gen_id, prompt, category in all_sfx:
        prompt_lower = (prompt or "").lower()
        category_str = (category or "").lower()

        # Check each tagging rule
        for byk3s_tag, keywords in TAGGING_RULES.items():
            # Check if any keyword matches
            for keyword in keywords:
                if keyword in prompt_lower or keyword in category_str:
                    if tag_sound(cursor, gen_id, byk3s_tag, dry_run):
                        stats[byk3s_tag] += 1
                        total_tagged += 1
                        if verbose:
                            print(f"  Tagged [{byk3s_tag}]: {prompt[:50]}...")
                    break  # Only add each tag once per sound

    if not dry_run:
        conn.commit()

    conn.close()

    # Print results
    print()
    print("TAGGING RESULTS:")
    print("-" * 40)
    for tag, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {tag}: {count} sounds")
    print("-" * 40)
    print(f"  TOTAL: {total_tagged} tags added")

    return stats


def show_tagged_samples(limit: int = 5):
    """Show sample sounds for each Byk3s category."""
    conn = get_db()
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("SAMPLE SOUNDS PER CATEGORY")
    print("=" * 60)

    for tag in TAGGING_RULES.keys():
        cursor.execute("""
            SELECT prompt FROM generations
            WHERE category LIKE ?
            LIMIT ?
        """, (f'%"{tag}"%', limit))

        rows = cursor.fetchall()
        if rows:
            print(f"\n{tag} ({len(rows)} samples):")
            for row in rows:
                print(f"  - {row[0][:60]}...")

    conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Tag SFX for Byk3s game")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show each tag")
    parser.add_argument("--samples", action="store_true", help="Show sample sounds")

    args = parser.parse_args()

    if args.samples:
        show_tagged_samples()
    else:
        find_and_tag_sounds(dry_run=args.dry_run, verbose=args.verbose)
