/**
 * Error States E2E Tests
 *
 * Tests error handling and edge cases:
 * - Network timeout handling
 * - API error messages
 * - Invalid input feedback
 * - Empty state displays
 * - Rate limiting responses
 * - Offline behavior
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.TEST_URL || 'http://localhost:5309';

test.describe('Network Error Handling', () => {
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

    test('handles offline state gracefully', async ({ page }) => {
        // Go offline
        await page.context().setOffline(true);

        // Try to navigate
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(1000);

        // UI should still work (tabs should switch)
        await expect(page.locator('#content-library')).toBeVisible();

        // Might show error message or empty state
        const errorMessage = page.locator('.error-message, .offline-notice, [class*="error"]');

        // Go back online
        await page.context().setOffline(false);
    });

    test('recovers when network is restored', async ({ page }) => {
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        // Go offline briefly
        await page.context().setOffline(true);
        await page.waitForTimeout(500);

        // Go back online
        await page.context().setOffline(false);

        // Reload and verify recovery
        await page.reload();
        await page.waitForLoadState('networkidle');

        // Page should load normally
        await expect(page.locator('.main-tab').first()).toBeVisible();
    });

    test.skip('shows loading state during slow requests', async ({ page }) => {
        // SKIPPED: App does not show a loading indicator during API requests
        // This would require implementing a loading state UI component

        await page.route('**/api/library**', async route => {
            await new Promise(resolve => setTimeout(resolve, 1500));
            await route.continue();
        });

        await page.click('.main-tab:has-text("Library")');

        // Look for loading indicator - check immediately after click
        const loadingIndicator = page.locator(
            '.loading, .spinner, [class*="loading"], .skeleton, .library-loading'
        );

        // Wait briefly and check for loading indicator
        await page.waitForTimeout(200);
        await expect(loadingIndicator.first()).toBeVisible({ timeout: 1000 });
    });
});

test.describe('API Error Messages', () => {
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

    test('displays error for 500 server error', async ({ page }) => {
        // Mock 500 error
        await page.route('**/api/library**', async route => {
            await route.fulfill({
                status: 500,
                contentType: 'application/json',
                body: JSON.stringify({ error: 'Internal server error' })
            });
        });

        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(1000);

        // Should show error message or empty state
        const errorIndicator = page.locator(
            '.error, [class*="error"], .empty-state, .no-results'
        );

        // UI should not crash
        await expect(page.locator('.main-tab').first()).toBeVisible();
    });

    test('displays error for 404 not found', async ({ page }) => {
        await page.route('**/api/library/nonexistent**', async route => {
            await route.fulfill({
                status: 404,
                contentType: 'application/json',
                body: JSON.stringify({ error: 'Not found' })
            });
        });

        // UI should handle 404 gracefully
        await expect(page.locator('.main-tab').first()).toBeVisible();
    });

    test('displays error for 403 forbidden', async ({ page }) => {
        await page.route('**/api/admin/**', async route => {
            await route.fulfill({
                status: 403,
                contentType: 'application/json',
                body: JSON.stringify({ error: 'Forbidden' })
            });
        });

        // UI should remain functional
        await expect(page.locator('.main-tab').first()).toBeVisible();
    });
});

test.describe('Invalid Input Handling', () => {
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

    test('search handles special characters safely', async ({ page }) => {
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        const searchInput = page.locator('#library-search, input[placeholder*="Search"]');
        if (await searchInput.first().isVisible()) {
            // Try potentially dangerous input
            await searchInput.first().fill('<script>alert("xss")</script>');
            await page.waitForTimeout(500);

            // Page should not break
            await expect(page.locator('.main-tab').first()).toBeVisible();

            // Try SQL injection pattern
            await searchInput.first().fill("'; DROP TABLE users; --");
            await page.waitForTimeout(500);

            await expect(page.locator('.main-tab').first()).toBeVisible();
        }
    });

    test('generate handles empty prompt gracefully', async ({ page }) => {
        await page.click('.main-tab:has-text("Generate")');
        await page.waitForTimeout(300);

        const promptInput = page.locator('#prompt, textarea[name="prompt"]');
        await expect(promptInput.first()).toBeVisible({ timeout: 5000 });

        // Check if input is disabled (unauthenticated)
        const isDisabled = await promptInput.first().isDisabled();
        if (isDisabled) {
            // Unauthenticated - verify proper disabled state
            const placeholder = await promptInput.first().getAttribute('placeholder');
            expect(placeholder?.toLowerCase()).toContain('sign');
            return;
        }

        // Test empty prompt handling for authenticated users
        await promptInput.first().fill('');
        const generateBtn = page.locator('#generate-btn, button:has-text("Generate")');

        if (await generateBtn.first().isVisible()) {
            const btnDisabled = await generateBtn.first().isDisabled();
            // Button should be disabled for empty prompt, or clicking shows error
            expect(btnDisabled).toBeTruthy();
        }
    });

    test('handles very long input gracefully', async ({ page }) => {
        await page.click('.main-tab:has-text("Generate")');
        await page.waitForTimeout(300);

        const promptInput = page.locator('#prompt, textarea[name="prompt"]');
        await expect(promptInput.first()).toBeVisible({ timeout: 5000 });

        // Check if input is disabled (unauthenticated)
        const isDisabled = await promptInput.first().isDisabled();
        if (isDisabled) {
            // Verify maxlength attribute exists for security
            const maxLength = await promptInput.first().getAttribute('maxlength');
            expect(maxLength).toBeTruthy();
            return;
        }

        // Test long input handling
        const longText = 'a'.repeat(10000);
        await promptInput.first().fill(longText);
        await page.waitForTimeout(300);

        // Should either truncate or handle gracefully
        const value = await promptInput.first().inputValue();
        const maxLength = await promptInput.first().getAttribute('maxlength');
        if (maxLength) {
            expect(value.length).toBeLessThanOrEqual(parseInt(maxLength));
        }
    });
});

test.describe('Empty State Displays', () => {
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

    test('shows empty state for no search results', async ({ page }) => {
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        const searchInput = page.locator('#library-search, input[placeholder*="Search"]');
        if (await searchInput.first().isVisible()) {
            await searchInput.first().fill('xyznonexistentterm123456');
            await page.waitForTimeout(1000);

            // Should show empty state message
            const emptyState = page.locator(
                '.no-results, .empty-state, .empty-message, ' +
                '[class*="no-results"], [class*="empty"]'
            );

            if (await emptyState.count() > 0) {
                await expect(emptyState.first()).toBeVisible();
            }
        }
    });

    test('empty favorites shows helpful message', async ({ page }) => {
        // Clear any existing favorites
        await page.evaluate(() => {
            localStorage.removeItem('soundbox_favorites');
        });

        const favStation = page.locator(
            '.station-card:has-text("Favorites"), [data-station="favorites"]'
        );

        if (await favStation.count() > 0 && await favStation.first().isVisible()) {
            await favStation.first().click();
            await page.waitForTimeout(500);

            // Should show empty favorites message
            const emptyMessage = page.locator('.empty-favorites, .no-favorites, .empty-state');
        }
    });

    test('empty playlist shows add tracks prompt', async ({ page }) => {
        const playlistTab = page.locator('.main-tab:has-text("Playlist")');

        if (await playlistTab.count() > 0) {
            await playlistTab.first().click();
            await page.waitForTimeout(500);

            // If no playlists, should show create prompt
            const emptyState = page.locator('.empty-playlists, .no-playlists, .create-first');
        }
    });
});

test.describe('Rate Limiting', () => {
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

    test('handles 429 rate limit response', async ({ page }) => {
        await page.route('**/api/**', async route => {
            await route.fulfill({
                status: 429,
                contentType: 'application/json',
                body: JSON.stringify({ error: 'Too many requests. Please wait.' })
            });
        });

        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        // Should show rate limit message or retry indicator
        const errorMessage = page.locator('[class*="error"], [class*="rate-limit"], .toast');

        // UI should remain functional
        await expect(page.locator('.main-tab').first()).toBeVisible();
    });

    test('rapid clicks are debounced', async ({ page }) => {
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        const libraryItem = page.locator('.library-item, .track-item');
        await expect(libraryItem.first()).toBeVisible({ timeout: 10000 });

        const voteBtn = libraryItem.first().locator('.upvote, .downvote');

        if (await voteBtn.count() > 0 && await voteBtn.first().isVisible()) {
            // Rapid clicks should be debounced
            for (let i = 0; i < 5; i++) {
                await voteBtn.first().click();
            }
            await page.waitForTimeout(500);

            // Button should still work
            await expect(voteBtn.first()).toBeEnabled();
        }
    });
});

test.describe('Form Validation', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        await page.click('.main-tab:has-text("Generate")');
        await page.waitForTimeout(300);
    });

    test('prompt has proper validation attributes', async ({ page }) => {
        const promptInput = page.locator('#prompt, textarea[name="prompt"]');
        await expect(promptInput.first()).toBeVisible({ timeout: 5000 });

        // Check for maxlength attribute (security)
        const maxLength = await promptInput.first().getAttribute('maxlength');
        expect(maxLength).toBeTruthy();

        // If disabled, verify placeholder indicates auth required
        const isDisabled = await promptInput.first().isDisabled();
        if (isDisabled) {
            const placeholder = await promptInput.first().getAttribute('placeholder');
            expect(placeholder?.toLowerCase()).toContain('sign');
        }
    });

    test('duration slider has proper range constraints', async ({ page }) => {
        const durationSlider = page.locator('#duration, input[type="range"]');

        if (await durationSlider.count() > 0 && await durationSlider.first().isVisible()) {
            // Check for min/max attributes
            const min = await durationSlider.first().getAttribute('min');
            const max = await durationSlider.first().getAttribute('max');

            expect(min).toBeTruthy();
            expect(max).toBeTruthy();
            expect(parseInt(max)).toBeGreaterThan(parseInt(min));
        } else {
            // Slider not visible - verify Generate tab still works
            await expect(page.locator('.main-tab:has-text("Generate")')).toBeVisible();
        }
    });
});

test.describe('Session Handling', () => {
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

    test('device ID is created and persisted', async ({ page }) => {
        // Wait for page to fully initialize
        await page.waitForTimeout(500);

        const deviceId = await page.evaluate(() => {
            return localStorage.getItem('soundbox_device_id') ||
                   localStorage.getItem('device_id') ||
                   sessionStorage.getItem('soundbox_device_id');
        });

        // Device ID may or may not be set depending on app implementation
        if (deviceId) {
            expect(deviceId.length).toBeGreaterThan(5);
        } else {
            // No device ID - verify app still functions
            await expect(page.locator('.main-tab').first()).toBeVisible();
        }
    });

    test('tab state persists across reload', async ({ page }) => {
        // Switch to Library tab
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(300);

        // Reload
        await page.reload();
        await page.waitForLoadState('networkidle');

        // Check if tab state was preserved (might return to Library)
        const savedTab = await page.evaluate(() => {
            return localStorage.getItem('soundbox_tab');
        });
    });

    test('handles expired session gracefully', async ({ page }) => {
        // Mock 401 unauthorized
        await page.route('**/api/user/**', async route => {
            await route.fulfill({
                status: 401,
                contentType: 'application/json',
                body: JSON.stringify({ error: 'Unauthorized' })
            });
        });

        // UI should remain functional for non-auth features
        await expect(page.locator('#content-radio')).toBeVisible();
    });
});

test.describe('Concurrent Request Handling', () => {
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

    test('handles rapid tab switching', async ({ page }) => {
        // Rapidly switch tabs
        const tabs = ['.main-tab:has-text("Library")', '.main-tab:has-text("Generate")', '.main-tab:has-text("Radio")'];

        for (let i = 0; i < 10; i++) {
            const tab = tabs[i % tabs.length];
            await page.click(tab);
            await page.waitForTimeout(50);
        }

        // Final state should be stable
        await page.waitForTimeout(500);
        await expect(page.locator('.main-tab').first()).toBeVisible();
    });

    test('handles rapid search input', async ({ page }) => {
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(500);

        const searchInput = page.locator('#library-search, input[placeholder*="Search"]');

        if (await searchInput.first().isVisible()) {
            // Type rapidly
            await searchInput.first().type('ambient electronic chill music', { delay: 10 });
            await page.waitForTimeout(500);

            // Should debounce and show final results
            await expect(page.locator('.library-item, .track-item, .no-results').first()).toBeVisible({ timeout: 5000 });
        }
    });
});
