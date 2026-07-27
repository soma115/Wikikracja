// Loguje się raz przez allauth login form i zapisuje storageState dla reszty testów.
const { test: setup, expect } = require('@playwright/test');
const path = require('path');

const STORAGE_STATE = path.join(__dirname, '.auth/user.json');

setup('login as dev user', async ({ page }) => {
    const email = process.env.E2E_EMAIL;
    const password = process.env.E2E_PASSWORD;
    if (!email || !password) {
        throw new Error('E2E_EMAIL i E2E_PASSWORD muszą być w .env.local (gitignored)');
    }

    await page.goto('/accounts/login/');
    await page.fill('input[name="login"]', email);
    await page.fill('input[name="password"]', password);

    await Promise.all([
        page.waitForURL(url => !url.pathname.startsWith('/accounts/login'), { timeout: 15000 }),
        page.click('form.login button[type="submit"]'),
    ]);
    // Poczekaj na sidebar — renderowany tylko dla zalogowanych ({% if user.is_authenticated %}).
    // networkidle odpada bo WebSockety nigdy nie milkną. Sidebar = pewny sygnał że sesja
    // z _auth_user_id jest zapisana i odpowiedź serwera ją potwierdziła.
    await page.waitForSelector('#sidebar', { timeout: 15000 });

    await page.context().storageState({ path: STORAGE_STATE });
});
