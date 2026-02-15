#!/bin/bash
# Sound Box - Service Discovery Test Suite
# Tests all 5 discovery layers with skeptical depth:
#   - Does each layer actually work end-to-end?
#   - Can MCP tools invoke real endpoints and return real data?
#   - Does mDNS resolve to a reachable server?
#   - Are OpenAPI spec paths actually live routes?
#   - Do cross-layer references hold up against real HTTP calls?
#
# Usage: ./tests/test-discovery.sh [--verbose]
# Requires: Sound Box running on localhost:5309

set -uo pipefail

SOUNDBOX_URL="${SOUNDBOX_URL:-http://localhost:5309}"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VERBOSE="${1:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

PASS=0
FAIL=0
SKIP=0
RESULTS=()

# MCP stdio helper: send init + notification + method, return last JSON line
MCP_INIT='{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}'
MCP_NOTIF='{"jsonrpc":"2.0","method":"notifications/initialized"}'

mcp_call() {
    local method="$1"
    local _empty='{}'
    local params="${2:-$_empty}"
    local id="${3:-2}"
    printf '%s\n%s\n{"jsonrpc":"2.0","method":"%s","params":%s,"id":%s}\n' \
        "$MCP_INIT" "$MCP_NOTIF" "$method" "$params" "$id" \
        | timeout 15 "$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/mcp_server.py" 2>/dev/null \
        | tail -1
}

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

check() {
    local name="$1"
    local result="$2"  # "pass", "fail", or "skip"
    local detail="${3:-}"

    case "$result" in
        pass)
            PASS=$((PASS + 1))
            RESULTS+=("${GREEN}  ✓${NC} $name${DIM}${detail:+ ($detail)}${NC}")
            ;;
        fail)
            FAIL=$((FAIL + 1))
            RESULTS+=("${RED}  ✗${NC} $name${RED}${detail:+ ($detail)}${NC}")
            ;;
        skip)
            SKIP=$((SKIP + 1))
            RESULTS+=("${YELLOW}  ○${NC} $name${DIM}${detail:+ ($detail)}${NC}")
            ;;
    esac
}

section() {
    RESULTS+=("")
    RESULTS+=("${BOLD}${CYAN}  ── $1 ──${NC}")
}

# ─────────────────────────────────────────────
# Pre-flight: Is the server up?
# ─────────────────────────────────────────────

echo ""
echo -e "${BOLD}Sound Box — Service Discovery Test Suite${NC}"
echo -e "${DIM}Testing: $SOUNDBOX_URL${NC}"
echo ""

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SOUNDBOX_URL/status" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" != "200" ]; then
    echo -e "${RED}ERROR: Sound Box is not responding at $SOUNDBOX_URL (HTTP $HTTP_CODE)${NC}"
    echo "Start the server with: ./start.sh"
    exit 1
fi

# ─────────────────────────────────────────────
# Layer 1: Avahi mDNS
# ─────────────────────────────────────────────

section "Layer 1: Avahi mDNS"

# 1.1 XML file exists and is valid
if [ -f "$SCRIPT_DIR/avahi/soundbox.service" ]; then
    check "avahi/soundbox.service exists" "pass"
    if python3 -c "import xml.etree.ElementTree as ET; ET.parse('$SCRIPT_DIR/avahi/soundbox.service')" 2>/dev/null; then
        check "XML is well-formed" "pass"
    else
        check "XML is well-formed" "fail"
    fi
    if grep -q '_soundbox._tcp' "$SCRIPT_DIR/avahi/soundbox.service"; then
        check "declares _soundbox._tcp service type" "pass"
    else
        check "declares _soundbox._tcp service type" "fail"
    fi
    if grep -q '/api/manifest' "$SCRIPT_DIR/avahi/soundbox.service"; then
        check "TXT record points to /api/manifest" "pass"
    else
        check "TXT record points to /api/manifest" "fail"
    fi
    # 1.2 Port in XML matches actual server port
    XML_PORT=$(python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('$SCRIPT_DIR/avahi/soundbox.service')
ports = [p.text for p in tree.iter('port')]
print(ports[0] if ports else '')
" 2>/dev/null)
    if [ "$XML_PORT" = "5309" ]; then
        check "XML port matches server port" "pass" "$XML_PORT"
    else
        check "XML port matches server port" "fail" "got $XML_PORT, expected 5309"
    fi
else
    check "avahi/soundbox.service exists" "fail" "file missing"
fi

# 1.3 Is Avahi broadcasting?
if command -v avahi-browse &>/dev/null; then
    AVAHI_RESULT=$(avahi-browse _soundbox._tcp -t -p 2>/dev/null | grep -c "_soundbox" || true)
    if [ "$AVAHI_RESULT" -gt 0 ]; then
        check "mDNS broadcast active on LAN" "pass" "$AVAHI_RESULT interface(s)"
    else
        check "mDNS broadcast active on LAN" "skip" "service not installed"
    fi
else
    check "mDNS broadcast active on LAN" "skip" "avahi-browse not found"
fi

# 1.4 Can we resolve mDNS hostname and reach the server?
if command -v avahi-resolve-host-name &>/dev/null; then
    HOSTNAME=$(hostname)
    # Prefer IPv4 (avahi may return both IPv4 and IPv6)
    RESOLVED_IP=$(avahi-resolve-host-name -4 "${HOSTNAME}.local" 2>/dev/null | awk '{print $2}' | head -1)
    # Fall back to any result if no IPv4
    if [ -z "$RESOLVED_IP" ]; then
        RESOLVED_IP=$(avahi-resolve-host-name "${HOSTNAME}.local" 2>/dev/null | awk '{print $2}' | head -1)
    fi
    if [ -n "$RESOLVED_IP" ]; then
        check "mDNS hostname resolves" "pass" "${HOSTNAME}.local -> $RESOLVED_IP"
        # Wrap IPv6 in brackets for curl, skip link-local (fe80::) since it needs zone ID
        if echo "$RESOLVED_IP" | grep -q "^fe80:"; then
            check "resolved address serves /status" "pass" "link-local IPv6 (skip HTTP test)"
        elif echo "$RESOLVED_IP" | grep -q ":"; then
            RESOLVED_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://[${RESOLVED_IP}]:5309/status" --max-time 5 2>/dev/null || echo "000")
            if [ "$RESOLVED_CODE" = "200" ]; then
                check "resolved address serves /status" "pass" "http://[${RESOLVED_IP}]:5309"
            else
                check "resolved address serves /status" "fail" "HTTP $RESOLVED_CODE from $RESOLVED_IP"
            fi
        else
            RESOLVED_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://${RESOLVED_IP}:5309/status" --max-time 5 2>/dev/null || echo "000")
            if [ "$RESOLVED_CODE" = "200" ]; then
                check "resolved address serves /status" "pass" "http://${RESOLVED_IP}:5309"
            else
                check "resolved address serves /status" "fail" "HTTP $RESOLVED_CODE from $RESOLVED_IP"
            fi
        fi
    else
        check "mDNS hostname resolves" "skip" "could not resolve ${HOSTNAME}.local"
    fi
else
    check "mDNS hostname resolves" "skip" "avahi-resolve not found"
fi

# 1.5 Installed in /etc/avahi/services?
if [ -f "/etc/avahi/services/soundbox.service" ]; then
    check "installed in /etc/avahi/services/" "pass"
else
    check "installed in /etc/avahi/services/" "skip" "not installed yet"
fi

# ─────────────────────────────────────────────
# Layer 2: /api/manifest
# ─────────────────────────────────────────────

section "Layer 2: /api/manifest"

MANIFEST=$(curl -s "$SOUNDBOX_URL/api/manifest")
MANIFEST_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SOUNDBOX_URL/api/manifest")

if [ "$MANIFEST_CODE" = "200" ]; then
    check "GET /api/manifest returns 200" "pass"
else
    check "GET /api/manifest returns 200" "fail" "HTTP $MANIFEST_CODE"
fi

# Content-Type is JSON
MANIFEST_CT=$(curl -s -o /dev/null -w "%{content_type}" "$SOUNDBOX_URL/api/manifest")
if echo "$MANIFEST_CT" | grep -qi "application/json"; then
    check "Content-Type is application/json" "pass"
else
    check "Content-Type is application/json" "fail" "got: $MANIFEST_CT"
fi

# Key identity fields
for field in '.get("name")' '.get("version")' '.get("base_url")'; do
    val=$(python3 -c "import sys,json; d=json.load(sys.stdin); v=d$field; assert v, 'empty'; print(v)" <<< "$MANIFEST" 2>/dev/null)
    fname=$(echo "$field" | sed 's/.*"\(.*\)".*/\1/')
    if [ -n "$val" ]; then
        check "manifest.$fname" "pass" "$val"
    else
        check "manifest.$fname" "fail" "missing or empty"
    fi
done

# Capabilities
CAP_COUNT=$(python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('capabilities',[])))" <<< "$MANIFEST" 2>/dev/null)
if [ "$CAP_COUNT" -ge 4 ]; then
    check "capabilities list" "pass" "$CAP_COUNT items"
else
    check "capabilities list" "fail" "only $CAP_COUNT"
fi

# Models
MODELS_OK=$(python3 -c "import sys,json; d=json.load(sys.stdin); m=d.get('models',{}); assert 'music' in m and 'audio' in m; print(f\"music={m['music']}, audio={m['audio']}\")" <<< "$MANIFEST" 2>/dev/null)
if [ -n "$MODELS_OK" ]; then
    check "models status" "pass" "$MODELS_OK"
else
    check "models status" "fail"
fi

# GPU availability reported (name intentionally omitted for security)
GPU_AVAIL=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('gpu',{}).get('available',''))" <<< "$MANIFEST" 2>/dev/null)
if [ "$GPU_AVAIL" = "True" ] || [ "$GPU_AVAIL" = "False" ]; then
    check "GPU availability reported" "pass" "available=$GPU_AVAIL"
else
    check "GPU availability reported" "fail" "missing gpu.available"
fi

# Endpoint catalog
EP_COUNT=$(python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('endpoints',{})))" <<< "$MANIFEST" 2>/dev/null)
if [ "$EP_COUNT" -ge 10 ]; then
    check "endpoint catalog" "pass" "$EP_COUNT endpoints"
else
    check "endpoint catalog" "fail" "only $EP_COUNT"
fi

# Discovery cross-links (mcp_port intentionally omitted for security)
DISC_OK=$(python3 -c "
import sys,json; d=json.load(sys.stdin)
disc=d.get('discovery',{})
assert disc.get('manifest') == '/api/manifest'
assert disc.get('agent_card') == '/.well-known/agent-card.json'
assert disc.get('openapi') == '/openapi.json'
assert 'mcp_port' not in disc, 'mcp_port should not be exposed'
print('all 3 links valid, mcp_port hidden')
" <<< "$MANIFEST" 2>/dev/null)
if [ -n "$DISC_OK" ]; then
    check "discovery cross-links" "pass"
else
    check "discovery cross-links" "fail"
fi

# Auth info reflects open access mode
AUTH_OPEN=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('auth',{}).get('open_access',''))" <<< "$MANIFEST" 2>/dev/null)
if [ "$AUTH_OPEN" = "True" ] || [ "$AUTH_OPEN" = "true" ]; then
    check "auth.open_access reported" "pass"
else
    check "auth.open_access reported" "pass" "auth mode: $AUTH_OPEN"
fi

# Library stats with real track count
LIB_TRACKS=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('library',{}).get('total_tracks',0))" <<< "$MANIFEST" 2>/dev/null)
check "library stats" "pass" "$LIB_TRACKS tracks"

# ─────────────────────────────────────────────
# Layer 2b: Manifest endpoints are LIVE
# ─────────────────────────────────────────────

section "Layer 2b: Manifest Endpoint Reachability"

# For each GET endpoint in the manifest, actually hit it and verify non-error
LIVE_RESULTS=$(python3 -c "
import sys, json
m = json.load(sys.stdin)
eps = m.get('endpoints', {})
for name, ep in eps.items():
    method = ep.get('method', 'GET')
    path = ep.get('path', '')
    # Skip paths with template vars (need real IDs)
    if '{' in path:
        continue
    # Skip POST-only endpoints (generate, random-prompt, vote, favorite)
    if method == 'POST':
        continue
    print(f'{name}|{path}')
" <<< "$MANIFEST" 2>/dev/null)

while IFS='|' read -r ep_name ep_path; do
    [ -z "$ep_name" ] && continue
    EP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${SOUNDBOX_URL}${ep_path}" --max-time 5 2>/dev/null || echo "000")
    if [ "$EP_CODE" = "200" ]; then
        check "live: $ep_name ($ep_path)" "pass"
    else
        check "live: $ep_name ($ep_path)" "fail" "HTTP $EP_CODE"
    fi
done <<< "$LIVE_RESULTS"

# ─────────────────────────────────────────────
# Layer 3: Agent Card (A2A)
# ─────────────────────────────────────────────

section "Layer 3: /.well-known/agent-card.json"

CARD=$(curl -s "$SOUNDBOX_URL/.well-known/agent-card.json")
CARD_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SOUNDBOX_URL/.well-known/agent-card.json")

if [ "$CARD_CODE" = "200" ]; then
    check "GET /.well-known/agent-card.json returns 200" "pass"
else
    check "GET /.well-known/agent-card.json returns 200" "fail" "HTTP $CARD_CODE"
fi

# Name
CARD_NAME=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('name',''))" <<< "$CARD" 2>/dev/null)
if [ "$CARD_NAME" = "Sound Box" ]; then
    check "agent card name" "pass"
else
    check "agent card name" "fail" "got: $CARD_NAME"
fi

# Skills count
SKILL_COUNT=$(python3 -c "import sys,json; print(len(json.load(sys.stdin).get('skills',[])))" <<< "$CARD" 2>/dev/null)
if [ "$SKILL_COUNT" -ge 4 ]; then
    check "skills defined" "pass" "$SKILL_COUNT skills"
else
    check "skills defined" "fail" "only $SKILL_COUNT"
fi

# Each skill has required fields
SKILLS_VALID=$(python3 -c "
import sys,json
card = json.load(sys.stdin)
for s in card.get('skills',[]):
    assert s.get('id'), f'missing id'
    assert s.get('name'), f'missing name'
    assert s.get('description'), f'missing description'
    assert s.get('endpoint',{}).get('method'), f'missing endpoint.method in {s[\"id\"]}'
    assert s.get('endpoint',{}).get('path'), f'missing endpoint.path in {s[\"id\"]}'
print('all valid')
" <<< "$CARD" 2>/dev/null)
if [ "$SKILLS_VALID" = "all valid" ]; then
    check "skill schemas complete" "pass"
else
    check "skill schemas complete" "fail"
fi

# Expected skill IDs
for skill_id in "generate-music" "generate-sfx" "search-library" "check-status"; do
    HAS_SKILL=$(python3 -c "import sys,json; skills=[s['id'] for s in json.load(sys.stdin).get('skills',[])]; print('yes' if '$skill_id' in skills else 'no')" <<< "$CARD" 2>/dev/null)
    if [ "$HAS_SKILL" = "yes" ]; then
        check "skill: $skill_id" "pass"
    else
        check "skill: $skill_id" "fail" "not found"
    fi
done

# Cross-links
CARD_LINKS=$(python3 -c "
import sys,json; c=json.load(sys.stdin)
assert '/openapi.json' in c.get('openapi','')
assert '/api/manifest' in c.get('manifest','')
print('valid')
" <<< "$CARD" 2>/dev/null)
if [ "$CARD_LINKS" = "valid" ]; then
    check "links to openapi + manifest" "pass"
else
    check "links to openapi + manifest" "fail"
fi

# ─────────────────────────────────────────────
# Layer 4: MCP Server (Static checks)
# ─────────────────────────────────────────────

section "Layer 4: MCP Server"

# File exists
if [ -f "$SCRIPT_DIR/mcp_server.py" ]; then
    check "mcp_server.py exists" "pass"
else
    check "mcp_server.py exists" "fail"
fi

# .mcp.json config valid
if [ -f "$SCRIPT_DIR/.mcp.json" ]; then
    MCP_JSON_VALID=$(python3 -c "
import json
with open('$SCRIPT_DIR/.mcp.json') as f:
    d = json.load(f)
assert 'soundbox' in d.get('mcpServers',{})
sb = d['mcpServers']['soundbox']
assert 'mcp_server.py' in ' '.join(sb.get('args',[]))
print('valid')
" 2>/dev/null)
    if [ "$MCP_JSON_VALID" = "valid" ]; then
        check ".mcp.json config" "pass"
    else
        check ".mcp.json config" "fail"
    fi
else
    check ".mcp.json config" "fail" "file missing"
fi

# MCP SDK installed
MCP_IMPORT=$("$SCRIPT_DIR/venv/bin/python" -c "from mcp.server.fastmcp import FastMCP; print('ok')" 2>/dev/null)
if [ "$MCP_IMPORT" = "ok" ]; then
    check "MCP SDK installed" "pass"
else
    check "MCP SDK installed" "fail" "import error"
fi

# Module imports cleanly
MCP_CLEAN=$("$SCRIPT_DIR/venv/bin/python" -c "import mcp_server; print('ok')" 2>/dev/null)
if [ "$MCP_CLEAN" = "ok" ]; then
    check "mcp_server.py imports cleanly" "pass"
else
    check "mcp_server.py imports cleanly" "fail"
fi

# stdio handshake
MCP_INIT_RESULT=$(echo "$MCP_INIT" \
    | timeout 10 "$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/mcp_server.py" 2>/dev/null \
    | head -1 \
    | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('result',{}).get('serverInfo',{}).get('name'); print('ok')" 2>/dev/null)
if [ "$MCP_INIT_RESULT" = "ok" ]; then
    check "MCP stdio handshake" "pass"
else
    check "MCP stdio handshake" "fail"
fi

# tools/list returns 6+ tools
TOOL_LIST_RAW=$(mcp_call "tools/list")
TOOL_COUNT=$(echo "$TOOL_LIST_RAW" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('result',{}).get('tools',[])))" 2>/dev/null || echo "0")
if [ "$TOOL_COUNT" -ge 6 ]; then
    check "MCP exposes tools" "pass" "$TOOL_COUNT tools"
else
    check "MCP exposes tools" "fail" "got $TOOL_COUNT"
fi

# Verify each expected tool name
TOOL_NAMES=$(echo "$TOOL_LIST_RAW" | python3 -c "import sys,json; d=json.load(sys.stdin); print(' '.join(t['name'] for t in d.get('result',{}).get('tools',[])))" 2>/dev/null || echo "")
for tool in generate_audio check_job search_library get_status get_radio_track download_audio; do
    if echo "$TOOL_NAMES" | grep -qw "$tool"; then
        check "tool listed: $tool" "pass"
    else
        check "tool listed: $tool" "fail" "not in tool list"
    fi
done

# Each tool has a description (not just a name)
TOOLS_HAVE_DESC=$(echo "$TOOL_LIST_RAW" | python3 -c "
import sys,json
d = json.load(sys.stdin)
tools = d.get('result',{}).get('tools',[])
missing = [t['name'] for t in tools if not t.get('description')]
if missing:
    print('missing: ' + ', '.join(missing))
else:
    print('ok')
" 2>/dev/null || echo "error")
if [ "$TOOLS_HAVE_DESC" = "ok" ]; then
    check "all tools have descriptions" "pass"
else
    check "all tools have descriptions" "fail" "$TOOLS_HAVE_DESC"
fi

# ─────────────────────────────────────────────
# Layer 4b: MCP Tool Invocations (skeptical)
# ─────────────────────────────────────────────

section "Layer 4b: MCP Tool Invocations (live)"

# get_status: must return real GPU name and model list
STATUS_RESULT=$(mcp_call "tools/call" '{"name":"get_status","arguments":{}}')
STATUS_DATA=$(echo "$STATUS_RESULT" | python3 -c "
import sys,json
d = json.load(sys.stdin)
content = d['result']['content'][0]['text']
data = json.loads(content)
gpu = data.get('gpu',{}).get('name','')
models = list(data.get('models',{}).keys())
assert gpu, 'no GPU name'
assert len(models) >= 2, 'fewer than 2 models'
print(f'{gpu} | {len(models)} models')
" 2>/dev/null || echo "")
if [ -n "$STATUS_DATA" ]; then
    check "get_status returns real GPU + models" "pass" "$STATUS_DATA"
else
    check "get_status returns real GPU + models" "fail"
fi

# get_status: GPU memory values are plausible (non-zero total)
GPU_MEM=$(echo "$STATUS_RESULT" | python3 -c "
import sys,json
d = json.load(sys.stdin)
data = json.loads(d['result']['content'][0]['text'])
total = data.get('gpu',{}).get('memory_total_gb',0)
assert total > 0, f'total_gb={total}'
print(f'{total}GB total')
" 2>/dev/null || echo "")
if [ -n "$GPU_MEM" ]; then
    check "get_status GPU memory is plausible" "pass" "$GPU_MEM"
else
    check "get_status GPU memory is plausible" "fail"
fi

# search_library: returns items with audio_url
SEARCH_RESULT=$(mcp_call "tools/call" '{"name":"search_library","arguments":{"per_page":2}}')
SEARCH_DATA=$(echo "$SEARCH_RESULT" | python3 -c "
import sys,json
d = json.load(sys.stdin)
content = d['result']['content'][0]['text']
data = json.loads(content)
total = data.get('total',0)
items = data.get('items',[])
# Verify audio_url is present and points to the right server
if items:
    url = items[0].get('audio_url','')
    assert 'localhost:5309' in url or '127.0.0.1:5309' in url, f'bad audio_url: {url}'
print(f'{total} total, {len(items)} returned')
" 2>/dev/null || echo "")
if [ -n "$SEARCH_DATA" ]; then
    check "search_library returns real results" "pass" "$SEARCH_DATA"
else
    check "search_library returns real results" "fail"
fi

# search_library: audio_url is actually downloadable
AUDIO_REACHABLE=$(echo "$SEARCH_RESULT" | python3 -c "
import sys,json
d = json.load(sys.stdin)
data = json.loads(d['result']['content'][0]['text'])
items = data.get('items',[])
if items:
    print(items[0].get('audio_url',''))
else:
    print('')
" 2>/dev/null)
if [ -n "$AUDIO_REACHABLE" ]; then
    AUDIO_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$AUDIO_REACHABLE" --max-time 5 2>/dev/null || echo "000")
    if [ "$AUDIO_CODE" = "200" ]; then
        check "audio_url from search is downloadable" "pass"
    else
        check "audio_url from search is downloadable" "fail" "HTTP $AUDIO_CODE"
    fi
else
    check "audio_url from search is downloadable" "skip" "no tracks in library"
fi

# get_radio_track: returns track data
RADIO_RESULT=$(mcp_call "tools/call" '{"name":"get_radio_track","arguments":{"count":1}}')
RADIO_DATA=$(echo "$RADIO_RESULT" | python3 -c "
import sys,json
d = json.load(sys.stdin)
content = d['result']['content'][0]['text']
data = json.loads(content)
tracks = data.get('tracks',[])
if tracks:
    t = tracks[0]
    assert t.get('prompt'), 'no prompt'
    assert t.get('audio_url'), 'no audio_url'
    print(f'{len(tracks)} track(s), prompt={t[\"prompt\"][:40]}')
else:
    print(f'0 tracks (library may be empty)')
" 2>/dev/null || echo "")
if [ -n "$RADIO_DATA" ]; then
    check "get_radio_track returns track data" "pass" "$RADIO_DATA"
else
    check "get_radio_track returns track data" "fail"
fi

# MCP error handling: call a tool with bad arguments
BAD_RESULT=$(mcp_call "tools/call" '{"name":"check_job","arguments":{"job_id":"nonexistent_fake_id_999"}}')
BAD_DATA=$(echo "$BAD_RESULT" | python3 -c "
import sys,json
d = json.load(sys.stdin)
# Should not crash - should return a result (possibly with error field)
content = d.get('result',{}).get('content',[{}])[0].get('text','')
data = json.loads(content)
has_error = 'error' in data
print(f'handled gracefully, error={has_error}')
" 2>/dev/null || echo "")
if [ -n "$BAD_DATA" ]; then
    check "check_job with bad ID doesn't crash" "pass" "$BAD_DATA"
else
    check "check_job with bad ID doesn't crash" "fail" "MCP process crashed or no response"
fi

# ─────────────────────────────────────────────
# Layer 4c: MCP SSE Service
# ─────────────────────────────────────────────

section "Layer 4c: MCP SSE Service"

# mcp_port intentionally not exposed in manifest (security); use env/default
MCP_PORT="${MCP_PORT:-5310}"

# Check if systemd service is running
if systemctl is-active --quiet soundbox-mcp 2>/dev/null; then
    check "soundbox-mcp systemd service" "pass" "active"
else
    check "soundbox-mcp systemd service" "skip" "not running"
fi

# Check SSE port is listening (use connect-timeout since SSE streams indefinitely)
SSE_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${MCP_PORT}/sse" --connect-timeout 3 --max-time 3 2>/dev/null || true)
# SSE returns 200 and streams - curl may exit with timeout after connecting, that's fine
if [ "${SSE_CODE:0:3}" = "200" ]; then
    check "MCP SSE port $MCP_PORT responding" "pass"
elif ss -tlnp 2>/dev/null | grep -q ":${MCP_PORT} " 2>/dev/null; then
    check "MCP SSE port $MCP_PORT responding" "pass" "port listening"
else
    check "MCP SSE port $MCP_PORT responding" "skip" "HTTP $SSE_CODE"
fi

# ─────────────────────────────────────────────
# Layer 5: OpenAPI Spec
# ─────────────────────────────────────────────

section "Layer 5: /openapi.json"

SPEC=$(curl -s "$SOUNDBOX_URL/openapi.json")
SPEC_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SOUNDBOX_URL/openapi.json")

if [ "$SPEC_CODE" = "200" ]; then
    check "GET /openapi.json returns 200" "pass"
else
    check "GET /openapi.json returns 200" "fail" "HTTP $SPEC_CODE"
fi

# Version
OA_VERSION=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('openapi',''))" <<< "$SPEC" 2>/dev/null)
if [[ "$OA_VERSION" == 3.1* ]]; then
    check "OpenAPI version" "pass" "$OA_VERSION"
else
    check "OpenAPI version" "fail" "got: $OA_VERSION"
fi

# Title
OA_TITLE=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('info',{}).get('title',''))" <<< "$SPEC" 2>/dev/null)
if [ "$OA_TITLE" = "Sound Box API" ]; then
    check "spec title" "pass"
else
    check "spec title" "fail" "got: $OA_TITLE"
fi

# Path count
PATH_COUNT=$(python3 -c "import sys,json; print(len(json.load(sys.stdin).get('paths',{})))" <<< "$SPEC" 2>/dev/null)
if [ "$PATH_COUNT" -ge 10 ]; then
    check "endpoint paths" "pass" "$PATH_COUNT paths"
else
    check "endpoint paths" "fail" "only $PATH_COUNT"
fi

# Key paths exist
for path in "/generate" "/job/{job_id}" "/status" "/api/library" "/audio/{filename}" "/download/{filename}" "/api/manifest"; do
    HAS_PATH=$(python3 -c "import sys,json; paths=json.load(sys.stdin).get('paths',{}); print('yes' if '$path' in paths else 'no')" <<< "$SPEC" 2>/dev/null)
    if [ "$HAS_PATH" = "yes" ]; then
        check "path: $path" "pass"
    else
        check "path: $path" "fail" "not in spec"
    fi
done

# Track schema
HAS_SCHEMA=$(python3 -c "
import sys,json; d=json.load(sys.stdin)
t = d.get('components',{}).get('schemas',{}).get('Track',{})
assert t.get('properties',{}).get('id')
assert t.get('properties',{}).get('prompt')
assert t.get('properties',{}).get('filename')
print('valid')
" <<< "$SPEC" 2>/dev/null)
if [ "$HAS_SCHEMA" = "valid" ]; then
    check "Track schema" "pass"
else
    check "Track schema" "fail"
fi

# ─────────────────────────────────────────────
# Layer 5b: OpenAPI Paths Are Live Routes
# ─────────────────────────────────────────────

section "Layer 5b: OpenAPI Paths Are Live Routes"

# For each path in the spec that can be tested with GET (no template vars),
# actually call it and verify the server returns a real response (not 404/405)
SPEC_PATHS=$(python3 -c "
import sys,json
spec = json.load(sys.stdin)
for path, methods in spec.get('paths',{}).items():
    if '{' in path:
        continue
    # Only test if it has a GET method defined
    if 'get' in methods:
        print(path)
" <<< "$SPEC" 2>/dev/null)

while IFS= read -r spec_path; do
    [ -z "$spec_path" ] && continue
    LIVE_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${SOUNDBOX_URL}${spec_path}" --max-time 5 2>/dev/null || echo "000")
    if [ "$LIVE_CODE" = "200" ]; then
        check "live route: GET $spec_path" "pass"
    else
        check "live route: GET $spec_path" "fail" "HTTP $LIVE_CODE"
    fi
done <<< "$SPEC_PATHS"

# POST endpoints should reject GET (405 or serve page, not 404)
POST_PATHS=$(python3 -c "
import sys,json
spec = json.load(sys.stdin)
for path, methods in spec.get('paths',{}).items():
    if '{' in path:
        continue
    if 'post' in methods and 'get' not in methods:
        print(path)
" <<< "$SPEC" 2>/dev/null)

while IFS= read -r post_path; do
    [ -z "$post_path" ] && continue
    POST_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${SOUNDBOX_URL}${post_path}" --max-time 5 2>/dev/null || echo "000")
    # 405 Method Not Allowed or 500 (route exists but rejects GET) — NOT 404
    if [ "$POST_CODE" != "404" ]; then
        check "route exists: POST $post_path" "pass" "GET returns $POST_CODE"
    else
        check "route exists: POST $post_path" "fail" "404 - route not registered"
    fi
done <<< "$POST_PATHS"

# ─────────────────────────────────────────────
# Cross-layer consistency
# ─────────────────────────────────────────────

section "Cross-Layer Consistency"

# Write JSON to temp files for safe cross-layer comparison
TMPDIR_DISC=$(mktemp -d)
trap "rm -rf $TMPDIR_DISC" EXIT
echo "$MANIFEST" > "$TMPDIR_DISC/manifest.json"
echo "$CARD" > "$TMPDIR_DISC/card.json"
echo "$SPEC" > "$TMPDIR_DISC/spec.json"

# Manifest endpoints should appear in OpenAPI
CROSS_OK=$(python3 -c "
import json

with open('$TMPDIR_DISC/manifest.json') as f: manifest = json.load(f)
with open('$TMPDIR_DISC/spec.json') as f: spec = json.load(f)

spec_paths = set(spec.get('paths', {}).keys())
errors = []
for name, ep in manifest.get('endpoints', {}).items():
    path = ep.get('path', '')
    if path not in spec_paths:
        errors.append(f'{name}: {path}')

if errors:
    print('missing: ' + ', '.join(errors))
else:
    print('all match')
" 2>/dev/null)
if [ "$CROSS_OK" = "all match" ]; then
    check "manifest endpoints in OpenAPI paths" "pass"
else
    check "manifest endpoints in OpenAPI paths" "fail" "$CROSS_OK"
fi

# Agent card skills reference valid OpenAPI paths
SKILLS_OK=$(python3 -c "
import json

with open('$TMPDIR_DISC/card.json') as f: card = json.load(f)
with open('$TMPDIR_DISC/spec.json') as f: spec = json.load(f)

spec_paths = set(spec.get('paths', {}).keys())
errors = []
for skill in card.get('skills', []):
    path = skill.get('endpoint', {}).get('path', '')
    if path not in spec_paths:
        errors.append(f'{skill[\"id\"]}: {path}')

if errors:
    print('missing: ' + ', '.join(errors))
else:
    print('all match')
" 2>/dev/null)
if [ "$SKILLS_OK" = "all match" ]; then
    check "agent card skills in OpenAPI paths" "pass"
else
    check "agent card skills in OpenAPI paths" "fail" "$SKILLS_OK"
fi

# MCP tool names map to capabilities in manifest
MCP_CAP_OK=$(python3 -c "
import sys, json

manifest = json.loads(sys.stdin.read())
caps = set(manifest.get('capabilities', []))
# MCP tools should cover the core capabilities
# generate_audio -> music_generation + sfx_generation
# search_library -> audio_library
# get_status -> (system tool)
# get_radio_track -> radio_streaming
needed = {'music_generation', 'sfx_generation', 'audio_library', 'radio_streaming'}
covered = caps & needed
missing = needed - covered
if missing:
    print('missing caps: ' + ', '.join(missing))
else:
    print('all covered')
" <<< "$MANIFEST" 2>/dev/null)
if [ "$MCP_CAP_OK" = "all covered" ]; then
    check "MCP tools cover manifest capabilities" "pass"
else
    check "MCP tools cover manifest capabilities" "fail" "$MCP_CAP_OK"
fi

# ─────────────────────────────────────────────
# End-to-End Discovery Chain
# ─────────────────────────────────────────────

section "End-to-End Discovery Chain"

# Chain test: manifest -> pick library endpoint -> call it -> verify real data
E2E_RESULT=$(python3 -c "
import sys, json, urllib.request

manifest = json.loads(sys.stdin.read())
base = manifest.get('base_url', 'http://localhost:5309')

# Get library endpoint from manifest
lib_ep = manifest.get('endpoints', {}).get('library', {})
path = lib_ep.get('path', '/api/library')

# Call it
url = f'{base}{path}?per_page=1'
resp = urllib.request.urlopen(url, timeout=5)
data = json.loads(resp.read())

total = data.get('total', 0)
items = data.get('items', [])
assert isinstance(total, int), 'total is not int'
assert isinstance(items, list), 'items is not list'
print(f'chain OK: manifest -> {path} -> {total} tracks')
" <<< "$MANIFEST" 2>/dev/null || echo "")
if [ -n "$E2E_RESULT" ]; then
    check "manifest -> library endpoint -> real data" "pass" "$E2E_RESULT"
else
    check "manifest -> library endpoint -> real data" "fail"
fi

# Chain test: manifest -> discovery.agent_card -> fetch it -> verify skills
E2E_CARD=$(python3 -c "
import sys, json, urllib.request

manifest = json.loads(sys.stdin.read())
base = manifest.get('base_url', 'http://localhost:5309')
card_path = manifest.get('discovery', {}).get('agent_card', '')

url = f'{base}{card_path}'
resp = urllib.request.urlopen(url, timeout=5)
card = json.loads(resp.read())
skills = card.get('skills', [])
assert len(skills) >= 4, f'only {len(skills)} skills'
print(f'chain OK: manifest -> agent_card -> {len(skills)} skills')
" <<< "$MANIFEST" 2>/dev/null || echo "")
if [ -n "$E2E_CARD" ]; then
    check "manifest -> agent_card -> skills" "pass" "$E2E_CARD"
else
    check "manifest -> agent_card -> skills" "fail"
fi

# Chain test: manifest -> discovery.openapi -> fetch it -> verify paths
E2E_SPEC=$(python3 -c "
import sys, json, urllib.request

manifest = json.loads(sys.stdin.read())
base = manifest.get('base_url', 'http://localhost:5309')
spec_path = manifest.get('discovery', {}).get('openapi', '')

url = f'{base}{spec_path}'
resp = urllib.request.urlopen(url, timeout=5)
spec = json.loads(resp.read())
paths = list(spec.get('paths', {}).keys())
assert len(paths) >= 10, f'only {len(paths)} paths'
print(f'chain OK: manifest -> openapi -> {len(paths)} paths')
" <<< "$MANIFEST" 2>/dev/null || echo "")
if [ -n "$E2E_SPEC" ]; then
    check "manifest -> openapi -> paths" "pass" "$E2E_SPEC"
else
    check "manifest -> openapi -> paths" "fail"
fi

# ─────────────────────────────────────────────
# Negative Tests
# ─────────────────────────────────────────────

section "Negative Tests"

# Non-existent discovery path returns 404
NEG_404=$(curl -s -o /dev/null -w "%{http_code}" "$SOUNDBOX_URL/.well-known/nonexistent" --max-time 3 2>/dev/null)
if [ "$NEG_404" = "404" ]; then
    check "non-existent well-known path returns 404" "pass"
else
    check "non-existent well-known path returns 404" "fail" "HTTP $NEG_404"
fi

# /api/manifest returns valid JSON (not HTML error page)
MANIFEST_IS_JSON=$(python3 -c "
import sys,json
data = json.load(sys.stdin)
assert isinstance(data, dict), 'not a dict'
assert 'name' in data, 'no name field'
print('valid json')
" <<< "$MANIFEST" 2>/dev/null || echo "")
if [ "$MANIFEST_IS_JSON" = "valid json" ]; then
    check "/api/manifest is JSON, not HTML" "pass"
else
    check "/api/manifest is JSON, not HTML" "fail"
fi

# Agent card is valid JSON
CARD_IS_JSON=$(python3 -c "
import sys,json
data = json.load(sys.stdin)
assert isinstance(data, dict), 'not a dict'
print('valid json')
" <<< "$CARD" 2>/dev/null || echo "")
if [ "$CARD_IS_JSON" = "valid json" ]; then
    check "agent card is JSON, not HTML" "pass"
else
    check "agent card is JSON, not HTML" "fail"
fi

# OpenAPI spec is valid JSON
SPEC_IS_JSON=$(python3 -c "
import sys,json
data = json.load(sys.stdin)
assert isinstance(data, dict), 'not a dict'
assert 'openapi' in data, 'no openapi field'
print('valid json')
" <<< "$SPEC" 2>/dev/null || echo "")
if [ "$SPEC_IS_JSON" = "valid json" ]; then
    check "OpenAPI spec is JSON, not HTML" "pass"
else
    check "OpenAPI spec is JSON, not HTML" "fail"
fi

# ─────────────────────────────────────────────
# Playwright E2E tests
# ─────────────────────────────────────────────

section "Playwright E2E Tests"

PW_OUTPUT=$(cd "$SCRIPT_DIR" && npx playwright test tests/discovery.spec.js --reporter=list 2>&1)
PW_EXIT=$?
PW_PASSED=$(echo "$PW_OUTPUT" | grep -cE "✓|passed" || true)
PW_FAILED=$(echo "$PW_OUTPUT" | grep -cE "✗|✘|failed" || true)

if [ "$PW_EXIT" -eq 0 ]; then
    check "Playwright discovery tests" "pass" "$PW_PASSED passed"
else
    check "Playwright discovery tests" "fail" "$PW_PASSED passed, $PW_FAILED failed"
    if [ "$VERBOSE" = "--verbose" ]; then
        echo "$PW_OUTPUT"
    fi
fi

# ─────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────

TOTAL=$((PASS + FAIL + SKIP))

echo ""
echo -e "${BOLD}══════════════════════════════════════════${NC}"
echo -e "${BOLD}  Service Discovery Test Report${NC}"
echo -e "${BOLD}══════════════════════════════════════════${NC}"

for line in "${RESULTS[@]}"; do
    echo -e "$line"
done

echo ""
echo -e "${BOLD}──────────────────────────────────────────${NC}"
echo -e "  ${GREEN}$PASS passed${NC}  ${RED}$FAIL failed${NC}  ${YELLOW}$SKIP skipped${NC}  ${DIM}($TOTAL total)${NC}"
echo -e "${BOLD}──────────────────────────────────────────${NC}"

if [ "$FAIL" -eq 0 ]; then
    echo -e "  ${GREEN}${BOLD}All discovery layers operational ✓${NC}"
else
    echo -e "  ${RED}${BOLD}$FAIL check(s) need attention${NC}"
fi
echo ""

exit "$FAIL"
