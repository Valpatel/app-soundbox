---
name: search
description: Search the Sound Box audio library by keyword
disable-model-invocation: true
allowed-tools: Bash
argument-hint: "<query> [--model music|audio] [--sort newest|popular] [--limit N]"
---

## Search Library

Search the Sound Box audio library.

Parse `$ARGUMENTS` for:
- **query** (required) - Search terms (everything before flags)
- **--model** (optional) - Filter by `music` or `audio`
- **--sort** (optional) - `newest` or `popular` (default: `newest`)
- **--limit** (optional) - Max results, 1-100 (default: `10`)

If no arguments provided, show the 10 most recent tracks.

Steps:
1. Build URL: `http://localhost:5309/api/library?q=<query>&model=<model>&sort=<sort>&per_page=<limit>`
2. Fetch: `curl -s "<url>"`
3. Format results as a table:
   - ID | Prompt | Model | Duration | Votes | Created
4. Report total results count and page info
