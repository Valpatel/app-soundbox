const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.TEST_URL || 'http://localhost:5309';

test.skip('inspect API page widgets', async ({ page }) => {
    // SKIPPED: API tab is hidden in production UI
    // The embeddable widget feature requires the API tab to be visible
    // TODO: Enable API tab or remove this test if feature is deprecated

    await page.goto(BASE_URL);
    await page.waitForSelector('#content-radio', { timeout: 10000 });

    // API tab must be visible
    const apiTab = page.locator('#tab-api, .main-tab:has-text("API")');
    await expect(apiTab.first()).toBeVisible({ timeout: 5000 });

    // Click on API tab
    await apiTab.first().click();
    await page.waitForTimeout(3000);

    // Inspect each widget demo
    const sizes = ['minimal', 'small', 'medium', 'large'];

    for (const size of sizes) {
        const container = await page.$(`#demo-${size}`);
        console.log(`\n${'='.repeat(60)}`);
        console.log(`=== ${size.toUpperCase()} WIDGET ===`);
        console.log(`${'='.repeat(60)}`);

        if (container) {
            // Get the inner HTML to see what's rendered
            const html = await container.innerHTML();
            console.log('\nHTML Structure:');
            console.log(html);

            // Get computed styles for key elements
            const widget = await container.$('.radio-widget');
            if (widget) {
                const box = await widget.boundingBox();
                console.log(`\nDimensions: ${box?.width}x${box?.height}`);

                // Check vote buttons layout
                const voteButtons = await widget.$('.rw-vote-buttons');
                if (voteButtons) {
                    const voteBox = await voteButtons.boundingBox();
                    const voteStyle = await voteButtons.evaluate(el => {
                        const style = window.getComputedStyle(el);
                        return {
                            display: style.display,
                            flexDirection: style.flexDirection,
                            gap: style.gap
                        };
                    });
                    console.log(`\nVote buttons: ${voteBox?.width}x${voteBox?.height}`);
                    console.log(`Vote layout: display=${voteStyle.display}, flex-direction=${voteStyle.flexDirection}, gap=${voteStyle.gap}`);
                }

                // Check branding
                const branding = await widget.$('.rw-branding');
                if (branding) {
                    const brandingHtml = await branding.innerHTML();
                    console.log(`\nBranding HTML: ${brandingHtml}`);
                }
            }
        } else {
            console.log('Container not found or empty');
        }
    }

    // Take a single page screenshot
    await page.screenshot({ path: 'tests/screenshots/api-page.png' });
    console.log('\nScreenshot saved to tests/screenshots/api-page.png');
});
