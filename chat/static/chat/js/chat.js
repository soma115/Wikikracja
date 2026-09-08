/**
 * @file
 * Main chat module for handling chat room interactions, message processing, and room management.
 * Coordinates between WebSocket API (WsApi) and DOM API (DomApi) to provide chat functionality.
 */

import { clearReplyTarget as coreClearReplyTarget, setReplyTarget as coreSetReplyTarget, voteButtonTitle } from './chat-core.js';
import DomApi from './domapi.js';
import { MessageHistory } from './templates.js';
import { $, $$, _, dateBannerHtml, formatDate, formatDateTime, Lock, mobileMedia, parseParms } from './utility.js';
import WsApi from './wsapi.js';

/**
 * Global WebSocket API instance
 * @type {WsApi}
 */
let WS_API;

/**
 * Global DOM API instance
 * @type {DomApi}
 */
let DOM_API;

/**
 * Lock for preventing concurrent room join/leave operations
 * @type {Lock}
 */
const RoomLock = new Lock();

/**
 * Currently active room ID
 * @type {number|null}
 */
let CurrentRoomId = null;

/**
 * Message ID being replied to
 * @type {number|null}
 */
let currentReplyId = null;
let currentReplyData = null;

const pendingTimeouts = new Map();
const PENDING_TIMEOUT_MS = 10000;

let isClearingInput = false;

/**
 * Message ID to scroll to when joining a room (e.g., from link)
 * @type {number|null}
 */
let ScrollToMessageId = null;

/**
 * Current sort/filter state for messages in the active room.
 * Always reset to defaults on room change — not persisted.
 */
let SortState = { sort_by: 'date', order: 'desc', popular_only: false };

function resetSortState() {
    SortState = { sort_by: 'date', order: 'desc', popular_only: false };
}

function saveDraft() {
    if (isClearingInput) return;
    const input = DOM_API?.getMessageInput();
    if (!input || !CurrentRoomId) return;
    const content = input.isContentEditable ? input.innerHTML : input.value;
    // Always save draft (even if empty) - it will be cleared when message is sent
    localStorage.setItem(`chat_draft_${CurrentRoomId}`, content);
}

function restoreDraft(roomId) {
    const input = DOM_API?.getMessageInput();
    if (!input) return;
    const draft = localStorage.getItem(`chat_draft_${roomId}`);
    if (!draft) return;
    // Don't restore empty drafts
    if (!draft.replace(/<[^>]*>/g, '').trim()) return;
    if (input.isContentEditable) {
        input.innerHTML = draft;
    } else {
        input.value = draft;
    }
    input.dispatchEvent(new InputEvent('input', { bubbles: true }));
}

function clearDraft(roomId) {
    localStorage.removeItem(`chat_draft_${roomId}`);
}

function bindSortToolbar() {
    const dateBtn = $('#chat-sort-date');
    const likesBtn = $('#chat-sort-likes');
    const popularBtn = $('#chat-filter-popular');
    if (!dateBtn || !likesBtn || !popularBtn) return;

    const applyActiveStyles = () => {
        dateBtn.classList.toggle('tw-active', SortState.sort_by === 'date');
        likesBtn.classList.toggle('tw-active', SortState.sort_by === 'likes');
        popularBtn.classList.toggle('tw-active', SortState.popular_only);

        const setArrow = (btn, active) => {
            const arrow = btn.querySelector('.tw-sort-arrow');
            if (!arrow) return;
            if (!active) { arrow.className = 'fas fa-arrow-down tw-sort-arrow tw-invisible'; return; }
            arrow.className = 'fas fa-arrow-' + (SortState.order === 'asc' ? 'up' : 'down') + ' tw-sort-arrow';
        };
        setArrow(dateBtn, SortState.sort_by === 'date');
        setArrow(likesBtn, SortState.sort_by === 'likes');
    };

    const refetch = () => {
        if (CurrentRoomId == null) return;
        WS_API.fetchMessages(CurrentRoomId, SortState.sort_by, SortState.order, SortState.popular_only);
    };

    const toggleSort = (key) => {
        if (SortState.sort_by === key) {
            SortState.order = SortState.order === 'desc' ? 'asc' : 'desc';
        } else {
            SortState.sort_by = key;
            SortState.order = 'desc';
        }
        applyActiveStyles();
        refetch();
    };

    dateBtn.addEventListener('click', () => toggleSort('date'));
    likesBtn.addEventListener('click', () => toggleSort('likes'));
    popularBtn.addEventListener('click', () => {
        SortState.popular_only = !SortState.popular_only;
        applyActiveStyles();
        refetch();
    });

    applyActiveStyles();
}

/**
 * Czysty parser lokalizacji czatu — zamienia URL na deklaratywną intencję widoku.
 * UWAGA: synchronizować z chat/static/chat/js/__tests__/chat_routing.test.js
 * (wzór jak draft.test.js — funkcja kopiowana 1:1 do testu).
 *
 * Semantyka:
 *   #room_id=X[&message_id=Y] → view 'room' — hash bije query params
 *   ?view=unread / ?unread=1  → view 'unread' — lista + filtr nieprzeczytanych
 *   ?view=rooms               → view 'rooms' — lista bez auto-joinu
 *   pozostałe (/chat/ itd.)   → view 'default' — przy starcie auto-joinuje pokój
 */
function parseChatLocation({ search = '', hash = '' } = {}) {
    const hashParams = parseParms(hash.startsWith('#') ? hash.slice(1) : hash);
    const roomId = hashParams.room_id ? parseInt(hashParams.room_id, 10) : null;
    const messageId = hashParams.message_id ? parseInt(hashParams.message_id, 10) : null;
    // Hash ma bezwzględny priorytet — użytkownik wprost prosi o konkretny pokój.
    if (roomId) return { view: 'room', roomId, messageId };

    const params = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
    const view = params.get('view');
    if (view === 'unread' || params.get('unread') === '1') {
        return { view: 'unread', roomId: null, messageId: null };
    }
    if (view === 'rooms') {
        return { view: 'rooms', roomId: null, messageId: null };
    }
    return { view: 'default', roomId: null, messageId: null };
}

/**
 * Deklaratywny stan widoku — jedyne źródło klas room-active / room-list-showing.
 * room-list-hidden (desktopowa preferencja zwinięcia listy) zarządza handlers.js.
 */
const ViewState = {
    /** 'list' | 'room' — panel widoczny na mobile; na desktopie widoczne są oba. */
    panel: 'list',
    /** Pokój wynikający z URL/kliknięcia — może się jeszcze nie dołączyć. */
    requestedRoomId: null,
    /** 'idle' | 'joining' | 'joined' | 'error' */
    joinStatus: 'idle',
    /** 'connecting' | 'online' | 'reconnecting' | 'offline' */
    connectionStatus: 'connecting',
};
/** Generacja żądania joinu — późna odpowiedź starszego żądania jest ignorowana. */
let JoinGeneration = 0;
/** Klucz ostatnio zastosowanej trasy — deduplikacja popstate + hashchange. */
let LastAppliedRouteKey = null;
/** Czy normalizacja stosu Wstecz dla deep-linka już się wykonała. */
let HistoryNormalized = false;

// Filtr nieprzeczytanych — stan modułowy (współdzielą go router i handlery).
let isUnreadFilterActive = false;
// Gdy user recznie kliknie filtr, jego decyzja jest ostateczna na te sesje strony —
// pozniejsze zastosowanie trasy NIE moze jej nadpisac intencja z URL.
let userToggledFilter = false;

/**
 * Decyduje, czy intencja filtra z URL ma zmienic aktualny stan filtra unread.
 * Reczny klik usera (userToggled) MA PIERWSZENSTWO nad URL — inaczej
 * asynchroniczne zastosowanie trasy cofaloby decyzje usera
 * ("filtr wraca po odkliknieciu"). Zwraca 'enable' | 'disable' | 'none'.
 * UWAGA: synchronizować z chat/static/chat/js/__tests__/unread_filter_override.test.js.
 */
function decideUnreadFilterOverride({ urlFilter, isActive, userToggled }) {
    // Reczna decyzja usera jest ostateczna — nie nadpisujemy jej intencja z URL.
    if (userToggled) return 'none';
    if (urlFilter === 'on' && !isActive) return 'enable';
    // Nie wyłączamy filtra dla urlFilter === 'off' — pozwalamy na przywracanie z localStorage
    return 'none';
}

function applyUnreadFilter() {
    // Filter rooms - show only unread using CSS class
    const allRoomLinks = $$('.tw-room-link[data-room-id]');
    allRoomLinks.forEach(roomLink => {
        // Add class to hide read rooms
        if (!roomLink.classList.contains('tw-room-link--not-seen')) {
            roomLink.classList.add('tw-room-link--filtered-out');
        } else {
            roomLink.classList.remove('tw-room-link--filtered-out');
        }
    });
    // Empty state w prawej kolumnie — zawsze gdy filtr daje 0 wynikow
    const unreadCount = $$('.tw-room-link.tw-room-link--not-seen[data-room-id]').length;
    if (unreadCount === 0) {
        showUnreadEmptyState();
    } else {
        hideUnreadEmptyState();
    }
}

function removeUnreadFilter() {
    const allRoomLinks = $$('.tw-room-link[data-room-id]');
    allRoomLinks.forEach(roomLink => {
        roomLink.classList.remove('tw-room-link--filtered-out');
    });
    hideUnreadEmptyState();
}

// Function to reapply unread filter when room seen status changes
function updateUnreadFilter() {
    if (isUnreadFilterActive) {
        applyUnreadFilter();
    }
}

function setUnreadFilter(active) {
    isUnreadFilterActive = active;
    document.getElementById('unread-filter-btn')?.classList.toggle('tw-active', active);
    if (active) {
        localStorage.setItem('chat-unread-filter', 'active');
        applyUnreadFilter();
    } else {
        localStorage.removeItem('chat-unread-filter');
        removeUnreadFilter();
    }
}

function applyUnreadUrlIntent(urlFilter) {
    const decision = decideUnreadFilterOverride({
        urlFilter,
        isActive: isUnreadFilterActive,
        userToggled: userToggledFilter,
    });
    if (decision === 'enable') setUnreadFilter(true);
    else if (decision === 'disable') setUnreadFilter(false);
}

/**
 * Jedno miejsce synchronizacji klas widoku z deklaratywnego stanu:
 *   room-active       — pokój jest dołączony (treść pokoju istnieje w DOM),
 *   room-list-showing — na mobile użytkownik jest na panelu listy.
 */
function renderChatView() {
    const chatRooms = $('.tw-chat-rooms');
    if (!chatRooms) return;
    chatRooms.classList.toggle('tw-room-active', CurrentRoomId != null);
    chatRooms.classList.toggle('tw-room-list-showing', mobileMedia.matches && ViewState.panel === 'list');
    // aria-current na linku aktywnego pokoju.
    $$('.tw-room-link[aria-current]').forEach(el => el.removeAttribute('aria-current'));
    if (CurrentRoomId != null) {
        DOM_API?.getRoomLinkDiv(CurrentRoomId)?.setAttribute('aria-current', 'true');
    }
}

function routeKey(route) {
    return `${route.view}|${route.roomId ?? ''}|${route.messageId ?? ''}`;
}

/**
 * Parsuje aktualny URL i stosuje trasę. Idempotentne: ta sama trasa
 * zastosowana drugi raz (np. popstate + hashchange przy jednym Wstecz)
 * jest pomijana.
 */
function syncRouteFromLocation({ initial = false } = {}) {
    const route = parseChatLocation({ search: location.search, hash: location.hash });
    const key = routeKey(route);
    if (!initial && key === LastAppliedRouteKey) return;
    LastAppliedRouteKey = key;
    if (initial && !HistoryNormalized) {
        HistoryNormalized = true;
        if (route.view === 'room') {
            // Deep-link: pod wpis pokoju wkładamy wpis listy, żeby pierwszy
            // Wstecz pokazał listę pokoi, a nie opuszczał stronę czatu.
            const roomUrl = location.pathname + location.search + location.hash;
            history.replaceState(null, '', location.pathname + location.search);
            history.pushState(null, '', roomUrl);
        }
    }
    applyChatRoute(route, { initial });
}

function applyChatRoute(route, { initial = false } = {}) {
    if (route.view === 'room') {
        ViewState.panel = 'room';
        ViewState.requestedRoomId = route.roomId;
        if (route.messageId) ScrollToMessageId = route.messageId;
        if (CurrentRoomId === route.roomId) {
            hideRoomPlaceholder();
            renderChatView(); // już dołączony — tylko pokaż panel pokoju
        } else {
            void onRoomTryJoin(route.roomId);
        }
        return;
    }

    // Widok listy: 'rooms' | 'unread' | 'default' poza startem (powrót Wstecz)
    ViewState.panel = 'list';
    ViewState.requestedRoomId = null;
    $('.tw-chat-rooms')?.classList.remove('tw-room-list-hidden');
    renderChatView();
    if (CurrentRoomId == null) showRoomPlaceholder();
    if (route.view === 'unread') applyUnreadUrlIntent('on');
    else if (route.view === 'rooms') applyUnreadUrlIntent('off');
    if (initial && route.view === 'default') {
        const roomId = pickInitialRoomId();
        // pushState nad wpisem /chat/ — Wstecz wraca do listy pokoi.
        if (roomId) navigateToRoom(roomId);
    }
}

/**
 * Wybiera pokój do auto-joinu przy czystym wejściu na /chat/:
 * ostatnio używany (jeśli dozwolony) → pierwszy publiczny → pierwszy dozwolony.
 */
function pickInitialRoomId() {
    const roomLinks = $$('.tw-room-link[data-room-id]');
    const allowedRoomIds = new Set([...roomLinks].map(el => parseInt(el.dataset.roomId)));
    if (localStorage.lastUsedRoomID) {
        const storedId = parseInt(localStorage.lastUsedRoomID);
        if (allowedRoomIds.has(storedId)) return storedId;
        delete localStorage.lastUsedRoomID;
    }
    const publicRooms = $$('.tw-room-link[data-room-id][data-room-type="public"]');
    return publicRooms.length ? parseInt(publicRooms[0].dataset.roomId) : ([...allowedRoomIds][0] ?? 0);
}

/** Nawigacja do pokoju — pushState + jawne zastosowanie trasy. */
export function navigateToRoom(roomId, messageId = null) {
    roomId = parseInt(roomId);
    if (!roomId) return;
    const hash = `#room_id=${roomId}` + (messageId ? `&message_id=${messageId}` : '');
    const target = location.pathname + location.search + hash;
    if (location.pathname + location.search + location.hash !== target) {
        history.pushState(null, '', target);
    }
    syncRouteFromLocation();
}

/** Nawigacja do listy pokoi — usuwa hash, zachowuje parametry ?view. */
export function navigateToRoomList() {
    const wasRoomPanel = mobileMedia.matches && ViewState.panel === 'room';
    if (location.hash) {
        history.pushState(null, '', location.pathname + location.search);
    }
    syncRouteFromLocation();
    // a11y: po powrocie z pokoju na listę przywracamy fokus linkowi aktywnego
    // pokoju — klawiatura/screen reader nie gubią kontekstu na pustym focuse.
    if (wasRoomPanel && CurrentRoomId != null) {
        DOM_API?.getRoomLinkDiv(CurrentRoomId)?.focus();
    }
}

/** Aktualnie dołączony pokój (joinedRoomId). */
export function getCurrentRoomId() {
    return CurrentRoomId;
}

// Placeholder "Wybierz pokoj" w lewej kolumnie — gdy nie ma joinowanego pokoju.
// Tekst budujemy przez textContent (defense-in-depth — gdyby kiedys w tlumaczeniu
// pojawil sie znak < lub &, to nie zlamie HTML'a).
function showRoomPlaceholder() {
    const messages = document.querySelector('.tw-chat-root-messages');
    if (!messages || document.getElementById('chat-no-room-placeholder')) return;
    const div = document.createElement('div');
    div.id = 'chat-no-room-placeholder';
    div.className = 'tw-chat-no-room-placeholder';

    const icon = document.createElement('i');
    icon.className = 'fas fa-comments tw-chat-no-room-icon';
    icon.setAttribute('aria-hidden', 'true');

    const text = document.createElement('p');
    text.className = 'tw-chat-no-room-text';
    text.textContent = _("Select a room from the list");

    div.append(icon, text);
    messages.appendChild(div);
}

function hideRoomPlaceholder() {
    document.getElementById('chat-no-room-placeholder')?.remove();
    document.getElementById('chat-join-error')?.remove();
}

/**
 * Jawny stan błędu joinu w kolumnie wiadomości z przyciskiem ponowienia —
 * błąd sieciowy nie może kończyć się pustym panelem ani samym toastem.
 * Teksty przez textContent (defense-in-depth, patrz showRoomPlaceholder).
 */
function showJoinError(roomId) {
    const messages = document.querySelector('.tw-chat-root-messages');
    if (!messages || document.getElementById('chat-join-error')) return;
    hideRoomPlaceholder();

    const div = document.createElement('div');
    div.id = 'chat-join-error';
    div.className = 'tw-chat-join-error';

    const icon = document.createElement('i');
    icon.className = 'fas fa-plug-circle-xmark tw-chat-no-room-icon';
    icon.setAttribute('aria-hidden', 'true');

    const text = document.createElement('p');
    text.className = 'tw-chat-no-room-text';
    text.textContent = _('Could not join the room.');

    const retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'tw-btn tw-btn-secondary tw-chat-join-retry';
    retry.innerHTML = '<i class="fas fa-rotate-right fa-fw" aria-hidden="true"></i>';
    retry.append(' ' + _('Try again'));
    retry.addEventListener('click', () => {
        div.remove();
        void onRoomTryJoin(roomId);
    });

    div.append(icon, text, retry);
    messages.appendChild(div);
}

// Empty state w prawej kolumnie — gdy filtr unread aktywny ale brak nieprzeczytanych.
// Tekst budujemy przez textContent; w hint'cie ikona inline jest realnym elementem
// DOM (a nie innerHTML'em wstrzyknietym z tlumaczenia) — bezpieczne nawet gdy
// tlumaczenie zawiera znaki specjalne wokol placeholdera {icon}.
// .room-list-groups chowamy przez CSS :has() (patrz tailwind.css) — nie tykamy
// inline style, zeby nie kolidowac z sort'em wg czasu, ktory tez ustawia
// .room-list-groups { display: none }.
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

    // Hint: split tlumaczenia po {icon} i wstaw realny <i> miedzy text nodes.
    // Ikona jest dokladnie ta sama co w #unread-filter-btn — wizualnie spina
    // komunikat z akcja, ktora user ma wykonac.
    const hint = document.createElement('p');
    hint.className = 'tw-chat-no-unread-hint';
    // after = '' jako bezpiecznik: gdyby tlumaczenie kiedys zgubilo placeholder {icon},
    // split zwroci 1-elementowa tablice i bez defaultu createTextNode(undefined) wstawilby
    // literalny napis "undefined" po przycisku.
    const [before, after = ''] = _("Tap {icon} above the list to disable the unread filter").split('{icon}');
    hint.appendChild(document.createTextNode(before));
    // Realny, klikalny przycisk wygladajacy DOKLADNIE jak aktywny #unread-filter-btn —
    // user widzi tu te sama (podswietlona) ikone, ktora ma kliknac w pasku, i moze ja
    // kliknac wprost stad. Logiki nie duplikujemy: delegujemy do .click() prawdziwego
    // przycisku (zdejmie filtr i — przez removeUnreadFilter — usunie ten empty state).
    const inlineBtn = document.createElement('button');
    inlineBtn.type = 'button';
    inlineBtn.className = 'tw-chat-no-unread-inline-btn';
    // Etykieta opisuje AKCJE tego przycisku (zawsze zdejmuje filtr), nie kierunek toggle'a —
    // ten przycisk, w przeciwienstwie do #unread-filter-btn w pasku, tylko wylacza filtr.
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

function hideUnreadEmptyState() {
    // .remove() wystarcza — CSS :has() wyrejestruje regule
    // .room-list-groups { display: none } sam
    document.getElementById('chat-no-unread-empty-state')?.remove();
}

// ── Model listy pokoi (Etap H) ──────────────────────────────────────────────
// Serwerowy DOM pozostaje źródłem prawdy hierarchii (kategorie, archiwa).
// Model przechowuje wyłącznie "pozycję domową" każdego linku: element
// nadrzędny + indeks wśród jego dzieci. Reset odtwarza pozycję z modelu,
// więc nie zależy od przypadkowego nextSibling.

/** Klucz sortowania pokoju — unix seconds z data-last-activity. */
function roomLinkSortKey(link) {
    return parseInt(link.dataset.lastActivity || '0', 10);
}

/** Komparator płaskiej listy: 'newest' malejąco, 'oldest' rosnąco. */
function roomLinkComparator(mode) {
    return (a, b) => mode === 'oldest'
        ? roomLinkSortKey(a) - roomLinkSortKey(b)
        : roomLinkSortKey(b) - roomLinkSortKey(a);
}

/** Pokój bierze udział w płaskim widoku, gdy nie siedzi w ukrytym archiwum. */
function isRoomListLinkVisible(link) {
    const archive = link.closest('.tw-archive-section');
    return !archive || archive.classList.contains('tw-visible');
}

/** Map<Element, {parent, index}> — domowe pozycje linków przed spłaszczeniem. */
function captureRoomHomes(links) {
    return new Map(links.map(link => [link, {
        parent: link.parentElement,
        index: Array.prototype.indexOf.call(link.parentElement.children, link),
    }]));
}

/**
 * Odtwarza pozycje z modelu: grupuje po parent i wstawia rosnąco po index,
 * więc poprawne nawet gdy rodzeństwo w międzyczasie się zmieniło.
 */
function restoreRoomHomes(homes) {
    const byParent = new Map();
    homes.forEach((pos, link) => {
        if (!byParent.has(pos.parent)) byParent.set(pos.parent, []);
        byParent.get(pos.parent).push([pos.index, link]);
    });
    byParent.forEach((entries, parent) => {
        entries.sort((a, b) => a[0] - b[0]);
        entries.forEach(([index, link]) => {
            parent.insertBefore(link, parent.children[index] || null);
        });
    });
}

let roomHomes = null;   // Map<Element, {parent, index}> albo null gdy sort wyłączony
let roomSortMode = null; // 'newest' | 'oldest' | null
let flatListEl = null;   // #room-list-flat — kontener płaskiej listy

/** Spłaszcza listę do #room-list-flat i sortuje wg data-last-activity. */
function applyRoomSort(mode) {
    const roomListEl = $('#room-list');
    const groups = roomListEl?.querySelector('.tw-room-list-groups');
    if (!roomListEl || !groups) return;

    if (!flatListEl) {
        const links = [...$$('.tw-room-link[data-room-id]')].filter(isRoomListLinkVisible);
        roomHomes = captureRoomHomes(links);
        flatListEl = document.createElement('div');
        flatListEl.id = 'room-list-flat';
        links.forEach(link => flatListEl.appendChild(link));
        groups.classList.add('tw-d-none');
        roomListEl.appendChild(flatListEl);
    }

    resortFlatRoomList(mode);

    const btn = $('#sort-activity-btn');
    btn?.classList.add('tw-active');
    const dirIcon = btn?.querySelector('.tw-sort-dir-icon');
    if (dirIcon) dirIcon.className = `tw-sort-dir-icon fas fa-arrow-${mode === 'oldest' ? 'up' : 'down'}`;
    localStorage.setItem('chat-sort-mode', mode);
}

/** Przywraca układ kategorii z modelu i usuwa płaski kontener. */
function resetRoomSort() {
    if (!flatListEl || !roomHomes) return;

    restoreRoomHomes(roomHomes);
    flatListEl.remove();
    flatListEl = null;
    roomHomes = null;
    roomSortMode = null;

    const groups = $('#room-list')?.querySelector('.tw-room-list-groups');
    if (groups) groups.classList.remove('tw-d-none');

    const btn = $('#sort-activity-btn');
    btn?.classList.remove('tw-active');
    const dirIcon = btn?.querySelector('.tw-sort-dir-icon');
    if (dirIcon) dirIcon.className = 'tw-sort-dir-icon fas fa-arrow-down';
    localStorage.removeItem('chat-sort-mode');
}

/**
 * Deterministycznie porządkuje płaską listę; wołane także po aktualizacji
 * data-last-activity przez updateRoomListForMessage, żeby tryb 'oldest'
 * nie rozjechał się z DOM.
 */
function resortFlatRoomList(mode = roomSortMode) {
    if (!flatListEl || !mode) return;
    roomSortMode = mode;
    [...flatListEl.querySelectorAll('.tw-room-link[data-room-id]')]
        .sort(roomLinkComparator(mode))
        .forEach(link => flatListEl.appendChild(link));
}

/**
 * Aktualizacja wiersza pokoju po wiadomości: domapi aktualizuje model
 * (data-*, podgląd, unread), a my dociągamy bieżący widok płaskiej listy.
 */
function updateRoomListForMessage(msg, opts) {
    DOM_API.updateSidebarForMessage(msg, opts);
    resortFlatRoomList();
}

document.addEventListener('DOMContentLoaded', () => {
    WS_API = new WsApi();
    DOM_API = new DomApi();

    // Set the WebSocket message handler to break circular dependency
    WS_API.socketMessageHandler = onSocketMessage;

    // Nawigacja historii i ręczne zmiany fragmentu → idempotentna synchronizacja trasy.
    window.addEventListener('popstate', () => syncRouteFromLocation());
    window.addEventListener('hashchange', () => syncRouteFromLocation());
    mobileMedia.addEventListener('change', renderChatView);

    document.addEventListener('input', (e) => {
        if (e.target.id === 'message-input') saveDraft();
    });

    // Handle unread filter functionality
    const unreadFilterBtn = $('#unread-filter-btn');

    // Restore filter state from localStorage. URL params bija zapisany stan:
    //   ?view=unread  -> wymuszamy filtr ON  (dashboard badge; ?unread=1 to legacy alias)
    // Robimy to juz tu (nie tylko przy otwarciu WS), zeby unikac wizualnego migniecia.
    const initialParams = new URLSearchParams(location.search);
    const initialView = initialParams.get('view');
    const wantsUnreadStart = initialView === 'unread' || initialParams.get('unread') === '1';
    const savedFilterState = localStorage.getItem('chat-unread-filter');
    const shouldRestoreFilter = wantsUnreadStart || savedFilterState === 'active';
    if (shouldRestoreFilter) {
        isUnreadFilterActive = true;
        unreadFilterBtn?.classList.add('tw-active');
        applyUnreadFilter();
    }

    unreadFilterBtn?.addEventListener('click', () => {
        userToggledFilter = true;
        setUnreadFilter(!isUnreadFilterActive);
    });

    // Make function globally available for other modules
    window.updateUnreadFilter = updateUnreadFilter;

    // Sort rooms by last activity — cycles: off → newest → oldest → newest…
    // Logika i model pozycji są na poziomie modułu (patrz sekcja "Model listy
    // pokoi"); tu pozostaje tylko okablowanie przycisków i zapisanej preferencji.
    const savedSort = localStorage.getItem('chat-sort-mode');
    if (savedSort === 'newest' || savedSort === 'oldest') {
        applyRoomSort(savedSort);
    }

    $('#sort-activity-btn')?.addEventListener('click', () => {
        applyRoomSort(roomSortMode === 'newest' ? 'oldest' : 'newest');
    });
    $('#sort-reset-btn')?.addEventListener('click', resetRoomSort);

    // Trasa z URL jest stosowana natychmiast — niezależnie od stanu socketu.
    // Join do pokoju i tak kolejkuje się do pierwszego otwarcia socketu
    // (ReconnectingWebSocket buforuje wysyłkę), a ?view=rooms / ?view=unread
    // pokazują listę nawet gdy połączenie jeszcze nie wstało.
    syncRouteFromLocation({ initial: true });

    // Jawny wskaźnik stanu połączenia — widoczny tylko przy rozłączeniu,
    // nie zasłania wiadomości (pointer-events: none). 'offline' pochodzi
    // z navigator.onLine / zdarzeń offline/online — reszta z lifecycle WS.
    const connStatusEl = document.getElementById('chat-conn-status');
    const connStatusText = document.getElementById('chat-conn-status-text');
    const setConnectionStatus = (status) => {
        ViewState.connectionStatus = status;
        if (!connStatusEl) return;
        const show = status === 'reconnecting' || status === 'offline';
        connStatusEl.classList.toggle('tw-d-none', !show);
        if (show) {
            connStatusText.textContent = status === 'offline' ? _('You are offline.') : _('Reconnecting...');
        }
    };
    window.addEventListener('offline', () => setConnectionStatus('offline'));
    window.addEventListener('online', () => setConnectionStatus('reconnecting'));

    // Pierwszy open tego socketu: tylko poboczne dane, niezależnie —
    // ich błąd nie może zablokować nawigacji.
    WS_API.wsOnConnect = () => {
        setConnectionStatus('online');
        WS_API.getOnlineUsers()
            .then(d => d.online_data.forEach(u => DOM_API.updateOnline(u.room_id, u.online)))
            .catch(err => console.warn('getOnlineUsers failed:', err));
        WS_API.getNotificationData()
            .then(data => {
                const enabledRooms = new Set(data.rooms.map(id => parseInt(id)));
                $$('.tw-notif-switch[data-room-id]').forEach(btn => {
                    DOM_API.setRoomNotifications(parseInt(btn.dataset.roomId), enabledRooms.has(parseInt(btn.dataset.roomId)));
                });
            })
            .catch(err => console.warn('getNotificationData failed:', err));
    };

    // Kolejny open po zerwaniu: reconnect NIE może zmieniać URL, historii
    // ani widocznego panelu — tylko przywraca członkostwo w pokoju.
    WS_API.wsOnReconnect = () => {
        setConnectionStatus('online');
        WS_API.getOnlineUsers()
            .then(d => d.online_data.forEach(u => DOM_API.updateOnline(u.room_id, u.online)))
            .catch(err => console.warn('getOnlineUsers failed:', err));
        if (ViewState.requestedRoomId && ViewState.requestedRoomId !== CurrentRoomId) {
            // Nawigacja do pokoju była w toku, gdy połączenie się urwało — dokończ ją.
            void onRoomTryJoin(ViewState.requestedRoomId);
        } else if (CurrentRoomId) {
            const roomToRejoin = CurrentRoomId;
            CurrentRoomId = null; // odblokuj short-circuit w onRoomTryJoin
            void onRoomTryJoin(roomToRejoin, { preserveView: true });
        }
    };

    WS_API.wsOnDisconnect = () => setConnectionStatus(navigator.onLine === false ? 'offline' : 'reconnecting');
});

export async function onSocketMessage(data) {
    if (data.join || data.leave) console.warn("deprecated");
    else if (data.replace_messages) onReplaceMessages(data.messages, data.room_id);
    else if (data.messages) onReceiveMessages(data.messages);
    else if (data.unsee_room) onRoomUnsee(data.unsee_room);
    else if (data.room_seen) onRoomSeen(data.room_seen);
    else if (data.update_votes) onReceiveVotes(data.update_votes);
    else if (data.edit_message) onReceiveEdit(data.edit_message);
    else if (data.online_data) onReceiveOnlineUpdates(data.online_data);
    else if (data.update_reactions) onReceiveReactions(data.update_reactions);
    else if (data.messages_read) onReceiveReadBy(data.messages_read);
    // data.notification jest obsługiwane przez notifications.js (jeden właściciel
    // browserowych powiadomień — broadcast idzie do wszystkich subskrybentów).
    // unread_count is consumed by the home page WS listener — ignore here
    else console.log("Cannot handle message!");
}

/**
 * Expands the nav-cat-content (and archive section if needed) for the given room link.
 * @param {HTMLElement} roomLink - The room link element
 */
function expandCategoryForRoom(roomLink) {
    // Expand the nav-cat-content that wraps this room
    const navCatContent = roomLink.closest('.tw-chat-cat-content');
    if (navCatContent) {
        if (!navCatContent.classList.contains('tw-open')) {
            navCatContent.classList.add('tw-open');
            const catId = navCatContent.id;
            const catBtn = catId ? document.querySelector(`[data-cat-content="${catId}"]`) : null;
            if (catBtn) catBtn.setAttribute('aria-expanded', 'true');
            if (catId) localStorage.setItem(`chat-cat-${catId}`, 'expanded');
        }
    }

    // If it's inside an archive section, reveal all archived rooms via the global toggle
    if (roomLink.closest('.tw-archive-section')) {
        document.querySelectorAll('.tw-archive-section').forEach(s => s.classList.add('tw-visible'));
        document.getElementById('archive-toggle-global-btn')?.classList.add('tw-active');
        localStorage.setItem('chat-archive-global', 'visible');
    }
}

/**
 * Build breadcrumb parts array for a given room_id by walking the sidebar DOM.
 * @param {number|string} room_id
 * @returns {Array<{label: string, active?: boolean}>}
 */
function deriveBreadcrumb(room_id) {
    const link = DOM_API.getRoomLinkDiv(room_id);
    if (!link) return [];

    const parts = [];

    // L0 — category label from the nav-cat-btn
    const navCatContent = link.closest('.tw-chat-cat-content');
    if (navCatContent) {
        const catId = navCatContent.id;
        const catBtn = catId ? document.querySelector(`[data-cat-content="${catId}"]`) : null;
        if (catBtn) {
            // Extract text nodes only (skip .nav-cat-arrow span)
            const label = Array.from(catBtn.childNodes)
                .filter(n => n.nodeType === Node.TEXT_NODE)
                .map(n => n.textContent.trim())
                .filter(Boolean)
                .join('');
            if (label) parts.push({ label });
        }
    }

    // Leaf — room name (may show override_label = task/vote title)
    const roomName = link.querySelector('.tw-room-name')?.textContent?.trim();
    if (roomName) parts.push({ label: roomName, active: true });

    return parts;
}

/**
 * Dołącza do pokoju. Treść pokoju buduje zawsze po sukcesie; przełączenie
 * widocznego panelu następuje tylko gdy żądanie jest nadal aktualne
 * (nie wyprzedziło go nowsze) i nie jest to techniczny rejoin.
 * @param {number} room_id
 * @param {Object} [options]
 * @param {boolean} [options.preserveView] - reconnect: dołącz bez zmiany panelu
 */
export async function onRoomTryJoin(room_id, { preserveView = false } = {}) {
    room_id = parseInt(room_id);
    if (room_id === CurrentRoomId) {
        // Już dołączony — upewnij się tylko, że panel pokoju jest widoczny.
        ViewState.panel = 'room';
        ViewState.requestedRoomId = room_id;
        hideRoomPlaceholder();
        renderChatView();
        return;
    }
    const generation = ++JoinGeneration;
    ViewState.requestedRoomId = room_id;
    ViewState.joinStatus = 'joining';
    if (RoomLock.locked()) await RoomLock.wait();
    if (generation !== JoinGeneration) return; // wyprzedziło nas nowsze żądanie
    if (CurrentRoomId) await onRoomTryLeave(false);

    const joiningRoomLink = DOM_API.getRoomLinkDiv(room_id);
    joiningRoomLink?.classList.add("tw-room-link--joined");
    // WS może być jeszcze w trakcie łączenia (np. tuż po otwarciu strony albo
    // reconnect po zerwaniu połączenia) — komenda "join" zostanie zakolejkowana
    // i wyslana automatycznie po otwarciu socketu, ale to moze potrwac chwile.
    // Pokazujemy prosty spinner na linku do pokoju, zeby user wiedzial, ze cos sie dzieje.
    const showConnectingSpinner = !WS_API.isConnected();
    if (showConnectingSpinner) joiningRoomLink?.classList.add("tw-room-link--connecting");
    RoomLock.lock();
    let response;
    try {
        response = await WS_API.joinRoom(room_id);
    } catch (error) {
        RoomLock.unlock();
        if (showConnectingSpinner) joiningRoomLink?.classList.remove("tw-room-link--connecting");
        joiningRoomLink?.classList.remove("tw-room-link--joined");
        ViewState.joinStatus = 'error';
        if (error === 'ROOM_INVALID' || error === 'ACCESS_DENIED') {
            delete localStorage.lastUsedRoomID;
            // Pokój niedostępny/nieistniejący — wróć do listy (replace, nie push,
            // żeby nie zostawiać martwego wpisu z hashem w historii).
            if (location.hash) {
                history.replaceState(null, '', location.pathname + location.search);
                LastAppliedRouteKey = null;
                syncRouteFromLocation();
            }
            window.showToast?.(_('This room is not available.'));
        } else {
            // Błędy techniczne (timeout, rozłączenie) — toast + jawny stan
            // z retry w kolumnie wiadomości (na desktopie panel byłby pusty).
            window.showToast?.(_('Could not join the room.'));
            showJoinError(room_id);
            console.warn('joinRoom failed:', error);
        }
        return;
    }
    RoomLock.unlock();
    if (showConnectingSpinner) joiningRoomLink?.classList.remove("tw-room-link--connecting");

    // Żądanie mogło zostać wyprzedzone (klik w inny pokój albo powrót na listę)
    // albo to techniczny rejoin — wtedy budujemy treść, ale nie ruszamy panelu.
    const stale = generation !== JoinGeneration || ViewState.requestedRoomId !== room_id;
    localStorage.lastUsedRoomID = room_id;
    CurrentRoomId = room_id;
    ViewState.joinStatus = 'joined';
    // TODO: send seen confirmation to server after a little while
    DOM_API.seenChat(room_id);
    WS_API.seenRoom(room_id);
    DOM_API.setRoomNotifications(response.notifications);
    DOM_API.createRoomDiv(room_id, response.title, response.public, response.notifications, response.can_post ?? true);
    resetSortState();
    bindSortToolbar();
    DOM_API.updateBreadcrumb(deriveBreadcrumb(room_id));

    // Auto-expand category and archive section if needed
    const roomLink = DOM_API.getRoomLinkDiv(room_id);
    if (roomLink) {
        expandCategoryForRoom(roomLink);
    }

    if (!stale && !preserveView) {
        ViewState.panel = 'room';
        hideRoomPlaceholder();
    }
    renderChatView();

    // Restore draft after DOM is fully updated
    requestAnimationFrame(() => restoreDraft(room_id));

    // Focus only on desktop — on mobile the keyboard would open immediately
    if (!stale && !preserveView && !mobileMedia.matches) {
        DOM_API.getMessageInput()?.focus();
    }
}

/**
 * @param {boolean} sync_with_server - If true, sends leave command to server
 */
export async function onRoomTryLeave(sync_with_server) {
    if (RoomLock.locked()) await RoomLock.wait();
    saveDraft();
    isClearingInput = true;
    if (sync_with_server) {
        RoomLock.lock();
        await WS_API.leaveRoom(CurrentRoomId);
        RoomLock.unlock();
    }
    DOM_API.getRoomLinkDiv(CurrentRoomId)?.classList.remove("tw-room-link--joined");
    DOM_API.clearRoomData();
    resetSortState();
    for (const t of pendingTimeouts.values()) clearTimeout(t);
    pendingTimeouts.clear();
    CurrentRoomId = null;
    ViewState.joinStatus = 'idle';
    isClearingInput = false;
    renderChatView();
}


/**
 * @param {Array} messages - Array of message objects from server
 */
export async function onReceiveMessages(messages) {
    const room_id = parseInt(messages[0].room_id);
    if (room_id !== CurrentRoomId) {
        console.warn("received message for wrong room");
        return;
    }

    const msgdiv = DOM_API.getMessagesDiv();
    DOM_API.removeNoMessagesBanner();

    if (messages.length === 1) {
        // Single message (real-time) — normal path
        const message = messages[0];

        // Optimistic UI — own message echoed back matches a pending placeholder; skip normal render path.
        if (message.own && message.temp_id) {
            const pending = msgdiv?.querySelector(`.tw-chat-message[data-temp-id="${message.temp_id}"]`);
            if (pending) {
                DOM_API.confirmMessage(message.temp_id, message.message_id);
                const t = pendingTimeouts.get(message.temp_id);
                if (t) { clearTimeout(t); pendingTimeouts.delete(message.temp_id); }
                updateRoomListForMessage(message);
                return;
            }
        }

        DOM_API.appendDateBanner(formatDate(message.timestamp));
        DOM_API.addMessage(
            message.room_id, message.user_id ?? null, message.avatar_url ?? null, message.citizen_color_class ?? '', message.message_id, message.username, message.message,
            message.upvotes, message.downvotes, message.your_vote, message.own, message.edited,
            message.attachments, message.timestamp, message.latest_timestamp,
            message.reply_to ?? null,
            message.reactions ?? { bulb: 0, question: 0 },
            message.your_reactions ?? [],
            message.read_by ?? [],
            message.upvoters, message.downvoters,
            null, message.display_name ?? null, message.initials ?? null
        );
        if (message.new) updateRoomListForMessage(message);
        if (message.new && !message.own) WS_API?.markMessageRead(message.message_id);
        requestAnimationFrame(() => DOM_API.markOverflow(DOM_API.getMessageDiv(message.message_id)));
    } else {
        // Batch load (join room) — build all HTML at once, single DOM insertion
        let batchHtml = '';
        let lastBannerText = DOM_API.lastDateBannerText();

        for (const message of messages) {
            const current_banner = formatDate(message.timestamp);
            if (current_banner !== lastBannerText) {
                batchHtml += dateBannerHtml(current_banner);
                lastBannerText = current_banner;
            }
            batchHtml += DOM_API.buildMessageHtml(
                message.room_id, message.user_id ?? null, message.avatar_url ?? null, message.citizen_color_class ?? '', message.message_id, message.username, message.message,
                message.upvotes, message.downvotes, message.your_vote, message.own, message.edited,
                message.attachments, message.timestamp, message.latest_timestamp,
                message.reply_to ?? null,
                message.reactions ?? { bulb: 0, question: 0 },
                message.your_reactions ?? [],
                message.read_by ?? [],
                message.upvoters, message.downvoters,
                message.display_name ?? null, message.initials ?? null
            );
        }
        if (batchHtml) msgdiv.insertAdjacentHTML('beforeend', batchHtml);

        // Apply active vote states after batch insert
        for (const message of messages) {
            if (message.your_vote) {
                DOM_API.getVoteDiv(message.message_id, message.your_vote)?.classList.add('tw-active');
            }
        }
        const toMarkRead = messages.filter(m => !m.own).map(m => m.message_id);
        WS_API?.markMessagesReadBulk(toMarkRead, messages[0].room_id);
        requestAnimationFrame(() => DOM_API.markOverflow(msgdiv));
    }

    let shouldStickToBottom = !ScrollToMessageId;
    if (ScrollToMessageId) {
        const didScroll = DOM_API.scrollToMessage(ScrollToMessageId);
        if (didScroll) {
            shouldStickToBottom = false;
            ScrollToMessageId = null;
        }
    }
    if (shouldStickToBottom && msgdiv) msgdiv.scrollTop = msgdiv.scrollHeight;
}

/**
 * Replace all rendered messages after a sort/filter fetch.
 * Clears existing messages and re-renders them in the order returned by server.
 */
export async function onReplaceMessages(messages, room_id) {
    if (room_id != CurrentRoomId) {
        console.warn("replace_messages for wrong room", room_id, CurrentRoomId);
        return;
    }

    const msgdiv = DOM_API.getMessagesDiv();
    if (!msgdiv) return;
    msgdiv.innerHTML = '';

    if (!messages || !messages.length) {
        DOM_API.removeNoMessagesBanner();
        msgdiv.insertAdjacentHTML('beforeend', `<div class='tw-empty-chat-message'>${_("No messages match the current filter.")}</div>`);
        return;
    }

    for (const message of messages) {
        DOM_API.addMessage(
            message.room_id, message.user_id ?? null, message.avatar_url ?? null, message.citizen_color_class ?? '', message.message_id, message.username, message.message,
            message.upvotes, message.downvotes, message.your_vote, message.own, message.edited,
            message.attachments, message.timestamp, message.latest_timestamp,
            message.reply_to ?? null,
            message.reactions ?? { bulb: 0, question: 0 },
            message.your_reactions ?? [],
            message.read_by ?? [],
            message.upvoters, message.downvoters,
            null, message.display_name ?? null, message.initials ?? null
        );
        if (message.your_vote) {
            DOM_API.getVoteDiv(message.message_id, message.your_vote)?.classList.add('tw-active');
        }
    }

    requestAnimationFrame(() => DOM_API.markOverflow(msgdiv));
    msgdiv.scrollTop = 0;
}

/**
 * Handles vote updates for a message
 * @param {Object} event - Vote update event data
 * @param {number} event.message_id - ID of the message that was voted on
 * @param {number} event.upvotes - Updated upvote count
 * @param {number} event.downvotes - Updated downvote count
 * @param {string|null} event.your_vote - Current user's vote ('upvote', 'downvote', or null)
 * @param {boolean} event.add - Whether vote was added (true) or removed (false)
 */
export async function onReceiveVotes(event) {
    const message_div = DOM_API.getMessageDiv(event.message_id);
    DOM_API.getMessageUpvotesCountDiv(event.message_id).textContent = event.upvotes;
    DOM_API.getMessageDownvotesCountDiv(event.message_id).textContent = event.downvotes;

    if (event.your_vote /* vote type e.g. upvote or downvote or null if it wasn't you who triggered */) {
        const active_btn = DOM_API.getVoteDiv(event.message_id, event.your_vote);
        if (message_div) $$('.tw-msg-vote', message_div).forEach(btn => btn.classList.remove('tw-active'));
        if (event.add) active_btn?.classList.add('tw-active');
    }

    // Pokoje zadań: serwer dosyła nicki głosujących — odśwież tooltipsy łapek.
    if (event.upvoters !== undefined) {
        const upBtn = DOM_API.getVoteDiv(event.message_id, 'upvote');
        const dnBtn = DOM_API.getVoteDiv(event.message_id, 'downvote');
        if (upBtn) upBtn.title = voteButtonTitle(_('Upvote'), event.upvoters);
        if (dnBtn) dnBtn.title = voteButtonTitle(_('Downvote'), event.downvoters);
    }

    // update vote bar after vote change
    DOM_API.updateVoteBar(event.message_id, event.upvotes, event.downvotes);
}

/**
 * update emoji reaction counts + active state for a message.
 */
export async function onReceiveReactions(event) {
    const msgDiv = DOM_API.getMessageDiv(event.message_id);
    if (!msgDiv) return;

    // Update counts
    for (const [key, count] of Object.entries(event.counts || {})) {
        const countEl = $(`.tw-reaction-btn[data-reaction="${key}"] .tw-reaction-count`, msgDiv);
        const btn = $(`.tw-reaction-btn[data-reaction="${key}"]`, msgDiv);
        if (!btn) continue;
        if (count > 0) {
            if (countEl) {
                countEl.textContent = count;
            } else {
                btn.insertAdjacentHTML('beforeend', `<span class="tw-reaction-count">${count}</span>`);
            }
        } else if (countEl) {
            countEl.remove();
        }
    }

    // Toggle active state if it was the current user
    if (event.your_reaction !== undefined && event.your_reaction !== null) {
        const btn = $(`.tw-reaction-btn[data-reaction="${event.your_reaction}"]`, msgDiv);
        if (btn) btn.classList.toggle('tw-reaction-btn--active', event.added ?? false);
    }
}

/**
 * Update "read by" button and dropdown for a message after someone reads it.
 */
export async function onReceiveReadBy(event) {
    const msgDiv = DOM_API.getMessageDiv(event.message_id);
    if (!msgDiv) return;

    const readBy = event.read_by || [];
    const btn = msgDiv.querySelector('.tw-read-by-toggle');
    const dropdown = document.getElementById(`read-by-dropdown-${event.message_id}`);
    if (!btn || !dropdown) return;

    const listHtml = readBy.map(u => {
        const colorClass = u.citizen_color_class || '';
        const name = u.display_name || u.username || '';
        const avatar = u.avatar_url
            ? `<img class="tw-avatar tw-avatar-xl" src="${u.avatar_url}" alt="${name}">`
            : `<span class="tw-avatar tw-avatar-xl tw-avatar-fallback ${colorClass}">${u.initials || (u.username || '').slice(0, 2).toUpperCase()}</span>`;
        return `<div class="tw-read-by-item">${avatar}<span class="tw-read-by-username">${name}</span></div>`;
    }).join('');

    let countEl = btn.querySelector('.tw-read-by-count');
    if (!countEl) {
        countEl = document.createElement('span');
        countEl.className = 'tw-read-by-count';
        btn.appendChild(countEl);
    }
    countEl.textContent = readBy.length;
    btn.title = `${readBy.length} osób przeczytało tę wiadomość`;
    dropdown.querySelector('.tw-read-by-list').innerHTML = listHtml;
}

export async function onReceiveEdit(edit_info) {
    DOM_API.editMessageText(edit_info.message_id, edit_info.text, edit_info.timestamp);
    if (edit_info.attachments !== undefined) {
        DOM_API.updateMessageAttachments(edit_info.message_id, edit_info.attachments);
    }
    DOM_API.showHistoryButton(edit_info.message_id);

    if (edit_info.is_last_message) {
        updateRoomListForMessage({
            room_id: edit_info.room_id,
            username: edit_info.username,
            display_name: edit_info.display_name,
            anonymous: edit_info.anonymous,
            message: edit_info.text,
            timestamp: edit_info.timestamp,
        }, {reorder: false});
    }

    // Stop editing mode if this was the message being edited
    const editedId = DOM_API.getEditedMessageId();

    // Convert both to strings for comparison since message_id can be string or number
    const editedIdStr = editedId ? String(editedId) : null;
    const messageIdStr = String(edit_info.message_id);

    if (DOM_API.isEditing() && editedIdStr && editedIdStr === messageIdStr) {
        DOM_API.stopEditing();
    }
}

export async function onReceiveOnlineUpdates(updates) {
    for (const update of updates) {
        DOM_API.updateOnline(update.room_id, update.online);
    }
}

export async function onRoomUnsee(room_id) {
    if (CurrentRoomId == room_id) return;
    DOM_API.getRoomLinkDiv(room_id)?.classList.add("tw-room-link--not-seen");
    DOM_API.setRoomSeenIconState(room_id, false);
    updateUnreadFilter();
}

export async function onRoomSeen(room_id) {
    DOM_API.getRoomLinkDiv(room_id)?.classList.remove("tw-room-link--not-seen");
    DOM_API.setRoomSeenIconState(room_id, true);
    updateUnreadFilter();
}

/**
 * Set a message as the current reply target.
 * Updates the reply-preview bar in the input area.
 */
export function setReplyTarget(message_id, username, snippet) {
    const preview = document.getElementById('reply-preview');
    const previewText = document.getElementById('reply-preview-text');
    currentReplyId = coreSetReplyTarget(message_id, username, snippet, preview, previewText);
    currentReplyData = { id: message_id, username, snippet };
}

/**
 * Clear the current reply target.
 */
export function clearReplyTarget() {
    const preview = document.getElementById('reply-preview');
    currentReplyId = coreClearReplyTarget(preview);
    currentReplyData = null;
}

/**
 * send toggle-reaction command to server.
 */
export function onToggleReaction(reaction, message_id) {
    WS_API?.toggleReaction(reaction, message_id);
}

export async function onUpdateVote(vote, message_id, is_add) {
    this.classList.toggle('tw-active');
    is_add ? WS_API.addVote(vote, message_id) : WS_API.removeVote(vote, message_id);
}

export async function onToggleNotifications(room_id, is_enabled) {
    WS_API.toggleNotifications(room_id, is_enabled);
}

export async function onToggleSeen(room_id, is_seen) {
    if (is_seen) {
        WS_API.seenRoom(room_id);
    } else {
        WS_API.markRoomUnseen(room_id);
    }
}

export async function onMessageHistory(message_id) {
    const data = await WS_API.getMessageHistory(message_id);
    const history = (data?.message_history || []).map(entry => ({
        ...entry, formattedTime: formatDateTime(entry.timestamp)
    }));

    $("#message-history-modal .tw-modal-body").innerHTML = MessageHistory({ history });
    const modal = $("#message-history-modal"); // Tailwind modal show
    if (modal && typeof TwModal !== 'undefined') {
        TwModal.show(modal);
    }
}

export async function copyRoomLink(room_id, button) {
    if (!room_id) return;
    const success = await writeToClipboard(buildRoomUrl(room_id));
    showCopyFeedback(button, success);
}

export async function copyMessageLink(room_id, message_id, button) {
    if (!room_id || !message_id) return;
    const success = await writeToClipboard(buildMessageUrl(room_id, message_id));
    showCopyFeedback(button, success);
}

async function writeToClipboard(text) {
    if (navigator.clipboard?.writeText) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (err) { console.warn('Clipboard API copy failed', err); }
    }
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.className = 'tw-offscreen';
    document.body.appendChild(textarea);
    textarea.select();
    let success = false;
    try { success = document.execCommand('copy'); }
    catch (err) { console.warn('document.execCommand copy failed', err); }
    finally { document.body.removeChild(textarea); }
    return success;
}

function showCopyFeedback(button, success) {
    const message = success ? _("Link copied") : _("Could not copy link");
    if (button?.closest('.tw-dropdown') && window.showToast) {
        window.showToast(message);
        return;
    }
    if (!button || !DOM_API || typeof DOM_API.showCopyFeedback !== 'function') return;
    DOM_API.showCopyFeedback(button, message, success);
}

function buildRoomUrl(room_id) {
    return `${window.location.origin}/chat#room_id=${room_id}`;
}

function buildMessageUrl(room_id, message_id) {
    return `${buildRoomUrl(room_id)}&message_id=${message_id}`;
}

export async function onSubmitMessage(message, editing_message_id) {
    if (editing_message_id) {
        const files = DOM_API.getFiles();
        const attachments = {};
        // Upload new files if any
        if (files?.length) {
            const sendBtn = document.querySelector('.tw-send-message');
            if (sendBtn) sendBtn.disabled = true;
            try {
                attachments.images = (await WS_API.uploadFiles(files)).filenames;
            } catch (err) {
                console.error('Upload failed', err);
                return;
            } finally {
                if (sendBtn) sendBtn.disabled = false;
            }
        }
        WS_API.editMessage(editing_message_id, message, attachments, DOM_API.getRemovedAttachments(), DOM_API.getOriginalMessageText(editing_message_id));
        // Don't stop editing immediately - let onReceiveEdit handle it after server confirms
    } else {
        const files = DOM_API.getFiles();
        const messageText = (typeof message === 'string')
            ? (message.replace(/<[^>]*>/g, '').trim())
            : '';
        if (messageText.length === 0 && (!files || files.length === 0)) return;

        const sendBtn = document.querySelector('.tw-send-message');
        if (sendBtn) sendBtn.disabled = true;

        const attachments = {};
        if (files?.length) {
            try {
                attachments.images = (await WS_API.uploadFiles(files)).filenames;
            } catch (err) {
                if (sendBtn) sendBtn.disabled = false;
                console.error('Upload failed', err);
                return;
            }
        }

        const is_anonymous = DOM_API.getAnonymousValue();
        const temp_id = (crypto.randomUUID?.() || `tmp-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`);
        const reply_to = currentReplyData
            ? { id: currentReplyData.id, username: currentReplyData.username, text_snippet: currentReplyData.snippet }
            : null;
        const userNameEl = document.querySelector('.tw-user-name');
        const ownUsername = is_anonymous
            ? 'Anonymous'
            : (userNameEl?.textContent?.trim() || '');
        const ownInitials = is_anonymous
            ? 'AN'
            : (userNameEl?.dataset?.initials || '');
        const now = Date.now();

        DOM_API.removeNoMessagesBanner();
        const msgdiv = DOM_API.getMessagesDiv();
        DOM_API.appendDateBanner(formatDate(now));

        DOM_API.addMessage(
            CurrentRoomId, null, null, '', temp_id, ownUsername, message,
            0, 0, null, true, false,
            attachments, now, now,
            reply_to, { bulb: 0, question: 0 }, [], [],
            null, null, temp_id, ownUsername, ownInitials
        );
        requestAnimationFrame(() => DOM_API.markOverflow(DOM_API.getMessageDiv(temp_id)));
        if (msgdiv) msgdiv.scrollTop = msgdiv.scrollHeight;

        WS_API.sendMessage(CurrentRoomId, message, is_anonymous, attachments, currentReplyId, temp_id);

        pendingTimeouts.set(temp_id, setTimeout(() => {
            pendingTimeouts.delete(temp_id);
            DOM_API.failMessage(temp_id);
        }, PENDING_TIMEOUT_MS));

        if (sendBtn) sendBtn.disabled = false;

        clearReplyTarget();
        DOM_API.clearFiles();
        const messageInput = DOM_API.getMessageInput();
        if (messageInput) {
            if (messageInput.isContentEditable) {
                messageInput.innerHTML = '';
            } else {
                messageInput.value = '';
                messageInput.style.setProperty('--textarea-height', 'auto');
                messageInput.style.setProperty('--textarea-height', '38px');
            }
            clearDraft(CurrentRoomId);
            messageInput.dispatchEvent(new InputEvent('input', { bubbles: true }));
        }
        if (DOM_API.isEditing()) {
            DOM_API.stopEditing();
        }
    }
}