"""
Unit tests for database.py

Tests core database functions with a real SQLite database.
No mocking of database operations - tests real behavior.
"""

import pytest
import sqlite3
import tempfile
import os
import json
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database as db


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    # Save original path
    original_path = db.DB_PATH

    # Create temp database
    fd, temp_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    db.DB_PATH = temp_path

    # Initialize schema
    db.init_db()

    yield temp_path

    # Restore original path and cleanup
    db.DB_PATH = original_path
    try:
        os.unlink(temp_path)
    except OSError:
        pass


class TestSanitizeFts5Query:
    """Test FTS5 query sanitization for security."""

    def test_basic_query(self):
        """Simple word query should be quoted."""
        result = db.sanitize_fts5_query("ambient")
        assert result == '"ambient"'

    def test_multiple_words(self):
        """Multiple words should be OR-joined."""
        result = db.sanitize_fts5_query("ambient electronic")
        assert '"ambient"' in result
        assert '"electronic"' in result
        assert ' OR ' in result

    def test_removes_dangerous_operators(self):
        """FTS5 operators should be removed."""
        result = db.sanitize_fts5_query("test NOT evil")
        assert 'NOT' not in result
        assert '"test"' in result
        assert '"evil"' in result

    def test_removes_asterisk_wildcard(self):
        """Wildcard operators should be removed."""
        result = db.sanitize_fts5_query("test*")
        assert '*' not in result
        assert '"test"' in result

    def test_removes_column_specifier(self):
        """Column specifiers should be removed."""
        result = db.sanitize_fts5_query("prompt:test")
        assert ':' not in result

    def test_empty_input(self):
        """Empty input should return None."""
        assert db.sanitize_fts5_query("") is None
        assert db.sanitize_fts5_query(None) is None

    def test_only_operators(self):
        """Input with only operators should return None."""
        assert db.sanitize_fts5_query("NOT AND OR") is None

    def test_injection_attempt(self):
        """SQL injection attempts should be sanitized."""
        result = db.sanitize_fts5_query("test'); DROP TABLE--")
        # Should be safe and not contain dangerous chars
        assert ';' not in result
        assert '--' not in result


class TestCreateGeneration:
    """Test generation creation."""

    def test_create_generation(self, test_db):
        """Create a generation and verify it exists."""
        gen_id = "test123"
        db.create_generation(
            gen_id=gen_id,
            prompt="Test prompt",
            model="music",
            filename="test.wav",
            duration=30.0
        )

        # Verify it was created
        with db.get_db() as conn:
            row = conn.execute(
                "SELECT * FROM generations WHERE id = ?", (gen_id,)
            ).fetchone()

            assert row is not None
            assert row['prompt'] == "Test prompt"
            assert row['model'] == "music"
            assert row['filename'] == "test.wav"
            assert row['duration'] == 30.0

    def test_create_generation_with_category(self, test_db):
        """Create generation with category tags."""
        gen_id = "test_cat"
        db.create_generation(
            gen_id=gen_id,
            prompt="Ambient music",
            model="music",
            filename="ambient.wav",
            duration=60.0,
            tags=["ambient", "chill"]
        )

        with db.get_db() as conn:
            row = conn.execute(
                "SELECT category FROM generations WHERE id = ?", (gen_id,)
            ).fetchone()

            assert row is not None
            categories = json.loads(row['category'])
            assert "ambient" in categories
            assert "chill" in categories

    def test_create_voice_generation(self, test_db):
        """Create voice generation with voice_id."""
        gen_id = "voice_test"
        db.create_generation(
            gen_id=gen_id,
            prompt="Hello world",
            model="voice",
            filename="hello.wav",
            duration=2.0,
            voice_id="en_US-lessac-medium"
        )

        with db.get_db() as conn:
            row = conn.execute(
                "SELECT voice_id FROM generations WHERE id = ?", (gen_id,)
            ).fetchone()

            assert row is not None
            assert row['voice_id'] == "en_US-lessac-medium"


class TestGetLibrary:
    """Test library retrieval."""

    @pytest.fixture
    def populated_db(self, test_db):
        """Create a database with test data."""
        # Add some test generations
        for i in range(15):
            model = "music" if i % 3 == 0 else ("audio" if i % 3 == 1 else "voice")
            db.create_generation(
                gen_id=f"gen_{i}",
                prompt=f"Test prompt {i}",
                model=model,
                filename=f"test_{i}.wav",
                duration=30.0,
                is_public=True
            )
        return test_db

    def test_get_library_pagination(self, populated_db):
        """Test pagination works correctly."""
        # First page
        result = db.get_library(page=1, per_page=5)
        assert len(result['items']) == 5
        assert result['page'] == 1
        assert result['total'] >= 15

        # Second page
        result2 = db.get_library(page=2, per_page=5)
        assert len(result2['items']) == 5

        # Items should be different
        ids1 = {item['id'] for item in result['items']}
        ids2 = {item['id'] for item in result2['items']}
        assert ids1.isdisjoint(ids2)

    def test_get_library_model_filter(self, populated_db):
        """Test filtering by model type."""
        result = db.get_library(model="music")

        for item in result['items']:
            assert item['model'] == "music"

    def test_get_library_search(self, populated_db):
        """Test search functionality."""
        result = db.get_library(search="Test prompt")

        # Should find results
        assert len(result['items']) > 0


class TestVoting:
    """Test voting functionality."""

    @pytest.fixture
    def gen_with_votes(self, test_db):
        """Create a generation for voting tests."""
        gen_id = "vote_test_gen"
        db.create_generation(
            gen_id=gen_id,
            prompt="Test for voting",
            model="music",
            filename="vote_test.wav",
            duration=30.0,
            is_public=True
        )
        return gen_id

    def test_upvote(self, gen_with_votes):
        """Test upvoting a generation."""
        gen_id = gen_with_votes
        user_id = "user_123"

        result = db.vote(gen_id, user_id, 1)
        assert result['success'] == True

        # Check vote count
        with db.get_db() as conn:
            row = conn.execute(
                "SELECT upvotes, downvotes FROM generations WHERE id = ?",
                (gen_id,)
            ).fetchone()
            assert row['upvotes'] == 1
            assert row['downvotes'] == 0

    def test_downvote(self, gen_with_votes):
        """Test downvoting a generation."""
        gen_id = gen_with_votes
        user_id = "user_456"

        result = db.vote(gen_id, user_id, -1)
        assert result['success'] == True

        with db.get_db() as conn:
            row = conn.execute(
                "SELECT upvotes, downvotes FROM generations WHERE id = ?",
                (gen_id,)
            ).fetchone()
            assert row['upvotes'] == 0
            assert row['downvotes'] == 1

    def test_change_vote(self, gen_with_votes):
        """Test changing vote from up to down."""
        gen_id = gen_with_votes
        user_id = "user_789"

        # First upvote
        db.vote(gen_id, user_id, 1)

        # Then change to downvote
        db.vote(gen_id, user_id, -1)

        with db.get_db() as conn:
            row = conn.execute(
                "SELECT upvotes, downvotes FROM generations WHERE id = ?",
                (gen_id,)
            ).fetchone()
            # Should have canceled upvote and added downvote
            assert row['upvotes'] == 0
            assert row['downvotes'] == 1

    def test_remove_vote(self, gen_with_votes):
        """Test removing a vote."""
        gen_id = gen_with_votes
        user_id = "user_abc"

        # First upvote
        db.vote(gen_id, user_id, 1)

        # Then remove vote
        db.vote(gen_id, user_id, 0)

        with db.get_db() as conn:
            row = conn.execute(
                "SELECT upvotes, downvotes FROM generations WHERE id = ?",
                (gen_id,)
            ).fetchone()
            assert row['upvotes'] == 0
            assert row['downvotes'] == 0


class TestFavorites:
    """Test favorites functionality."""

    @pytest.fixture
    def gen_for_favorites(self, test_db):
        """Create a generation for favorites tests."""
        gen_id = "fav_test_gen"
        db.create_generation(
            gen_id=gen_id,
            prompt="Test for favorites",
            model="music",
            filename="fav_test.wav",
            duration=30.0,
            is_public=True
        )
        return gen_id

    def test_add_favorite(self, gen_for_favorites):
        """Test adding a favorite."""
        gen_id = gen_for_favorites
        user_id = "fav_user"

        result = db.toggle_favorite(gen_id, user_id)
        assert result['success'] == True
        assert result['is_favorite'] == True

    def test_remove_favorite(self, gen_for_favorites):
        """Test removing a favorite."""
        gen_id = gen_for_favorites
        user_id = "fav_user2"

        # Add then remove
        db.toggle_favorite(gen_id, user_id)
        result = db.toggle_favorite(gen_id, user_id)

        assert result['success'] == True
        assert result['is_favorite'] == False

    def test_get_favorites(self, gen_for_favorites):
        """Test getting user favorites."""
        gen_id = gen_for_favorites
        user_id = "fav_user3"

        # Add favorite
        db.toggle_favorite(gen_id, user_id)

        # Get favorites
        favorites = db.get_favorites(user_id)

        assert len(favorites['favorites']) > 0
        fav_ids = [f['id'] for f in favorites['favorites']]
        assert gen_id in fav_ids


class TestCategoryFunctions:
    """Test category-related functions."""

    def test_music_categories_defined(self):
        """Music categories should be defined."""
        assert hasattr(db, 'MUSIC_CATEGORIES')
        assert len(db.MUSIC_CATEGORIES) > 0

    def test_sfx_categories_defined(self):
        """SFX categories should be defined."""
        assert hasattr(db, 'SFX_CATEGORIES')
        assert len(db.SFX_CATEGORIES) > 0

    def test_get_category_counts(self, test_db):
        """Test getting category counts."""
        # Add some categorized generations
        db.create_generation(
            gen_id="cat_test_1",
            prompt="Ambient music",
            model="music",
            filename="cat1.wav",
            duration=30.0,
            is_public=True,
            tags=["ambient"]
        )
        db.create_generation(
            gen_id="cat_test_2",
            prompt="Explosion sound",
            model="audio",
            filename="cat2.wav",
            duration=5.0,
            is_public=True,
            tags=["explosion"]
        )

        counts = db.get_category_counts()

        # Should return a dict with category counts
        assert isinstance(counts, dict)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
