// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Tests for the My Generations API endpoints.
 * All three routes require auth; in OPEN_ACCESS_MODE the server creates an
 * anonymous user from the caller's IP, so no token is needed in tests.
 *
 * Routes covered:
 * - GET  /api/my-generations         (list + pagination)
 * - GET  /api/my-generations/storage (storage usage stats)
 * - POST /api/my-generations/cleanup (delete oldest non-favorited)
 */

test.describe('My Generations API', () => {

    test.describe('GET /api/my-generations', () => {

        test('returns 200 with valid top-level structure', async ({ request }) => {
            const res = await request.get('/api/my-generations');
            expect(res.status()).toBe(200);

            const body = await res.json();

            // Pagination envelope
            expect(typeof body.total).toBe('number');
            expect(typeof body.page).toBe('number');
            expect(typeof body.per_page).toBe('number');
            expect(typeof body.pages).toBe('number');

            // Item list
            expect(Array.isArray(body.items)).toBe(true);

            // Model breakdown
            expect(body.by_model).toBeDefined();
            expect(typeof body.by_model).toBe('object');

            // Inline storage info
            expect(body.storage).toBeDefined();

            // CC0 notice
            expect(typeof body.license_notice).toBe('string');
            expect(body.license_notice).toContain('CC0');
        });

        test('pagination defaults: page 1, per_page within allowed range', async ({ request }) => {
            const res = await request.get('/api/my-generations');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body.page).toBe(1);
            expect(body.per_page).toBeGreaterThanOrEqual(1);
            expect(body.per_page).toBeLessThanOrEqual(100);
        });

        test('pagination params: page and per_page are respected', async ({ request }) => {
            const res = await request.get('/api/my-generations?page=2&per_page=5');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body.page).toBe(2);
            expect(body.per_page).toBe(5);
            // items array length must not exceed per_page
            expect(body.items.length).toBeLessThanOrEqual(5);
        });

        test('per_page is clamped to max 100', async ({ request }) => {
            const res = await request.get('/api/my-generations?per_page=9999');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body.per_page).toBeLessThanOrEqual(100);
        });

        test('model filter param is accepted without error', async ({ request }) => {
            for (const model of ['music', 'audio', 'voice']) {
                const res = await request.get(`/api/my-generations?model=${model}`);
                expect(res.status()).toBe(200);

                const body = await res.json();
                expect(Array.isArray(body.items)).toBe(true);
                // Every returned item must match the requested model
                for (const item of body.items) {
                    expect(item.model).toBe(model);
                }
            }
        });

        test('each item in the list has required generation fields', async ({ request }) => {
            // Generate a page that is likely to contain items if any exist
            const res = await request.get('/api/my-generations?per_page=10');
            expect(res.status()).toBe(200);

            const body = await res.json();
            for (const item of body.items) {
                expect(item.id).toBeTruthy();
                expect(typeof item.prompt).toBe('string');
                expect(typeof item.model).toBe('string');
                expect(typeof item.created_at).toBe('string');
                // is_favorite flag must be present (0/1 or bool)
                expect(item.is_favorite).toBeDefined();
            }
        });

        test('pages calculation is consistent with total and per_page', async ({ request }) => {
            const res = await request.get('/api/my-generations?per_page=10');
            expect(res.status()).toBe(200);

            const body = await res.json();
            const expectedPages = body.total === 0
                ? 0
                : Math.ceil(body.total / body.per_page);
            expect(body.pages).toBe(expectedPages);
        });

    });

    test.describe('GET /api/my-generations/storage', () => {

        test('returns 200 with all required storage fields', async ({ request }) => {
            const res = await request.get('/api/my-generations/storage');
            expect(res.status()).toBe(200);

            const storage = await res.json();

            expect(typeof storage.used).toBe('number');
            expect(typeof storage.limit).toBe('number');
            expect(typeof storage.favorites).toBe('number');
            expect(typeof storage.percent_used).toBe('number');
            expect(typeof storage.can_generate).toBe('boolean');
            expect(typeof storage.near_limit).toBe('boolean');
            expect(typeof storage.at_limit).toBe('boolean');
        });

        test('storage values are self-consistent', async ({ request }) => {
            const res = await request.get('/api/my-generations/storage');
            expect(res.status()).toBe(200);

            const storage = await res.json();

            // limit must be a positive number matching a known tier cap
            expect(storage.limit).toBeGreaterThan(0);

            // used cannot exceed limit (or at_limit would be true)
            if (storage.at_limit) {
                expect(storage.used).toBeGreaterThanOrEqual(storage.limit);
            }

            // near_limit is true at >= 80%
            if (storage.near_limit) {
                expect(storage.percent_used).toBeGreaterThanOrEqual(80);
            }

            // can_generate is the inverse of at_limit
            expect(storage.can_generate).toBe(!storage.at_limit);
        });

        test('includes tier and upgrade_url fields', async ({ request }) => {
            const res = await request.get('/api/my-generations/storage');
            expect(res.status()).toBe(200);

            const storage = await res.json();
            expect(typeof storage.tier).toBe('string');
            // upgrade_url is either a string or null — just confirm it exists as a key
            expect('upgrade_url' in storage).toBe(true);
        });

        test('storage endpoint matches inline storage in my-generations response', async ({ request }) => {
            const [listRes, storageRes] = await Promise.all([
                request.get('/api/my-generations'),
                request.get('/api/my-generations/storage'),
            ]);

            expect(listRes.status()).toBe(200);
            expect(storageRes.status()).toBe(200);

            const list = await listRes.json();
            const storage = await storageRes.json();

            // Both come from get_user_storage_info — core fields must agree
            expect(list.storage.used).toBe(storage.used);
            expect(list.storage.limit).toBe(storage.limit);
            expect(list.storage.favorites).toBe(storage.favorites);
        });

    });

    test.describe('POST /api/my-generations/cleanup', () => {

        test('returns 200 with success, deleted, and storage fields', async ({ request }) => {
            // Pass keep_count equal to the maximum tier limit so the query
            // keeps all existing generations — deleted will be 0.
            const res = await request.post('/api/my-generations/cleanup', {
                data: { keep_count: 500 },
            });
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body.success).toBe(true);
            expect(typeof body.deleted).toBe('number');
            expect(body.storage).toBeDefined();
        });

        test('cleanup with large keep_count deletes nothing (safe no-op)', async ({ request }) => {
            // keep_count is clamped to tier limit (max 500 for creator).
            // Any value at or above the tier limit means "keep everything",
            // so deleted must be 0 regardless of how many generations exist.
            const res = await request.post('/api/my-generations/cleanup', {
                data: { keep_count: 500 },
            });
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body.deleted).toBe(0);
        });

        test('cleanup response storage shape matches /storage endpoint', async ({ request }) => {
            const cleanupRes = await request.post('/api/my-generations/cleanup', {
                data: { keep_count: 500 },
            });
            expect(cleanupRes.status()).toBe(200);

            const cleanup = await cleanupRes.json();
            const storage = cleanup.storage;

            // Must have the same fields as /api/my-generations/storage
            expect(typeof storage.used).toBe('number');
            expect(typeof storage.limit).toBe('number');
            expect(typeof storage.favorites).toBe('number');
            expect(typeof storage.percent_used).toBe('number');
            expect(typeof storage.can_generate).toBe('boolean');
            expect(typeof storage.near_limit).toBe('boolean');
            expect(typeof storage.at_limit).toBe('boolean');
        });

        test('invalid keep_count returns 400', async ({ request }) => {
            const res = await request.post('/api/my-generations/cleanup', {
                data: { keep_count: 'not-a-number' },
            });
            expect(res.status()).toBe(400);

            const body = await res.json();
            expect(body.error).toContain('keep_count');
        });

        test('cleanup with no body succeeds (keep_count optional)', async ({ request }) => {
            // Omitting keep_count falls back to the tier default.
            // A fresh anonymous test user has 0 private generations, so
            // deleted will be 0; regardless, the response must be valid.
            const res = await request.post('/api/my-generations/cleanup', {
                data: {},
            });
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body.success).toBe(true);
            expect(typeof body.deleted).toBe('number');
            expect(body.deleted).toBeGreaterThanOrEqual(0);
        });

        test('deleted count is a non-negative integer', async ({ request }) => {
            const res = await request.post('/api/my-generations/cleanup', {
                data: { keep_count: 500 },
            });
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(Number.isInteger(body.deleted)).toBe(true);
            expect(body.deleted).toBeGreaterThanOrEqual(0);
        });

    });

});
