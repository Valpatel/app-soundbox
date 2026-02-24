/**
 * Screenshot generator for Sound Box README.
 *
 * Takes screenshots of each major view for use in the project README.
 * Runs headed (not headless) so canvas visualizations render properly.
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
const fs = require('fs');

const BASE_URL = process.env.SOUNDBOX_URL || 'http://localhost:5309';
const OUTPUT_DIR = path.join(__dirname, '..', 'screenshots');

async function takeScreenshots() {
    // Ensure output directory exists
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });

    // Launch headed so canvas/WebGL renders properly
    const browser = await chromium.launch({ headless: false });
    const context = await browser.newContext({
        viewport: { width: 1280, height: 800 },
        deviceScaleFactor: 2,
        // Allow autoplay so audio starts without user gesture
        bypassCSP: true,
    });

    // Grant autoplay permission
    context.grantPermissions([], { origin: BASE_URL });

    const page = await context.newPage();

    // Auto-dismiss any dialogs
    page.on('dialog', dialog => dialog.dismiss());

    console.log(`Connecting to ${BASE_URL}...`);
    await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 });
    console.log('Page loaded.');
    await page.waitForTimeout(1500);

    // --- 1. Radio tab with a station playing ---
    console.log('1/5 Capturing radio tab...');
    await page.click('#tab-radio');
    await page.waitForTimeout(500);

    // Start the "All Music" station to populate the now-playing area
    await page.locator('.station-card.station-all').click({ force: true });
    // Wait for track info to appear (the prompt text replaces the placeholder)
    await page.waitForFunction(() => {
        const el = document.getElementById('radio-prompt');
        return el && el.textContent !== 'Pick a station to start' && el.textContent.length > 0;
    }, { timeout: 10000 }).catch(() => console.log('  (track info did not populate, continuing)'));
    await page.waitForTimeout(1500);

    // Scroll to top so station cards are fully visible
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);

    await page.screenshot({ path: path.join(OUTPUT_DIR, 'radio.png') });
    console.log('  -> radio.png');

    // --- 2. Library tab ---
    console.log('2/5 Capturing library tab...');
    await page.click('#tab-library');
    // Wait for library items to render
    await page.waitForFunction(() => {
        const grid = document.querySelector('.library-grid, .library-results, #library-results');
        return grid && grid.children.length > 0;
    }, { timeout: 8000 }).catch(() => console.log('  (library items did not load, continuing)'));
    await page.waitForTimeout(1000);

    await page.screenshot({ path: path.join(OUTPUT_DIR, 'library.png') });
    console.log('  -> library.png');

    // --- 3. Generate tab ---
    console.log('3/5 Capturing generate tab...');
    await page.click('#tab-generate');
    await page.waitForTimeout(800);

    // Type a sample prompt so the UI looks active
    const promptInput = page.locator('textarea#prompt');
    if (await promptInput.isVisible({ timeout: 2000 }).catch(() => false)) {
        await promptInput.fill('ambient forest soundscape with birdsong and gentle wind');
    }
    await page.waitForTimeout(500);

    await page.screenshot({ path: path.join(OUTPUT_DIR, 'generate.png') });
    console.log('  -> generate.png');

    // --- 4. Fullscreen visualizer ---
    console.log('4/5 Capturing visualizer...');
    // Go back to radio and make sure something is playing
    await page.click('#tab-radio');
    await page.waitForTimeout(500);

    // Create a fake fullscreen view by injecting the widget at viewport size
    // (native requestFullscreen doesn't work reliably in automated browsers)
    const hasVisualizer = await page.evaluate(() => {
        // Check if a track is loaded
        if (typeof currentRadioTrack === 'undefined' || !currentRadioTrack) return false;

        // Create fullscreen container covering the viewport
        let container = document.getElementById('screenshot-fullscreen');
        if (!container) {
            container = document.createElement('div');
            container.id = 'screenshot-fullscreen';
            container.setAttribute('data-branding', 'false');
            container.style.cssText = `
                position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
                z-index: 999999; background: #000;
            `;
            document.body.appendChild(container);
        }

        // Create a fullscreen-sized widget with visualizer
        if (typeof RadioWidget !== 'undefined') {
            const mainAudio = document.getElementById('radio-player');
            const widget = RadioWidget.create(container, {
                size: 'fullscreen',
                template: 'default',
                showBranding: false,
                connectToExisting: false,
                audioElement: mainAudio,
            });

            if (widget && widget.core) {
                widget.core.audioElement = mainAudio;
                widget.core.currentTrack = currentRadioTrack;
                widget.core.queue = typeof radioQueue !== 'undefined' ? [...radioQueue] : [];
                widget.core.isPlaying = !mainAudio.paused;
                widget.core._events.emit('trackChange', currentRadioTrack);
                widget.core._events.emit('playStateChange', !mainAudio.paused);
            }

            // Initialize visualizer after layout settles
            if (widget && widget._initVisualizer) {
                widget._initVisualizer();
            }
            return true;
        }
        return false;
    });

    if (hasVisualizer) {
        // Let the visualizer animate for a few frames
        await page.waitForTimeout(3000);
        await page.screenshot({ path: path.join(OUTPUT_DIR, 'visualizer.png') });
        console.log('  -> visualizer.png');

        // Clean up the overlay
        await page.evaluate(() => {
            const el = document.getElementById('screenshot-fullscreen');
            if (el) el.remove();
        });
    } else {
        console.log('  (no track playing, skipping visualizer — start a station first)');
    }

    // --- 5. Generate tab with progress (if a job is running) ---
    // Check if there's an active generation to show progress
    console.log('5/5 Checking for active generation...');
    const hasActiveJob = await page.evaluate(() => {
        const progress = document.querySelector('.generation-progress, #generation-progress');
        return progress && progress.offsetHeight > 0;
    });
    if (hasActiveJob) {
        await page.click('#tab-generate');
        await page.waitForTimeout(500);
        await page.screenshot({ path: path.join(OUTPUT_DIR, 'generating.png') });
        console.log('  -> generating.png');
    } else {
        console.log('  (no active generation, skipping progress screenshot)');
    }

    await browser.close();

    // List what was captured
    const files = fs.readdirSync(OUTPUT_DIR).filter(f => f.endsWith('.png'));
    console.log(`\nDone! ${files.length} screenshots saved to ${OUTPUT_DIR}/`);
    files.forEach(f => {
        const stats = fs.statSync(path.join(OUTPUT_DIR, f));
        console.log(`  ${f} (${(stats.size / 1024).toFixed(0)} KB)`);
    });
}

takeScreenshots().catch((err) => {
    console.error('Screenshot failed:', err.message);
    console.error('Make sure Sound Box is running at', BASE_URL);
    process.exit(1);
});
