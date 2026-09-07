// Regresja komponentów tw-* w czacie (plan 3.9): dropdown, modal, lightbox
// podglądu obrazów, strzałka sortowania, empty state wyszukiwania.
// Asercje dotyczą realnej widoczności (klasy + geometria), nie tylko DOM.
const { test, expect } = require('@playwright/test');

async function setupChatPage(page) {
    // ?view=rooms → lista bez auto-joina (deterministyczny punkt startowy).
    await page.goto('/chat/?view=rooms');
    await page.waitForSelector('.room-link', { timeout: 10000 });
    await page.evaluate(() => {
        document.querySelectorAll('.nav-cat-btn[aria-expanded="false"]').forEach(b => b.click());
    });
    await page.waitForTimeout(400);
}

test.describe('chat — komponenty tw-* po migracji Tailwind', () => {
    test('dropdown akcji pokoju: otwiera i zamyka menu (tw-show + aria-expanded)', async ({ page }, testInfo) => {
        test.skip(testInfo.project.name !== 'desktop-chromium', 'Desktop-only test');
        await setupChatPage(page);

        // Menu jest scopowane do TEGO room-linka — .first() na całej stronie
        // łapałby menu toolbaru i udawał regresję.
        const roomLink = page.locator('.room-link').first();
        const chevron = roomLink.locator('.room-link__chevron[data-tw-toggle="dropdown"]');
        const menu = roomLink.locator('.tw-dropdown-menu');

        await chevron.click();
        await expect(chevron).toHaveAttribute('aria-expanded', 'true');
        await expect(menu).toBeVisible();

        // Klik poza menu zamyka dropdown (document-level delegated handler).
        await page.locator('body').click({ position: { x: 5, y: 5 } });
        await expect(chevron).toHaveAttribute('aria-expanded', 'false');
        await expect(menu).toBeHidden();
    });

    test('modal rename: TwModal.show → tw-show + body.tw-modal-open, dismiss zamyka', async ({ page }, testInfo) => {
        test.skip(testInfo.project.name !== 'desktop-chromium', 'Desktop-only test');
        await setupChatPage(page);

        // Renama istnieje tylko dla publicznych, niechronionych pokoi —
        // kontrakt testujemy przez TwModal API na istniejącym modalu w DOM.
        await page.evaluate(() => {
            const modal = document.getElementById('rename-room-modal');
            if (modal) window.TwModal.show(modal);
        });
        const modal = page.locator('#rename-room-modal');
        await expect(modal).toHaveClass(/tw-show/, { timeout: 5000 });
        await expect(page.locator('body')).toHaveClass(/tw-modal-open/);
        // hide() w tw-modal.js no-opuje w trakcie tranzycji otwarcia (300 ms) —
        // czekamy na shown.tw.modal zamiast arbitralnego timeoutu.
        await page.evaluate(() => new Promise(resolve =>
            document.getElementById('rename-room-modal')
                .addEventListener('shown.tw.modal', resolve, { once: true })));

        // Zamknięcie przez [data-tw-dismiss] — kontrakt z tw-modal.js.
        await modal.locator('[data-tw-dismiss="modal"]').first().click();
        await expect(modal).not.toHaveClass(/tw-show/, { timeout: 5000 });
        await expect(page.locator('body')).not.toHaveClass(/tw-modal-open/);
    });

    test('lightbox obrazów: klik w .attached-image otwiera overlay, Escape zamyka', async ({ page }, testInfo) => {
        test.skip(testInfo.project.name !== 'desktop-chromium', 'Desktop-only test');
        await setupChatPage(page);

        // Delegowany handler createImageClickHandler jest na document —
        // wstrzykujemy załącznik do DOM, jak po renderze wiadomości.
        await page.evaluate(() => {
            const box = document.querySelector('.chat-root-messages') || document.body;
            box.insertAdjacentHTML('beforeend',
                `<div class="attachment-image-container">
                   <img class="attached-image" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==">
                 </div>`);
        });
        // dispatchEvent omija actionability (1px img w scrollowalnym panelu);
        // bubbling click trafia w ten sam delegowany handler co realny klik.
        await page.locator('.attached-image').dispatchEvent('click');
        await expect(page.locator('#image-viewer-overlay')).toBeVisible();
        await expect(page.locator('body')).toHaveClass(/tw-modal-open/);

        await page.keyboard.press('Escape');
        await expect(page.locator('#image-viewer-overlay')).toHaveCount(0);
        await expect(page.locator('body')).not.toHaveClass(/tw-modal-open/);
    });

    test('sort wg aktywności: płaska lista → starsze → reset do kategorii', async ({ page }, testInfo) => {
        test.skip(testInfo.project.name !== 'desktop-chromium', 'Desktop-only test');
        await setupChatPage(page);

        const sortBtn = page.locator('#sort-activity-btn');
        const resetBtn = page.locator('#sort-reset-btn');

        // 1. Pierwszy klik → 'newest': płaska lista, grupy ukryte.
        await sortBtn.click();
        await expect(page.locator('#room-list-flat')).toBeVisible();
        await expect(page.locator('#room-list .room-list-groups')).toBeHidden();
        const order = await page.evaluate(() =>
            [...document.querySelectorAll('#room-list-flat .room-link[data-room-id]')]
                .map(l => parseInt(l.dataset.lastActivity || '0', 10)));
        const sortedDesc = [...order].sort((a, b) => b - a);
        expect(order).toEqual(sortedDesc);

        // 2. Drugi klik → 'oldest' (strzałka w górę).
        await sortBtn.click();
        await expect(page.locator('#sort-activity-btn .sort-dir-icon')).toHaveClass(/fa-arrow-up/);
        const orderAsc = await page.evaluate(() =>
            [...document.querySelectorAll('#room-list-flat .room-link[data-room-id]')]
                .map(l => parseInt(l.dataset.lastActivity || '0', 10)));
        expect(orderAsc).toEqual([...orderAsc].sort((a, b) => a - b));

        // 3. Reset → z powrotem drzewo kategorii.
        await resetBtn.click();
        await expect(page.locator('#room-list-flat')).toHaveCount(0);
        await expect(page.locator('#room-list .room-list-groups')).toBeVisible();
    });

    test('wyszukiwarka pokoi: brak wyników pokazuje jawny empty state', async ({ page }, testInfo) => {
        test.skip(testInfo.project.name !== 'desktop-chromium', 'Desktop-only test');
        await setupChatPage(page);

        await page.locator('#room-search').fill('zzz-nie-istnieje-taki-pokoj');
        const note = page.locator('#chat-no-search-results');
        await expect(note).toBeVisible();
        // drzewo kategorii schowane przez :has() — nie zostaje pusty szkielet
        await expect(page.locator('#room-list .room-list-groups')).toBeHidden();

        // Wyczyszczenie zapytania → notka znika, kategorie wracają.
        await page.locator('#room-search').fill('');
        await expect(note).toHaveCount(0);
        await expect(page.locator('#room-list .room-list-groups')).toBeVisible();
    });
});
