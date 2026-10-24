// Regresja: po edycji wiadomości w treści pojawia się literalny tekst "… pokaż więcej".
// Przyczyna: setEditing pobierał innerHTML z .msg-text (czyli całą strukturę .expandable z
// dokleconym .expandable-hint "… pokaż więcej"), bo dataset.raw nie był ustawiany przy batch
// insert (historia/replace) — tylko w addMessage. Edytor dostawał HTML expandable, user wysyłał
// go z powrotem, backend zapisywał razem z tekstem hint'a.
//
// Fix: data-raw="<%=raw_message%>" jako atrybut template'u .msg-text — single source of truth
// dla każdej ścieżki renderu (addMessage, batch insert, replaceMessages, history scroll-back).
const { test, expect } = require('@playwright/test');
const path = require('path');

const imageFixture = path.join(__dirname, '..', 'home', 'static', 'home', 'images', 'icon-192.png');

async function enterFirstRoom(page) {
    await page.goto('/chat/?view=rooms');
    await page.waitForSelector('.tw-room-link', { timeout: 10000 });
    const publicCategory = page.locator('.tw-chat-cat-btn[data-cat-content="cat-public"]');
    if (await publicCategory.getAttribute('aria-expanded') !== 'true') await publicCategory.click();
    await page.waitForTimeout(400);
    const roomLink = page.locator('.tw-room-link').first();
    await expect(roomLink).toBeVisible();
    await roomLink.click();
    await expect(roomLink).toHaveClass(/tw-room-link--joined/, { timeout: 10000 });
    await page.waitForSelector('.tw-chat-messages', { timeout: 10000 });
}

async function sendMessage(page, text) {
    const input = page.locator('#message-input');
    await input.click();
    await input.fill(text);
    await page.locator('.tw-send-message').click();
    // Czekamy aż wiadomość trafi do DOM (own + treść) — wracamy z return tego elementu.
    const ownMessages = page.locator('.tw-chat-message.tw-chat-message--own .tw-msg-text', { hasText: text });
    await expect(ownMessages.last()).toBeVisible({ timeout: 10000 });

    const message = page.locator('.tw-chat-message.tw-chat-message--own', { has: page.locator('.tw-msg-text', { hasText: text }) }).last();
    await expect(message).not.toHaveAttribute('data-temp-id', { timeout: 10000 });
    return ownMessages.last();
}

async function editOwnMessage(page, originalText, appendedText) {
    // Klik edit na ostatniej wiadomości pasującej do originalText.
    const msgDiv = page.locator('.tw-chat-message.tw-chat-message--own', { has: page.locator('.tw-msg-text', { hasText: originalText }) }).last();
    await msgDiv.locator('.tw-edit-message').click();
    // Input jest contenteditable — typujemy na końcu (focus już przeniesiony przez setEditing).
    const input = page.locator('#message-input');
    await expect(input).toBeFocused();
    // Przesuwamy kursor na koniec i dopisujemy.
    await input.press('End');
    await input.pressSequentially(appendedText);
    await page.locator('.tw-send-message').click();
}

test.describe('chat — edycja wiadomości zachowuje treść i załączniki', () => {
    test.use({ viewport: { width: 1280, height: 800 } });

    test('desktop: edycja wiadomości wysłanej w tej sesji nie zostawia "pokaż więcej" w treści', async ({ page }, testInfo) => {
        test.skip(testInfo.project.name !== 'desktop-chromium', 'Desktop-only test');
        await enterFirstRoom(page);

        const stamp = Date.now();
        const original = `E2E Playwright: Krótka treść testowa ${stamp}`;
        const appended = ' edytowane';
        await sendMessage(page, original);
        await editOwnMessage(page, original, appended);

        // Po edycji: szukamy wiadomości po finalnej treści. Treść NIE może zawierać "pokaż więcej".
        const edited = page.locator('.tw-chat-message.tw-chat-message--own .tw-msg-text', { hasText: `${original}${appended}` }).last();
        await expect(edited).toBeVisible({ timeout: 10000 });
        const text = await edited.locator('.tw-expandable-body').innerText();
        expect(text).not.toContain('pokaż więcej');
        expect(text.trim()).toBe(`${original}${appended}`);
    });

    test('desktop: edycja wiadomości załadowanej z historii (po reload) nie zostawia "pokaż więcej"', async ({ page }, testInfo) => {
        test.skip(testInfo.project.name !== 'desktop-chromium', 'Desktop-only test');
        await enterFirstRoom(page);

        const stamp = Date.now();
        const original = `E2E Playwright: Wiadomość z historii ${stamp}`;
        const appended = ' edytowane-z-historii';
        await sendMessage(page, original);

        // Reload: po reentry wiadomość przychodzi z batch insert (historia), nie z addMessage.
        // To ścieżka która regress'owała — dataset.raw nie był ustawiany.
        await page.reload();
        await page.waitForSelector(`.tw-chat-message.tw-chat-message--own .tw-msg-text:has-text("${original}")`, { timeout: 10000 });

        await editOwnMessage(page, original, appended);

        const edited = page.locator('.tw-chat-message.tw-chat-message--own .tw-msg-text', { hasText: `${original}${appended}` }).last();
        await expect(edited).toBeVisible({ timeout: 10000 });
        const text = await edited.locator('.tw-expandable-body').innerText();
        expect(text).not.toContain('pokaż więcej');
        expect(text.trim()).toBe(`${original}${appended}`);
    });

    test('desktop: edycja wiadomosci dodaje i usuwa obrazy bez utraty tekstu', async ({ page }, testInfo) => {
        test.skip(testInfo.project.name !== 'desktop-chromium', 'Desktop-only test');
        await enterFirstRoom(page);

        const original = `E2E Playwright: edycja obrazu ${Date.now()}`;
        await sendMessage(page, original);
        const message = page.locator('.tw-chat-message.tw-chat-message--own')
            .filter({ has: page.locator('.tw-msg-text', { hasText: original }) })
            .last();

        await message.locator('.tw-edit-message').click();
        await page.locator('#file-input').setInputFiles(imageFixture);
        await expect(page.locator('.tw-preview-images .tw-new-attachment')).toHaveCount(1);
        await page.locator('.tw-send-message').click();
        await expect(message.locator('.tw-attached-image')).toHaveCount(1, { timeout: 10000 });
        await expect(message.locator('.tw-msg-text')).toContainText(original);

        await message.locator('.tw-edit-message').click();
        await page.locator('.tw-remove-existing-attachment').click();
        await page.locator('.tw-send-message').click();
        await expect(message.locator('.tw-attached-image')).toHaveCount(0, { timeout: 10000 });
        await expect(message.locator('.tw-msg-text')).toContainText(original);

        await message.locator('.tw-edit-message').click();
        await page.locator('#file-input').setInputFiles(imageFixture);
        await page.locator('.tw-send-message').click();
        await expect(message.locator('.tw-attached-image')).toHaveCount(1, { timeout: 10000 });

        await message.locator('.tw-edit-message').click();
        await page.locator('.tw-delete-images-preview').click();
        await page.locator('.tw-send-message').click();
        await expect(message.locator('.tw-attached-image')).toHaveCount(0, { timeout: 10000 });
        await expect(message.locator('.tw-msg-text')).toContainText(original);
    });
});
