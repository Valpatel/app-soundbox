# Radio eligibility and listener-driven generation

Radio excludes a song when downvotes exceed upvotes. Ties and unvoted songs stay
eligible; votes can restore eligibility. Library files and playlist membership are
not deleted. All database radio selectors enforce the same rule.

Selecting an empty music station, or finishing its available queue, requests one
90-second instrumental song through `POST /api/radio/fill`. The server uses a fixed
station prompt, checks for existing unplayed eligible tracks, and shares an active
station job across listeners. The normal generation handler still enforces access,
quota configuration, readiness and atomic queue capacity. There is no new worker
or background generation timer. Favorites and saved playlists stay curated.

Progress and errors appear inside Now Playing. While a station generates, radio
plays an eligible library interlude, allowing repeats if necessary. The new song
goes next without interrupting the current song. A completely empty library keeps
a visible waiting player. Switching tabs pauses all audio sources. Switching
stations, changing tabs or choosing Stop invalidates pending radio responses; a shared GPU job already
admitted can finish and remains in the public library. Passive page loads do not
generate. Failed requests do not retry automatically. Browser autoplay policy may
require pressing Play when the first song finishes generating. A mini-player
provides explicit resume and Stop controls outside Radio. Library refreshes pause
audio elements that disappear, including detached previews on navigation.

The generation queue shows descriptions only for explicitly public jobs. Private
and legacy jobs keep their prompts and station metadata hidden; no owner identities
are returned. Expand a queue description to read the full prompt.

Generation jobs use the existing single-process in-memory queue. Restarting loses
pending jobs; drain the queue before deployment. Concurrent requests to one server
share a job; multiple independent server processes would require shared durable
admission before using this as a multi-worker service.

Validation:

- `pytest tests/test_database.py tests/test_generation_quotas.py tests/test_radio_generation.py`
- `python scripts/check_radio_lifecycle.py --url URL` (mocked GPU jobs, real browser UI)
- `python scripts/check_playback_experience.py --url URL` (mocked generation and audio;
  interludes, six viewport widths, exclusive playback, navigation and removed players).
- `python scripts/check_queue_details.py --url URL` (mocked queue details and layout).
- `pytest tests/test_queue_details.py` (actual route serialization and private redaction).
- Existing generation controls and pagination browser checks.
- `python scripts/check_live_radio.py --url URL --station dreamy --run-generation`
  (requires an empty station; creates one real public song and verifies shared
  admission, 90-second downloadable audio and library visibility).

`scripts/deploy_container_patch.py` accepts reviewed diffs, including a newly added
root Python module. It compiles staged Python, fingerprints the staged application,
uses an immutable derived image, refuses a busy queue and preserves data volumes.
Keep its receipt and previous image for rollback; verify deployed build identity,
health and affected browser flows. Run real radio generation qualification after
changes to generation behavior; UI-only changes can use mocked browser jobs and
existing audio without consuming GPU time.

## Continuous radio and optional overnight stocking

All Music and the station presets repeat eligible songs when history is exhausted.
The queue panel stays visible while the final song plays. Radio prefers the least
recently played songs in the selected category and uses an all-music interlude if
that category has no eligible songs. It prefetches when fewer than two tracks are
queued, sharing one active generation per station. Favorites/playlists stay curated.

For deliberate unattended stocking, run this separate, bounded command on the
Soundbox host (Python 3.10+; standard library only):

```sh
python3 scripts/radio_precache.py --url http://127.0.0.1:5309 \
  --until 2026-10-15T08:00:00-07:00 --max-tracks 120 \
  --state /var/lib/soundbox/precache.json \
  --pause-file /var/lib/soundbox/precache.pause
```

Use your intended date and timezone. The deadline stops new admissions; an
already-running job may finish. Creating the pause file pauses admissions after
the current job, allowing an empty queue for maintenance. Removing it resumes
within the original deadline. The state file records completed library IDs and
current work; restarting with the same state resumes polling, not duplicate work.
Only one process can own a state file. Do not use multiple state files for the
same batch. Ambiguous submission failures deliberately stop for queue inspection.
Three consecutive failed jobs also stop the batch.

The tool waits behind existing queues and model warmup. It stocks six station
categories, prioritizing low eligible-track counts relative to a target adjusted
by positive votes and accumulated plays. Downvoted-majority songs do not count as
stock. This is a simple demand heuristic, not an audio-quality classifier. It
varies instrument/mood prompts and chooses 60/90/120-second instrumental songs.
There is no automatic night schedule or power-policy change.

Validate with `pytest tests/test_radio_precache.py` and
`python scripts/check_continuous_radio.py --url URL` (mocked jobs, six consecutive
track transitions at phone/desktop widths).
