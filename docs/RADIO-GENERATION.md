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
