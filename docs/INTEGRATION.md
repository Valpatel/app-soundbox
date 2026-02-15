# Using Sound Box from Other Projects

How to generate music, sound effects, and speech from any project on this machine using Claude Code.

## Quick Setup

Run the installer from the Sound Box repo:

```bash
~/Code/app-soundbox/install-claude-skill.sh
```

This installs the global `/soundbox-generate` skill and generates an `.mcp.json` you can copy into other projects.

### Option A: Skill only

The `/soundbox-generate` skill works immediately from any Claude Code session:

```
/soundbox-generate epic orchestral trailer music --duration 15
/soundbox-generate UI button click --model audio --duration 2
/soundbox-generate Hello and welcome to the app --model tts
/soundbox-generate rain on a window --model audio --duration 30
```

### Option B: Full MCP tools (recommended)

Copy the generated config into your project for full tool access:

```bash
cp ~/Code/app-soundbox/.mcp-external.json /path/to/your-project/.mcp.json
```

This gives Claude all 6 Sound Box MCP tools (generate_audio, check_job, search_library, get_status, get_radio_track, download_audio). Restart Claude Code after adding.

## How It Works

```
Your Project                Sound Box
───────────                 ─────────
Claude Code ──stdio──> MCP Server (mcp_server.py)
                            │
                            ▼ HTTP
                       Flask API (:5309)
                            │
                            ▼
                       MusicGen / AudioGen / Piper TTS (GPU)
                            │
                            ▼
                       generated/*.wav
```

Claude Code spawns the MCP server as a local subprocess via stdio. The MCP server translates tool calls into HTTP requests to the Flask API. No network exposure — everything runs on localhost.

## Prerequisites

- Sound Box server running: `sudo systemctl start soundbox`
- GPU with loaded models (check with `curl localhost:5309/status`)

## Three Generation Modes

### Music (model: music)
Generate melodies, background music, loops using MusicGen.

```
/soundbox-generate upbeat electronic dance music with synth arpeggios --duration 15
/soundbox-generate calm piano melody in C major
/soundbox-generate lo-fi hip hop beat with vinyl crackle --duration 30
```

**Prompt tips:** Include genre + mood + instruments.

### Sound Effects (model: audio)
Generate SFX, ambience, and environmental sounds using AudioGen.

```
/soundbox-generate thunder rolling across a mountain valley --model audio --duration 12
/soundbox-generate footsteps walking on gravel --model audio --duration 5
/soundbox-generate spaceship engine humming --model audio --duration 8
```

**Prompt tips:** Be specific and descriptive. Include environment context.

### Speech (model: tts)
Generate spoken audio using Piper TTS. Returns instantly (no queue).

```
/soundbox-generate Welcome to Sound Box --model tts
/soundbox-generate Please enter your password --model tts --voice en_GB-alan-medium
```

**Available voices:**
| Voice ID | Description |
|----------|-------------|
| `en_US-lessac-medium` | US English, neutral (default) |
| `en_US-amy-medium` | US English, female |
| `en_US-joe-medium` | US English, male |
| `en_US-ryan-medium` | US English, male |
| `en_GB-alan-medium` | British English, male |
| `en_GB-alba-medium` | British English, female |

## Available MCP Tools

| Tool | What It Does | Example Use |
|------|-------------|-------------|
| `generate_audio` | Create music or SFX from text | "Generate a 10s ambient track" |
| `check_job` | Poll generation progress | Automatic when using `wait: true` |
| `search_library` | Find existing audio | "Find thunder sound effects" |
| `get_status` | GPU, models, queue info | "Is the server ready?" |
| `get_radio_track` | Random tracks | "Play me something" |
| `download_audio` | Get audio file URL | "Download track abc123" |

## CLAUDE.md Snippet

Add this to your project's `CLAUDE.md` to help Claude use Sound Box effectively:

```markdown
## Sound Box (AI Audio Generation)

This project has access to Sound Box MCP tools for generating music, sound effects, and speech.

### Generating Audio
- Use the `generate_audio` tool or `/soundbox-generate` skill
- model: `"music"` (melodies), `"audio"` (sound effects)
- Set `wait: true` to block until generation completes (recommended)
- Duration: 1-60 seconds (default 8)

### Text-to-Speech
- POST to `/api/tts/generate` with `{"text": "...", "voice_id": "en_US-lessac-medium"}`
- Or use `/soundbox-generate Hello world --model tts`
- Voices: en_US-lessac-medium (default), en_US-amy-medium, en_GB-alan-medium, etc.

### Prompt Tips
- Music: genre + mood + instruments ("upbeat electronic with synth arpeggios")
- SFX: specific + descriptive ("heavy rain on a tin roof with distant thunder")

### Generated Files
Audio files served at `http://localhost:5309/audio/<filename>`.
All generated audio is CC0 (public domain) — free for any use.
```

## Example: Game Project

```
/soundbox-generate sword clash metal impact --model audio --duration 3
/soundbox-generate victory fanfare orchestral brass --duration 5
/soundbox-generate footsteps on stone dungeon --model audio --duration 8
/soundbox-generate You have been defeated --model tts --voice en_GB-alan-medium
```

Then copy the WAV files from `~/Code/app-soundbox/generated/` into your game's assets.

## Example: Web App

```
/soundbox-generate soft notification chime --model audio --duration 1
/soundbox-generate error alert buzzer --model audio --duration 1
/soundbox-generate Welcome back --model tts
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Sound Box not running" | `sudo systemctl start soundbox` |
| "Model not ready" | Wait ~30s for model loading, check `curl localhost:5309/status` |
| MCP tools not showing | Restart Claude Code after adding `.mcp.json` |
| Slow generation | GPU may be busy — check queue with `get_status` tool |
| Skill not found | Run `~/Code/app-soundbox/install-claude-skill.sh` |
