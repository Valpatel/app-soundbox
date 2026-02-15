---
name: generate-test
description: Generate a test audio clip via the API to verify the server is working
disable-model-invocation: true
allowed-tools: Bash
argument-hint: "[prompt]"
---

## Generate Test Audio

Submit a generation job to the Sound Box API and wait for completion.

Default prompt: "short test beep" (override with `$ARGUMENTS`)

Steps:
1. Check server status: `curl -s http://localhost:5309/status`
2. If models are ready, submit generation:
   ```bash
   curl -s -X POST http://localhost:5309/generate \
     -H "Content-Type: application/json" \
     -d '{"prompt": "<prompt>", "model": "audio", "duration": 3}'
   ```
3. Poll `http://localhost:5309/job/<job_id>` every 2 seconds until completed
4. Report: success/failure, duration, filename, quality score
