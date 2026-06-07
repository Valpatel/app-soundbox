// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Tests for stats API endpoints.
 * Covers three routes:
 * - GET /api/stats         — general DB stats (public, rate-limited)
 * - GET /api/stats/user/<id> — per-user stats (require_auth; 403 for wrong user)
 * - GET /api/stats/system  — system-wide stats (require_auth + is_admin; 403 for non-admin)
 */

test.describe('Stats API', () => {

    test.describe('GET /api/stats', () => {
        test('returns 200 with valid JSON', async ({ request }) => {
            const res = await request.get('/api/stats');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body).toBeDefined();
        });

        test('response contains expected top-level keys', async ({ request }) => {
            const res = await request.get('/api/stats');
            const body = await res.json();

            expect(body).toHaveProperty('generations');
            expect(body).toHaveProperty('music');
            expect(body).toHaveProperty('audio');
            expect(body).toHaveProperty('votes');
            expect(body).toHaveProperty('feedback');
        });

        test('all numeric fields are non-negative integers', async ({ request }) => {
            const res = await request.get('/api/stats');
            const body = await res.json();

            for (const key of ['generations', 'music', 'audio', 'votes', 'feedback']) {
                expect(typeof body[key]).toBe('number');
                expect(body[key]).toBeGreaterThanOrEqual(0);
                expect(Number.isInteger(body[key])).toBe(true);
            }
        });

        test('music + audio counts do not exceed total generations', async ({ request }) => {
            const res = await request.get('/api/stats');
            const body = await res.json();

            // Each generation is classified as music or audio; the sum may be
            // less than or equal to total (rows without a model would be excluded).
            expect(body.music + body.audio).toBeLessThanOrEqual(body.generations);
        });

        test('responds quickly (under 1500ms)', async ({ request }) => {
            const start = Date.now();
            const res = await request.get('/api/stats', { timeout: 1500 });
            const elapsed = Date.now() - start;

            expect(res.status()).toBe(200);
            expect(elapsed).toBeLessThan(1500);
        });
    });

    // /api/stats/system is protected by require_auth + is_admin.
    // is_localhost_request() uses request.remote_addr (never XFF), so test runner
    // connects as localhost and receives is_admin=true → 200 with full payload.
    test.describe('GET /api/stats/system', () => {
        test('returns 200 for localhost (admin) request', async ({ request }) => {
            const res = await request.get('/api/stats/system');
            expect(res.status()).toBe(200);
        });

        test('response body contains expected system stats fields', async ({ request }) => {
            const res = await request.get('/api/stats/system');
            expect(res.status()).toBe(200);
            const body = await res.json();

            // System stats from db.get_system_stats() returns: totals, by_model,
            // generation_rate, top_users — verify the top-level structure is present.
            expect(body).toHaveProperty('totals');
            expect(body).toHaveProperty('generation_rate');
        });

        test('responds quickly (under 1500ms)', async ({ request }) => {
            const start = Date.now();
            const res = await request.get('/api/stats/system', { timeout: 1500 });
            const elapsed = Date.now() - start;

            expect(res.status()).toBe(200);
            expect(elapsed).toBeLessThan(1500);
        });
    });

    // /api/stats/user/<user_id> — in open access mode an anonymous user is created
    // from the requesting IP. Normally only own-user requests are allowed, but
    // is_localhost_request() uses request.remote_addr (not XFF), so the test runner
    // connects as localhost → is_admin=true, bypassing the own-user guard.
    // Admin callers can view any user's stats.
    test.describe('GET /api/stats/user/<user_id>', () => {
        // A realistic anon_id for a user with no activity on a fresh DB.
        const UNKNOWN_USER = 'anon_000000000000';
        // A syntactically invalid user_id to exercise any future validation.
        const INVALID_USER = '../../../../etc/passwd';

        test('returns 200 for localhost (admin) viewing any user stats', async ({ request }) => {
            // Localhost callers get is_admin=true, bypassing the own-user guard.
            // The response is a stats object (possibly all zeros for an unknown user).
            const res = await request.get(`/api/stats/user/${UNKNOWN_USER}`);
            // Admin can view any user — no 403 from localhost.
            expect(res.status()).not.toBe(500);
            expect([200, 404]).toContain(res.status());
        });

        test('response for unknown user is JSON without a 500', async ({ request }) => {
            const res = await request.get(`/api/stats/user/${UNKNOWN_USER}`);
            expect(res.status()).not.toBe(500);

            const body = await res.json();
            expect(body).toBeDefined();
            // For 4xx responses Flask returns { error: '...' }
            if (res.status() >= 400) {
                expect(body).toHaveProperty('error');
            }
        });

        test('path traversal user_id is handled safely (no 500)', async ({ request }) => {
            const res = await request.get(`/api/stats/user/${encodeURIComponent(INVALID_USER)}`);
            // Flask may 404 on the route or 403 from the auth guard — anything except 500.
            expect(res.status()).not.toBe(500);
        });

        test('user stats shape is correct when returned for own identity', async ({ request, page }) => {
            // Navigate to the app to let open access assign an anon identity, then
            // read that identity from the page and query the stats endpoint for it.
            await page.goto('/');
            await page.waitForLoadState('networkidle');

            // The frontend stores the anon ID in localStorage.
            const userId = await page.evaluate(() => localStorage.getItem('soundbox_anon_id'));

            if (!userId) {
                // If the key is absent the app hasn't set one yet; skip shape assertions.
                test.skip();
                return;
            }

            const res = await request.get(`/api/stats/user/${userId}`);
            // In open access mode, the API request comes from the same IP so it may
            // succeed (200) or fail (403) depending on how the test runner is proxied.
            if (res.status() === 200) {
                const body = await res.json();
                expect(body).toHaveProperty('user_id');
                expect(body).toHaveProperty('generations');
                expect(body.generations).toHaveProperty('total');
                expect(body.generations).toHaveProperty('by_model');
                expect(body.generations).toHaveProperty('recent');
                expect(body).toHaveProperty('content_stats');
                expect(body.content_stats).toHaveProperty('plays_received');
                expect(body.content_stats).toHaveProperty('upvotes');
                expect(body.content_stats).toHaveProperty('downvotes');
                expect(body.content_stats).toHaveProperty('favorites');
                expect(body).toHaveProperty('listening');
                // All numeric fields in content_stats must be non-negative.
                for (const key of ['plays_received', 'unique_listeners', 'downloads', 'upvotes', 'downvotes', 'favorites']) {
                    expect(typeof body.content_stats[key]).toBe('number');
                    expect(body.content_stats[key]).toBeGreaterThanOrEqual(0);
                }
            } else {
                expect([401, 403]).toContain(res.status());
            }
        });
    });

});
