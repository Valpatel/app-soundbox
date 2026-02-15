---
name: logs
description: View recent Sound Box server logs
disable-model-invocation: true
allowed-tools: Bash
argument-hint: "[N|mcp|all]"
---

## View Logs

Show recent Sound Box logs from journalctl.

Parse `$ARGUMENTS`:
- **number** (e.g., `50`) - Show last N lines of main soundbox logs
- **mcp** - Show last 50 lines of MCP server logs only
- **all** - Show last 50 lines of both services interleaved
- **no argument** - Show last 30 lines of main soundbox logs

Commands:
- Default/number: `sudo journalctl -u soundbox --no-pager -n <N>`
- mcp: `sudo journalctl -u soundbox-mcp --no-pager -n 50`
- all: `sudo journalctl -u soundbox -u soundbox-mcp --no-pager -n 50`

After showing logs, briefly summarize any errors or warnings found.
