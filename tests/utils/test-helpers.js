/**
 * Shared test utilities for Playwright tests
 */

/**
 * Disable CSS animations for stable element interactions
 */
async function disableAnimations(page) {
    await page.addStyleTag({
        content: `
            *, *::before, *::after {
                animation-duration: 0s !important;
                animation-delay: 0s !important;
                transition-duration: 0s !important;
                transition-delay: 0s !important;
            }
        `
    });
}

/**
 * Wait for library to fully load with items
 */
async function waitForLibraryLoad(page, timeout = 10000) {
    await page.click('.main-tab:has-text("Library")');
    await page.waitForTimeout(300);
    await page.waitForSelector('.library-item', { timeout });
}

/**
 * Expand a collapsed genre group by name
 */
async function expandGenreGroup(page, groupName) {
    const header = page.locator(`.genre-section-header:has-text("${groupName}")`);
    if (await header.isVisible()) {
        // Check if group is collapsed
        const group = header.locator('..').locator('..');
        const isCollapsed = await group.evaluate(el => el.classList.contains('collapsed'));
        if (isCollapsed) {
            await header.click();
            await page.waitForTimeout(300);
        }
    }
}

/**
 * Complete the feedback modal submission flow
 */
async function submitFeedbackModal(page) {
    const modal = page.locator('#feedback-modal');
    if (await modal.isVisible()) {
        const submitBtn = page.locator('#feedback-submit-btn');
        await submitBtn.click();
        await page.waitForTimeout(500);
    }
}

/**
 * Close feedback modal if open
 */
async function closeFeedbackModal(page) {
    const modal = page.locator('#feedback-modal');
    if (await modal.isVisible()) {
        await page.keyboard.press('Escape');
        await page.waitForTimeout(300);
    }
}

/**
 * Switch to a main tab reliably
 */
async function switchToTab(page, tabName) {
    await page.click(`.main-tab:has-text("${tabName}")`);
    await page.waitForTimeout(300);

    const contentId = `#content-${tabName.toLowerCase()}`;
    await page.waitForSelector(contentId, { state: 'visible', timeout: 5000 });
}

/**
 * Wait for toast message to appear
 */
async function waitForToast(page, text = null, timeout = 3000) {
    const toastSelector = text
        ? `.toast:has-text("${text}")`
        : '.toast';
    await page.waitForSelector(toastSelector, { timeout });
}

/**
 * Get vote state for a library item
 */
async function getLibraryItemVoteState(page, itemIndex = 0) {
    const item = page.locator('.library-item').nth(itemIndex);
    const upBtn = item.locator('button[title="Like this track"]');
    const downBtn = item.locator('button[title="Dislike this track"]');

    const isUpvoted = await upBtn.evaluate(el => el.classList.contains('voted'));
    const isDownvoted = await downBtn.evaluate(el => el.classList.contains('voted'));

    return { isUpvoted, isDownvoted };
}

module.exports = {
    disableAnimations,
    waitForLibraryLoad,
    expandGenreGroup,
    submitFeedbackModal,
    closeFeedbackModal,
    switchToTab,
    waitForToast,
    getLibraryItemVoteState
};
