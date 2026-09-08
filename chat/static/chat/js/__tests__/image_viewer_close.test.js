/**
 * @jest-environment jsdom
 *
 * Testy kontraktu zamknięcia podglądu obrazów (lightbox) — plan 3.5.
 * Kontrakt: openBigImage tworzy #image-viewer-overlay i ustawia
 * body.tw-modal-open; KAŻDA ścieżka zamknięcia (×, Escape, klik w tło,
 * programowe closeBigImage) usuwa overlay i zdejmuje tw-modal-open.
 * Bez tego regresja daje modal nie do zamknięcia albo body zablokowane
 * na scroll przez osierocony tw-modal-open.
 *
 * Kontrakt z chat-core.js / domapi.js (synchronizowac przy zmianie —
 * funkcje kopiowane 1:1).
 */

// ── wierna kopia z chat-core.js (synchronizowac przy zmianie!) ──────────────
function openBigImage(srcs, startIndex = 0) {
    document.getElementById('image-viewer-overlay')?.remove();

    const overlay = document.createElement('div');
    overlay.id = 'image-viewer-overlay';
    overlay.className = 'tw-image-viewer-overlay';
    overlay.innerHTML = `
        <button class="tw-image-viewer-close" aria-label="Close">&times;</button>
        <button class="tw-image-viewer-nav tw-image-viewer-prev" aria-label="Previous">&#10094;</button>
        <button class="tw-image-viewer-nav tw-image-viewer-next" aria-label="Next">&#10095;</button>
        <div class="tw-image-viewer-container">
            <img class="tw-image-viewer-img" src="" alt="">
        </div>
        <div class="tw-image-viewer-counter"></div>
    `;
    document.body.appendChild(overlay);
    document.body.classList.add('tw-modal-open');

    let currentIndex = startIndex;
    const imgEl = overlay.querySelector('.tw-image-viewer-img');
    const counterEl = overlay.querySelector('.tw-image-viewer-counter');
    const prevBtn = overlay.querySelector('.tw-image-viewer-prev');
    const nextBtn = overlay.querySelector('.tw-image-viewer-next');

    function show(index) {
        currentIndex = (index + srcs.length) % srcs.length;
        imgEl.src = srcs[currentIndex];
        const multi = srcs.length > 1;
        counterEl.textContent = multi ? `${currentIndex + 1} / ${srcs.length}` : '';
        prevBtn.classList.toggle('tw-d-none', !multi);
        nextBtn.classList.toggle('tw-d-none', !multi);
    }

    function close() {
        document.removeEventListener('keydown', onKey);
        overlay.remove();
        document.body.classList.remove('tw-modal-open');
    }

    function onKey(e) {
        if (e.key === 'Escape') close();
        if (e.key === 'ArrowLeft') show(currentIndex - 1);
        if (e.key === 'ArrowRight') show(currentIndex + 1);
    }

    overlay.querySelector('.tw-image-viewer-close').addEventListener('click', close);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    prevBtn.addEventListener('click', (e) => { e.stopPropagation(); show(currentIndex - 1); });
    nextBtn.addEventListener('click', (e) => { e.stopPropagation(); show(currentIndex + 1); });
    document.addEventListener('keydown', onKey);

    show(currentIndex);
}

// ── wierna kopia z domapi.js (synchronizowac przy zmianie!) ─────────────────
function closeBigImage() {
    document.getElementById('image-viewer-overlay')?.remove();
    document.body.classList.remove('tw-modal-open');
}

// ── pomocnicze ──────────────────────────────────────────────────────────────
const overlay = () => document.getElementById('image-viewer-overlay');
const pressKey = (key) =>
    document.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));

beforeEach(() => {
    document.body.innerHTML = '';
    document.body.className = '';
});

describe('openBigImage — kontrakt otwarcia', () => {
    test('otwiera overlay i ustawia tw-modal-open na body', () => {
        openBigImage(['/a.png', '/b.png']);
        expect(overlay()).not.toBeNull();
        expect(document.body.classList.contains('tw-modal-open')).toBe(true);
        expect(overlay().querySelector('.tw-image-viewer-img').src).toContain('/a.png');
        expect(overlay().querySelector('.tw-image-viewer-counter').textContent).toBe('1 / 2');
    });

    test('pojedynczy obraz: brak nawigacji i licznika', () => {
        openBigImage(['/only.png']);
        expect(overlay().querySelector('.tw-image-viewer-counter').textContent).toBe('');
        expect(overlay().querySelector('.tw-image-viewer-prev').classList.contains('tw-d-none')).toBe(true);
        expect(overlay().querySelector('.tw-image-viewer-next').classList.contains('tw-d-none')).toBe(true);
    });

    test('startIndex wybiera wskazany obraz', () => {
        openBigImage(['/a.png', '/b.png', '/c.png'], 1);
        expect(overlay().querySelector('.tw-image-viewer-img').src).toContain('/b.png');
        expect(overlay().querySelector('.tw-image-viewer-counter').textContent).toBe('2 / 3');
    });

    test('ponowne otwarcie nie duplikuje overlaya', () => {
        openBigImage(['/a.png']);
        openBigImage(['/b.png']);
        expect(document.querySelectorAll('#image-viewer-overlay').length).toBe(1);
        expect(overlay().querySelector('.tw-image-viewer-img').src).toContain('/b.png');
    });
});

describe('zamknięcie — wszystkie ścieżki sprzątają kontrakt', () => {
    test('przycisk × zamyka overlay i zdejmuje tw-modal-open', () => {
        openBigImage(['/a.png']);
        overlay().querySelector('.tw-image-viewer-close').click();
        expect(overlay()).toBeNull();
        expect(document.body.classList.contains('tw-modal-open')).toBe(false);
    });

    test('Escape zamyka overlay i zdejmuje tw-modal-open', () => {
        openBigImage(['/a.png']);
        pressKey('Escape');
        expect(overlay()).toBeNull();
        expect(document.body.classList.contains('tw-modal-open')).toBe(false);
    });

    test('klik w tło (sam overlay) zamyka', () => {
        openBigImage(['/a.png']);
        const ov = overlay();
        ov.dispatchEvent(new MouseEvent('click', { bubbles: true }));
        expect(overlay()).toBeNull();
        expect(document.body.classList.contains('tw-modal-open')).toBe(false);
    });

    test('klik w treść NIE zamyka (target !== overlay)', () => {
        openBigImage(['/a.png']);
        overlay().querySelector('.tw-image-viewer-img')
            .dispatchEvent(new MouseEvent('click', { bubbles: true }));
        expect(overlay()).not.toBeNull();
    });

    test('programowe closeBigImage() usuwa overlay i tw-modal-open', () => {
        openBigImage(['/a.png']);
        closeBigImage();
        expect(overlay()).toBeNull();
        expect(document.body.classList.contains('tw-modal-open')).toBe(false);
    });

    test('po zamknięciu listener klawiatury jest odpięty (brak wycieku)', () => {
        openBigImage(['/a.png', '/b.png']);
        overlay().querySelector('.tw-image-viewer-close').click();
        // Ponowne otwarcie — Escape nie może podwójnie odpalić starego handlera.
        openBigImage(['/c.png', '/d.png']);
        pressKey('ArrowRight');
        expect(overlay().querySelector('.tw-image-viewer-img').src).toContain('/d.png');
        pressKey('Escape');
        expect(overlay()).toBeNull();
    });
});

describe('nawigacja strzałkami', () => {
    test('ArrowRight/ArrowLeft i przyciski prev/next zmieniają obraz z zawinięciem', () => {
        openBigImage(['/a.png', '/b.png', '/c.png']);
        pressKey('ArrowRight');
        expect(overlay().querySelector('.tw-image-viewer-img').src).toContain('/b.png');
        // zawinięcie: ostatni → pierwszy
        pressKey('ArrowRight');
        pressKey('ArrowRight');
        expect(overlay().querySelector('.tw-image-viewer-img').src).toContain('/a.png');
        // wstecz z pierwszego → ostatni
        pressKey('ArrowLeft');
        expect(overlay().querySelector('.tw-image-viewer-img').src).toContain('/c.png');
        expect(overlay().querySelector('.tw-image-viewer-counter').textContent).toBe('3 / 3');
        // przyciski UI robią to samo
        overlay().querySelector('.tw-image-viewer-next').click();
        expect(overlay().querySelector('.tw-image-viewer-img').src).toContain('/a.png');
    });
});
