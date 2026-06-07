// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Tests for routes with previously zero coverage:
 * - GET /queue-status      — lightweight public queue snapshot (JSON)
 * - GET /api/queue         — full queue listing for Queue Explorer (JSON)
 * - GET /track/<id>        — shareable track page (HTML, renders index.html SPA)
 * - GET /history           — legacy filesystem-scan endpoint (JSON array, NOT HTML)
 * - POST /random-prompt    — server-side random prompt generator (JSON)
 * - GET /widget/soundbox-radio.js  — embeddable widget JS with CORS headers
 * - GET /widget/soundbox-radio.css — embeddable widget CSS with CORS headers
 */

test.describe('Queue Routes', () => {

    test.describe('GET /queue-status', () => {
        test('returns 200 with valid JSON structure', async ({ request }) => {
            const res = await request.get('/queue-status');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(typeof body.queue_length).toBe('number');
            expect(body.queue_length).toBeGreaterThanOrEqual(0);
            expect(Array.isArray(body.jobs)).toBe(true);
            // current_job may be null or an object
            expect('current_job' in body).toBe(true);
        });

        test('each job in queue has required fields', async ({ request }) => {
            const res = await request.get('/queue-status');
            const body = await res.json();

            for (const job of body.jobs) {
                expect(typeof job.id).toBe('string');
                expect(['queued', 'processing']).toContain(job.status);
                expect(typeof job.model).toBe('string');
                expect(typeof job.priority).toBe('string');
            }
        });

        test('queue_length matches jobs array length', async ({ request }) => {
            const res = await request.get('/queue-status');
            const body = await res.json();
            expect(body.queue_length).toBe(body.jobs.length);
        });
    });

    test.describe('GET /api/queue', () => {
        test('returns 200 with valid JSON structure', async ({ request }) => {
            const res = await request.get('/api/queue');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(Array.isArray(body.jobs)).toBe(true);
            expect(typeof body.total).toBe('number');
            expect('current_job' in body).toBe(true);
        });

        test('total matches jobs array length', async ({ request }) => {
            const res = await request.get('/api/queue');
            const body = await res.json();
            expect(body.total).toBe(body.jobs.length);
        });

        test('each job includes detailed fields not in /queue-status', async ({ request }) => {
            const res = await request.get('/api/queue');
            const body = await res.json();

            for (const job of body.jobs) {
                expect(typeof job.id).toBe('string');
                expect(['queued', 'processing']).toContain(job.status);
                // /api/queue adds duration and progress_pct; /queue-status does not
                expect(typeof job.duration).toBe('number');
                expect(typeof job.progress_pct).toBe('number');
                expect(typeof job.position).toBe('number');
            }
        });
    });
});

test.describe('GET /track/<track_id>', () => {
    test('unknown hex id renders the SPA (200, not 404)', async ({ page }) => {
        // The handler always renders index.html — invalid IDs still return 200
        // because the route falls back gracefully (no 404 for bad IDs from URL)
        await page.goto('/track/aabbccdd1122334455667788aabbccdd');
        await expect(page).toHaveTitle(/Sound Box/i);
    });

    test('non-hex garbage id also renders the SPA (no server crash)', async ({ page }) => {
        // is_valid_gen_id rejects it; handler returns plain index.html (200)
        await page.goto('/track/not-a-valid-id');
        await expect(page).toHaveTitle(/Sound Box/i);
    });

    test('known track id renders SPA and sets shared_track_id in page source', async ({ request, page }) => {
        // Fetch a real track id from the library; skip if library is empty
        const libRes = await request.get('/api/library?limit=1');
        expect(libRes.status()).toBe(200);
        const lib = await libRes.json();
        const tracks = lib.tracks ?? lib;

        if (!Array.isArray(tracks) || tracks.length === 0) {
            test.skip(true, 'Library is empty — cannot test known-track page');
            return;
        }

        const trackId = tracks[0].id;
        await page.goto(`/track/${trackId}`);
        await expect(page).toHaveTitle(/Sound Box/i);

        // The template embeds shared_track_id as a JS variable when a valid id is passed
        const hasSharedId = await page.evaluate((id) => {
            return typeof window !== 'undefined' &&
                document.documentElement.innerHTML.includes(id);
        }, trackId);
        expect(hasSharedId).toBe(true);
    });

    test('completely unknown valid-format hex id returns 200 not 404', async ({ request }) => {
        // The route always returns 200 (renders index.html); 404 is never thrown here
        const res = await request.get('/track/deadbeef00000000deadbeef00000000');
        expect(res.status()).toBe(200);
    });
});

test.describe('GET /history', () => {
    test('returns 200 with a JSON array (not an HTML page)', async ({ request }) => {
        // /history is NOT deprecated — it is a legacy filesystem-scan JSON endpoint.
        // The handler scans the output directory, reads metadata, and returns an array.
        // Prefer /api/library (database-backed) for pagination; /history is kept for
        // backward compatibility with older widget code.
        const res = await request.get('/history');
        expect(res.status()).toBe(200);

        const contentType = res.headers()['content-type'] ?? '';
        expect(contentType).toContain('application/json');

        const body = await res.json();
        expect(Array.isArray(body)).toBe(true);
    });

    test('each history item has expected shape when non-empty', async ({ request }) => {
        const res = await request.get('/history');
        const items = await res.json();

        for (const item of items.slice(0, 5)) {
            expect(typeof item.filename).toBe('string');
            expect(item.filename.endsWith('.wav')).toBe(true);
            expect(typeof item.prompt).toBe('string');
            expect(typeof item.model).toBe('string');
        }
    });

    test('accepts limit query parameter', async ({ request }) => {
        const res = await request.get('/history?limit=2');
        expect(res.status()).toBe(200);
        const items = await res.json();
        expect(items.length).toBeLessThanOrEqual(2);
    });
});

test.describe('POST /random-prompt', () => {
    test('returns a music prompt string with no body', async ({ request }) => {
        const res = await request.post('/random-prompt', { data: {} });
        expect(res.status()).toBe(200);

        const body = await res.json();
        expect(body.success).toBe(true);
        expect(typeof body.prompt).toBe('string');
        expect(body.prompt.length).toBeGreaterThan(5);
    });

    test('returns a music prompt when model=music is specified', async ({ request }) => {
        const res = await request.post('/random-prompt', {
            data: { model: 'music' },
        });
        expect(res.status()).toBe(200);
        const body = await res.json();
        expect(body.success).toBe(true);
        expect(typeof body.prompt).toBe('string');
        expect(body.prompt.length).toBeGreaterThan(0);
    });

    test('returns a sound-effect prompt when model=audio is specified', async ({ request }) => {
        const res = await request.post('/random-prompt', {
            data: { model: 'audio' },
        });
        expect(res.status()).toBe(200);
        const body = await res.json();
        expect(body.success).toBe(true);
        expect(typeof body.prompt).toBe('string');
        expect(body.prompt.length).toBeGreaterThan(0);
    });

    test('two successive calls return different prompts (randomness check)', async ({ request }) => {
        const [r1, r2] = await Promise.all([
            request.post('/random-prompt', { data: { model: 'music' } }),
            request.post('/random-prompt', { data: { model: 'music' } }),
        ]);
        const b1 = await r1.json();
        const b2 = await r2.json();
        // Collision is astronomically unlikely given the vocabulary size
        expect(b1.prompt).not.toBe(b2.prompt);
    });
});

test.describe('Widget Asset Routes', () => {

    test.describe('GET /widget/soundbox-radio.js', () => {
        test('returns 200 with application/javascript content-type', async ({ request }) => {
            const res = await request.get('/widget/soundbox-radio.js');
            expect(res.status()).toBe(200);
            const contentType = res.headers()['content-type'] ?? '';
            expect(contentType).toContain('application/javascript');
        });

        test('includes Access-Control-Allow-Origin: * CORS header', async ({ request }) => {
            const res = await request.get('/widget/soundbox-radio.js');
            expect(res.headers()['access-control-allow-origin']).toBe('*');
        });

        test('includes Access-Control-Allow-Methods header', async ({ request }) => {
            const res = await request.get('/widget/soundbox-radio.js');
            const methods = res.headers()['access-control-allow-methods'] ?? '';
            expect(methods).toContain('GET');
        });

        test('file is non-empty (> 1 KB)', async ({ request }) => {
            const res = await request.get('/widget/soundbox-radio.js');
            const body = await res.body();
            expect(body.length).toBeGreaterThan(1024);
        });

        test('includes Cache-Control header', async ({ request }) => {
            const res = await request.get('/widget/soundbox-radio.js');
            const cacheControl = res.headers()['cache-control'] ?? '';
            expect(cacheControl).toBeTruthy();
        });
    });

    test.describe('GET /widget/soundbox-radio.css', () => {
        test('returns 200 with text/css content-type', async ({ request }) => {
            const res = await request.get('/widget/soundbox-radio.css');
            expect(res.status()).toBe(200);
            const contentType = res.headers()['content-type'] ?? '';
            expect(contentType).toContain('text/css');
        });

        test('includes Access-Control-Allow-Origin: * CORS header', async ({ request }) => {
            const res = await request.get('/widget/soundbox-radio.css');
            expect(res.headers()['access-control-allow-origin']).toBe('*');
        });

        test('includes Access-Control-Allow-Methods header', async ({ request }) => {
            const res = await request.get('/widget/soundbox-radio.css');
            const methods = res.headers()['access-control-allow-methods'] ?? '';
            expect(methods).toContain('GET');
        });

        test('file is non-empty (> 1 KB)', async ({ request }) => {
            const res = await request.get('/widget/soundbox-radio.css');
            const body = await res.body();
            expect(body.length).toBeGreaterThan(1024);
        });
    });
});
