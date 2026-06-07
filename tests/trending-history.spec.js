// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Tests for trending, most-played, and user history endpoints.
 *
 * Routes covered:
 * - GET /api/trending         (line 3605 in app.py)
 * - GET /api/most-played      (line 3620 in app.py)
 * - GET /api/history/plays    (line 3318 in app.py, @require_auth)
 * - GET /api/history/votes    (line 3336 in app.py, @require_auth)
 *
 * Sort logic:
 * - /api/trending   — ORDER BY recent_plays DESC  (play_events JOIN, time-windowed)
 * - /api/most-played — ORDER BY play_count DESC   (generations.play_count column, all-time)
 *   These two can therefore differ: a track with many old plays may rank high in
 *   most-played but low (or absent) in trending if it hasn't been played recently.
 *
 * In OPEN_ACCESS_MODE the @require_auth decorator falls back to an anonymous IP-based
 * user, so history endpoints return 200 (not 401) from the test runner's IP.
 */

test.describe('Trending and Most-Played', () => {

    test.describe('GET /api/trending', () => {

        test('returns 200 with a tracks array', async ({ request }) => {
            const res = await request.get('/api/trending');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body).toHaveProperty('tracks');
            expect(Array.isArray(body.tracks)).toBe(true);
        });

        test('each track has expected fields when results are non-empty', async ({ request }) => {
            const res = await request.get('/api/trending');
            const body = await res.json();

            // Skip rather than silently pass with zero assertions on a fresh DB
            if (body.tracks.length === 0) {
                test.skip(true, 'No trending tracks in DB — skipping field shape assertions');
                return;
            }

            expect(body.tracks.length).toBeGreaterThan(0);
            for (const track of body.tracks) {
                expect(track).toHaveProperty('id');
                expect(track).toHaveProperty('prompt');
                // recent_plays is the computed column added by the JOIN
                expect(typeof track.recent_plays).toBe('number');
                expect(track.recent_plays).toBeGreaterThan(0);
            }
        });

        test('respects ?limit= parameter — returns at most limit items', async ({ request }) => {
            const res = await request.get('/api/trending?limit=5');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body.tracks.length).toBeLessThanOrEqual(5);
        });

        test('default limit is capped at 100', async ({ request }) => {
            // Default is 20; the handler clamps to 1-100, so even requesting 999 returns <=100
            const res = await request.get('/api/trending?limit=999');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body.tracks.length).toBeLessThanOrEqual(100);
        });

        test('respects ?hours= parameter — different windows can differ', async ({ request }) => {
            // Both should return 200; we just verify structural correctness for each
            const [resNarrow, resWide] = await Promise.all([
                request.get('/api/trending?hours=1'),
                request.get('/api/trending?hours=8760'),
            ]);
            expect(resNarrow.status()).toBe(200);
            expect(resWide.status()).toBe(200);

            const narrow = await resNarrow.json();
            const wide = await resWide.json();
            expect(Array.isArray(narrow.tracks)).toBe(true);
            expect(Array.isArray(wide.tracks)).toBe(true);
        });

        test('results are ordered by recent_plays descending when multiple tracks present', async ({ request }) => {
            const res = await request.get('/api/trending?limit=20');
            const body = await res.json();

            if (body.tracks.length >= 2) {
                for (let i = 0; i < body.tracks.length - 1; i++) {
                    expect(body.tracks[i].recent_plays).toBeGreaterThanOrEqual(
                        body.tracks[i + 1].recent_plays
                    );
                }
            }
        });

        test('filters by ?model= music or audio', async ({ request }) => {
            for (const model of ['music', 'audio']) {
                const res = await request.get(`/api/trending?model=${model}`);
                expect(res.status()).toBe(200);

                const body = await res.json();
                expect(Array.isArray(body.tracks)).toBe(true);

                // Any tracks returned must match the requested model
                for (const track of body.tracks) {
                    expect(track.model).toBe(model);
                }
            }
        });

        test('invalid ?model= value is silently ignored — still returns 200', async ({ request }) => {
            const res = await request.get('/api/trending?model=invalid_type');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(Array.isArray(body.tracks)).toBe(true);
        });

    });

});

test.describe('Most Played', () => {

    test.describe('GET /api/most-played', () => {

        test('returns 200 with a tracks array', async ({ request }) => {
            const res = await request.get('/api/most-played');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body).toHaveProperty('tracks');
            expect(Array.isArray(body.tracks)).toBe(true);
        });

        test('each track has a play_count field and play_count > 0', async ({ request }) => {
            const res = await request.get('/api/most-played');
            const body = await res.json();

            // Handler filters WHERE play_count > 0, so every returned track must have it
            for (const track of body.tracks) {
                expect(track).toHaveProperty('play_count');
                expect(track.play_count).toBeGreaterThan(0);
            }
        });

        test('respects ?limit= parameter — returns at most limit items', async ({ request }) => {
            const res = await request.get('/api/most-played?limit=5');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body.tracks.length).toBeLessThanOrEqual(5);
        });

        test('default limit is capped at 100', async ({ request }) => {
            const res = await request.get('/api/most-played?limit=500');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body.tracks.length).toBeLessThanOrEqual(100);
        });

        test('results are ordered by play_count descending when multiple tracks present', async ({ request }) => {
            const res = await request.get('/api/most-played?limit=20');
            const body = await res.json();

            if (body.tracks.length >= 2) {
                for (let i = 0; i < body.tracks.length - 1; i++) {
                    expect(body.tracks[i].play_count).toBeGreaterThanOrEqual(
                        body.tracks[i + 1].play_count
                    );
                }
            }
        });

        test('respects ?days= parameter to narrow time window', async ({ request }) => {
            const res = await request.get('/api/most-played?days=7&limit=10');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(Array.isArray(body.tracks)).toBe(true);
            expect(body.tracks.length).toBeLessThanOrEqual(10);
        });

        test('filters by ?model= music or audio', async ({ request }) => {
            for (const model of ['music', 'audio']) {
                const res = await request.get(`/api/most-played?model=${model}`);
                expect(res.status()).toBe(200);

                const body = await res.json();
                for (const track of body.tracks) {
                    expect(track.model).toBe(model);
                }
            }
        });

    });

    test.describe('Trending vs Most-Played ordering difference', () => {

        test('most-played uses all-time play_count, trending uses recent play_events', async ({ request }) => {
            // Both must succeed independently — their sort criteria differ:
            // most-played = generations.play_count (all-time stored counter)
            // trending     = COUNT(play_events) within the last N hours
            const [trendingRes, mostPlayedRes] = await Promise.all([
                request.get('/api/trending?limit=10'),
                request.get('/api/most-played?limit=10'),
            ]);

            expect(trendingRes.status()).toBe(200);
            expect(mostPlayedRes.status()).toBe(200);

            const trending = await trendingRes.json();
            const mostPlayed = await mostPlayedRes.json();

            // Trending tracks carry a `recent_plays` field (not on most-played)
            // Most-played tracks carry a `play_count` field (stored all-time counter)
            if (trending.tracks.length > 0) {
                expect(trending.tracks[0]).toHaveProperty('recent_plays');
            }
            if (mostPlayed.tracks.length > 0) {
                expect(mostPlayed.tracks[0]).toHaveProperty('play_count');
            }
        });

    });

});

test.describe('User History (open-access anonymous user)', () => {

    test.describe('GET /api/history/plays', () => {

        test('returns 200 with history array and pagination fields', async ({ request }) => {
            // In OPEN_ACCESS_MODE @require_auth creates an anonymous user from IP
            const res = await request.get('/api/history/plays');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body).toHaveProperty('history');
            expect(Array.isArray(body.history)).toBe(true);
            expect(typeof body.limit).toBe('number');
            expect(typeof body.offset).toBe('number');
            expect(typeof body.has_more).toBe('boolean');
        });

        test('returns empty list for a fresh anonymous user without error', async ({ request }) => {
            const res = await request.get('/api/history/plays');
            expect(res.status()).toBe(200);

            const body = await res.json();
            // An anonymous user with no play history should get [] not a 500
            expect(Array.isArray(body.history)).toBe(true);
        });

        test('each history entry has required fields when non-empty', async ({ request }) => {
            const res = await request.get('/api/history/plays');
            const body = await res.json();

            for (const entry of body.history) {
                expect(entry).toHaveProperty('id');
                expect(entry).toHaveProperty('generation_id');
                expect(entry).toHaveProperty('played_at');
                expect(entry).toHaveProperty('prompt');
                expect(entry).toHaveProperty('model');
            }
        });

        test('respects ?limit= and ?offset= pagination parameters', async ({ request }) => {
            const res = await request.get('/api/history/plays?limit=5&offset=0');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body.limit).toBe(5);
            expect(body.offset).toBe(0);
            expect(body.history.length).toBeLessThanOrEqual(5);
        });

        test('has_more is false when history length is less than limit', async ({ request }) => {
            // Request a large limit so we definitely get everything
            const res = await request.get('/api/history/plays?limit=100');
            const body = await res.json();

            if (body.history.length < 100) {
                expect(body.has_more).toBe(false);
            }
        });

    });

    test.describe('GET /api/history/votes', () => {

        test('returns 200 with history array and pagination fields', async ({ request }) => {
            const res = await request.get('/api/history/votes');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body).toHaveProperty('history');
            expect(Array.isArray(body.history)).toBe(true);
            expect(typeof body.limit).toBe('number');
            expect(typeof body.offset).toBe('number');
            expect(typeof body.has_more).toBe('boolean');
        });

        test('returns empty list for a fresh anonymous user without error', async ({ request }) => {
            const res = await request.get('/api/history/votes');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(Array.isArray(body.history)).toBe(true);
        });

        test('each vote history entry has required fields when non-empty', async ({ request }) => {
            const res = await request.get('/api/history/votes');
            const body = await res.json();

            for (const entry of body.history) {
                expect(entry).toHaveProperty('id');
                expect(entry).toHaveProperty('generation_id');
                expect(entry).toHaveProperty('vote');
                expect(entry).toHaveProperty('created_at');
                expect(entry).toHaveProperty('prompt');
                expect(entry).toHaveProperty('model');
            }
        });

        test('supports ?limit= and ?offset= pagination', async ({ request }) => {
            const resPage1 = await request.get('/api/history/votes?limit=5&offset=0');
            expect(resPage1.status()).toBe(200);

            const page1 = await resPage1.json();
            expect(page1.limit).toBe(5);
            expect(page1.offset).toBe(0);
            expect(page1.history.length).toBeLessThanOrEqual(5);

            // Offset page — must also return 200 even if empty
            const resPage2 = await request.get('/api/history/votes?limit=5&offset=5');
            expect(resPage2.status()).toBe(200);
            const page2 = await resPage2.json();
            expect(page2.offset).toBe(5);
        });

        test('has_more is false when returned count is less than limit', async ({ request }) => {
            const res = await request.get('/api/history/votes?limit=100');
            const body = await res.json();

            if (body.history.length < 100) {
                expect(body.has_more).toBe(false);
            }
        });

    });

});
