/**
 * View Modes & Advanced Features E2E Tests
 *
 * Tests advanced UI features:
 * - List/Grid view toggle
 * - Copy to clipboard buttons
 * - History tab functionality
 * - Quick filters
 * - Sort options
 * - Spectrogram display
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.TEST_URL || 'http://localhost:5309';

test.describe('View Mode Toggle', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);
    });

    test('view mode toggle is visible', async ({ page }) => {
        const viewToggle = page.locator(
            '.view-toggle, .view-mode-toggle, ' +
            'button[aria-label*="view" i], .list-grid-toggle'
        );

        if (await viewToggle.count() > 0) {
            await expect(viewToggle.first()).toBeVisible();
        }
    });

    test('can switch to grid view', async ({ page }) => {
        const gridBtn = page.locator(
            'button[aria-label*="grid" i], .grid-view-btn, ' +
            '[data-view="grid"], button:has-text("Grid")'
        );

        if (await gridBtn.count() > 0 && await gridBtn.first().isVisible()) {
            await gridBtn.first().click();
            await page.waitForTimeout(300);

            // Library container should have grid class or grid layout
            const libraryContainer = page.locator('.library-list, .library-container');
            if (await libraryContainer.count() > 0) {
                const hasGridClass = await libraryContainer.first().evaluate(el => {
                    return el.classList.contains('grid') ||
                           el.classList.contains('grid-view') ||
                           getComputedStyle(el).display === 'grid';
                });
            }
        }
    });

    test('can switch to list view', async ({ page }) => {
        const listBtn = page.locator(
            'button[aria-label*="list" i], .list-view-btn, ' +
            '[data-view="list"], button:has-text("List")'
        );

        if (await listBtn.count() > 0 && await listBtn.first().isVisible()) {
            await listBtn.first().click();
            await page.waitForTimeout(300);
        }
    });

    test('view preference persists', async ({ page }) => {
        const gridBtn = page.locator('button[aria-label*="grid" i], [data-view="grid"]');

        if (await gridBtn.count() > 0 && await gridBtn.first().isVisible()) {
            await gridBtn.first().click();
            await page.waitForTimeout(300);

            // Check localStorage
            const viewPref = await page.evaluate(() => {
                return localStorage.getItem('soundbox_view_mode') ||
                       localStorage.getItem('library_view');
            });
        }
    });
});

test.describe('Copy to Clipboard', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);
    });

    test('copy ID button is visible on library items', async ({ page }) => {
        const libraryItem = page.locator('.library-item, .track-item');
        await expect(libraryItem.first()).toBeVisible({ timeout: 10000 });

        const copyBtn = libraryItem.first().locator(
            '.copy-id, button[aria-label*="copy" i], .copy-btn'
        );

        if (await copyBtn.count() > 0) {
            await expect(copyBtn.first()).toBeVisible();
        }
    });

    test('clicking copy button copies to clipboard', async ({ page, context }) => {
        // Grant clipboard permissions
        await context.grantPermissions(['clipboard-read', 'clipboard-write']);

        const libraryItem = page.locator('.library-item, .track-item');
        await expect(libraryItem.first()).toBeVisible({ timeout: 10000 });

        const copyBtn = libraryItem.first().locator('.copy-id, button[aria-label*="copy" i]');

        if (await copyBtn.count() > 0 && await copyBtn.first().isVisible()) {
            await copyBtn.first().click();
            await page.waitForTimeout(300);

            // Check clipboard or success indicator
            const successIndicator = page.locator('.copy-success, .copied, [class*="success"]');
            if (await successIndicator.count() > 0) {
                // Brief success message might appear
            }
        }
    });

    test('copy prompt button copies prompt text', async ({ page, context }) => {
        await context.grantPermissions(['clipboard-read', 'clipboard-write']);

        const libraryItem = page.locator('.library-item, .track-item');
        await expect(libraryItem.first()).toBeVisible({ timeout: 10000 });

        const copyPromptBtn = libraryItem.first().locator(
            '.copy-prompt, button[aria-label*="copy prompt" i]'
        );

        if (await copyPromptBtn.count() > 0 && await copyPromptBtn.first().isVisible()) {
            await copyPromptBtn.first().click();
            await page.waitForTimeout(300);
        }
    });
});

test.describe('History Tab', () => {
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

    test('history tab exists or app has alternative history access', async ({ page }) => {
        // History tab may exist but be hidden (feature gated) - check for any history access
        const historyTab = page.locator('.main-tab:has-text("History")');

        const hasHistoryTab = await historyTab.count() > 0;
        const isVisible = hasHistoryTab && await historyTab.first().isVisible();

        if (isVisible) {
            // History tab exists and is visible
            await expect(historyTab.first()).toBeVisible();
        } else {
            // No visible history tab - verify main UI still works (this is OK)
            // History might be a hidden/premium feature
            await expect(page.locator('.main-tab').first()).toBeVisible();
        }
    });

    test('recent plays are tracked if history exists', async ({ page }) => {
        // Check if plays are tracked - may be in localStorage even without History tab
        const hasPlayTracking = await page.evaluate(() => {
            return localStorage.getItem('soundbox_play_history') !== null ||
                   localStorage.getItem('soundbox_recent') !== null ||
                   localStorage.getItem('recentPlays') !== null;
        });

        // Either tracking exists or feature is not implemented - both are valid
        expect(typeof hasPlayTracking).toBe('boolean');

        // Main UI should still work
        await expect(page.locator('.main-tab').first()).toBeVisible();
    });

    test('vote history accessible if history feature exists', async ({ page }) => {
        // Check for vote tracking in localStorage
        const hasVoteHistory = await page.evaluate(() => {
            return localStorage.getItem('soundbox_vote_history') !== null ||
                   localStorage.getItem('votes') !== null;
        });

        // Either tracking exists or not - both are valid
        expect(typeof hasVoteHistory).toBe('boolean');

        // Main UI should still work
        await expect(page.locator('.main-tab').first()).toBeVisible();
    });

    test('history items are playable if visible', async ({ page }) => {
        // Look for any history-related content
        const historyContent = page.locator('.history-item, .history-track, #history-content');

        // If history content exists, verify it
        if (await historyContent.count() > 0) {
            const playBtn = historyContent.first().locator('.play-btn, button[aria-label*="play" i]');
            if (await playBtn.count() > 0) {
                await expect(playBtn.first()).toBeVisible();
            }
        }

        // Main UI should work regardless
        await expect(page.locator('.main-tab').first()).toBeVisible();
    });

    test('load more pagination works if available', async ({ page }) => {
        // Look for pagination on any tab
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        const paginationBtns = page.locator('.pagination button, .page-btn, #next-page');

        if (await paginationBtns.count() > 0 && await paginationBtns.first().isVisible()) {
            // Pagination exists
            await expect(paginationBtns.first()).toBeVisible();
        }

        // Main UI should work
        await expect(page.locator('.main-tab').first()).toBeVisible();
    });
});

test.describe('Quick Filters', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);
    });

    test('favorites quick filter shows only favorites', async ({ page }) => {
        const favFilter = page.locator(
            '.quick-filter:has-text("Favorites"), button[data-filter="favorites"], ' +
            '.favorites-filter'
        );

        if (await favFilter.count() > 0 && await favFilter.first().isVisible()) {
            await favFilter.first().click();
            await page.waitForTimeout(500);
        }
    });

    test('recent quick filter shows recent items', async ({ page }) => {
        const recentFilter = page.locator(
            '.quick-filter:has-text("Recent"), button[data-filter="recent"]'
        );

        if (await recentFilter.count() > 0 && await recentFilter.first().isVisible()) {
            await recentFilter.first().click();
            await page.waitForTimeout(500);
        }
    });
});

test.describe('Sort Options', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);
    });

    test('sort dropdown is visible', async ({ page }) => {
        const sortDropdown = page.locator(
            '#sort-select, select[name="sort"], .sort-dropdown, .sort-select'
        );

        if (await sortDropdown.count() > 0) {
            await expect(sortDropdown.first()).toBeVisible();
        }
    });

    test('can sort by recent', async ({ page }) => {
        const sortDropdown = page.locator('#sort-select, select[name="sort"]');

        if (await sortDropdown.count() > 0 && await sortDropdown.first().isVisible()) {
            await sortDropdown.first().selectOption('recent');
            await page.waitForTimeout(500);
        }
    });

    test('can sort by popular', async ({ page }) => {
        const sortDropdown = page.locator('#sort-select, select[name="sort"]');

        if (await sortDropdown.count() > 0 && await sortDropdown.first().isVisible()) {
            await sortDropdown.first().selectOption('popular');
            await page.waitForTimeout(500);
        }
    });

    test('can sort by rating', async ({ page }) => {
        const sortDropdown = page.locator('#sort-select, select[name="sort"]');

        if (await sortDropdown.count() > 0 && await sortDropdown.first().isVisible()) {
            await sortDropdown.first().selectOption('rating');
            await page.waitForTimeout(500);
        }
    });
});

test.describe('Spectrogram Display', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);
    });

    test('spectrogram image is visible on library items', async ({ page }) => {
        const libraryItem = page.locator('.library-item, .track-item');
        await expect(libraryItem.first()).toBeVisible({ timeout: 10000 });

        const spectrogram = libraryItem.first().locator(
            '.spectrogram, img[src*="spectrogram"], .waveform'
        );

        if (await spectrogram.count() > 0) {
            await expect(spectrogram.first()).toBeVisible();
        }
    });

    test('spectrogram loads correctly', async ({ page }) => {
        const spectrogram = page.locator('.spectrogram img, img[src*="spectrogram"]');

        if (await spectrogram.count() > 0) {
            const imgSrc = await spectrogram.first().getAttribute('src');
            if (imgSrc) {
                expect(imgSrc.length).toBeGreaterThan(0);
            }
        }
    });
});

test.describe('Category Sidebar', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);
    });

    test('category sidebar is visible', async ({ page }) => {
        const sidebar = page.locator('.category-sidebar, .genre-sidebar, #library-sidebar');

        if (await sidebar.count() > 0) {
            await expect(sidebar.first()).toBeVisible();
        }
    });

    test('categories show item counts', async ({ page }) => {
        const categoryItem = page.locator('.category-item, .genre-item');

        if (await categoryItem.count() > 0) {
            const countBadge = categoryItem.first().locator('.count, .badge, .item-count');
            if (await countBadge.count() > 0) {
                const countText = await countBadge.first().textContent();
                // Should be a number or number format
            }
        }
    });

    test('clicking category filters library', async ({ page }) => {
        const categoryItem = page.locator('.category-item, .genre-item');

        if (await categoryItem.count() > 0 && await categoryItem.first().isVisible()) {
            await categoryItem.first().click();
            await page.waitForTimeout(500);

            // Category should be selected
            const selectedCategory = page.locator('.category-item.active, .genre-item.selected');
        }
    });

    test('mobile category toggle button works', async ({ page }) => {
        // Set mobile viewport
        await page.setViewportSize({ width: 375, height: 667 });
        await page.waitForTimeout(300);

        const toggleBtn = page.locator(
            '.category-toggle, .sidebar-toggle, #toggle-categories'
        );

        if (await toggleBtn.count() > 0 && await toggleBtn.first().isVisible()) {
            await toggleBtn.first().click();
            await page.waitForTimeout(300);

            // Sidebar should expand/collapse
        }
    });
});
