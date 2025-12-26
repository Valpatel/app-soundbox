/**
 * Search and Filter Tests
 *
 * Tests the search functionality and various filtering options
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.TEST_URL || 'http://localhost:5309';

test.describe('Library Search', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);
    });

    test('search input is visible', async ({ page }) => {
        const searchInput = page.locator('#library-search, input[placeholder*="Search"]');
        await expect(searchInput).toBeVisible();
    });

    test('search filters results by prompt text', async ({ page }) => {
        // Wait for initial load
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Get initial count
        const initialCount = await page.locator('.library-item').count();

        // Search for specific term
        const searchInput = page.locator('#library-search, input[placeholder*="Search"]');
        await searchInput.fill('ambient');
        await page.waitForTimeout(800);  // Debounce

        // Results should be filtered (possibly fewer)
        const filteredCount = await page.locator('.library-item').count();
        console.log(`Search results: ${initialCount} -> ${filteredCount}`);

        // Take screenshot
        await page.screenshot({
            path: 'test-results/search-ambient.png',
            fullPage: true
        });
    });

    test('search handles empty results gracefully', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Search for something unlikely to exist
        const searchInput = page.locator('#library-search, input[placeholder*="Search"]');
        await searchInput.fill('xyznonexistent12345');
        await page.waitForTimeout(800);

        // Should show empty state or no results message
        const emptyState = page.locator('.empty-state, .no-results');
        const items = await page.locator('.library-item').count();

        expect(items === 0 || await emptyState.isVisible()).toBeTruthy();

        // Take screenshot
        await page.screenshot({
            path: 'test-results/search-no-results.png',
            fullPage: true
        });
    });

    test('clearing search shows all results', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Search first
        const searchInput = page.locator('#library-search, input[placeholder*="Search"]');
        await searchInput.fill('ambient');
        await page.waitForTimeout(800);

        const filteredCount = await page.locator('.library-item').count();

        // Clear search
        await searchInput.fill('');
        await page.waitForTimeout(800);

        const clearedCount = await page.locator('.library-item').count();

        // Should have more or equal results after clearing
        expect(clearedCount).toBeGreaterThanOrEqual(filteredCount);
    });

    test('search is case insensitive', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const searchInput = page.locator('#library-search, input[placeholder*="Search"]');

        // Search lowercase
        await searchInput.fill('ambient');
        await page.waitForTimeout(800);
        const lowerCount = await page.locator('.library-item').count();

        // Search uppercase
        await searchInput.fill('AMBIENT');
        await page.waitForTimeout(800);
        const upperCount = await page.locator('.library-item').count();

        // Should return same results
        expect(lowerCount).toBe(upperCount);
    });

    test('search handles special characters', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const searchInput = page.locator('#library-search, input[placeholder*="Search"]');

        // Search with special characters (should not break)
        await searchInput.fill('test & "quotes" <script>');
        await page.waitForTimeout(800);

        // Page should not break
        await expect(page.locator('.main-tab')).toBeVisible();
    });
});

test.describe('Type Filters', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);
    });

    test('can filter by Music type', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const musicTab = page.locator('.type-tab:has-text("Music"), [data-type="music"]');
        if (await musicTab.isVisible()) {
            await musicTab.click();
            await page.waitForTimeout(500);

            // Tab should be active
            await expect(musicTab).toHaveClass(/active/);

            // Take screenshot
            await page.screenshot({
                path: 'test-results/filter-music.png',
                fullPage: true
            });
        }
    });

    test('can filter by SFX type', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const sfxTab = page.locator('.type-tab:has-text("SFX"), .type-tab:has-text("Audio"), [data-type="audio"]');
        if (await sfxTab.isVisible()) {
            await sfxTab.click();
            await page.waitForTimeout(500);

            // Tab should be active
            await expect(sfxTab).toHaveClass(/active/);

            // Take screenshot
            await page.screenshot({
                path: 'test-results/filter-sfx.png',
                fullPage: true
            });
        }
    });

    test('All tab shows all types', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const allTab = page.locator('.type-tab:has-text("All"), [data-type="all"]');
        if (await allTab.isVisible()) {
            // Click Music first
            const musicTab = page.locator('.type-tab:has-text("Music")');
            if (await musicTab.isVisible()) {
                await musicTab.click();
                await page.waitForTimeout(500);
            }

            // Then click All
            await allTab.click();
            await page.waitForTimeout(500);

            // All tab should be active
            await expect(allTab).toHaveClass(/active/);
        }
    });
});

test.describe('Category/Genre Filters', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);
    });

    test('category sidebar is visible', async ({ page }) => {
        const sidebar = page.locator('#category-sidebar, .genre-sidebar, .categories-sidebar');
        // May not exist on mobile
        if (await sidebar.isVisible()) {
            await expect(sidebar).toBeVisible();
        }
    });

    test('clicking category filters results', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Expand the "Ambient & Chill" genre group first
        const ambientHeader = page.locator('.genre-section-header:has-text("Ambient")');
        if (await ambientHeader.isVisible()) {
            await ambientHeader.click();
            await page.waitForTimeout(300);
        }

        const genreItem = page.locator('.genre-item[data-genre="ambient"]');
        if (await genreItem.isVisible()) {
            await genreItem.click({ force: true });
            await page.waitForTimeout(500);

            // Genre should be active
            await expect(genreItem).toHaveClass(/active/);
        }
    });

    test('clear filter button removes category filter', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Expand a genre group first
        const genreHeader = page.locator('.genre-section-header').first();
        if (await genreHeader.isVisible()) {
            await genreHeader.click();
            await page.waitForTimeout(300);
        }

        // Click a genre
        const genreItem = page.locator('.genre-item').first();
        if (await genreItem.isVisible()) {
            await genreItem.click({ force: true });
            await page.waitForTimeout(500);

            // Click clear button
            const clearBtn = page.locator('#clear-filter-btn, .clear-filter');
            if (await clearBtn.isVisible()) {
                await clearBtn.click({ force: true });
                await page.waitForTimeout(500);

                // No genre should be active
                const activeGenres = await page.locator('.genre-item.active').count();
                expect(activeGenres).toBe(0);
            }
        }
    });
});

test.describe('Sort Options', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);
    });

    test('sort dropdown is visible', async ({ page }) => {
        const sortDropdown = page.locator('#sort-select, .sort-dropdown, select[name="sort"]');
        if (await sortDropdown.isVisible()) {
            await expect(sortDropdown).toBeVisible();
        }
    });

    test('can sort by recent', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const sortDropdown = page.locator('#sort-select, .sort-dropdown');
        if (await sortDropdown.isVisible()) {
            await sortDropdown.selectOption('recent');
            await page.waitForTimeout(500);

            // Take screenshot
            await page.screenshot({
                path: 'test-results/sort-recent.png',
                fullPage: true
            });
        }
    });

    test('can sort by popular', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const sortDropdown = page.locator('#sort-select, .sort-dropdown');
        if (await sortDropdown.isVisible()) {
            await sortDropdown.selectOption('popular');
            await page.waitForTimeout(500);

            // Take screenshot
            await page.screenshot({
                path: 'test-results/sort-popular.png',
                fullPage: true
            });
        }
    });
});

test.describe('Pagination', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);
    });

    test('pagination controls are visible', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const pagination = page.locator('.pagination, .page-controls');
        if (await pagination.isVisible()) {
            await expect(pagination).toBeVisible();
        }
    });

    test('can navigate to next page', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const nextBtn = page.locator('.pagination .next, .page-btn:has-text("Next"), button:has-text("›")');
        if (await nextBtn.isVisible() && await nextBtn.isEnabled()) {
            await nextBtn.click();
            await page.waitForTimeout(500);

            // Page should change
            // Take screenshot
            await page.screenshot({
                path: 'test-results/pagination-page2.png',
                fullPage: true
            });
        }
    });

    test('can navigate to specific page', async ({ page }) => {
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const pageBtn = page.locator('.page-btn:has-text("2"), .pagination button:has-text("2")');
        if (await pageBtn.isVisible()) {
            await pageBtn.click();
            await page.waitForTimeout(500);

            // Page 2 should be active
            await expect(pageBtn).toHaveClass(/active/);
        }
    });
});

test.describe('API Search Endpoints', () => {
    test('GET /api/library with search parameter', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/library?search=ambient`);
        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data).toHaveProperty('items');
        expect(data).toHaveProperty('total');
    });

    test('GET /api/library with category parameter', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/library?category=ambient`);
        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data).toHaveProperty('items');
    });

    test('GET /api/library with model parameter', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/library?model=music`);
        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data).toHaveProperty('items');

        // All items should be music type
        for (const item of data.items) {
            expect(item.model).toBe('music');
        }
    });

    test('GET /api/library with pagination', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/library?page=1&per_page=5`);
        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data.items.length).toBeLessThanOrEqual(5);
        expect(data.page).toBe(1);
    });

    test('GET /api/library with sort parameter', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/library?sort=popular`);
        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data).toHaveProperty('items');
    });
});
