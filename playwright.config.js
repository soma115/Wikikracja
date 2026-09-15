// Minimalna konfiguracja Playwright — mobile + desktop viewport, baseURL na lokalnego Django.
// Ładuje .env.local (gitignored) z credentialami dedykowanego konta E2E:
// E2E_EMAIL, E2E_PASSWORD. Nigdy nie używaj konta admina, prywatnego ani dev usera.
//
// PREREQUISITES przed `npx playwright test`:
//   1. Redis up (docker compose) — chat consumers tego wymagają
//   2. Daphne/runserver na :8000 (`python manage.py runserver 0.0.0.0:8000`)
//   3. .env.local z danymi konta utworzonego wyłącznie do testów E2E (verified email)
const fs = require('fs');
const path = require('path');
const { defineConfig, devices } = require('@playwright/test');

// Prosty loader .env.local bez zewnętrznej zależności (dotenv).
try {
    const envFile = path.join(__dirname, '.env.local');
    fs.readFileSync(envFile, 'utf8').split('\n').forEach(line => {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) return;
        const eq = trimmed.indexOf('=');
        if (eq === -1) return;
        const key = trimmed.slice(0, eq).trim();
        const value = trimmed.slice(eq + 1).trim().replace(/^["']|["']$/g, '');
        if (key && !process.env[key]) process.env[key] = value;
    });
} catch (_) { /* .env.local opcjonalny */ }

const STORAGE_STATE = path.join(__dirname, 'e2e/.auth/user.json');

module.exports = defineConfig({
    testDir: './e2e',
    fullyParallel: false,
    workers: 1,
    reporter: [['list']],
    use: {
        baseURL: 'http://localhost:8000',
        trace: 'retain-on-failure',
        screenshot: 'only-on-failure',
    },
    projects: [
        // Setup project: loguje się raz, zapisuje storageState dla reszty.
        {
            name: 'setup',
            testMatch: /auth\.setup\.js/,
        },
        {
            name: 'mobile-chromium',
            use: { ...devices['Pixel 5'], storageState: STORAGE_STATE },
            dependencies: ['setup'],
            testIgnore: /auth\.setup\.js/,
        },
        {
            name: 'desktop-chromium',
            use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 }, storageState: STORAGE_STATE },
            dependencies: ['setup'],
            testIgnore: /auth\.setup\.js/,
        },
    ],
});
