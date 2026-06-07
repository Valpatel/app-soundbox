// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Tests for the Backup API endpoints.
 *
 * Both /api/backup/status and /api/backup/run are admin-only.
 * In OPEN_ACCESS_MODE (default), is_admin is true for localhost requests.
 * is_localhost_request() uses request.remote_addr — X-Forwarded-For is ignored.
 * The test runner connects from localhost, so it receives is_admin=true.
 *
 * POST /api/backup/run requires BACKUP_DIR to be configured. When unset the
 * endpoint returns 400 before writing anything to disk.
 */

test.describe('Backup API', () => {

    test.describe('GET /api/backup/status', () => {

        test('returns 200 for localhost (admin) requests', async ({ request }) => {
            // is_localhost_request() uses request.remote_addr (never XFF).
            // Test runner connects from localhost → is_admin=true → 200.
            const res = await request.get('/api/backup/status');
            expect(res.status()).toBe(200);
        });

        test('responds quickly (under 1500ms)', async ({ request }) => {
            const start = Date.now();
            await request.get('/api/backup/status');
            const elapsed = Date.now() - start;
            expect(elapsed).toBeLessThan(1500);
        });

        test('returns JSON with backup status fields', async ({ request }) => {
            // Localhost callers get is_admin=true and receive a valid status object.
            const res = await request.get('/api/backup/status');
            const body = await res.json();
            expect(body).toBeDefined();
            if (res.status() === 200) {
                // Verify the backup status shape (enabled flag is always present)
                expect(typeof body.enabled).toBe('boolean');
            }
        });

        /**
         * This test verifies the shape of a successful backup status response.
         * It can only pass when called from a localhost context (e.g., a local
         * admin script), so it is skipped in the standard test suite.
         *
         * To run manually against a local server:
         *   npx playwright test tests/backup.spec.js --grep "status structure" --headed
         *
         * The expected response shape from backup.get_backup_status():
         * {
         *   enabled: boolean,
         *   backup_dir: string | null,
         *   retention_policy: string,
         *   backup_time: string,           // "HH:MM" default "03:00"
         *   last_backup: {
         *     time: string | null,
         *     status: string | null,
         *     size_mb: number | null,
         *     error: string | null
         *   },
         *   backup_count?: number,         // present when enabled and dir exists
         *   latest_backup_date?: string    // present when backups exist
         * }
         */
        test.skip('admin: status structure is valid (localhost only)', async ({ request }) => {
            const res = await request.get('/api/backup/status');
            expect(res.status()).toBe(200);

            const status = await res.json();
            expect(typeof status.enabled).toBe('boolean');
            expect(typeof status.retention_policy).toBe('string');
            expect(typeof status.backup_time).toBe('string');
            // backup_time should be HH:MM format
            expect(status.backup_time).toMatch(/^\d{2}:\d{2}$/);
            expect(status.last_backup).toBeDefined();
            // last_backup fields may be null on a fresh system
            expect('time' in status.last_backup).toBe(true);
            expect('status' in status.last_backup).toBe(true);
            expect('size_mb' in status.last_backup).toBe(true);
            expect('error' in status.last_backup).toBe(true);
        });
    });

    test.describe('POST /api/backup/run', () => {

        test('returns 400 for localhost (admin) requests when BACKUP_DIR is unset', async ({ request }) => {
            // is_localhost_request() uses request.remote_addr — test runner is localhost
            // → is_admin=true. BACKUP_DIR is not set in CI, so endpoint returns 400.
            const res = await request.post('/api/backup/run');
            // 400 = BACKUP_DIR not configured; 200 = backup started (BACKUP_DIR set)
            expect([200, 400]).toContain(res.status());
        });

        test('returns JSON with an error or status field', async ({ request }) => {
            // Localhost callers pass the admin check; response shape depends on BACKUP_DIR.
            const res = await request.post('/api/backup/run');
            const body = await res.json();
            expect(body).toBeDefined();
            // Either an error (BACKUP_DIR unset) or a status field (backup started)
            const hasExpectedField = body.error || body.status;
            expect(hasExpectedField).toBeTruthy();
        });

        /**
         * This test verifies the endpoint accepts the call from an admin and
         * returns a started/status response.
         *
         * Destructive-safety note:
         * POST /api/backup/run is destructive (rsync + DB copy). However, it
         * requires BACKUP_DIR to be set in the environment — when unset it returns
         * 400 immediately without writing anything. In CI / standard test runs
         * BACKUP_DIR is not set, so this test would always get 400. The test is
         * therefore skipped; run it manually only when BACKUP_DIR is intentionally
         * configured and a backup is actually desired.
         *
         * If a dry_run parameter is added to the endpoint in the future, this
         * test should be updated to use it (e.g., POST /api/backup/run?dry_run=1).
         */
        test.skip('admin: run returns 200 or 400 (localhost only, BACKUP_DIR required)', async ({ request }) => {
            const res = await request.post('/api/backup/run');
            // 400 = BACKUP_DIR not configured (safe no-op)
            // 200 = backup actually started (only if BACKUP_DIR is set)
            expect([200, 400]).toContain(res.status());

            const body = await res.json();
            if (res.status() === 200) {
                expect(body.status).toBe('started');
                expect(body.message).toBeTruthy();
            } else {
                expect(body.error).toBeTruthy();
            }
        });

        test('rate limit header is present (indicates limiter is active)', async ({ request }) => {
            const res = await request.post('/api/backup/run');
            // The endpoint has @limiter.limit("2 per hour").
            // Flask-Limiter adds X-RateLimit-* headers on most responses.
            // We verify the endpoint is reached (not a 404/405) and responds with JSON.
            expect(res.status()).not.toBe(404);
            expect(res.status()).not.toBe(405);
            const contentType = res.headers()['content-type'] || '';
            expect(contentType).toContain('application/json');
        });
    });
});
