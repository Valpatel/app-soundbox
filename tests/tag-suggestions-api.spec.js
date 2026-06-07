// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * API tests for tag suggestion endpoints.
 * UI interaction tests for the tag-suggestion modal are in modal-interactions.spec.js.
 *
 * Endpoints:
 *   GET  /api/library/<gen_id>/tag-suggestions  — list pending suggestions
 *   POST /api/library/<gen_id>/suggest-tag      — submit a suggestion
 *   POST /api/library/<gen_id>/cancel-tag       — cancel own suggestion
 *
 * Note: suggest-tag validates gen_id via is_valid_gen_id() and also validates
 * that the category exists in the known category lists (MUSIC/SFX/SPEECH).
 * cancel-tag skips the gen_id format check — it will return 400 for missing
 * category but proceed to the DB lookup for any gen_id format.
 */

// A well-formed but nonexistent generation ID (32 hex chars)
const FAKE_GEN_ID = 'deadbeef00000000cafebabe11223344';

// An invalid gen_id that fails the hex regex
const MALFORMED_GEN_ID = 'not-a-valid-id!!';

// A valid category name that exists in MUSIC_CATEGORIES
const VALID_CATEGORY = 'electronic';

test.describe('Tag Suggestions API', () => {

    // -------------------------------------------------------------------------
    // GET /api/library/<gen_id>/tag-suggestions
    // -------------------------------------------------------------------------
    test.describe('GET tag-suggestions', () => {

        test('returns 404 for nonexistent gen_id', async ({ request }) => {
            const res = await request.get(`/api/library/${FAKE_GEN_ID}/tag-suggestions`);
            expect(res.status()).toBe(404);
            const body = await res.json();
            expect(body.error).toBeTruthy();
        });

        test('returns valid structure for a known gen_id (skips if library is empty)', async ({ request }) => {
            // Fetch a real track from the library
            const libraryRes = await request.get('/api/library?limit=1');
            expect(libraryRes.status()).toBe(200);
            const library = await libraryRes.json();

            const items = library.items ?? library.generations ?? library.tracks ?? [];
            if (items.length === 0) {
                test.skip(true, 'Library is empty — skipping live gen_id test');
                return;
            }

            const genId = items[0].id;
            const res = await request.get(`/api/library/${genId}/tag-suggestions`);
            expect(res.status()).toBe(200);

            const body = await res.json();
            // Top-level keys required by the handler
            expect(body).toHaveProperty('suggestions');
            expect(body).toHaveProperty('user_suggestions');
            expect(body).toHaveProperty('current_categories');
            expect(body).toHaveProperty('threshold');

            // suggestions is grouped by action: {add: {...}, remove: {...}}
            expect(body.suggestions).toHaveProperty('add');
            expect(body.suggestions).toHaveProperty('remove');

            // user_suggestions mirrors same structure
            expect(body.user_suggestions).toHaveProperty('add');
            expect(body.user_suggestions).toHaveProperty('remove');

            // current_categories is an array
            expect(Array.isArray(body.current_categories)).toBe(true);

            // threshold should be a positive integer (default 3)
            expect(typeof body.threshold).toBe('number');
            expect(body.threshold).toBeGreaterThan(0);
        });

    });

    // -------------------------------------------------------------------------
    // POST /api/library/<gen_id>/suggest-tag — input validation
    // -------------------------------------------------------------------------
    test.describe('POST suggest-tag — validation', () => {

        test('rejects missing body with 400', async ({ request }) => {
            const res = await request.post(`/api/library/${FAKE_GEN_ID}/suggest-tag`, {
                data: '',
                headers: { 'Content-Type': 'application/json' },
            });
            expect(res.status()).toBe(400);
            const body = await res.json();
            expect(body.error).toBeTruthy();
        });

        test('rejects body without category field with 400', async ({ request }) => {
            const res = await request.post(`/api/library/${FAKE_GEN_ID}/suggest-tag`, {
                data: { action: 'add' },
            });
            expect(res.status()).toBe(400);
            const body = await res.json();
            expect(body.error).toMatch(/category/i);
        });

        test('rejects invalid action value with 400', async ({ request }) => {
            const res = await request.post(`/api/library/${FAKE_GEN_ID}/suggest-tag`, {
                data: { category: VALID_CATEGORY, action: 'badaction' },
            });
            expect(res.status()).toBe(400);
            const body = await res.json();
            expect(body.error).toMatch(/action/i);
        });

        test('rejects malformed gen_id (hex validation) with 400', async ({ request }) => {
            const res = await request.post(`/api/library/${MALFORMED_GEN_ID}/suggest-tag`, {
                data: { category: VALID_CATEGORY },
            });
            expect(res.status()).toBe(400);
            const body = await res.json();
            expect(body.error).toMatch(/invalid.*generation.*id/i);
        });

        test('rejects unknown category with 400', async ({ request }) => {
            // Need a valid hex gen_id so we get past the ID check
            const res = await request.post(`/api/library/${FAKE_GEN_ID}/suggest-tag`, {
                data: { category: 'totally_made_up_category_xyz' },
            });
            // suggest-tag validates category via db.submit_tag_suggestion before
            // hitting the DB, so this should fail with 400
            expect(res.status()).toBe(400);
            const body = await res.json();
            expect(body.error ?? body.message).toBeTruthy();
        });

        test('returns 200 (or 400 "not found") for valid body with existing gen_id', async ({ request }) => {
            // Fetch a real track so we can attempt a valid suggestion
            const libraryRes = await request.get('/api/library?limit=1');
            expect(libraryRes.status()).toBe(200);
            const library = await libraryRes.json();
            const items = library.items ?? library.generations ?? library.tracks ?? [];

            if (items.length === 0) {
                test.skip(true, 'Library is empty — skipping live suggest-tag test');
                return;
            }

            const genId = items[0].id;
            const res = await request.post(`/api/library/${genId}/suggest-tag`, {
                data: { category: VALID_CATEGORY, action: 'add' },
            });

            // 200 = suggestion recorded (or consensus reached)
            // 400 = category already applied, or user already suggested this
            // Both are valid outcomes; what matters is the response is well-formed
            expect([200, 400]).toContain(res.status());
            const body = await res.json();
            if (res.status() === 200) {
                expect(body).toHaveProperty('success', true);
                expect(body).toHaveProperty('message');
            } else {
                expect(body.error ?? body.message).toBeTruthy();
            }
        });

    });

    // -------------------------------------------------------------------------
    // POST /api/library/<gen_id>/cancel-tag — validation
    // -------------------------------------------------------------------------
    test.describe('POST cancel-tag — validation', () => {

        test('rejects missing body with 400', async ({ request }) => {
            const res = await request.post(`/api/library/${FAKE_GEN_ID}/cancel-tag`, {
                data: '',
                headers: { 'Content-Type': 'application/json' },
            });
            expect(res.status()).toBe(400);
            const body = await res.json();
            expect(body.error).toBeTruthy();
        });

        test('rejects body without category field with 400', async ({ request }) => {
            const res = await request.post(`/api/library/${FAKE_GEN_ID}/cancel-tag`, {
                data: { action: 'add' },
            });
            expect(res.status()).toBe(400);
            const body = await res.json();
            expect(body.error).toMatch(/category/i);
        });

        test('rejects invalid action value with 400', async ({ request }) => {
            const res = await request.post(`/api/library/${FAKE_GEN_ID}/cancel-tag`, {
                data: { category: VALID_CATEGORY, action: 'notvalid' },
            });
            expect(res.status()).toBe(400);
            const body = await res.json();
            expect(body.error).toMatch(/action/i);
        });

        test('returns 400 for nonexistent suggestion (no prior vote)', async ({ request }) => {
            // cancel-tag returns success:false when no matching suggestion row exists
            const res = await request.post(`/api/library/${FAKE_GEN_ID}/cancel-tag`, {
                data: { category: VALID_CATEGORY, action: 'add' },
            });
            // db.cancel_tag_suggestion returns {success: false, message: 'Suggestion not found'}
            // which causes the handler to return 400
            expect(res.status()).toBe(400);
            const body = await res.json();
            expect(body.message ?? body.error).toMatch(/not found/i);
        });

    });

    // -------------------------------------------------------------------------
    // Hex validation across all three endpoints
    // -------------------------------------------------------------------------
    test.describe('gen_id hex validation', () => {

        test('GET tag-suggestions: malformed gen_id returns 404 (DB miss, no format check)', async ({ request }) => {
            // GET handler does NOT call is_valid_gen_id(); it just queries the DB
            // so a malformed ID will simply miss in the DB and return 404
            const res = await request.get(`/api/library/${MALFORMED_GEN_ID}/tag-suggestions`);
            // Flask may also 404 the route itself for special chars — either is fine
            expect([400, 404]).toContain(res.status());
        });

        test('POST suggest-tag: malformed gen_id rejected with 400 before DB hit', async ({ request }) => {
            const res = await request.post(`/api/library/${MALFORMED_GEN_ID}/suggest-tag`, {
                data: { category: VALID_CATEGORY },
            });
            expect(res.status()).toBe(400);
            const body = await res.json();
            expect(body.error).toMatch(/invalid.*id/i);
        });

        test('POST cancel-tag: malformed gen_id with valid body — 400 due to missing suggestion', async ({ request }) => {
            // cancel-tag skips is_valid_gen_id, goes straight to DB; no row → 400
            const res = await request.post(`/api/library/${MALFORMED_GEN_ID}/cancel-tag`, {
                data: { category: VALID_CATEGORY },
            });
            // Route may not even match if Flask rejects path chars, yielding 404
            expect([400, 404]).toContain(res.status());
        });

    });

    // -------------------------------------------------------------------------
    // Round-trip: suggest then cancel (requires live library entry)
    // -------------------------------------------------------------------------
    test.describe('suggest → cancel round-trip', () => {

        test('suggest-tag followed by cancel-tag removes the suggestion', async ({ request }) => {
            const libraryRes = await request.get('/api/library?limit=1');
            expect(libraryRes.status()).toBe(200);
            const library = await libraryRes.json();
            const items = library.items ?? library.generations ?? library.tracks ?? [];

            if (items.length === 0) {
                test.skip(true, 'Library is empty — skipping round-trip test');
                return;
            }

            const genId = items[0].id;

            // Step 1: suggest (may already exist from a prior test run; that is fine)
            const suggestRes = await request.post(`/api/library/${genId}/suggest-tag`, {
                data: { category: VALID_CATEGORY, action: 'add' },
            });
            // 200 = newly recorded; 400 with "already suggested" or "already applied"
            // We can only cancel if suggestion was newly recorded (200)
            if (suggestRes.status() !== 200) {
                // Suggestion already present from a previous run; skip round-trip
                const msg = (await suggestRes.json()).message ?? '';
                test.skip(msg.includes('already'), 'Suggestion already exists from prior run');
                return;
            }

            const suggestBody = await suggestRes.json();
            expect(suggestBody.success).toBe(true);

            // Step 2: cancel it
            const cancelRes = await request.post(`/api/library/${genId}/cancel-tag`, {
                data: { category: VALID_CATEGORY, action: 'add' },
            });
            expect(cancelRes.status()).toBe(200);
            const cancelBody = await cancelRes.json();
            expect(cancelBody.success).toBe(true);
            expect(cancelBody.message).toMatch(/canceled/i);
        });

    });

});
