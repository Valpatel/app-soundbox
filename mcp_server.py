"""
Sound Box MCP Server

Exposes Sound Box API endpoints as MCP tools for AI agents.
Runs as a separate process, communicating with the Flask app via HTTP.

Usage:
  # stdio transport (for Claude Code / .mcp.json)
  venv/bin/python mcp_server.py

  # SSE transport (for network AI agents)
  venv/bin/python mcp_server.py --transport sse --port 5310
"""

import os
import re
import sys
import time
import argparse
import httpx
from mcp.server.fastmcp import FastMCP

SOUNDBOX_URL = os.environ.get("SOUNDBOX_URL", "http://localhost:5309")

# MCP API key for SSE transport authentication.
# When set, all SSE connections must provide this key via Bearer token.
# stdio transport (local process) is always trusted and never requires a key.
MCP_API_KEY = os.environ.get("MCP_API_KEY", "")

mcp = FastMCP(
    "Sound Box",
    instructions=(
        "Sound Box is an AI audio generation server. Use these tools to generate "
        "music and sound effects from text prompts, search the audio library, "
        "and check system status. Generated audio is CC0 (public domain)."
    ),
)

# Shared HTTP client — uses a dedicated header so Flask can identify
# MCP-proxied requests and apply appropriate rate limits.
_client = None

def get_client():
    global _client
    if _client is None:
        _client = httpx.Client(
            base_url=SOUNDBOX_URL,
            timeout=30.0,
            headers={"X-MCP-Proxy": "true"},
        )
    return _client


# ─────────────────────────────────────────────
# Input validation helpers
# ─────────────────────────────────────────────

# Hex string pattern for UUIDs / job IDs (32 hex chars, no slashes or dots)
_SAFE_ID_RE = re.compile(r"^[a-fA-F0-9]{8,64}$")

def _validate_id(value: str, name: str) -> str:
    """Validate that an ID is a safe hex string (no path traversal)."""
    if not value or not _SAFE_ID_RE.match(value):
        raise ValueError(f"Invalid {name}: must be 8-64 hex characters")
    return value


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


# ─────────────────────────────────────────────
# MCP Tools
# ─────────────────────────────────────────────

@mcp.tool()
def generate_audio(
    prompt: str,
    model: str = "music",
    duration: int = 8,
    wait: bool = False,
    poll_interval: int = 3,
    max_wait: int = 120,
) -> dict:
    """Submit an audio generation job.

    Args:
        prompt: Text description of the audio to generate.
                For music: "upbeat electronic with synth pads"
                For SFX: "thunder rolling across a valley"
        model: "music" (MusicGen), "audio" (AudioGen/SFX),
               "magnet-music", or "magnet-audio"
        duration: Length in seconds (1-60, default 8)
        wait: If True, poll until the job completes and return the result.
              If False (default), return immediately with the job_id.
        poll_interval: Seconds between polls when wait=True (default 3)
        max_wait: Maximum seconds to wait when wait=True (default 120)

    Returns:
        Job info dict with id, status, and (if complete) filename and download URL.
    """
    # Validate model
    if model not in ("music", "audio", "magnet-music", "magnet-audio"):
        return {"error": f"Invalid model: {model}. Use music, audio, magnet-music, or magnet-audio."}

    # Clamp numeric parameters to safe ranges
    duration = _clamp(duration, 1, 60)
    poll_interval = _clamp(poll_interval, 2, 30)
    max_wait = _clamp(max_wait, 5, 300)

    client = get_client()
    r = client.post("/generate", json={
        "prompt": prompt,
        "model": model,
        "duration": duration,
    })
    data = r.json()

    if not data.get("success"):
        return {"error": data.get("error", "Generation failed"), "status_code": r.status_code}

    job_id = data["job_id"]
    result = {"job_id": job_id, "status": "queued"}

    if not wait:
        return result

    # Poll for completion
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval
        status = client.get(f"/job/{job_id}").json()
        result["status"] = status.get("status", "unknown")
        result["progress"] = status.get("progress", "")
        result["progress_pct"] = status.get("progress_pct", 0)

        if status.get("status") == "complete":
            filename = status.get("filename", "")
            result["filename"] = filename
            result["audio_url"] = f"{SOUNDBOX_URL}/audio/{filename}"
            result["download_url"] = f"{SOUNDBOX_URL}/download/{filename}"
            return result

        if status.get("status") == "failed":
            result["error"] = status.get("error", "Generation failed")
            return result

    result["error"] = f"Timed out after {max_wait}s (job still {result['status']})"
    return result


@mcp.tool()
def check_job(job_id: str) -> dict:
    """Check the status of a generation job.

    Args:
        job_id: The job ID returned by generate_audio.

    Returns:
        Job status with progress info, and audio URLs if complete.
    """
    try:
        job_id = _validate_id(job_id, "job_id")
    except ValueError as e:
        return {"error": str(e)}

    client = get_client()
    r = client.get(f"/job/{job_id}")
    if r.status_code == 404:
        return {"error": "Job not found"}

    status = r.json()
    result = {
        "job_id": job_id,
        "status": status.get("status"),
        "progress": status.get("progress", ""),
        "progress_pct": status.get("progress_pct", 0),
    }

    if status.get("status") == "complete":
        filename = status.get("filename", "")
        result["filename"] = filename
        result["audio_url"] = f"{SOUNDBOX_URL}/audio/{filename}"
        result["download_url"] = f"{SOUNDBOX_URL}/download/{filename}"

    if status.get("error"):
        result["error"] = status["error"]

    return result


@mcp.tool()
def search_library(
    search: str = "",
    model: str = "",
    sort: str = "recent",
    category: str = "",
    page: int = 1,
    per_page: int = 10,
) -> dict:
    """Search and browse the Sound Box audio library.

    Args:
        search: Full-text search query (searches prompts).
        model: Filter by type: "music", "audio" (SFX), or "voice".
        sort: Sort order: "recent", "popular", or "rating".
        category: Filter by genre/category (e.g. "ambient", "nature").
        page: Page number (default 1).
        per_page: Results per page (default 10, max 100).

    Returns:
        Paginated results with track metadata and audio URLs.
    """
    page = _clamp(page, 1, 1000)
    per_page = _clamp(per_page, 1, 100)

    client = get_client()
    params = {"page": page, "per_page": per_page, "sort": sort}
    if search:
        params["search"] = search
    if model:
        params["model"] = model
    if category:
        params["category"] = category

    r = client.get("/api/library", params=params)
    data = r.json()

    # Add audio URLs to each track
    for item in data.get("items", []):
        filename = item.get("filename", "")
        if filename:
            item["audio_url"] = f"{SOUNDBOX_URL}/audio/{filename}"
            item["download_url"] = f"{SOUNDBOX_URL}/download/{filename}"

    return data


@mcp.tool()
def get_status() -> dict:
    """Get Sound Box system status including GPU info, model states, and queue length.

    Returns:
        System status with model loading states, GPU memory, queue length,
        and estimated wait time.
    """
    client = get_client()
    r = client.get("/status")
    return r.json()


@mcp.tool()
def get_radio_track(
    model: str = "music",
    search: str = "",
    count: int = 1,
) -> dict:
    """Get random tracks from the radio.

    Useful for discovering audio, getting samples, or curating playlists.

    Args:
        model: "music" or "audio" (SFX).
        search: Optional keyword filter (e.g. "ambient", "rain").
        count: Number of tracks to return (1-50, default 1).

    Returns:
        List of random tracks with metadata and audio URLs.
    """
    count = _clamp(count, 1, 50)

    client = get_client()
    params = {"count": count}
    if model:
        params["model"] = model
    if search:
        params["search"] = search

    r = client.get("/api/radio/shuffle", params=params)
    data = r.json()

    for track in data.get("tracks", []):
        filename = track.get("filename", "")
        if filename:
            track["audio_url"] = f"{SOUNDBOX_URL}/audio/{filename}"
            track["download_url"] = f"{SOUNDBOX_URL}/download/{filename}"

    return data


@mcp.tool()
def download_audio(gen_id: str) -> dict:
    """Get download and streaming URLs for a track.

    Args:
        gen_id: The generation/track ID.

    Returns:
        Track metadata with audio_url (streaming) and download_url.
    """
    try:
        gen_id = _validate_id(gen_id, "gen_id")
    except ValueError as e:
        return {"error": str(e)}

    client = get_client()
    r = client.get(f"/api/library/{gen_id}")
    if r.status_code == 404:
        return {"error": "Track not found"}

    track = r.json()
    filename = track.get("filename", "")
    if filename:
        track["audio_url"] = f"{SOUNDBOX_URL}/audio/{filename}"
        track["download_url"] = f"{SOUNDBOX_URL}/download/{filename}"

    return track


def main():
    parser = argparse.ArgumentParser(description="Sound Box MCP Server")
    parser.add_argument(
        "--transport", choices=["stdio", "sse"], default="stdio",
        help="Transport mode (default: stdio)"
    )
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("MCP_PORT", 5310)),
        help="Port for SSE transport (default: 5310)"
    )
    args = parser.parse_args()

    if args.transport == "sse":
        if not MCP_API_KEY:
            print(
                "WARNING: MCP_API_KEY is not set. The SSE server will reject all connections.\n"
                "Set MCP_API_KEY in .env or environment to enable SSE access.\n"
                "Example: MCP_API_KEY=$(python3 -c \"import secrets; print(secrets.token_urlsafe(32))\")",
                file=sys.stderr,
            )

        # Bind to localhost only — use a reverse proxy for network access
        mcp.settings.host = "127.0.0.1"
        mcp.settings.port = args.port
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
