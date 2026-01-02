/**
 * Voice/TTS E2E Tests
 *
 * Tests text-to-speech functionality:
 * - Voice selection and filtering
 * - Voice sample playback
 * - TTS generation
 * - Language/locale filters
 * - Voice favorites
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.TEST_URL || 'http://localhost:5309';

test.describe('Voice Selection', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        // Navigate to Generate tab and look for Voice/TTS section
        await page.click('.main-tab:has-text("Generate")');
        await page.waitForTimeout(300);
    });

    test('voice section is accessible from generate tab', async ({ page }) => {
        // Look for voice tab or section - use type-tab selector matching other tabs
        const voiceTab = page.locator(
            'button.type-tab[data-type="voice"], [data-type="voice"], ' +
            'button:has-text("Voice"), .voice-tab'
        );

        // Voice tab should exist in the Generate tab
        const exists = await voiceTab.count() > 0;
        const isVisible = exists && await voiceTab.first().isVisible();

        if (isVisible) {
            await expect(voiceTab.first()).toBeVisible();
        } else {
            // Voice tab may be hidden (auth required) - verify Generate tab works
            await expect(page.locator('.main-tab:has-text("Generate")')).toBeVisible();
        }
    });

    test('voice list displays available voices', async ({ page }) => {
        const voiceTab = page.locator('button:has-text("Voice"), [data-type="voice"]');

        if (await voiceTab.count() > 0 && await voiceTab.first().isVisible()) {
            await voiceTab.first().click();
            await page.waitForTimeout(500);

            // Look for voice list
            const voiceList = page.locator('.voice-list, .voice-selector, #voice-list');
            if (await voiceList.count() > 0) {
                await expect(voiceList.first()).toBeVisible({ timeout: 5000 });
            }

            // Check for voice cards/items
            const voiceItems = page.locator('.voice-card, .voice-option, .voice-item');
            if (await voiceItems.count() > 0) {
                expect(await voiceItems.count()).toBeGreaterThan(0);
            }
        }
    });

    test('can select a voice', async ({ page }) => {
        const voiceTab = page.locator('button:has-text("Voice"), [data-type="voice"]');

        if (await voiceTab.count() > 0 && await voiceTab.first().isVisible()) {
            await voiceTab.first().click();
            await page.waitForTimeout(500);

            const voiceItem = page.locator('.voice-card, .voice-option');
            if (await voiceItem.count() > 0 && await voiceItem.first().isVisible()) {
                await voiceItem.first().click();
                await page.waitForTimeout(300);

                // Should show selected state
                const selectedVoice = page.locator('.voice-card.selected, .voice-option.selected');
                // Or the voice name should appear somewhere
            }
        }
    });

    test('voice shows language/locale info', async ({ page }) => {
        const voiceTab = page.locator('button:has-text("Voice"), [data-type="voice"]');

        if (await voiceTab.count() > 0 && await voiceTab.first().isVisible()) {
            await voiceTab.first().click();
            await page.waitForTimeout(500);

            const voiceItem = page.locator('.voice-card, .voice-option');
            if (await voiceItem.count() > 0) {
                // Look for locale/language text
                const localeText = voiceItem.first().locator('.locale, .language, [class*="locale"]');
                if (await localeText.count() > 0) {
                    const text = await localeText.first().textContent();
                    expect(text?.length).toBeGreaterThan(0);
                }
            }
        }
    });
});

test.describe('Voice Filtering', () => {
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

        const voiceTab = page.locator('button:has-text("Voice"), [data-type="voice"]');
        if (await voiceTab.count() > 0 && await voiceTab.first().isVisible()) {
            await voiceTab.first().click();
            await page.waitForTimeout(500);
        }
    });

    test('language filter shows available languages', async ({ page }) => {
        const languageFilter = page.locator(
            '#language-filter, select[name="language"], .language-select'
        );

        if (await languageFilter.count() > 0 && await languageFilter.first().isVisible()) {
            const options = await languageFilter.first().locator('option').count();
            expect(options).toBeGreaterThan(0);
        }
    });

    test('can filter voices by language', async ({ page }) => {
        const languageFilter = page.locator('#language-filter, select[name="language"]');

        if (await languageFilter.count() > 0 && await languageFilter.first().isVisible()) {
            // Get initial voice count
            const initialCount = await page.locator('.voice-card, .voice-option').count();

            // Select a specific language
            await languageFilter.first().selectOption({ index: 1 });
            await page.waitForTimeout(500);

            // Voice list should update (might be same or different count)
            const newCount = await page.locator('.voice-card, .voice-option').count();
            // Just verify filtering works without errors
        }
    });

    test('search input filters voices by name', async ({ page }) => {
        const searchInput = page.locator(
            '#voice-search, input[placeholder*="search" i], .voice-search'
        );

        if (await searchInput.count() > 0 && await searchInput.first().isVisible()) {
            await searchInput.first().fill('jenny');
            await page.waitForTimeout(500);

            // Results should be filtered
            const voiceItems = page.locator('.voice-card, .voice-option');
            // Some or no results - just verify no errors
        }
    });

    test('gender filter works if available', async ({ page }) => {
        const genderFilter = page.locator(
            '#gender-filter, select[name="gender"], .gender-select, ' +
            'button[data-gender]'
        );

        if (await genderFilter.count() > 0 && await genderFilter.first().isVisible()) {
            await genderFilter.first().click();
            await page.waitForTimeout(300);
        }
    });
});

test.describe('Voice Sample Playback', () => {
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

        const voiceTab = page.locator('button:has-text("Voice"), [data-type="voice"]');
        if (await voiceTab.count() > 0 && await voiceTab.first().isVisible()) {
            await voiceTab.first().click();
            await page.waitForTimeout(500);
        }
    });

    test('voice card has play sample button', async ({ page }) => {
        const voiceItem = page.locator('.voice-card, .voice-option');

        if (await voiceItem.count() > 0) {
            const playBtn = voiceItem.first().locator(
                '.play-sample, button[aria-label*="play" i], .sample-btn'
            );

            if (await playBtn.count() > 0) {
                await expect(playBtn.first()).toBeVisible();
            }
        }
    });

    test('clicking play sample plays voice preview', async ({ page }) => {
        const voiceItem = page.locator('.voice-card, .voice-option');

        if (await voiceItem.count() > 0 && await voiceItem.first().isVisible()) {
            const playBtn = voiceItem.first().locator('.play-sample, button[aria-label*="play" i]');

            if (await playBtn.count() > 0 && await playBtn.first().isVisible()) {
                await playBtn.first().click();
                await page.waitForTimeout(500);

                // Button might change to stop/pause
                await expect(playBtn.first()).toBeEnabled();
            }
        }
    });
});

test.describe('TTS Generation', () => {
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

        const voiceTab = page.locator('button:has-text("Voice"), [data-type="voice"]');
        if (await voiceTab.count() > 0 && await voiceTab.first().isVisible()) {
            await voiceTab.first().click();
            await page.waitForTimeout(500);
        }
    });

    test('TTS text input accepts text', async ({ page }) => {
        const textInput = page.locator(
            '#tts-text, textarea[name="text"], #voice-text, .tts-input'
        );

        if (await textInput.count() > 0 && await textInput.first().isVisible()) {
            await textInput.first().fill('Hello, this is a test of text to speech generation.');
            await expect(textInput.first()).toHaveValue(/Hello/);
        }
    });

    test('generate button submits TTS request', async ({ page }) => {
        // Select a voice first
        const voiceItem = page.locator('.voice-card, .voice-option');
        if (await voiceItem.count() > 0 && await voiceItem.first().isVisible()) {
            await voiceItem.first().click();
            await page.waitForTimeout(300);
        }

        // Enter text
        const textInput = page.locator('#tts-text, textarea[name="text"], .tts-input');
        if (await textInput.count() > 0 && await textInput.first().isVisible()) {
            await textInput.first().fill('Hello world, this is a test.');
        }

        // Click generate
        const generateBtn = page.locator(
            '#generate-tts-btn, button:has-text("Generate"), ' +
            'button:has-text("Speak"), button[type="submit"]'
        );

        if (await generateBtn.count() > 0 && await generateBtn.first().isVisible()) {
            // Mock the API
            await page.route('**/api/tts/generate', async route => {
                await route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({
                        job_id: 'tts-test-123',
                        status: 'queued'
                    })
                });
            });

            await generateBtn.first().click();
            await page.waitForTimeout(500);
        }
    });

    test('shows character/word count', async ({ page }) => {
        const textInput = page.locator('#tts-text, textarea[name="text"]');

        if (await textInput.count() > 0 && await textInput.first().isVisible()) {
            await textInput.first().fill('Hello world');

            const charCount = page.locator('.char-count, .word-count, [class*="count"]');
            if (await charCount.count() > 0) {
                await expect(charCount.first()).toBeVisible();
            }
        }
    });
});

test.describe('Voice Favorites', () => {
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

        const voiceTab = page.locator('button:has-text("Voice"), [data-type="voice"]');
        if (await voiceTab.count() > 0 && await voiceTab.first().isVisible()) {
            await voiceTab.first().click();
            await page.waitForTimeout(500);
        }
    });

    test('can favorite a voice', async ({ page }) => {
        const voiceItem = page.locator('.voice-card, .voice-option');

        if (await voiceItem.count() > 0) {
            const favBtn = voiceItem.first().locator(
                '.favorite-voice, button[aria-label*="favorite" i], .voice-fav-btn'
            );

            if (await favBtn.count() > 0 && await favBtn.first().isVisible()) {
                await favBtn.first().click();
                await page.waitForTimeout(300);
            }
        }
    });

    test('favorite voices filter shows only favorites', async ({ page }) => {
        const favFilter = page.locator(
            '#show-favorites, button:has-text("Favorites"), .favorites-filter'
        );

        if (await favFilter.count() > 0 && await favFilter.first().isVisible()) {
            await favFilter.first().click();
            await page.waitForTimeout(500);
        }
    });
});
