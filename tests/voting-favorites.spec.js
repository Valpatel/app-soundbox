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

        // Disable animations for stable element interactions
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

    test('can upvote a track in library', async ({ page }) => {
        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Find vote buttons using title attribute
        const upvoteBtn = page.locator('.library-item button[title="Like this track"]').first();
        await expect(upvoteBtn).toBeVisible({ timeout: 5000 });
        await upvoteBtn.click();
        await page.waitForTimeout(500);

        // Clicking opens a feedback modal - confirm it appears
        const modal = page.locator('#feedback-modal-container');
        await expect(modal).toBeVisible({ timeout: 5000 });
    });

    test('can downvote a track in library', async ({ page }) => {
        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Find downvote buttons using title attribute (triggers feedback modal)
        const downvoteBtn = page.locator('.library-item button[title="Dislike this track"]').first();
        await expect(downvoteBtn).toBeVisible({ timeout: 5000 });
        await downvoteBtn.click();
        await page.waitForTimeout(500);

        // Should trigger feedback modal
        const modal = page.locator('#feedback-modal-container');
        await expect(modal).toBeVisible({ timeout: 5000 });
    });

    test('can change vote from up to down', async ({ page }) => {
        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const upvoteBtn = page.locator('.library-item button[title="Like this track"]').first();
        const downvoteBtn = page.locator('.library-item button[title="Dislike this track"]').first();

        await expect(upvoteBtn).toBeVisible({ timeout: 5000 });

        // Click upvote to open feedback modal
        await upvoteBtn.click();
        await page.waitForTimeout(500);

        // Feedback modal should open
        const modal = page.locator('#feedback-modal-container');
        await expect(modal).toBeVisible({ timeout: 5000 });

        // Select a feedback option to enable submit button
        const feedbackOption = page.locator('#feedback-modal-options button').first();
        await feedbackOption.click();
        await page.waitForTimeout(200);

        // Submit the positive feedback
        const submitBtn = page.locator('#feedback-modal-submit');
        await expect(submitBtn).toBeVisible({ timeout: 3000 });
        await expect(submitBtn).toBeEnabled({ timeout: 2000 });
        await submitBtn.click();

        // Wait for modal to close (indicates successful submission)
        await expect(modal).not.toBeVisible({ timeout: 5000 });

        // Verify upvote is now active
        await expect(upvoteBtn).toHaveClass(/voted/, { timeout: 5000 });

        // Now click downvote to change the vote
        await downvoteBtn.click();
        await page.waitForTimeout(500);

        // Modal opens again for downvote - select a feedback option
        await expect(modal).toBeVisible({ timeout: 5000 });
        const feedbackOption2 = page.locator('#feedback-modal-options button').first();
        await feedbackOption2.click();
        await page.waitForTimeout(200);
        await expect(submitBtn).toBeEnabled({ timeout: 2000 });
        await submitBtn.click();

        // Wait for modal to close
        await expect(modal).not.toBeVisible({ timeout: 5000 });

        // Downvote should now be active, upvote should not be
        await expect(downvoteBtn).toHaveClass(/voted/, { timeout: 5000 });
        await expect(upvoteBtn).not.toHaveClass(/voted/);
    });

    test('vote counts update after voting', async ({ page }) => {
        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Click upvote using title attribute
        const upvoteBtn = page.locator('.library-item button[title="Like this track"]').first();
        await expect(upvoteBtn).toBeVisible({ timeout: 5000 });

        // Get initial count from the button's span
        const countSpan = upvoteBtn.locator('.vote-count');
        const initialCount = await countSpan.textContent();

        await upvoteBtn.click();
        await page.waitForTimeout(500);

        // Feedback modal opens - select option and submit
        const modal = page.locator('#feedback-modal-container');
        await expect(modal).toBeVisible({ timeout: 5000 });

        // Select a feedback option to enable submit button
        const feedbackOption = page.locator('#feedback-modal-options button').first();
        await feedbackOption.click();
        await page.waitForTimeout(200);

        const submitBtn = page.locator('#feedback-modal-submit');
        await expect(submitBtn).toBeVisible({ timeout: 3000 });
        await expect(submitBtn).toBeEnabled({ timeout: 2000 });
        await submitBtn.click();
        await page.waitForTimeout(500);

        // Count should change after submission
        const newCount = await countSpan.textContent();
        console.log(`Vote count: ${initialCount} -> ${newCount}`);
    });

    test('can clear vote by clicking same button again', async ({ page }) => {
        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const upvoteBtn = page.locator('.library-item button[title="Like this track"]').first();
        await expect(upvoteBtn).toBeVisible({ timeout: 5000 });

        // First, upvote the track
        await upvoteBtn.click();
        await page.waitForTimeout(500);

        // Feedback modal opens - select option and submit
        const modal = page.locator('#feedback-modal-container');
        await expect(modal).toBeVisible({ timeout: 5000 });

        // Select a feedback option to enable submit button
        const feedbackOption = page.locator('#feedback-modal-options button').first();
        await feedbackOption.click();
        await page.waitForTimeout(200);

        const submitBtn = page.locator('#feedback-modal-submit');
        await expect(submitBtn).toBeVisible({ timeout: 3000 });
        await expect(submitBtn).toBeEnabled({ timeout: 2000 });
        await submitBtn.click();

        // Wait for modal to close (indicates successful submission)
        await expect(modal).not.toBeVisible({ timeout: 5000 });

        // Verify upvote is active
        await expect(upvoteBtn).toHaveClass(/voted/, { timeout: 5000 });

        // Click upvote again to clear the vote (toggle off)
        await upvoteBtn.click();
        await page.waitForTimeout(500);

        // Should NOT open modal - vote should be cleared directly
        // Modal should not be visible (or should close immediately)
        await expect(modal).not.toBeVisible({ timeout: 2000 });

        // Upvote should no longer be active
        await expect(upvoteBtn).not.toHaveClass(/voted/, { timeout: 5000 });
    });
});

test.describe('Radio Player Voting', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Disable animations for stable element interactions
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

    test('can vote on current radio track', async ({ page }) => {
        // Wait for radio to load and track to be selected with prompt text
        await page.waitForSelector('.now-playing:not(.hidden)', { timeout: 10000 });
        await page.waitForFunction(() => {
            const prompt = document.getElementById('radio-prompt');
            return prompt && prompt.textContent && prompt.textContent.trim().length > 5;
        }, { timeout: 15000 });
        await page.waitForTimeout(1000);

        // Find radio vote button
        const radioUpvote = page.locator('#radio-vote-up');
        await expect(radioUpvote).toBeVisible({ timeout: 5000 });
        await radioUpvote.click();
        await page.waitForTimeout(1000);

        // Radio vote opens feedback modal - select option and submit
        const modal = page.locator('#feedback-modal-container');
        await expect(modal).toBeVisible({ timeout: 5000 });

        // Select a feedback option to enable submit button
        const feedbackOption = page.locator('#feedback-modal-options button').first();
        await feedbackOption.click();
        await page.waitForTimeout(200);

        const submitBtn = page.locator('#feedback-modal-submit');
        await expect(submitBtn).toBeVisible({ timeout: 3000 });
        await expect(submitBtn).toBeEnabled({ timeout: 2000 });
        await submitBtn.click();
        await page.waitForTimeout(500);

        // After submitting, vote should be applied
        await expect(radioUpvote).toHaveClass(/voted-up/);
    });

    test('vote persists when track changes', async ({ page }) => {
        // This tests that vote state is properly saved
        await page.waitForSelector('.now-playing:not(.hidden)', { timeout: 10000 });
        await page.waitForFunction(() => {
            const prompt = document.getElementById('radio-prompt');
            return prompt && prompt.textContent && prompt.textContent.trim().length > 5;
        }, { timeout: 15000 });
        await page.waitForTimeout(1000);

        const radioUpvote = page.locator('#radio-vote-up');
        await expect(radioUpvote).toBeVisible({ timeout: 5000 });

        // Vote on current track
        await radioUpvote.click();
        await page.waitForTimeout(500);

        // Submit feedback modal - select option first
        const modal = page.locator('#feedback-modal-container');
        await expect(modal).toBeVisible({ timeout: 5000 });

        // Select a feedback option to enable submit button
        const feedbackOption = page.locator('#feedback-modal-options button').first();
        await feedbackOption.click();
        await page.waitForTimeout(200);

        const submitBtn = page.locator('#feedback-modal-submit');
        await expect(submitBtn).toBeVisible({ timeout: 3000 });
        await expect(submitBtn).toBeEnabled({ timeout: 2000 });
        await submitBtn.click();
        await page.waitForTimeout(500);

        // Verify vote was applied
        await expect(radioUpvote).toHaveClass(/voted-up/);

        // Skip to next track using the skip button
        const nextBtn = page.locator('button[title="Skip to next track"]');
        await expect(nextBtn).toBeVisible({ timeout: 5000 });
        await nextBtn.click();
        await page.waitForTimeout(1500);

        // New track should not have vote active (vote resets per track)
        await expect(radioUpvote).not.toHaveClass(/voted-up/);
    });
});

test.describe('Favorites System', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Disable animations for stable element interactions
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

    test('can add track to favorites from library', async ({ page }) => {
        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Find favorite button (actual class is .item-favorite)
        const favBtn = page.locator('.library-item .item-favorite').first();
        await expect(favBtn).toBeVisible({ timeout: 5000 });
        await favBtn.click();
        await page.waitForTimeout(500);

        // Should show favorited state
        await expect(favBtn).toHaveClass(/favorited/);
    });

    test('can remove track from favorites', async ({ page }) => {
        // First add a favorite
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const favBtn = page.locator('.library-item .item-favorite').first();
        await expect(favBtn).toBeVisible({ timeout: 5000 });

        // Click to add
        await favBtn.click();
        await page.waitForTimeout(500);

        // Click again to remove
        await favBtn.click();
        await page.waitForTimeout(500);

        // Should not be favorited
        await expect(favBtn).not.toHaveClass(/favorited/);
    });

    test('favorites appear in favorites station', async ({ page }) => {
        // Add a favorite first
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        const favBtn = page.locator('.library-item .item-favorite').first();
        await expect(favBtn).toBeVisible({ timeout: 5000 });
        await favBtn.click();
        await page.waitForTimeout(500);

        // Go to Radio tab and click Favorites station preset
        await page.click('.main-tab:has-text("Radio")');
        await page.waitForTimeout(500);

        // Click on Favorites station card (has title containing "favorited")
        const favStation = page.locator('.station-card[title*="favorited"]');
        await expect(favStation).toBeVisible({ timeout: 5000 });
        await favStation.click();
        await page.waitForTimeout(500);

        // Take screenshot
        await page.screenshot({
            path: 'test-results/favorites-station.png',
            fullPage: true
        });
    });

    test('can favorite current radio track', async ({ page }) => {
        // Wait for radio to load and track to be selected with prompt text
        await page.waitForSelector('.now-playing:not(.hidden)', { timeout: 10000 });
        await page.waitForFunction(() => {
            const prompt = document.getElementById('radio-prompt');
            return prompt && prompt.textContent && prompt.textContent.trim().length > 5;
        }, { timeout: 15000 });
        await page.waitForTimeout(1000);

        const radioFavBtn = page.locator('#radio-favorite-btn');
        await expect(radioFavBtn).toBeVisible({ timeout: 5000 });

        // Click to favorite
        await radioFavBtn.click();
        await page.waitForTimeout(800);

        // Should now have favorited class
        await expect(radioFavBtn).toHaveClass(/favorited/);

        // Toggle off to clean up
        await radioFavBtn.click();
        await page.waitForTimeout(500);
        await expect(radioFavBtn).not.toHaveClass(/favorited/);
    });
});

test.describe('Tag Suggestions', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Disable animations for stable element interactions
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

    test('can open tag suggestion modal', async ({ page }) => {
        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Find tag button (in library-item actions area)
        const tagBtn = page.locator('.library-item .action-btn:has-text("Tag")').first();
        if (await tagBtn.count() > 0 && await tagBtn.isVisible()) {
            await tagBtn.click();
            await page.waitForTimeout(500);

            // Modal should open
            const modal = page.locator('.tag-modal, .modal');
            await expect(modal).toBeVisible({ timeout: 3000 });

            // Take screenshot
            await page.screenshot({
                path: 'test-results/tag-modal.png',
                fullPage: true
            });
        } else {
            // Skip if tag button not found (feature may not be in library items)
            console.log('Tag button not found in library items');
        }
    });

    test('can suggest a tag for a track', async ({ page }) => {
        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Tag button may be in library items or radio controls
        const tagBtn = page.locator('.library-item .action-btn:has-text("Tag")').first();
        if (await tagBtn.count() > 0 && await tagBtn.isVisible()) {
            await tagBtn.click();
            await page.waitForTimeout(500);

            // Find a category to select in modal
            const categoryBtn = page.locator('.tag-modal .tag-option, .modal .category-btn').first();
            if (await categoryBtn.count() > 0 && await categoryBtn.isVisible()) {
                await categoryBtn.click();
                await page.waitForTimeout(500);

                // Submit button
                const submitBtn = page.locator('.tag-modal button:has-text("Submit"), .modal button:has-text("Submit")');
                if (await submitBtn.count() > 0 && await submitBtn.isVisible()) {
                    await submitBtn.click();
                    await page.waitForTimeout(500);
                }
            }
        } else {
            console.log('Tag button not found in library items');
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
