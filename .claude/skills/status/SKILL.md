---
name: status
description: Quick health check of the Sound Box server, MCP server, GPU, and systemd services
disable-model-invocation: true
allowed-tools: Bash
argument-hint: ""
---

## Status Check

Run a comprehensive health check of Sound Box services.

Steps:
1. Check Flask server: `curl -s http://localhost:5309/status`
2. Check systemd services:
   ```bash
   systemctl is-active soundbox 2>/dev/null || echo "not installed"
   systemctl is-active soundbox-mcp 2>/dev/null || echo "not installed"
   ```
3. Check GPU: `nvidia-smi --query-gpu=name,memory.used,memory.total,temperature.gpu --format=csv,noheader 2>/dev/null || echo "No GPU detected"`
4. Check MCP server (stdio handshake):
   ```bash
   echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}' | timeout 5 ./venv/bin/python mcp_server.py 2>/dev/null | head -1
   ```

Output a summary table:
- Flask server: running/down (with model states)
- MCP server: responding/down
- Systemd services: active/inactive/not installed
- GPU: name, memory usage, temperature
- Queue: length and estimated wait
