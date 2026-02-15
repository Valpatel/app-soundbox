---
name: generate
description: Generate audio with a text prompt via the Sound Box API
disable-model-invocation: true
allowed-tools: Bash
argument-hint: "<prompt> [--model music|audio] [--duration N]"
---

## Generate Audio

Generate music or sound effects from a text prompt.

Parse `$ARGUMENTS` for:
- **prompt** (required) - Everything before `--model` or `--duration` flags
- **--model** (optional) - `music` or `audio` (default: `music`)
- **--duration** (optional) - Seconds, 1-60 (default: `8`)

If no arguments provided, ask the user for a prompt.

Steps:
1. Check server status: `curl -s http://localhost:5309/status`
   - If models not ready, report status and stop
2. Submit generation:
   ```bash
   curl -s -X POST http://localhost:5309/generate \
     -H "Content-Type: application/json" \
     -d '{"prompt": "<prompt>", "model": "<model>", "duration": <duration>}'
   ```
3. Poll `http://localhost:5309/job/<job_id>` every 3 seconds until completed or failed
4. Report result:
   - Success: prompt, model, duration, filename, audio URL, quality score
   - Failure: error message
