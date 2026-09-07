// Bug fix verify: na mobile klik w już aktywny pokój z rozwiniętej listy zwija listę.
// Po przebudowie: nawigacja lista <-> pokój idzie przez URL (router w chat.js),
// a widoczność paneli wynika ze stanu (room-active / room-list-showing).
const { test, expect } = require('@playwright/test');

async function setupChatPage(page) {
    // ?view=rooms → parseChatLocation zwraca view 'rooms' (lista, brak auto-joina).
    // Bez tego czyste /chat/ auto-joinuje pierwszy publiczny pokój → na mobile
    // od razu room-active + lista schowana.
    await page.goto('/chat/?view=rooms');
    await page.waitForSelector('.room-link', { timeout: 10000 });
    // Rozwiń wszystkie kategorie (na mobile często collapsed). evaluate() klika synchronicznie
    // wszystkie naraz — bez tego per-locator iteracja wpada w race condition gdy lista się przeklika.
    await page.evaluate(() => {
        document.querySelectorAll('.nav-cat-btn[aria-expanded="false"]').forEach(b => b.click());
    });
    // Buffer na animację collapse — bez tego room-link bywa "not stable" przy kliku.
    await page.waitForTimeout(400);
    // Pierwszy room-link bez visible filter — locator musi pozostać valid PO wejściu w pokój
    // (na mobile room-active hideuje .room-list-col, :visible przestałby matchować ten sam element).
    const roomLink = page.locator('.room-link').first();
    await expect(roomLink).toBeVisible();
    return roomLink;
}

// Asercje geometrii — sama obecność klas nie wystarcza; bug "pusty mobile"
// to był panel o zerowej wysokości mimo poprawnych klas.
async function expectPositiveBox(locator, label) {
    const box = await locator.boundingBox();
    expect(box, `${label}: element nie jest widoczny w layoucie`).not.toBeNull();
    expect(box.width, `${label}: width > 0`).toBeGreaterThan(0);
    expect(box.height, `${label}: height > 0`).toBeGreaterThan(0);
}

test.describe('chat mobile — room list collapse on tap of active room', () => {
    test('mobile: klik aktywnego pokoju z rozwiniętej listy zdejmuje room-list-showing', async ({ page }, testInfo) => {
        // Tylko mobile-chromium. Na desktop project ten test się nie odpala
        // (feature jest mobile-only przez guard mobileMedia.matches).
        test.skip(testInfo.project.name !== 'mobile-chromium', 'Mobile-only test');
        const roomLink = await setupChatPage(page);
        const chatRooms = page.locator('.chat-rooms');

        // Geometria startowa: lista ma realne wymiary, nie sam toolbar.
        await expectPositiveBox(page.locator('.room-list'), 'room-list po ?view=rooms');

        // 1. Klik w pokój — wchodzi do niego (mobile: lista znika, wiadomości fullscreen)
        await roomLink.click();
        await expect(chatRooms).toHaveClass(/room-active/, { timeout: 10000 });
        await expect(chatRooms).not.toHaveClass(/room-list-showing/);
        await expect(roomLink).toHaveClass(/joined/);
        // Router zapisał hash pokoju w URL.
        await expect(page).toHaveURL(/#room_id=\d+/);

        // 2. Klik w >> (toggle-room-list-btn) — pokazuje listę nad aktywnym pokojem
        await page.locator('#toggle-room-list-btn').click();
        await expect(chatRooms).toHaveClass(/room-list-showing/);
        await expect(chatRooms).toHaveClass(/room-active/);

        // 3. KLUCZOWE: klik w ten sam pokój → lista ma się zwinąć, room-active zostaje
        await roomLink.click();
        await expect(chatRooms).not.toHaveClass(/room-list-showing/);
        await expect(chatRooms).toHaveClass(/room-active/);
    });

    test('mobile: Wstecz z pokoju wraca do listy pokoi', async ({ page }, testInfo) => {
        test.skip(testInfo.project.name !== 'mobile-chromium', 'Mobile-only test');
        const roomLink = await setupChatPage(page);
        const chatRooms = page.locator('.chat-rooms');

        await roomLink.click();
        await expect(chatRooms).toHaveClass(/room-active/, { timeout: 10000 });
        await expect(page).toHaveURL(/#room_id=\d+/);

        // Wstecz → wpis /chat/?view=rooms → lista (pokój zostaje dołączony w tle).
        await page.goBack();
        await expect(chatRooms).toHaveClass(/room-list-showing/);
        await expect(chatRooms).toHaveClass(/room-active/);
        await expect(page).not.toHaveURL(/#room_id=/);

        // Naprzód → z powrotem w pokoju.
        await page.goForward();
        await expect(page).toHaveURL(/#room_id=\d+/);
        await expect(chatRooms).not.toHaveClass(/room-list-showing/);
    });

    test('mobile: refresh na ?view=rooms reprodukuje listę (URL jest źródłem prawdy)', async ({ page }, testInfo) => {
        test.skip(testInfo.project.name !== 'mobile-chromium', 'Mobile-only test');
        await setupChatPage(page);
        const chatRooms = page.locator('.chat-rooms');
        // ?view=rooms NIE jest kasowany z URL — refresh ma dać ten sam widok.
        await expect(page).toHaveURL(/view=rooms/);
        await page.reload();
        await page.waitForSelector('.room-link', { timeout: 10000 });
        await expectPositiveBox(page.locator('.room-list'), 'room-list po reload');
        await expect(chatRooms).not.toHaveClass(/room-active/);
    });
});

test.describe('chat desktop — guard: aktywny pokój nie zdejmuje room-list-showing', () => {
    test.use({ viewport: { width: 1280, height: 800 } });

    test('desktop: klik aktywnego pokoju nie usuwa room-list-showing (gdyby była)', async ({ page }, testInfo) => {
        // Tylko desktop-chromium. Mobile project ma device descriptor Pixel 5 (mobile UA + touch);
        // sam override viewportu nie zmienia device i daje hybrydę myląco zieloną.
        test.skip(testInfo.project.name !== 'desktop-chromium', 'Desktop-only test');
        const roomLink = await setupChatPage(page);
        const chatRooms = page.locator('.chat-rooms');

        // Desktop: oba panele mają realną geometrię (master-detail).
        await expectPositiveBox(page.locator('.room-list'), 'room-list desktop');
        await expectPositiveBox(page.locator('.chat-root-messages'), 'chat-root-messages desktop');

        // Wejdź do pokoju i POCZEKAJ na pełen async flow (websocket join → room-active)
        await roomLink.click();
        await expect(roomLink).toHaveClass(/joined/, { timeout: 10000 });
        await expect(chatRooms).toHaveClass(/room-active/);

        // Sztucznie dodaj room-list-showing (symulacja stanu, który mógłby przyjść
        // z widoku listy) — na desktopie klasa nie ma efektu wizualnego.
        await chatRooms.evaluate(el => el.classList.add('room-list-showing'));
        await expect(chatRooms).toHaveClass(/room-list-showing/);

        // Klik w aktywny pokój — NA DESKTOPIE nic się nie dzieje (lista zostaje).
        // Uwaga: MutationObserver/renderChatView może zdjąć obce klasy przy kolejnym
        // renderze — asercja dotyczy tylko braku natychmiastowego side-effectu kliknięcia.
        await roomLink.click();
        await expect(chatRooms).toHaveClass(/room-list-showing/);
    });
});
