#!/usr/bin/env python3
"""
Improved voice clip categorization with deterministic rules + LLM fallback.
Uses both graphlings-ai-01 and graphlings-ai-02 for load balancing.
"""

import sqlite3
import json
import requests
import re
import random

# Load balance between servers
OLLAMA_SERVERS = [
    "http://graphlings-ai-01:11434/api/generate",
    "http://graphling-ai-02:11434/api/generate",
    "http://graphdone-ai-01:11434/api/generate",
    "http://graphdone-ai-rtx3080:11434/api/generate",
]
MODEL = "qwen2.5:14b"

# ============================================================================
# DETERMINISTIC RULES - Applied first, no LLM needed
# ============================================================================

# NATO Phonetic Alphabet (exact matches only)
NATO_ALPHABET = {
    'alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot', 'golf', 'hotel',
    'india', 'juliet', 'kilo', 'lima', 'mike', 'november', 'oscar', 'papa',
    'quebec', 'romeo', 'sierra', 'tango', 'uniform', 'victor', 'whiskey',
    'x-ray', 'xray', 'yankee', 'zulu'
}

# Cardinal numbers (spoken form)
CARDINAL_NUMBERS = {
    'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
    'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen',
    'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty', 'thirty',
    'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety', 'hundred',
    'thousand', 'million', 'billion'
}

# Ordinal numbers (spoken form)
ORDINAL_NUMBERS = {
    'first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh',
    'eighth', 'ninth', 'tenth', 'eleventh', 'twelfth', 'thirteenth',
    'fourteenth', 'fifteenth', 'sixteenth', 'seventeenth', 'eighteenth',
    'nineteenth', 'twentieth', 'thirtieth', 'fortieth', 'fiftieth',
    'hundredth', 'thousandth'
}

# Single letter pattern
SINGLE_LETTER_PATTERN = re.compile(r'^[A-Za-z]\.?$')

# Pure number counting pattern (e.g., "One, two, three" or "1, 2, 3")
COUNTING_PATTERN = re.compile(r'^[\d\w,\s]+$')


def get_deterministic_category(prompt):
    """
    Apply deterministic rules. Returns category if matched, None if LLM needed.
    """
    text = prompt.strip()
    text_lower = text.lower().rstrip('.!?')
    words = text_lower.split()

    # Single letter (A, B, C, etc.) -> alphabet
    if SINGLE_LETTER_PATTERN.match(text):
        return 'alphabet'

    # Multiple single letters (A, B, C, D, E) -> alphabet
    if re.match(r'^[A-Za-z](?:,\s*[A-Za-z])+\.?$', text):
        return 'alphabet'

    # NATO phonetic word alone -> phonetic
    if text_lower in NATO_ALPHABET:
        return 'phonetic'

    # Pure cardinal number alone (One, Two, etc.) -> numbers
    if text_lower in CARDINAL_NUMBERS:
        return 'numbers'

    # Ordinals alone -> ordinal (subset of numbers)
    if text_lower in ORDINAL_NUMBERS:
        return 'ordinal'

    # Compound numbers like "Twenty-five", "One hundred" -> numbers
    if all(w.rstrip(',-') in CARDINAL_NUMBERS or w in {'and'} for w in words if w):
        return 'numbers'

    # Money amounts -> numbers
    if re.match(r'^[\d\w\s,.-]*(dollar|cent|pound|euro|pence)s?\.?$', text_lower):
        return 'numbers'

    # Counting sequences -> numbers
    if re.match(r'^(one|two|three|four|five|six|seven|eight|nine|ten|zero)(\s*,\s*(one|two|three|four|five|six|seven|eight|nine|ten|zero))+\.?$', text_lower):
        return 'numbers'

    # Countdowns -> numbers
    if 'counting down' in text_lower or re.match(r'^(ten|five|three),?\s*(nine|four|two)', text_lower):
        return 'numbers'

    return None  # Need LLM


# ============================================================================
# LLM CATEGORIES - For semantic classification
# ============================================================================

LLM_CATEGORIES = [
    'greeting',       # Hello, welcome, good morning/afternoon/evening
    'farewell',       # Goodbye, see you, take care
    'thanks',         # Thank you, appreciate it
    'apology',        # Sorry, excuse me
    'question',       # Any question
    'exclamation',    # Wow, amazing, oh no, emotional expressions
    'affirmation',    # Yes, okay, sure, correct, agreement
    'denial',         # No, wrong, incorrect, refusal

    'time',           # Clock times like "3:45 PM", "midnight", NOT greetings
    'date',           # Days, months, years, specific dates

    'announcement',   # Attention please, notice, alerts
    'instruction',    # Please do X, step 1, commands
    'narration',      # Storytelling, descriptive, "once upon a time"
    'dialogue',       # Movie quotes, conversational exchanges
    'commercial',     # Advertising, promotional, buy now
    'news',           # News-style delivery, breaking news, reports

    'game_voice',     # Game over, level up, player 1, gaming specific
    'system',         # System messages, errors, loading, technical

    'weather',        # Weather reports, forecasts, conditions
    'traffic',        # Traffic updates, road conditions
    'directions',     # Navigation, turn left, go straight
]

SYSTEM_PROMPT = f"""You categorize voice clips. Given text, return the most relevant category from this list:

{json.dumps(LLM_CATEGORIES, indent=2)}

Rules:
1. Return ONLY a JSON array with 1-2 categories, nothing else
2. "greeting" = hello, welcome, good morning/afternoon/evening, hi there
3. "time" = ONLY clock times (3:45, midnight, noon), NOT "good evening"
4. "game_voice" = gaming terms (game over, level up, player 1, headshot)
5. "system" = technical (loading, error, connected, processing)
6. Be specific - choose the most accurate category

Examples:
- "Good evening" -> ["greeting"]
- "The time is 3:45 PM" -> ["time"]
- "Game over" -> ["game_voice"]
- "Loading" -> ["system"]
- "Buy now!" -> ["commercial", "instruction"]
"""


def categorize_with_llm(prompt_text):
    """Use Ollama to categorize a voice clip prompt."""
    server = random.choice(OLLAMA_SERVERS)
    try:
        response = requests.post(
            server,
            json={
                "model": MODEL,
                "prompt": f'Categorize: "{prompt_text}"\nReturn ONLY a JSON array.',
                "system": SYSTEM_PROMPT,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 50}
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        text = result.get('response', '').strip()

        # Extract JSON array
        start = text.find('[')
        end = text.rfind(']') + 1
        if start >= 0 and end > start:
            categories = json.loads(text[start:end])
            return [c for c in categories if c in LLM_CATEGORIES]
        return []
    except Exception as e:
        print(f"  LLM Error: {e}")
        return []


# ============================================================================
# VOICE METADATA
# ============================================================================

KNOWN_VOICES = {
    'en_gb-vctk-medium': {'gender': 'female', 'accent': 'british'},
    'en_us-lessac-medium': {'gender': 'female', 'accent': 'american'},
    'en_us-amy-medium': {'gender': 'female', 'accent': 'american'},
    'en_us-ryan-medium': {'gender': 'male', 'accent': 'american'},
}


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
# MAIN
# ============================================================================

def main():
    db_path = '/home/mvalancy/Code/app-soundbox/soundbox.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, prompt, voice_id, category
        FROM generations WHERE model = 'voice' ORDER BY id
    """)
    clips = cursor.fetchall()

    print(f"Found {len(clips)} voice clips")
    print(f"Using servers: {OLLAMA_SERVERS}")
    print()

    stats = {'deterministic': 0, 'llm': 0, 'errors': 0}

    for i, clip in enumerate(clips):
        clip_id = clip['id']
        prompt = clip['prompt'] or ''
        voice_id = clip['voice_id'] or ''

        # Start with voice metadata
        metadata = get_voice_metadata(voice_id)
        final_categories = []
        if metadata.get('accent'):
            final_categories.append(metadata['accent'])
        if metadata.get('gender'):
            final_categories.append(metadata['gender'])

        # Try deterministic rules first
        det_cat = get_deterministic_category(prompt)
        if det_cat:
            final_categories.append(det_cat)
            stats['deterministic'] += 1
            method = 'DET'
        else:
            # Fall back to LLM
            llm_cats = categorize_with_llm(prompt)
            if llm_cats:
                final_categories.extend(llm_cats)
                stats['llm'] += 1
                method = 'LLM'
            else:
                stats['errors'] += 1
                method = 'ERR'

        # Deduplicate
        seen = set()
        unique = []
        for c in final_categories:
            if c not in seen:
                seen.add(c)
                unique.append(c)

        # Update database
        cursor.execute(
            "UPDATE generations SET category = ? WHERE id = ?",
            (json.dumps(unique), clip_id)
        )

        print(f"[{i+1}/{len(clips)}] {method}: {prompt[:45]:<45} -> {unique}")

        if (i + 1) % 50 == 0:
            conn.commit()
            print(f"  --- Committed {i+1} ---")

    conn.commit()
    conn.close()

    print()
    print("=" * 60)
    print(f"Done! Processed {len(clips)} clips")
    print(f"  Deterministic: {stats['deterministic']}")
    print(f"  LLM: {stats['llm']}")
    print(f"  Errors: {stats['errors']}")


if __name__ == '__main__':
    main()
