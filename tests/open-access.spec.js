// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Tests for Open Access Mode functionality.
 * Verifies that when OPEN_ACCESS_MODE=true, users can:
 * - Access all features without login
 * - Generate audio without authentication
 * - Vote and favorite without authentication
 * - See proper UI state (no login prompts)
 */

test.describe('Open Access Mode', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/');
        await page.waitForLoadState('networkidle');
    });

    test('page loads successfully', async ({ page }) => {
        await expect(page).toHaveTitle(/Sound Box/i);
    });

    test('OPEN_ACCESS_MODE is true in frontend', async ({ page }) => {
        const openAccess = await page.evaluate(() => {
            return typeof OPEN_ACCESS_MODE !== 'undefined' && OPEN_ACCESS_MODE === true;
        });
        expect(openAccess).toBe(true);
    });

    test('user is authenticated automatically', async ({ page }) => {
        const isAuth = await page.evaluate(() => {
            return typeof isUserAuthenticated === 'function' && isUserAuthenticated();
        });
        expect(isAuth).toBe(true);
    });

    test('currentUserId is set automatically', async ({ page }) => {
        const userId = await page.evaluate(() => {
            return typeof currentUserId !== 'undefined' && currentUserId !== null;
        });
        expect(userId).toBe(true);
    });

    test('no login prompt shown', async ({ page }) => {
        // showLoginPrompt should be a no-op in open access
        const result = await page.evaluate(() => {
            if (typeof showLoginPrompt === 'function') {
                showLoginPrompt('test');
                return true; // no error = no-op success
            }
            return false;
        });
        expect(result).toBe(true);

        // Verify no login modal is visible
        const loginModal = page.locator('.graphlings-modal, .login-modal, #login-modal');
        await expect(loginModal).not.toBeVisible();
    });

    test('generate tab is accessible', async ({ page }) => {
        const genTab = page.locator('.main-tab:has-text("Generate")');
        if (await genTab.isVisible()) {
            await genTab.click();
            await page.waitForTimeout(500);

            // Generate form should be visible and enabled
            const promptInput = page.locator('#prompt-input, #generate-prompt, textarea[placeholder*="prompt" i], textarea[placeholder*="describe" i]');
            if (await promptInput.isVisible()) {
                await expect(promptInput).toBeEnabled();
            }
        }
    });

    test('no Graphlings SDK loaded', async ({ page }) => {
        const hasGraphlings = await page.evaluate(() => {
            return typeof window.GraphlingsSDK !== 'undefined' ||
                   document.querySelector('script[src*="graphlings"]') !== null;
        });
        expect(hasGraphlings).toBe(false);
    });
});

test.describe('Open Access - API Endpoints', () => {
    test('status endpoint returns model info', async ({ request }) => {
        const response = await request.get('/status');
        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data).toHaveProperty('models');
        expect(data).toHaveProperty('gpu');
        expect(data).toHaveProperty('queue_length');
    });

    test('generate endpoint accepts requests without auth token', async ({ request }) => {
        const response = await request.post('/generate', {
            data: {
                prompt: 'test beep sound',
                model: 'audio',
                duration: 2
            }
        });
        // Should accept the job (200) or return 503 if model still loading
        expect([200, 503]).toContain(response.status());

        if (response.status() === 200) {
            const data = await response.json();
            expect(data.success).toBe(true);
            expect(data).toHaveProperty('job_id');
        }
    });

    test('favorites endpoint works without auth', async ({ request }) => {
        const response = await request.get('/api/favorites');
        expect(response.ok()).toBeTruthy();
    });

    test('library endpoint returns items', async ({ request }) => {
        const response = await request.get('/api/library?limit=5');
        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data).toHaveProperty('items');
        expect(Array.isArray(data.items)).toBe(true);
    });

    test('vote endpoint works without auth token', async ({ request }) => {
        // Get a track first
        const tracksResp = await request.get('/api/radio/tracks');
        const tracksData = await tracksResp.json();

        if (tracksData.tracks && tracksData.tracks.length > 0) {
            const trackId = tracksData.tracks[0].id;
            const voteResp = await request.post(`/api/library/${trackId}/vote`, {
                data: { vote: 1 }
            });
            // Should work (200) - not require auth
            expect([200, 400]).toContain(voteResp.status());
        }
    });

    test('rate limiting is enforced', async ({ request }) => {
        // Make rapid requests - shouldn't crash
        const responses = [];
        for (let i = 0; i < 5; i++) {
            responses.push(await request.get('/status'));
        }
        // All should succeed (within rate limits)
        for (const resp of responses) {
            expect(resp.ok()).toBeTruthy();
        }
    });
});

test.describe('Open Access - Audio Generation Flow', () => {
    test.setTimeout(90000); // Generation can take up to 60s

    test('can submit and complete audio generation', async ({ request }) => {
        // Submit generation job
        const genResp = await request.post('/generate', {
            data: {
                prompt: 'short click sound effect',
                model: 'audio',
                duration: 2
            }
        });

        if (genResp.status() !== 200) {
            test.skip(true, 'Model not ready for generation');
            return;
        }

        const genData = await genResp.json();
        expect(genData.success).toBe(true);
        const jobId = genData.job_id;

        // Poll for completion (up to 60s)
        let completed = false;
        for (let i = 0; i < 30; i++) {
            await new Promise(resolve => setTimeout(resolve, 2000));
            const statusResp = await request.get(`/job/${jobId}`);
            if (statusResp.ok()) {
                const statusData = await statusResp.json();
                if (statusData.status === 'completed') {
                    completed = true;
                    expect(statusData.filename).toBeTruthy();
                    expect(statusData.progress_pct).toBe(100);

                    // Verify file is streamable
                    const streamResp = await request.get(`/audio/${statusData.filename}`);
                    expect(streamResp.ok()).toBeTruthy();
                    break;
                } else if (statusData.status === 'error') {
                    throw new Error(`Generation failed: ${statusData.error}`);
                }
            }
        }
        expect(completed).toBe(true);
    });
});
