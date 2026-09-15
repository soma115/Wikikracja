const { test, expect } = require('@playwright/test');

const referendumUrl = process.env.E2E_REFERENDUM_URL;

test.describe('SQLite production reliability smoke test', () => {
    test('logs in, opens the test referendum and casts one vote', async ({ page }, testInfo) => {
        test.skip(testInfo.project.name !== 'desktop-chromium', 'The fixture account must cast the vote only once');
        test.skip(!referendumUrl, 'E2E_REFERENDUM_URL must point to an open test referendum');

        await page.goto(referendumUrl);
        await expect(page.locator('form[data-vote-submit]')).toBeVisible({ timeout: 15000 });

        await page.locator('button[name="tak"]').click();
        const confirmation = page.locator('[data-tw-confirm-action]');
        await expect(confirmation).toBeVisible({ timeout: 5000 });
        await confirmation.click();

        await expect(page.locator('form[data-vote-submit]')).toHaveCount(0, { timeout: 15000 });
        await expect(page.locator('body')).toContainText(/already voted|już zagłosowali|zagłosowano/i);
    });
});
