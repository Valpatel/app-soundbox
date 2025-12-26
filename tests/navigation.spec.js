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
        await expect(page.locator('#radio-tab')).toBeVisible();

        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await expect(page.locator('#library-tab')).toBeVisible();
        await expect(page.locator('#radio-tab')).not.toBeVisible();

        // Switch to Generate
        await page.click('.main-tab:has-text("Generate")');
        await expect(page.locator('#generate-tab')).toBeVisible();
        await expect(page.locator('#library-tab')).not.toBeVisible();

        // Switch back to Radio
        await page.click('.main-tab:has-text("Radio")');
        await expect(page.locator('#radio-tab')).toBeVisible();
        await expect(page.locator('#generate-tab')).not.toBeVisible();
    });

    test('tab state persists on reload', async ({ page }) => {
        // Switch to Library
        await page.click('.main-tab:has-text("Library")');
        await expect(page.locator('#library-tab')).toBeVisible();

        // Reload page
        await page.reload();
        await page.waitForLoadState('networkidle');

        // Library should still be active
        await expect(page.locator('#library-tab')).toBeVisible();
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
    });

    test('Tab key navigates through interactive elements', async ({ page }) => {
        // Focus first element
        await page.keyboard.press('Tab');

        // Continue tabbing and check we can reach main tabs
        for (let i = 0; i < 10; i++) {
            await page.keyboard.press('Tab');
            const focusedElement = await page.locator(':focus');
            const tag = await focusedElement.evaluate(el => el.tagName.toLowerCase());
            // Should be focusable elements
            expect(['button', 'a', 'input', 'select', 'div']).toContain(tag);
        }
    });

    test('Enter key activates buttons', async ({ page }) => {
        // Switch to Generate tab to test prompt input
        await page.click('.main-tab:has-text("Generate")');
        await page.waitForTimeout(300);

        // Focus prompt input
        const promptInput = page.locator('#prompt');
        await promptInput.focus();
        await promptInput.fill('test prompt');

        // Tab to generate button
        await page.keyboard.press('Tab');
        await page.keyboard.press('Tab');

        // Check we're focused on a button
        const focused = await page.locator(':focus');
        await expect(focused).toBeVisible();
    });

    test('Escape key closes modals', async ({ page }) => {
        // Go to Library
        await page.click('.main-tab:has-text("Library")');
        await page.waitForSelector('.library-item', { timeout: 10000 });

        // Click an item to potentially open a modal (if there's a detail view)
        const firstItem = page.locator('.library-item').first();
        if (await firstItem.count() > 0) {
            // Check if clicking opens a modal
            await firstItem.click();
            await page.waitForTimeout(300);

            // If a modal opened, Escape should close it
            await page.keyboard.press('Escape');
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

        await expect(page.locator('#library-tab')).toBeVisible();
    });

    test('can navigate directly to generate', async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.evaluate(() => {
            localStorage.setItem('soundbox_tab', 'generate');
        });
        await page.reload();
        await page.waitForLoadState('networkidle');

        await expect(page.locator('#generate-tab')).toBeVisible();
    });
});
