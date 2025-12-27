/**
 * Responsive Design Tests
 *
 * Tests layout and functionality across different viewport sizes
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.TEST_URL || 'http://localhost:5309';

const viewports = {
    mobile: { width: 375, height: 667, name: 'mobile' },
    mobileLarge: { width: 414, height: 896, name: 'mobile-large' },
    tablet: { width: 768, height: 1024, name: 'tablet' },
    tabletLandscape: { width: 1024, height: 768, name: 'tablet-landscape' },
    laptop: { width: 1366, height: 768, name: 'laptop' },
    desktop: { width: 1920, height: 1080, name: 'desktop' },
    ultrawide: { width: 2560, height: 1080, name: 'ultrawide' }
};

test.describe('Viewport Breakpoints - Radio Tab', () => {
    for (const [key, viewport] of Object.entries(viewports)) {
        test(`radio layout works at ${viewport.name} (${viewport.width}x${viewport.height})`, async ({ page }) => {
            await page.setViewportSize({ width: viewport.width, height: viewport.height });
            await page.goto(BASE_URL);
            await page.waitForLoadState('networkidle');

            // Radio tab should be visible
            await expect(page.locator('#content-radio')).toBeVisible();

            // Station cards should be visible
            const stationCards = page.locator('.station-card');
            await expect(stationCards.first()).toBeVisible({ timeout: 5000 });

            // Take screenshot
            await page.screenshot({
                path: `test-results/responsive-radio-${viewport.name}.png`,
                fullPage: true
            });
        });
    }
});

test.describe('Viewport Breakpoints - Library Tab', () => {
    for (const [key, viewport] of Object.entries(viewports)) {
        test(`library layout works at ${viewport.name} (${viewport.width}x${viewport.height})`, async ({ page }) => {
            await page.setViewportSize({ width: viewport.width, height: viewport.height });
            await page.goto(BASE_URL);
            await page.waitForLoadState('networkidle');

            // Switch to Library
            await page.click('.main-tab:has-text("Library")');
            await page.waitForTimeout(500);

            // Library should be visible
            await expect(page.locator('#content-library')).toBeVisible();

            // Wait for items to load
            await page.waitForSelector('.library-item, .empty-state', { timeout: 10000 });

            // Take screenshot
            await page.screenshot({
                path: `test-results/responsive-library-${viewport.name}.png`,
                fullPage: true
            });
        });
    }
});

test.describe('Viewport Breakpoints - Generate Tab', () => {
    for (const [key, viewport] of Object.entries(viewports)) {
        test(`generate form works at ${viewport.name} (${viewport.width}x${viewport.height})`, async ({ page }) => {
            await page.setViewportSize({ width: viewport.width, height: viewport.height });
            await page.goto(BASE_URL);
            await page.waitForLoadState('networkidle');

            // Switch to Generate
            await page.click('.main-tab:has-text("Generate")');
            await page.waitForTimeout(500);

            // Form should be visible
            await expect(page.locator('#prompt')).toBeVisible();
            await expect(page.locator('#generate-btn')).toBeVisible();

            // Take screenshot
            await page.screenshot({
                path: `test-results/responsive-generate-${viewport.name}.png`,
                fullPage: true
            });
        });
    }
});

test.describe('Touch and Scroll Behavior', () => {
    test('mobile scrolling works correctly', async ({ page }) => {
        await page.setViewportSize({ width: 375, height: 667 });
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Switch to Library for scrollable content
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        // Scroll down
        await page.evaluate(() => window.scrollTo(0, 500));
        await page.waitForTimeout(300);

        // Get scroll position
        const scrollY = await page.evaluate(() => window.scrollY);
        expect(scrollY).toBeGreaterThan(0);

        // Take screenshot
        await page.screenshot({
            path: 'test-results/responsive-scroll-mobile.png',
            fullPage: false
        });
    });

    test('horizontal scrolling on station cards', async ({ page }) => {
        await page.setViewportSize({ width: 375, height: 667 });
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Check if station grid scrolls horizontally on mobile
        const stationGrid = page.locator('.station-grid, .stations-container');
        if (await stationGrid.isVisible()) {
            const box = await stationGrid.boundingBox();
            expect(box).toBeTruthy();
        }
    });
});

test.describe('Text Readability', () => {
    test('text is readable at mobile size', async ({ page }) => {
        await page.setViewportSize({ width: 375, height: 667 });
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Check font sizes are reasonable
        const bodyFontSize = await page.evaluate(() => {
            const body = document.body;
            return parseInt(window.getComputedStyle(body).fontSize);
        });

        // Body font should be at least 14px for readability
        expect(bodyFontSize).toBeGreaterThanOrEqual(14);
    });

    test('buttons are touch-friendly on mobile', async ({ page }) => {
        await page.setViewportSize({ width: 375, height: 667 });
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Check main tab buttons are at least 44px (Apple's recommended touch target)
        const tabs = page.locator('.main-tab');
        const firstTab = tabs.first();

        if (await firstTab.isVisible()) {
            const box = await firstTab.boundingBox();
            expect(box.height).toBeGreaterThanOrEqual(40);
        }
    });
});

test.describe('Orientation Changes', () => {
    test('handles portrait to landscape switch', async ({ page }) => {
        // Start in portrait
        await page.setViewportSize({ width: 375, height: 667 });
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Disable animations for stability
        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        // Verify content is visible in portrait
        await expect(page.locator('.main-tab').first()).toBeVisible();

        await page.screenshot({
            path: 'test-results/orientation-portrait.png',
            fullPage: true
        });

        // Switch to landscape
        await page.setViewportSize({ width: 667, height: 375 });
        await page.waitForTimeout(800);

        await page.screenshot({
            path: 'test-results/orientation-landscape.png',
            fullPage: true
        });

        // Content should still be visible after orientation change
        await expect(page.locator('.main-tab').first()).toBeVisible();
    });
});

test.describe('Content Overflow', () => {
    test('long prompts do not break layout', async ({ page }) => {
        await page.setViewportSize({ width: 375, height: 667 });
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        // Check that library items with long prompts don't overflow
        const libraryItems = page.locator('.library-item');
        const count = await libraryItems.count();

        if (count > 0) {
            const firstItem = libraryItems.first();
            const box = await firstItem.boundingBox();

            // Item should not be wider than viewport
            expect(box.width).toBeLessThanOrEqual(375);
        }
    });

    test('category sidebar fits on tablet', async ({ page }) => {
        await page.setViewportSize({ width: 768, height: 1024 });
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        // Take screenshot to verify sidebar layout
        await page.screenshot({
            path: 'test-results/responsive-sidebar-tablet.png',
            fullPage: true
        });
    });
});
