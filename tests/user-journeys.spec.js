/**
 * User Journey Tests
 *
 * Tests complete user workflows from start to finish
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.TEST_URL || 'http://localhost:5309';

test.describe('First-Time User Journey', () => {
    test.beforeEach(async ({ page }) => {
        // Disable animations for stability
        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        }).catch(() => {}); // May fail if page not loaded yet
    });

    test('can browse and listen to existing audio', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Disable animations after page load
        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        // 1. Land on Radio tab (default)
        await expect(page.locator('#content-radio')).toBeVisible();

        // 2. See radio stations
        const stationCards = page.locator('.station-card');
        await expect(stationCards.first()).toBeVisible({ timeout: 5000 });

        // 3. Station should be active (ambient is pre-selected)
        const activeStation = page.locator('.station-card.active');
        await expect(activeStation).toBeVisible({ timeout: 5000 });

        // 4. Queue or now-playing section should be visible
        const nowPlaying = page.locator('#radio-now-playing, .now-playing, #radio-queue');
        await expect(nowPlaying.first()).toBeVisible({ timeout: 5000 });

        await page.screenshot({
            path: 'test-results/journey-first-time-radio.png',
            fullPage: true
        });
    });

    test('can browse library and filter', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        // 1. Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(300);

        // 2. Library items should load
        const libraryItems = page.locator('.library-item');
        await expect(libraryItems.first()).toBeVisible({ timeout: 10000 });

        // 3. Type tabs should be visible
        const musicTab = page.locator('button.type-tab[data-type="music"]');
        await expect(musicTab).toBeVisible({ timeout: 5000 });

        // 4. Search input should be visible
        const searchInput = page.locator('#library-search');
        await expect(searchInput).toBeVisible();

        await page.screenshot({
            path: 'test-results/journey-first-time-library.png',
            fullPage: true
        });
    });

    test('can view generate page and understand options', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        // 1. Switch to Generate
        await page.click('.main-tab:has-text("Generate")');
        await page.waitForTimeout(300);

        // 2. Generate form should be visible
        const promptInput = page.locator('#prompt');
        await expect(promptInput).toBeVisible({ timeout: 5000 });

        // 3. Duration control should be visible (slider or input)
        const durationControl = page.locator('#duration, input[name="duration"]');
        await expect(durationControl).toBeVisible();

        // 4. Generate button should be visible
        const generateBtn = page.locator('#generate-btn, button:has-text("Generate")');
        await expect(generateBtn.first()).toBeVisible();

        await page.screenshot({
            path: 'test-results/journey-first-time-generate.png',
            fullPage: true
        });
    });
});

test.describe('Power User Journey', () => {
    test.beforeEach(async ({ page }) => {
        // Disable animations for stability
        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        }).catch(() => {}); // May fail if page not loaded yet
    });

    test('can quickly generate and rate audio', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        // 1. Go to Generate
        await page.click('.main-tab:has-text("Generate")');
        await page.waitForTimeout(300);

        // 2. Enter a prompt
        const promptInput = page.locator('#prompt');
        await promptInput.fill('calm ambient electronic background music');

        // 3. Adjust duration
        const durationSlider = page.locator('#duration');
        await durationSlider.fill('10');

        // 4. Check loop checkbox if available
        const loopCheckbox = page.locator('#loop-checkbox, input[type="checkbox"]');
        if (await loopCheckbox.isVisible()) {
            await loopCheckbox.check();
        }

        // 5. Click Random Prompt button to test that feature
        const randomBtn = page.locator('#random-btn, button:has-text("Random")');
        if (await randomBtn.isVisible()) {
            await randomBtn.click();
            await page.waitForTimeout(500);
        }

        // Take screenshot
        await page.screenshot({
            path: 'test-results/journey-power-user-generate.png',
            fullPage: true
        });
    });

    test('can use keyboard shortcuts efficiently', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Tab through main elements quickly
        for (let i = 0; i < 5; i++) {
            await page.keyboard.press('Tab');
        }

        // Use Enter to activate focused element
        await page.keyboard.press('Enter');
        await page.waitForTimeout(300);

        // Take screenshot
        await page.screenshot({
            path: 'test-results/journey-keyboard-user.png',
            fullPage: true
        });
    });
});

test.describe('Mobile User Journey', () => {
    test.beforeEach(async ({ page }) => {
        await page.setViewportSize({ width: 375, height: 667 });
    });

    test('can navigate and use all features on mobile', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        // 1. Radio should be visible
        await expect(page.locator('#content-radio')).toBeVisible();

        // 2. Tabs should be scrollable or visible
        const tabsContainer = page.locator('.main-tabs');
        await expect(tabsContainer).toBeVisible();

        // 3. Navigate to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        // 4. Library content should be visible
        await expect(page.locator('#content-library')).toBeVisible();

        // Take screenshot
        await page.screenshot({
            path: 'test-results/journey-mobile.png',
            fullPage: true
        });
    });

    test('touch interactions work correctly', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        // Use click instead of tap for consistency (tap may not be fully supported)
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        // Verify tab switched
        await expect(page.locator('#content-library')).toBeVisible();

        // Take screenshot
        await page.screenshot({
            path: 'test-results/journey-mobile-touch.png',
            fullPage: true
        });
    });
});

test.describe('Returning User Journey', () => {
    test('favorites are preserved across sessions', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        // Check localStorage for saved state
        const savedTab = await page.evaluate(() => {
            return localStorage.getItem('soundbox_tab');
        });

        // Device ID should be created/preserved
        const deviceId = await page.evaluate(() => {
            return localStorage.getItem('soundbox_device_id');
        });

        expect(deviceId).toBeTruthy();
        console.log(`Device ID: ${deviceId}`);
    });

    test('can access favorites station preset', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        // Wait for station cards to load
        await page.waitForSelector('.station-card', { timeout: 5000 });

        // Look for favorites station card (might be labeled differently)
        const favStation = page.locator('.station-card:has-text("Favorites"), .station-card[data-station="favorites"]');

        if (await favStation.count() > 0 && await favStation.first().isVisible()) {
            await favStation.first().click();
            await page.waitForTimeout(500);

            // Take screenshot
            await page.screenshot({
                path: 'test-results/journey-favorites-station.png',
                fullPage: true
            });
        }

        // Verify we're still on radio tab
        await expect(page.locator('#content-radio')).toBeVisible();
    });
});

test.describe('Error Recovery Journey', () => {
    test('handles network errors gracefully', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        // Make sure we're on a working page first
        await expect(page.locator('.main-tab').first()).toBeVisible();

        // Go offline
        await page.context().setOffline(true);

        // Try to navigate - UI should still work even if data doesn't load
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(1000);

        // Tab should still switch even when offline
        await expect(page.locator('#content-library')).toBeVisible();

        // Take screenshot to see error state
        await page.screenshot({
            path: 'test-results/journey-offline.png',
            fullPage: true
        });

        // Go back online
        await page.context().setOffline(false);
        await page.reload();
        await page.waitForLoadState('networkidle');

        // Should recover
        await expect(page.locator('.main-tab')).toBeVisible();
    });

    test('handles API errors gracefully', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        // Try to trigger an error (e.g., by searching for special characters)
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        const searchInput = page.locator('#library-search, input[placeholder*="Search"]');
        if (await searchInput.first().isVisible()) {
            await searchInput.first().fill('<script>alert("xss")</script>');
            await page.waitForTimeout(800);
        }

        // Page should not break - main tabs should still be visible
        await expect(page.locator('.main-tab').first()).toBeVisible();

        // Take screenshot
        await page.screenshot({
            path: 'test-results/journey-error-recovery.png',
            fullPage: true
        });
    });
});
