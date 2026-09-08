/**
 * @jest-environment jsdom
 *
 * Testy showUnreadEmptyState — empty-state "brak nieprzeczytanych" w lewej kolumnie.
 * Pokrywaja zachowanie DOM, ktorego nie da sie wyciagnac do czystej funkcji (closure
 * DOMContentLoaded), a ktore jest podatne na regresje:
 *   - inline-przycisk istnieje jako realny <button> (a nie gola, nieklikalna ikona),
 *   - klik DELEGUJE do #unread-filter-btn — nie duplikuje logiki filtra,
 *   - aria-label opisuje AKCJE przycisku (zdejmuje filtr), wiec uzywa przetlumaczonego stringa,
 *   - tlumaczenie bez placeholdera {icon} NIE wstawia literalnego "undefined" (guard after = '').
 *
 * Kontrakt z chat.js (synchronizowac przy zmianie — funkcja kopiowana 1:1).
 */

// ── stub i18n: _() zwraca tlumaczenie albo sam klucz (jak realny _ w chat.js) ──
let translations = {};
const _ = (key) => translations[key] ?? key;

// ── wierna kopia z chat.js (synchronizowac przy zmianie!) ─────────────────────
function showUnreadEmptyState() {
    const roomList = document.querySelector('#room-list');
    if (!roomList || document.getElementById('chat-no-unread-empty-state')) return;

    const div = document.createElement('div');
    div.id = 'chat-no-unread-empty-state';
    div.className = 'tw-chat-no-unread-empty-state';

    const iconBig = document.createElement('i');
    iconBig.className = 'fas fa-envelope-open tw-chat-no-unread-icon';
    iconBig.setAttribute('aria-hidden', 'true');

    const title = document.createElement('p');
    title.className = 'tw-chat-no-unread-title';
    title.textContent = _("No unread messages");

    const hint = document.createElement('p');
    hint.className = 'tw-chat-no-unread-hint';
    const [before, after = ''] = _("Tap {icon} above the list to disable the unread filter").split('{icon}');
    hint.appendChild(document.createTextNode(before));
    const inlineBtn = document.createElement('button');
    inlineBtn.type = 'button';
    inlineBtn.className = 'tw-chat-no-unread-inline-btn';
    inlineBtn.setAttribute('aria-label', _("Disable the unread filter"));
    const inlineIcon = document.createElement('i');
    inlineIcon.className = 'fas fa-eye-slash';
    inlineIcon.setAttribute('aria-hidden', 'true');
    inlineBtn.appendChild(inlineIcon);
    inlineBtn.addEventListener('click', () => {
        document.getElementById('unread-filter-btn')?.click();
    });
    hint.appendChild(inlineBtn);
    hint.appendChild(document.createTextNode(after));

    div.append(iconBig, title, hint);
    roomList.appendChild(div);
}

// W chat.js #room-list jest zawsze obecny; #unread-filter-btn to przycisk w pasku,
// do ktorego delegujemy klik.
function setupDom() {
    document.body.innerHTML =
        '<button id="unread-filter-btn"></button><div id="room-list"></div>';
}

beforeEach(() => {
    translations = {};
    setupDom();
});

afterEach(() => {
    document.body.innerHTML = '';
});

// ── Inline przycisk: istnieje, jest dostepny, deleguje ────────────────────────

describe('showUnreadEmptyState — inline przycisk', () => {

    test('renderuje realny <button> z ukryta dla AT ikona (nie gola ikone)', () => {
        showUnreadEmptyState();
        const btn = document.querySelector('.tw-chat-no-unread-inline-btn');
        expect(btn).not.toBeNull();
        expect(btn.tagName).toBe('BUTTON');

        const icon = btn.querySelector('i.fa-eye-slash');
        expect(icon).not.toBeNull();
        expect(icon.getAttribute('aria-hidden')).toBe('true');
    });

    test('klik inline-buttona DELEGUJE do #unread-filter-btn (nie duplikuje logiki)', () => {
        const spy = jest.fn();
        document.getElementById('unread-filter-btn').addEventListener('click', spy);

        showUnreadEmptyState();
        document.querySelector('.tw-chat-no-unread-inline-btn').click();

        expect(spy).toHaveBeenCalledTimes(1);
    });

    test('aria-label opisuje akcje przyciskiem przetlumaczonego stringa', () => {
        translations['Disable the unread filter'] = 'Wyłącz filtr nieprzeczytanych';
        showUnreadEmptyState();
        const btn = document.querySelector('.tw-chat-no-unread-inline-btn');
        expect(btn.getAttribute('aria-label')).toBe('Wyłącz filtr nieprzeczytanych');
    });
});

// ── Odpornosc na tlumaczenia (placeholder {icon}) ─────────────────────────────

describe('showUnreadEmptyState — odpornosc na tlumaczenia', () => {

    test('tlumaczenie BEZ {icon} nie wstawia literalnego "undefined"', () => {
        // Symulacja: translator zgubil placeholder. split() zwroci 1 element,
        // a bez defaultu after === undefined -> createTextNode("undefined").
        translations['Tap {icon} above the list to disable the unread filter'] =
            'Kliknij ikonę nad listą, aby wyłączyć filtr';
        showUnreadEmptyState();
        const hint = document.querySelector('.tw-chat-no-unread-hint');
        expect(hint.textContent).not.toContain('undefined');
        expect(hint.textContent).toContain('Kliknij ikonę nad listą, aby wyłączyć filtr');
    });

    test('tlumaczenie Z {icon} rozdziela tekst na przed/po przycisku', () => {
        showUnreadEmptyState(); // domyslny _() zwraca klucz z {icon}
        const hint = document.querySelector('.tw-chat-no-unread-hint');
        expect(hint.textContent).toContain('Tap ');
        expect(hint.textContent).toContain(' above the list to disable the unread filter');
        expect(hint.textContent).not.toContain('{icon}');
    });
});

// ── Guard idempotencji (pre-existing, lock na regresje) ───────────────────────

describe('showUnreadEmptyState — idempotencja', () => {

    test('drugie wywolanie nie tworzy duplikatu empty-state', () => {
        showUnreadEmptyState();
        showUnreadEmptyState();
        expect(document.querySelectorAll('#chat-no-unread-empty-state').length).toBe(1);
    });
});
