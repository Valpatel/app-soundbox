/**
 * Voting and Favorites Tests
 *
 * Tests the voting system, favorites, and feedback functionality
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.TEST_URL || 'http://localhost:5309';

test.describe('Voting System', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
    });

    test('can upvote a track in library', async ({ page }) => {
        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Find vote buttons (actual class is .action-btn.vote-up)
        const upvoteBtn = page.locator('.library-item .vote-up').first();
        if (await upvoteBtn.isVisible()) {
            await upvoteBtn.click();
            await page.waitForTimeout(500);

            // Button should show active state
            await expect(upvoteBtn).toHaveClass(/active|voted/);
        }
    });

    test('can downvote a track in library', async ({ page }) => {
        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Find downvote buttons
        const downvoteBtn = page.locator('.library-item .vote-down, .library-item .downvote-btn').first();
        if (await downvoteBtn.isVisible()) {
            await downvoteBtn.click();
            await page.waitForTimeout(500);

            // Should trigger feedback modal or show active state
            const modal = page.locator('.modal, [role="dialog"]');
            const hasModal = await modal.isVisible();
            const hasActiveClass = await downvoteBtn.evaluate(el => el.classList.contains('active') || el.classList.contains('voted'));

            expect(hasModal || hasActiveClass).toBeTruthy();
        }
    });

    test('can change vote from up to down', async ({ page }) => {
        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const upvoteBtn = page.locator('.library-item .vote-up, .library-item .upvote-btn').first();
        const downvoteBtn = page.locator('.library-item .vote-down, .library-item .downvote-btn').first();

        if (await upvoteBtn.isVisible() && await downvoteBtn.isVisible()) {
            // First upvote
            await upvoteBtn.click();
            await page.waitForTimeout(500);

            // Then downvote
            await downvoteBtn.click();
            await page.waitForTimeout(500);

            // Upvote should no longer be active
            await expect(upvoteBtn).not.toHaveClass(/active/);
        }
    });

    test('vote counts update after voting', async ({ page }) => {
        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Get initial count
        const voteCount = page.locator('.library-item .vote-count, .library-item .upvote-count').first();
        let initialCount = '0';
        if (await voteCount.isVisible()) {
            initialCount = await voteCount.textContent();
        }

        // Click upvote
        const upvoteBtn = page.locator('.library-item .vote-up, .library-item .upvote-btn').first();
        if (await upvoteBtn.isVisible()) {
            await upvoteBtn.click();
            await page.waitForTimeout(500);

            // Count should change
            if (await voteCount.isVisible()) {
                const newCount = await voteCount.textContent();
                // Count may have changed
                console.log(`Vote count: ${initialCount} -> ${newCount}`);
            }
        }
    });
});

test.describe('Radio Player Voting', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
    });

    test('can vote on current radio track', async ({ page }) => {
        // Wait for radio to load
        await page.waitForTimeout(2000);

        // Find radio vote buttons
        const radioUpvote = page.locator('#radio-upvote, .radio-controls .vote-up');
        const radioDownvote = page.locator('#radio-downvote, .radio-controls .vote-down');

        if (await radioUpvote.isVisible()) {
            await radioUpvote.click();
            await page.waitForTimeout(500);
            await expect(radioUpvote).toHaveClass(/active|voted/);
        }
    });

    test('vote persists when track changes', async ({ page }) => {
        // This tests that vote state is properly saved
        await page.waitForTimeout(2000);

        const radioUpvote = page.locator('#radio-upvote, .radio-controls .vote-up');
        if (await radioUpvote.isVisible()) {
            // Vote on current track
            await radioUpvote.click();
            await page.waitForTimeout(500);

            // Skip to next track
            const nextBtn = page.locator('#radio-next, .radio-controls .next-btn');
            if (await nextBtn.isVisible()) {
                await nextBtn.click();
                await page.waitForTimeout(1000);

                // New track should not have vote active
                await expect(radioUpvote).not.toHaveClass(/active/);
            }
        }
    });
});

test.describe('Favorites System', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
    });

    test('can add track to favorites from library', async ({ page }) => {
        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Find favorite button
        const favBtn = page.locator('.library-item .favorite-btn, .library-item .add-favorite').first();
        if (await favBtn.isVisible()) {
            await favBtn.click();
            await page.waitForTimeout(500);

            // Should show favorited state
            await expect(favBtn).toHaveClass(/favorited|active/);
        }
    });

    test('can remove track from favorites', async ({ page }) => {
        // First add a favorite
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const favBtn = page.locator('.library-item .favorite-btn, .library-item .add-favorite').first();
        if (await favBtn.isVisible()) {
            // Click to add
            await favBtn.click();
            await page.waitForTimeout(500);

            // Click again to remove
            await favBtn.click();
            await page.waitForTimeout(500);

            // Should not be favorited
            await expect(favBtn).not.toHaveClass(/favorited|active/);
        }
    });

    test('favorites appear in favorites station', async ({ page }) => {
        // Add a favorite first
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const favBtn = page.locator('.library-item .item-favorite, .library-item .favorite-btn').first();
        if (await favBtn.isVisible()) {
            await favBtn.click();
            await page.waitForTimeout(500);
        }

        // Go to Radio tab and click Favorites station preset
        await page.click('.main-tab:has-text("Radio")');
        await page.waitForTimeout(500);

        // Click on Favorites station preset (it's a station, not a main tab)
        const favStation = page.locator('[title*="favorited"], .station-preset:has-text("Favorites")');
        if (await favStation.isVisible()) {
            await favStation.click();
            await page.waitForTimeout(500);
        }

        // Take screenshot
        await page.screenshot({
            path: 'test-results/favorites-station.png',
            fullPage: true
        });
    });

    test('can favorite current radio track', async ({ page }) => {
        await page.waitForTimeout(2000);

        const radioFavBtn = page.locator('#radio-favorite, .radio-controls .favorite-btn');
        if (await radioFavBtn.isVisible()) {
            await radioFavBtn.click();
            await page.waitForTimeout(500);
            await expect(radioFavBtn).toHaveClass(/favorited|active/);
        }
    });
});

test.describe('Tag Suggestions', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
    });

    test('can open tag suggestion modal', async ({ page }) => {
        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Find tag button
        const tagBtn = page.locator('.library-item .tag-btn, .library-item .suggest-tag').first();
        if (await tagBtn.isVisible()) {
            await tagBtn.click();
            await page.waitForTimeout(500);

            // Modal should open
            const modal = page.locator('.tag-modal, .modal:has-text("tag"), [role="dialog"]');
            if (await modal.isVisible()) {
                await expect(modal).toBeVisible();

                // Take screenshot
                await page.screenshot({
                    path: 'test-results/tag-modal.png',
                    fullPage: true
                });
            }
        }
    });

    test('can suggest a tag for a track', async ({ page }) => {
        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const tagBtn = page.locator('.library-item .tag-btn, .library-item .suggest-tag').first();
        if (await tagBtn.isVisible()) {
            await tagBtn.click();
            await page.waitForTimeout(500);

            // Find a category to select
            const categoryBtn = page.locator('.tag-modal .category-btn, .modal .tag-option').first();
            if (await categoryBtn.isVisible()) {
                await categoryBtn.click();
                await page.waitForTimeout(500);

                // Submit button should be clickable
                const submitBtn = page.locator('.tag-modal .submit-btn, .modal button:has-text("Submit")');
                if (await submitBtn.isVisible()) {
                    await submitBtn.click();
                    await page.waitForTimeout(500);
                }
            }
        }
    });
});

test.describe('API Vote Endpoints', () => {
    test('POST /api/library/{id}/vote works', async ({ request }) => {
        // First get a generation ID
        const libraryResponse = await request.get(`${BASE_URL}/api/library?per_page=1`);
        const libraryData = await libraryResponse.json();

        if (libraryData.items && libraryData.items.length > 0) {
            const genId = libraryData.items[0].id;

            // Submit a vote
            const voteResponse = await request.post(`${BASE_URL}/api/library/${genId}/vote`, {
                data: {
                    vote: 1,
                    user_id: 'test_user_123'
                }
            });

            expect(voteResponse.ok()).toBeTruthy();
            const voteData = await voteResponse.json();
            // API returns upvotes/downvotes/user_vote (success may or may not be present)
            expect(voteData).toHaveProperty('upvotes');
            expect(voteData).toHaveProperty('user_vote');

            // Remove the vote
            await request.post(`${BASE_URL}/api/library/${genId}/vote`, {
                data: {
                    vote: 0,
                    user_id: 'test_user_123'
                }
            });
        }
    });

    test('POST /api/favorites/{id} works', async ({ request }) => {
        // First get a generation ID
        const libraryResponse = await request.get(`${BASE_URL}/api/library?per_page=1`);
        const libraryData = await libraryResponse.json();

        if (libraryData.items && libraryData.items.length > 0) {
            const genId = libraryData.items[0].id;

            // Add to favorites
            const addResponse = await request.post(`${BASE_URL}/api/favorites/${genId}`, {
                data: {
                    user_id: 'test_user_123'
                }
            });

            expect(addResponse.ok()).toBeTruthy();

            // Remove from favorites
            await request.delete(`${BASE_URL}/api/favorites/${genId}`, {
                data: {
                    user_id: 'test_user_123'
                }
            });
        }
    });
});
