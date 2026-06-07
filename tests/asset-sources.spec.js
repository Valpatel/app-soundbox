// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Tests for Asset Sources API endpoints.
 * Verifies the project-sources asset management routes:
 * - GET /api/assets/sources          - list all sources with counts
 * - GET /api/assets/sources/<id>     - single source detail
 * - GET /api/assets/library          - paginated library filtered by source
 * - POST /api/assets/set-source      - bulk-assign source to generations
 */

test.describe('Asset Sources API', () => {

    // ---------------------------------------------------------------------------
    // GET /api/assets/sources
    // ---------------------------------------------------------------------------

    test.describe('GET /api/assets/sources', () => {

        test('returns 200 with valid JSON', async ({ request }) => {
            const res = await request.get('/api/assets/sources');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body).toBeDefined();
        });

        test('response contains sources and counts objects', async ({ request }) => {
            const res = await request.get('/api/assets/sources');
            const body = await res.json();

            expect(body.sources).toBeDefined();
            expect(typeof body.sources).toBe('object');
            expect(body.counts).toBeDefined();
            expect(typeof body.counts).toBe('object');
        });

        test('counts entries match sources keys', async ({ request }) => {
            const res = await request.get('/api/assets/sources');
            const { sources, counts } = await res.json();

            const sourceKeys = Object.keys(sources);
            // Every count entry should correspond to a known source key
            for (const key of Object.keys(counts)) {
                expect(sourceKeys).toContain(key);
            }
        });

        test('each count entry has numeric music/audio/voice/total fields when present', async ({ request }) => {
            const res = await request.get('/api/assets/sources');
            const { counts } = await res.json();

            for (const [, entry] of Object.entries(counts)) {
                expect(typeof entry.music).toBe('number');
                expect(typeof entry.audio).toBe('number');
                expect(typeof entry.voice).toBe('number');
                expect(typeof entry.total).toBe('number');
            }
        });
    });

    // ---------------------------------------------------------------------------
    // GET /api/assets/sources/<source_id>
    // ---------------------------------------------------------------------------

    test.describe('GET /api/assets/sources/<source_id>', () => {

        test('returns 404 for unknown source id', async ({ request }) => {
            const res = await request.get('/api/assets/sources/totally-nonexistent-source-xyz');
            expect(res.status()).toBe(404);

            const body = await res.json();
            expect(body.error).toBeTruthy();
        });

        test('returns 200 with full detail for a known source', async ({ request }) => {
            // Discover available sources first; skip if none configured
            const listRes = await request.get('/api/assets/sources');
            const { sources } = await listRes.json();
            const sourceKeys = Object.keys(sources);

            if (sourceKeys.length === 0) {
                test.skip(true, 'No project sources configured — skipping single-source detail test');
                return;
            }

            const firstKey = sourceKeys[0];
            const res = await request.get(`/api/assets/sources/${firstKey}`);
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body.source_id).toBe(firstKey);
            expect(body.source).toBeDefined();
            expect(body.counts).toBeDefined();
        });

        test('detail counts have expected numeric fields', async ({ request }) => {
            const listRes = await request.get('/api/assets/sources');
            const { sources } = await listRes.json();
            const sourceKeys = Object.keys(sources);

            if (sourceKeys.length === 0) {
                test.skip(true, 'No project sources configured — skipping counts shape test');
                return;
            }

            const res = await request.get(`/api/assets/sources/${sourceKeys[0]}`);
            const { counts } = await res.json();

            expect(typeof counts.music).toBe('number');
            expect(typeof counts.audio).toBe('number');
            expect(typeof counts.voice).toBe('number');
            expect(typeof counts.total).toBe('number');
        });
    });

    // ---------------------------------------------------------------------------
    // GET /api/assets/library
    // ---------------------------------------------------------------------------

    test.describe('GET /api/assets/library', () => {

        test('returns 400 when source param is missing', async ({ request }) => {
            const res = await request.get('/api/assets/library');
            expect(res.status()).toBe(400);

            const body = await res.json();
            expect(body.error).toMatch(/source/i);
        });

        test('returns 400 for an unknown source value', async ({ request }) => {
            const res = await request.get('/api/assets/library?source=no-such-source-ever');
            expect(res.status()).toBe(400);

            const body = await res.json();
            expect(body.error).toBeTruthy();
        });

        test('returns paginated library for a valid source', async ({ request }) => {
            const listRes = await request.get('/api/assets/sources');
            const { sources } = await listRes.json();
            const sourceKeys = Object.keys(sources);

            if (sourceKeys.length === 0) {
                test.skip(true, 'No project sources configured — skipping library pagination test');
                return;
            }

            const res = await request.get(`/api/assets/library?source=${sourceKeys[0]}`);
            expect(res.status()).toBe(200);

            const body = await res.json();
            // db.get_library() returns { items, total, page, per_page, pages }
            expect(Array.isArray(body.items)).toBe(true);
        });

        test('pagination params are respected (page/per_page)', async ({ request }) => {
            const listRes = await request.get('/api/assets/sources');
            const { sources } = await listRes.json();
            const sourceKeys = Object.keys(sources);

            if (sourceKeys.length === 0) {
                test.skip(true, 'No project sources configured — skipping pagination params test');
                return;
            }

            const res = await request.get(`/api/assets/library?source=${sourceKeys[0]}&page=1&per_page=5`);
            expect(res.status()).toBe(200);

            // db.get_library() echoes back the clamped pagination params
            const body = await res.json();
            expect(body.page).toBe(1);
            expect(body.per_page).toBe(5);
            // Should return at most 5 items
            expect(body.items.length).toBeLessThanOrEqual(5);
        });
    });

    // ---------------------------------------------------------------------------
    // POST /api/assets/set-source
    // ---------------------------------------------------------------------------

    test.describe('POST /api/assets/set-source', () => {

        test('returns 400 when generation_ids is missing', async ({ request }) => {
            const res = await request.post('/api/assets/set-source', {
                data: { source: 'some-source' },
                headers: { 'Content-Type': 'application/json' }
            });
            // 400 (missing ids) or 400 (invalid source) - either way, not 2xx
            expect(res.status()).toBeGreaterThanOrEqual(400);
            expect(res.status()).toBeLessThan(500);
        });

        test('returns 400 when generation_ids is empty list', async ({ request }) => {
            const res = await request.post('/api/assets/set-source', {
                data: { generation_ids: [], source: 'any-source' },
                headers: { 'Content-Type': 'application/json' }
            });
            expect(res.status()).toBe(400);

            const body = await res.json();
            expect(body.error).toMatch(/generation_ids/i);
        });

        test('returns 400 when source is invalid', async ({ request }) => {
            const res = await request.post('/api/assets/set-source', {
                data: { generation_ids: ['deadbeef01234567'], source: 'totally-invalid-source-xyz' },
                headers: { 'Content-Type': 'application/json' }
            });
            expect(res.status()).toBe(400);

            const body = await res.json();
            expect(body.error).toBeTruthy();
        });

        test('happy path: set source on a real generation id', async ({ request }) => {
            // Discover a valid source
            const listRes = await request.get('/api/assets/sources');
            const { sources } = await listRes.json();
            const sourceKeys = Object.keys(sources);

            if (sourceKeys.length === 0) {
                test.skip(true, 'No project sources configured — skipping set-source happy path test');
                return;
            }

            // Fetch a real generation id from the general library
            const libRes = await request.get('/api/library?per_page=1');
            const libBody = await libRes.json();
            const tracks = Array.isArray(libBody) ? libBody : (libBody.tracks || libBody.items || libBody.results || []);

            if (tracks.length === 0) {
                test.skip(true, 'Library is empty — skipping set-source happy path test');
                return;
            }

            const genId = tracks[0].id;
            const targetSource = sourceKeys[0];

            const res = await request.post('/api/assets/set-source', {
                data: { generation_ids: [genId], source: targetSource },
                headers: { 'Content-Type': 'application/json' }
            });

            expect(res.status()).toBe(200);
            const body = await res.json();
            expect(body.success).toBe(true);
            expect(typeof body.updated).toBe('number');
            expect(body.source).toBe(targetSource);
        });

        test('set source with null clears assignment', async ({ request }) => {
            // Fetch a real generation id
            const libRes = await request.get('/api/library?per_page=1');
            const libBody = await libRes.json();
            const tracks = Array.isArray(libBody) ? libBody : (libBody.tracks || libBody.items || libBody.results || []);

            if (tracks.length === 0) {
                test.skip(true, 'Library is empty — skipping clear-source test');
                return;
            }

            const genId = tracks[0].id;

            const res = await request.post('/api/assets/set-source', {
                data: { generation_ids: [genId], source: null },
                headers: { 'Content-Type': 'application/json' }
            });

            // Null source = clear assignment; server should accept this
            expect(res.status()).toBe(200);
            const body = await res.json();
            expect(body.success).toBe(true);
            expect(body.source).toBeNull();
        });
    });
});
