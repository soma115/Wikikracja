/**
 * @jest-environment jsdom
 *
 * Testy wskaznika nieprzeczytanych wiadomosci na faviconie (utility.js).
 * Kontrakt: badge zielonej kropki ma zachowac favicon wyrenderowany przez serwer
 * (moze to byc wlasny brand mark z /media/site_branding/derived/), a po
 * przeczytaniu wszystkich pokoi removeNotification() przywraca ORYGINALNY href —
 * nigdy domyslna ikone projektu ani pusty href (favicon przegladarki).
 *
 * Sciezka canvas (renderUnreadIcon) nie jest pokryta — jsdom nie ma 2d context,
 * wiec funkcja deterministycznie spada na FALLBACK_UNREAD_ICON.
 *
 * Kontrakt z utility.js (synchronizowac przy zmianie — funkcje kopiowane 1:1).
 */

// ── wierna kopia z utility.js (synchronizowac przy zmianie!) ──────────────────
let originalIconHref = null;
let unreadIconHref = null;

const UNREAD_BADGE_COLOR = '#7cb342';
const FALLBACK_ICON = '/static/chat/images/notification-off.ico';
const FALLBACK_UNREAD_ICON = '/static/chat/images/notification-on.ico';

function getIconLink() {
    let link = document.querySelector("link[rel~='icon']");
    if (!link) {
        link = document.createElement('link');
        link.rel = 'icon';
        document.getElementsByTagName('head')[0].appendChild(link);
    }
    return link;
}

function captureOriginalIcon() {
    if (originalIconHref === null) {
        originalIconHref = getIconLink().href || FALLBACK_ICON;
    }
}

function removeNotification() {
    captureOriginalIcon();
    changeIcon(originalIconHref);
}

function changeIcon(resource) {
    const link = getIconLink();
    captureOriginalIcon();
    link.href = resource;
}

async function renderUnreadIcon(href) {
    try {
        const img = new Image();
        img.src = href;
        await img.decode();
        const size = 64;
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = size;
        const ctx = canvas.getContext('2d');
        const scale = Math.min(size / img.naturalWidth, size / img.naturalHeight);
        const w = img.naturalWidth * scale;
        const h = img.naturalHeight * scale;
        ctx.drawImage(img, (size - w) / 2, (size - h) / 2, w, h);
        const r = Math.round(size * 0.15);
        ctx.beginPath();
        ctx.arc(size - r, r, r, 0, Math.PI * 2);
        ctx.fillStyle = UNREAD_BADGE_COLOR;
        ctx.fill();
        return canvas.toDataURL('image/png');
    } catch (e) {
        return null;
    }
}

async function showUnreadIcon() {
    captureOriginalIcon();
    if (unreadIconHref === null) {
        unreadIconHref = (await renderUnreadIcon(originalIconHref)) || FALLBACK_UNREAD_ICON;
    }
    changeIcon(unreadIconHref);
}
// ── koniec kopii ──────────────────────────────────────────────────────────────

// jsdom absolutyzuje href wzgledem document.URL (http://localhost/)
const ABS = (p) => new URL(p, document.URL).href;
const BRANDED = '/media/site_branding/derived/favicon.ico?v=123';

function setServerFavicon(href) {
    document.head.querySelectorAll("link[rel~='icon']").forEach(l => l.remove());
    const link = document.createElement('link');
    link.rel = 'icon';
    link.href = href;
    document.head.appendChild(link);
}

beforeEach(() => {
    originalIconHref = null;
    unreadIconHref = null;
    document.head.querySelectorAll("link[rel~='icon']").forEach(l => l.remove());
});

afterEach(() => {
    document.head.querySelectorAll("link[rel~='icon']").forEach(l => l.remove());
});

describe('favicon unread — przywracanie oryginalnego href', () => {

    test('removeNotification przywraca favicon brand marku (nie domyslna ikone)', async () => {
        setServerFavicon(BRANDED);
        await showUnreadIcon();
        removeNotification();
        expect(getIconLink().href).toBe(ABS(BRANDED));
    });

    test('showUnreadIcon NIE nadpisuje faviconu statyczna domyslna ikona projektu', async () => {
        setServerFavicon(BRANDED);
        await showUnreadIcon();
        // W jsdom canvas render pada -> fallback; w przegladarce to data: URL z
        // narysowanym brandem. W obu przypadkach oryginal musi zostac zapamietany.
        expect(getIconLink().href).toBe(ABS(FALLBACK_UNREAD_ICON));
        removeNotification();
        expect(getIconLink().href).toBe(ABS(BRANDED));
    });

    test('oryginalny href jest lapany tylko raz — kolejne swapy go nie psuja', async () => {
        setServerFavicon(BRANDED);
        await showUnreadIcon();
        await showUnreadIcon();
        removeNotification();
        expect(getIconLink().href).toBe(ABS(BRANDED));
    });
});

describe('favicon unread — brak linku w head', () => {

    test('removeNotification nie ustawia pustego href (favicon przegladarki)', () => {
        // Regresja: changeIcon na swiezo utworzonym linku lapal href === '' i
        // restore ustawial pusty href -> przegladarka pokazywala swoj default.
        removeNotification();
        expect(getIconLink().href).toBe(ABS(FALLBACK_ICON));
    });
});
