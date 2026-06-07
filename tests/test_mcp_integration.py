"""
Integration tests for mcp_server.py

Spawns the MCP server as a real subprocess (stdio transport) and speaks the
MCP protocol to it via the official `mcp` Python SDK client. These tests
complement the unit tests in test_mcp_server.py — they verify that the server
actually starts, registers its tools with FastMCP correctly, and responds to
real MCP protocol messages.

Requires the Flask server on port 5309 to be running (tools that call
/status, /api/library, etc. proxy through to it).
"""

import os
import sys
from pathlib import Path

import pytest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# Project root (one level above this file)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Expected tool names registered by mcp_server.py
EXPECTED_TOOLS = {
    "generate_audio",
    "check_job",
    "search_library",
    "get_status",
    "get_radio_track",
    "generate_for_project",
    "tag_for_project",
    "get_project_assets",
    "get_rejected_assets",
    "list_project_sources",
    "download_audio",
}


def _server_params() -> StdioServerParameters:
    """Build StdioServerParameters that spawn the MCP server from this repo."""
    venv_python = PROJECT_ROOT / "venv" / "bin" / "python"
    server_script = PROJECT_ROOT / "mcp_server.py"

    # Inherit a minimal but functional env. The SDK requires at least PATH;
    # we also pass through HOME and SOUNDBOX_URL so the server can reach Flask.
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "SOUNDBOX_URL": os.environ.get("SOUNDBOX_URL", "http://localhost:5309"),
        "PYTHONUNBUFFERED": "1",
    }

    return StdioServerParameters(
        command=str(venv_python),
        args=[str(server_script)],
        env=env,
        cwd=str(PROJECT_ROOT),
    )


# ─────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_server_starts():
    """Server spawns via stdio and an MCP session initializes cleanly."""
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            init_result = await session.initialize()
            # Server should advertise itself; name comes from FastMCP("Sound Box")
            assert init_result is not None
            assert init_result.serverInfo is not None
            assert init_result.serverInfo.name.lower().startswith("sound")


@pytest.mark.asyncio
async def test_list_tools():
    """All 11 expected tools are registered with FastMCP."""
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            names = {tool.name for tool in tools_result.tools}
            missing = EXPECTED_TOOLS - names
            assert not missing, f"Missing tools: {missing}. Got: {names}"
            assert len(tools_result.tools) >= len(EXPECTED_TOOLS)


@pytest.mark.asyncio
async def test_tool_schemas():
    """Every registered tool has an inputSchema and a description."""
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            for tool in tools_result.tools:
                assert tool.description, f"{tool.name} has no description"
                assert tool.inputSchema, f"{tool.name} has no inputSchema"
                # inputSchema should be a JSON Schema object dict
                assert isinstance(tool.inputSchema, dict), (
                    f"{tool.name} inputSchema is not a dict: {type(tool.inputSchema)}"
                )
                assert tool.inputSchema.get("type") == "object", (
                    f"{tool.name} inputSchema type is not object"
                )


@pytest.mark.asyncio
async def test_call_get_status():
    """get_status proxies to Flask /status and returns expected keys."""
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("get_status", {})

            assert result is not None
            assert not result.isError, f"Tool returned error: {result.content}"

            # FastMCP returns dict results both as structuredContent (when
            # supported by the SDK version) and as JSON text content.
            payload = None
            if getattr(result, "structuredContent", None):
                payload = result.structuredContent
            else:
                # Fall back to parsing JSON text content
                import json
                for block in result.content:
                    text = getattr(block, "text", None)
                    if text:
                        try:
                            payload = json.loads(text)
                            break
                        except json.JSONDecodeError:
                            continue

            assert isinstance(payload, dict), f"Expected dict, got {type(payload)}: {payload}"
            # /status returns these top-level keys
            assert "gpu" in payload or "models" in payload or "queue_length" in payload, (
                f"Unexpected /status payload: {list(payload.keys())}"
            )


@pytest.mark.asyncio
async def test_call_search_library():
    """search_library accepts query+limit and returns successfully."""
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_library", {"query": "test", "limit": 5}
            )
            assert result is not None
            assert not result.isError, f"Tool returned error: {result.content}"
            # We don't assert on specific contents — just that the call
            # completed without error and produced some content.
            assert result.content, "search_library returned empty content"


@pytest.mark.asyncio
async def test_invalid_tool_call():
    """Calling a non-existent tool returns an error (not a crash)."""
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # The SDK may either return a CallToolResult with isError=True
            # or raise an McpError. Either is acceptable — what matters is
            # that the server does not crash the session.
            from mcp.shared.exceptions import McpError

            errored = False
            try:
                result = await session.call_tool("this_tool_does_not_exist", {})
                if result.isError:
                    errored = True
            except McpError:
                errored = True

            assert errored, "Expected error for non-existent tool"

            # Session should still be alive — verify by listing tools again
            tools_result = await session.list_tools()
            assert len(tools_result.tools) > 0
