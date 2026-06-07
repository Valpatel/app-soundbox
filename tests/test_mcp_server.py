"""
Unit tests for mcp_server.py

Tests each MCP tool function by mocking the underlying httpx client.
No live Flask server required - all HTTP calls are intercepted.
"""

import pytest
import os
import sys
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mcp_server


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def make_response(json_data, status_code=200):
    """Build a mock httpx Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


@pytest.fixture
def mock_client(monkeypatch):
    """Replace get_client() with a MagicMock; reset any cached client."""
    # Reset cached singleton so get_client returns our mock
    monkeypatch.setattr(mcp_server, "_client", None)
    client = MagicMock()
    monkeypatch.setattr(mcp_server, "get_client", lambda: client)
    return client


@pytest.fixture
def no_sleep(monkeypatch):
    """Patch time.sleep inside mcp_server so polling tests run instantly."""
    monkeypatch.setattr(mcp_server.time, "sleep", lambda _s: None)


# ─────────────────────────────────────────────
# Validation helpers
# ─────────────────────────────────────────────

class TestValidationHelpers:
    def test_validate_id_accepts_valid_hex(self):
        assert mcp_server._validate_id("abc123def456", "job_id") == "abc123def456"

    def test_validate_id_accepts_long_hex(self):
        long_hex = "a" * 64
        assert mcp_server._validate_id(long_hex, "job_id") == long_hex

    def test_validate_id_rejects_empty(self):
        with pytest.raises(ValueError):
            mcp_server._validate_id("", "job_id")

    def test_validate_id_rejects_short(self):
        with pytest.raises(ValueError):
            mcp_server._validate_id("abc", "job_id")

    def test_validate_id_rejects_path_traversal(self):
        with pytest.raises(ValueError):
            mcp_server._validate_id("../../../etc/passwd", "job_id")

    def test_validate_id_rejects_non_hex(self):
        with pytest.raises(ValueError):
            mcp_server._validate_id("xyznotvalidhex!!", "job_id")

    def test_clamp_within_range(self):
        assert mcp_server._clamp(5, 1, 10) == 5

    def test_clamp_below_min(self):
        assert mcp_server._clamp(-3, 1, 10) == 1

    def test_clamp_above_max(self):
        assert mcp_server._clamp(999, 1, 10) == 10


# ─────────────────────────────────────────────
# get_client
# ─────────────────────────────────────────────

class TestGetClient:
    def test_get_client_returns_singleton(self, monkeypatch):
        monkeypatch.setattr(mcp_server, "_client", None)
        c1 = mcp_server.get_client()
        c2 = mcp_server.get_client()
        assert c1 is c2
        # Reset to avoid leaking real httpx client to other tests
        monkeypatch.setattr(mcp_server, "_client", None)

    def test_get_client_sets_mcp_proxy_header(self, monkeypatch):
        monkeypatch.setattr(mcp_server, "_client", None)
        client = mcp_server.get_client()
        assert client.headers.get("X-MCP-Proxy") == "true"
        monkeypatch.setattr(mcp_server, "_client", None)


# ─────────────────────────────────────────────
# generate_audio
# ─────────────────────────────────────────────

class TestGenerateAudio:
    def test_invalid_model_returns_error(self, mock_client):
        result = mcp_server.generate_audio("hello", model="bogus")
        assert "error" in result
        assert "Invalid model" in result["error"]
        mock_client.post.assert_not_called()

    def test_no_wait_returns_job_id(self, mock_client):
        mock_client.post.return_value = make_response(
            {"success": True, "job_id": "abc123def456"}
        )
        result = mcp_server.generate_audio("upbeat synth", model="music", duration=10)
        assert result == {"job_id": "abc123def456", "status": "queued"}
        # Verify duration was passed through
        call_kwargs = mock_client.post.call_args
        assert call_kwargs.kwargs["json"]["duration"] == 10
        assert call_kwargs.kwargs["json"]["prompt"] == "upbeat synth"

    def test_duration_clamped_high(self, mock_client):
        mock_client.post.return_value = make_response(
            {"success": True, "job_id": "abc123def456"}
        )
        mcp_server.generate_audio("hi", model="audio", duration=9999)
        assert mock_client.post.call_args.kwargs["json"]["duration"] == 60

    def test_duration_clamped_low(self, mock_client):
        mock_client.post.return_value = make_response(
            {"success": True, "job_id": "abc123def456"}
        )
        mcp_server.generate_audio("hi", model="audio", duration=0)
        assert mock_client.post.call_args.kwargs["json"]["duration"] == 1

    def test_submission_failure_returns_error(self, mock_client):
        mock_client.post.return_value = make_response(
            {"success": False, "error": "Queue full"}, status_code=503
        )
        result = mcp_server.generate_audio("hi", model="music")
        assert result["error"] == "Queue full"
        assert result["status_code"] == 503

    def test_submission_failure_default_message(self, mock_client):
        mock_client.post.return_value = make_response({"success": False}, status_code=500)
        result = mcp_server.generate_audio("hi", model="music")
        assert result["error"] == "Generation failed"

    def test_wait_true_completes(self, mock_client, no_sleep):
        mock_client.post.return_value = make_response(
            {"success": True, "job_id": "abc123def456"}
        )
        mock_client.get.side_effect = [
            make_response({"status": "running", "progress_pct": 30, "progress": "30%"}),
            make_response({
                "status": "complete",
                "filename": "out.wav",
                "progress_pct": 100,
            }),
        ]
        result = mcp_server.generate_audio(
            "drums", model="music", wait=True, poll_interval=2, max_wait=10
        )
        assert result["status"] == "complete"
        assert result["filename"] == "out.wav"
        assert "out.wav" in result["audio_url"]
        assert "out.wav" in result["download_url"]

    def test_wait_true_failed_job(self, mock_client, no_sleep):
        mock_client.post.return_value = make_response(
            {"success": True, "job_id": "abc123def456"}
        )
        mock_client.get.return_value = make_response(
            {"status": "failed", "error": "OOM"}
        )
        result = mcp_server.generate_audio("x", wait=True, poll_interval=2, max_wait=10)
        assert result["status"] == "failed"
        assert result["error"] == "OOM"

    def test_wait_true_timeout(self, mock_client, no_sleep):
        mock_client.post.return_value = make_response(
            {"success": True, "job_id": "abc123def456"}
        )
        mock_client.get.return_value = make_response(
            {"status": "running", "progress_pct": 10}
        )
        # max_wait clamped low: 5s with 2s polls -> loop ~3x
        result = mcp_server.generate_audio(
            "x", wait=True, poll_interval=2, max_wait=5
        )
        assert "Timed out" in result["error"]


# ─────────────────────────────────────────────
# check_job
# ─────────────────────────────────────────────

class TestCheckJob:
    def test_invalid_job_id(self, mock_client):
        result = mcp_server.check_job("../../bad")
        assert "error" in result
        mock_client.get.assert_not_called()

    def test_job_not_found(self, mock_client):
        mock_client.get.return_value = make_response({}, status_code=404)
        result = mcp_server.check_job("abc123def456")
        assert result["error"] == "Job not found"

    def test_status_running(self, mock_client):
        mock_client.get.return_value = make_response({
            "status": "running",
            "progress": "50%",
            "progress_pct": 50,
        })
        result = mcp_server.check_job("abc123def456")
        assert result["status"] == "running"
        assert result["progress_pct"] == 50
        assert "audio_url" not in result

    def test_status_complete_includes_urls(self, mock_client):
        mock_client.get.return_value = make_response({
            "status": "complete",
            "filename": "song.wav",
        })
        result = mcp_server.check_job("abc123def456")
        assert result["filename"] == "song.wav"
        assert result["audio_url"].endswith("/audio/song.wav")
        assert result["download_url"].endswith("/download/song.wav")

    def test_status_includes_error_field(self, mock_client):
        mock_client.get.return_value = make_response({
            "status": "failed",
            "error": "model crashed",
        })
        result = mcp_server.check_job("abc123def456")
        assert result["error"] == "model crashed"


# ─────────────────────────────────────────────
# search_library
# ─────────────────────────────────────────────

class TestSearchLibrary:
    def test_basic_search(self, mock_client):
        mock_client.get.return_value = make_response({
            "items": [{"id": "1", "filename": "a.wav"}],
            "total": 1,
        })
        result = mcp_server.search_library(search="ambient")
        assert result["total"] == 1
        assert result["items"][0]["audio_url"].endswith("/audio/a.wav")
        params = mock_client.get.call_args.kwargs["params"]
        assert params["search"] == "ambient"
        assert params["page"] == 1
        assert params["per_page"] == 10

    def test_page_clamped(self, mock_client):
        mock_client.get.return_value = make_response({"items": []})
        mcp_server.search_library(page=99999)
        assert mock_client.get.call_args.kwargs["params"]["page"] == 1000

    def test_per_page_clamped(self, mock_client):
        mock_client.get.return_value = make_response({"items": []})
        mcp_server.search_library(per_page=500)
        assert mock_client.get.call_args.kwargs["params"]["per_page"] == 100

    def test_per_page_clamped_low(self, mock_client):
        mock_client.get.return_value = make_response({"items": []})
        mcp_server.search_library(per_page=0)
        assert mock_client.get.call_args.kwargs["params"]["per_page"] == 1

    def test_optional_filters_omitted(self, mock_client):
        mock_client.get.return_value = make_response({"items": []})
        mcp_server.search_library()
        params = mock_client.get.call_args.kwargs["params"]
        assert "search" not in params
        assert "model" not in params
        assert "category" not in params

    def test_items_without_filename_skip_urls(self, mock_client):
        mock_client.get.return_value = make_response({
            "items": [{"id": "1"}],  # No filename
        })
        result = mcp_server.search_library()
        assert "audio_url" not in result["items"][0]


# ─────────────────────────────────────────────
# get_status
# ─────────────────────────────────────────────

class TestGetStatus:
    def test_returns_status_dict(self, mock_client):
        mock_client.get.return_value = make_response({
            "gpu": "RTX 4090", "queue_length": 0,
        })
        result = mcp_server.get_status()
        assert result["gpu"] == "RTX 4090"
        mock_client.get.assert_called_with("/status")


# ─────────────────────────────────────────────
# get_radio_track
# ─────────────────────────────────────────────

class TestGetRadioTrack:
    def test_basic(self, mock_client):
        mock_client.get.return_value = make_response({
            "tracks": [{"id": "1", "filename": "track1.wav"}],
        })
        result = mcp_server.get_radio_track(model="music", count=1)
        assert result["tracks"][0]["audio_url"].endswith("/audio/track1.wav")

    def test_count_clamped_high(self, mock_client):
        mock_client.get.return_value = make_response({"tracks": []})
        mcp_server.get_radio_track(count=999)
        assert mock_client.get.call_args.kwargs["params"]["count"] == 50

    def test_count_clamped_low(self, mock_client):
        mock_client.get.return_value = make_response({"tracks": []})
        mcp_server.get_radio_track(count=0)
        assert mock_client.get.call_args.kwargs["params"]["count"] == 1

    def test_search_param_included(self, mock_client):
        mock_client.get.return_value = make_response({"tracks": []})
        mcp_server.get_radio_track(search="rain")
        params = mock_client.get.call_args.kwargs["params"]
        assert params["search"] == "rain"


# ─────────────────────────────────────────────
# generate_for_project
# ─────────────────────────────────────────────

class TestGenerateForProject:
    def test_invalid_model_returns_error(self, mock_client):
        result = mcp_server.generate_for_project("hi", "myproj", model="bogus")
        assert "error" in result
        mock_client.post.assert_not_called()

    def test_no_wait_returns_queued(self, mock_client):
        mock_client.post.return_value = make_response(
            {"success": True, "job_id": "abc123def456"}
        )
        result = mcp_server.generate_for_project(
            "yawn", "myproj", model="audio", wait=False
        )
        assert result["job_id"] == "abc123def456"
        assert result["status"] == "queued"
        assert result["project"] == "myproj"

    def test_submission_failure(self, mock_client):
        mock_client.post.return_value = make_response(
            {"success": False, "error": "rate limited"}, status_code=429
        )
        result = mcp_server.generate_for_project("x", "p", wait=False)
        assert result["error"] == "rate limited"
        assert result["status_code"] == 429

    def test_wait_true_completes_and_tags(self, mock_client, no_sleep):
        # First post: generation; second post: tag
        mock_client.post.side_effect = [
            make_response({"success": True, "job_id": "abc123def456"}),
            make_response({"success": True, "updated": 1}),
        ]
        mock_client.get.return_value = make_response({
            "status": "complete",
            "filename": "out.wav",
        })
        result = mcp_server.generate_for_project(
            "yawn", "myproj", wait=True, poll_interval=2, max_wait=10
        )
        assert result["status"] == "complete"
        assert result["filename"] == "out.wav"
        assert result["tagged"] is True
        # Verify tag call payload
        tag_call = mock_client.post.call_args_list[1]
        assert tag_call.kwargs["json"]["source"] == "myproj"
        assert tag_call.kwargs["json"]["generation_ids"] == ["abc123def456"]

    def test_wait_true_failed(self, mock_client, no_sleep):
        mock_client.post.return_value = make_response(
            {"success": True, "job_id": "abc123def456"}
        )
        mock_client.get.return_value = make_response(
            {"status": "failed", "error": "model fail"}
        )
        result = mcp_server.generate_for_project(
            "x", "p", wait=True, poll_interval=2, max_wait=10
        )
        assert result["error"] == "model fail"

    def test_duration_clamped(self, mock_client):
        mock_client.post.return_value = make_response(
            {"success": True, "job_id": "abc123def456"}
        )
        mcp_server.generate_for_project("hi", "p", duration=100, wait=False)
        assert mock_client.post.call_args.kwargs["json"]["duration"] == 60


# ─────────────────────────────────────────────
# tag_for_project
# ─────────────────────────────────────────────

class TestTagForProject:
    def test_invalid_id_rejected(self, mock_client):
        result = mcp_server.tag_for_project(["badid!!"], "p")
        assert "error" in result
        mock_client.post.assert_not_called()

    def test_valid_ids_tagged(self, mock_client):
        mock_client.post.return_value = make_response(
            {"success": True, "updated": 2}
        )
        result = mcp_server.tag_for_project(
            ["abc123def456", "deadbeef1234"], "myproj"
        )
        assert result["success"] is True
        assert result["updated"] == 2
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["source"] == "myproj"
        assert payload["generation_ids"] == ["abc123def456", "deadbeef1234"]

    def test_mixed_invalid_id_rejects_all(self, mock_client):
        result = mcp_server.tag_for_project(
            ["abc123def456", "../bad"], "p"
        )
        assert "error" in result
        mock_client.post.assert_not_called()


# ─────────────────────────────────────────────
# get_project_assets
# ─────────────────────────────────────────────

class TestGetProjectAssets:
    def test_basic(self, mock_client):
        mock_client.get.return_value = make_response({
            "items": [{"id": "1", "filename": "a.wav"}],
            "total": 1,
        })
        result = mcp_server.get_project_assets("myproj")
        assert result["items"][0]["audio_url"].endswith("/audio/a.wav")
        params = mock_client.get.call_args.kwargs["params"]
        assert params["source"] == "myproj"
        assert params["sort"] == "recent"

    def test_page_clamped(self, mock_client):
        mock_client.get.return_value = make_response({"items": []})
        mcp_server.get_project_assets("p", page=99999, per_page=9999)
        params = mock_client.get.call_args.kwargs["params"]
        assert params["page"] == 1000
        assert params["per_page"] == 100


# ─────────────────────────────────────────────
# get_rejected_assets
# ─────────────────────────────────────────────

class TestGetRejectedAssets:
    def test_filters_only_downvoted(self, mock_client):
        # Library response: mixed items, library endpoint always called first
        # Then vote endpoint called per rejected item
        mock_client.get.side_effect = [
            make_response({
                "items": [
                    {"id": "abc1", "filename": "x.wav", "downvotes": 2, "upvotes": 0,
                     "prompt": "p1", "model": "audio", "duration": 3},
                    {"id": "abc2", "filename": "y.wav", "downvotes": 0, "upvotes": 5,
                     "prompt": "p2", "model": "audio", "duration": 3},
                ],
                "total": 2,
            }),
            make_response({"votes": [{"feedback": "too quiet"}]}),
        ]
        result = mcp_server.get_rejected_assets("myproj")
        assert result["project"] == "myproj"
        assert result["total_assets"] == 2
        assert result["rejected_count"] == 1
        assert result["rejected"][0]["id"] == "abc1"
        assert result["rejected"][0]["audio_url"].endswith("/audio/x.wav")
        assert "feedback" in result["rejected"][0]

    def test_vote_endpoint_failure_is_swallowed(self, mock_client):
        mock_client.get.side_effect = [
            make_response({
                "items": [
                    {"id": "abc1", "filename": "x.wav", "downvotes": 1,
                     "upvotes": 0, "prompt": "p", "model": "audio", "duration": 3},
                ],
                "total": 1,
            }),
            make_response({}, status_code=500),  # Not 200, so feedback omitted
        ]
        result = mcp_server.get_rejected_assets("myproj")
        assert result["rejected_count"] == 1
        assert "feedback" not in result["rejected"][0]

    def test_vote_endpoint_exception_swallowed(self, mock_client):
        # First call returns items, second call raises
        first = make_response({
            "items": [
                {"id": "abc1", "filename": "x.wav", "downvotes": 1,
                 "upvotes": 0, "prompt": "p", "model": "audio", "duration": 3},
            ],
            "total": 1,
        })

        def get_side(*args, **kwargs):
            if not hasattr(get_side, "called"):
                get_side.called = True
                return first
            raise RuntimeError("network down")

        mock_client.get.side_effect = get_side
        result = mcp_server.get_rejected_assets("myproj")
        assert result["rejected_count"] == 1

    def test_no_items(self, mock_client):
        mock_client.get.return_value = make_response({"items": [], "total": 0})
        result = mcp_server.get_rejected_assets("myproj")
        assert result["rejected_count"] == 0
        assert result["rejected"] == []


# ─────────────────────────────────────────────
# list_project_sources
# ─────────────────────────────────────────────

class TestListProjectSources:
    def test_returns_sources(self, mock_client):
        mock_client.get.return_value = make_response({
            "sources": [{"id": "p1", "name": "Project One"}],
        })
        result = mcp_server.list_project_sources()
        assert result["sources"][0]["id"] == "p1"
        mock_client.get.assert_called_with("/api/assets/sources")


# ─────────────────────────────────────────────
# download_audio
# ─────────────────────────────────────────────

class TestDownloadAudio:
    def test_invalid_id(self, mock_client):
        result = mcp_server.download_audio("../etc/passwd")
        assert "error" in result
        mock_client.get.assert_not_called()

    def test_not_found(self, mock_client):
        mock_client.get.return_value = make_response({}, status_code=404)
        result = mcp_server.download_audio("abc123def456")
        assert result["error"] == "Track not found"

    def test_success(self, mock_client):
        mock_client.get.return_value = make_response({
            "id": "abc123def456",
            "filename": "song.wav",
            "prompt": "ambient",
        })
        result = mcp_server.download_audio("abc123def456")
        assert result["audio_url"].endswith("/audio/song.wav")
        assert result["download_url"].endswith("/download/song.wav")
        assert result["prompt"] == "ambient"

    def test_no_filename_no_urls(self, mock_client):
        mock_client.get.return_value = make_response({
            "id": "abc123def456",
            "filename": "",
        })
        result = mcp_server.download_audio("abc123def456")
        assert "audio_url" not in result
