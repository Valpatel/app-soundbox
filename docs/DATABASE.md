# Sound Box Database Schema

## Overview

Sound Box uses SQLite with FTS5 (Full-Text Search) for storing audio generation metadata, user interactions, and crowdsourced categorization.

**Database File:** `soundbox.db`

## Tables

### generations
Primary table storing all generated audio metadata.

```sql
CREATE TABLE generations (
    id TEXT PRIMARY KEY,              -- UUID
    filename TEXT NOT NULL UNIQUE,    -- e.g., "abc123.wav"
    prompt TEXT NOT NULL,             -- User's text prompt
    model TEXT NOT NULL,              -- "music" or "audio"
    duration INTEGER NOT NULL,        -- Length in seconds
    is_loop BOOLEAN DEFAULT FALSE,    -- Seamless loop mode
    quality_score INTEGER,            -- 0-100 quality rating
    spectrogram TEXT,                 -- Spectrogram filename
    user_id TEXT,                     -- Graphlings user ID
    category TEXT,                    -- JSON array of categories (added via migration)
    upvotes INTEGER DEFAULT 0,        -- Denormalized count
    downvotes INTEGER DEFAULT 0,      -- Denormalized count
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### votes
User votes with private feedback.

```sql
CREATE TABLE votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_id TEXT NOT NULL,      -- FK to generations
    user_id TEXT NOT NULL,            -- Voter's user ID
    vote INTEGER NOT NULL,            -- -1, 0, or 1
    feedback_reasons TEXT,            -- JSON array of reason tags
    notes TEXT,                       -- Private notes (not public)
    suggested_model TEXT,             -- Reclassification suggestion
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE,
    UNIQUE(generation_id, user_id)
);
```

**Feedback Reason Tags:**
- Positive: `great_quality`, `creative_prompt`, `useful_sound`, `perfect_loop`
- Negative: `poor_quality`, `wrong_category`, `too_short`, `clipping`, `noise`

### favorites
User favorites for quick access.

```sql
CREATE TABLE favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    generation_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE,
    UNIQUE(user_id, generation_id)
);
```

### tag_suggestions
Crowdsourced category suggestions.

```sql
CREATE TABLE tag_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    suggested_category TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE,
    UNIQUE(generation_id, user_id, suggested_category)
);
```

### tag_consensus
Tracks when category changes should be applied.

```sql
CREATE TABLE tag_consensus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_id TEXT NOT NULL UNIQUE,
    new_category TEXT NOT NULL,
    suggestion_count INTEGER DEFAULT 1,
    applied BOOLEAN DEFAULT FALSE,
    applied_at TIMESTAMP,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE
);
```

**Consensus Threshold:** 3 users must suggest the same category for it to be auto-applied.

### generations_fts
Virtual FTS5 table for full-text search on prompts.

```sql
CREATE VIRTUAL TABLE generations_fts USING fts5(
    prompt,
    content='generations',
    content_rowid='rowid'
);
```

## Indexes

```sql
-- Generations table
CREATE INDEX idx_generations_model ON generations(model);
CREATE INDEX idx_generations_created ON generations(created_at DESC);
CREATE INDEX idx_generations_category ON generations(category);  -- Added via migration

-- Votes table
CREATE INDEX idx_votes_generation ON votes(generation_id);

-- Favorites table
CREATE INDEX idx_favorites_user ON favorites(user_id);
CREATE INDEX idx_favorites_generation ON favorites(generation_id);

-- Tag suggestions table
CREATE INDEX idx_tag_suggestions_generation ON tag_suggestions(generation_id);
CREATE INDEX idx_tag_suggestions_category ON tag_suggestions(suggested_category);

-- Tag consensus table
CREATE INDEX idx_tag_consensus_generation ON tag_consensus(generation_id);
```

**Note:** There are no indexes on `generations(upvotes, downvotes)` or `generations(user_id)`. Queries on these fields may be slower on large datasets.

## Auto-Categorization

When audio is generated, categories are automatically assigned based on prompt keywords.

### Music Categories (77 total)
Organized into groups:
- **Electronic:** ambient, electronic, synthwave, techno, house, trance, dubstep, drum_and_bass
- **Acoustic:** acoustic, piano, guitar, strings, folk, classical, jazz, blues
- **Cinematic:** cinematic, epic, orchestral, trailer, dramatic, heroic
- **Era:** 60s, 70s, 80s, retro, chiptune, arcade
- **World:** african, asian, celtic, latin, middle_eastern
- **Mood:** happy, sad, angry, calm, energetic, dark_ambient
- **Genre:** lofi, hip_hop, rock, metal, punk, grunge, indie, soul

### SFX Categories (50+ total)
- **Nature:** rain, thunder, wind, water, forest, ocean, birds
- **Mechanical:** engine, machine, factory, industrial, metal
- **Human:** footsteps, voice, crowd, breath, laugh
- **Fantasy:** magic, spell, creature, dragon, supernatural
- **UI:** notification, button, click, menu, select, error
- **Impacts:** explosion, hit, punch, crash, slam
- **Movement:** whoosh, swoosh, transition, sweep

### Categorization Logic
```python
def categorize_prompt(prompt: str, model: str) -> list:
    """Match keywords and return top 5 categories max."""
    words = set(re.findall(r'[\w-]+', prompt.lower()))
    categories = MUSIC_CATEGORIES if model == 'music' else SFX_CATEGORIES

    matches = []
    for category, keywords in categories.items():
        score = 0
        for kw in keywords:
            if kw in words:                    # Exact word match
                score += 3
            elif len(kw) >= 4 and any(kw in word for word in words):  # Partial
                score += 2
            elif len(kw) >= 5 and kw in prompt.lower():  # Substring
                score += 1
        if score > 0:
            matches.append((category, score))

    matches.sort(key=lambda x: x[1], reverse=True)
    return [m[0] for m in matches[:5]]  # Max 5 categories
```

**Fallback:** If no categories match, assigns a generic fallback:
- Music: `ambient` (for loop/background), `advertising` (for jingle/commercial), else `acoustic`
- SFX: `button` (for game), `whoosh` (for effect), else `notification`

## Common Queries

### Get library items with pagination
```sql
SELECT g.*,
       (SELECT vote FROM votes WHERE generation_id = g.id AND user_id = ?) as user_vote
FROM generations g
WHERE model = ?
ORDER BY created_at DESC
LIMIT ? OFFSET ?
```

### Full-text search
```sql
SELECT g.* FROM generations g
JOIN generations_fts fts ON g.rowid = fts.rowid
WHERE fts.prompt MATCH ?
ORDER BY rank
```

### Top-rated tracks
```sql
SELECT * FROM generations
WHERE model = 'music'
ORDER BY (upvotes - downvotes) DESC
LIMIT 20
```

### Category counts
```sql
SELECT COUNT(*) FROM generations
WHERE category LIKE '%"ambient"%'
```

### User favorites
```sql
SELECT g.* FROM generations g
JOIN favorites f ON g.id = f.generation_id
WHERE f.user_id = ?
ORDER BY f.created_at DESC
```

## Migration

### From JSON to SQLite
The original system stored metadata in `generations.json`. Migration happens automatically on first run:

```python
def migrate_from_json():
    """Migrate generations.json to SQLite."""
    if not os.path.exists('generations.json'):
        return 0

    with open('generations.json') as f:
        data = json.load(f)

    for gen_id, gen in data.items():
        # Insert into SQLite with auto-categorization
        create_generation(gen_id, gen['filename'], gen['prompt'], ...)

    return len(data)
```

### Adding new columns
Schema changes use `ALTER TABLE` with exception handling:

```python
try:
    conn.execute("ALTER TABLE generations ADD COLUMN category TEXT")
except sqlite3.OperationalError:
    pass  # Column already exists
```

## Backup & Recovery

### Backup
```bash
sqlite3 soundbox.db ".backup backup.db"
```

### Export to JSON
```python
with get_db() as conn:
    rows = conn.execute("SELECT * FROM generations").fetchall()
    data = {row['id']: dict(row) for row in rows}
    json.dump(data, open('backup.json', 'w'))
```

### Vacuum (optimize)
```bash
sqlite3 soundbox.db "VACUUM"
```
