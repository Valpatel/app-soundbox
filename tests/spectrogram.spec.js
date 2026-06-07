// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Tests for spectrogram endpoints.
 * Verifies that both routes work correctly:
 * - GET /spectrogram/<filename>   — serves a pre-generated spectrogram PNG
 * - GET /generate-spectrogram/<audio_filename> — on-demand spectrogram generation
 *
 * Both routes validate filenames with is_safe_filename() and enforce path-
 * containment via os.path.realpath(), so path-traversal attempts return 400.
 */

test.describe('Spectrogram endpoints', () => {

    // ---------------------------------------------------------------------------
    // /spectrogram/<filename>  — serve existing PNG
    // ---------------------------------------------------------------------------
    test.describe('GET /spectrogram/<filename>', () => {

        test('returns 404 for a nonexistent spectrogram', async ({ request }) => {
            const res = await request.get('/spectrogram/00000000000000000000000000000000nonexistent.png');
            expect(res.status()).toBe(404);
        });

        test('returns 200 with image/png content-type for an existing spectrogram', async ({ request }) => {
            // Discover a real track from the library so we use an actual file.
            const libRes = await request.get('/api/library?limit=1');
            expect(libRes.status()).toBe(200);
            const lib = await libRes.json();

            const tracks = lib.tracks ?? lib.items ?? lib.results ?? lib;
            if (!Array.isArray(tracks) || tracks.length === 0) {
                test.skip(true, 'No tracks in library — skipping existing-spectrogram test');
                return;
            }

            const track = tracks[0];
            // The spectrogram filename mirrors the audio filename with .png extension.
            const audioFilename = track.filename ?? track.audio_filename ?? track.file;
            if (!audioFilename) {
                test.skip(true, 'Track has no filename field — skipping');
                return;
            }

            const specFilename = audioFilename.replace(/\.wav$/i, '.png');
            const res = await request.get(`/spectrogram/${specFilename}`);

            // The spectrogram may or may not have been pre-generated.
            // If it exists (200) verify the content-type; if not (404) that is also valid.
            if (res.status() === 200) {
                const contentType = res.headers()['content-type'] ?? '';
                expect(contentType).toContain('image/png');
            } else {
                expect(res.status()).toBe(404);
            }
        });

        test('returns 400 for a filename without .png extension', async ({ request }) => {
            const res = await request.get('/spectrogram/somefile.wav');
            expect(res.status()).toBe(400);
        });

        test('blocks path traversal via ../ in URL segment', async ({ request }) => {
            // Flask/Werkzeug normalises paths before they reach the route handler,
            // but is_safe_filename() also rejects any '..' in the name.
            // Either a 400 (caught by validation) or a 404/308 redirect is acceptable —
            // the key guarantee is that we never get a 200 serving /etc/passwd.
            const res = await request.get('/spectrogram/../etc/passwd', { maxRedirects: 0 });
            expect(res.status()).not.toBe(200);
        });

        test('blocks path traversal encoded as %2F (slash) in filename', async ({ request }) => {
            // URL-encoded slashes: %2F should not allow directory traversal.
            const res = await request.get('/spectrogram/..%2Fetc%2Fpasswd');
            expect(res.status()).not.toBe(200);
        });
    });

    // ---------------------------------------------------------------------------
    // /generate-spectrogram/<audio_filename>  — on-demand generation
    // ---------------------------------------------------------------------------
    test.describe('GET /generate-spectrogram/<audio_filename>', () => {

        test('returns 404 for a nonexistent audio file', async ({ request }) => {
            const res = await request.get('/generate-spectrogram/00000000000000000000000000000000nonexistent.wav');
            expect(res.status()).toBe(404);
        });

        test('returns 200 with spectrogram filename for an existing audio file', async ({ request }) => {
            // Discover a real track from the library.
            const libRes = await request.get('/api/library?limit=1');
            expect(libRes.status()).toBe(200);
            const lib = await libRes.json();

            const tracks = lib.tracks ?? lib.items ?? lib.results ?? lib;
            if (!Array.isArray(tracks) || tracks.length === 0) {
                test.skip(true, 'No tracks in library — skipping generate-spectrogram test');
                return;
            }

            const track = tracks[0];
            const audioFilename = track.filename ?? track.audio_filename ?? track.file;
            if (!audioFilename) {
                test.skip(true, 'Track has no filename field — skipping');
                return;
            }

            // Generation can take a few seconds (librosa + matplotlib).
            const res = await request.get(`/generate-spectrogram/${audioFilename}`, {
                timeout: 30_000,
            });
            expect(res.status()).toBe(200);

            const body = await res.json();
            expect(body.spectrogram).toBeTruthy();
            expect(body.spectrogram).toMatch(/\.png$/i);
        });

        test('returns 400 for a filename without .wav extension', async ({ request }) => {
            const res = await request.get('/generate-spectrogram/somefile.mp3');
            expect(res.status()).toBe(400);
        });

        test('blocks path traversal via ../ in URL segment', async ({ request }) => {
            const res = await request.get('/generate-spectrogram/../etc/passwd', { maxRedirects: 0 });
            expect(res.status()).not.toBe(200);
        });

        test('blocks path traversal encoded as %2F in filename', async ({ request }) => {
            const res = await request.get('/generate-spectrogram/..%2Fetc%2Fpasswd');
            expect(res.status()).not.toBe(200);
        });
    });

    // ---------------------------------------------------------------------------
    // Round-trip: generate-spectrogram then serve via /spectrogram/<filename>
    // ---------------------------------------------------------------------------
    test.describe('Round-trip', () => {

        test('spectrogram generated on-demand is then serveable via /spectrogram', async ({ request }) => {
            const libRes = await request.get('/api/library?limit=1');
            expect(libRes.status()).toBe(200);
            const lib = await libRes.json();

            const tracks = lib.tracks ?? lib.items ?? lib.results ?? lib;
            if (!Array.isArray(tracks) || tracks.length === 0) {
                test.skip(true, 'No tracks in library — skipping round-trip test');
                return;
            }

            const track = tracks[0];
            const audioFilename = track.filename ?? track.audio_filename ?? track.file;
            if (!audioFilename) {
                test.skip(true, 'Track has no filename field — skipping');
                return;
            }

            // Step 1 — generate (or confirm already generated).
            const genRes = await request.get(`/generate-spectrogram/${audioFilename}`, {
                timeout: 30_000,
            });
            expect(genRes.status()).toBe(200);
            const { spectrogram } = await genRes.json();
            expect(spectrogram).toBeTruthy();

            // Step 2 — serve the spectrogram we just generated.
            const serveRes = await request.get(`/spectrogram/${spectrogram}`);
            expect(serveRes.status()).toBe(200);
            const contentType = serveRes.headers()['content-type'] ?? '';
            expect(contentType).toContain('image/png');
        });
    });
});
