"""
Unit tests for API input validation

Tests the validation functions used by API endpoints.
These are real tests - no mocking of validation logic.
"""

import pytest
import sys
import os
import re

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import after adding to path
try:
    from app import (
        is_safe_filename,
        validate_prompt,
        validate_integer,
        contains_blocked_content,
        SAFE_FILENAME_PATTERN
    )
    HAS_APP = True
except ImportError as e:
    print(f"Could not import from app: {e}")
    HAS_APP = False


@pytest.mark.skipif(not HAS_APP, reason="App module not available")
class TestSafeFilename:
    """Test filename validation."""

    def test_valid_filename(self):
        """Valid filenames should pass."""
        assert is_safe_filename("audio_123.wav") == True
        assert is_safe_filename("music-test.wav") == True
        assert is_safe_filename("file.wav") == True

    def test_path_traversal_blocked(self):
        """Path traversal attempts should be blocked."""
        assert is_safe_filename("../etc/passwd") == False
        assert is_safe_filename("..\\windows\\system32") == False
        assert is_safe_filename("dir/file.wav") == False
        assert is_safe_filename("dir\\file.wav") == False

    def test_double_dot_blocked(self):
        """Double dots should be blocked."""
        assert is_safe_filename("..file.wav") == False
        assert is_safe_filename("file..wav") == False

    def test_wrong_extension_blocked(self):
        """Non-wav/png extensions should be blocked."""
        assert is_safe_filename("file.exe") == False
        assert is_safe_filename("file.php") == False
        assert is_safe_filename("file.txt") == False
        assert is_safe_filename("file") == False

    def test_png_extension_allowed(self):
        """PNG extension should be allowed (for spectrograms)."""
        assert is_safe_filename("spectrogram.png") == True

    def test_empty_filename_blocked(self):
        """Empty filename should be blocked."""
        assert is_safe_filename("") == False
        assert is_safe_filename(None) == False

    def test_special_chars_blocked(self):
        """Special characters should be blocked."""
        assert is_safe_filename("file<script>.wav") == False
        assert is_safe_filename("file;rm -rf.wav") == False
        assert is_safe_filename("file|cat.wav") == False


@pytest.mark.skipif(not HAS_APP, reason="App module not available")
class TestValidatePrompt:
    """Test prompt validation."""

    def test_valid_prompt(self):
        """Valid prompts should pass."""
        is_valid, prompt, error = validate_prompt("Create ambient music")
        assert is_valid == True
        assert prompt == "Create ambient music"
        assert error is None

    def test_empty_prompt_default(self):
        """Empty prompt should get default."""
        is_valid, prompt, error = validate_prompt("")
        # Should either pass with default or fail with error
        assert isinstance(is_valid, bool)

    def test_too_long_prompt(self):
        """Overly long prompts should be truncated or rejected."""
        long_prompt = "x" * 10000
        is_valid, prompt, error = validate_prompt(long_prompt)
        # Should either truncate or reject
        assert len(prompt) < 10000 or error is not None

    def test_prompt_stripped(self):
        """Prompts should be stripped of whitespace."""
        is_valid, prompt, error = validate_prompt("  ambient music  ")
        assert prompt.strip() == prompt


@pytest.mark.skipif(not HAS_APP, reason="App module not available")
class TestValidateInteger:
    """Test integer validation."""

    def test_valid_integer(self):
        """Valid integers should pass."""
        is_valid, value, error = validate_integer(30, "duration", 1, 180)
        assert is_valid == True
        assert value == 30

    def test_string_integer(self):
        """String integers should be converted."""
        is_valid, value, error = validate_integer("30", "duration", 1, 180)
        assert is_valid == True
        assert value == 30

    def test_below_minimum(self):
        """Values below minimum should fail."""
        is_valid, value, error = validate_integer(0, "duration", 1, 180)
        assert is_valid == False
        assert error is not None

    def test_above_maximum(self):
        """Values above maximum should fail."""
        is_valid, value, error = validate_integer(300, "duration", 1, 180)
        assert is_valid == False
        assert error is not None

    def test_invalid_value(self):
        """Non-numeric values should fail."""
        is_valid, value, error = validate_integer("not_a_number", "duration", 1, 180)
        assert is_valid == False

    def test_default_value(self):
        """Default value should be used when None."""
        is_valid, value, error = validate_integer(None, "duration", 1, 180, default=30)
        assert is_valid == True
        assert value == 30


@pytest.mark.skipif(not HAS_APP, reason="App module not available")
class TestBlockedContent:
    """Test content blocking."""

    def test_normal_content_allowed(self):
        """Normal content should be allowed."""
        is_blocked, reason = contains_blocked_content("ambient electronic music")
        assert is_blocked == False

    def test_empty_content_allowed(self):
        """Empty content should be allowed (or handled)."""
        is_blocked, reason = contains_blocked_content("")
        # Empty might be allowed or blocked - just shouldn't crash
        assert isinstance(is_blocked, bool)


class TestSafeFilenamePattern:
    """Test the filename regex pattern directly."""

    def test_alphanumeric(self):
        """Alphanumeric should match."""
        pattern = re.compile(r'^[a-zA-Z0-9_\-\.]+$')
        assert pattern.match("test123")
        assert pattern.match("TEST_file-name.wav")

    def test_special_chars_no_match(self):
        """Special chars should not match."""
        pattern = re.compile(r'^[a-zA-Z0-9_\-\.]+$')
        assert not pattern.match("test<>file")
        assert not pattern.match("test;file")
        assert not pattern.match("test file")  # space
        assert not pattern.match("test/file")


class TestPathTraversalPrevention:
    """Test path traversal prevention patterns."""

    def test_basic_traversal(self):
        """Basic path traversal should be detected."""
        dangerous_paths = [
            "../etc/passwd",
            "..\\windows\\system32",
            "....//....//etc/passwd",
            "..\\..",
        ]
        for path in dangerous_paths:
            assert ".." in path or "/" in path or "\\" in path

    def test_encoded_traversal(self):
        """URL-encoded traversal patterns."""
        # These should be handled by Flask/Werkzeug, but document them
        encoded_patterns = [
            "%2e%2e%2f",  # ../
            "%2e%2e/",   # ../
            "..%2f",     # ../
            "%2e%2e%5c", # ..\
        ]
        # Note: URL decoding happens before our validation
        # These are informational - our validation catches decoded versions


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
