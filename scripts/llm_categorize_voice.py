#!/usr/bin/env python3
"""
Use Ollama LLM to intelligently categorize voice clips.
Much more accurate than keyword matching.
"""

import sqlite3
import json
import requests
import time
import sys

OLLAMA_URL = "http://graphling-ai-02:11434/api/generate"
MODEL = "qwen2.5:14b"  # Good balance of speed and quality

# Categories the LLM can choose from
CATEGORIES = [
    # Voice characteristics (from metadata, not LLM)
    # 'male', 'female', 'british', 'american'

    # Content types
    'greeting',       # Hello, welcome, good morning/afternoon/evening
    'farewell',       # Goodbye, see you, take care
    'thanks',         # Thank you, appreciate it
    'apology',        # Sorry, excuse me
    'question',       # Any question
    'exclamation',    # Wow, amazing, oh no
    'affirmation',    # Yes, okay, sure, correct
    'denial',         # No, wrong, incorrect

    # Specific content
    'numbers',        # Counting, digits, amounts
    'time',           # Clock times (not greetings like "good evening")
    'date',           # Days, months, years
    'alphabet',       # Single letters, spelling
    'phonetic',       # Alpha, bravo, charlie (NATO alphabet)

    # Use cases
    'announcement',   # Attention please, notice
    'instruction',    # Please do X, step 1
    'narration',      # Storytelling, descriptive
    'dialogue',       # Conversational speech
    'commercial',     # Advertising, promotional
    'news',           # News-style delivery

    # Gaming/Media
    'game_voice',     # Game over, level up, player 1
    'system',         # System messages, errors, loading

    # Other
    'weather',        # Weather reports
    'traffic',        # Traffic updates
    'directions',     # Turn left, go straight
]

SYSTEM_PROMPT = f"""You are a voice clip categorizer. Given a text prompt that was used to generate a voice clip, assign the most relevant categories from this list:

{json.dumps(CATEGORIES, indent=2)}

Rules:
1. Return ONLY a JSON array of category names, nothing else
2. Choose 1-3 most relevant categories
3. "greeting" includes hello, welcome, good morning/afternoon/evening
4. "time" is ONLY for clock times like "3:45 PM", NOT greetings like "good evening"
5. "alphabet" is for single letter prompts or spelling out words
6. "phonetic" is for NATO alphabet (Alpha, Bravo, Charlie, etc.)
7. Be specific - don't over-categorize

Examples:
- "Hello, welcome to our store" -> ["greeting", "commercial"]
- "Good evening" -> ["greeting"]
- "The time is 3:45 PM" -> ["time", "announcement"]
- "A" -> ["alphabet"]
- "Alpha" -> ["phonetic"]
- "Game over" -> ["game_voice"]
- "Thank you for calling" -> ["thanks", "commercial"]
- "Is this available?" -> ["question"]
"""

def categorize_with_llm(prompt_text):
    """Use Ollama to categorize a voice clip prompt."""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": f"Categorize this voice clip text: \"{prompt_text}\"\n\nReturn ONLY a JSON array of categories.",
                "system": SYSTEM_PROMPT,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temp for consistency
                    "num_predict": 100   # Short response
                }
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        # Extract JSON array from response
        text = result.get('response', '').strip()

        # Find JSON array in response
        start = text.find('[')
        end = text.rfind(']') + 1
        if start >= 0 and end > start:
            categories = json.loads(text[start:end])
            # Validate categories
            return [c for c in categories if c in CATEGORIES]

        return []
    except Exception as e:
        print(f"  Error: {e}")
        return []

def get_voice_metadata(voice_id):
    """Get gender and accent from voice_id."""
    voice_id_lower = voice_id.lower() if voice_id else ''

    KNOWN_VOICES = {
        'en_gb-vctk-medium': {'gender': 'female', 'accent': 'british'},
        'en_us-lessac-medium': {'gender': 'female', 'accent': 'american'},
        'en_us-amy-medium': {'gender': 'female', 'accent': 'american'},
        'en_us-ryan-medium': {'gender': 'male', 'accent': 'american'},
    }

    if voice_id_lower in KNOWN_VOICES:
        return KNOWN_VOICES[voice_id_lower]

    # Fallback detection
    result = {}
    if 'gb' in voice_id_lower or 'uk' in voice_id_lower:
        result['accent'] = 'british'
    elif 'us' in voice_id_lower:
        result['accent'] = 'american'

    return result

def main():
    db_path = '/home/mvalancy/Code/app-soundbox/soundbox.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all voice clips
    cursor.execute("""
        SELECT id, prompt, voice_id, category
        FROM generations
        WHERE model = 'voice'
        ORDER BY id
    """)
    clips = cursor.fetchall()

    print(f"Found {len(clips)} voice clips to categorize")
    print(f"Using model: {MODEL}")
    print()

    # Track progress
    changed = 0
    errors = 0

    for i, clip in enumerate(clips):
        clip_id = clip['id']
        prompt = clip['prompt'] or ''
        voice_id = clip['voice_id'] or ''

        # Get LLM categories
        llm_categories = categorize_with_llm(prompt)

        # Add voice metadata (always include these)
        metadata = get_voice_metadata(voice_id)
        final_categories = []
        if metadata.get('accent'):
            final_categories.append(metadata['accent'])
        if metadata.get('gender'):
            final_categories.append(metadata['gender'])

        # Add LLM categories
        final_categories.extend(llm_categories)

        # Remove duplicates, preserve order
        seen = set()
        unique_categories = []
        for c in final_categories:
            if c not in seen:
                seen.add(c)
                unique_categories.append(c)

        # Update database
        new_category = json.dumps(unique_categories)
        cursor.execute(
            "UPDATE generations SET category = ? WHERE id = ?",
            (new_category, clip_id)
        )

        # Progress output
        status = "OK" if llm_categories else "EMPTY"
        if not llm_categories:
            errors += 1
        else:
            changed += 1

        print(f"[{i+1}/{len(clips)}] {status}: {prompt[:50]:<50} -> {unique_categories}")

        # Commit every 50 clips
        if (i + 1) % 50 == 0:
            conn.commit()
            print(f"  --- Committed {i+1} clips ---")

    # Final commit
    conn.commit()
    conn.close()

    print()
    print("=" * 60)
    print(f"Done! Processed {len(clips)} clips")
    print(f"  Successfully categorized: {changed}")
    print(f"  Errors/empty: {errors}")

if __name__ == '__main__':
    main()
