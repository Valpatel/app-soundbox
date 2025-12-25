"""
Sound Box Database Layer
SQLite database for generations, votes, and comments.
"""
import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime

DB_PATH = 'soundbox.db'
METADATA_FILE = 'generations.json'

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

-- Votes table
CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    vote INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE,
    UNIQUE(generation_id, user_id)
);

-- Comments table
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    username TEXT,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_generations_model ON generations(model);
CREATE INDEX IF NOT EXISTS idx_generations_created ON generations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_votes_generation ON votes(generation_id);
CREATE INDEX IF NOT EXISTS idx_comments_generation ON comments(generation_id);
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
        conn.commit()
    print("[DB] Database initialized")


def migrate_from_json():
    """Migrate existing generations.json to SQLite."""
    if not os.path.exists(METADATA_FILE):
        print("[DB] No generations.json to migrate")
        return 0

    with open(METADATA_FILE, 'r') as f:
        metadata = json.load(f)

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
    """Create a new generation record."""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO generations
            (id, filename, prompt, model, duration, is_loop, quality_score, spectrogram, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (gen_id, filename, prompt, model, duration, is_loop, quality_score, spectrogram, user_id))
        conn.commit()


def get_generation(gen_id):
    """Get a single generation by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM generations WHERE id = ?", (gen_id,)
        ).fetchone()
        return dict(row) if row else None


def get_library(page=1, per_page=20, model=None, search=None, sort='recent', user_id=None):
    """
    Get paginated library with filters.

    Args:
        page: Page number (1-indexed)
        per_page: Items per page (max 100)
        model: Filter by 'music' or 'audio'
        search: Full-text search query
        sort: 'recent', 'popular', or 'rating'
        user_id: Optional user filter for 'my generations'

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

    # Full-text search (OR logic for multiple words)
    if search:
        words = search.strip().split()
        if words:
            fts_query = ' OR '.join(words)
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
            SELECT g.*,
                   (SELECT COUNT(*) FROM comments c WHERE c.generation_id = g.id) as comment_count
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


def get_random_tracks(model=None, search=None, count=10):
    """Get random tracks for radio shuffle."""
    conditions = []
    params = []

    if model:
        conditions.append("g.model = ?")
        params.append(model)

    if search:
        # Convert multi-word search to OR query for FTS5 (match any word)
        words = search.strip().split()
        if words:
            fts_query = ' OR '.join(words)
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
    """Delete a generation and its votes/comments (cascades)."""
    with get_db() as conn:
        conn.execute("DELETE FROM generations WHERE id = ?", (gen_id,))
        conn.commit()


# =============================================================================
# Voting
# =============================================================================

def vote(generation_id, user_id, vote_value):
    """
    Cast or update a vote.

    Args:
        generation_id: The generation ID
        user_id: The voter's user ID
        vote_value: 1 (upvote), -1 (downvote), or 0 (remove)

    Returns:
        dict with upvotes, downvotes, user_vote
    """
    with get_db() as conn:
        if vote_value == 0:
            # Remove vote
            conn.execute(
                "DELETE FROM votes WHERE generation_id = ? AND user_id = ?",
                (generation_id, user_id)
            )
        else:
            # Upsert vote
            conn.execute("""
                INSERT INTO votes (generation_id, user_id, vote)
                VALUES (?, ?, ?)
                ON CONFLICT(generation_id, user_id)
                DO UPDATE SET vote = ?, created_at = CURRENT_TIMESTAMP
            """, (generation_id, user_id, vote_value, vote_value))

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


# =============================================================================
# Comments
# =============================================================================

def add_comment(generation_id, user_id, content, username=None):
    """Add a comment to a generation."""
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO comments (generation_id, user_id, username, content)
            VALUES (?, ?, ?, ?)
        """, (generation_id, user_id, username, content))
        conn.commit()
        return cursor.lastrowid


def get_comments(generation_id, page=1, per_page=20):
    """Get paginated comments for a generation."""
    offset = (page - 1) * per_page

    with get_db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM comments WHERE generation_id = ?",
            (generation_id,)
        ).fetchone()[0]

        rows = conn.execute("""
            SELECT * FROM comments
            WHERE generation_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (generation_id, per_page, offset)).fetchall()

    return {
        'comments': [dict(row) for row in rows],
        'total': total,
        'page': page,
        'per_page': per_page
    }


def delete_comment(comment_id, user_id):
    """Delete a comment (only by owner)."""
    with get_db() as conn:
        result = conn.execute(
            "DELETE FROM comments WHERE id = ? AND user_id = ?",
            (comment_id, user_id)
        )
        conn.commit()
        return result.rowcount > 0


# =============================================================================
# Cleanup / Maintenance
# =============================================================================

def get_stats():
    """Get database statistics."""
    with get_db() as conn:
        gen_count = conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
        vote_count = conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
        comment_count = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
        music_count = conn.execute("SELECT COUNT(*) FROM generations WHERE model = 'music'").fetchone()[0]
        audio_count = conn.execute("SELECT COUNT(*) FROM generations WHERE model = 'audio'").fetchone()[0]

    return {
        'generations': gen_count,
        'music': music_count,
        'audio': audio_count,
        'votes': vote_count,
        'comments': comment_count
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
            print(f"Comments: {stats['comments']}")

        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python database.py [init|migrate|stats]")
    else:
        print("Usage: python database.py [init|migrate|stats]")
