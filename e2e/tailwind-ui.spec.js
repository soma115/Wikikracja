// Regression / coverage tests for Tailwind UI components across desktop and mobile.
// Relies on e2e/auth.setup.js for storageState.
const { test, expect } = require('@playwright/test');

const DESKTOP = { width: 1280, height: 800 };
const MOBILE = { width: 393, height: 851 }; // Pixel 5-ish

async function waitForLayout(page) {
    await page.waitForSelector('.tw-layout-wrapper', { timeout: 15000 });
}

async function dismissNotificationBanner(page) {
    await page.evaluate(() => {
        const btn = document.getElementById('dismiss-blocked-banner') || document.getElementById('dismiss-notifications-banner');
        if (btn) btn.click();
    });
}

test.describe('desktop', () => {
    test.use({ viewport: DESKTOP });

    test('dashboard renders and layout is visible', async ({ page }) => {
        await page.goto('/');
        await waitForLayout(page);

        await expect(page.locator('.tw-layout-wrapper')).toBeVisible();
        await expect(page.locator('#sidebar')).toBeVisible();
        await expect(page.locator('.tw-topbar')).toBeVisible();
        await expect(page.locator('.tw-dashboard-grid')).toBeVisible();
    });

    test('theme toggle switches data-theme', async ({ page }) => {
        await page.goto('/');
        await waitForLayout(page);
        await dismissNotificationBanner(page);

        const before = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
        expect(['dark', 'light']).toContain(before);

        await page.evaluate(() => document.getElementById('theme-toggle-btn').click());

        await page.waitForFunction(
            (initial) => document.documentElement.getAttribute('data-theme') !== initial,
            before,
            { timeout: 5000 }
        );
        const after = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
        expect(after).not.toBe(before);
    });

    test('table list renders project table markup', async ({ page }) => {
        await page.goto('/obywatele/');
        await waitForLayout(page);

        const table = page.locator('table');
        await expect(table).toBeVisible();
        await expect(table).toHaveClass(/tw-table|table/);
    });

    test('form page renders project form controls', async ({ page }) => {
        await page.goto('/glosowania/nowy/');
        await waitForLayout(page);

        const form = page.locator('form.post-form');
        await expect(form).toBeVisible();

        await expect(page.locator('#id_title')).toBeVisible();
        await expect(page.locator('form.post-form button[type="submit"]')).toHaveCount(1);
    });

    test('modal opens and closes with a11y attributes', async ({ page }) => {
        await page.goto('/obywatele/settings/');
        await waitForLayout(page);

        const modal = page.locator('#deletionModal');
        await expect(modal).toHaveAttribute('aria-hidden', 'true');

        await page.locator('[data-tw-target="#deletionModal"]').click();
        await expect(modal).toHaveClass(/tw-show/);
        await expect(modal).toBeVisible();
        await expect(modal).toHaveAttribute('aria-hidden', 'false');

        // Give the modal show transition time to set _isShown = true.
        await page.waitForTimeout(350);

        const closeBtn = page.locator('#deletionModal [data-tw-dismiss="modal"]').first();
        await closeBtn.click();
        await expect(modal).not.toHaveClass(/tw-show/);
        await expect(modal).toHaveAttribute('aria-hidden', 'true');
    });

    test('category filter dropdown has correct a11y attributes', async ({ page }) => {
        await page.goto('/tasks/');
        await waitForLayout(page);

        const toggle = page.locator('#catFilterBtn');
        const panel = page.locator('#catFilterPanel');

        await expect(toggle).toHaveAttribute('aria-expanded', 'false');
        await expect(panel).toHaveAttribute('hidden');

        await toggle.click();
        await expect(toggle).toHaveAttribute('aria-expanded', 'true');
        await expect(panel).not.toHaveAttribute('hidden');

        // Clicking outside the filter should close it.
        await page.mouse.click(10, 10);
        await expect(toggle).toHaveAttribute('aria-expanded', 'false');
        await expect(panel).toHaveAttribute('hidden');
    });
});

test.describe('mobile', () => {
    test.use({ viewport: MOBILE });

    test('sidebar can be toggled', async ({ page }) => {
        await page.goto('/');
        await waitForLayout(page);

        const sidebar = page.locator('#sidebar');
        const toggle = page.locator('#sidebar-toggle');

        const wasOpen = await sidebar.evaluate((el) => el.classList.contains('sidebar-open'));

        await toggle.click();
        await page.waitForTimeout(200);
        const isOpen = await sidebar.evaluate((el) => el.classList.contains('sidebar-open'));
        expect(isOpen).toBe(!wasOpen);

        await page.locator('#sidebar-close-btn, #sidebar-toggle').first().click();
        await page.waitForTimeout(200);
        const isOpenAgain = await sidebar.evaluate((el) => el.classList.contains('sidebar-open'));
        expect(isOpenAgain).toBe(wasOpen);
    });

    test('dashboard renders in mobile viewport', async ({ page }) => {
        await page.goto('/');
        await waitForLayout(page);

        await expect(page.locator('.tw-main-content')).toBeVisible();
        await expect(page.locator('.tw-topbar')).toBeVisible();
    });
});
