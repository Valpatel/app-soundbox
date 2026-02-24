"""
Sound Box Database Layer
SQLite database for generations and votes with private feedback.
No public comments - feedback stored privately with votes.
"""
import sqlite3
import json
import os
import re
from contextlib import contextmanager
from datetime import datetime


def sanitize_fts5_query(search):
    """
    Sanitize search input for FTS5 to prevent query injection.

    FTS5 has special operators like *, ^, +, -, NOT, AND, OR, NEAR that can
    cause query parsing errors or unexpected behavior if not sanitized.

    Args:
        search: Raw search string from user input

    Returns:
        Sanitized FTS5 query string with terms quoted and joined with OR,
        or None if no valid terms remain.
    """
    if not search:
        return None

    # Remove FTS5 operators and special characters
    clean_search = re.sub(r'[*^+\-]', '', search)
    # Remove standalone operators (case insensitive)
    clean_search = re.sub(r'\b(NOT|AND|OR|NEAR)\b', '', clean_search, flags=re.IGNORECASE)
    # Remove colons (used for column specifiers in FTS5)
    clean_search = clean_search.replace(':', ' ')

    words = clean_search.strip().split()
    if not words:
        return None

    # Quote each term and remove any embedded quotes
    quoted_words = []
    for w in words:
        w = w.replace('"', '').strip()
        if w:  # Skip empty strings
            quoted_words.append(f'"{w}"')

    if not quoted_words:
        return None

    return ' OR '.join(quoted_words)

DB_PATH = os.environ.get('DB_PATH', 'soundbox.db')
METADATA_FILE = 'generations.json'

# =============================================================================
# User Storage Limits (by subscription tier)
# =============================================================================
# Maximum number of private generations a user can store in "My Generations"
# When limit is exceeded, oldest non-favorited generations are auto-deleted
# (Favorites are exempt from auto-deletion)

USER_STORAGE_LIMITS = {
    'creator': 500,    # $20/mo - generous allocation
    'premium': 200,    # $10/mo
    'supporter': 100,  # $5/mo
    'free': 20         # Free tier - just enough to try the service
}

# =============================================================================
# Category Keyword Mappings for Auto-Categorization
# =============================================================================

# Expanded MUSIC categories for fine-grained searching
# Organized by: Genres, Moods, Instruments, Styles, Use Cases
MUSIC_CATEGORIES = {
    # === ELECTRONIC & DANCE ===
    'electronic': ['electronic', 'synth', 'synthesizer', 'digital', 'produced', 'sequencer', 'electro', 'synthetic'],
    'edm': ['edm', 'dance', 'club', 'rave', 'festival', 'drop', 'buildup', 'dancefloor'],
    'house': ['house', 'deep house', 'tech house', 'progressive house', 'disco house', 'funky house', 'four on the floor'],
    'techno': ['techno', 'minimal', 'industrial', 'dark techno', 'acid', 'berlin', 'warehouse'],
    'trance': ['trance', 'uplifting', 'psytrance', 'goa', 'progressive trance', 'euphoric', 'hypnotic'],
    'dubstep': ['dubstep', 'wub', 'wobble', 'brostep', 'riddim', 'bass drop', 'heavy bass'],
    'drum_and_bass': ['drum and bass', 'dnb', 'd&b', 'jungle', 'liquid', 'neurofunk', 'breakbeat'],
    'synthwave': ['synthwave', 'retrowave', 'outrun', 'vaporwave', '80s synth', 'neon', 'cyberpunk', 'futuristic'],

    # === AMBIENT & ATMOSPHERIC ===
    'ambient': ['ambient', 'atmospheric', 'ethereal', 'floating', 'spacey', 'immersive', 'soundscape', 'background', 'pads'],
    'drone': ['drone', 'droning', 'sustained', 'evolving', 'texture', 'pad', 'pads'],
    'meditation': ['meditation', 'zen', 'mindful', 'healing', 'yoga', 'spa', 'wellness', 'sleep', 'relaxation', 'serene'],
    'nature_music': ['nature', 'organic', 'natural', 'earthy', 'forest music', 'water music', 'woodland'],
    'space': ['space', 'cosmic', 'galactic', 'stellar', 'interstellar', 'nebula', 'astral', 'starfield', 'celestial'],
    'dark_ambient': ['dark ambient', 'doom', 'gloomy', 'ominous', 'foreboding', 'eerie', 'sinister'],

    # === CINEMATIC & ORCHESTRAL ===
    'cinematic': ['cinematic', 'film', 'movie', 'score', 'soundtrack', 'motion picture'],
    'epic': ['epic', 'massive', 'grandiose', 'sweeping', 'majestic', 'powerful', 'triumphant'],
    'orchestral': ['orchestral', 'orchestra', 'symphonic', 'symphony', 'philharmonic'],
    'trailer': ['trailer', 'teaser', 'promo', 'preview', 'blockbuster', 'action trailer'],
    'dramatic': ['dramatic', 'intense', 'climactic', 'theatrical', 'emotional drama'],
    'suspense': ['suspense', 'tension', 'thriller', 'mystery', 'intrigue', 'anxious', 'nervous'],
    'heroic': ['heroic', 'hero', 'brave', 'courageous', 'victory', 'conquest', 'champion'],
    'romantic': ['romantic', 'love', 'passionate', 'tender', 'heartfelt', 'sentimental'],

    # === CLASSICAL & ACOUSTIC ===
    'classical': ['classical', 'baroque', 'renaissance', 'romantic era', 'contemporary classical'],
    'piano': ['piano', 'keys', 'keyboard', 'grand piano', 'solo piano', 'piano melody'],
    'guitar': ['guitar', 'acoustic guitar', 'fingerstyle', 'nylon', 'classical guitar'],
    'strings': ['strings', 'string quartet', 'violin', 'viola', 'cello', 'contrabass', 'bow'],
    'orchestra_section': ['brass', 'woodwind', 'flute', 'clarinet', 'oboe', 'trumpet', 'horn'],
    'acoustic': ['acoustic', 'unplugged', 'organic', 'natural', 'unamplified', 'raw'],

    # === LO-FI & CHILL ===
    'lofi': ['lo-fi', 'lofi', 'lo fi', 'low fidelity', 'dusty', 'vinyl', 'tape', 'chill beats', 'relaxed vibe'],
    'chillhop': ['chillhop', 'chill hop', 'jazzy hip hop', 'boom bap chill', 'study beats', 'hip hop', 'hip-hop'],
    'chill': ['chill', 'chillout', 'laid back', 'easy', 'smooth', 'mellow', 'lazy', 'relaxed'],
    'study': ['study', 'focus', 'concentration', 'work', 'productivity', 'background', 'homework'],
    'cafe': ['cafe', 'coffee shop', 'cozy', 'warm', 'comfortable', 'lounge', 'hygge', 'homey', 'comfort'],

    # === HIP HOP & RAP ===
    'hiphop': ['hip hop', 'hiphop', 'hip-hop', 'rap', 'rapper', 'mc', 'urban'],
    'trap': ['trap', 'trap beat', 'hi-hat', '808', 'atlanta', 'drill'],
    'boom_bap': ['boom bap', 'old school', '90s hip hop', 'golden era', 'sample based'],
    'instrumental_hiphop': ['instrumental hip hop', 'beat', 'instrumental', 'no vocals'],

    # === ROCK & ALTERNATIVE ===
    'rock': ['rock', 'guitar rock', 'rock band', 'drums', 'electric guitar'],
    'indie': ['indie', 'independent', 'alternative', 'alt rock', 'indie rock'],
    'metal': ['metal', 'heavy metal', 'hard rock', 'heavy', 'distortion', 'shred'],
    'punk': ['punk', 'punk rock', 'hardcore', 'fast', 'aggressive', 'raw energy'],
    'grunge': ['grunge', 'seattle', 'dirty', 'gritty', 'distorted'],

    # === JAZZ & BLUES ===
    'jazz': ['jazz', 'swing', 'bebop', 'cool jazz', 'smooth jazz', 'improvisation'],
    'blues': ['blues', 'bluesy', 'soulful', 'delta blues', 'chicago blues', 'slide guitar'],
    'soul': ['soul', 'motown', 'r&b', 'rhythm and blues', 'soulful'],
    'funk': ['funk', 'funky', 'groove', 'bass heavy', 'rhythmic', 'slap bass'],

    # === WORLD & ETHNIC ===
    'world': ['world', 'world music', 'ethnic', 'tribal', 'cultural', 'traditional'],
    'asian': ['asian', 'japanese', 'chinese', 'korean', 'oriental', 'eastern', 'j-pop', 'jpop', 'anime', 'kawaii'],
    'latin': ['latin', 'salsa', 'bossa nova', 'samba', 'tango', 'spanish', 'flamenco', 'mariachi'],
    'african': ['african', 'afrobeat', 'tribal drums', 'percussion', 'djembe', 'afro'],
    'celtic': ['celtic', 'irish', 'scottish', 'gaelic', 'folk celtic', 'fiddle', 'bagpipe'],
    'middle_eastern': ['middle eastern', 'arabic', 'persian', 'indian', 'bollywood', 'sitar', 'tabla'],

    # === MOODS & EMOTIONS ===
    'happy': ['happy', 'joyful', 'cheerful', 'uplifting', 'positive', 'bright', 'sunny', 'bouncy', 'playful'],
    'sad': ['sad', 'melancholy', 'somber', 'sorrowful', 'tearful', 'grief', 'loss', 'bittersweet'],
    'angry': ['angry', 'aggressive', 'intense', 'rage', 'fury', 'fierce', 'energetic burst'],
    'peaceful': ['peaceful', 'calm', 'serene', 'tranquil', 'gentle', 'soft', 'quiet', 'dreamy', 'tender'],
    'mysterious': ['mysterious', 'enigmatic', 'cryptic', 'puzzling', 'curious', 'wonder', 'curiosity'],
    'scary': ['scary', 'horror', 'creepy', 'spooky', 'haunting', 'terrifying', 'nightmare', 'eerie'],
    'inspirational': ['inspirational', 'motivational', 'uplifting', 'empowering', 'hopeful', 'triumphant'],

    # === ENERGY LEVELS ===
    'upbeat': ['upbeat', 'energetic', 'lively', 'dynamic', 'vibrant', 'peppy'],
    'relaxing': ['relaxing', 'soothing', 'calming', 'restful', 'unwinding'],
    'intense': ['intense', 'powerful', 'driving', 'hard hitting', 'forceful'],
    'gentle': ['gentle', 'soft', 'delicate', 'light', 'subtle', 'quiet'],

    # === RETRO & VINTAGE ===
    'retro': ['retro', 'vintage', 'old school', 'classic', 'throwback', 'nostalgic', 'catchy', 'melodies'],
    'chiptune': ['chiptune', '8-bit', '8bit', 'pixel', 'nes', 'gameboy', 'chip', 'nes-style', 'bleeps', 'bloops', 'synthesized'],
    'arcade': ['arcade', 'videogame', 'game', 'gaming', 'console', 'level', 'boss', 'game music', 'game audio'],
    '80s': ['80s', '1980s', 'eighties', 'synth pop', 'new wave', 'synth-pop'],
    '70s': ['70s', '1970s', 'seventies', 'disco', 'groovy', 'funky'],
    '60s': ['60s', '1960s', 'sixties', 'psychedelic', 'beatles', 'mod'],

    # === USE CASES ===
    'corporate': ['corporate', 'business', 'professional', 'presentation', 'commercial'],
    'advertising': ['advertising', 'ad', 'jingle', 'commercial', 'promo', 'marketing'],
    'youtube': ['youtube', 'vlog', 'content', 'creator', 'influencer', 'social media'],
    'podcast': ['podcast', 'intro', 'outro', 'transition', 'bumper', 'talk show'],
    'game_music': ['game', 'gaming', 'level music', 'boss battle', 'menu', 'victory'],
    'holiday': ['holiday', 'christmas', 'festive', 'celebration', 'party', 'new year'],
    'workout': ['workout', 'exercise', 'gym', 'fitness', 'running', 'training', 'sport'],
    'kids': ['kids', 'children', 'playful', 'cartoon', 'whimsical', 'fun', 'silly', 'cute', 'bubbly', 'sweet']
}

# Expanded SFX categories for fine-grained searching
# Organized by: UI/Game, Actions, Environment, Characters, Objects, Sci-Fi/Fantasy
SFX_CATEGORIES = {
    # === UI & INTERFACE ===
    'notification': ['notification', 'alert', 'ping', 'ding', 'chime', 'reminder', 'message', 'popup', 'toast'],
    'button': ['button', 'click', 'tap', 'press', 'toggle', 'switch', 'checkbox', 'select'],
    'menu': ['menu', 'ui', 'interface', 'navigate', 'scroll', 'hover', 'focus', 'tab'],
    'success': ['success', 'complete', 'achieve', 'unlock', 'win', 'victory', 'level up', 'bonus', 'reward', 'coin', 'collect'],
    'error': ['error', 'fail', 'wrong', 'invalid', 'denied', 'reject', 'lose', 'game over', 'death'],
    'typing': ['typing', 'keyboard', 'keystroke', 'type', 'letter', 'text', 'input'],

    # === ACTIONS & MOVEMENTS ===
    'whoosh': ['whoosh', 'swoosh', 'swish', 'sweep', 'swing', 'swipe', 'slash', 'fast', 'speed', 'rush'],
    'impact': ['impact', 'hit', 'punch', 'kick', 'slap', 'strike', 'thud', 'thump', 'knock'],
    'explosion': ['explosion', 'explode', 'blast', 'boom', 'detonate', 'bomb', 'burst', 'bang'],
    'crash': ['crash', 'smash', 'break', 'shatter', 'crack', 'destroy', 'collapse', 'debris'],
    'jump': ['jump', 'hop', 'bounce', 'spring', 'leap', 'land', 'drop'],
    'footstep': ['footstep', 'walk', 'run', 'step', 'stomp', 'tiptoe', 'shuffle', 'feet'],

    # === NATURE & WEATHER ===
    'rain': ['rain', 'drizzle', 'downpour', 'storm', 'raindrop', 'shower', 'wet'],
    'wind': ['wind', 'breeze', 'gust', 'howl', 'blow', 'windy', 'draft', 'air', 'winter wind'],
    'thunder': ['thunder', 'lightning', 'thunderstorm', 'rumble', 'electric storm', 'volcanic'],
    'water': ['water', 'splash', 'drip', 'flow', 'stream', 'river', 'pour', 'bubble', 'underwater', 'bubbles', 'swimming'],
    'ocean': ['ocean', 'sea', 'wave', 'beach', 'surf', 'tide', 'coastal', 'shore', 'whale', 'seagull', 'tropical'],
    'fire': ['fire', 'flame', 'burn', 'torch', 'campfire', 'fireplace', 'crackle', 'blaze', 'crackling'],
    'forest': ['forest', 'jungle', 'tree', 'leaves', 'rustling', 'woods', 'branch', 'nature', 'ambience'],

    # === ANIMALS & CREATURES ===
    'bird': ['bird', 'chirp', 'tweet', 'sing', 'crow', 'owl', 'eagle', 'seagull', 'wings', 'flap'],
    'dog': ['dog', 'bark', 'growl', 'puppy', 'howl', 'whine', 'pant', 'woof'],
    'cat': ['cat', 'meow', 'purr', 'hiss', 'kitten', 'feline'],
    'insect': ['insect', 'bug', 'bee', 'buzz', 'fly', 'mosquito', 'cricket', 'cicada'],
    'monster': ['monster', 'creature', 'beast', 'demon', 'alien', 'roar', 'growl', 'snarl', 'hiss'],

    # === HUMAN SOUNDS ===
    'voice': ['voice', 'speak', 'talk', 'say', 'vocal', 'human', 'mouth', 'dialogue'],
    'laugh': ['laugh', 'giggle', 'chuckle', 'funny', 'comedy', 'humor', 'haha', 'hehe'],
    'scream': ['scream', 'shout', 'yell', 'cry', 'shriek', 'terror', 'horror', 'afraid'],
    'breath': ['breath', 'breathe', 'exhale', 'inhale', 'sigh', 'gasp', 'pant', 'huff', 'drifting'],
    'eating': ['eat', 'chew', 'munch', 'crunch', 'bite', 'swallow', 'gulp', 'drink', 'slurp', 'food', 'delicious', 'yummy', 'meat', 'cake', 'candy', 'thirst'],
    'crowd': ['crowd', 'audience', 'cheer', 'applause', 'clap', 'people', 'murmur', 'chatter'],

    # === OBJECTS & ITEMS ===
    'door': ['door', 'open', 'close', 'creak', 'slam', 'knock', 'lock', 'unlock', 'handle'],
    'glass': ['glass', 'clink', 'shatter', 'break', 'bottle', 'crystal', 'window'],
    'metal': ['metal', 'clang', 'clank', 'metallic', 'iron', 'steel', 'chain', 'sword', 'blade'],
    'wood': ['wood', 'wooden', 'creak', 'crack', 'plank', 'board', 'timber', 'log'],
    'paper': ['paper', 'page', 'flip', 'tear', 'crumple', 'rustle', 'book', 'card'],
    'cloth': ['cloth', 'fabric', 'clothing', 'rip', 'tear', 'rustle', 'flag', 'cape'],
    'bell': ['bell', 'ring', 'chime', 'toll', 'jingle', 'doorbell', 'alarm'],

    # === MACHINES & VEHICLES ===
    'engine': ['engine', 'motor', 'car', 'vehicle', 'drive', 'accelerate', 'idle', 'rev'],
    'mechanical': ['mechanical', 'machine', 'gear', 'cog', 'hydraulic', 'piston', 'pump'],
    'electronic': ['electronic', 'electric', 'buzz', 'hum', 'static', 'power', 'circuit', 'glitch'],
    'robot': ['robot', 'android', 'mech', 'servo', 'mechanical', 'droid', 'cyborg'],

    # === WEAPONS ===
    'gun': ['gun', 'shoot', 'shot', 'bullet', 'rifle', 'pistol', 'reload', 'cock', 'fire'],
    'laser': ['laser', 'beam', 'ray', 'zap', 'pew', 'blaster', 'phaser', 'energy'],
    'sword': ['sword', 'blade', 'slash', 'slice', 'stab', 'parry', 'duel', 'unsheathe'],

    # === MAGIC & FANTASY ===
    'magic': ['magic', 'spell', 'cast', 'enchant', 'mystical', 'arcane', 'sorcery', 'witch', 'wizard', 'magical', 'enchanted'],
    'sparkle': ['sparkle', 'shimmer', 'twinkle', 'glitter', 'shine', 'glow', 'fairy', 'pixie', 'chime', 'chimes', 'wand'],
    'portal': ['portal', 'teleport', 'warp', 'dimension', 'vortex', 'rift', 'summon', 'wave'],
    'power_up': ['power up', 'powerup', 'buff', 'boost', 'charge', 'energy', 'aura', 'transform', 'collect', 'coin'],
    'heal': ['heal', 'health', 'restore', 'cure', 'regenerate', 'potion', 'medicine', 'bubbling'],

    # === SCI-FI & TECHNOLOGY ===
    'scifi': ['sci-fi', 'scifi', 'futuristic', 'space', 'spaceship', 'spacecraft', 'alien'],
    'computer': ['computer', 'digital', 'data', 'process', 'scan', 'download', 'upload', 'loading'],
    'alarm': ['alarm', 'siren', 'warning', 'emergency', 'danger', 'klaxon', 'horn'],
    'drone': ['drone', 'hum', 'ambient', 'atmosphere', 'background', 'tone', 'pad'],

    # === HORROR & TENSION ===
    'horror': ['horror', 'scary', 'creepy', 'spooky', 'eerie', 'haunted', 'dark', 'sinister'],
    'tension': ['tension', 'suspense', 'dramatic', 'intense', 'thriller', 'anxious', 'dread'],
    'ghost': ['ghost', 'spirit', 'phantom', 'apparition', 'paranormal', 'haunting', 'whisper'],

    # === CARTOON & COMEDY ===
    'cartoon': ['cartoon', 'comic', 'silly', 'wacky', 'zany', 'boing', 'sproing', 'wobble', 'anime', 'cute', 'squeaky'],
    'funny': ['funny', 'comedy', 'humor', 'joke', 'gag', 'silly', 'playful', 'quirky', 'cheerful'],

    # === MUSICAL & INSTRUMENTS ===
    'drum': ['drum', 'percussion', 'beat', 'snare', 'kick', 'cymbal', 'tom', 'hi-hat'],
    'stinger': ['stinger', 'accent', 'hit', 'musical hit', 'orchestra hit', 'brass hit', 'sting'],
    'transition': ['transition', 'riser', 'build', 'swell', 'drop', 'sweep', 'downer']
}

# Speech/Voice categories for TTS content
# Organized by: Gender, Style, Content Type, Phrases, Instructions, Media
SPEECH_CATEGORIES = {
    # === VOICE GENDER ===
    'male': ['male', 'man', 'gentleman', 'guy', 'masculine', 'his', 'he'],
    'female': ['female', 'woman', 'lady', 'feminine', 'her', 'she'],
    'child': ['child', 'kid', 'young', 'youth', 'little'],
    'neutral': ['neutral', 'androgynous', 'robotic'],

    # === VOICE STYLE ===
    'natural': ['natural', 'conversational', 'casual', 'normal'],
    'professional': ['professional', 'formal', 'business', 'corporate'],
    'dramatic': ['dramatic', 'theatrical', 'expressive', 'emotional'],
    'whisper': ['whisper', 'soft', 'quiet', 'hushed', 'asmr'],
    'robotic': ['robotic', 'mechanical', 'synthetic', 'ai', 'digital'],
    'announcer': ['announcer', 'broadcast', 'radio', 'presenter', 'dj'],

    # === CONTENT TYPE ===
    'announcement': ['announce', 'attention', 'notice', 'announcement', 'announcing'],
    'narration': ['narration', 'narrator', 'story', 'storytelling', 'narrative'],
    'dialogue': ['dialogue', 'conversation', 'talk', 'speaking', 'chat'],
    'monologue': ['monologue', 'solo', 'speech', 'address'],
    'voiceover': ['voiceover', 'voice-over', 'vo', 'narrate'],
    'audiobook': ['audiobook', 'book', 'reading', 'chapter', 'novel'],

    # === NUMBERS & DATA ===
    'numbers': ['number', 'digit', 'count', 'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'hundred', 'thousand', 'million'],
    'counting': ['counting', 'count', 'sequence', 'series'],
    'time': ['time', 'clock', 'hour', 'minute', 'second', 'o\'clock', 'am', 'pm', 'noon', 'midnight'],
    'date': ['date', 'day', 'month', 'year', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'],
    'currency': ['dollar', 'cent', 'price', 'money', 'cost', 'pound', 'euro', 'yen'],
    'phone_number': ['phone', 'call', 'dial', 'telephone', 'number'],
    'address': ['address', 'street', 'avenue', 'road', 'city', 'state', 'zip', 'location'],

    # === COMMON PHRASES ===
    'greeting': ['hello', 'hi', 'hey', 'welcome', 'good morning', 'good afternoon', 'good evening', 'greetings'],
    'farewell': ['goodbye', 'bye', 'farewell', 'see you', 'take care', 'later', 'goodnight'],
    'thanks': ['thank', 'thanks', 'appreciate', 'grateful', 'gratitude'],
    'apology': ['sorry', 'apologize', 'apology', 'excuse me', 'pardon', 'forgive'],
    'confirmation': ['yes', 'correct', 'confirmed', 'okay', 'right', 'affirmative', 'agreed', 'indeed'],
    'denial': ['no', 'incorrect', 'wrong', 'denied', 'negative', 'refuse', 'decline'],
    'question': ['what', 'where', 'when', 'how', 'why', 'who', 'which', 'can', 'could', 'would', 'should'],

    # === INSTRUCTIONS ===
    'directions': ['turn', 'left', 'right', 'straight', 'continue', 'proceed', 'navigate', 'route'],
    'tutorial': ['step', 'first', 'next', 'then', 'finally', 'begin', 'start', 'end', 'complete'],
    'warning': ['warning', 'caution', 'danger', 'alert', 'careful', 'beware', 'hazard'],
    'reminder': ['remember', 'don\'t forget', 'reminder', 'note', 'recall'],
    'prompt': ['please', 'enter', 'press', 'select', 'choose', 'click', 'tap', 'input'],

    # === MEDIA & ENTERTAINMENT ===
    'commercial': ['buy', 'sale', 'discount', 'offer', 'limited', 'shop', 'order', 'deal'],
    'trailer_voice': ['coming soon', 'this summer', 'one man', 'in a world', 'epic', 'adventure'],
    'podcast': ['episode', 'today we', 'welcome to', 'podcast', 'show', 'host', 'guest'],
    'radio': ['station', 'fm', 'am', 'live', 'broadcast', 'on air', 'tune in'],
    'game_voice': ['game over', 'level', 'player', 'score', 'ready', 'fight', 'victory', 'defeat'],
    'character': ['hero', 'villain', 'wizard', 'knight', 'princess', 'dragon', 'monster'],
    'news': ['breaking', 'report', 'tonight', 'sources', 'according', 'headline', 'update'],
    'weather': ['temperature', 'degrees', 'forecast', 'rain', 'sunny', 'cloudy', 'wind', 'humidity'],
    'sports': ['goal', 'score', 'team', 'player', 'game', 'match', 'championship', 'winner'],
    'traffic': ['traffic', 'highway', 'road', 'congestion', 'delay', 'accident', 'route'],

    # === PHONETIC & LETTERS ===
    'alphabet': ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'letter', 'alphabet', 'spelling'],
    'phonetic': ['alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot', 'nato', 'phonetic'],

    # === SYSTEM & UI ===
    'system': ['system', 'error', 'loading', 'complete', 'processing', 'ready', 'standby', 'initializing'],
    'assistant': ['assistant', 'help', 'support', 'service', 'customer', 'agent'],

    # === ACCENTS (from voice metadata) ===
    'british': ['british', 'uk', 'england', 'english'],
    'american': ['american', 'usa', 'us', 'united states'],
    'australian': ['australian', 'aussie', 'australia'],
    'scottish': ['scottish', 'scotland', 'scots'],
    'irish': ['irish', 'ireland'],
}

# =============================================================================
# Project Sources
# =============================================================================
# Assets can be tagged with a source to indicate which project uses them.
# This enables a unified assets tab showing all project audio in one place.
# Format: 'source_id': {'name': 'Display Name', 'icon': 'icon-name', 'type': 'game'|'app'}

PROJECT_SOURCES = {
    'byk3s': {
        'name': 'Byk3s',
        'description': 'Cyberpunk bike combat game',
        'icon': 'gamepad',
        'type': 'game'
    },
    'graphlings': {
        'name': 'Graphlings',
        'description': 'AI crystal creature companions - offline Godot game',
        'icon': 'sparkles',
        'type': 'game'
    },
}

SCHEMA = """
-- Generations table (replaces generations.json)
CREATE TABLE IF NOT EXISTS generations (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL UNIQUE,
    prompt TEXT NOT NULL,
    model TEXT NOT NULL,
    duration INTEGER NOT NULL,
    is_loop BOOLEAN DEFAULT FALSE,
    quality_score INTEGER,
    spectrogram TEXT,
    user_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upvotes INTEGER DEFAULT 0,
    downvotes INTEGER DEFAULT 0
);

-- Votes table with private feedback (no public comments)
CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    vote INTEGER NOT NULL,
    feedback_reasons TEXT,  -- JSON array of selected feedback tags
    notes TEXT,             -- Private notes (not displayed publicly)
    suggested_model TEXT,   -- Reclassification suggestion: 'music' or 'audio'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE,
    UNIQUE(generation_id, user_id)
);

-- Favorites table
CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    generation_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE,
    UNIQUE(user_id, generation_id)
);

-- Tag Suggestions table for crowdsourced categorization
CREATE TABLE IF NOT EXISTS tag_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    suggested_category TEXT NOT NULL,  -- The category the user thinks fits better
    action TEXT NOT NULL DEFAULT 'add',  -- 'add' or 'remove'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE,
    UNIQUE(generation_id, user_id, suggested_category, action)
);

-- Tag Consensus table to track when categories should be updated
CREATE TABLE IF NOT EXISTS tag_consensus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_id TEXT NOT NULL,
    category TEXT NOT NULL,
    action TEXT NOT NULL DEFAULT 'add',  -- 'add' or 'remove'
    suggestion_count INTEGER DEFAULT 1,
    applied BOOLEAN DEFAULT FALSE,
    applied_at TIMESTAMP,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE,
    UNIQUE(generation_id, category, action)
);

-- Playlists table
CREATE TABLE IF NOT EXISTS playlists (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Playlist tracks junction table
CREATE TABLE IF NOT EXISTS playlist_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id TEXT NOT NULL,
    generation_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE,
    UNIQUE(playlist_id, generation_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_generations_model ON generations(model);
CREATE INDEX IF NOT EXISTS idx_generations_created ON generations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_generations_user_id ON generations(user_id);
-- idx_generations_public created after is_public column migration in init_db()
CREATE INDEX IF NOT EXISTS idx_votes_generation ON votes(generation_id);
CREATE INDEX IF NOT EXISTS idx_votes_created_at ON votes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_favorites_generation ON favorites(generation_id);
CREATE INDEX IF NOT EXISTS idx_tag_suggestions_generation ON tag_suggestions(generation_id);
CREATE INDEX IF NOT EXISTS idx_tag_suggestions_category ON tag_suggestions(suggested_category);
CREATE INDEX IF NOT EXISTS idx_tag_consensus_generation ON tag_consensus(generation_id);
CREATE INDEX IF NOT EXISTS idx_playlists_user ON playlists(user_id);
CREATE INDEX IF NOT EXISTS idx_playlist_tracks_playlist ON playlist_tracks(playlist_id);
CREATE INDEX IF NOT EXISTS idx_playlist_tracks_position ON playlist_tracks(playlist_id, position);
"""

# Full-text search table (created separately due to IF NOT EXISTS limitation)
FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS generations_fts USING fts5(
    prompt,
    content='generations',
    content_rowid='rowid'
);
"""

FTS_TRIGGERS = """
-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS generations_ai AFTER INSERT ON generations BEGIN
    INSERT INTO generations_fts(rowid, prompt) VALUES (NEW.rowid, NEW.prompt);
END;

CREATE TRIGGER IF NOT EXISTS generations_ad AFTER DELETE ON generations BEGIN
    INSERT INTO generations_fts(generations_fts, rowid, prompt) VALUES('delete', OLD.rowid, OLD.prompt);
END;

CREATE TRIGGER IF NOT EXISTS generations_au AFTER UPDATE ON generations BEGIN
    INSERT INTO generations_fts(generations_fts, rowid, prompt) VALUES('delete', OLD.rowid, OLD.prompt);
    INSERT INTO generations_fts(rowid, prompt) VALUES (NEW.rowid, NEW.prompt);
END;
"""


@contextmanager
def get_db():
    """Get database connection with row factory and proper concurrency settings."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)  # 30 second timeout for locks
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # Better concurrency
    conn.execute("PRAGMA busy_timeout = 30000")  # 30 second busy timeout
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize database schema."""
    with get_db() as conn:
        conn.executescript(SCHEMA)
        try:
            conn.executescript(FTS_SCHEMA)
            conn.executescript(FTS_TRIGGERS)
        except sqlite3.OperationalError:
            pass  # FTS table may already exist

        # Migration: Add feedback columns to votes table if missing
        try:
            conn.execute("ALTER TABLE votes ADD COLUMN feedback_reasons TEXT")
            print("[DB] Added feedback_reasons column to votes table")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            conn.execute("ALTER TABLE votes ADD COLUMN notes TEXT")
            print("[DB] Added notes column to votes table")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            conn.execute("ALTER TABLE votes ADD COLUMN suggested_model TEXT")
            print("[DB] Added suggested_model column to votes table")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Add category column if missing
        try:
            conn.execute("ALTER TABLE generations ADD COLUMN category TEXT")
            print("[DB] Added category column to generations table")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Index for fast category filtering
        conn.execute("CREATE INDEX IF NOT EXISTS idx_generations_category ON generations(category)")

        # Migration: Add license_type column for differentiating AI-generated (CC0) vs human-made content
        try:
            conn.execute("ALTER TABLE generations ADD COLUMN license_type TEXT DEFAULT 'cc0'")
            print("[DB] Added license_type column to generations table")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Add creator tracking for user uploads from widget
        try:
            conn.execute("ALTER TABLE generations ADD COLUMN creator_id TEXT")
            print("[DB] Added creator_id column to generations table")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            conn.execute("ALTER TABLE generations ADD COLUMN creator_name TEXT")
            print("[DB] Added creator_name column to generations table")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            conn.execute("ALTER TABLE generations ADD COLUMN is_user_upload BOOLEAN DEFAULT FALSE")
            print("[DB] Added is_user_upload column to generations table")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Index for creator lookups
        conn.execute("CREATE INDEX IF NOT EXISTS idx_generations_creator ON generations(creator_id)")

        # Migration: Add is_public column for content moderation
        # New generations start private, admin reviews before promoting to public library
        try:
            conn.execute("ALTER TABLE generations ADD COLUMN is_public BOOLEAN DEFAULT FALSE")
            print("[DB] Added is_public column to generations table")
            # Mark ALL existing generations as public (grandfathered in)
            # Use is_public = 0 check since DEFAULT FALSE gives 0, not NULL
            conn.execute("UPDATE generations SET is_public = TRUE WHERE is_public = 0 OR is_public IS NULL")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Create index for is_public after column exists
        conn.execute("CREATE INDEX IF NOT EXISTS idx_generations_public ON generations(is_public)")
        # Composite index for common library query (public + sort by recent)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_generations_public_created ON generations(is_public, created_at DESC)")
        # Composite index for model filter with date sort
        conn.execute("CREATE INDEX IF NOT EXISTS idx_generations_model_created ON generations(model, created_at DESC)")

        # Migration: Add admin_reviewed flag for moderation workflow
        try:
            conn.execute("ALTER TABLE generations ADD COLUMN admin_reviewed BOOLEAN DEFAULT FALSE")
            print("[DB] Added admin_reviewed column to generations table")
            # Mark existing as reviewed (grandfathered)
            conn.execute("UPDATE generations SET admin_reviewed = TRUE WHERE admin_reviewed IS NULL")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Add play/download tracking for analytics
        try:
            conn.execute("ALTER TABLE generations ADD COLUMN play_count INTEGER DEFAULT 0")
            print("[DB] Added play_count column to generations table")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            conn.execute("ALTER TABLE generations ADD COLUMN unique_plays INTEGER DEFAULT 0")
            print("[DB] Added unique_plays column to generations table")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            conn.execute("ALTER TABLE generations ADD COLUMN download_count INTEGER DEFAULT 0")
            print("[DB] Added download_count column to generations table")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Create plays tracking table for unique play counting
        conn.execute("""
            CREATE TABLE IF NOT EXISTS play_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generation_id TEXT NOT NULL,
                user_id TEXT,
                session_id TEXT,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                play_duration REAL,
                source TEXT DEFAULT 'radio',
                FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_play_events_generation ON play_events(generation_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_play_events_user ON play_events(user_id)")
        # Index for trending calculations (played_at) and composite for efficient join+filter
        conn.execute("CREATE INDEX IF NOT EXISTS idx_play_events_played_at ON play_events(played_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_play_events_gen_played ON play_events(generation_id, played_at DESC)")

        # Create downloads tracking table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS download_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generation_id TEXT NOT NULL,
                user_id TEXT,
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                format TEXT DEFAULT 'wav',
                FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_download_events_generation ON download_events(generation_id)")

        # Migration: Add voice_id column for TTS voice tracking
        try:
            conn.execute("ALTER TABLE generations ADD COLUMN voice_id TEXT")
            print("[DB] Added voice_id column to generations table")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Create index for voice_id lookups
        conn.execute("CREATE INDEX IF NOT EXISTS idx_generations_voice ON generations(voice_id)")

        # Migration: Add source column for project tagging
        # Allows assets to be tagged with which project uses them (e.g., 'byk3s')
        try:
            conn.execute("ALTER TABLE generations ADD COLUMN source TEXT")
            print("[DB] Added source column to generations table for project tagging")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Create index for source lookups (fast filtering by project)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_generations_source ON generations(source)")

        # Migration: Add action column to tag_suggestions if missing
        try:
            conn.execute("ALTER TABLE tag_suggestions ADD COLUMN action TEXT NOT NULL DEFAULT 'add'")
            print("[DB] Added action column to tag_suggestions table")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Add action column to tag_consensus if missing
        try:
            conn.execute("ALTER TABLE tag_consensus ADD COLUMN action TEXT NOT NULL DEFAULT 'add'")
            print("[DB] Added action column to tag_consensus table")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Rename new_category to category in tag_consensus if needed
        try:
            # Check if new_category column exists (old schema)
            cursor = conn.execute("PRAGMA table_info(tag_consensus)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'new_category' in columns and 'category' not in columns:
                # SQLite doesn't support RENAME COLUMN in older versions, so we'll just use new_category
                pass
        except sqlite3.OperationalError:
            pass

        conn.commit()
    print("[DB] Database initialized")


def migrate_from_json():
    """Migrate existing generations.json to SQLite."""
    if not os.path.exists(METADATA_FILE):
        print("[DB] No generations.json to migrate")
        return 0

    # Check if we already have data in the database
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
        if count > 0:
            print(f"[DB] Database already has {count} generations, skipping JSON migration")
            return 0

    try:
        with open(METADATA_FILE, 'r') as f:
            metadata = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[DB] Error reading generations.json: {e}")
        print("[DB] Skipping migration due to corrupt JSON file")
        return 0

    if not metadata:
        print("[DB] Empty generations.json")
        return 0

    migrated = 0
    with get_db() as conn:
        for filename, info in metadata.items():
            # Extract ID from filename (remove .wav extension)
            gen_id = filename.replace('.wav', '')

            try:
                conn.execute("""
                    INSERT OR IGNORE INTO generations
                    (id, filename, prompt, model, duration, is_loop, quality_score, spectrogram, user_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    gen_id,
                    filename,
                    info.get('prompt', 'Unknown'),
                    info.get('model', 'music'),
                    info.get('duration', 8),
                    info.get('loop', False),
                    info.get('quality_score'),
                    info.get('spectrogram'),
                    info.get('user_id'),
                    info.get('created', datetime.now().isoformat())
                ))
                migrated += 1
            except sqlite3.Error as e:
                print(f"[DB] Migration error for {filename}: {e}")

        conn.commit()

    # Rebuild FTS index
    with get_db() as conn:
        conn.execute("INSERT INTO generations_fts(generations_fts) VALUES('rebuild')")
        conn.commit()

    print(f"[DB] Migrated {migrated} generations from JSON")
    return migrated


# =============================================================================
# Generation CRUD
# =============================================================================

def create_generation(gen_id, filename, prompt, model, duration, is_loop=False,
                      quality_score=None, spectrogram=None, user_id=None, is_public=False,
                      voice_id=None, tags=None):
    """Create a new generation record with auto-categorization.

    Args:
        gen_id: Unique generation ID
        filename: Output audio filename
        prompt: Generation prompt text
        model: Model type ('music', 'audio', 'voice')
        duration: Audio duration in seconds
        is_loop: Whether audio is loopable
        quality_score: Quality analysis score (0-100)
        spectrogram: Path to spectrogram image
        user_id: Creator's user ID (from auth)
        is_public: Whether to add to public library (default False for moderation)
        voice_id: For voice model, the TTS voice ID used (e.g., 'en_GB-vctk-medium')
        tags: Optional list of category tags to merge with auto-categorization

    New generations start as private (is_public=False) and require admin review
    before being promoted to the public library. All content is CC0 licensed.
    """
    # Auto-categorize based on prompt
    auto_categories = categorize_prompt(prompt, model)

    # Merge with provided tags if any
    if tags:
        # Combine auto categories with provided tags, removing duplicates
        all_categories = list(set(auto_categories + tags))
    else:
        all_categories = auto_categories

    category_json = json.dumps(all_categories) if all_categories else None

    with get_db() as conn:
        # If is_public=True, it's from localhost/admin and doesn't need review
        admin_reviewed = is_public
        conn.execute("""
            INSERT INTO generations
            (id, filename, prompt, model, duration, is_loop, quality_score, spectrogram, user_id, category, is_public, admin_reviewed, voice_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (gen_id, filename, prompt, model, duration, is_loop, quality_score, spectrogram, user_id, category_json, is_public, admin_reviewed, voice_id))
        conn.commit()


def get_generation(gen_id):
    """Get a single generation by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM generations WHERE id = ?", (gen_id,)
        ).fetchone()
        return dict(row) if row else None


def get_library(page=1, per_page=20, model=None, search=None, sort='recent', user_id=None, category=None, source=None):
    """
    Get paginated PUBLIC library with filters.

    The public library only shows generations that have been reviewed and approved.
    For user's own private generations, use get_user_generations() instead.

    Args:
        page: Page number (1-indexed)
        per_page: Items per page (max 100)
        model: Filter by 'music' or 'audio'
        search: Full-text search query
        sort: 'recent', 'popular', or 'rating'
        user_id: Deprecated - use get_user_generations() for private content
        category: Filter by category/genre (e.g., 'ambient', 'nature')
        source: Filter by project source (e.g., 'byk3s')

    Returns:
        dict with items, total, page, per_page, pages
    """
    per_page = min(per_page, 100)
    offset = (page - 1) * per_page

    # Build query - PUBLIC library only shows approved content
    conditions = ["g.is_public = TRUE"]
    params = []

    if model:
        conditions.append("g.model = ?")
        params.append(model)

    # user_id filter deprecated for library - use get_user_generations() for private content
    if user_id:
        conditions.append("g.user_id = ?")
        params.append(user_id)

    # Category filter (stored as JSON array)
    if category:
        conditions.append("g.category LIKE ?")
        params.append(f'%"{category}"%')

    # Source filter for projects
    if source:
        conditions.append("g.source = ?")
        params.append(source)

    # Full-text search (sanitized for FTS5 injection prevention)
    if search:
        fts_query = sanitize_fts5_query(search)
        if fts_query:
            conditions.append("g.rowid IN (SELECT rowid FROM generations_fts WHERE generations_fts MATCH ?)")
            params.append(fts_query)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Sort order
    order_map = {
        'recent': 'g.created_at DESC',
        'popular': '(g.upvotes + g.downvotes) DESC, g.created_at DESC',
        'rating': '(g.upvotes - g.downvotes) DESC, g.created_at DESC'
    }
    order_clause = order_map.get(sort, 'g.created_at DESC')

    with get_db() as conn:
        # Get total count
        count_sql = f"SELECT COUNT(*) FROM generations g WHERE {where_clause}"
        total = conn.execute(count_sql, params).fetchone()[0]

        # Get page items
        items_sql = f"""
            SELECT g.*
            FROM generations g
            WHERE {where_clause}
            ORDER BY {order_clause}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(items_sql, params + [per_page, offset]).fetchall()

    items = [dict(row) for row in rows]
    pages = (total + per_page - 1) // per_page

    return {
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': pages
    }


def get_random_tracks(model=None, search=None, count=10, min_duration=60):
    """Get random tracks for radio shuffle."""
    conditions = []
    params = []

    # Filter out short tracks (sound effects) - minimum 60 seconds for radio
    if min_duration:
        conditions.append("g.duration >= ?")
        params.append(min_duration)

    if model:
        conditions.append("g.model = ?")
        params.append(model)

    # Full-text search (sanitized for FTS5 injection prevention)
    if search:
        fts_query = sanitize_fts5_query(search)
        if fts_query:
            conditions.append("g.rowid IN (SELECT rowid FROM generations_fts WHERE generations_fts MATCH ?)")
            params.append(fts_query)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    with get_db() as conn:
        sql = f"""
            SELECT * FROM generations g
            WHERE {where_clause}
            ORDER BY RANDOM()
            LIMIT ?
        """
        rows = conn.execute(sql, params + [count]).fetchall()

    return [dict(row) for row in rows]


def get_random_tracks_excluding(model=None, search=None, count=10, min_duration=60, exclude_ids=None):
    """Get random tracks for radio, excluding recently played."""
    conditions = []
    params = []

    # Filter out short tracks - minimum 60 seconds for radio
    if min_duration:
        conditions.append("g.duration >= ?")
        params.append(min_duration)

    if model:
        conditions.append("g.model = ?")
        params.append(model)

    # Exclude recently played tracks
    if exclude_ids:
        placeholders = ','.join('?' * len(exclude_ids))
        conditions.append(f"g.id NOT IN ({placeholders})")
        params.extend(exclude_ids)

    # Full-text search (sanitized for FTS5 injection prevention)
    if search:
        fts_query = sanitize_fts5_query(search)
        if fts_query:
            conditions.append("g.rowid IN (SELECT rowid FROM generations_fts WHERE generations_fts MATCH ?)")
            params.append(fts_query)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    with get_db() as conn:
        sql = f"""
            SELECT * FROM generations g
            WHERE {where_clause}
            ORDER BY RANDOM()
            LIMIT ?
        """
        rows = conn.execute(sql, params + [count]).fetchall()

    return [dict(row) for row in rows]


def delete_generation(gen_id):
    """Delete a generation and its votes (cascades)."""
    with get_db() as conn:
        conn.execute("DELETE FROM generations WHERE id = ?", (gen_id,))
        conn.commit()


# =============================================================================
# User Generations ("My Generations") - Private Content Management
# =============================================================================

def get_user_generations(user_id, model=None, page=1, per_page=50):
    """
    Get a user's private generations grouped by model type.

    This returns the user's own generations (both public and private),
    organized for the "My Generations" section of their profile.

    Args:
        user_id: The user's ID
        model: Optional filter by 'music', 'audio', or 'voice'
        page: Page number
        per_page: Items per page

    Returns:
        dict with items, total, page, per_page, pages, and grouped counts
    """
    if not user_id:
        return {'items': [], 'total': 0, 'page': 1, 'pages': 0, 'by_model': {}}

    per_page = min(per_page, 100)
    offset = (page - 1) * per_page

    conditions = ["g.user_id = ?"]
    params = [user_id]

    if model:
        conditions.append("g.model = ?")
        params.append(model)

    where_clause = " AND ".join(conditions)

    with get_db() as conn:
        # Get total count
        total = conn.execute(
            f"SELECT COUNT(*) FROM generations g WHERE {where_clause}",
            params
        ).fetchone()[0]

        # Get items with favorite status
        items_sql = f"""
            SELECT g.*,
                   (SELECT 1 FROM favorites f WHERE f.generation_id = g.id AND f.user_id = ?) as is_favorite
            FROM generations g
            WHERE {where_clause}
            ORDER BY g.created_at DESC
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(items_sql, [user_id] + params + [per_page, offset]).fetchall()

        # Get counts by model type
        counts = conn.execute("""
            SELECT model, COUNT(*) as count
            FROM generations
            WHERE user_id = ?
            GROUP BY model
        """, (user_id,)).fetchall()

    items = [dict(row) for row in rows]
    pages = (total + per_page - 1) // per_page if total > 0 else 0
    by_model = {row['model']: row['count'] for row in counts}

    return {
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': pages,
        'by_model': by_model
    }


def get_user_storage_info(user_id, tier='free'):
    """
    Get storage usage information for a user.

    Args:
        user_id: The user's ID
        tier: User's subscription tier for limit lookup

    Returns:
        dict with used, limit, percent_used, can_generate
    """
    limit = USER_STORAGE_LIMITS.get(tier, USER_STORAGE_LIMITS['free'])

    with get_db() as conn:
        used = conn.execute(
            "SELECT COUNT(*) FROM generations WHERE user_id = ? AND is_public = FALSE",
            (user_id,)
        ).fetchone()[0]

        # Count favorites (these are protected from auto-deletion)
        favorites = conn.execute("""
            SELECT COUNT(*) FROM favorites f
            JOIN generations g ON f.generation_id = g.id
            WHERE f.user_id = ? AND g.user_id = ?
        """, (user_id, user_id)).fetchone()[0]

    percent = (used / limit * 100) if limit > 0 else 0

    return {
        'used': used,
        'limit': limit,
        'favorites': favorites,
        'percent_used': round(percent, 1),
        'can_generate': used < limit,
        'near_limit': percent >= 80,
        'at_limit': used >= limit
    }


def cleanup_old_generations(user_id, tier='free', keep_count=None):
    """
    Remove oldest non-favorited generations to make room for new ones.

    Called automatically when user exceeds storage limit.
    Favorites are NEVER deleted - only non-favorited generations.

    Args:
        user_id: The user's ID
        tier: User's subscription tier
        keep_count: Override number to keep (default: tier limit)

    Returns:
        Number of generations deleted
    """
    limit = keep_count if keep_count is not None else USER_STORAGE_LIMITS.get(tier, USER_STORAGE_LIMITS['free'])

    with get_db() as conn:
        # Get IDs of generations to delete (oldest first, excluding favorites)
        # Only delete private (is_public=FALSE) generations that aren't favorited
        to_delete = conn.execute("""
            SELECT g.id, g.filename, g.spectrogram
            FROM generations g
            WHERE g.user_id = ?
              AND g.is_public = FALSE
              AND g.id NOT IN (SELECT generation_id FROM favorites WHERE user_id = ?)
            ORDER BY g.created_at ASC
            LIMIT (
                SELECT MAX(0, COUNT(*) - ?) FROM generations
                WHERE user_id = ? AND is_public = FALSE
                  AND id NOT IN (SELECT generation_id FROM favorites WHERE user_id = ?)
            )
        """, (user_id, user_id, limit, user_id, user_id)).fetchall()

        deleted_count = 0
        for row in to_delete:
            gen_id = row['id']
            filename = row['filename']
            spectrogram = row['spectrogram']

            # Delete files from disk
            # SECURITY: Use basename to prevent path traversal attacks
            # Even though filenames come from DB, defense in depth is important
            safe_filename = os.path.basename(filename) if filename else None
            if safe_filename and safe_filename == filename:  # Ensure no path components
                audio_path = os.path.join('generated', safe_filename)
                if os.path.exists(audio_path):
                    try:
                        os.remove(audio_path)
                    except OSError as e:
                        print(f"[Storage] Warning: Failed to remove audio file {audio_path}: {e}")
            elif filename:
                print(f"[SECURITY] Blocked potential path traversal in cleanup: {filename}")

            if spectrogram:
                safe_spectrogram = os.path.basename(spectrogram)
                if safe_spectrogram and safe_spectrogram == spectrogram:  # Ensure no path components
                    spec_path = os.path.join('spectrograms', safe_spectrogram)
                    if os.path.exists(spec_path):
                        try:
                            os.remove(spec_path)
                        except OSError as e:
                            print(f"[Storage] Warning: Failed to remove spectrogram {spec_path}: {e}")
                else:
                    print(f"[SECURITY] Blocked potential path traversal in spectrogram cleanup: {spectrogram}")

            # Delete from database
            conn.execute("DELETE FROM generations WHERE id = ?", (gen_id,))
            deleted_count += 1

        if deleted_count > 0:
            conn.commit()
            print(f"[Storage] Cleaned up {deleted_count} old generations for user {user_id[:8]}...")

    return deleted_count


# =============================================================================
# Admin Moderation Functions
# =============================================================================

def get_pending_moderation(page=1, per_page=50, model=None):
    """
    Get generations pending admin review.

    Args:
        page: Page number
        per_page: Items per page
        model: Optional filter by model type

    Returns:
        dict with items and pagination info
    """
    per_page = min(per_page, 100)
    offset = (page - 1) * per_page

    conditions = ["admin_reviewed = FALSE"]
    params = []

    if model:
        conditions.append("model = ?")
        params.append(model)

    where_clause = " AND ".join(conditions)

    with get_db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM generations WHERE {where_clause}",
            params
        ).fetchone()[0]

        rows = conn.execute(f"""
            SELECT * FROM generations
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, params + [per_page, offset]).fetchall()

    items = [dict(row) for row in rows]
    pages = (total + per_page - 1) // per_page if total > 0 else 0

    return {
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': pages
    }


def moderate_generation(gen_id, admin_user_id, action, reason=None):
    """
    Moderate a generation (approve/reject for public library).

    Args:
        gen_id: Generation ID
        admin_user_id: ID of admin performing moderation
        action: 'approve' (add to public) or 'reject' (keep private/delete)
        reason: Optional reason for rejection

    Returns:
        dict with success status
    """
    with get_db() as conn:
        gen = conn.execute("SELECT * FROM generations WHERE id = ?", (gen_id,)).fetchone()
        if not gen:
            return {'success': False, 'error': 'Generation not found'}

        if action == 'approve':
            conn.execute("""
                UPDATE generations
                SET is_public = TRUE, admin_reviewed = TRUE
                WHERE id = ?
            """, (gen_id,))
            conn.commit()
            return {'success': True, 'action': 'approved', 'is_public': True}

        elif action == 'reject':
            # Keep private, mark as reviewed
            conn.execute("""
                UPDATE generations
                SET is_public = FALSE, admin_reviewed = TRUE
                WHERE id = ?
            """, (gen_id,))
            conn.commit()
            return {'success': True, 'action': 'rejected', 'is_public': False}

        elif action == 'delete':
            # Remove entirely (for really bad content)
            conn.execute("DELETE FROM generations WHERE id = ?", (gen_id,))
            conn.commit()
            return {'success': True, 'action': 'deleted'}

        return {'success': False, 'error': f'Unknown action: {action}'}


def bulk_moderate(gen_ids, admin_user_id, action):
    """
    Moderate multiple generations at once.

    Args:
        gen_ids: List of generation IDs
        admin_user_id: ID of admin
        action: 'approve', 'reject', or 'delete'

    Returns:
        dict with count of processed items
    """
    if not gen_ids:
        return {'success': True, 'processed': 0}

    processed = 0
    errors = []
    for gen_id in gen_ids:
        try:
            result = moderate_generation(gen_id, admin_user_id, action)
            if result.get('success'):
                processed += 1
            else:
                errors.append({'id': gen_id, 'error': result.get('error', 'Unknown error')})
        except Exception as e:
            errors.append({'id': gen_id, 'error': str(e)})

    result = {'success': True, 'processed': processed, 'total': len(gen_ids)}
    if errors:
        result['errors'] = errors
    return result


# =============================================================================
# Voting with Private Feedback
# =============================================================================

def vote(generation_id, user_id, vote_value, feedback_reasons=None, notes=None, suggested_model=None):
    """
    Cast or update a vote with optional private feedback.

    Args:
        generation_id: The generation ID
        user_id: The voter's user ID
        vote_value: 1 (upvote), -1 (downvote), or 0 (remove)
        feedback_reasons: List of feedback tags (e.g., ['catchy', 'quality'])
        notes: Private notes (not displayed publicly)
        suggested_model: Reclassification suggestion ('music' or 'audio')

    Returns:
        dict with upvotes, downvotes, user_vote
    """
    # Convert feedback_reasons list to JSON string
    reasons_json = json.dumps(feedback_reasons) if feedback_reasons else None

    with get_db() as conn:
        if vote_value == 0:
            # Remove vote
            conn.execute(
                "DELETE FROM votes WHERE generation_id = ? AND user_id = ?",
                (generation_id, user_id)
            )
        else:
            # Upsert vote with feedback
            conn.execute("""
                INSERT INTO votes (generation_id, user_id, vote, feedback_reasons, notes, suggested_model)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(generation_id, user_id)
                DO UPDATE SET vote = ?, feedback_reasons = ?, notes = ?, suggested_model = ?, created_at = CURRENT_TIMESTAMP
            """, (generation_id, user_id, vote_value, reasons_json, notes, suggested_model,
                  vote_value, reasons_json, notes, suggested_model))

        # Recalculate denormalized counts atomically using UPDATE with subquery
        conn.execute("""
            UPDATE generations SET
                upvotes = (SELECT COALESCE(SUM(CASE WHEN vote = 1 THEN 1 ELSE 0 END), 0) FROM votes WHERE generation_id = ?),
                downvotes = (SELECT COALESCE(SUM(CASE WHEN vote = -1 THEN 1 ELSE 0 END), 0) FROM votes WHERE generation_id = ?)
            WHERE id = ?
        """, (generation_id, generation_id, generation_id))

        conn.commit()

        # Get updated counts
        counts = conn.execute("""
            SELECT upvotes, downvotes FROM generations WHERE id = ?
        """, (generation_id,)).fetchone()

        # Handle case where generation doesn't exist
        if not counts:
            return {'success': False, 'error': 'Generation not found'}

        # Get user's current vote
        user_vote_row = conn.execute(
            "SELECT vote FROM votes WHERE generation_id = ? AND user_id = ?",
            (generation_id, user_id)
        ).fetchone()

        return {
            'success': True,
            'upvotes': counts['upvotes'],
            'downvotes': counts['downvotes'],
            'user_vote': user_vote_row['vote'] if user_vote_row else 0
        }


def get_user_votes(generation_ids, user_id):
    """Get user's votes for multiple generations."""
    if not generation_ids:
        return {}

    placeholders = ','.join('?' * len(generation_ids))
    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT generation_id, vote FROM votes
            WHERE generation_id IN ({placeholders}) AND user_id = ?
        """, generation_ids + [user_id]).fetchall()

    return {row['generation_id']: row['vote'] for row in rows}


def get_feedback_stats():
    """Get aggregate feedback statistics for admin review."""
    with get_db() as conn:
        # Count feedback reasons across all votes
        rows = conn.execute("""
            SELECT feedback_reasons FROM votes
            WHERE feedback_reasons IS NOT NULL AND feedback_reasons != 'null'
        """).fetchall()

    reason_counts = {}
    for row in rows:
        try:
            reasons = json.loads(row['feedback_reasons'])
            for reason in reasons:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass

    return reason_counts


def get_generation_feedback(generation_id):
    """Get feedback summary for a specific generation, including reclassification suggestions."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT vote, feedback_reasons, suggested_model FROM votes
            WHERE generation_id = ?
        """, (generation_id,)).fetchall()

    positive = {}
    negative = {}
    reclassify = {'music': 0, 'audio': 0}

    for row in rows:
        # Count feedback reasons
        if row['feedback_reasons'] and row['feedback_reasons'] != 'null':
            try:
                reasons = json.loads(row['feedback_reasons'])
                target = positive if row['vote'] == 1 else negative
                for reason in reasons:
                    target[reason] = target.get(reason, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass

        # Count reclassification suggestions
        if row['suggested_model'] in ('music', 'audio'):
            reclassify[row['suggested_model']] += 1

    return {'positive': positive, 'negative': negative, 'reclassify': reclassify}


# =============================================================================
# Favorites
# =============================================================================

def add_favorite(user_id, generation_id):
    """Add a generation to user's favorites."""
    with get_db() as conn:
        try:
            conn.execute("""
                INSERT INTO favorites (user_id, generation_id)
                VALUES (?, ?)
            """, (user_id, generation_id))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Already favorited
            return False


def remove_favorite(user_id, generation_id):
    """Remove a generation from user's favorites."""
    with get_db() as conn:
        cursor = conn.execute("""
            DELETE FROM favorites
            WHERE user_id = ? AND generation_id = ?
        """, (user_id, generation_id))
        conn.commit()
        return cursor.rowcount > 0


def is_favorite(user_id, generation_id):
    """Check if a generation is in user's favorites."""
    with get_db() as conn:
        row = conn.execute("""
            SELECT 1 FROM favorites
            WHERE user_id = ? AND generation_id = ?
        """, (user_id, generation_id)).fetchone()
        return row is not None


def get_user_favorites(user_id, generation_ids):
    """Get which generations are favorited by user (for batch checking)."""
    if not generation_ids:
        return set()

    placeholders = ','.join('?' * len(generation_ids))
    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT generation_id FROM favorites
            WHERE user_id = ? AND generation_id IN ({placeholders})
        """, [user_id] + list(generation_ids)).fetchall()

    return {row['generation_id'] for row in rows}


def get_library_counts():
    """Get counts for each content type."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
        music = conn.execute("SELECT COUNT(*) FROM generations WHERE model = 'music'").fetchone()[0]
        audio = conn.execute("SELECT COUNT(*) FROM generations WHERE model = 'audio'").fetchone()[0]
        voice = conn.execute("SELECT COUNT(*) FROM generations WHERE model = 'voice'").fetchone()[0]

    return {
        'total': total,
        'music': music,
        'audio': audio,
        'voice': voice
    }


# =============================================================================
# Category System
# =============================================================================

def categorize_prompt(prompt: str, model: str) -> list:
    """
    Analyze prompt text and return matching categories (max 5).
    Uses smart matching with word boundaries and partial matches.

    Args:
        prompt: The generation prompt text
        model: 'music' or 'audio' to determine which category set to use

    Returns:
        List of category strings, sorted by match score
    """
    import re
    prompt_lower = prompt.lower()
    # Tokenize: split on non-alphanumeric, keep hyphens for things like "lo-fi"
    words = set(re.findall(r'[\w-]+', prompt_lower))

    if model == 'music':
        categories = MUSIC_CATEGORIES
    elif model == 'voice':
        categories = SPEECH_CATEGORIES
    else:
        categories = SFX_CATEGORIES

    matches = []
    for category, keywords in categories.items():
        score = 0
        for kw in keywords:
            # Exact word match (highest priority)
            if kw in words:
                score += 3
            # Hyphenated word match (e.g., "lo-fi" in "lofi")
            elif kw.replace('-', '') in words or kw.replace('-', ' ') in prompt_lower:
                score += 3
            # Partial word match (e.g., "synth" matches "synthesizer")
            elif len(kw) >= 4 and any(kw in word for word in words):
                score += 2
            # Substring match (lowest priority, for multi-word phrases)
            elif len(kw) >= 5 and kw in prompt_lower:
                score += 1

        if score > 0:
            matches.append((category, score))

    # Sort by score descending, return top 5
    matches.sort(key=lambda x: x[1], reverse=True)
    result = [m[0] for m in matches[:5]]

    # Fallback: assign a generic category if nothing matched
    if not result:
        if model == 'music':
            # Check for common patterns
            if 'loop' in words or 'background' in words:
                result = ['ambient']
            elif 'jingle' in words or 'commercial' in words:
                result = ['advertising']
            else:
                result = ['acoustic']  # Generic fallback
        elif model == 'voice':
            # Check for common voice patterns
            if any(q in prompt_lower for q in ['?', 'what', 'where', 'when', 'how', 'why']):
                result = ['question']
            elif any(g in prompt_lower for g in ['hello', 'hi ', 'welcome', 'good morning', 'good afternoon']):
                result = ['greeting']
            else:
                result = ['natural']  # Generic fallback
        else:
            if 'game' in words:
                result = ['button']
            elif 'effect' in words:
                result = ['whoosh']
            else:
                result = ['notification']  # Generic fallback

    return result


def migrate_categories(force=False):
    """
    Categorize all existing generations based on prompt analysis.
    Call this on startup to ensure all items have categories.

    Args:
        force: If True, re-categorize ALL items (reset existing categories)

    Returns:
        Number of items categorized
    """
    with get_db() as conn:
        if force:
            # Re-categorize everything
            rows = conn.execute(
                "SELECT id, prompt, model FROM generations"
            ).fetchall()
        else:
            # Only uncategorized items
            rows = conn.execute(
                "SELECT id, prompt, model FROM generations WHERE category IS NULL OR category = ''"
            ).fetchall()

        categorized = 0
        for row in rows:
            categories = categorize_prompt(row['prompt'], row['model'])
            if categories:
                conn.execute(
                    "UPDATE generations SET category = ? WHERE id = ?",
                    (json.dumps(categories), row['id'])
                )
                categorized += 1

        conn.commit()

    if categorized > 0:
        print(f"[DB] Categorized {categorized} generations" + (" (force refresh)" if force else ""))
    return categorized


def get_category_counts(model=None):
    """
    Get counts for each category/genre.

    Args:
        model: Optional filter by 'music' or 'audio'

    Returns:
        Dict mapping category names to counts
    """
    # Build set of valid categories for the requested model(s)
    valid_categories = set()
    if not model or model == 'music':
        valid_categories.update(MUSIC_CATEGORIES.keys())
    if not model or model == 'audio':
        valid_categories.update(SFX_CATEGORIES.keys())
    if not model or model == 'voice':
        valid_categories.update(SPEECH_CATEGORIES.keys())

    counts = {cat: 0 for cat in valid_categories}

    with get_db() as conn:
        # Single query instead of N separate queries
        if model:
            rows = conn.execute(
                "SELECT category FROM generations WHERE model = ?",
                (model,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT category FROM generations"
            ).fetchall()

        # Count in Python - O(M) instead of O(N*M)
        for (category_json,) in rows:
            if not category_json:
                continue
            try:
                categories = json.loads(category_json)
                if isinstance(categories, list):
                    for cat in categories:
                        if cat in counts:
                            counts[cat] += 1
            except (json.JSONDecodeError, TypeError):
                continue

    return counts


def get_favorites(user_id, page=1, per_page=20, model=None):
    """Get paginated list of user's favorite generations."""
    per_page = min(per_page, 100)
    offset = (page - 1) * per_page

    conditions = ["f.user_id = ?"]
    params = [user_id]

    if model:
        conditions.append("g.model = ?")
        params.append(model)

    where_clause = " AND ".join(conditions)

    with get_db() as conn:
        # Get total count
        count_sql = f"""
            SELECT COUNT(*) FROM favorites f
            JOIN generations g ON f.generation_id = g.id
            WHERE {where_clause}
        """
        total = conn.execute(count_sql, params).fetchone()[0]

        # Get items
        items_sql = f"""
            SELECT g.*, f.created_at as favorited_at
            FROM favorites f
            JOIN generations g ON f.generation_id = g.id
            WHERE {where_clause}
            ORDER BY f.created_at DESC
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(items_sql, params + [per_page, offset]).fetchall()

    items = [dict(row) for row in rows]
    pages = (total + per_page - 1) // per_page

    return {
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': pages
    }


def get_random_favorites(user_id, count=10, model=None):
    """Get random tracks from user's favorites for radio."""
    conditions = ["f.user_id = ?"]
    params = [user_id]

    if model:
        conditions.append("g.model = ?")
        params.append(model)

    where_clause = " AND ".join(conditions)

    with get_db() as conn:
        sql = f"""
            SELECT g.* FROM favorites f
            JOIN generations g ON f.generation_id = g.id
            WHERE {where_clause}
            ORDER BY RANDOM()
            LIMIT ?
        """
        rows = conn.execute(sql, params + [count]).fetchall()

    return [dict(row) for row in rows]


def get_top_rated_tracks(model=None, count=10, min_duration=60):
    """Get top rated tracks sorted by (upvotes - downvotes)."""
    conditions = []
    params = []

    if min_duration:
        conditions.append("duration >= ?")
        params.append(min_duration)

    if model:
        conditions.append("model = ?")
        params.append(model)

    # Only include tracks with at least some votes
    conditions.append("(upvotes + downvotes) > 0")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    with get_db() as conn:
        sql = f"""
            SELECT * FROM generations
            WHERE {where_clause}
            ORDER BY (upvotes - downvotes) DESC, upvotes DESC
            LIMIT ?
        """
        rows = conn.execute(sql, params + [count]).fetchall()

    return [dict(row) for row in rows]


def get_recent_tracks(model=None, count=10, min_duration=60, hours=168):
    """Get recently created tracks (default: last 7 days = 168 hours)."""
    conditions = []
    params = []

    if min_duration:
        conditions.append("duration >= ?")
        params.append(min_duration)

    if model:
        conditions.append("model = ?")
        params.append(model)

    # Filter by time
    conditions.append("created_at >= datetime('now', ?)")
    params.append(f'-{hours} hours')

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    with get_db() as conn:
        sql = f"""
            SELECT * FROM generations
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
        """
        rows = conn.execute(sql, params + [count]).fetchall()

    return [dict(row) for row in rows]


# =============================================================================
# Play & Download Tracking
# =============================================================================

def record_play(generation_id, user_id=None, session_id=None, play_duration=None, source='radio'):
    """
    Record a play event for a track.

    Args:
        generation_id: The generation ID
        user_id: Optional user ID (from widget or anonymous)
        session_id: Browser session ID for unique counting
        play_duration: How long they listened (seconds)
        source: Where it was played from ('radio', 'library', 'embed', etc.)

    Returns:
        dict with updated play counts
    """
    with get_db() as conn:
        # SECURITY: Check for existing play BEFORE inserting to prevent race condition
        # where two concurrent plays both see count=1 and both increment unique_plays
        identifier = user_id or session_id
        is_first_play = False
        if identifier:
            existing_before = conn.execute("""
                SELECT COUNT(*) FROM play_events
                WHERE generation_id = ? AND (user_id = ? OR session_id = ?)
            """, (generation_id, identifier, identifier)).fetchone()[0]
            is_first_play = (existing_before == 0)

        # Record the play event
        conn.execute("""
            INSERT INTO play_events (generation_id, user_id, session_id, play_duration, source)
            VALUES (?, ?, ?, ?, ?)
        """, (generation_id, user_id, session_id, play_duration, source))

        # Update total play count, and unique_plays if this is their first play
        if is_first_play:
            conn.execute("""
                UPDATE generations SET play_count = play_count + 1, unique_plays = unique_plays + 1 WHERE id = ?
            """, (generation_id,))
        else:
            conn.execute("""
                UPDATE generations SET play_count = play_count + 1 WHERE id = ?
            """, (generation_id,))

        conn.commit()

        # Get updated counts
        row = conn.execute("""
            SELECT play_count, unique_plays FROM generations WHERE id = ?
        """, (generation_id,)).fetchone()

        return {
            'play_count': row['play_count'] if row else 0,
            'unique_plays': row['unique_plays'] if row else 0
        }


def record_download(generation_id, user_id=None, format='wav'):
    """
    Record a download event for a track.

    Args:
        generation_id: The generation ID
        user_id: Optional user ID
        format: Download format (wav, mp3, etc.)

    Returns:
        dict with updated download count
    """
    with get_db() as conn:
        # Record the download event
        conn.execute("""
            INSERT INTO download_events (generation_id, user_id, format)
            VALUES (?, ?, ?)
        """, (generation_id, user_id, format))

        # Update download count
        conn.execute("""
            UPDATE generations SET download_count = download_count + 1 WHERE id = ?
        """, (generation_id,))

        conn.commit()

        # Get updated count
        row = conn.execute("""
            SELECT download_count FROM generations WHERE id = ?
        """, (generation_id,)).fetchone()

        return {
            'download_count': row['download_count'] if row else 0
        }


def get_user_play_history(user_id, limit=50, offset=0):
    """
    Get play history for a user.

    Args:
        user_id: The user ID
        limit: Maximum number of results (default 50)
        offset: Pagination offset (default 0)

    Returns:
        List of play history entries with track metadata
    """
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                pe.id,
                pe.generation_id,
                pe.played_at,
                pe.source,
                g.prompt,
                g.category,
                g.model,
                g.duration,
                g.upvotes,
                g.downvotes
            FROM play_events pe
            JOIN generations g ON pe.generation_id = g.id
            WHERE pe.user_id = ?
            ORDER BY pe.played_at DESC
            LIMIT ? OFFSET ?
        """, (user_id, limit, offset)).fetchall()

        return [dict(row) for row in rows]


def get_user_vote_history(user_id, limit=50, offset=0):
    """
    Get vote history for a user.

    Args:
        user_id: The user ID
        limit: Maximum number of results (default 50)
        offset: Pagination offset (default 0)

    Returns:
        List of vote history entries with track metadata
    """
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                v.id,
                v.generation_id,
                v.vote,
                v.feedback_reasons,
                v.created_at,
                g.prompt,
                g.category,
                g.model,
                g.duration,
                g.upvotes,
                g.downvotes
            FROM votes v
            JOIN generations g ON v.generation_id = g.id
            WHERE v.user_id = ?
            ORDER BY v.created_at DESC
            LIMIT ? OFFSET ?
        """, (user_id, limit, offset)).fetchall()

        return [dict(row) for row in rows]


def get_play_stats(generation_id):
    """Get detailed play statistics for a track."""
    with get_db() as conn:
        # Get basic counts
        row = conn.execute("""
            SELECT play_count, unique_plays, download_count FROM generations WHERE id = ?
        """, (generation_id,)).fetchone()

        if not row:
            return None

        # Get plays by source
        sources = conn.execute("""
            SELECT source, COUNT(*) as count FROM play_events
            WHERE generation_id = ?
            GROUP BY source
        """, (generation_id,)).fetchall()

        # Get plays over time (last 7 days)
        daily = conn.execute("""
            SELECT date(played_at) as day, COUNT(*) as count FROM play_events
            WHERE generation_id = ? AND played_at >= datetime('now', '-7 days')
            GROUP BY day
            ORDER BY day
        """, (generation_id,)).fetchall()

        return {
            'play_count': row['play_count'],
            'unique_plays': row['unique_plays'],
            'download_count': row['download_count'],
            'by_source': {r['source']: r['count'] for r in sources},
            'daily': [{r['day']: r['count']} for r in daily]
        }


def get_trending_tracks(hours=24, limit=20, model=None):
    """
    Get trending tracks based on recent play activity.

    Args:
        hours: Time window for trending calculation
        limit: Number of tracks to return
        model: Optional filter by 'music' or 'audio'

    Returns:
        List of tracks with play counts
    """
    conditions = ["pe.played_at >= datetime('now', ?)"]
    params = [f'-{hours} hours']

    if model:
        conditions.append("g.model = ?")
        params.append(model)

    where_clause = " AND ".join(conditions)

    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT g.*, COUNT(pe.id) as recent_plays
            FROM generations g
            JOIN play_events pe ON g.id = pe.generation_id
            WHERE {where_clause}
            GROUP BY g.id
            ORDER BY recent_plays DESC
            LIMIT ?
        """, params + [limit]).fetchall()

    return [dict(row) for row in rows]


def get_most_played(limit=50, model=None, days=None):
    """
    Get most played tracks of all time or within a time period.

    Args:
        limit: Number of tracks to return
        model: Optional filter by 'music' or 'audio'
        days: Optional time window in days

    Returns:
        List of tracks sorted by play count
    """
    conditions = []
    params = []

    if model:
        conditions.append("model = ?")
        params.append(model)

    if days:
        conditions.append("created_at >= datetime('now', ?)")
        params.append(f'-{days} days')

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT * FROM generations
            WHERE {where_clause} AND play_count > 0
            ORDER BY play_count DESC
            LIMIT ?
        """, params + [limit]).fetchall()

    return [dict(row) for row in rows]


# =============================================================================
# Cleanup / Maintenance
# =============================================================================

def get_stats():
    """Get database statistics."""
    with get_db() as conn:
        gen_count = conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
        vote_count = conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
        music_count = conn.execute("SELECT COUNT(*) FROM generations WHERE model = 'music'").fetchone()[0]
        audio_count = conn.execute("SELECT COUNT(*) FROM generations WHERE model = 'audio'").fetchone()[0]
        feedback_count = conn.execute(
            "SELECT COUNT(*) FROM votes WHERE feedback_reasons IS NOT NULL"
        ).fetchone()[0]

    return {
        'generations': gen_count,
        'music': music_count,
        'audio': audio_count,
        'votes': vote_count,
        'feedback': feedback_count
    }


def get_user_stats(user_id):
    """
    Get generation and usage statistics for a specific user.

    Args:
        user_id: The user ID to get stats for

    Returns:
        dict with user's generation counts, plays, downloads, etc.
    """
    with get_db() as conn:
        # Generation counts by model
        gen_stats = conn.execute("""
            SELECT
                model,
                COUNT(*) as count,
                SUM(duration) as total_duration
            FROM generations
            WHERE user_id = ?
            GROUP BY model
        """, (user_id,)).fetchall()

        gen_by_model = {row['model']: {'count': row['count'], 'duration': row['total_duration'] or 0}
                        for row in gen_stats}
        total_generations = sum(m['count'] for m in gen_by_model.values())

        # Play events (how many times user's content was played by others)
        content_plays = conn.execute("""
            SELECT COUNT(*) as plays, COUNT(DISTINCT pe.user_id) as unique_listeners
            FROM play_events pe
            JOIN generations g ON pe.generation_id = g.id
            WHERE g.user_id = ? AND pe.user_id != ?
        """, (user_id, user_id)).fetchone()

        # User's own listening activity
        listening = conn.execute("""
            SELECT COUNT(*) as plays, COUNT(DISTINCT generation_id) as unique_tracks
            FROM play_events
            WHERE user_id = ?
        """, (user_id,)).fetchone()

        # Downloads of user's content
        downloads = conn.execute("""
            SELECT COUNT(*) as count
            FROM download_events de
            JOIN generations g ON de.generation_id = g.id
            WHERE g.user_id = ?
        """, (user_id,)).fetchone()

        # Votes received
        votes = conn.execute("""
            SELECT
                SUM(CASE WHEN v.vote = 1 THEN 1 ELSE 0 END) as upvotes,
                SUM(CASE WHEN v.vote = -1 THEN 1 ELSE 0 END) as downvotes
            FROM votes v
            JOIN generations g ON v.generation_id = g.id
            WHERE g.user_id = ?
        """, (user_id,)).fetchone()

        # Favorites received
        favorites = conn.execute("""
            SELECT COUNT(*) as count
            FROM favorites f
            JOIN generations g ON f.generation_id = g.id
            WHERE g.user_id = ?
        """, (user_id,)).fetchone()

        # Recent activity (last 24h, 7d, 30d)
        recent = conn.execute("""
            SELECT
                SUM(CASE WHEN created_at > datetime('now', '-1 day') THEN 1 ELSE 0 END) as last_24h,
                SUM(CASE WHEN created_at > datetime('now', '-7 days') THEN 1 ELSE 0 END) as last_7d,
                SUM(CASE WHEN created_at > datetime('now', '-30 days') THEN 1 ELSE 0 END) as last_30d
            FROM generations
            WHERE user_id = ?
        """, (user_id,)).fetchone()

    return {
        'user_id': user_id,
        'generations': {
            'total': total_generations,
            'by_model': gen_by_model,
            'recent': {
                'last_24h': recent['last_24h'] or 0,
                'last_7d': recent['last_7d'] or 0,
                'last_30d': recent['last_30d'] or 0
            }
        },
        'content_stats': {
            'plays_received': content_plays['plays'] or 0,
            'unique_listeners': content_plays['unique_listeners'] or 0,
            'downloads': downloads['count'] or 0,
            'upvotes': votes['upvotes'] or 0,
            'downvotes': votes['downvotes'] or 0,
            'favorites': favorites['count'] or 0
        },
        'listening': {
            'total_plays': listening['plays'] or 0,
            'unique_tracks': listening['unique_tracks'] or 0
        }
    }


def get_system_stats():
    """
    Get overall system statistics for admin dashboard.

    Returns:
        dict with system-wide stats including user counts, generation rates, etc.
    """
    with get_db() as conn:
        # Total counts
        totals = conn.execute("""
            SELECT
                COUNT(*) as total_generations,
                COUNT(DISTINCT user_id) as unique_users,
                SUM(duration) as total_duration,
                SUM(play_count) as total_plays,
                SUM(download_count) as total_downloads
            FROM generations
        """).fetchone()

        # By model
        by_model = conn.execute("""
            SELECT model, COUNT(*) as count, SUM(duration) as duration
            FROM generations
            GROUP BY model
        """).fetchall()

        # Generation rate (last 24h, 7d)
        rate = conn.execute("""
            SELECT
                SUM(CASE WHEN created_at > datetime('now', '-1 day') THEN 1 ELSE 0 END) as last_24h,
                SUM(CASE WHEN created_at > datetime('now', '-7 days') THEN 1 ELSE 0 END) as last_7d
            FROM generations
        """).fetchone()

        # Top users by generation count
        top_users = conn.execute("""
            SELECT user_id, COUNT(*) as count
            FROM generations
            WHERE user_id IS NOT NULL
            GROUP BY user_id
            ORDER BY count DESC
            LIMIT 10
        """).fetchall()

    return {
        'totals': {
            'generations': totals['total_generations'] or 0,
            'unique_users': totals['unique_users'] or 0,
            'total_duration_seconds': totals['total_duration'] or 0,
            'total_plays': totals['total_plays'] or 0,
            'total_downloads': totals['total_downloads'] or 0
        },
        'by_model': {row['model']: {'count': row['count'], 'duration': row['duration'] or 0}
                     for row in by_model},
        'generation_rate': {
            'last_24h': rate['last_24h'] or 0,
            'last_7d': rate['last_7d'] or 0
        },
        'top_users': [{'user_id': row['user_id'], 'count': row['count']} for row in top_users]
    }


# =============================================================================
# Tag Suggestions - Crowdsourced Categorization
# =============================================================================

# Minimum number of users who must agree before a category change is applied
TAG_CONSENSUS_THRESHOLD = 3


def submit_tag_suggestion(generation_id, user_id, suggested_category, action='add'):
    """
    Submit a tag/category suggestion for a generation.

    Args:
        generation_id: The ID of the generation
        user_id: The ID of the user suggesting
        suggested_category: The category they think fits better
        action: 'add' to suggest adding a tag, 'remove' to suggest removing a tag

    Returns:
        dict with 'success' boolean and 'message' or 'consensus_reached' if applied
    """
    # Validate action
    if action not in ('add', 'remove'):
        return {'success': False, 'message': f'Invalid action: {action}. Must be "add" or "remove"'}

    # Validate the category exists (music, audio, OR voice categories are all valid)
    all_categories = list(MUSIC_CATEGORIES.keys()) + list(SFX_CATEGORIES.keys()) + list(SPEECH_CATEGORIES.keys())
    if suggested_category not in all_categories:
        return {'success': False, 'message': f'Invalid category: {suggested_category}'}

    with get_db() as conn:
        # Check if the generation exists
        gen = conn.execute(
            "SELECT id, category FROM generations WHERE id = ?",
            (generation_id,)
        ).fetchone()

        if not gen:
            return {'success': False, 'message': 'Generation not found'}

        # Get current categories (handle corrupted JSON gracefully)
        try:
            current_categories = json.loads(gen['category'] or '[]')
        except (json.JSONDecodeError, TypeError):
            current_categories = []

        # Validate action makes sense
        if action == 'add':
            if suggested_category in current_categories:
                return {'success': False, 'message': 'This category is already applied'}
        elif action == 'remove':
            if suggested_category not in current_categories:
                return {'success': False, 'message': 'This category is not currently applied'}

        try:
            # Insert the suggestion (will fail if duplicate)
            conn.execute(
                """INSERT INTO tag_suggestions (generation_id, user_id, suggested_category, action)
                   VALUES (?, ?, ?, ?)""",
                (generation_id, user_id, suggested_category, action)
            )
            # Note: Don't commit here - wait until all operations complete for atomicity
        except sqlite3.IntegrityError:
            action_verb = 'adding' if action == 'add' else 'removing'
            return {'success': False, 'message': f'You already suggested {action_verb} this category'}

        # Count how many users suggested this category with the same action
        count = conn.execute(
            """SELECT COUNT(DISTINCT user_id) FROM tag_suggestions
               WHERE generation_id = ? AND suggested_category = ? AND action = ?""",
            (generation_id, suggested_category, action)
        ).fetchone()[0]

        # Check if consensus threshold reached
        if count >= TAG_CONSENSUS_THRESHOLD:
            if action == 'add':
                # Add the category
                new_categories = current_categories + [suggested_category]
                message = f'Consensus reached! Category "{suggested_category}" has been added.'
            else:
                # Remove the category
                new_categories = [c for c in current_categories if c != suggested_category]
                message = f'Consensus reached! Category "{suggested_category}" has been removed.'

            conn.execute(
                "UPDATE generations SET category = ? WHERE id = ?",
                (json.dumps(new_categories), generation_id)
            )

            # Record the consensus
            try:
                conn.execute(
                    """INSERT INTO tag_consensus (generation_id, category, action, suggestion_count, applied, applied_at)
                       VALUES (?, ?, ?, ?, TRUE, CURRENT_TIMESTAMP)""",
                    (generation_id, suggested_category, action, count)
                )
            except sqlite3.IntegrityError:
                # Already recorded
                pass

            conn.commit()
            return {
                'success': True,
                'consensus_reached': True,
                'message': message,
                'new_categories': new_categories,
                'action': action
            }

        # Commit the suggestion (no consensus reached yet)
        conn.commit()

        action_verb = 'add' if action == 'add' else 'remove'
        return {
            'success': True,
            'consensus_reached': False,
            'message': f'Suggestion recorded. {count}/{TAG_CONSENSUS_THRESHOLD} users have suggested to {action_verb} this category.',
            'current_votes': count,
            'threshold': TAG_CONSENSUS_THRESHOLD,
            'action': action
        }


def get_tag_suggestions(generation_id):
    """
    Get all tag suggestions for a generation with vote counts, grouped by action.

    Returns:
        dict with 'add' and 'remove' keys, each mapping category names to suggestion counts
    """
    with get_db() as conn:
        rows = conn.execute(
            """SELECT suggested_category, action, COUNT(DISTINCT user_id) as count
               FROM tag_suggestions
               WHERE generation_id = ?
               GROUP BY suggested_category, action
               ORDER BY count DESC""",
            (generation_id,)
        ).fetchall()

    result = {'add': {}, 'remove': {}}
    for row in rows:
        action = row['action'] if 'action' in row.keys() else 'add'
        result[action][row['suggested_category']] = row['count']

    return result


def get_user_suggestions(generation_id, user_id):
    """
    Get the categories a specific user has suggested for a generation.

    Returns:
        dict with 'add' and 'remove' lists of category names
    """
    with get_db() as conn:
        rows = conn.execute(
            """SELECT suggested_category, action FROM tag_suggestions
               WHERE generation_id = ? AND user_id = ?""",
            (generation_id, user_id)
        ).fetchall()

    result = {'add': [], 'remove': []}
    for row in rows:
        action = row['action'] if 'action' in row.keys() else 'add'
        result[action].append(row['suggested_category'])

    return result


def cancel_tag_suggestion(generation_id, user_id, suggested_category, action='add'):
    """
    Cancel a user's own tag suggestion.

    Args:
        generation_id: The ID of the generation
        user_id: The ID of the user canceling their suggestion
        suggested_category: The category to cancel
        action: 'add' or 'remove' - which type of suggestion to cancel

    Returns:
        dict with 'success' boolean and 'message'
    """
    with get_db() as conn:
        # Check if the suggestion exists
        existing = conn.execute(
            """SELECT id FROM tag_suggestions
               WHERE generation_id = ? AND user_id = ? AND suggested_category = ? AND action = ?""",
            (generation_id, user_id, suggested_category, action)
        ).fetchone()

        if not existing:
            return {'success': False, 'message': 'Suggestion not found'}

        # Delete the suggestion
        conn.execute(
            """DELETE FROM tag_suggestions
               WHERE generation_id = ? AND user_id = ? AND suggested_category = ? AND action = ?""",
            (generation_id, user_id, suggested_category, action)
        )
        conn.commit()

        return {'success': True, 'message': 'Suggestion canceled'}


def get_pending_consensus():
    """
    Get generations that are close to reaching consensus.

    Returns:
        list of dicts with generation info and suggestion counts
    """
    min_suggestions = TAG_CONSENSUS_THRESHOLD - 1  # One away from consensus

    with get_db() as conn:
        rows = conn.execute(
            """SELECT ts.generation_id, ts.suggested_category,
                      COUNT(DISTINCT ts.user_id) as count,
                      g.prompt, g.model
               FROM tag_suggestions ts
               JOIN generations g ON ts.generation_id = g.id
               LEFT JOIN tag_consensus tc ON ts.generation_id = tc.generation_id
                    AND ts.suggested_category = tc.new_category
               WHERE tc.id IS NULL
               GROUP BY ts.generation_id, ts.suggested_category
               HAVING count >= ?
               ORDER BY count DESC""",
            (min_suggestions,)
        ).fetchall()

    return [dict(row) for row in rows]


def get_available_categories(model):
    """
    Get all available categories for a given model type.

    Args:
        model: 'music', 'audio', or 'voice'

    Returns:
        dict of category name -> display name
    """
    if model == 'music':
        categories = MUSIC_CATEGORIES
    elif model == 'voice':
        categories = SPEECH_CATEGORIES
    else:
        categories = SFX_CATEGORIES

    # Convert to display names (replace underscores with spaces, title case)
    return {
        cat: cat.replace('_', ' ').title()
        for cat in categories.keys()
    }


# =============================================================================
# Project Source Functions
# =============================================================================

def get_project_sources():
    """
    Get all available project sources.

    Returns:
        dict of source_id -> source info
    """
    return PROJECT_SOURCES


def get_project_source_counts():
    """
    Get counts of assets per project source, broken down by model type.

    Returns:
        dict of source_id -> {music: count, audio: count, voice: count, total: count}
    """
    counts = {}

    with get_db() as conn:
        # Get counts grouped by source and model
        rows = conn.execute("""
            SELECT source, model, COUNT(*) as count
            FROM generations
            WHERE source IS NOT NULL AND is_public = TRUE
            GROUP BY source, model
        """).fetchall()

        for row in rows:
            source = row['source']
            model = row['model']
            count = row['count']

            if source not in counts:
                counts[source] = {'music': 0, 'audio': 0, 'voice': 0, 'total': 0}

            counts[source][model] = count
            counts[source]['total'] += count

    return counts


def set_generation_source(generation_id, source):
    """
    Set or update the source for a generation.

    Args:
        generation_id: The generation ID
        source: Source ID (e.g., 'byk3s') or None to clear

    Returns:
        True on success, False on error
    """
    # Validate source if provided
    if source and source not in PROJECT_SOURCES:
        return False

    with get_db() as conn:
        try:
            conn.execute("""
                UPDATE generations SET source = ? WHERE id = ?
            """, (source, generation_id))
            conn.commit()
            return True
        except sqlite3.Error:
            return False


def bulk_set_source(generation_ids, source):
    """
    Set source for multiple generations at once.

    Args:
        generation_ids: List of generation IDs
        source: Source ID or None to clear

    Returns:
        Number of rows updated
    """
    if source and source not in PROJECT_SOURCES:
        return 0

    if not generation_ids:
        return 0

    placeholders = ','.join('?' * len(generation_ids))

    with get_db() as conn:
        try:
            cursor = conn.execute(f"""
                UPDATE generations SET source = ?
                WHERE id IN ({placeholders})
            """, [source] + list(generation_ids))
            conn.commit()
            return cursor.rowcount
        except sqlite3.Error:
            return 0


# =============================================================================
# Playlists - Requires authenticated user_id
# =============================================================================

def create_playlist(playlist_id, user_id, name, description=None):
    """
    Create a new playlist.

    Args:
        playlist_id: Unique playlist ID (e.g., 'pl_abc123')
        user_id: Authenticated user ID
        name: Playlist name
        description: Optional description

    Returns:
        dict with playlist info or None on error
    """
    if not user_id:
        return None  # Require authenticated user

    with get_db() as conn:
        try:
            conn.execute("""
                INSERT INTO playlists (id, user_id, name, description)
                VALUES (?, ?, ?, ?)
            """, (playlist_id, user_id, name, description))
            conn.commit()

            return {
                'id': playlist_id,
                'user_id': user_id,
                'name': name,
                'description': description,
                'track_count': 0
            }
        except sqlite3.IntegrityError:
            return None


def get_playlist(playlist_id):
    """Get a single playlist by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM playlists WHERE id = ?", (playlist_id,)
        ).fetchone()

        if not row:
            return None

        playlist = dict(row)

        # Get track count
        count = conn.execute(
            "SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id = ?",
            (playlist_id,)
        ).fetchone()[0]
        playlist['track_count'] = count

        return playlist


def get_user_playlists(user_id, page=1, per_page=50):
    """
    Get all playlists for a user.

    Args:
        user_id: Authenticated user ID
        page: Page number
        per_page: Items per page

    Returns:
        dict with playlists list and pagination info
    """
    if not user_id:
        return {'playlists': [], 'total': 0, 'page': 1, 'pages': 0}

    per_page = min(per_page, 100)
    offset = (page - 1) * per_page

    with get_db() as conn:
        # Get total count
        total = conn.execute(
            "SELECT COUNT(*) FROM playlists WHERE user_id = ?",
            (user_id,)
        ).fetchone()[0]

        # Get playlists with track counts
        rows = conn.execute("""
            SELECT p.*,
                   (SELECT COUNT(*) FROM playlist_tracks pt WHERE pt.playlist_id = p.id) as track_count
            FROM playlists p
            WHERE p.user_id = ?
            ORDER BY p.updated_at DESC
            LIMIT ? OFFSET ?
        """, (user_id, per_page, offset)).fetchall()

    playlists = [dict(row) for row in rows]
    pages = (total + per_page - 1) // per_page if total > 0 else 0

    return {
        'playlists': playlists,
        'total': total,
        'page': page,
        'pages': pages
    }


def update_playlist(playlist_id, user_id, name=None, description=None):
    """
    Update playlist metadata.

    Args:
        playlist_id: Playlist ID
        user_id: Must match playlist owner
        name: New name (optional)
        description: New description (optional)

    Returns:
        Updated playlist dict or None if not found/unauthorized
    """
    with get_db() as conn:
        # Verify ownership
        existing = conn.execute(
            "SELECT * FROM playlists WHERE id = ? AND user_id = ?",
            (playlist_id, user_id)
        ).fetchone()

        if not existing:
            return None

        # Build update
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.extend([playlist_id, user_id])

            conn.execute(f"""
                UPDATE playlists SET {', '.join(updates)}
                WHERE id = ? AND user_id = ?
            """, params)
            conn.commit()

        return get_playlist(playlist_id)


def delete_playlist(playlist_id, user_id):
    """
    Delete a playlist (cascades to playlist_tracks).

    Args:
        playlist_id: Playlist ID
        user_id: Must match playlist owner

    Returns:
        True if deleted, False otherwise
    """
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM playlists WHERE id = ? AND user_id = ?",
            (playlist_id, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def add_track_to_playlist(playlist_id, generation_id, user_id, position=None):
    """
    Add a track to a playlist.

    Args:
        playlist_id: Playlist ID
        generation_id: Track ID to add
        user_id: Must match playlist owner
        position: Optional position (appends to end if not specified)

    Returns:
        dict with success status and track info
    """
    with get_db() as conn:
        # Verify ownership
        playlist = conn.execute(
            "SELECT * FROM playlists WHERE id = ? AND user_id = ?",
            (playlist_id, user_id)
        ).fetchone()

        if not playlist:
            return {'success': False, 'error': 'Playlist not found or unauthorized'}

        # Verify track exists
        track = conn.execute(
            "SELECT id FROM generations WHERE id = ?",
            (generation_id,)
        ).fetchone()

        if not track:
            return {'success': False, 'error': 'Track not found'}

        # Get next position if not specified
        if position is None:
            max_pos = conn.execute(
                "SELECT COALESCE(MAX(position), 0) FROM playlist_tracks WHERE playlist_id = ?",
                (playlist_id,)
            ).fetchone()[0]
            position = max_pos + 1

        try:
            conn.execute("""
                INSERT INTO playlist_tracks (playlist_id, generation_id, position)
                VALUES (?, ?, ?)
            """, (playlist_id, generation_id, position))

            # Update playlist's updated_at
            conn.execute(
                "UPDATE playlists SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (playlist_id,)
            )
            conn.commit()

            return {'success': True, 'position': position}
        except sqlite3.IntegrityError:
            return {'success': False, 'error': 'Track already in playlist'}


def remove_track_from_playlist(playlist_id, generation_id, user_id):
    """
    Remove a track from a playlist.

    Args:
        playlist_id: Playlist ID
        generation_id: Track ID to remove
        user_id: Must match playlist owner

    Returns:
        True if removed, False otherwise
    """
    with get_db() as conn:
        # Verify ownership
        playlist = conn.execute(
            "SELECT * FROM playlists WHERE id = ? AND user_id = ?",
            (playlist_id, user_id)
        ).fetchone()

        if not playlist:
            return False

        cursor = conn.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id = ? AND generation_id = ?",
            (playlist_id, generation_id)
        )

        if cursor.rowcount > 0:
            # Update playlist's updated_at
            conn.execute(
                "UPDATE playlists SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (playlist_id,)
            )
            conn.commit()
            return True

        return False


def get_playlist_tracks(playlist_id, include_metadata=True):
    """
    Get all tracks in a playlist, ordered by position.

    Args:
        playlist_id: Playlist ID
        include_metadata: If True, include full track metadata

    Returns:
        List of track dicts
    """
    with get_db() as conn:
        if include_metadata:
            rows = conn.execute("""
                SELECT g.*, pt.position, pt.added_at as added_to_playlist
                FROM playlist_tracks pt
                JOIN generations g ON pt.generation_id = g.id
                WHERE pt.playlist_id = ?
                ORDER BY pt.position ASC
            """, (playlist_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT generation_id, position, added_at
                FROM playlist_tracks
                WHERE playlist_id = ?
                ORDER BY position ASC
            """, (playlist_id,)).fetchall()

    return [dict(row) for row in rows]


def reorder_playlist_tracks(playlist_id, user_id, track_order):
    """
    Reorder tracks in a playlist.

    Args:
        playlist_id: Playlist ID
        user_id: Must match playlist owner
        track_order: List of generation_ids in new order

    Returns:
        True if reordered, False otherwise
    """
    with get_db() as conn:
        # Verify ownership
        playlist = conn.execute(
            "SELECT * FROM playlists WHERE id = ? AND user_id = ?",
            (playlist_id, user_id)
        ).fetchone()

        if not playlist:
            return False

        # Update positions
        for position, generation_id in enumerate(track_order, start=1):
            conn.execute("""
                UPDATE playlist_tracks
                SET position = ?
                WHERE playlist_id = ? AND generation_id = ?
            """, (position, playlist_id, generation_id))

        conn.execute(
            "UPDATE playlists SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (playlist_id,)
        )
        conn.commit()
        return True


def get_playlist_for_radio(playlist_id, shuffle=False):
    """
    Get playlist tracks formatted for radio playback.

    Args:
        playlist_id: Playlist ID
        shuffle: If True, return tracks in random order

    Returns:
        List of track dicts ready for radio queue
    """
    with get_db() as conn:
        order = "RANDOM()" if shuffle else "pt.position ASC"
        rows = conn.execute(f"""
            SELECT g.*
            FROM playlist_tracks pt
            JOIN generations g ON pt.generation_id = g.id
            WHERE pt.playlist_id = ?
            ORDER BY {order}
        """, (playlist_id,)).fetchall()

    return [dict(row) for row in rows]


if __name__ == '__main__':
    # CLI for testing
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == 'init':
            init_db()
            print("Database initialized")

        elif cmd == 'migrate':
            init_db()
            count = migrate_from_json()
            print(f"Migrated {count} generations")

        elif cmd == 'stats':
            init_db()
            stats = get_stats()
            print(f"Generations: {stats['generations']} ({stats['music']} music, {stats['audio']} audio)")
            print(f"Votes: {stats['votes']}")
            print(f"Feedback: {stats['feedback']}")

        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python database.py [init|migrate|stats]")
    else:
        print("Usage: python database.py [init|migrate|stats]")
