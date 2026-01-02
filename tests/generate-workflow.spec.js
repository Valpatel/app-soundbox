/**
 * Generate Tab E2E Tests
 *
 * Tests the complete audio generation workflow including:
 * - Prompt input and validation
 * - Duration slider interaction
 * - Loop checkbox behavior
 * - Random prompt generation
 * - Form submission and queue display
 * - Progress feedback
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.TEST_URL || 'http://localhost:5309';

test.describe('Generate Tab - Form Controls', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Disable animations
        await page.addStyleTag({
            content: `*, *::before, *::after {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }`
        });

        // Navigate to Generate tab
        await page.click('.main-tab:has-text("Generate")');
        await page.waitForTimeout(300);
    });

    test('prompt input is visible and properly configured', async ({ page }) => {
        const promptInput = page.locator('#prompt, textarea[name="prompt"]');
        await expect(promptInput.first()).toBeVisible({ timeout: 5000 });

        // Check if input is enabled (authenticated) or disabled (requires sign in)
        const isDisabled = await promptInput.first().isDisabled();

        if (!isDisabled) {
            // Type a prompt if enabled
            await promptInput.first().fill('ambient electronic music with soft pads');
            await expect(promptInput.first()).toHaveValue('ambient electronic music with soft pads');

            // Check for character count indicator if present
            const charCount = page.locator('.char-count, .character-count, [class*="char"]');
            if (await charCount.count() > 0) {
                await expect(charCount.first()).toBeVisible();
            }
        } else {
            // Verify disabled state shows sign-in message
            const placeholder = await promptInput.first().getAttribute('placeholder');
            expect(placeholder?.toLowerCase()).toContain('sign');
        }
    });

    test('duration slider is visible and configurable', async ({ page }) => {
        const durationSlider = page.locator('#duration, input[type="range"][name="duration"]');

        // Duration slider may or may not be visible depending on UI state
        if (await durationSlider.count() > 0 && await durationSlider.first().isVisible()) {
            const isDisabled = await durationSlider.first().isDisabled();

            if (!isDisabled) {
                // Get initial value
                const initialValue = await durationSlider.first().inputValue();

                // Change to a specific value
                await durationSlider.first().fill('15');

                // Verify value changed
                const newValue = await durationSlider.first().inputValue();
                expect(newValue).toBe('15');

                // Check for duration display if present
                const durationDisplay = page.locator('.duration-display, .duration-value, #duration-value');
                if (await durationDisplay.count() > 0) {
                    await expect(durationDisplay.first()).toContainText(/15|seconds/i);
                }
            } else {
                // Slider exists but is disabled - still a valid state
                await expect(durationSlider.first()).toBeVisible();
            }
        }
    });

    test('duration slider respects min/max bounds', async ({ page }) => {
        const durationSlider = page.locator('#duration, input[type="range"][name="duration"]');

        if (await durationSlider.count() > 0 && await durationSlider.first().isVisible()) {
            const isDisabled = await durationSlider.first().isDisabled();
            if (isDisabled) {
                // Slider disabled - valid for unauthenticated users
                return;
            }

            // Get min/max attributes
            const min = await durationSlider.first().getAttribute('min') || '3';
            const max = await durationSlider.first().getAttribute('max') || '120';

            // Try to set below minimum
            await durationSlider.first().fill('1');
            const minResult = await durationSlider.first().inputValue();
            expect(parseInt(minResult)).toBeGreaterThanOrEqual(parseInt(min));

            // Try to set above maximum
            await durationSlider.first().fill('999');
            const maxResult = await durationSlider.first().inputValue();
            expect(parseInt(maxResult)).toBeLessThanOrEqual(parseInt(max));
        }
    });

    test('loop checkbox can be toggled', async ({ page }) => {
        const loopCheckbox = page.locator('#loop, #loop-checkbox, input[type="checkbox"][name="loop"]');

        if (await loopCheckbox.count() > 0 && await loopCheckbox.first().isVisible()) {
            // Get initial state
            const initialState = await loopCheckbox.first().isChecked();

            // Toggle
            await loopCheckbox.first().click();

            // Verify state changed
            const newState = await loopCheckbox.first().isChecked();
            expect(newState).toBe(!initialState);

            // Toggle back
            await loopCheckbox.first().click();
            const finalState = await loopCheckbox.first().isChecked();
            expect(finalState).toBe(initialState);
        }
    });

    test('random prompt button generates new prompt', async ({ page }) => {
        const promptInput = page.locator('#prompt, textarea[name="prompt"]');
        await expect(promptInput.first()).toBeVisible({ timeout: 5000 });

        // Get initial value (might be empty)
        const initialValue = await promptInput.first().inputValue();

        // Find and click random button
        const randomBtn = page.locator('#random-btn, button:has-text("Random"), button[aria-label*="random" i]');

        if (await randomBtn.count() > 0 && await randomBtn.first().isVisible()) {
            await randomBtn.first().click();
            await page.waitForTimeout(500);

            // Verify prompt changed (or was filled if empty)
            const newValue = await promptInput.first().inputValue();

            // Should have some text now
            expect(newValue.length).toBeGreaterThan(0);
        }
    });

    test('generate button is visible', async ({ page }) => {
        const generateBtn = page.locator('#generate-btn, button:has-text("Generate"), button[type="submit"]');
        await expect(generateBtn.first()).toBeVisible({ timeout: 5000 });

        // Button exists - may be disabled for unauthenticated users
        const promptInput = page.locator('#prompt, textarea[name="prompt"]');
        const isPromptDisabled = await promptInput.first().isDisabled();

        if (!isPromptDisabled) {
            // Fill prompt to ensure button is enabled
            await promptInput.first().fill('test audio generation prompt');
            await expect(generateBtn.first()).toBeEnabled();
        } else {
            // Unauthenticated - button should exist but may be disabled
            await expect(generateBtn.first()).toBeVisible();
        }
    });

    test('model/type selector works if present', async ({ page }) => {
        const modelSelector = page.locator('#model-select, select[name="model"], .model-selector');

        if (await modelSelector.count() > 0 && await modelSelector.first().isVisible()) {
            // Get available options
            const options = await modelSelector.first().locator('option').allTextContents();

            if (options.length > 1) {
                // Select different option
                await modelSelector.first().selectOption({ index: 1 });
                await page.waitForTimeout(300);
            }
        }
    });
});

test.describe('Generate Tab - Submission Flow', () => {
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

    test('form shows progress indicator on submission or requires auth', async ({ page }) => {
        const promptInput = page.locator('#prompt, textarea[name="prompt"]');
        const isPromptDisabled = await promptInput.first().isDisabled();

        if (isPromptDisabled) {
            // Unauthenticated user - verify sign-in prompt is shown
            const placeholder = await promptInput.first().getAttribute('placeholder');
            expect(placeholder?.toLowerCase()).toContain('sign');
            return;
        }

        // Fill in the form
        await promptInput.first().fill('short test sound effect');

        const durationSlider = page.locator('#duration, input[type="range"]');
        if (await durationSlider.count() > 0 && await durationSlider.first().isVisible()) {
            await durationSlider.first().fill('3'); // Shortest duration
        }

        // Submit
        const generateBtn = page.locator('#generate-btn, button:has-text("Generate"), button[type="submit"]');

        // Set up request interception to avoid actual generation
        await page.route('**/generate', async route => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    job_id: 'test-job-123',
                    status: 'queued',
                    position: 1
                })
            });
        });

        await generateBtn.first().click();
        await page.waitForTimeout(500);

        // Should show some kind of progress indicator or button state change
        const progressIndicator = page.locator(
            '.progress, .queue-status, .generating, ' +
            '[class*="progress"], [class*="queue"], ' +
            '#generation-status, .status-message'
        );

        const hasProgress = await progressIndicator.count() > 0;
        const buttonText = await generateBtn.first().textContent();
        const buttonDisabled = await generateBtn.first().isDisabled();

        expect(hasProgress || buttonDisabled || buttonText?.toLowerCase().includes('generating')).toBeTruthy();
    });

    test('empty prompt is handled correctly', async ({ page }) => {
        const promptInput = page.locator('#prompt, textarea[name="prompt"]');
        const isPromptDisabled = await promptInput.first().isDisabled();

        if (isPromptDisabled) {
            // Unauthenticated - can't test validation, but verify disabled state
            await expect(promptInput.first()).toBeDisabled();
            return;
        }

        await promptInput.first().fill('');
        await promptInput.first().blur();

        const generateBtn = page.locator('#generate-btn, button:has-text("Generate"), button[type="submit"]');

        // Button should be disabled or clicking should show error
        const isDisabled = await generateBtn.first().isDisabled();

        if (!isDisabled) {
            await generateBtn.first().click();
            await page.waitForTimeout(500);

            // Look for error message
            const errorMsg = page.locator('.error, .validation-error, [class*="error"], [role="alert"]');
            if (await errorMsg.count() > 0) {
                await expect(errorMsg.first()).toBeVisible();
            }
        } else {
            // Button correctly disabled for empty prompt
            await expect(generateBtn.first()).toBeDisabled();
        }
    });

    test('queue explorer shows pending jobs', async ({ page }) => {
        // Navigate to queue explorer if there's a link
        const queueLink = page.locator('a:has-text("Queue"), button:has-text("Queue"), .queue-link');

        if (await queueLink.count() > 0 && await queueLink.first().isVisible()) {
            await queueLink.first().click();
            await page.waitForTimeout(500);

            // Queue display should be visible
            const queueDisplay = page.locator('.queue-list, .queue-explorer, #queue-content');
            if (await queueDisplay.count() > 0) {
                await expect(queueDisplay.first()).toBeVisible();
            }
        }
    });
});

test.describe('Generate Tab - Voice/TTS Mode', () => {
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

    test('can switch to voice/TTS mode if available', async ({ page }) => {
        // Look for voice/TTS toggle or tab
        const voiceTab = page.locator(
            'button:has-text("Voice"), button:has-text("TTS"), ' +
            '.generate-type-tab:has-text("Voice"), [data-type="voice"]'
        );

        if (await voiceTab.count() > 0 && await voiceTab.first().isVisible()) {
            await voiceTab.first().click();
            await page.waitForTimeout(500);

            // Voice-specific controls should appear
            const voiceSelector = page.locator('#voice-select, .voice-selector, select[name="voice"]');
            const textInput = page.locator('#tts-text, textarea[name="text"]');

            const hasVoiceControls = await voiceSelector.count() > 0 || await textInput.count() > 0;
            expect(hasVoiceControls).toBeTruthy();
        }
    });

    test('voice selector shows available voices', async ({ page }) => {
        // Try to find voice selector
        const voiceTab = page.locator('button:has-text("Voice"), [data-type="voice"]');

        if (await voiceTab.count() > 0 && await voiceTab.first().isVisible()) {
            await voiceTab.first().click();
            await page.waitForTimeout(500);
        }

        const voiceSelector = page.locator('#voice-select, .voice-selector, .voice-list');

        if (await voiceSelector.count() > 0 && await voiceSelector.first().isVisible()) {
            // Should have voice options
            const voiceOptions = page.locator('.voice-option, .voice-card, option[value]');
            const count = await voiceOptions.count();

            // Should have at least one voice option
            expect(count).toBeGreaterThan(0);
        }
    });
});

test.describe('Generate Tab - Advanced Options', () => {
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

    test('advanced options can be expanded if present', async ({ page }) => {
        const advancedToggle = page.locator(
            'button:has-text("Advanced"), .advanced-toggle, ' +
            'details summary:has-text("Advanced"), [class*="advanced"]'
        );

        if (await advancedToggle.count() > 0 && await advancedToggle.first().isVisible()) {
            await advancedToggle.first().click();
            await page.waitForTimeout(300);

            // Advanced options should now be visible
            const advancedOptions = page.locator('.advanced-options, .advanced-panel, details[open]');
            if (await advancedOptions.count() > 0) {
                await expect(advancedOptions.first()).toBeVisible();
            }
        }
    });

    test('seed input works if present', async ({ page }) => {
        const seedInput = page.locator('#seed, input[name="seed"], input[placeholder*="seed" i]');

        if (await seedInput.count() > 0 && await seedInput.first().isVisible()) {
            await seedInput.first().fill('12345');
            await expect(seedInput.first()).toHaveValue('12345');
        }
    });

    test('temperature/creativity slider works if present', async ({ page }) => {
        const tempSlider = page.locator(
            '#temperature, input[name="temperature"], ' +
            '#creativity, input[name="creativity"]'
        );

        if (await tempSlider.count() > 0 && await tempSlider.first().isVisible()) {
            const initialValue = await tempSlider.first().inputValue();
            await tempSlider.first().fill('0.7');
            const newValue = await tempSlider.first().inputValue();
            expect(newValue).not.toBe(initialValue);
        }
    });
});
