#!/bin/bash
# ============================================================================
# Sound Box - Claude Code Integration Installer
# ============================================================================
# Installs the global /soundbox-generate skill and shows how to add MCP
# config to your other projects.
#
# Usage:
#   ./install-claude-skill.sh          # Install skill + show MCP setup
#   ./install-claude-skill.sh --remove # Remove skill
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$HOME/.claude/skills/soundbox-generate"
MCP_SNIPPET_FILE="$SCRIPT_DIR/.mcp-external.json"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

# --remove flag
if [ "$1" = "--remove" ] || [ "$1" = "uninstall" ]; then
    if [ -d "$SKILL_DIR" ]; then
        rm -rf "$SKILL_DIR"
        echo -e "${GREEN}Removed global skill: /soundbox-generate${NC}"
    else
        echo "Skill not installed."
    fi
    exit 0
fi

echo -e "${BOLD}Sound Box — Claude Code Integration Installer${NC}"
echo ""

# ── 1. Install global skill ──────────────────────────────────────────────────

mkdir -p "$SKILL_DIR"
cat > "$SKILL_DIR/SKILL.md" << 'SKILL_EOF'
---
name: soundbox-generate
description: Generate music, sound effects, or speech using the Sound Box AI audio server
disable-model-invocation: true
allowed-tools: Bash
argument-hint: "<prompt> [--model music|audio|tts] [--duration N] [--voice VOICE]"
---

## Generate Audio with Sound Box

Generate music, sound effects, or speech from a text prompt using the Sound Box AI server at localhost:5309.

Parse `$ARGUMENTS` for:
- **prompt** (required) - Text description (music/SFX) or text to speak (TTS). Everything before any `--` flags.
- **--model** (optional) - `music` (MusicGen), `audio` (AudioGen/SFX), or `tts` (Piper speech). Default: `music`
- **--duration** (optional) - Seconds, 1-60. For music/audio only. Default: `8`
- **--voice** (optional) - TTS voice ID. Default: `en_US-lessac-medium`. Available: en_US-lessac-medium, en_US-amy-medium, en_US-joe-medium, en_US-ryan-medium, en_GB-alan-medium, en_GB-alba-medium

If no arguments are provided, ask the user what they'd like to generate.

### Examples
- `/soundbox-generate cinematic orchestral trailer music` → music, 8s
- `/soundbox-generate thunder rolling across a valley --model audio --duration 12` → sfx, 12s
- `/soundbox-generate Hello world, this is a test --model tts` → speech
- `/soundbox-generate Welcome to the game --model tts --voice en_GB-alan-medium` → speech (British male)
- `/soundbox-generate UI button click --model audio --duration 2` → sfx, 2s

### Steps

1. **Check server**: `curl -sf http://localhost:5309/status | python3 -c "import sys,json; s=json.load(sys.stdin); print(f'GPU: {s[\"gpu\"][\"name\"]} | Models: {s[\"models\"]}')" 2>/dev/null || echo "ERROR: Sound Box not running on localhost:5309"`
   - If server is not running, tell the user: `sudo systemctl start soundbox`
   - If the needed model is not ready, report the model status and wait

2. **Submit generation**:

   For music or audio (model=music or model=audio):
   ```bash
   curl -s -X POST http://localhost:5309/generate \
     -H "Content-Type: application/json" \
     -d '{"prompt": "<prompt>", "model": "<model>", "duration": <duration>}'
   ```
   Then poll `http://localhost:5309/job/<job_id>` every 3 seconds until complete. Timeout after 120s.

   For TTS (model=tts):
   ```bash
   curl -s -X POST http://localhost:5309/api/tts/generate \
     -H "Content-Type: application/json" \
     -d '{"text": "<prompt>", "voice_id": "<voice>"}'
   ```
   TTS returns immediately (no polling needed).

3. **Report result**:
   - Success: prompt, model, duration/voice, and the URL `http://localhost:5309/audio/<filename>`
   - Failure: error message

### Prompt Tips

**Music** (model: music):
- Include genre + mood + instruments: "upbeat electronic dance music with synth arpeggios"
- Genres: jazz, electronic, orchestral, lo-fi, ambient, rock, classical, hip-hop

**Sound Effects** (model: audio):
- Be specific: "heavy rain on a tin roof with distant thunder"
- Include environment: indoor, outdoor, underwater, space

**Speech** (model: tts):
- Just write the text to speak naturally
- Voices: lessac (US neutral), amy (US female), joe (US male), ryan (US male), alan (GB male), alba (GB female)
SKILL_EOF

echo -e "${GREEN}Installed global skill:${NC} /soundbox-generate"
echo "  Location: $SKILL_DIR/SKILL.md"
echo ""

# ── 2. Generate .mcp-external.json with absolute paths ──────────────────────

VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"
MCP_SCRIPT="$SCRIPT_DIR/mcp_server.py"

cat > "$MCP_SNIPPET_FILE" << EOF
{
  "mcpServers": {
    "soundbox": {
      "command": "$VENV_PYTHON",
      "args": ["$MCP_SCRIPT"],
      "env": {"SOUNDBOX_URL": "http://localhost:5309"}
    }
  }
}
EOF

echo -e "${GREEN}Generated MCP config:${NC} $MCP_SNIPPET_FILE"
echo ""

# ── 3. Show instructions ────────────────────────────────────────────────────

echo -e "${BOLD}${CYAN}How to use from other projects:${NC}"
echo ""
echo -e "${BOLD}Option A: Skill only (no MCP tools)${NC}"
echo "  The /soundbox-generate skill is now globally available."
echo "  Just type in any Claude Code session:"
echo ""
echo -e "    ${CYAN}/soundbox-generate epic orchestral music --duration 15${NC}"
echo -e "    ${CYAN}/soundbox-generate rain on a window --model audio${NC}"
echo ""
echo -e "${BOLD}Option B: Full MCP tools (recommended)${NC}"
echo "  Copy .mcp-external.json into your project as .mcp.json:"
echo ""
echo -e "    ${CYAN}cp $MCP_SNIPPET_FILE /path/to/your-project/.mcp.json${NC}"
echo ""
echo "  This gives Claude all 6 Sound Box tools (generate, search, status, etc.)."
echo "  Restart Claude Code after adding .mcp.json."
echo ""
echo -e "${BOLD}Option C: Add CLAUDE.md snippet${NC}"
echo "  Add this to your project's CLAUDE.md for better AI context:"
echo ""
cat << 'SNIPPET'
    ## Sound Box (AI Audio Generation)
    This project has access to Sound Box for generating music, SFX, and speech.
    - Use `generate_audio` tool or `/soundbox-generate` skill
    - model: "music" (melodies), "audio" (sound effects), "tts" (speech)
    - TTS endpoint: POST /api/tts/generate with text + voice_id
    - Duration: 1-60 seconds (music/audio). All output is CC0 (public domain).
    - Files served at http://localhost:5309/audio/<filename>
SNIPPET
echo ""
echo -e "${YELLOW}Prerequisite:${NC} Sound Box must be running (sudo systemctl start soundbox)"
echo ""
