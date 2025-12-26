"""
Sound Box Database Layer
SQLite database for generations and votes with private feedback.
No public comments - feedback stored privately with votes.
"""
import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime

DB_PATH = 'soundbox.db'
METADATA_FILE = 'generations.json'

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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE,
    UNIQUE(generation_id, user_id, suggested_category)
);

-- Tag Consensus table to track when categories should be updated
CREATE TABLE IF NOT EXISTS tag_consensus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_id TEXT NOT NULL UNIQUE,
    new_category TEXT NOT NULL,
    suggestion_count INTEGER DEFAULT 1,
    applied BOOLEAN DEFAULT FALSE,
    applied_at TIMESTAMP,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_generations_model ON generations(model);
CREATE INDEX IF NOT EXISTS idx_generations_created ON generations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_votes_generation ON votes(generation_id);
CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_favorites_generation ON favorites(generation_id);
CREATE INDEX IF NOT EXISTS idx_tag_suggestions_generation ON tag_suggestions(generation_id);
CREATE INDEX IF NOT EXISTS idx_tag_suggestions_category ON tag_suggestions(suggested_category);
CREATE INDEX IF NOT EXISTS idx_tag_consensus_generation ON tag_consensus(generation_id);
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
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
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
                      quality_score=None, spectrogram=None, user_id=None):
    """Create a new generation record with auto-categorization."""
    # Auto-categorize based on prompt
    categories = categorize_prompt(prompt, model)
    category_json = json.dumps(categories) if categories else None

    with get_db() as conn:
        conn.execute("""
            INSERT INTO generations
            (id, filename, prompt, model, duration, is_loop, quality_score, spectrogram, user_id, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (gen_id, filename, prompt, model, duration, is_loop, quality_score, spectrogram, user_id, category_json))
        conn.commit()


def get_generation(gen_id):
    """Get a single generation by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM generations WHERE id = ?", (gen_id,)
        ).fetchone()
        return dict(row) if row else None


def get_library(page=1, per_page=20, model=None, search=None, sort='recent', user_id=None, category=None):
    """
    Get paginated library with filters.

    Args:
        page: Page number (1-indexed)
        per_page: Items per page (max 100)
        model: Filter by 'music' or 'audio'
        search: Full-text search query
        sort: 'recent', 'popular', or 'rating'
        user_id: Optional user filter for 'my generations'
        category: Filter by category/genre (e.g., 'ambient', 'nature')

    Returns:
        dict with items, total, page, per_page, pages
    """
    per_page = min(per_page, 100)
    offset = (page - 1) * per_page

    # Build query
    conditions = []
    params = []

    if model:
        conditions.append("g.model = ?")
        params.append(model)

    if user_id:
        conditions.append("g.user_id = ?")
        params.append(user_id)

    # Category filter (stored as JSON array)
    if category:
        conditions.append("g.category LIKE ?")
        params.append(f'%"{category}"%')

    # Full-text search (OR logic for multiple words)
    # Quote each term to handle special chars like hyphens (lo-fi)
    if search:
        words = search.strip().split()
        if words:
            quoted_words = ['"' + w.replace('"', '') + '"' for w in words]
            fts_query = ' OR '.join(quoted_words)
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

    if search:
        # Convert multi-word search to OR query for FTS5 (match any word)
        # Quote each term to handle special chars like hyphens (lo-fi)
        words = search.strip().split()
        if words:
            # Quote each word and join with OR
            quoted_words = ['"' + w.replace('"', '') + '"' for w in words]
            fts_query = ' OR '.join(quoted_words)
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

    if search:
        words = search.strip().split()
        if words:
            quoted_words = ['"' + w.replace('"', '') + '"' for w in words]
            fts_query = ' OR '.join(quoted_words)
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

        # Recalculate denormalized counts
        counts = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN vote = 1 THEN 1 ELSE 0 END), 0) as upvotes,
                COALESCE(SUM(CASE WHEN vote = -1 THEN 1 ELSE 0 END), 0) as downvotes
            FROM votes WHERE generation_id = ?
        """, (generation_id,)).fetchone()

        conn.execute("""
            UPDATE generations SET upvotes = ?, downvotes = ? WHERE id = ?
        """, (counts['upvotes'], counts['downvotes'], generation_id))

        conn.commit()

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

    return {
        'total': total,
        'music': music,
        'audio': audio
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

    categories = MUSIC_CATEGORIES if model == 'music' else SFX_CATEGORIES

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
    all_categories = {
        'music': list(MUSIC_CATEGORIES.keys()),
        'audio': list(SFX_CATEGORIES.keys())
    }

    counts = {}
    with get_db() as conn:
        for cat_type, cats in all_categories.items():
            if model and model != cat_type:
                continue
            for cat in cats:
                # Category is stored as JSON array, use LIKE to match
                count = conn.execute(
                    "SELECT COUNT(*) FROM generations WHERE category LIKE ? AND model = ?",
                    (f'%"{cat}"%', cat_type)
                ).fetchone()[0]
                counts[cat] = count

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


# =============================================================================
# Tag Suggestions - Crowdsourced Categorization
# =============================================================================

# Minimum number of users who must agree before a category change is applied
TAG_CONSENSUS_THRESHOLD = 3


def submit_tag_suggestion(generation_id, user_id, suggested_category):
    """
    Submit a tag/category suggestion for a generation.

    Args:
        generation_id: The ID of the generation
        user_id: The ID of the user suggesting
        suggested_category: The category they think fits better

    Returns:
        dict with 'success' boolean and 'message' or 'consensus_reached' if applied
    """
    # Validate the category exists
    all_categories = list(MUSIC_CATEGORIES.keys()) + list(SFX_CATEGORIES.keys())
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

        # Check if this category is already applied
        current_categories = json.loads(gen['category'] or '[]')
        if suggested_category in current_categories:
            return {'success': False, 'message': 'This category is already applied'}

        try:
            # Insert the suggestion (will fail if duplicate)
            conn.execute(
                """INSERT INTO tag_suggestions (generation_id, user_id, suggested_category)
                   VALUES (?, ?, ?)""",
                (generation_id, user_id, suggested_category)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return {'success': False, 'message': 'You already suggested this category'}

        # Count how many users suggested this category
        count = conn.execute(
            """SELECT COUNT(DISTINCT user_id) FROM tag_suggestions
               WHERE generation_id = ? AND suggested_category = ?""",
            (generation_id, suggested_category)
        ).fetchone()[0]

        # Check if consensus threshold reached
        if count >= TAG_CONSENSUS_THRESHOLD:
            # Apply the category
            new_categories = current_categories + [suggested_category]
            conn.execute(
                "UPDATE generations SET category = ? WHERE id = ?",
                (json.dumps(new_categories), generation_id)
            )

            # Record the consensus
            try:
                conn.execute(
                    """INSERT INTO tag_consensus (generation_id, new_category, suggestion_count, applied, applied_at)
                       VALUES (?, ?, ?, TRUE, CURRENT_TIMESTAMP)""",
                    (generation_id, suggested_category, count)
                )
            except sqlite3.IntegrityError:
                # Already recorded
                pass

            conn.commit()
            return {
                'success': True,
                'consensus_reached': True,
                'message': f'Consensus reached! Category "{suggested_category}" has been added.',
                'new_categories': new_categories
            }

        return {
            'success': True,
            'consensus_reached': False,
            'message': f'Suggestion recorded. {count}/{TAG_CONSENSUS_THRESHOLD} users have suggested this category.',
            'current_votes': count,
            'threshold': TAG_CONSENSUS_THRESHOLD
        }


def get_tag_suggestions(generation_id):
    """
    Get all tag suggestions for a generation with vote counts.

    Returns:
        dict mapping category names to suggestion counts
    """
    with get_db() as conn:
        rows = conn.execute(
            """SELECT suggested_category, COUNT(DISTINCT user_id) as count
               FROM tag_suggestions
               WHERE generation_id = ?
               GROUP BY suggested_category
               ORDER BY count DESC""",
            (generation_id,)
        ).fetchall()

    return {row['suggested_category']: row['count'] for row in rows}


def get_user_suggestions(generation_id, user_id):
    """
    Get the categories a specific user has suggested for a generation.

    Returns:
        list of category names
    """
    with get_db() as conn:
        rows = conn.execute(
            """SELECT suggested_category FROM tag_suggestions
               WHERE generation_id = ? AND user_id = ?""",
            (generation_id, user_id)
        ).fetchall()

    return [row['suggested_category'] for row in rows]


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
        model: 'music' or 'audio'

    Returns:
        dict of category name -> display name
    """
    if model == 'music':
        categories = MUSIC_CATEGORIES
    else:
        categories = SFX_CATEGORIES

    # Convert to display names (replace underscores with spaces, title case)
    return {
        cat: cat.replace('_', ' ').title()
        for cat in categories.keys()
    }


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
