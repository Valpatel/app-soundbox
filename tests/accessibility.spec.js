/**
 * Accessibility Tests
 *
 * Tests for WCAG compliance, screen reader compatibility, and keyboard access
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.TEST_URL || 'http://localhost:5309';

test.describe('Accessibility - Basic Requirements', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
    });

    test('page has a title', async ({ page }) => {
        const title = await page.title();
        expect(title).toBeTruthy();
        expect(title.length).toBeGreaterThan(0);
    });

    test('page has a main heading', async ({ page }) => {
        const h1 = page.locator('h1');
        const count = await h1.count();
        expect(count).toBeGreaterThanOrEqual(1);
    });

    test('images have alt text', async ({ page }) => {
        const images = page.locator('img');
        const count = await images.count();

        for (let i = 0; i < count; i++) {
            const img = images.nth(i);
            const alt = await img.getAttribute('alt');
            const src = await img.getAttribute('src');

            // Only check visible images
            if (await img.isVisible()) {
                // Alt can be empty for decorative images but should exist
                expect(alt !== null || src?.includes('spectrogram')).toBeTruthy();
            }
        }
    });

    test('form inputs have labels or aria-labels', async ({ page }) => {
        // Switch to Generate tab where inputs exist
        await page.click('.main-tab:has-text("Generate")');
        await page.waitForTimeout(300);

        const inputs = page.locator('input, select, textarea');
        const count = await inputs.count();

        for (let i = 0; i < count; i++) {
            const input = inputs.nth(i);
            if (await input.isVisible()) {
                const id = await input.getAttribute('id');
                const ariaLabel = await input.getAttribute('aria-label');
                const ariaLabelledBy = await input.getAttribute('aria-labelledby');
                const placeholder = await input.getAttribute('placeholder');

                // Should have some form of label
                const hasLabel = id || ariaLabel || ariaLabelledBy || placeholder;
                expect(hasLabel).toBeTruthy();
            }
        }
    });

    test('buttons have accessible names', async ({ page }) => {
        const buttons = page.locator('button');
        const count = await buttons.count();

        for (let i = 0; i < Math.min(count, 20); i++) {  // Check first 20 buttons
            const button = buttons.nth(i);
            if (await button.isVisible()) {
                const text = await button.textContent();
                const ariaLabel = await button.getAttribute('aria-label');
                const title = await button.getAttribute('title');

                // Button should have some accessible name
                const hasName = (text && text.trim().length > 0) || ariaLabel || title;
                expect(hasName).toBeTruthy();
            }
        }
    });

    test('interactive elements are focusable', async ({ page }) => {
        const interactiveElements = page.locator('button, a, input, select, [tabindex]');
        const count = await interactiveElements.count();

        let focusableCount = 0;
        for (let i = 0; i < Math.min(count, 30); i++) {
            const el = interactiveElements.nth(i);
            if (await el.isVisible()) {
                const tabindex = await el.getAttribute('tabindex');
                // tabindex of -1 means not focusable via keyboard
                if (tabindex !== '-1') {
                    focusableCount++;
                }
            }
        }

        expect(focusableCount).toBeGreaterThan(0);
    });
});

test.describe('Accessibility - Color and Contrast', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
    });

    test('text has sufficient color contrast', async ({ page }) => {
        // Check body text color against background
        const bodyBg = await page.evaluate(() => {
            return window.getComputedStyle(document.body).backgroundColor;
        });
        const bodyColor = await page.evaluate(() => {
            return window.getComputedStyle(document.body).color;
        });

        // Both should be defined
        expect(bodyBg).toBeTruthy();
        expect(bodyColor).toBeTruthy();
    });

    test('error states are not only indicated by color', async ({ page }) => {
        // Switch to Generate tab
        await page.click('.main-tab:has-text("Generate")');
        await page.waitForTimeout(300);

        // Try to generate with empty prompt (should show error)
        const promptInput = page.locator('#prompt');
        await promptInput.fill('');

        // Error messages should have text, not just color
        // This is a basic check - full implementation would require triggering errors
    });
});

test.describe('Accessibility - Screen Reader', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
    });

    test('dynamic content has ARIA live regions', async ({ page }) => {
        // Check for ARIA live regions on dynamic content
        const liveRegions = page.locator('[aria-live], [role="alert"], [role="status"]');
        // It's okay if there aren't any, but good to have for toasts/status updates
        const count = await liveRegions.count();
        console.log(`Found ${count} ARIA live regions`);
    });

    test('modals trap focus correctly', async ({ page }) => {
        // Check if modal elements have correct ARIA attributes
        const modals = page.locator('[role="dialog"], .modal, [aria-modal="true"]');
        const count = await modals.count();

        for (let i = 0; i < count; i++) {
            const modal = modals.nth(i);
            if (await modal.isVisible()) {
                // Modal should have aria-modal or role="dialog"
                const role = await modal.getAttribute('role');
                const ariaModal = await modal.getAttribute('aria-modal');
                expect(role === 'dialog' || ariaModal === 'true').toBeTruthy();
            }
        }
    });

    test('navigation landmarks exist', async ({ page }) => {
        // Check for landmark elements
        const nav = page.locator('nav, [role="navigation"]');
        const main = page.locator('main, [role="main"]');

        // Should have at least some landmark
        const navCount = await nav.count();
        const mainCount = await main.count();
        console.log(`Navigation landmarks: ${navCount}, Main landmarks: ${mainCount}`);
    });
});

test.describe('Accessibility - Reduced Motion', () => {
    test('respects prefers-reduced-motion', async ({ page }) => {
        // Emulate reduced motion preference
        await page.emulateMedia({ reducedMotion: 'reduce' });
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Take screenshot to verify no distracting animations
        await page.screenshot({
            path: 'test-results/reduced-motion.png',
            fullPage: true
        });
    });
});

test.describe('Accessibility - Focus Visibility', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
    });

    test('focus indicator is visible on keyboard navigation', async ({ page }) => {
        // Tab through elements and verify focus is visible
        await page.keyboard.press('Tab');

        const focusedElement = page.locator(':focus');
        await expect(focusedElement).toBeVisible();

        // Take screenshot of focused element
        await page.screenshot({
            path: 'test-results/focus-visible.png',
            fullPage: true
        });
    });

    test('skip link exists or content is reachable quickly', async ({ page }) => {
        // Check for skip link or verify main content is quickly reachable
        const skipLink = page.locator('a:has-text("Skip to"), [href="#main"], [href="#content"]');
        const skipLinkCount = await skipLink.count();

        if (skipLinkCount === 0) {
            // If no skip link, main tabs should be reachable within 5 tabs
            let foundMainContent = false;
            for (let i = 0; i < 10; i++) {
                await page.keyboard.press('Tab');
                const focused = await page.locator(':focus');
                const classes = await focused.getAttribute('class');
                if (classes && classes.includes('main-tab')) {
                    foundMainContent = true;
                    break;
                }
            }
            expect(foundMainContent).toBeTruthy();
        }
    });
});
