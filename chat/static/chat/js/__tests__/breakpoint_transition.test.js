/**
 * @jest-environment jsdom
 *
 * Test przejścia breakpointu mobile <-> desktop (plan 5.6).
 * Symuluje zmianę mobileMedia.matches tak, jak robi to listener
 * mobileMedia.addEventListener('change', renderChatView) w DOMContentLoaded:
 * po każdej zmianie matches wywołujemy renderChatView() i sprawdzamy,
 * że klasy widoku są w pełni wyprowadzone ze stanu — brak osieroconych
 * klas, brak panelu o zerowej geometrii logicznej, preferencja desktopowa
 * nie wycieka na mobile.
 *
 * Kontrakt z chat.js (synchronizowac przy zmianie — funkcje kopiowane 1:1).
 */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// Mutable stub — test "przestawia" matches i woła renderChatView, tak jak
// robi to listener 'change' na mobileMedia.
const mobileMedia = { matches: false };

let CurrentRoomId = null;
const ViewState = {
    panel: 'list',
    requestedRoomId: null,
    joinStatus: 'idle',
    connectionStatus: 'connecting',
};

// Stub DomApi — renderChatView woła tylko getRoomLinkDiv.
const DOM_API = {
    getRoomLinkDiv: (room_id) => $(`.room-link[data-room-id="${room_id}"]`),
};

// ── wierna kopia z chat.js (synchronizowac przy zmianie!) ──────────────────
function renderChatView() {
    const chatRooms = $('.chat-rooms');
    if (!chatRooms) return;
    chatRooms.classList.toggle('room-active', CurrentRoomId != null);
    chatRooms.classList.toggle('room-list-showing', mobileMedia.matches && ViewState.panel === 'list');
    // aria-current na linku aktywnego pokoju.
    $$('.room-link[aria-current]').forEach(el => el.removeAttribute('aria-current'));
    if (CurrentRoomId != null) {
        DOM_API?.getRoomLinkDiv(CurrentRoomId)?.setAttribute('aria-current', 'true');
    }
}

function buildChatDom() {
    document.body.innerHTML = `
      <div class="chat-rooms">
        <div class="chat-root-messages"></div>
        <div class="room-list-col">
          <div class="room-list" id="room-list">
            <div class="room-list-groups">
              <div class="room-link" data-room-id="1" tabindex="-1"></div>
              <div class="room-link" data-room-id="2" tabindex="-1"></div>
            </div>
          </div>
        </div>
      </div>`;
}

const chatRooms = () => $('.chat-rooms');

/** Symuluje event 'change' na matchMedia — tak jak produkcyjny listener. */
function setMobile(matches) {
    mobileMedia.matches = matches;
    renderChatView();
}

beforeEach(() => {
    buildChatDom();
    mobileMedia.matches = false;
    CurrentRoomId = null;
    ViewState.panel = 'list';
});

describe('renderChatView — wyprowadzanie klas ze stanu', () => {
    test('mobile + panel=list → room-list-showing; desktop → nigdy', () => {
        ViewState.panel = 'list';
        setMobile(true);
        expect(chatRooms().classList.contains('room-list-showing')).toBe(true);

        setMobile(false);
        expect(chatRooms().classList.contains('room-list-showing')).toBe(false);
    });

    test('room-active podąża za CurrentRoomId niezależnie od breakpointu', () => {
        CurrentRoomId = 1;
        setMobile(false);
        expect(chatRooms().classList.contains('room-active')).toBe(true);
        setMobile(true);
        expect(chatRooms().classList.contains('room-active')).toBe(true);
    });

    test('przejście desktop → mobile → desktop nie zostawia osieroconych klas', () => {
        // start: mobile, użytkownik w pokoju
        CurrentRoomId = 1;
        ViewState.panel = 'room';
        setMobile(true);
        expect(chatRooms().className.trim()).toBe('chat-rooms room-active');

        // obrót/resize na desktop — room-list-showing nie może zostać
        setMobile(false);
        expect(chatRooms().classList.contains('room-list-showing')).toBe(false);
        expect(chatRooms().classList.contains('room-active')).toBe(true);

        // powrót na mobile — panel z pamięci stanu, nie z "co było na ekranie"
        setMobile(true);
        expect(chatRooms().classList.contains('room-list-showing')).toBe(false);
    });

    test('przejście breakpointu przy panelu listy przywraca room-list-showing na mobile', () => {
        ViewState.panel = 'list';
        setMobile(true);
        expect(chatRooms().classList.contains('room-list-showing')).toBe(true);
        setMobile(false);
        expect(chatRooms().classList.contains('room-list-showing')).toBe(false);
        setMobile(true);
        expect(chatRooms().classList.contains('room-list-showing')).toBe(true);
    });

    test('aria-current śledzi CurrentRoomId po przejściach breakpointu', () => {
        CurrentRoomId = 2;
        ViewState.panel = 'room';
        setMobile(false);
        expect($('.room-link[data-room-id="2"]').getAttribute('aria-current')).toBe('true');
        expect($('.room-link[data-room-id="1"]').getAttribute('aria-current')).toBeNull();

        setMobile(true);
        expect($('.room-link[data-room-id="2"]').getAttribute('aria-current')).toBe('true');

        // wyjście z pokoju czyści atrybut
        CurrentRoomId = null;
        ViewState.panel = 'list';
        renderChatView();
        expect(document.querySelectorAll('.room-link[aria-current]').length).toBe(0);
    });
});
