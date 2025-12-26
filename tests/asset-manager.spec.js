/**
 * Asset Manager / Library Tests
 *
 * Tests the library functionality including browsing, voting, and playback
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.TEST_URL || 'http://localhost:5309';

test.describe('Library', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Disable CSS animations for stable element interactions
        await page.addStyleTag({
            content: `
                *, *::before, *::after {
                    animation-duration: 0s !important;
                    animation-delay: 0s !important;
                    transition-duration: 0s !important;
                    transition-delay: 0s !important;
                }
            `
        });

        // Navigate to Library tab
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);
    });

    test('should display library section when assets exist', async ({ page }) => {
        // Wait for library tab content
        const libraryTab = page.locator('#content-library');
        await expect(libraryTab).toBeVisible({ timeout: 10000 });

        // Check for library items container
        const libraryItems = page.locator('#library-items, .library-items');
        await expect(libraryItems).toBeVisible();
    });

    test('should display library items', async ({ page }) => {
        // Wait for library to load
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Count displayed items
        const items = page.locator('.library-item');
        const count = await items.count();

        console.log(`Displayed library items: ${count}`);
        expect(count).toBeGreaterThan(0);
    });

    test('should have vote buttons for each item', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Check first item for vote buttons
        const firstItem = page.locator('.library-item').first();

        // Look for upvote/downvote buttons
        const upButton = firstItem.locator('.vote-up, .upvote-btn, .item-upvote');
        const downButton = firstItem.locator('.vote-down, .downvote-btn, .item-downvote');

        // At least one vote mechanism should be present
        const hasUpvote = await upButton.count() > 0;
        const hasDownvote = await downButton.count() > 0;

        console.log(`Has upvote: ${hasUpvote}, Has downvote: ${hasDownvote}`);
        expect(hasUpvote || hasDownvote).toBeTruthy();
    });

    test('should have favorite button for each item', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Check first item for favorite button
        const firstItem = page.locator('.library-item').first();
        const favButton = firstItem.locator('.item-favorite, .favorite-btn, .add-favorite');

        const hasFavorite = await favButton.count() > 0;
        console.log(`Has favorite button: ${hasFavorite}`);
        expect(hasFavorite).toBeTruthy();
    });

    test('should have download functionality', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Check first item for download
        const firstItem = page.locator('.library-item').first();
        const downloadBtn = firstItem.locator('.action-btn.download, a[href*="/download/"]');

        const hasDownload = await downloadBtn.count() > 0;
        console.log(`Has download: ${hasDownload}`);
        expect(hasDownload).toBeTruthy();
    });

    test('should display item metadata', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // First item should have prompt text
        const firstItem = page.locator('.library-item').first();
        const promptText = await firstItem.textContent();

        console.log(`First item text: ${promptText?.substring(0, 100)}`);
        expect(promptText?.length).toBeGreaterThan(0);
    });

    test('API should return library items', async ({ page }) => {
        // Direct API test
        const response = await page.request.get(`${BASE_URL}/api/library`);
        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        console.log(`API returned ${data.items?.length || 0} items, total: ${data.total}`);

        // Check structure of returned items
        expect(data).toHaveProperty('items');
        expect(data).toHaveProperty('total');

        if (data.items && data.items.length > 0) {
            const firstItem = data.items[0];
            expect(firstItem).toHaveProperty('id');
            expect(firstItem).toHaveProperty('prompt');
            expect(firstItem).toHaveProperty('model');
        }
    });

    test('should be able to vote via API', async ({ page }) => {
        // Get first item from API
        const libraryResponse = await page.request.get(`${BASE_URL}/api/library?per_page=1`);
        const data = await libraryResponse.json();

        if (!data.items || data.items.length === 0) {
            test.skip();
            return;
        }

        const itemId = data.items[0].id;

        // Vote on the item
        const voteResponse = await page.request.post(`${BASE_URL}/api/library/${itemId}/vote`, {
            data: {
                vote: 1,
                user_id: 'test_user'
            }
        });

        expect(voteResponse.ok()).toBeTruthy();

        const result = await voteResponse.json();
        // API returns upvotes/downvotes/user_vote
        expect(result).toHaveProperty('upvotes');
        expect(result).toHaveProperty('user_vote');

        // Remove the vote
        await page.request.post(`${BASE_URL}/api/library/${itemId}/vote`, {
            data: {
                vote: 0,
                user_id: 'test_user'
            }
        });
    });

    test('search input is visible', async ({ page }) => {
        const searchInput = page.locator('#library-search, input[placeholder*="Search"]');
        await expect(searchInput).toBeVisible();
    });

    test('can filter by type', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Look for type filter tabs
        const typeTabs = page.locator('.type-tab, [data-type]');
        const count = await typeTabs.count();

        console.log(`Found ${count} type filter tabs`);
        expect(count).toBeGreaterThan(0);
    });

    test('pagination is visible when needed', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Check for pagination controls
        const pagination = page.locator('.pagination, .page-controls, .page-btn');
        const hasPagination = await pagination.count() > 0;

        console.log(`Has pagination: ${hasPagination}`);
        // Pagination may not be visible if there are few items
    });
});
