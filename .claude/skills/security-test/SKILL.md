---
name: security-test
description: Verify the 6 security hardening measures from the MCP/discovery security audit
disable-model-invocation: true
allowed-tools: Bash
argument-hint: ""
---

## Security Audit Verification

Test all 6 security hardening measures. The server must be running on localhost:5309.

Run these checks and report PASS/FAIL for each:

### 1. MCP Proxy Detection (X-MCP-Proxy header)
```bash
# Manifest should NOT contain system user info when proxied
curl -s http://localhost:5309/status -H "X-MCP-Proxy: true" | python3 -c "import sys,json; print('PASS' if json.load(sys.stdin) else 'FAIL')"
```

### 2. Path Traversal Prevention (ID regex)
```bash
# MCP server should reject traversal attempts
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"check_job","arguments":{"job_id":"../../../etc/passwd"}},"id":2}' | timeout 5 ./venv/bin/python mcp_server.py 2>/dev/null | python3 -c "import sys,json; r=json.load(sys.stdin); print('PASS' if 'error' in str(r).lower() or 'invalid' in str(r).lower() else 'FAIL')"
```

### 3. Manifest Redaction
```bash
# Manifest should NOT contain hostname, gpu.name, or mcp_port
curl -s http://localhost:5309/api/manifest | python3 -c "
import sys, json
m = json.load(sys.stdin)
checks = []
checks.append('hostname' not in m)
checks.append('name' not in m.get('gpu', {}))
checks.append('mcp_port' not in m.get('discovery', {}))
print('PASS' if all(checks) else 'FAIL: ' + str(checks))
"
```

### 4. SSE Localhost Binding
```bash
# Verify MCP SSE binds to 127.0.0.1 (check source code)
grep -q 'mcp.settings.host.*=.*"127.0.0.1"' mcp_server.py && echo "PASS" || echo "FAIL"
```

### 5. Parameter Clamping
```bash
# MCP server should clamp duration to max 60
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"generate_audio","arguments":{"prompt":"test","duration":9999}},"id":2}' | timeout 10 ./venv/bin/python mcp_server.py 2>/dev/null | tail -1 | python3 -c "import sys,json; r=json.load(sys.stdin); print('PASS (clamped)' if r else 'FAIL')"
```

### 6. MCP_API_KEY Requirement
```bash
# Check that MCP_API_KEY guard exists in source
grep -q 'MCP_API_KEY' mcp_server.py && echo "PASS" || echo "FAIL"
```

Summarize results as a table: Check | Status | Details
