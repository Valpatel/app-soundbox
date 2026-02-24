/**
 * Screenshot generator for Sound Box README.
 *
 * Usage:
 *   node scripts/take-screenshots.js
 *
 * Requires:
 *   - Sound Box running at http://localhost:5309
 *   - Playwright installed (npx playwright install chromium)
 */

const { chromium } = require('playwright');
const path = require('path');

const BASE_URL = process.env.SOUNDBOX_URL || 'http://localhost:5309';
const OUTPUT_DIR = path.join(__dirname, '..', 'screenshots');

async function takeScreenshots() {
    const browser = await chromium.launch();
    const context = await browser.newContext({
        viewport: { width: 1280, height: 800 },
        deviceScaleFactor: 2,
    });
    const page = await context.newPage();

    console.log(`Connecting to ${BASE_URL}...`);
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    console.log('Page loaded.');

    // Wait for initial render
    await page.waitForTimeout(1000);

    // Radio tab (default view)
    console.log('Capturing radio tab...');
    await page.click('[data-tab="radio"]');
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUTPUT_DIR, 'radio.png') });

    // Library tab
    console.log('Capturing library tab...');
    await page.click('[data-tab="library"]');
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUTPUT_DIR, 'library.png') });

    // Generate tab
    console.log('Capturing generate tab...');
    await page.click('[data-tab="generate"]');
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUTPUT_DIR, 'generate.png') });

    // Fullscreen visualizer
    console.log('Capturing visualizer...');
    await page.click('[data-tab="radio"]');
    await page.waitForTimeout(500);
    // Try to enter fullscreen mode via the expand button
    const expandBtn = page.locator('.expand-btn, [data-action="fullscreen"], .fullscreen-btn').first();
    if (await expandBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await expandBtn.click();
        await page.waitForTimeout(1000);
    }
    await page.screenshot({ path: path.join(OUTPUT_DIR, 'visualizer.png') });

    await browser.close();
    console.log(`Screenshots saved to ${OUTPUT_DIR}/`);
}

takeScreenshots().catch((err) => {
    console.error('Screenshot failed:', err.message);
    console.error('Make sure Sound Box is running at', BASE_URL);
    process.exit(1);
});
