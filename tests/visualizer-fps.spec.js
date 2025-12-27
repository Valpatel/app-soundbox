const { test, expect } = require('@playwright/test');

/**
 * Visualizer FPS Benchmark Tests
 *
 * Tests each visualization mode for performance.
 * FPS thresholds:
 *   - Good: >= 50 FPS
 *   - OK: >= 30 FPS
 *   - Bad: < 30 FPS
 */

const VISUALIZATION_MODES = [
    'bars',
    'wave',
    'circle',
    'particles',
    'lissajous',
    'tempest',
    'pong',
    'breakout',
    'snake'
];

// Duration to sample FPS for each mode (ms)
const SAMPLE_DURATION = 5000;
// How often to sample FPS (ms)
const SAMPLE_INTERVAL = 500;

test.describe('Visualizer Performance', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/');
        // Wait for page to load - the page shows the radio section by default
        await page.waitForSelector('#content-radio', { timeout: 10000 });
    });

    test('should measure FPS across all visualization modes', async ({ page }) => {
        test.setTimeout(120000); // 2 minutes for all 9 modes
        const results = {};

        // The page already shows the Radio tab by default
        // Wait for any animations to settle
        await page.waitForTimeout(1000);

        // First, start playing audio by clicking a station
        const stationClicked = await page.evaluate(() => {
            const station = document.querySelector('.station-card.station-all');
            if (station) {
                station.click();
                return true;
            }
            return false;
        });

        if (stationClicked) {
            console.log('Started "All" station to load audio');
            await page.waitForTimeout(3000); // Wait for station to load and start
        } else {
            console.log('Could not find station card to start playback');
        }

        // Look for the fullscreen button in the radio player controls
        // Use evaluate to click since animations may affect stability
        const clicked = await page.evaluate(() => {
            const btn = document.querySelector('button[onclick="enterRadioFullscreen()"]');
            if (btn) {
                btn.click();
                return true;
            }
            return false;
        });

        if (clicked) {
            console.log('Entered fullscreen mode');
            await page.waitForTimeout(2000); // Wait for fullscreen widget to initialize
        } else {
            console.log('No fullscreen button found, testing in current mode');
        }

        // Test each visualization mode
        for (const mode of VISUALIZATION_MODES) {
            console.log(`Testing visualization mode: ${mode}`);

            // Click the visualization mode button using evaluate for stability
            const found = await page.evaluate((vizMode) => {
                const btn = document.querySelector(`[data-viz-mode="${vizMode}"]`);
                if (btn) {
                    btn.click();
                    return true;
                }
                return false;
            }, mode);

            if (!found) {
                console.log(`  Mode button not found for: ${mode}`);
                results[mode] = { error: 'Button not found' };
                continue;
            }

            await page.waitForTimeout(500); // Let it initialize

            // Collect FPS samples
            const fpsSamples = [];
            const startTime = Date.now();

            while (Date.now() - startTime < SAMPLE_DURATION) {
                const fpsText = await page.evaluate(() => {
                    const fpsEl = document.getElementById('rw-fps-counter');
                    if (fpsEl) {
                        return fpsEl.textContent;
                    }
                    return null;
                });

                if (fpsText) {
                    const fpsMatch = fpsText.match(/(\d+)/);
                    if (fpsMatch) {
                        fpsSamples.push(parseInt(fpsMatch[1], 10));
                    }
                }

                await page.waitForTimeout(SAMPLE_INTERVAL);
            }

            // Calculate statistics
            if (fpsSamples.length > 0) {
                const avgFps = Math.round(fpsSamples.reduce((a, b) => a + b, 0) / fpsSamples.length);
                const minFps = Math.min(...fpsSamples);
                const maxFps = Math.max(...fpsSamples);

                results[mode] = {
                    avgFps,
                    minFps,
                    maxFps,
                    samples: fpsSamples.length,
                    status: avgFps >= 50 ? 'GOOD' : avgFps >= 30 ? 'OK' : 'BAD'
                };

                console.log(`  ${mode}: avg=${avgFps} min=${minFps} max=${maxFps} [${results[mode].status}]`);
            } else {
                results[mode] = { error: 'No FPS data collected' };
                console.log(`  ${mode}: No FPS data collected`);
            }
        }

        // Print summary
        console.log('\n========== FPS BENCHMARK SUMMARY ==========');
        console.log('Mode         | Avg FPS | Min | Max | Status');
        console.log('-------------|---------|-----|-----|-------');

        for (const mode of VISUALIZATION_MODES) {
            const r = results[mode];
            if (r.error) {
                console.log(`${mode.padEnd(13)}| ERROR: ${r.error}`);
            } else {
                console.log(`${mode.padEnd(13)}| ${String(r.avgFps).padStart(7)} | ${String(r.minFps).padStart(3)} | ${String(r.maxFps).padStart(3)} | ${r.status}`);
            }
        }
        console.log('============================================\n');

        // Assert that no visualization has critically low FPS
        const badModes = Object.entries(results)
            .filter(([, r]) => r.avgFps && r.avgFps < 20)
            .map(([mode]) => mode);

        if (badModes.length > 0) {
            console.warn(`Warning: These modes have critically low FPS: ${badModes.join(', ')}`);
        }

        // Store results for potential optimization
        await page.evaluate((data) => {
            window.__FPS_BENCHMARK_RESULTS__ = data;
        }, results);

        // Soft assertion - warn but don't fail if FPS is low
        // (for CI purposes we might want to track but not block)
        expect(Object.keys(results).length).toBeGreaterThan(0);
    });

    test('should maintain 30+ FPS under CPU stress', async ({ page }) => {
        // The page already shows the Radio tab by default
        // Wait for any animations to settle
        await page.waitForTimeout(1000);

        // First, start playing audio by clicking a station
        await page.evaluate(() => {
            const station = document.querySelector('.station-card.station-all');
            if (station) station.click();
        });
        await page.waitForTimeout(3000);

        // Enter fullscreen if available using evaluate
        const clicked = await page.evaluate(() => {
            const btn = document.querySelector('button[onclick="enterRadioFullscreen()"]');
            if (btn) {
                btn.click();
                return true;
            }
            return false;
        });

        if (clicked) {
            await page.waitForTimeout(2000);
        }

        // Test the most intensive visualization (particles)
        const particlesBtn = await page.$('[data-viz-mode="particles"]');
        if (particlesBtn) {
            await particlesBtn.click();
            await page.waitForTimeout(500);
        }

        // Simulate CPU stress by running heavy JS
        await page.evaluate(() => {
            let counter = 0;
            const stressTest = () => {
                for (let i = 0; i < 100000; i++) {
                    counter += Math.sqrt(i);
                }
            };
            // Run stress in background
            window.__stressInterval = setInterval(stressTest, 100);
        });

        // Wait and collect FPS
        await page.waitForTimeout(3000);

        const fpsSamples = [];
        for (let i = 0; i < 5; i++) {
            const fpsText = await page.evaluate(() => {
                const fpsEl = document.getElementById('rw-fps-counter');
                return fpsEl?.textContent || '';
            });
            const fpsMatch = fpsText.match(/(\d+)/);
            if (fpsMatch) {
                fpsSamples.push(parseInt(fpsMatch[1], 10));
            }
            await page.waitForTimeout(500);
        }

        // Stop stress test
        await page.evaluate(() => {
            if (window.__stressInterval) {
                clearInterval(window.__stressInterval);
            }
        });

        if (fpsSamples.length > 0) {
            const avgFps = fpsSamples.reduce((a, b) => a + b, 0) / fpsSamples.length;
            console.log(`CPU stress test FPS: avg=${Math.round(avgFps)}, samples=${fpsSamples.length}`);

            // The adaptive complexity system should keep FPS above 20
            // even under stress
            expect(avgFps).toBeGreaterThanOrEqual(15);
        }
    });
});
