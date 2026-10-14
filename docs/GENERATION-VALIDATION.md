# Generation workflow qualification

The anonymous duration limit is 120 seconds, matching the Generate slider.
Each new attempt restores the status panel after a previous success, including
validation errors. GPU device failures are reported separately from memory exhaustion.

Run the strict controls check with Python, Playwright and Chrome installed:

```sh
python scripts/check_generation_controls.py --url https://your-private-soundbox
```

This clicks the actual desktop and phone UI: model tabs, every displayed prompt
preset, speech filters/search, Random, duration values 3/60/120, Loop off/on,
Generate, and another submission after completion. It checks exact submitted
values and visible errors. Expensive generation responses are stubbed; it is
not a GPU test and does not claim coverage of every Library/playlist/admin control.
Animations are disabled in the browser to make click stability deterministic.

A separate opt-in test performs real inference through the phone UI:

```sh
python scripts/check_live_music_loop.py --url https://your-private-soundbox --run-generation
```

It creates one public 120-second looped music track, waits up to 30 minutes,
checks the completed player and Library item, downloads the WAV and validates
its duration. It never treats an accepted queue request as successful generation.
If interrupted, inspect the printed job ID before rerunning to avoid duplicates.

## Deployment preserving installed customizations

`scripts/deploy_container_patch.py` runs on the Docker host with explicitly
reviewed patch files. It refuses a busy generation queue or an existing Compose
override, applies patches with no fuzz to copies of the installed sources, and
builds a derived image without reinstalling CUDA or replacing data volumes.
The persistent Compose override selects that image across container recreation.
The receipt records the prior image for rollback. Reconcile any existing override
explicitly rather than bypassing that refusal. For an image-only override created
by this tool, pass `--expected-image` with its exact currently installed tag;
unrecognized overrides or concurrent changes are still refused.

For rollback, restore the receipt's prior image in the Compose override and run
`docker compose up -d --no-build soundbox` after verifying the queue is empty.
Database visibility migration has its own SQLite backup and is separate from
image rollback. Public means visible in Soundbox's library; network access policy
is unchanged.
