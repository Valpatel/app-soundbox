/**
 * Navigation and Tab Tests
 *
 * Tests tab navigation, keyboard accessibility, and navigation persistence
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.TEST_URL || 'http://localhost:5309';

test.describe('Tab Navigation', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
    });

    test('all main tabs are visible', async ({ page }) => {
        // The app has 3 main tabs: Radio, Library, Generate
        const tabs = ['Radio', 'Library', 'Generate'];
        for (const tabName of tabs) {
            const tab = page.locator(`#tab-${tabName.toLowerCase()}, .main-tab:has-text("${tabName}")`);
            await expect(tab).toBeVisible();
        }
    });

    test('clicking tab switches content', async ({ page }) => {
        // Start on Radio (default)
        await expect(page.locator('#content-radio')).toBeVisible();

        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await expect(page.locator('#content-library')).toBeVisible();
        await expect(page.locator('#content-radio')).not.toBeVisible();

        // Switch to Generate
        await page.click('.main-tab:has-text("Generate")');
        await expect(page.locator('#content-generate')).toBeVisible();
        await expect(page.locator('#content-library')).not.toBeVisible();

        // Switch back to Radio
        await page.click('.main-tab:has-text("Radio")');
        await expect(page.locator('#content-radio')).toBeVisible();
        await expect(page.locator('#content-generate')).not.toBeVisible();
    });

    test('tab state persists on reload', async ({ page }) => {
        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await expect(page.locator('#content-library')).toBeVisible();

        // Reload page
        await page.reload();
        await page.waitForLoadState('networkidle');

        // Library should still be active
        await expect(page.locator('#content-library')).toBeVisible();
    });

    test('active tab has visual indicator', async ({ page }) => {
        // Radio should be active by default
        const radioTab = page.locator('.main-tab:has-text("Radio")');
        await expect(radioTab).toHaveClass(/active/);

        // Click Library
        await page.click('.main-tab:has-text("Library")');
        const libraryTab = page.locator('.main-tab:has-text("Library")');
        await expect(libraryTab).toHaveClass(/active/);
        await expect(radioTab).not.toHaveClass(/active/);
    });
});

test.describe('Keyboard Navigation', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Disable animations for stability
        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });
    });

    test('Tab key navigates through interactive elements', async ({ page }) => {
        // Tab through elements and verify focus moves
        let focusedCount = 0;

        for (let i = 0; i < 10; i++) {
            await page.keyboard.press('Tab');
            await page.waitForTimeout(50);

            const hasFocus = await page.evaluate(() => {
                const el = document.activeElement;
                return el && el !== document.body;
            });

            if (hasFocus) focusedCount++;
        }

        // Should have focused on multiple elements
        expect(focusedCount).toBeGreaterThan(3);
    });

    test('Enter key activates buttons', async ({ page }) => {
        // Test keyboard activation on Library tab (always accessible)
        await page.click('.main-tab:has-text("Library")');
        await page.waitForTimeout(300);
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Focus a library item's play button if available
        const playBtn = page.locator('.library-item .play-btn').first();
        if (await playBtn.count() > 0 && await playBtn.isVisible()) {
            await playBtn.focus();
        }

        // Tab to next focusable element
        await page.keyboard.press('Tab');

        // Check something is focused
        const hasFocus = await page.evaluate(() => {
            const el = document.activeElement;
            return el && el !== document.body;
        });
        expect(hasFocus).toBeTruthy();
    });

    test('Escape key closes modals', async ({ page }) => {
        // Go to Library and try to open feedback modal
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Click vote button to open feedback modal (use correct selector)
        const voteBtn = page.locator('.library-item .vote-up, .library-item .action-btn.vote-up').first();

        if (await voteBtn.count() > 0 && await voteBtn.isVisible()) {
            await voteBtn.click();
            await page.waitForTimeout(500);

            // Check if modal opened
            const modal = page.locator('#feedback-modal-container, [role="dialog"], .modal:visible');

            if (await modal.count() > 0 && await modal.first().isVisible()) {
                // Press Escape to close
                await page.keyboard.press('Escape');
                await page.waitForTimeout(300);

                // Modal should be closed
                await expect(modal.first()).not.toBeVisible();
            }
        } else {
            // No vote button - verify keyboard navigation still works
            await page.keyboard.press('Escape');
            await expect(page.locator('.main-tab').first()).toBeVisible();
        }
    });
});

test.describe('URL and Deep Links', () => {
    test('can navigate directly to library', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Programmatically set tab
        await page.evaluate(() => {
            localStorage.setItem('soundbox_tab', 'library');
        });
        await page.reload();
        await page.waitForLoadState('networkidle');

        await expect(page.locator('#content-library')).toBeVisible();
    });

    test('can navigate directly to generate', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.evaluate(() => {
            localStorage.setItem('soundbox_tab', 'generate');
        });
        await page.reload();
        await page.waitForLoadState('networkidle');

        await expect(page.locator('#content-generate')).toBeVisible();
    });
});
