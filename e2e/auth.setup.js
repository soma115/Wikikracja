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

    // Chat E2E potrzebuje co najmniej jednego pokoju dostępnego dla użytkownika.
    // Środowisko CI może być świeże i nie mieć danych demonstracyjnych, dlatego
    // utwórz pokój testowy tylko wtedy, gdy lista jest pusta.
    await page.goto('/chat/?view=rooms');
    if (await page.locator('.tw-room-link').count() === 0) {
        await page.goto('/chat/add_room/');
        await page.fill('input[name="title"]', `E2E Playwright Room ${Date.now()}`);
        await Promise.all([
            page.waitForURL(/\/chat\/\?view=rooms|\/chat\/#room_id=/, { timeout: 15000 }),
            page.click('form button[type="submit"]'),
        ]);
    }

    await page.context().storageState({ path: STORAGE_STATE });
});
