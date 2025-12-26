/**
 * User Journey Tests
 *
 * Tests complete user workflows from start to finish
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.TEST_URL || 'http://localhost:5309';

test.describe('First-Time User Journey', () => {
    test('can browse and listen to existing audio', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // 1. Land on Radio tab (default)
        await expect(page.locator('#content-radio')).toBeVisible();

        // 2. See radio stations
        const stationCards = page.locator('.station-card');
        await expect(stationCards.first()).toBeVisible({ timeout: 5000 });

        // 3. Click a station to play (station-all is the shuffle/all music station)
        await page.click('.station-card.station-all, .station-card.station-ambient', { force: true });
        await page.waitForTimeout(1000);

        // 4. Audio player should be ready
        const playButton = page.locator('#radio-play-btn, .play-btn').first();
        await expect(playButton).toBeVisible({ timeout: 5000 });

        // Take screenshot of radio experience
        await page.screenshot({
            path: 'test-results/journey-first-time-radio.png',
            fullPage: true
        });
    });

    test('can browse library and filter', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // 1. Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        // 2. Library items should load
        const libraryItems = page.locator('.library-item');
        await expect(libraryItems.first()).toBeVisible({ timeout: 10000 });

        // 3. Filter by type (Music)
        const musicTab = page.locator('.type-tab:has-text("Music"), [data-type="music"]');
        if (await musicTab.isVisible()) {
            await musicTab.click();
            await page.waitForTimeout(500);
        }

        // 4. Search for something
        const searchInput = page.locator('#library-search, input[placeholder*="Search"]');
        if (await searchInput.isVisible()) {
            await searchInput.fill('ambient');
            await page.waitForTimeout(800);  // Debounce
        }

        // Take screenshot
        await page.screenshot({
            path: 'test-results/journey-first-time-library.png',
            fullPage: true
        });
    });

    test('can view generate page and understand options', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // 1. Switch to Generate
        await page.click('.main-tab:has-text("Generate")');
        await page.waitForTimeout(500);

        // 2. Generate form should be visible
        const promptInput = page.locator('#prompt');
        await expect(promptInput).toBeVisible();

        // 3. Model selector should be visible
        const modelButtons = page.locator('.model-btn, [data-model]');
        await expect(modelButtons.first()).toBeVisible();

        // 4. Duration slider should be visible
        const durationSlider = page.locator('#duration');
        await expect(durationSlider).toBeVisible();

        // 5. Generate button should be visible
        const generateBtn = page.locator('#generate-btn');
        await expect(generateBtn).toBeVisible();

        // Take screenshot
        await page.screenshot({
            path: 'test-results/journey-first-time-generate.png',
            fullPage: true
        });
    });
});

test.describe('Power User Journey', () => {
    test('can quickly generate and rate audio', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

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

        // Tap on Library tab
        await page.tap('.main-tab:has-text("Library")');
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

        // On Radio tab (default), find and click Favorites station preset
        const favStation = page.locator('.station-preset:has-text("Favorites"), [title*="favorited"]');
        if (await favStation.isVisible()) {
            await favStation.click();
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

        // Go offline
        await page.context().setOffline(true);

        // Try to navigate
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(1000);

        // Should show some indication or handle gracefully
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

        // Try to trigger an error (e.g., by searching for special characters)
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        const searchInput = page.locator('#library-search, input[placeholder*="Search"]');
        if (await searchInput.isVisible()) {
            await searchInput.fill('<script>alert("xss")</script>');
            await page.waitForTimeout(800);
        }

        // Page should not break
        await expect(page.locator('.main-tab')).toBeVisible();

        // Take screenshot
        await page.screenshot({
            path: 'test-results/journey-error-recovery.png',
            fullPage: true
        });
    });
});
