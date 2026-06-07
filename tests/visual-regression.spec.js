// @ts-check
/**
 * Visual Regression Tests
 *
 * Snapshot baselines for the 5 most user-visible pages/states.
 * Run with --update-snapshots to regenerate baselines.
 *
 * Determinism strategy:
 *  - /api/radio/shuffle mocked → fixed 6-track list, no random queue order
 *  - /api/library mocked → fixed 4-item result set
 *  - /api/playlists mocked → fixed 2 playlists
 *  - CSS animations disabled via injected style tag
 *  - networkidle + 500 ms settle before every screenshot
 *  - Timestamps, vote counts, play counts masked
 *  - Visualizer canvas masked (frames are never deterministic)
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.TEST_URL || 'http://localhost:5309';

// ── shared helpers ────────────────────────────────────────────────────────────

/** Kill CSS animations and transitions so layout doesn't shift mid-screenshot. */
async function freezeAnimations(page) {
    await page.addStyleTag({
        content: `
            *, *::before, *::after {
                animation-duration: 0s !important;
                animation-delay: 0s !important;
                transition-duration: 0s !important;
                transition-delay: 0s !important;
            }
        `,
    });
}

/** Mock radio endpoints with a fixed deterministic track list. */
async function mockRadioRoutes(page) {
    const makeTrack = (i) => ({
        id: `aabbccdd${String(i).padStart(2, '0')}ff1122334455667788aabbcc`,
        prompt: `visual regression track ${i}`,
        filename: `vr_track_${i}.wav`,
        duration: 30.0,
        model: i % 2 === 0 ? 'musicgen' : 'audiogen',
        upvotes: i,
        downvotes: 0,
        play_count: i * 2,
        tags: [],
        spectrogram: null,
        created_at: '2026-01-01T00:00:00Z',
    });
    const fakeTracks = Array.from({ length: 6 }, (_, i) => makeTrack(i + 1));
    const body = JSON.stringify({ tracks: fakeTracks });

    for (const pattern of [
        '**/api/radio/shuffle**',
        '**/api/radio/next**',
        '**/api/radio/favorites**',
        '**/api/radio/ambient**',
        '**/api/radio/retro**',
        '**/api/radio/happy**',
        '**/api/radio/lofi**',
    ]) {
        await page.route(pattern, async (route) => {
            await route.fulfill({ status: 200, contentType: 'application/json', body });
        });
    }

    // Stub audio files so <audio> doesn't spam network errors
    await page.route('**/audio/**', async (route) => {
        await route.fulfill({ status: 200, contentType: 'audio/wav', body: '' });
    });
}

/** Mock /api/library with a fixed result set. */
async function mockLibraryRoutes(page) {
    const makeItem = (i) => ({
        id: `aabbccdd${String(i).padStart(2, '0')}ee1122334455667788aabbcc`,
        prompt: `library visual regression item ${i}`,
        filename: `lib_${i}.wav`,
        duration: 15.0 + i,
        model: i % 2 === 0 ? 'musicgen' : 'audiogen',
        upvotes: i * 3,
        downvotes: 0,
        play_count: i * 5,
        tags: [],
        spectrogram: null,
        created_at: '2026-01-02T00:00:00Z',
    });
    const fakeItems = Array.from({ length: 4 }, (_, i) => makeItem(i + 1));

    await page.route('**/api/library**', async (route) => {
        const url = route.request().url();
        // Don't intercept vote or other sub-paths
        if (url.match(/\/api\/library\/[^?]+\/(vote|feedback|suggest-tag|tag-suggestions)/)) {
            await route.continue();
            return;
        }
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                items: fakeItems,
                total: fakeItems.length,
                page: 1,
                per_page: 20,
                has_more: false,
            }),
        });
    });

    await page.route('**/audio/**', async (route) => {
        await route.fulfill({ status: 200, contentType: 'audio/wav', body: '' });
    });
}

/** Mock /api/playlists with a small fixed list. */
async function mockPlaylistRoutes(page) {
    const fakePlaylists = [
        { id: 'pl000001', name: 'My Chill Mix', track_count: 5, created_at: '2026-01-01T00:00:00Z' },
        { id: 'pl000002', name: 'Retro Vibes', track_count: 3, created_at: '2026-01-02T00:00:00Z' },
    ];
    await page.route('**/api/playlists**', async (route) => {
        if (route.request().method() === 'GET') {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ playlists: fakePlaylists }),
            });
        } else {
            await route.continue();
        }
    });
}

// ── common locators to mask ───────────────────────────────────────────────────
// These contain live data (counts, times) that changes between runs.
const DYNAMIC_SELECTORS = [
    '.vote-count',
    '.play-count',
    '.upvotes',
    '.downvotes',
    '[data-vote-count]',
    '.timestamp',
    '.created-at',
    'time',
    '#mini-player',           // may appear if audio is "playing"
    '.toast',                 // audio-error / info toasts are timing-dependent
    '#toast-container',
    '.toast-container',
];

function dynamicMasks(page) {
    return DYNAMIC_SELECTORS.map((sel) => page.locator(sel));
}

// ── screenshot options ────────────────────────────────────────────────────────
const SCREENSHOT_OPTS = (page) => ({
    fullPage: false,
    mask: dynamicMasks(page),
    maxDiffPixelRatio: 0.02,
});

// ── viewport (applied per-test via use: block) ────────────────────────────────
test.use({ viewport: { width: 1280, height: 720 } });

// =============================================================================
// 1. Radio tab — initial load (no track playing)
// =============================================================================
test('radio tab — initial load visual baseline', async ({ page }) => {
    await mockRadioRoutes(page);

    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    await freezeAnimations(page);

    // Radio is the default active tab — just wait for station cards
    await page.waitForSelector('.station-card', { timeout: 10000 });
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('radio-tab-initial.png', {
        ...SCREENSHOT_OPTS(page),
    });
});

// =============================================================================
// 2. Library tab — search results layout
// =============================================================================
test('library tab — search results layout visual baseline', async ({ page }) => {
    await mockLibraryRoutes(page);

    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    await freezeAnimations(page);

    // Switch to Library tab
    await page.click('.main-tab:has-text("Library")');
    await page.waitForSelector('#content-library', { state: 'visible', timeout: 8000 });

    // Wait for mocked items to render
    await page.waitForSelector('.library-item', { timeout: 10000 });
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('library-tab-results.png', {
        ...SCREENSHOT_OPTS(page),
    });
});

// =============================================================================
// 3. Generate tab — form layout
// =============================================================================
test('generate tab — form layout visual baseline', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    await freezeAnimations(page);

    // Switch to Generate tab
    await page.click('.main-tab:has-text("Generate")');
    await page.waitForSelector('#content-generate', { state: 'visible', timeout: 8000 });
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('generate-tab-form.png', {
        ...SCREENSHOT_OPTS(page),
    });
});

// =============================================================================
// 4. Fullscreen visualizer — bars mode, canvas masked
// =============================================================================
// FIXME: The fullscreen overlay is rendered as a fixed/absolute element that
// fills the entire Chromium headless viewport and is dominated by its
// <canvas> element. Masking the canvas (the only meaningful content) produces
// a solid magenta rectangle — not a useful baseline.
//
// To make this deterministic we would need the fullscreen widget to expose a
// non-canvas UI layer that can be screenshotted independently, or to clip to
// the HUD controls strip. Marking fixme until that work is done.
test.fixme('fullscreen visualizer — bars mode visual baseline', async ({ page }) => {
    await mockRadioRoutes(page);

    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    await freezeAnimations(page);

    // Click a station to load a track so the fullscreen button becomes enabled
    const stationCard = page.locator('.station-card').first();
    await stationCard.waitFor({ state: 'visible', timeout: 10000 });
    await stationCard.click();

    // Wait for now-playing to appear (track loaded)
    await page.waitForFunction(() => {
        const np = document.getElementById('now-playing');
        return np && !np.classList.contains('hidden');
    }, { timeout: 15000 });

    // Open fullscreen via JS (avoids native fullscreen API, which headless blocks)
    await page.evaluate(() => {
        // Create and inject the fullscreen container directly, bypassing
        // requestFullscreen() which is blocked in headless Chromium.
        if (typeof enterRadioFullscreen === 'function') {
            // Prevent actual requestFullscreen so the overlay renders in-page
            const origRFS = Element.prototype.requestFullscreen;
            Element.prototype.requestFullscreen = () => Promise.resolve();
            enterRadioFullscreen();
            Element.prototype.requestFullscreen = origRFS;
        }
    });

    // Wait for the fullscreen container to appear
    await page.waitForSelector('#fullscreen-radio-container', { timeout: 8000 });
    await page.waitForTimeout(800); // Let visualizer initialize

    // Mask the canvas — animation frames are never deterministic pixel-by-pixel
    const canvasMask = page.locator('#fullscreen-radio-container canvas');

    await expect(page).toHaveScreenshot('fullscreen-visualizer-bars.png', {
        fullPage: false,
        mask: [...dynamicMasks(page), canvasMask],
        maxDiffPixelRatio: 0.02,
    });
});

// =============================================================================
// 5. Playlists tab — layout with mocked playlists
// =============================================================================
test('playlists tab — layout visual baseline', async ({ page }) => {
    await mockPlaylistRoutes(page);

    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    await freezeAnimations(page);

    // Switch to Playlists tab
    await page.click('#tab-playlists');
    await page.waitForSelector('#content-playlists', { state: 'visible', timeout: 8000 });
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('playlists-tab.png', {
        ...SCREENSHOT_OPTS(page),
    });
});
