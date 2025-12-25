const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.TEST_URL || 'http://localhost:5309';

test.describe('Asset Manager', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        // Wait for the page to load and history to populate
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
    });

    test('should display history section when assets exist', async ({ page }) => {
        // Wait for history card to appear
        const historyCard = page.locator('#history-card');
        await expect(historyCard).toBeVisible({ timeout: 10000 });

        // Check that history title shows "All Generations" with count
        const title = historyCard.locator('h2');
        await expect(title).toContainText(/All Generations/);
    });

    test('should display history items', async ({ page }) => {
        // Wait for history to load
        await page.waitForSelector('.history-item', { timeout: 10000 });

        // Count displayed items
        const items = page.locator('.history-item');
        const count = await items.count();

        console.log(`Displayed history items: ${count}`);
        expect(count).toBeGreaterThan(0);
    });

    test('should show all assets (not limited to 20)', async ({ page }) => {
        // Get total count from API (no model filter)
        const response = await page.request.get(`${BASE_URL}/history`);
        const apiItems = await response.json();
        const totalAssets = apiItems.length;

        console.log(`Total assets from API: ${totalAssets}`);

        // Wait for history to load
        await page.waitForSelector('.history-item', { timeout: 10000 });

        // Count displayed items
        const displayedItems = page.locator('.history-item');
        const displayedCount = await displayedItems.count();

        console.log(`Displayed items in UI: ${displayedCount}`);

        // All assets should now be displayed (showAllHistory defaults to true)
        expect(displayedCount).toBe(totalAssets);
        console.log(`SUCCESS: All ${totalAssets} assets displayed correctly!`);

        // Also verify the title shows "All Generations"
        const title = page.locator('#history-card h2');
        await expect(title).toContainText('All Generations');
    });

    test('should expand history item on click', async ({ page }) => {
        await page.waitForSelector('.history-item', { timeout: 10000 });

        // Get first history item
        const firstItem = page.locator('.history-item').first();
        const header = firstItem.locator('.history-header');

        // Click to expand
        await header.click();

        // Check that item is expanded
        await expect(firstItem).toHaveClass(/expanded/);

        // Check that content is visible
        const content = firstItem.locator('.history-content');
        await expect(content).toBeVisible();
    });

    test('should have rating buttons for each item', async ({ page }) => {
        await page.waitForSelector('.history-item', { timeout: 10000 });

        // Expand first item to see rating buttons
        const firstItem = page.locator('.history-item').first();
        await firstItem.locator('.history-header').click();

        // Check for rating buttons
        const upButton = firstItem.locator('.rating-btn').first();
        const downButton = firstItem.locator('.rating-btn').nth(1);

        await expect(upButton).toBeVisible();
        await expect(downButton).toBeVisible();
        await expect(upButton).toContainText('👍');
        await expect(downButton).toContainText('👎');
    });

    test('should toggle rating on click', async ({ page }) => {
        await page.waitForSelector('.history-item', { timeout: 10000 });

        // Expand first item
        const firstItem = page.locator('.history-item').first();
        await firstItem.locator('.history-header').click();

        // Get the thumbs up button
        const upButton = firstItem.locator('.rating-btn').first();

        // Click to rate up
        await upButton.click();

        // Wait for the API call to complete
        await page.waitForTimeout(500);

        // Check that it's now active
        await expect(upButton).toHaveClass(/active-up/);

        // Click again to remove rating
        await upButton.click();
        await page.waitForTimeout(500);

        // Check that it's no longer active
        await expect(upButton).not.toHaveClass(/active-up/);
    });

    test('should have audio player for each item', async ({ page }) => {
        await page.waitForSelector('.history-item', { timeout: 10000 });

        // Expand first item
        const firstItem = page.locator('.history-item').first();
        await firstItem.locator('.history-header').click();

        // Check for audio element
        const audio = firstItem.locator('audio');
        await expect(audio).toBeVisible();

        // Check that source is set
        const src = await audio.getAttribute('src');
        expect(src).toContain('/audio/');
    });

    test('should have download button for each item', async ({ page }) => {
        await page.waitForSelector('.history-item', { timeout: 10000 });

        // Expand first item
        const firstItem = page.locator('.history-item').first();
        await firstItem.locator('.history-header').click();

        // Check for download link (uses .download-btn class)
        const downloadLink = firstItem.locator('.download-btn');
        await expect(downloadLink).toBeVisible();

        const href = await downloadLink.getAttribute('href');
        expect(href).toContain('/download/');
    });

    test('should display spectrogram when available', async ({ page }) => {
        await page.waitForSelector('.history-item', { timeout: 10000 });

        // Expand first item
        const firstItem = page.locator('.history-item').first();
        await firstItem.locator('.history-header').click();

        // Check for spectrogram image (may not exist for older items)
        const spectrogram = firstItem.locator('img');
        const count = await spectrogram.count();

        if (count > 0) {
            const src = await spectrogram.first().getAttribute('src');
            expect(src).toContain('/spectrogram/');
        }
    });

    test('API should return all assets', async ({ page }) => {
        // Direct API test
        const response = await page.request.get(`${BASE_URL}/history`);
        expect(response.ok()).toBeTruthy();

        const items = await response.json();
        console.log(`API returned ${items.length} items`);

        // Check structure of returned items
        if (items.length > 0) {
            const firstItem = items[0];
            expect(firstItem).toHaveProperty('filename');
            expect(firstItem).toHaveProperty('prompt');
            expect(firstItem).toHaveProperty('model');
            expect(firstItem).toHaveProperty('duration');
            expect(firstItem).toHaveProperty('rating');
        }
    });

    test('should be able to rate via API', async ({ page }) => {
        // Get first item from API
        const historyResponse = await page.request.get(`${BASE_URL}/history`);
        const items = await historyResponse.json();

        if (items.length === 0) {
            test.skip();
            return;
        }

        const filename = items[0].filename;

        // Rate the item
        const rateResponse = await page.request.post(`${BASE_URL}/rate`, {
            data: {
                filename: filename,
                rating: 'up'
            }
        });

        expect(rateResponse.ok()).toBeTruthy();

        const result = await rateResponse.json();
        expect(result.success).toBe(true);

        // Remove the rating
        await page.request.post(`${BASE_URL}/rate`, {
            data: {
                filename: filename,
                rating: null
            }
        });
    });
});
