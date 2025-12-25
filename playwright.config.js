const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
    testDir: './tests',
    timeout: 30000,
    expect: {
        timeout: 10000
    },
    reporter: [['list'], ['html', { open: 'never' }]],
    use: {
        baseURL: process.env.TEST_URL || 'http://localhost:5309',
        trace: 'on-first-retry',
        screenshot: 'only-on-failure',
    },
    projects: [
        {
            name: 'chromium',
            use: { browserName: 'chromium' },
        },
    ],
});
