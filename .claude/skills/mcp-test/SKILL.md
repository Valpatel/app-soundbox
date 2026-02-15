---
name: mcp-test
description: Test MCP server tools via stdio transport
disable-model-invocation: true
allowed-tools: Bash
argument-hint: "[tool_name json_args]"
---

## MCP Tool Test

Test the MCP server tools via stdio transport. The Sound Box server must be running on localhost:5309.

If `$ARGUMENTS` specifies a tool name and args, test that specific tool. Otherwise test all 6 tools.

### Setup
First send the initialize handshake, then the tool call. Use a heredoc to send both messages:

```bash
(echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}'; echo '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}'; echo '<tool_call>') | timeout 10 ./venv/bin/python mcp_server.py 2>/dev/null
```

### All 6 Tools (no arguments)

Test each tool with safe read-only calls:

1. **get_status**: `{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_status","arguments":{}},"id":2}`
2. **search_library**: `{"jsonrpc":"2.0","method":"tools/call","params":{"name":"search_library","arguments":{"query":"test","per_page":2}},"id":3}`
3. **get_radio_track**: `{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_radio_track","arguments":{"count":1}},"id":4}`
4. **check_job**: `{"jsonrpc":"2.0","method":"tools/call","params":{"name":"check_job","arguments":{"job_id":"0000000000000000"}},"id":5}` (expect "not found" - that's OK)
5. **download_audio**: `{"jsonrpc":"2.0","method":"tools/call","params":{"name":"download_audio","arguments":{"gen_id":"0000000000000000"}},"id":6}` (expect "not found")
6. **generate_audio**: Skip actual generation — just verify the tool exists by calling `tools/list`

### Specific Tool (with arguments)

Call the specified tool with the provided JSON arguments.

### Output
Report for each tool: tool name, status (OK/ERROR), brief response summary.
