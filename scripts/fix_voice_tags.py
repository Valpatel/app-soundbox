#!/usr/bin/env python3
"""
Fix voice clip categorization.

Issues found:
1. "alphabet" applied to almost everything (because 'a', 'b', 'c' match any text)
2. SFX tags like "wood", "door", "cloth" incorrectly applied
3. Both "male" and "female" on some clips
4. "notification" overapplied

This script properly categorizes voice clips based on their prompts.
"""

import sqlite3
import json
import re
from collections import defaultdict

DB_PATH = 'soundbox.db'

# Proper speech categories with more specific matching
SPEECH_CATEGORIES = {
    # === VOICE STYLE ===
    'natural': {
        'keywords': ['natural', 'conversational', 'casual'],
        'patterns': []
    },
    'professional': {
        'keywords': ['professional', 'formal', 'business', 'corporate'],
        'patterns': []
    },
    'dramatic': {
        'keywords': ['dramatic', 'theatrical', 'expressive'],
        'patterns': []
    },
    'whisper': {
        'keywords': ['whisper', 'soft', 'quiet', 'hushed', 'asmr'],
        'patterns': []
    },
    'robotic': {
        'keywords': ['robotic', 'mechanical', 'synthetic', 'system'],
        'patterns': []
    },
    'announcer': {
        'keywords': ['announcer', 'broadcast', 'presenter'],
        'patterns': []
    },

    # === NUMBERS & DATA ===
    'numbers': {
        'keywords': ['zero', 'hundred', 'thousand', 'million', 'billion', 'dozen', 'half'],
        'patterns': [
            r'\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b',
            r'\b(thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)\b',
            r'\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\b',
            r'\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\b',
            r'\b(eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth)\b',
            r'\b(twenty-first|twenty-second|thirtieth|fortieth|fiftieth|sixtieth|seventieth|eightieth|ninetieth|hundredth)\b',
            r'\b\d+\b',  # actual digits
        ]
    },
    'counting': {
        'keywords': ['counting', 'count down', 'count up'],
        'patterns': [r'\bcount\s*(down|up|to)\b']
    },
    'time': {
        'keywords': ['o\'clock', 'noon', 'midnight', 'am', 'pm'],
        'patterns': [
            r'\b\d{1,2}:\d{2}\b',  # 10:30
            r'\b(morning|afternoon|evening|night)\b',
            r'\bhalf\s*(past|to)\b',
            r'\bquarter\s*(past|to)\b',
        ]
    },
    'date': {
        'keywords': ['january', 'february', 'march', 'april', 'may', 'june', 'july',
                     'august', 'september', 'october', 'november', 'december',
                     'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'],
        'patterns': [r'\b\d{1,2}(st|nd|rd|th)\b']
    },
    'currency': {
        'keywords': ['dollar', 'cent', 'pound', 'euro', 'yen', 'price', 'cost'],
        'patterns': [r'\$\d+', r'£\d+', r'€\d+']
    },

    # === COMMON PHRASES ===
    'greeting': {
        'keywords': ['hello', 'welcome', 'greetings', 'good morning', 'good afternoon', 'good evening',
                     'happy to help', 'here to help', 'at your service'],
        'patterns': [r'\b(hi|hey)\s*(there|everyone|folks)?\b', r'^hi,?\s+i\'m\b']
    },
    'farewell': {
        'keywords': ['goodbye', 'farewell', 'see you', 'take care', 'goodnight', 'bye bye',
                     'talk to you later', 'talk soon', 'until next time', 'catch you later',
                     'peace out', 'i\'ll be back', 'that\'s all for today', 'have a wonderful day',
                     'have a great day', 'have a nice day', 'have a safe trip', 'pleasant journey'],
        'patterns': [r'\bgood\s*bye\b', r'\bsee\s+you\s+(later|soon|next|tomorrow)\b', r'\btalk\s+(to you\s+)?later\b']
    },
    'thanks': {
        'keywords': ['thank you', 'thanks', 'appreciate', 'grateful', 'my pleasure'],
        'patterns': [r'\bthank(s|\s+you)\b']
    },
    'apology': {
        'keywords': ['sorry', 'apologize', 'excuse me', 'pardon', 'my bad', 'my apologies',
                     'didn\'t quite catch', 'don\'t mention it'],
        'patterns': [r'\b(i\'m|we\'re)\s+sorry\b']
    },
    'confirmation': {
        'keywords': ['affirmative', 'absolutely', 'certainly', 'indeed', 'of course', 'sure thing',
                     'roger that', 'copy that', 'go ahead', 'request approved', 'i agree'],
        'patterns': [r'\b(yes|okay|ok|right|correct|confirmed|agreed|sure)\b']
    },
    'denial': {
        'keywords': ['negative', 'denied', 'refuse', 'decline', 'cannot', 'won\'t', 'i disagree'],
        'patterns': [r'\b(no|nope|wrong|incorrect)\b']
    },
    'question': {
        'keywords': [],
        'patterns': [r'\?$', r'^(what|where|when|how|why|who|which|can|could|would|should|is|are|do|does|did)\b']
    },

    # === INSTRUCTIONS ===
    'directions': {
        'keywords': ['turn left', 'turn right', 'go straight', 'continue', 'proceed', 'navigate', 'take the',
                     'recalculating', 'destination', 'arrived', 'merge left', 'merge right',
                     'go through the tunnel', 'take the exit'],
        'patterns': [r'\b(turn|go|merge)\s+(left|right|straight|back)\b']
    },
    'tutorial': {
        'keywords': ['step one', 'step two', 'first', 'finally', 'begin by', 'start by', 'to start',
                     'let\'s dive in', 'that\'s all there is', 'pro tip', 'to summarize', 'for instance',
                     'here we have', 'as we can see', 'let\'s get started', 'note that'],
        'patterns': [r'\b(step\s+\d+|next\s+step|first\s+step|final\s+step)\b']
    },
    'warning': {
        'keywords': ['warning', 'caution', 'danger', 'alert', 'careful', 'beware', 'hazard', 'emergency',
                     'evacuate immediately', 'this is not a drill'],
        'patterns': []
    },
    'reminder': {
        'keywords': ['remember', 'don\'t forget', 'reminder', 'keep in mind', 'make sure'],
        'patterns': []
    },
    'prompt': {
        'keywords': ['please enter', 'please select', 'please choose', 'press the', 'click the', 'tap the',
                     'please make a selection', 'please speak', 'please subscribe', 'please wait',
                     'select an option', 'enter verification code'],
        'patterns': [r'\b(enter|input|select|choose|press|click|tap)\s+(your|the|a)\b', r'^please\s+\w+']
    },

    # === MEDIA & ENTERTAINMENT ===
    'commercial': {
        'keywords': ['buy now', 'sale', 'discount', 'limited time', 'order now', 'call now', 'special offer',
                     'act now', 'supplies last', 'huge savings', 'try it today', 'don\'t miss',
                     'subscribe to the channel', 'get yours today', 'this holiday season',
                     'free gift', 'call in now', 'satisfaction guaranteed'],
        'patterns': []
    },
    'trailer_voice': {
        'keywords': ['coming soon', 'this summer', 'in a world', 'one man', 'from the makers',
                     'in theaters', 'now playing', 'adventure was just beginning',
                     'coming to theaters', 'must-see film'],
        'patterns': []
    },
    'narration': {
        'keywords': ['our story begins', 'days turned into', 'and so it came to pass', 'epilogue',
                     'prologue', 'chapter', 'once upon a time', 'long ago', 'many years later',
                     'the adventure begins', 'story for another time', 'unbeknownst to them',
                     'meanwhile', 'and so the story begins', 'resistance is futile'],
        'patterns': []
    },
    'podcast': {
        'keywords': ['episode', 'welcome to the show', 'today on', 'podcast', 'our guest'],
        'patterns': []
    },
    'radio': {
        'keywords': ['station', 'fm', 'am', 'on air', 'tune in', 'more music', 'less talk',
                     'now playing', 'up next', 'you\'re listening to'],
        'patterns': []
    },
    'game_voice': {
        'keywords': ['game over', 'level up', 'player one', 'player two', 'victory', 'defeat',
                     'ready', 'fight', 'round', 'knockout', 'combo', 'perfect', 'bonus', 'power up',
                     'health low', 'ammo', 'reload', 'headshot', 'double kill', 'triple kill',
                     'achievement', 'unlocked', 'new high score', 'monster kill', 'killing spree',
                     'super effective', 'critical hit', 'waiting for players', 'match found',
                     'team wins', 'red team', 'blue team', 'respawn', 'checkpoint',
                     'artillery strike', 'flag captured', 'new item', 'press start',
                     'hostile detected', 'get set', 'free kick'],
        'patterns': [r'\b(level|stage|round|wave)\s*\d+\b', r'\b\w+\s+(wins|loses)\b']
    },
    'news': {
        'keywords': ['breaking news', 'this just in', 'according to sources', 'reports say', 'headline',
                     'we now go live', 'our correspondent', 'after the break', 'and we\'re back',
                     'top stories', 'reporting live', 'live from', 'authorities report',
                     'developing story'],
        'patterns': []
    },
    'weather': {
        'keywords': ['temperature', 'degrees', 'forecast', 'rain', 'sunny', 'cloudy', 'wind',
                     'humidity', 'chance of', 'high of', 'low of', 'fog', 'hazy', 'overcast',
                     'mist', 'lightning', 'current conditions', 'thunderstorm', 'severe weather',
                     'heat advisory', 'stay hydrated'],
        'patterns': []
    },
    'sports': {
        'keywords': ['goal', 'touchdown', 'home run', 'slam dunk', 'championship', 'final score',
                     'half time', 'full time', 'penalty', 'foul', 'red card', 'yellow card',
                     'gold medal', 'silver medal', 'bronze medal', 'world record'],
        'patterns': []
    },
    'traffic': {
        'keywords': ['traffic', 'highway', 'congestion', 'delay', 'accident reported', 'road closure',
                     'all lanes', 'at the intersection', 'follow the road', 'roadwork ahead',
                     'rest area', 'exit here', 'now arriving', 'parking available',
                     'use alternate route', 'alternate route'],
        'patterns': []
    },
    'announcement': {
        'keywords': ['attention', 'announcement', 'final boarding', 'boarding call', 'gate',
                     'event will start', 'don\'t go anywhere', 'stay tuned', 'dear passengers',
                     'meeting will begin', 'we are now open'],
        'patterns': []
    },

    # === PHONETIC & LETTERS ===
    'alphabet': {
        'keywords': ['alphabet', 'the letter', 'spelling'],
        'patterns': [
            r'^[A-Z]\.?$',  # Single letter prompts like "A" or "A."
            r'^letter\s+[a-z]$',  # "letter a"
        ]
    },
    'phonetic': {
        'keywords': ['alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot', 'golf', 'hotel',
                     'india', 'juliet', 'kilo', 'lima', 'mike', 'november', 'oscar', 'papa',
                     'quebec', 'romeo', 'sierra', 'tango', 'uniform', 'victor', 'whiskey',
                     'x-ray', 'yankee', 'zulu', 'nato alphabet', 'phonetic'],
        'patterns': []
    },

    # === SYSTEM & UI ===
    'system': {
        'keywords': ['system', 'error', 'loading', 'complete', 'processing', 'initializing',
                     'shutdown', 'startup', 'reboot', 'update', 'download', 'upload',
                     'connection', 'connected', 'disconnected', 'sync', 'backup',
                     'screenshot saved', 'changes saved', 'saved', 'calculating', 'recalculating',
                     'permission granted', 'access denied', 'normal mode', 'mode activated',
                     'paused', 'full screen', 'maintenance required', 'password changed',
                     'aborted', 'scan in progress', 'disk full', 'critical battery', 'battery low',
                     'clipboard', 'zoom in', 'zoom out', 'charging', 'canceled', 'restarting',
                     'undo', 'analyzing', 'try again', 'insufficient funds'],
        'patterns': []
    },
    'notification': {
        'keywords': ['notification', 'alert', 'message received', 'new message', 'you have',
                     'incoming', 'reminder'],
        'patterns': []
    },
    'assistant': {
        'keywords': ['how can i help', 'at your service', 'what can i do for you',
                     'i\'m listening', 'i found the following', 'i found'],
        'patterns': []
    },
    'success': {
        'keywords': ['success', 'complete', 'done', 'finished', 'accomplished', 'well done',
                     'congratulations', 'excellent', 'perfect', 'great job'],
        'patterns': []
    },
    'error': {
        'keywords': ['error', 'failed', 'failure', 'invalid', 'incorrect', 'problem',
                     'issue', 'unable to', 'cannot', 'could not'],
        'patterns': []
    },

    # === EMOTIONS/EXPRESSIONS ===
    'exclamation': {
        'keywords': ['wow', 'amazing', 'incredible', 'awesome', 'fantastic', 'oh no',
                     'oops', 'yay', 'hooray', 'hurrah', 'boo', 'grr', 'ugh', 'hmm',
                     'ouch', 'ow', 'ah', 'oh', 'whoa', 'yikes'],
        'patterns': [r'!$', r'^(wow|oh|ah|whoa|yay|oops|hmm|ugh|grr)!?$']
    },
}

# Tags to remove (SFX tags that shouldn't be on voice clips)
INVALID_VOICE_TAGS = {
    'wood', 'door', 'cloth', 'whoosh', 'paper', 'engine', 'footstep', 'metal',
    'glass', 'water', 'fire', 'explosion', 'impact', 'swoosh', 'beep', 'click',
    'thud', 'crash', 'bang', 'pop', 'buzz', 'hum', 'wind', 'thunder', 'rain',
    'ambient', 'nature', 'animal', 'bird', 'dog', 'cat', 'crowd', 'applause',
    'laser', 'sci-fi', 'magic', 'sparkle', 'shimmer', 'glitch', 'static',
    'button', 'interface', 'menu', 'ui', 'notification_sound',
}


def categorize_prompt(prompt: str) -> list:
    """Categorize a voice prompt based on content."""
    prompt_lower = prompt.lower().strip()
    categories = set()

    for category, rules in SPEECH_CATEGORIES.items():
        # Check keywords (must be word boundaries)
        for keyword in rules['keywords']:
            if keyword in prompt_lower:
                # Verify it's not part of another word for short keywords
                if len(keyword) <= 3:
                    pattern = r'\b' + re.escape(keyword) + r'\b'
                    if re.search(pattern, prompt_lower):
                        categories.add(category)
                else:
                    categories.add(category)
                break

        # Check regex patterns
        for pattern in rules.get('patterns', []):
            if re.search(pattern, prompt_lower, re.IGNORECASE):
                categories.add(category)
                break

    # Default to empty if no categories found (will show as "uncategorized")
    return sorted(list(categories))


def get_voice_info_from_id(voice_id: str) -> dict:
    """Extract info from voice_id like gender, accent."""
    info = {}
    if not voice_id:
        return info

    voice_lower = voice_id.lower()

    # Known voice configurations
    KNOWN_VOICES = {
        'en_gb-vctk-medium': {'gender': 'female', 'accent': 'british'},
        'en_us-lessac-medium': {'gender': 'female', 'accent': 'american'},
        'en_us-amy-medium': {'gender': 'female', 'accent': 'american'},
        'en_us-ryan-medium': {'gender': 'male', 'accent': 'american'},
    }

    # Check known voices first
    if voice_lower in KNOWN_VOICES:
        return KNOWN_VOICES[voice_lower]

    # Fallback to pattern matching
    if any(x in voice_lower for x in ['female', 'woman', 'jenny', 'aria', 'sarah', 'emma', 'olivia', 'amy']):
        info['gender'] = 'female'
    elif any(x in voice_lower for x in ['male', 'man', 'guy', 'john', 'james', 'ryan', 'davis']):
        info['gender'] = 'male'

    if 'en_gb' in voice_lower or 'british' in voice_lower or 'uk' in voice_lower:
        info['accent'] = 'british'
    elif 'en_us' in voice_lower or 'american' in voice_lower:
        info['accent'] = 'american'
    elif 'en_au' in voice_lower or 'australian' in voice_lower:
        info['accent'] = 'australian'

    return info


def fix_voice_tags():
    """Re-categorize all voice clips."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all voice clips
    cursor.execute("SELECT id, prompt, category, voice_id FROM generations WHERE model = 'voice'")
    rows = cursor.fetchall()

    print(f"Processing {len(rows)} voice clips...")

    stats = defaultdict(int)
    updates = []

    for row in rows:
        gen_id, prompt, old_category, voice_id = row

        # Parse old categories
        try:
            old_cats = set(json.loads(old_category)) if old_category else set()
        except (json.JSONDecodeError, TypeError, ValueError):
            old_cats = set()

        # Get new categories from prompt
        new_cats = set(categorize_prompt(prompt))

        # Add voice metadata if available
        voice_info = get_voice_info_from_id(voice_id)
        if 'gender' in voice_info:
            new_cats.add(voice_info['gender'])
        if 'accent' in voice_info:
            new_cats.add(voice_info['accent'])

        # Remove any invalid SFX tags
        new_cats -= INVALID_VOICE_TAGS

        # Track changes
        removed = old_cats - new_cats - INVALID_VOICE_TAGS
        added = new_cats - old_cats

        if old_cats != new_cats:
            stats['changed'] += 1
            if 'alphabet' in old_cats and 'alphabet' not in new_cats:
                stats['alphabet_removed'] += 1
        else:
            stats['unchanged'] += 1

        # Store update
        new_category_json = json.dumps(sorted(list(new_cats)))
        updates.append((new_category_json, gen_id))

    # Apply updates
    print(f"\nApplying updates...")
    cursor.executemany("UPDATE generations SET category = ? WHERE id = ?", updates)
    conn.commit()

    # Print stats
    print(f"\n=== Results ===")
    print(f"Total clips: {len(rows)}")
    print(f"Changed: {stats['changed']}")
    print(f"Unchanged: {stats['unchanged']}")
    print(f"Alphabet tag removed: {stats['alphabet_removed']}")

    # Show new category distribution
    cursor.execute("""
        SELECT category, COUNT(*) as cnt
        FROM generations
        WHERE model = 'voice'
        GROUP BY category
        ORDER BY cnt DESC
        LIMIT 30
    """)
    print(f"\n=== New Category Distribution (Top 30) ===")
    for row in cursor.fetchall():
        cat = row[0] if row[0] else '(none)'
        print(f"  {cat[:70]}: {row[1]}")

    conn.close()
    print("\nDone!")


if __name__ == '__main__':
    fix_voice_tags()
