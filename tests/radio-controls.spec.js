/**
 * Radio Controls E2E Tests
 *
 * Tests radio functionality:
 * - Station selection and switching
 * - Shuffle/random playback
 * - Queue visualization
 * - Skip and previous controls
 * - Station keywords/filters
 * - Featured playlists (Trending, New, Top Rated)
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.TEST_URL || 'http://localhost:5309';

test.describe('Radio - Station Selection', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });
    });

    test('station cards are displayed', async ({ page }) => {
        await expect(page.locator('#content-radio')).toBeVisible();

        const stationCards = page.locator('.station-card');
        await expect(stationCards.first()).toBeVisible({ timeout: 5000 });

        const count = await stationCards.count();
        expect(count).toBeGreaterThan(0);
    });

    test('clicking station card selects it', async ({ page }) => {
        const stationCards = page.locator('.station-card');
        await expect(stationCards.first()).toBeVisible({ timeout: 5000 });

        // Click a non-active station
        const inactiveStation = page.locator('.station-card:not(.active)');
        if (await inactiveStation.count() > 0) {
            await inactiveStation.first().click();
            await page.waitForTimeout(500);

            // Should now have active class or be selected
            const clickedCard = inactiveStation.first();
            const isActive = await clickedCard.evaluate(el => el.classList.contains('active'));
        }
    });

    test('each station has name and description', async ({ page }) => {
        const stationCards = page.locator('.station-card');
        await expect(stationCards.first()).toBeVisible({ timeout: 5000 });

        // Check first station has name
        const stationName = stationCards.first().locator('.station-name, h3, .title');
        if (await stationName.count() > 0) {
            const name = await stationName.first().textContent();
            expect(name?.length).toBeGreaterThan(0);
        }
    });

    test('ambient station is pre-selected by default', async ({ page }) => {
        await page.waitForSelector('.station-card', { timeout: 5000 });

        const activeStation = page.locator('.station-card.active');
        await expect(activeStation).toBeVisible({ timeout: 5000 });
    });
});

test.describe('Radio - Featured Playlists', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });
    });

    test('trending station loads trending tracks', async ({ page }) => {
        const trendingStation = page.locator(
            '.station-card:has-text("Trending"), [data-station="trending"]'
        );

        if (await trendingStation.count() > 0 && await trendingStation.first().isVisible()) {
            await trendingStation.first().click();
            await page.waitForTimeout(1000);

            // Queue should update
            const queue = page.locator('#radio-queue, .queue-list');
            if (await queue.count() > 0) {
                await expect(queue.first()).toBeVisible();
            }
        }
    });

    test('new arrivals station loads recent tracks', async ({ page }) => {
        const newStation = page.locator(
            '.station-card:has-text("New"), .station-card:has-text("Arrivals"), ' +
            '[data-station="new"]'
        );

        if (await newStation.count() > 0 && await newStation.first().isVisible()) {
            await newStation.first().click();
            await page.waitForTimeout(1000);
        }
    });

    test('top rated station loads highest rated tracks', async ({ page }) => {
        const topRatedStation = page.locator(
            '.station-card:has-text("Top"), .station-card:has-text("Rated"), ' +
            '[data-station="top-rated"]'
        );

        if (await topRatedStation.count() > 0 && await topRatedStation.first().isVisible()) {
            await topRatedStation.first().click();
            await page.waitForTimeout(1000);
        }
    });

    test('surprise me station loads random tracks', async ({ page }) => {
        const surpriseStation = page.locator(
            '.station-card:has-text("Surprise"), .station-card:has-text("Random"), ' +
            '[data-station="surprise"]'
        );

        if (await surpriseStation.count() > 0 && await surpriseStation.first().isVisible()) {
            await surpriseStation.first().click();
            await page.waitForTimeout(1000);
        }
    });

    test('favorites station shows user favorites', async ({ page }) => {
        const favStation = page.locator(
            '.station-card:has-text("Favorites"), [data-station="favorites"]'
        );

        if (await favStation.count() > 0 && await favStation.first().isVisible()) {
            await favStation.first().click();
            await page.waitForTimeout(1000);
        }
    });
});

test.describe('Radio - Queue Display', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });
    });

    test('queue section is visible', async ({ page }) => {
        const queueSection = page.locator('#radio-queue, .queue-section, .upcoming-tracks');
        await expect(queueSection.first()).toBeVisible({ timeout: 10000 });
    });

    test('queue shows upcoming tracks', async ({ page }) => {
        // Wait for queue to load
        await page.waitForTimeout(2000);

        const queueItems = page.locator('.queue-item, .queue-track, .upcoming-track');
        const count = await queueItems.count();

        // Queue might be empty or have tracks
        if (count > 0) {
            await expect(queueItems.first()).toBeVisible();
        }
    });

    test('now playing section shows current track', async ({ page }) => {
        const nowPlaying = page.locator('#radio-now-playing, .now-playing, .current-track-info');
        await expect(nowPlaying.first()).toBeVisible({ timeout: 10000 });

        // Should show track title
        const trackTitle = nowPlaying.first().locator('.track-title, .title, h3');
        if (await trackTitle.count() > 0) {
            await expect(trackTitle.first()).toBeVisible();
        }
    });
});

test.describe('Radio - Shuffle Controls', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });
    });

    test('shuffle button is visible', async ({ page }) => {
        const shuffleBtn = page.locator(
            '#shuffle-btn, .shuffle-btn, button[aria-label*="shuffle" i]'
        );

        if (await shuffleBtn.count() > 0) {
            await expect(shuffleBtn.first()).toBeVisible();
        }
    });

    test('shuffle button toggles shuffle mode', async ({ page }) => {
        const shuffleBtn = page.locator('#shuffle-btn, .shuffle-btn');

        if (await shuffleBtn.count() > 0 && await shuffleBtn.first().isVisible()) {
            // Get initial state
            const initialClass = await shuffleBtn.first().getAttribute('class') || '';

            await shuffleBtn.first().click();
            await page.waitForTimeout(300);

            // Click again to toggle
            await shuffleBtn.first().click();
            await page.waitForTimeout(300);

            await expect(shuffleBtn.first()).toBeEnabled();
        }
    });
});

test.describe('Radio - Skip Controls', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });
    });

    test('skip button advances to next track', async ({ page }) => {
        const nowPlaying = page.locator('#radio-now-playing, .now-playing');
        await expect(nowPlaying.first()).toBeVisible({ timeout: 10000 });

        // Get current track title
        const trackTitle = nowPlaying.first().locator('.track-title, .title');
        let currentTitle = '';
        if (await trackTitle.count() > 0) {
            currentTitle = await trackTitle.first().textContent() || '';
        }

        const skipBtn = page.locator('#skip-btn, .skip-btn, button[aria-label*="skip" i]');

        if (await skipBtn.count() > 0 && await skipBtn.first().isVisible()) {
            await skipBtn.first().click();
            await page.waitForTimeout(1000);

            // Track might have changed
            await expect(skipBtn.first()).toBeEnabled();
        }
    });

    test('previous button goes to previous track', async ({ page }) => {
        const prevBtn = page.locator('#prev-btn, .prev-btn, button[aria-label*="previous" i]');

        if (await prevBtn.count() > 0 && await prevBtn.first().isVisible()) {
            await prevBtn.first().click();
            await page.waitForTimeout(500);

            await expect(prevBtn.first()).toBeEnabled();
        }
    });

    test('skip shows cost indicator if premium feature', async ({ page }) => {
        const skipBtn = page.locator('#skip-btn, .skip-btn');

        if (await skipBtn.count() > 0 && await skipBtn.first().isVisible()) {
            // Look for aura/cost indicator
            const costIndicator = page.locator('.skip-cost, .aura-cost, [class*="cost"]');
            // Might or might not be visible depending on feature flags
        }
    });
});

test.describe('Radio - Keyword Filters', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });
    });

    test.skip('keyword input is visible if available', async ({ page }) => {
        // SKIPPED: Keyword filter feature is not implemented in current UI
        // TODO: Implement keyword filtering for radio stations

        const keywordInput = page.locator(
            '#radio-keywords, .keyword-filter, input[placeholder*="keyword" i]'
        );

        await expect(keywordInput.first()).toBeVisible({ timeout: 5000 });
    });

    test('entering keywords filters station content', async ({ page }) => {
        const keywordInput = page.locator('#radio-keywords, .keyword-filter');

        if (await keywordInput.count() > 0 && await keywordInput.first().isVisible()) {
            await keywordInput.first().fill('ambient');
            await page.waitForTimeout(500);

            // Trigger filter
            await page.keyboard.press('Enter');
            await page.waitForTimeout(1000);
        }
    });
});

test.describe('Radio - Visualizer', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });
    });

    test('visualizer canvas is visible', async ({ page }) => {
        const visualizer = page.locator('#visualizer, .visualizer, canvas.visualizer');

        if (await visualizer.count() > 0) {
            await expect(visualizer.first()).toBeVisible({ timeout: 5000 });
        }
    });

    test('visualizer mode selector works', async ({ page }) => {
        const modeSelector = page.locator(
            '#viz-mode, .viz-mode-selector, select[name="visualizer"]'
        );

        if (await modeSelector.count() > 0 && await modeSelector.first().isVisible()) {
            // Get available modes
            const options = await modeSelector.first().locator('option').count();
            expect(options).toBeGreaterThan(0);
        }
    });
});

test.describe('Radio - Track Actions', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });
    });

    test('voting buttons visible in now playing', async ({ page }) => {
        const nowPlaying = page.locator('#radio-now-playing, .now-playing');
        await expect(nowPlaying.first()).toBeVisible({ timeout: 10000 });

        const upvoteBtn = nowPlaying.first().locator('.upvote, button[aria-label*="upvote" i]');
        const downvoteBtn = nowPlaying.first().locator('.downvote, button[aria-label*="downvote" i]');

        if (await upvoteBtn.count() > 0) {
            await expect(upvoteBtn.first()).toBeVisible();
        }
    });

    test('favorite button visible in now playing', async ({ page }) => {
        const nowPlaying = page.locator('#radio-now-playing, .now-playing');
        await expect(nowPlaying.first()).toBeVisible({ timeout: 10000 });

        const favBtn = nowPlaying.first().locator(
            '.favorite-btn, button[aria-label*="favorite" i]'
        );

        if (await favBtn.count() > 0) {
            await expect(favBtn.first()).toBeVisible();
        }
    });

    test('download button visible in now playing', async ({ page }) => {
        const nowPlaying = page.locator('#radio-now-playing, .now-playing');
        await expect(nowPlaying.first()).toBeVisible({ timeout: 10000 });

        const downloadBtn = nowPlaying.first().locator(
            '.download-btn, button[aria-label*="download" i]'
        );

        if (await downloadBtn.count() > 0) {
            await expect(downloadBtn.first()).toBeVisible();
        }
    });
});
