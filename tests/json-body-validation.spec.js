// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Tests for JSON body validation on routes that previously called
 * `request.get_json()` (without silent=True) and would raise 415/500
 * when a client sent a non-JSON body (e.g. Content-Type: text/plain).
 *
 * After the fix, every one of these routes returns 400 with the shape
 * `{ error: "invalid_body", message: "..." }`.
 *
 * Each test below targets exactly one of the eight routes that were fixed.
 */

// A well-formed 32-char hex generation ID that passes is_valid_gen_id()
// but is unlikely to exist in the DB. The body validation runs after the
// hex check (for suggest-tag / cancel-tag) but before any DB lookup, so
// the 400 invalid_body response fires regardless of existence.
const VALID_HEX_GEN_ID = 'deadbeef' + '0'.repeat(24);

// A plausible playlist_id format (pl_ + 12 hex). Routing accepts any
// string here; auth + body validation both run before the DB lookup so
// no real playlist needs to exist.
const PLAYLIST_ID = 'pl_' + 'a'.repeat(12);

// Body the client mistakenly sends: plain text, not JSON.
const NON_JSON_BODY = 'this is not json {{{';
const TEXT_PLAIN_HEADERS = { 'Content-Type': 'text/plain' };

/**
 * Shared assertion: response must be 400 (not 415, not 500), and the body
 * must be JSON with `error === 'invalid_body'`.
 */
async function expectInvalidBody(res) {
    expect(res.status(), `expected 400 invalid_body but got ${res.status()}`).toBe(400);
    const body = await res.json();
    expect(body.error).toBe('invalid_body');
    expect(typeof body.message).toBe('string');
}

test.describe('JSON body validation - non-JSON content-type returns 400', () => {
    test('POST /api/library/<gen_id>/suggest-tag rejects text/plain body', async ({ request }) => {
        const res = await request.post(`/api/library/${VALID_HEX_GEN_ID}/suggest-tag`, {
            headers: TEXT_PLAIN_HEADERS,
            data: NON_JSON_BODY,
        });
        await expectInvalidBody(res);
    });

    test('POST /api/library/<gen_id>/cancel-tag rejects text/plain body', async ({ request }) => {
        const res = await request.post(`/api/library/${VALID_HEX_GEN_ID}/cancel-tag`, {
            headers: TEXT_PLAIN_HEADERS,
            data: NON_JSON_BODY,
        });
        await expectInvalidBody(res);
    });

    test('POST /api/playlists rejects text/plain body', async ({ request }) => {
        const res = await request.post('/api/playlists', {
            headers: TEXT_PLAIN_HEADERS,
            data: NON_JSON_BODY,
        });
        await expectInvalidBody(res);
    });

    test('PUT /api/playlists/<id> rejects text/plain body', async ({ request }) => {
        const res = await request.put(`/api/playlists/${PLAYLIST_ID}`, {
            headers: TEXT_PLAIN_HEADERS,
            data: NON_JSON_BODY,
        });
        await expectInvalidBody(res);
    });

    test('POST /api/playlists/<id>/tracks rejects text/plain body', async ({ request }) => {
        const res = await request.post(`/api/playlists/${PLAYLIST_ID}/tracks`, {
            headers: TEXT_PLAIN_HEADERS,
            data: NON_JSON_BODY,
        });
        await expectInvalidBody(res);
    });

    test('PUT /api/playlists/<id>/reorder rejects text/plain body', async ({ request }) => {
        const res = await request.put(`/api/playlists/${PLAYLIST_ID}/reorder`, {
            headers: TEXT_PLAIN_HEADERS,
            data: NON_JSON_BODY,
        });
        await expectInvalidBody(res);
    });

    test('POST /api/track/<id>/play rejects text/plain body', async ({ request }) => {
        const res = await request.post(`/api/track/${VALID_HEX_GEN_ID}/play`, {
            headers: TEXT_PLAIN_HEADERS,
            data: NON_JSON_BODY,
        });
        await expectInvalidBody(res);
    });

    test('POST /api/tts/generate rejects text/plain body', async ({ request }) => {
        const res = await request.post('/api/tts/generate', {
            headers: TEXT_PLAIN_HEADERS,
            data: NON_JSON_BODY,
        });
        await expectInvalidBody(res);
    });
});
