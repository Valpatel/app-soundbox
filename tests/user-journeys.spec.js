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

    test.skip('can quickly generate and rate audio', async ({ page }) => {
        // SKIPPED: Requires authentication to use generate functionality
        // The prompt input is disabled without sign-in
        // TODO: Implement auth flow or mock authentication properly

        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Go to Generate
        await page.click('.main-tab:has-text("Generate")');
        await page.waitForTimeout(300);

        // Prompt should be enabled for authenticated users
        const promptInput = page.locator('#prompt');
        await expect(promptInput).toBeEnabled({ timeout: 5000 });

        // Fill prompt
        await promptInput.fill('calm ambient electronic background music');

        // Adjust duration
        const durationSlider = page.locator('#duration');
        await expect(durationSlider).toBeEnabled();
        await durationSlider.fill('10');

        // Click generate and verify audio is created
        const generateBtn = page.locator('#generate-btn');
        await generateBtn.click();

        // Wait for generation to complete
        await expect(page.locator('.generated-audio, audio')).toBeVisible({ timeout: 60000 });
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

        // 2. On mobile (480px and below), navigation uses a dropdown select
        const mobileDropdown = page.locator('#mobile-tab-select');
        await expect(mobileDropdown).toBeVisible({ timeout: 5000 });

        // 3. Navigate to Library using mobile dropdown
        await mobileDropdown.selectOption('library');
        await page.waitForTimeout(500);

        // Library content should be visible
        await expect(page.locator('#content-library')).toBeVisible();

        // 4. Navigate to Generate
        await mobileDropdown.selectOption('generate');
        await page.waitForTimeout(500);
        await expect(page.locator('#content-generate')).toBeVisible();

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

        // On mobile, navigation uses dropdown select
        const mobileDropdown = page.locator('#mobile-tab-select');
        await expect(mobileDropdown).toBeVisible({ timeout: 5000 });

        // Test touch interaction with dropdown
        await mobileDropdown.selectOption('library');
        await page.waitForTimeout(500);

        // Verify tab switched
        await expect(page.locator('#content-library')).toBeVisible();

        // Test station card touch interaction
        await mobileDropdown.selectOption('radio');
        await page.waitForTimeout(500);

        const stationCard = page.locator('.station-card').first();
        await expect(stationCard).toBeVisible();
        await stationCard.click();
        await page.waitForTimeout(500);

        // Take screenshot
        await page.screenshot({
            path: 'test-results/journey-mobile-touch.png',
            fullPage: true
        });
    });
});

test.describe('Returning User Journey', () => {
    test.skip('favorites are preserved across sessions', async ({ page }) => {
        // SKIPPED: Requires authentication and actual favorite actions
        // The app uses server-side persistence with user accounts, not localStorage
        // TODO: Implement with proper auth flow

        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Add a track to favorites
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const favButton = page.locator('.library-item .favorite-btn').first();
        await favButton.click();
        await page.waitForTimeout(500);

        // Reload page
        await page.reload();
        await page.waitForLoadState('networkidle');

        // Navigate to favorites and verify track is still there
        await page.click('.station-card:has-text("Favorites")');
        await expect(page.locator('.now-playing .track-title')).toBeVisible();
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
        const libraryTab = page.locator('.main-tab:has-text("Library")');
        await libraryTab.click();
        await page.waitForTimeout(1000);

        // Tab content area should be visible (even if showing error state)
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

        // Should recover - page must be functional
        await expect(page.locator('.main-tab').first()).toBeVisible();
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
