/**
 * Playwright tests for Library Categorization and Radio Pre-Selection
 *
 * Tests cover:
 * - Category counts in sidebar
 * - Category filtering
 * - Radio station pre-selection
 * - Now-playing preview
 * - API endpoints
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.TEST_URL || 'http://localhost:5309';

test.describe('Category System', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
    });

    test('displays category counts in sidebar', async ({ page }) => {
        // Click Library tab
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        // Expand a genre group to see items (groups are collapsed by default)
        const genreHeader = page.locator('.genre-section-header').first();
        if (await genreHeader.isVisible()) {
            await genreHeader.click();
            await page.waitForTimeout(300);
        }

        // Check that genre count elements exist
        const counts = await page.locator('.genre-count').allTextContents();
        expect(counts.length).toBeGreaterThan(0);

        // Take screenshot of sidebar with counts
        await page.screenshot({
            path: 'test-results/category-counts.png',
            fullPage: true
        });
    });

    test('filters library by category when genre clicked', async ({ page }) => {
        // Click Library tab
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        // Expand the "Ambient & Chill" genre group (contains ambient)
        const ambientGroupHeader = page.locator('.genre-section-header:has-text("Ambient")');
        if (await ambientGroupHeader.isVisible()) {
            await ambientGroupHeader.click();
            await page.waitForTimeout(300);
        }

        // Click Ambient genre
        await page.click('.genre-item[data-genre="ambient"]', { force: true });
        await page.waitForTimeout(500);

        // Check that Ambient is now active
        const ambientItem = page.locator('.genre-item[data-genre="ambient"]');
        await expect(ambientItem).toHaveClass(/active/);

        // Take screenshot of filtered view
        await page.screenshot({
            path: 'test-results/filtered-ambient.png',
            fullPage: true
        });
    });

    test('clears filters when clear button clicked', async ({ page }) => {
        // Click Library tab
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        // Expand the Electronic group first
        const electronicHeader = page.locator('.genre-section-header:has-text("Electronic")');
        if (await electronicHeader.isVisible()) {
            await electronicHeader.click();
            await page.waitForTimeout(300);
        }

        // Click a genre first
        await page.click('.genre-item[data-genre="electronic"]', { force: true });
        await page.waitForTimeout(500);

        // Clear filter button should be visible
        const clearBtn = page.locator('#clear-filter-btn');
        if (await clearBtn.isVisible()) {
            // Click clear
            await clearBtn.click({ force: true });
            await page.waitForTimeout(500);

            // Check that no genre is active
            const activeGenres = await page.locator('.genre-item.active').count();
            expect(activeGenres).toBe(0);
        }
    });

    test('type tabs switch between Music and SFX genres', async ({ page }) => {
        // Click Library tab
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        // Click the SFX type tab
        const sfxTab = page.locator('.type-tab[data-type="audio"]');
        if (await sfxTab.isVisible()) {
            await sfxTab.click();
            await page.waitForTimeout(500);

            // Music genres should be hidden, SFX genres visible
            await expect(sfxTab).toHaveClass(/active/);
        }

        // SFX genres should be visible after switching
        const sfxGenres = page.locator('.sfx-genres');
        await expect(sfxGenres).toBeVisible();

        // Take screenshot
        await page.screenshot({
            path: 'test-results/sfx-genres.png',
            fullPage: true
        });
    });
});

test.describe('API Endpoints', () => {
    test('GET /api/library/category-counts returns counts', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/library/category-counts`);
        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        // Should have category keys
        expect(typeof data).toBe('object');
        expect(Object.keys(data).length).toBeGreaterThan(0);
    });

    test('GET /api/library with category filter works', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/library?category=ambient`);
        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data).toHaveProperty('items');
        expect(data).toHaveProperty('total');
    });

    test('GET /api/library/counts returns type counts', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/library/counts`);
        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data).toHaveProperty('total');
        expect(data).toHaveProperty('music');
        expect(data).toHaveProperty('audio');
    });
});

test.describe('Radio Pre-Selection', () => {
    test('pre-selects Ambient station on page load', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Check Ambient station card has active class
        const ambientCard = page.locator('.station-card.station-ambient');
        await expect(ambientCard).toHaveClass(/active/);

        // Take screenshot
        await page.screenshot({
            path: 'test-results/radio-preselected.png',
            fullPage: true
        });
    });

    test('shows now-playing section or queue after preload', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Wait for preload to complete
        await page.waitForTimeout(2000);

        // Either now-playing or queue should have content
        const queueItems = await page.locator('.queue-item').count();

        // Take screenshot
        await page.screenshot({
            path: 'test-results/now-playing-preview.png',
            fullPage: true
        });

        // Queue should have tracks after preload
        expect(queueItems).toBeGreaterThan(0);
    });

    test('radio page shows full UI on fresh load', async ({ page }) => {
        // Fresh context - new browser context
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(1500);

        // Radio stations should be visible
        const stationCards = await page.locator('.station-card').count();
        expect(stationCards).toBeGreaterThan(0);

        // Ambient should be active
        const ambientCard = page.locator('.station-card.station-ambient');
        await expect(ambientCard).toHaveClass(/active/);

        // Take screenshot
        await page.screenshot({
            path: 'test-results/radio-full-ui.png',
            fullPage: true
        });
    });

    test('clicking station starts playback', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(1000);

        // Click Retro station
        await page.click('.station-card.station-retro', { force: true });
        await page.waitForTimeout(500);

        // Retro should now be active
        const retroCard = page.locator('.station-card.station-retro');
        await expect(retroCard).toHaveClass(/active/);

        // Take screenshot
        await page.screenshot({
            path: 'test-results/station-changed.png',
            fullPage: true
        });
    });

    test('radio queue shows upcoming tracks', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Wait for queue to populate
        await page.waitForTimeout(1000);

        // Queue should be visible
        const queueSection = page.locator('#radio-queue');
        await expect(queueSection).toBeVisible();

        // Should have queue items
        const queueItems = await page.locator('.queue-item').count();
        expect(queueItems).toBeGreaterThan(0);

        // Take screenshot
        await page.screenshot({
            path: 'test-results/radio-queue.png',
            fullPage: true
        });
    });
});

test.describe('Responsive Layout', () => {
    test('large screen layout expands properly', async ({ page }) => {
        // Set large viewport
        await page.setViewportSize({ width: 1920, height: 1080 });
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Click Library tab
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-layout');

        // Take screenshot
        await page.screenshot({
            path: 'test-results/large-screen.png',
            fullPage: true
        });
    });

    test('mobile layout works correctly', async ({ page }) => {
        // Set mobile viewport
        await page.setViewportSize({ width: 375, height: 667 });
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Take screenshot
        await page.screenshot({
            path: 'test-results/mobile-layout.png',
            fullPage: true
        });
    });
});
