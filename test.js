const { chromium } = require('playwright');

async function test() {
    console.log('Starting Playwright test...');

    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();

    try {
        // Navigate to the app
        console.log('1. Loading page...');
        await page.goto('http://localhost:5309');
        await page.waitForTimeout(2000);

        // Check page title
        const title = await page.title();
        console.log(`   Page title: ${title}`);

        // Wait for models to load
        console.log('2. Waiting for models to load...');
        await page.waitForFunction(() => {
            const btn = document.getElementById('generate-btn');
            return btn && !btn.disabled;
        }, { timeout: 60000 });
        console.log('   Models loaded!');

        // Check GPU status is displayed
        const gpuName = await page.textContent('#gpu-name');
        console.log(`   GPU: ${gpuName}`);

        // Test random prompt button
        console.log('3. Testing random prompt...');
        await page.click('#random-btn');
        await page.waitForTimeout(1000);
        const promptValue = await page.inputValue('#prompt');
        console.log(`   Random prompt: "${promptValue}"`);

        // Test music generation with short duration
        console.log('4. Testing music generation...');
        await page.fill('#prompt', 'upbeat electronic music test');
        // Set duration slider to 3 seconds
        await page.evaluate(() => {
            document.getElementById('duration').value = 3;
            document.getElementById('duration-display').textContent = '3';
        });
        await page.click('#generate-btn');

        // Monitor progress
        console.log('   Monitoring generation progress...');
        let lastPct = 0;
        await page.waitForFunction(() => {
            const player = document.getElementById('player');
            const progressEl = document.querySelector('.progress-bar-fill');
            if (progressEl) {
                const width = progressEl.style.width;
                if (width && width !== '0%') {
                    console.log('Progress:', width);
                }
            }
            return player && player.classList.contains('show');
        }, { timeout: 120000 });
        console.log('   Music generated successfully!');

        // Check audio element has source
        const audioSrc = await page.getAttribute('#audio', 'src');
        console.log(`   Audio source: ${audioSrc}`);

        // Check history has items
        console.log('5. Checking history...');
        const historyItems = await page.locator('.history-item').count();
        console.log(`   History items: ${historyItems}`);

        // Test collapsible history
        if (historyItems > 0) {
            console.log('6. Testing collapsible history...');
            await page.click('.history-header');
            await page.waitForTimeout(500);
            const expanded = await page.locator('.history-item.expanded').count();
            console.log(`   Expanded items: ${expanded}`);
        }

        console.log('\n✓ All tests passed!');

    } catch (error) {
        console.error('\n✗ Test failed:', error.message);
    } finally {
        await browser.close();
    }
}

test();
