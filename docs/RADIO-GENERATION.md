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

The UI displays progress and errors. Switching stations or choosing Stop waiting
stops that listener's polling and prevents late playback; a shared GPU job already
admitted can finish and remains in the public library. Passive page loads do not
generate. Failed requests do not retry automatically. Browser autoplay policy may
require pressing Play when the first song finishes generating.

Generation jobs use the existing single-process in-memory queue. Restarting loses
pending jobs; drain the queue before deployment. Concurrent requests to one server
share a job; multiple independent server processes would require shared durable
admission before using this as a multi-worker service.

Validation:

- `pytest tests/test_database.py tests/test_generation_quotas.py tests/test_radio_generation.py`
- `python scripts/check_radio_lifecycle.py --url URL` (mocked GPU jobs, real browser UI)
- Existing generation controls and pagination browser checks.
- Deployment qualification: select a station with no eligible tracks, observe a
  real job complete, verify 90-second downloadable audio and library visibility.

`scripts/deploy_container_patch.py` accepts reviewed diffs, including a newly added
root Python module. It compiles staged Python, fingerprints the staged application,
uses an immutable derived image, refuses a busy queue and preserves data volumes.
Keep its receipt and previous image for rollback; verify the UI, status and a real
radio generation after deployment.
