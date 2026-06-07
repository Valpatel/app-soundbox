// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Tests for API edge cases — routes that are untested or shallow-tested elsewhere.
 *
 * Covers:
 * - GET  /job/<job_id>          — unknown ID, malformed (non-hex) ID
 * - POST /generate              — prompt validation (empty, too long, missing fields),
 *                                 duration over tier max is rejected (not clamped)
 * - GET  /api/library/<gen_id>  — single track fetch, 404 for unknown, 400 for bad format
 * - POST /api/track/<id>/play   — play counter increment, OPTIONS CORS preflight
 * - GET  /api/track/<id>/stats  — per-track stats shape
 * - POST /api/library/votes     — batch vote lookup, body schema validation
 * - GET  /api/library/<id>/feedback — feedback list shape
 * - POST /api/favorites/check   — bulk favorite-check
 * - GET  /api/voices            — Piper TTS voice list
 * - GET  /api/voice-licenses    — voice license metadata
 */

// A well-formed 32-char hex ID that does not exist in the DB
const UNKNOWN_VALID_ID = 'deadbeef' + '0'.repeat(24);

// An ID that is hex but the wrong length (31 chars) — fails is_valid_gen_id
const BAD_FORMAT_ID = 'abc123';

// A prompt that exceeds MAX_PROMPT_LENGTH (500 chars)
const LONG_PROMPT = 'a'.repeat(501);

test.describe('GET /job/<job_id>', () => {
    test('returns 404 for an unknown but well-formed hex job ID', async ({ request }) => {
        // job IDs are uuid4().hex (32 chars) — same hex format as gen IDs
        const res = await request.get(`/job/${UNKNOWN_VALID_ID}`);
        expect(res.status()).toBe(404);

        const body = await res.json();
        expect(body.error).toBeTruthy();
    });

    test('returns 404 for a non-hex / malformed job ID (no validation layer on this route)', async ({ request }) => {
        // The /job route checks the in-memory jobs dict; a non-existent key
        // simply returns 404 (there is no hex-format guard on this route).
        const res = await request.get('/job/not-a-valid-hex-id!!!');
        // The route does a dict lookup — missing key → 404
        expect(res.status()).toBe(404);

        const body = await res.json();
        expect(body.error).toBeTruthy();
    });
});

test.describe('POST /generate — prompt and duration validation', () => {
    test('returns 415 when Content-Type is not application/json', async ({ request }) => {
        const res = await request.post('/generate', {
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            data: 'prompt=test&model=audio&duration=2',
        });
        expect(res.status()).toBe(415);

        const body = await res.json();
        expect(body.error).toMatch(/Content-Type/i);
    });

    test('returns 400 for an empty prompt string', async ({ request }) => {
        const res = await request.post('/generate', {
            data: { prompt: '', model: 'audio', duration: 2 },
        });
        // Empty prompt fails validate_prompt (< 3 chars after strip)
        expect(res.status()).toBe(400);

        const body = await res.json();
        expect(body.success).toBe(false);
        expect(body.error).toBeTruthy();
    });

    test('returns 400 for a prompt longer than 500 characters', async ({ request }) => {
        const res = await request.post('/generate', {
            data: { prompt: LONG_PROMPT, model: 'audio', duration: 2 },
        });
        expect(res.status()).toBe(400);

        const body = await res.json();
        expect(body.success).toBe(false);
        // Error should mention the length limit
        expect(body.error).toMatch(/500/);
    });

    test('returns 400 for a prompt shorter than 3 characters', async ({ request }) => {
        const res = await request.post('/generate', {
            data: { prompt: 'ab', model: 'audio', duration: 2 },
        });
        expect(res.status()).toBe(400);

        const body = await res.json();
        expect(body.success).toBe(false);
        expect(body.error).toMatch(/short|minimum/i);
    });

    test('returns 400 when duration exceeds free-tier max (60s) — rejected, not clamped', async ({ request }) => {
        // validate_integer returns is_valid=False when value > max_val.
        // The handler converts that to a 400, not a silently-clamped value.
        const res = await request.post('/generate', {
            data: { prompt: 'upbeat electronic music', model: 'music', duration: 999 },
        });
        // Model may still be loading (503) on a fresh server — accept either
        // 400 (validation) or 503 (model not ready).  401/403 should not appear
        // because OPEN_ACCESS_MODE is true in tests.
        expect([400, 503]).toContain(res.status());

        if (res.status() === 400) {
            const body = await res.json();
            expect(body.success).toBe(false);
            expect(body.error).toMatch(/duration|60/i);
        }
    });

    test('returns 400 for an invalid model type', async ({ request }) => {
        const res = await request.post('/generate', {
            data: { prompt: 'upbeat electronic music', model: 'invalid-model', duration: 5 },
        });
        expect([400, 503]).toContain(res.status());

        if (res.status() === 400) {
            const body = await res.json();
            expect(body.success).toBe(false);
            expect(body.error).toMatch(/model/i);
        }
    });
});

test.describe('GET /api/library/<gen_id>', () => {
    test('returns 404 for an unknown but correctly-formatted 32-char hex ID', async ({ request }) => {
        const res = await request.get(`/api/library/${UNKNOWN_VALID_ID}`);
        expect(res.status()).toBe(404);

        const body = await res.json();
        expect(body.error).toBeTruthy();
    });

    test('returns 400 for a malformed generation ID (not 32-char hex)', async ({ request }) => {
        const res = await request.get(`/api/library/${BAD_FORMAT_ID}`);
        expect(res.status()).toBe(400);

        const body = await res.json();
        expect(body.error).toMatch(/invalid.*id|format/i);
    });

    test('returns 200 with track fields for a real library item (if library is non-empty)', async ({ request }) => {
        // Fetch a real track ID from the library first
        const listRes = await request.get('/api/library?limit=1');
        expect(listRes.ok()).toBeTruthy();

        const list = await listRes.json();
        if (!list.items || list.items.length === 0) {
            test.skip(true, 'Library is empty — skipping single-track fetch test');
            return;
        }

        const trackId = list.items[0].id;
        const res = await request.get(`/api/library/${trackId}`);
        expect(res.status()).toBe(200);

        const track = await res.json();
        expect(track.id).toBe(trackId);
        expect(track).toHaveProperty('prompt');
        expect(track).toHaveProperty('filename');
    });
});

test.describe('POST /api/track/<gen_id>/play', () => {
    test('OPTIONS preflight returns CORS headers', async ({ request }) => {
        const res = await request.fetch(`/api/track/${UNKNOWN_VALID_ID}/play`, {
            method: 'OPTIONS',
            headers: {
                'Origin': 'https://example.com',
                'Access-Control-Request-Method': 'POST',
            },
        });
        // Route explicitly handles OPTIONS and returns 200 with CORS headers
        expect(res.status()).toBe(200);

        const allowOrigin = res.headers()['access-control-allow-origin'];
        expect(allowOrigin).toBe('*');

        const allowMethods = res.headers()['access-control-allow-methods'];
        expect(allowMethods).toMatch(/POST/);
    });

    test('POST increments play_count (before + after via stats endpoint)', async ({ request }) => {
        // Need a real track to test counter increment
        const listRes = await request.get('/api/library?limit=1');
        expect(listRes.ok()).toBeTruthy();

        const list = await listRes.json();
        if (!list.items || list.items.length === 0) {
            test.skip(true, 'Library is empty — skipping play counter increment test');
            return;
        }

        const trackId = list.items[0].id;

        // Read stats before
        const beforeRes = await request.get(`/api/track/${trackId}/stats`);
        expect(beforeRes.status()).toBe(200);
        const before = await beforeRes.json();
        const beforeCount = before.play_count;

        // Record a play
        const playRes = await request.post(`/api/track/${trackId}/play`, {
            data: { source: 'library', session_id: 'test-session-01' },
        });
        expect(playRes.ok()).toBeTruthy();

        // Read stats after
        const afterRes = await request.get(`/api/track/${trackId}/stats`);
        expect(afterRes.status()).toBe(200);
        const after = await afterRes.json();

        expect(after.play_count).toBeGreaterThan(beforeCount);
    });
});

test.describe('GET /api/track/<gen_id>/stats', () => {
    test('returns 404 for an unknown track ID', async ({ request }) => {
        const res = await request.get(`/api/track/${UNKNOWN_VALID_ID}/stats`);
        expect(res.status()).toBe(404);

        const body = await res.json();
        expect(body.error).toBeTruthy();
    });

    test('returns correct shape for a known track', async ({ request }) => {
        const listRes = await request.get('/api/library?limit=1');
        const list = await listRes.json();

        if (!list.items || list.items.length === 0) {
            test.skip(true, 'Library is empty — skipping stats shape test');
            return;
        }

        const trackId = list.items[0].id;
        const res = await request.get(`/api/track/${trackId}/stats`);
        expect(res.status()).toBe(200);

        const stats = await res.json();
        expect(typeof stats.play_count).toBe('number');
        expect(typeof stats.unique_plays).toBe('number');
        expect(typeof stats.download_count).toBe('number');
        expect(stats).toHaveProperty('by_source');
        expect(stats).toHaveProperty('daily');
    });
});

test.describe('POST /api/library/votes', () => {
    test('returns 400 when generation_ids is not an array', async ({ request }) => {
        const res = await request.post('/api/library/votes', {
            data: { generation_ids: 'not-an-array' },
        });
        // require_auth in OPEN_ACCESS_MODE assigns an anon user, so no 401
        expect(res.status()).toBe(400);

        const body = await res.json();
        expect(body.error).toMatch(/list|array/i);
    });

    test('returns 400 when generation_ids exceeds 100 items', async ({ request }) => {
        const ids = Array.from({ length: 101 }, (_, i) => `item${i}`);
        const res = await request.post('/api/library/votes', {
            data: { generation_ids: ids },
        });
        expect(res.status()).toBe(400);

        const body = await res.json();
        expect(body.error).toMatch(/100/);
    });

    test('returns votes object for a valid (possibly empty) ID list', async ({ request }) => {
        const res = await request.post('/api/library/votes', {
            data: { generation_ids: [UNKNOWN_VALID_ID] },
        });
        expect(res.status()).toBe(200);

        const body = await res.json();
        expect(body).toHaveProperty('votes');
        expect(typeof body.votes).toBe('object');
    });
});

test.describe('GET /api/library/<gen_id>/feedback', () => {
    test('returns a feedback summary (empty or populated) for any ID', async ({ request }) => {
        // This endpoint does not validate gen_id format or check DB existence —
        // it just returns whatever db.get_generation_feedback returns (empty object/dict).
        const res = await request.get(`/api/library/${UNKNOWN_VALID_ID}/feedback`);
        expect(res.status()).toBe(200);

        const body = await res.json();
        // Shape is an object (dict of reason → count); may be empty for unknown ID
        expect(typeof body).toBe('object');
    });

    test('returns feedback summary for a known track', async ({ request }) => {
        const listRes = await request.get('/api/library?limit=1');
        const list = await listRes.json();

        if (!list.items || list.items.length === 0) {
            test.skip(true, 'Library is empty — skipping feedback test');
            return;
        }

        const trackId = list.items[0].id;
        const res = await request.get(`/api/library/${trackId}/feedback`);
        expect(res.status()).toBe(200);

        const body = await res.json();
        expect(typeof body).toBe('object');
    });
});

test.describe('POST /api/favorites/check', () => {
    test('returns 400 when generation_ids exceeds 100 items', async ({ request }) => {
        const ids = Array.from({ length: 101 }, (_, i) => `item${i}`);
        const res = await request.post('/api/favorites/check', {
            data: { generation_ids: ids },
        });
        expect(res.status()).toBe(400);

        const body = await res.json();
        expect(body.error).toMatch(/100/);
    });

    test('returns 400 when generation_ids is not an array', async ({ request }) => {
        const res = await request.post('/api/favorites/check', {
            data: { generation_ids: 'bad' },
        });
        expect(res.status()).toBe(400);

        const body = await res.json();
        expect(body.error).toMatch(/list|array/i);
    });

    test('returns favorites array for a valid ID list', async ({ request }) => {
        const res = await request.post('/api/favorites/check', {
            data: { generation_ids: [UNKNOWN_VALID_ID] },
        });
        expect(res.status()).toBe(200);

        const body = await res.json();
        expect(body).toHaveProperty('favorites');
        expect(Array.isArray(body.favorites)).toBe(true);
    });

    test('unknown IDs are not in the returned favorites array', async ({ request }) => {
        const res = await request.post('/api/favorites/check', {
            data: { generation_ids: [UNKNOWN_VALID_ID] },
        });
        expect(res.status()).toBe(200);

        const body = await res.json();
        // The unknown ID should not appear as a favorited item
        expect(body.favorites).not.toContain(UNKNOWN_VALID_ID);
    });
});

test.describe('GET /api/voices', () => {
    test('returns valid JSON with voices array and total count', async ({ request }) => {
        const res = await request.get('/api/voices');
        expect(res.status()).toBe(200);

        const body = await res.json();
        expect(body).toHaveProperty('voices');
        expect(Array.isArray(body.voices)).toBe(true);
        expect(typeof body.total).toBe('number');
        expect(body.total).toBe(body.voices.length);
    });

    test('each voice entry has required metadata fields', async ({ request }) => {
        const res = await request.get('/api/voices');
        const body = await res.json();

        if (body.voices.length === 0) {
            // Voices require setup.sh to install .onnx files — acceptable in CI
            test.skip(true, 'No Piper voice files installed — skipping per-entry field check');
            return;
        }

        for (const voice of body.voices) {
            expect(voice).toHaveProperty('id');
            expect(voice).toHaveProperty('name');
            expect(voice).toHaveProperty('locale');
        }
    });
});

test.describe('GET /api/voice-licenses', () => {
    test('returns valid JSON license information', async ({ request }) => {
        const res = await request.get('/api/voice-licenses');
        expect(res.status()).toBe(200);

        const body = await res.json();
        // get_all_voice_licenses() returns a top-level object with four keys:
        //   datasets: { [datasetId]: { name, license, creator, url, ... } }
        //   licenses: { [licenseId]: { name, short, commercial, ... } }
        //   commercial_datasets: string[]
        //   non_commercial_datasets: string[]
        expect(typeof body).toBe('object');
        expect(body).not.toBeNull();
        expect(body).toHaveProperty('datasets');
        expect(body).toHaveProperty('licenses');
        expect(body).toHaveProperty('commercial_datasets');
        expect(body).toHaveProperty('non_commercial_datasets');
        expect(typeof body.datasets).toBe('object');
        expect(typeof body.licenses).toBe('object');
        expect(Array.isArray(body.commercial_datasets)).toBe(true);
        expect(Array.isArray(body.non_commercial_datasets)).toBe(true);
    });

    test('each dataset entry has expected fields', async ({ request }) => {
        const res = await request.get('/api/voice-licenses');
        const body = await res.json();

        const datasetEntries = Object.entries(body.datasets || {});
        // DATASETS dict in voice_licenses.py is hardcoded and non-empty —
        // if this becomes empty the module is broken.
        expect(datasetEntries.length).toBeGreaterThan(0);

        for (const [datasetId, entry] of datasetEntries) {
            expect(typeof datasetId).toBe('string');
            expect(entry).toHaveProperty('name');
            expect(entry).toHaveProperty('license');
            expect(entry).toHaveProperty('creator');
            expect(typeof entry.name).toBe('string');
            // license is a license-type key that must exist in the licenses dict
            expect(body.licenses).toHaveProperty(entry.license);
        }
    });

    test('each license type has commercial flag and display name', async ({ request }) => {
        const res = await request.get('/api/voice-licenses');
        const body = await res.json();

        const licenseEntries = Object.entries(body.licenses || {});
        expect(licenseEntries.length).toBeGreaterThan(0);

        for (const [licenseId, info] of licenseEntries) {
            expect(typeof licenseId).toBe('string');
            expect(info).toHaveProperty('name');
            expect(info).toHaveProperty('commercial');
            expect(typeof info.commercial).toBe('boolean');
        }
    });

    test('commercial_datasets and non_commercial_datasets partition the dataset keys', async ({ request }) => {
        const res = await request.get('/api/voice-licenses');
        const body = await res.json();

        const allDatasetIds = new Set(Object.keys(body.datasets || {}));
        for (const id of body.commercial_datasets) {
            expect(allDatasetIds.has(id)).toBe(true);
        }
        for (const id of body.non_commercial_datasets) {
            expect(allDatasetIds.has(id)).toBe(true);
        }
        // commercial and non-commercial lists must be disjoint
        const commercialSet = new Set(body.commercial_datasets);
        for (const id of body.non_commercial_datasets) {
            expect(commercialSet.has(id)).toBe(false);
        }
    });
});
