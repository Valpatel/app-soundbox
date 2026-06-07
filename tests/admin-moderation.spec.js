// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Tests for admin moderation API endpoints.
 *
 * Auth model: All three routes use @require_auth + manual is_admin check.
 * In OPEN_ACCESS_MODE (default), anonymous users are created from IP hash.
 * is_admin is only true for localhost requests that are NOT MCP-proxied.
 * Test runner hits port 5309, which IS localhost — so requests from the
 * test runner receive is_admin=true and will reach the handler logic.
 *
 * Endpoints:
 *   GET  /api/admin/moderation          — list items pending moderation
 *   POST /api/admin/moderate/<gen_id>   — moderate a single generation
 *   POST /api/admin/moderate/bulk       — moderate multiple generations
 */

test.describe('Admin Moderation API', () => {

    // -------------------------------------------------------------------------
    // GET /api/admin/moderation
    // -------------------------------------------------------------------------
    test.describe('GET /api/admin/moderation', () => {

        test('returns 200 and expected structure for localhost (admin) requests', async ({ request }) => {
            const res = await request.get('/api/admin/moderation');
            // Localhost requests get is_admin=true, so this should succeed
            expect(res.status()).toBe(200);

            const body = await res.json();
            // Response should be an object (pagination envelope or direct list)
            expect(typeof body).toBe('object');
            expect(body).not.toBeNull();
        });

        test('result contains items array or equivalent list field', async ({ request }) => {
            const res = await request.get('/api/admin/moderation');
            expect(res.status()).toBe(200);

            const body = await res.json();
            // db.get_pending_moderation returns a paginated structure;
            // expect an array under a common key or a top-level array
            const hasItems = Array.isArray(body) ||
                Array.isArray(body.items) ||
                Array.isArray(body.generations) ||
                Array.isArray(body.results);
            expect(hasItems).toBe(true);
        });

        test('supports pagination via page and per_page query params', async ({ request }) => {
            const res = await request.get('/api/admin/moderation?page=1&per_page=5');
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(typeof body).toBe('object');
            expect(body).not.toBeNull();
        });

        test('clamps out-of-range pagination params without error', async ({ request }) => {
            // page=0 should be clamped to 1, per_page=9999 clamped to 100
            const res = await request.get('/api/admin/moderation?page=0&per_page=9999');
            expect(res.status()).toBe(200);
        });

        test('supports model filter query param', async ({ request }) => {
            const res = await request.get('/api/admin/moderation?model=musicgen');
            expect(res.status()).toBe(200);
        });

        // NOTE: X-Forwarded-For spoofing does NOT affect is_localhost_request(),
        // which uses request.remote_addr directly. Test runner connects from localhost,
        // so all admin routes return 200 — there is no reachable 403 path from here.
    });

    // -------------------------------------------------------------------------
    // POST /api/admin/moderate/<gen_id>
    // -------------------------------------------------------------------------
    test.describe('POST /api/admin/moderate/<gen_id>', () => {

        // NOTE: X-Forwarded-For does not affect is_localhost_request() — it uses
        // request.remote_addr. Test runner is localhost, so no 403 path is reachable.

        test('rejects missing Content-Type (non-JSON) even for admin', async ({ request }) => {
            // require_json_content_type() check fires before is_admin check
            const res = await request.post('/api/admin/moderate/abc123def456', {
                headers: { 'Content-Type': 'text/plain' },
                data: 'action=approve',
            });
            // Expect 400 or 415 — not 200
            expect(res.status()).toBeGreaterThanOrEqual(400);
        });

        test('returns 400 for invalid action value', async ({ request }) => {
            const res = await request.post('/api/admin/moderate/abc123def456', {
                headers: { 'Content-Type': 'application/json' },
                data: { action: 'ban' },
            });
            expect(res.status()).toBe(400);

            const body = await res.json();
            expect(body.error).toMatch(/action/i);
        });

        test('returns 400 or 404 for unknown gen_id with valid action', async ({ request }) => {
            // Use a syntactically valid but non-existent ID
            const fakeId = 'deadbeef00000000000000000000000000000000';
            const res = await request.post(`/api/admin/moderate/${fakeId}`, {
                headers: { 'Content-Type': 'application/json' },
                data: { action: 'approve' },
            });
            // Handler returns db.moderate_generation result; if not found it returns
            // {success: false, ...} → 400. Either 400 or 404 is acceptable.
            expect([400, 404]).toContain(res.status());

            const body = await res.json();
            expect(body.success).not.toBe(true);
        });

        test('returns 400 when action field is missing from body', async ({ request }) => {
            const res = await request.post('/api/admin/moderate/abc123def456', {
                headers: { 'Content-Type': 'application/json' },
                data: {},
            });
            expect(res.status()).toBe(400);

            const body = await res.json();
            expect(body.error).toMatch(/action/i);
        });

        test('accepts optional reason field alongside valid action', async ({ request }) => {
            // With a fake (non-existent) gen_id this will still fail at db level,
            // but we expect a 400 (not 500), confirming the body is parsed correctly.
            const fakeId = 'deadbeef00000000000000000000000000000000';
            const res = await request.post(`/api/admin/moderate/${fakeId}`, {
                headers: { 'Content-Type': 'application/json' },
                data: { action: 'reject', reason: 'Inappropriate content' },
            });
            // Should reach db layer (not blocked by validation) → 400 or 404
            expect([400, 404]).toContain(res.status());
        });
    });

    // -------------------------------------------------------------------------
    // POST /api/admin/moderate/bulk
    // -------------------------------------------------------------------------
    test.describe('POST /api/admin/moderate/bulk', () => {

        // NOTE: X-Forwarded-For does not affect is_localhost_request() — it uses
        // request.remote_addr. Test runner is localhost, so no 403 path is reachable.

        test('returns 400 when gen_ids is not an array', async ({ request }) => {
            const res = await request.post('/api/admin/moderate/bulk', {
                headers: { 'Content-Type': 'application/json' },
                data: { gen_ids: 'abc123', action: 'approve' },
            });
            expect(res.status()).toBe(400);

            const body = await res.json();
            expect(body.error).toMatch(/gen_ids/i);
        });

        test('returns 400 when gen_ids array is empty and action is missing', async ({ request }) => {
            const res = await request.post('/api/admin/moderate/bulk', {
                headers: { 'Content-Type': 'application/json' },
                data: { gen_ids: [], action: 'approve' },
            });
            // Empty array passes the list check but db.bulk_moderate should handle it;
            // however action validation fires first — if action is valid, expect 200 or 400
            // depending on db behavior. With action missing, expect 400 from action guard.
            const res2 = await request.post('/api/admin/moderate/bulk', {
                headers: { 'Content-Type': 'application/json' },
                data: { gen_ids: [] },
            });
            expect(res2.status()).toBe(400);
            const body = await res2.json();
            expect(body.error).toMatch(/action/i);
        });

        test('returns 400 when gen_ids exceeds 50 items', async ({ request }) => {
            const tooMany = Array.from({ length: 51 }, (_, i) => `id_${i}`);
            const res = await request.post('/api/admin/moderate/bulk', {
                headers: { 'Content-Type': 'application/json' },
                data: { gen_ids: tooMany, action: 'approve' },
            });
            expect(res.status()).toBe(400);

            const body = await res.json();
            expect(body.error).toMatch(/gen_ids/i);
        });

        test('returns 400 for invalid action value in bulk request', async ({ request }) => {
            const res = await request.post('/api/admin/moderate/bulk', {
                headers: { 'Content-Type': 'application/json' },
                data: { gen_ids: ['abc123'], action: 'hide' },
            });
            expect(res.status()).toBe(400);

            const body = await res.json();
            expect(body.error).toMatch(/action/i);
        });

        test('returns 400 when gen_ids contains non-string elements', async ({ request }) => {
            const res = await request.post('/api/admin/moderate/bulk', {
                headers: { 'Content-Type': 'application/json' },
                data: { gen_ids: [123, 456], action: 'approve' },
            });
            expect(res.status()).toBe(400);

            const body = await res.json();
            expect(body.error).toMatch(/gen_id/i);
        });

        test('accepts all three valid action values without Content-Type error', async ({ request }) => {
            for (const action of ['approve', 'reject', 'delete']) {
                const res = await request.post('/api/admin/moderate/bulk', {
                    headers: { 'Content-Type': 'application/json' },
                    data: { gen_ids: ['nonexistent_id_000'], action },
                });
                // Should reach db layer — not blocked by validation checks
                // Validation passes, so status should not be 400 from action guard
                const body = await res.json();
                const blockedByValidation = res.status() === 400 && body.error && body.error.match(/action/i);
                expect(blockedByValidation).toBeFalsy();
            }
        });
    });
});
