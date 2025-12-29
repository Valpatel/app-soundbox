#!/usr/bin/env python3
"""
Overnight categorization of ALL clips (SFX, Music, Voice) using LLM.
Uses multiple Ollama servers for load balancing.

Run with: nohup python3 -u scripts/categorize_all_overnight.py > /tmp/categorize_overnight.log 2>&1 &
"""

import sqlite3
import json
import requests
import re
import random
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ollama servers that have qwen2.5:14b model available
OLLAMA_SERVERS = [
    "http://graphlings-ai-01:11434/api/generate",
    "http://graphling-ai-02:11434/api/generate",
]

MODEL = "qwen2.5:14b"
DB_PATH = '/home/mvalancy/Code/app-soundbox/soundbox.db'

# ============================================================================
# SFX CATEGORIES
# ============================================================================

SFX_CATEGORIES = [
    # Nature
    'rain', 'thunder', 'wind', 'water', 'ocean', 'river', 'fire', 'forest',
    'birds', 'insects', 'animals', 'weather',

    # Human
    'footsteps', 'breathing', 'eating', 'drinking', 'voice', 'crowd',
    'applause', 'laughter', 'scream', 'whisper',

    # Mechanical
    'engine', 'motor', 'machine', 'clock', 'mechanical', 'hydraulic',
    'electric', 'industrial',

    # Impacts
    'hit', 'punch', 'kick', 'slap', 'crash', 'break', 'shatter', 'smash',
    'thud', 'bang', 'slam',

    # Materials
    'metal', 'wood', 'glass', 'plastic', 'paper', 'cloth', 'leather',
    'stone', 'concrete',

    # Household
    'door', 'window', 'drawer', 'cabinet', 'switch', 'button', 'lock',
    'key', 'bell', 'phone', 'kitchen', 'bathroom',

    # Vehicles
    'car', 'truck', 'motorcycle', 'airplane', 'helicopter', 'train',
    'boat', 'bicycle',

    # Weapons
    'gun', 'sword', 'knife', 'bow', 'explosion', 'reload', 'bullet',

    # Electronic/UI
    'beep', 'click', 'notification', 'alarm', 'buzz', 'static',
    'computer', 'typing', 'digital',

    # Game/Cartoon
    'powerup', 'levelup', 'coin', 'jump', 'land', 'damage', 'heal',
    'magic', 'sparkle', 'whoosh', 'cartoon', 'boing', 'splat',

    # Ambience
    'ambient', 'room_tone', 'city', 'traffic', 'construction',
    'office', 'restaurant', 'park',

    # Sci-Fi/Fantasy
    'laser', 'robot', 'alien', 'spaceship', 'teleport', 'energy',
    'scifi', 'fantasy', 'monster', 'creature',

    # Horror
    'horror', 'scary', 'creepy', 'ghost', 'zombie', 'gore',

    # Sports
    'ball', 'whistle', 'sports', 'gym',

    # Musical
    'drum', 'cymbal', 'percussion', 'string_pluck', 'piano_note',

    # Misc
    'transition', 'swoosh', 'rise', 'fall', 'tension', 'release',
    'success', 'failure', 'error', 'positive', 'negative',
]

# ============================================================================
# MUSIC CATEGORIES
# ============================================================================

MUSIC_CATEGORIES = [
    # Genres
    'electronic', 'ambient', 'orchestral', 'rock', 'pop', 'jazz',
    'classical', 'folk', 'country', 'blues', 'funk', 'soul', 'rnb',
    'hiphop', 'rap', 'edm', 'house', 'techno', 'trance', 'dubstep',
    'drum_and_bass', 'lofi', 'chillhop', 'synthwave', 'retrowave',
    'chiptune', 'cinematic', 'trailer', 'epic',

    # Moods
    'happy', 'sad', 'peaceful', 'tense', 'exciting', 'mysterious',
    'romantic', 'melancholic', 'uplifting', 'dark', 'bright',
    'energetic', 'calm', 'dreamy', 'nostalgic', 'hopeful', 'angry',

    # Instruments
    'piano', 'guitar', 'strings', 'brass', 'woodwind', 'drums',
    'synth', 'bass', 'violin', 'cello', 'flute', 'saxophone',
    'trumpet', 'organ', 'harp', 'bells', 'choir',

    # Use cases
    'background', 'intro', 'outro', 'loop', 'jingle', 'theme',
    'menu', 'gameplay', 'cutscene', 'credits', 'title',
    'podcast', 'youtube', 'corporate', 'advertising', 'wedding',
    'holiday', 'christmas', 'halloween',

    # Tempo/Energy
    'slow', 'medium', 'fast', 'building', 'climax', 'resolution',

    # Era/Style
    'retro', '80s', '90s', 'modern', 'futuristic', 'vintage',
    'minimalist', 'complex', 'layered',

    # Game specific
    'battle', 'boss', 'exploration', 'victory', 'defeat', 'shop',
    'town', 'dungeon', 'overworld', 'menu_music',

    # Other
    'vocal', 'instrumental', 'acapella', 'remix',
]

# ============================================================================
# VOICE CATEGORIES (from v2 script)
# ============================================================================

VOICE_CATEGORIES = [
    'greeting', 'farewell', 'thanks', 'apology', 'question',
    'exclamation', 'affirmation', 'denial', 'time', 'date',
    'announcement', 'instruction', 'narration', 'dialogue',
    'commercial', 'news', 'game_voice', 'system', 'weather',
    'traffic', 'directions',
]

# ============================================================================
# VOICE DETERMINISTIC RULES
# ============================================================================

NATO_ALPHABET = {
    'alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot', 'golf', 'hotel',
    'india', 'juliet', 'kilo', 'lima', 'mike', 'november', 'oscar', 'papa',
    'quebec', 'romeo', 'sierra', 'tango', 'uniform', 'victor', 'whiskey',
    'x-ray', 'xray', 'yankee', 'zulu'
}

CARDINAL_NUMBERS = {
    'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
    'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen',
    'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty', 'thirty',
    'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety', 'hundred',
    'thousand', 'million', 'billion'
}

ORDINAL_NUMBERS = {
    'first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh',
    'eighth', 'ninth', 'tenth', 'eleventh', 'twelfth', 'thirteenth',
    'fourteenth', 'fifteenth', 'sixteenth', 'seventeenth', 'eighteenth',
    'nineteenth', 'twentieth', 'thirtieth', 'fortieth', 'fiftieth',
    'hundredth', 'thousandth'
}

KNOWN_VOICES = {
    'en_gb-vctk-medium': {'gender': 'female', 'accent': 'british'},
    'en_us-lessac-medium': {'gender': 'female', 'accent': 'american'},
    'en_us-amy-medium': {'gender': 'female', 'accent': 'american'},
    'en_us-ryan-medium': {'gender': 'male', 'accent': 'american'},
}


def get_voice_deterministic(prompt):
    """Deterministic rules for voice clips."""
    text = prompt.strip()
    text_lower = text.lower().rstrip('.!?')
    words = text_lower.split()

    # Single letter
    if re.match(r'^[A-Za-z]\.?$', text):
        return 'alphabet'

    # Multiple single letters
    if re.match(r'^[A-Za-z](?:,\s*[A-Za-z])+\.?$', text):
        return 'alphabet'

    # NATO phonetic
    if text_lower in NATO_ALPHABET:
        return 'phonetic'

    # Cardinal number
    if text_lower in CARDINAL_NUMBERS:
        return 'numbers'

    # Ordinal
    if text_lower in ORDINAL_NUMBERS:
        return 'ordinal'

    # Compound numbers
    if all(w.rstrip(',-') in CARDINAL_NUMBERS or w in {'and'} for w in words if w):
        return 'numbers'

    # Money
    if re.match(r'^[\d\w\s,.-]*(dollar|cent|pound|euro|pence)s?\.?$', text_lower):
        return 'numbers'

    # Counting sequences
    if re.match(r'^(one|two|three|four|five|six|seven|eight|nine|ten|zero)(\s*,\s*(one|two|three|four|five|six|seven|eight|nine|ten|zero))+\.?$', text_lower):
        return 'numbers'

    # Countdowns
    if 'counting down' in text_lower or re.match(r'^(ten|five|three),?\s*(nine|four|two)', text_lower):
        return 'numbers'

    return None


def get_voice_metadata(voice_id):
    """Get gender and accent from voice_id."""
    voice_id_lower = (voice_id or '').lower()
    if voice_id_lower in KNOWN_VOICES:
        return KNOWN_VOICES[voice_id_lower]
    result = {}
    if 'gb' in voice_id_lower or 'uk' in voice_id_lower:
        result['accent'] = 'british'
    elif 'us' in voice_id_lower:
        result['accent'] = 'american'
    return result


# ============================================================================
# LLM CATEGORIZATION
# ============================================================================

def get_system_prompt(model_type):
    """Get appropriate system prompt for model type."""
    if model_type == 'audio':
        categories = SFX_CATEGORIES
        context = """You categorize sound effects based on their description. Return categories that match WHAT THE SOUND ACTUALLY IS.

CRITICAL RULES:
1. Return ONLY a JSON array with 2-4 categories, NOTHING else
2. Read the description carefully and choose categories that MATCH the description
3. NEVER return random categories - they must be relevant to the sound

Category mapping examples:
- "bounce", "bouncing", "ball" → ball, sports
- "game", "powerup", "levelup" → powerup, levelup, magic
- "UI", "click", "button", "notification" → click, button, notification
- "rain", "thunder", "storm" → rain, thunder, weather
- "fire", "burning", "flames" → fire
- "explosion", "blast", "boom" → explosion, bang
- "footsteps", "walking", "running" → footsteps
- "door", "open", "close", "creak" → door
- "whoosh", "swoosh", "transition" → whoosh, transition
- "happy", "positive", "success" → positive, success
- "toy", "playful", "fun" → cartoon, boing
- "eating", "food", "chewing" → eating
- "mechanical", "machine", "gears" → mechanical, machine
- "robot", "electronic", "digital" → robot, electronic, digital
- "monster", "creature", "beast" → monster, creature
"""
    elif model_type == 'music':
        categories = MUSIC_CATEGORIES
        context = """You categorize music tracks. Given a music description, return the most relevant categories.

Rules:
1. Return ONLY a JSON array with 3-5 categories
2. Include genre (electronic, ambient, orchestral, etc.)
3. Include mood (happy, sad, peaceful, tense, etc.)
4. Include primary instruments if mentioned
5. Include use case if clear (game, podcast, corporate, etc.)
"""
    else:  # voice
        categories = VOICE_CATEGORIES
        context = """You categorize voice clips. Given text, return the most relevant categories.

Rules:
1. Return ONLY a JSON array with 1-2 categories
2. "greeting" = hello, welcome, good morning/afternoon/evening
3. "time" = ONLY clock times (3:45, midnight), NOT "good evening"
4. "game_voice" = gaming terms (game over, level up, player 1)
5. "system" = technical (loading, error, connected)
"""

    return f"""{context}

Available categories:
{json.dumps(categories[:50], indent=2)}
{"..." if len(categories) > 50 else ""}

Return ONLY a JSON array, nothing else."""


def categorize_with_llm(prompt_text, model_type, server=None, retries=2):
    """Use Ollama to categorize a clip with retry logic."""
    categories_map = {
        'audio': SFX_CATEGORIES,
        'music': MUSIC_CATEGORIES,
        'voice': VOICE_CATEGORIES,
    }
    valid_categories = set(categories_map.get(model_type, []))

    for attempt in range(retries + 1):
        if server is None or attempt > 0:
            server = random.choice(OLLAMA_SERVERS)

        try:
            response = requests.post(
                server,
                json={
                    "model": MODEL,
                    "prompt": f'Categorize this {model_type}: "{prompt_text[:200]}"\nReturn ONLY a JSON array.',
                    "system": get_system_prompt(model_type),
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 100}
                },
                timeout=30  # Reduced timeout, will retry on different server
            )
            response.raise_for_status()
            result = response.json()
            text = result.get('response', '').strip()

            # Extract JSON array
            start = text.find('[')
            end = text.rfind(']') + 1
            if start >= 0 and end > start:
                categories = json.loads(text[start:end])
                # Validate and clean
                valid = [c.lower().replace(' ', '_') for c in categories
                        if isinstance(c, str) and c.lower().replace(' ', '_') in valid_categories][:5]
                if valid:
                    return valid
        except requests.exceptions.Timeout:
            continue  # Retry on timeout
        except Exception as e:
            if attempt < retries:
                continue
    return []


# ============================================================================
# MAIN PROCESSING
# ============================================================================

def process_clip(clip_data):
    """Process a single clip."""
    clip_id, prompt, model_type, voice_id, old_category = clip_data

    final_categories = []
    method = 'LLM'

    if model_type == 'voice':
        # Add voice metadata
        metadata = get_voice_metadata(voice_id)
        if metadata.get('accent'):
            final_categories.append(metadata['accent'])
        if metadata.get('gender'):
            final_categories.append(metadata['gender'])

        # Try deterministic first
        det_cat = get_voice_deterministic(prompt or '')
        if det_cat:
            final_categories.append(det_cat)
            method = 'DET'
        else:
            llm_cats = categorize_with_llm(prompt or '', model_type)
            final_categories.extend(llm_cats)
            if not llm_cats:
                method = 'ERR'
    else:
        # SFX or Music - use LLM
        llm_cats = categorize_with_llm(prompt or '', model_type)
        final_categories.extend(llm_cats)
        if not llm_cats:
            method = 'ERR'

    # Deduplicate
    seen = set()
    unique = []
    for c in final_categories:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    return clip_id, unique, method, prompt


def main():
    print("=" * 70)
    print("OVERNIGHT CATEGORIZATION - ALL CLIPS")
    print("=" * 70)
    print(f"Servers: {len(OLLAMA_SERVERS)}")
    print(f"Model: {MODEL}")
    print()

    # Test servers and verify model availability
    print("Testing servers...")
    working_servers = []
    for server in OLLAMA_SERVERS:
        try:
            r = requests.get(server.replace('/generate', '/tags'), timeout=5)
            if r.status_code == 200:
                data = r.json()
                models = [m['name'] for m in data.get('models', [])]
                if MODEL in models or any(MODEL in m for m in models):
                    working_servers.append(server)
                    print(f"  ✓ {server} (has {MODEL})")
                else:
                    print(f"  ✗ {server} (missing {MODEL})")
        except Exception as e:
            print(f"  ✗ {server} ({e})")

    if not working_servers:
        print("ERROR: No working servers!")
        sys.exit(1)

    # Update the servers list to only working ones
    OLLAMA_SERVERS.clear()
    OLLAMA_SERVERS.extend(working_servers)
    print()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all clips
    cursor.execute("""
        SELECT id, prompt, model, voice_id, category
        FROM generations
        ORDER BY model, id
    """)
    all_clips = [(row['id'], row['prompt'], row['model'], row['voice_id'], row['category'])
                 for row in cursor.fetchall()]

    print(f"Total clips to process: {len(all_clips)}")

    # Count by type
    by_type = {}
    for c in all_clips:
        by_type[c[2]] = by_type.get(c[2], 0) + 1
    for t, cnt in by_type.items():
        print(f"  {t}: {cnt}")
    print()

    # Process clips
    stats = {'DET': 0, 'LLM': 0, 'ERR': 0}
    start_time = time.time()
    last_commit = time.time()

    # Use thread pool for parallel processing (4 workers per server)
    num_workers = max(4, len(working_servers) * 4)
    print(f"Using {num_workers} worker threads")
    print()

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(process_clip, clip): clip for clip in all_clips}

        for i, future in enumerate(as_completed(futures)):
            try:
                clip_id, categories, method, prompt = future.result()
            except Exception as e:
                print(f"Error processing clip: {e}")
                stats['ERR'] = stats.get('ERR', 0) + 1
                continue

            stats[method] = stats.get(method, 0) + 1

            # Update database
            cursor.execute(
                "UPDATE generations SET category = ? WHERE id = ?",
                (json.dumps(categories), clip_id)
            )

            # Commit periodically (every 30 seconds or 100 clips)
            if time.time() - last_commit > 30 or (i + 1) % 100 == 0:
                conn.commit()
                last_commit = time.time()

            # Progress output
            if (i + 1) % 100 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                remaining = (len(all_clips) - i - 1) / rate / 60
                err_rate = stats.get('ERR', 0) / (i + 1) * 100
                print(f"[{i+1}/{len(all_clips)}] {method}: {(prompt or '')[:40]:<40} -> {categories}")
                print(f"  Rate: {rate:.1f}/s, ETA: {remaining:.1f} min, Errors: {err_rate:.1f}%")
            elif (i + 1) % 10 == 0:
                print(f"[{i+1}/{len(all_clips)}] {method}: {(prompt or '')[:40]:<40} -> {categories}")

    conn.commit()
    conn.close()

    elapsed = time.time() - start_time
    print()
    print("=" * 70)
    print(f"COMPLETE! Processed {len(all_clips)} clips in {elapsed/60:.1f} minutes")
    print(f"  Deterministic: {stats.get('DET', 0)}")
    print(f"  LLM: {stats.get('LLM', 0)}")
    print(f"  Errors: {stats.get('ERR', 0)}")
    print("=" * 70)


if __name__ == '__main__':
    main()
