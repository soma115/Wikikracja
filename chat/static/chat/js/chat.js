/**
 * @file
 * Main chat module for handling chat room interactions, message processing, and room management.
 * Coordinates between WebSocket API (WsApi) and DOM API (DomApi) to provide chat functionality.
 */

import { clearReplyTarget as coreClearReplyTarget, setReplyTarget as coreSetReplyTarget } from './chat-core.js';
import DomApi from './domapi.js';
import { MessageHistory } from './templates.js';
import { $, $$, _, formatDate, formatDateTime, Lock, makeNotification, parseParms } from './utility.js';
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
        dateBtn.classList.toggle('active', SortState.sort_by === 'date');
        likesBtn.classList.toggle('active', SortState.sort_by === 'likes');
        popularBtn.classList.toggle('active', SortState.popular_only);

        const setArrow = (btn, active) => {
            const arrow = btn.querySelector('.sort-arrow');
            if (!arrow) return;
            if (!active) { arrow.className = 'fas fa-arrow-down sort-arrow'; arrow.style.visibility = 'hidden'; return; }
            arrow.style.visibility = '';
            arrow.className = 'fas fa-arrow-' + (SortState.order === 'asc' ? 'up' : 'down') + ' sort-arrow';
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
 * Czysta funkcja decyzyjna dla startu chat'a na podstawie URL params + stanu DOM.
 * UWAGA: synchronizować z chat/static/chat/js/__tests__/startup_action.test.js
 * (wzór jak draft.test.js — funkcja kopiowana 1:1 do testu).
 */
function decideStartupAction({ search = '', hasHash = false, isMobile = false } = {}) {
    // Hash ma bezwzględny priorytet — użytkownik chce konkretny pokój
    if (hasHash) {
        return { mode: 'default', joinAction: 'auto' };
    }
    const params = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
    if (params.get('view') === 'rooms') {
        return {
            mode: 'rooms', unreadFilter: 'off', showPlaceholder: true,
            forceListVisible: true, mobileShowList: isMobile,
            joinAction: 'none', stripParam: 'view',
        };
    }
    // ?unread=1 to legacy alias (stare bookmark'y / push'e) — traktowany jak ?view=unread.
    // Akcja celowo nie zawiera showUnreadEmptyState — empty state jest pochodna stanu
    // filtra, obsluguje go applyUnreadFilter (zarowno przy starcie jak i w runtime).
    const wantsUnreadView = params.get('view') === 'unread' || params.get('unread') === '1';
    if (wantsUnreadView) {
        return {
            mode: 'unread', unreadFilter: 'on', showPlaceholder: true,
            forceListVisible: true, mobileShowList: isMobile,
            joinAction: 'none',
            stripParam: params.get('unread') === '1' ? 'unread' : 'view',
        };
    }
    return { mode: 'default', joinAction: 'auto' };
}

/**
 * Decyduje, czy STARTOWA intencja filtra (z URL) ma w wsOnConnect zmienic aktualny
 * stan filtra unread. Reczny klik usera (userToggled) MA PIERWSZENSTWO nad URL —
 * inaczej asynchroniczne wsOnConnect cofaloby decyzje usera ("filtr wraca po odkliknieciu").
 * Zwraca 'enable' | 'disable' | 'none'.
 * UWAGA: synchronizować z chat/static/chat/js/__tests__/unread_filter_override.test.js.
 */
function decideUnreadFilterOverride({ urlFilter, isActive, userToggled }) {
    // Reczna decyzja usera jest ostateczna — nie nadpisujemy jej intencja z URL.
    if (userToggled) return 'none';
    if (urlFilter === 'on' && !isActive) return 'enable';
    // Nie wyłączamy filtra dla urlFilter === 'off' — pozwalamy na przywracanie z localStorage
    return 'none';
}

// Placeholder "Wybierz pokoj" w lewej kolumnie — gdy nie ma joinowanego pokoju.
// Tekst budujemy przez textContent (defense-in-depth — gdyby kiedys w tlumaczeniu
// pojawil sie znak < lub &, to nie zlamie HTML'a).
function showRoomPlaceholder() {
    const messages = document.querySelector('.chat-root-messages');
    if (!messages || document.getElementById('chat-no-room-placeholder')) return;
    const div = document.createElement('div');
    div.id = 'chat-no-room-placeholder';
    div.className = 'chat-no-room-placeholder';

    const icon = document.createElement('i');
    icon.className = 'fas fa-comments chat-no-room-icon';
    icon.setAttribute('aria-hidden', 'true');

    const text = document.createElement('p');
    text.className = 'chat-no-room-text';
    text.textContent = _("Select a room from the list");

    div.append(icon, text);
    messages.appendChild(div);
}

function hideRoomPlaceholder() {
    document.getElementById('chat-no-room-placeholder')?.remove();
}

// Empty state w prawej kolumnie — gdy filtr unread aktywny ale brak nieprzeczytanych.
// Tekst budujemy przez textContent; w hint'cie ikona inline jest realnym elementem
// DOM (a nie innerHTML'em wstrzyknietym z tlumaczenia) — bezpieczne nawet gdy
// tlumaczenie zawiera znaki specjalne wokol placeholdera {icon}.
// .row chowamy przez CSS :has() (patrz chat.css) — nie tykamy inline style,
// zeby nie kolidowac z sort'em wg czasu, ktory tez ustawia .row { display: none }.
function showUnreadEmptyState() {
    const roomList = document.querySelector('#room-list');
    if (!roomList || document.getElementById('chat-no-unread-empty-state')) return;

    const div = document.createElement('div');
    div.id = 'chat-no-unread-empty-state';
    div.className = 'chat-no-unread-empty-state';

    const iconBig = document.createElement('i');
    iconBig.className = 'fas fa-envelope-open chat-no-unread-icon';
    iconBig.setAttribute('aria-hidden', 'true');

    const title = document.createElement('p');
    title.className = 'chat-no-unread-title';
    title.textContent = _("No unread messages");

    // Hint: split tlumaczenia po {icon} i wstaw realny <i> miedzy text nodes.
    // Ikona jest dokladnie ta sama co w #unread-filter-btn — wizualnie spina
    // komunikat z akcja, ktora user ma wykonac.
    const hint = document.createElement('p');
    hint.className = 'chat-no-unread-hint';
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
    inlineBtn.className = 'chat-no-unread-inline-btn';
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
    // .remove() wystarcza — CSS :has() wyrejestruje regule .row { display: none } sam
    document.getElementById('chat-no-unread-empty-state')?.remove();
}

document.addEventListener('DOMContentLoaded', () => {
    WS_API = new WsApi();
    DOM_API = new DomApi();

    // Set the WebSocket message handler to break circular dependency
    WS_API.socketMessageHandler = onSocketMessage;

    document.addEventListener('input', (e) => {
        if (e.target.id === 'message-input') saveDraft();
    });

    // Handle unread filter functionality
    const unreadFilterBtn = $('#unread-filter-btn');
    let isUnreadFilterActive = false;
    // Gdy user recznie kliknie filtr, jego decyzja jest ostateczna na te sesje strony —
    // pozniejsze (asynchroniczne) wsOnConnect NIE moze jej nadpisac intencja z URL.
    let userToggledFilter = false;

    // Restore filter state from localStorage. URL params bija zapisany stan:
    //   ?view=unread  -> wymuszamy filtr ON  (dashboard badge; ?unread=1 to legacy alias)
    // Robimy to juz tu (nie tylko w wsOnConnect), zeby unikac wizualnego migniecia.
    const initialParams = new URLSearchParams(location.search);
    const initialView = initialParams.get('view');
    const wantsUnreadStart = initialView === 'unread' || initialParams.get('unread') === '1';
    const savedFilterState = localStorage.getItem('chat-unread-filter');
    const shouldRestoreFilter = wantsUnreadStart || savedFilterState === 'active';
    if (shouldRestoreFilter) {
        isUnreadFilterActive = true;
        unreadFilterBtn?.classList.add('active');
        applyUnreadFilter();
    }

    unreadFilterBtn?.addEventListener('click', () => {
        userToggledFilter = true;
        isUnreadFilterActive = !isUnreadFilterActive;

        if (isUnreadFilterActive) {
            unreadFilterBtn.classList.add('active');
            localStorage.setItem('chat-unread-filter', 'active');
            applyUnreadFilter();
        } else {
            unreadFilterBtn.classList.remove('active');
            localStorage.removeItem('chat-unread-filter');
            removeUnreadFilter();
        }
    });

    function applyUnreadFilter() {
        // Filter rooms - show only unread using CSS class
        const allRoomLinks = $$('.room-link[data-room-id]');
        allRoomLinks.forEach(roomLink => {
            // Add class to hide read rooms
            if (!roomLink.classList.contains('room-not-seen')) {
                roomLink.classList.add('filtered-out');
            } else {
                roomLink.classList.remove('filtered-out');
            }
        });
        // Empty state w prawej kolumnie — zawsze gdy filtr daje 0 wynikow
        const unreadCount = $$('.room-link.room-not-seen[data-room-id]').length;
        if (unreadCount === 0) {
            showUnreadEmptyState();
        } else {
            hideUnreadEmptyState();
        }
    }

    function removeUnreadFilter() {
        const allRoomLinks = $$('.room-link[data-room-id]');
        allRoomLinks.forEach(roomLink => {
            roomLink.classList.remove('filtered-out');
        });
        hideUnreadEmptyState();
    }

    // Function to reapply unread filter when room seen status changes
    function updateUnreadFilter() {
        if (isUnreadFilterActive) {
            applyUnreadFilter();
        }
    }

    // Make function globally available for other modules
    window.updateUnreadFilter = updateUnreadFilter;

    // Sort rooms by last activity — cycles: off → newest → oldest → newest…
    const sortActivityBtn = $('#sort-activity-btn');
    const sortResetBtn = $('#sort-reset-btn');
    let isSortActive = false;
    let sortMode = null; // 'newest' | 'oldest'
    let roomOriginalPositions = null;
    let flatContainer = null;

    const savedSort = localStorage.getItem('chat-sort-mode');
    if (savedSort === 'newest' || savedSort === 'oldest') {
        applySortView(savedSort);
    }

    sortActivityBtn?.addEventListener('click', () => {
        if (!isSortActive) {
            applySortView('newest');
        } else {
            applySortView(sortMode === 'newest' ? 'oldest' : 'newest');
        }
    });

    sortResetBtn?.addEventListener('click', resetSortView);

    function applySortView(mode) {
        const roomListEl = $('#room-list');
        const categoryRow = roomListEl?.querySelector('.row');
        if (!categoryRow) return;

        if (!isSortActive) {
            const rooms = [...$$('.room-link[data-room-id]')].filter(room => {
                const archive = room.closest('.archive-section');
                return !archive || archive.classList.contains('visible');
            });

            roomOriginalPositions = new Map(rooms.map(room => [room, {
                parent: room.parentElement,
                nextSibling: room.nextSibling,
            }]));

            flatContainer = document.createElement('div');
            flatContainer.id = 'room-list-flat';
            rooms.forEach(room => flatContainer.appendChild(room));

            categoryRow.style.display = 'none';
            roomListEl.appendChild(flatContainer);
            isSortActive = true;
        }

        const roomsInFlat = [...flatContainer.querySelectorAll('.room-link[data-room-id]')];
        roomsInFlat.sort((a, b) => {
            const diff = parseInt(b.dataset.lastActivity || '0') - parseInt(a.dataset.lastActivity || '0');
            return mode === 'oldest' ? -diff : diff;
        });
        roomsInFlat.forEach(room => flatContainer.appendChild(room));

        sortMode = mode;
        sortActivityBtn?.classList.add('active');
        const dirIcon = sortActivityBtn?.querySelector('.sort-dir-icon');
        if (dirIcon) dirIcon.className = `sort-dir-icon fas fa-arrow-${mode === 'oldest' ? 'up' : 'down'}`;
        localStorage.setItem('chat-sort-mode', mode);
    }

    function resetSortView() {
        if (!isSortActive || !roomOriginalPositions) return;

        roomOriginalPositions.forEach((pos, room) => {
            if (pos.nextSibling?.parentElement === pos.parent) {
                pos.parent.insertBefore(room, pos.nextSibling);
            } else {
                pos.parent.appendChild(room);
            }
        });

        flatContainer?.remove();
        flatContainer = null;
        roomOriginalPositions = null;
        sortMode = null;

        const categoryRow = $('#room-list')?.querySelector('.row');
        if (categoryRow) categoryRow.style.display = '';

        isSortActive = false;
        sortActivityBtn?.classList.remove('active');
        const dirIcon = sortActivityBtn?.querySelector('.sort-dir-icon');
        if (dirIcon) dirIcon.className = 'sort-dir-icon fas fa-arrow-down';
        localStorage.removeItem('chat-sort-mode');
    }

    WS_API.wsOnConnect = async () => {
        for (const user of (await WS_API.getOnlineUsers()).online_data) {
            DOM_API.updateOnline(user.room_id, user.online);
        }

        const data = await WS_API.getNotificationData();
        const enabledRooms = new Set(data.rooms.map(id => parseInt(id)));
        $$('.notif-switch[data-room-id]').forEach(btn => {
            DOM_API.setRoomNotifications(parseInt(btn.dataset.roomId), enabledRooms.has(parseInt(btn.dataset.roomId)));
        });

        // On reconnect: rejoin the current room (server lost state after disconnect)
        if (CurrentRoomId) {
            const roomToRejoin = CurrentRoomId;
            CurrentRoomId = null; // reset so onRoomTryJoin doesn't short-circuit
            onRoomTryJoin(roomToRejoin);
            return;
        }

        const action = decideStartupAction({
            search: location.search,
            hasHash: !!window.location.hash,
            isMobile: window.innerWidth < 768,
        });

        // Usun zuzyty param zeby nie zostal w URL po reload
        if (action.stripParam) {
            const url = new URL(window.location.href);
            url.searchParams.delete(action.stripParam);
            history.replaceState(null, '', url.pathname + url.search + url.hash);
        }

        // Intencja z URL aplikuje filtr — ale reczny klik usera (userToggledFilter) bije
        // URL. Bez tego: user zdejmuje filtr w oknie miedzy DOMContentLoaded a polaczeniem
        // WS, a to (czytajace wciaz obecny ?view=unread) wlaczaloby go z powrotem.
        const filterOverride = decideUnreadFilterOverride({
            urlFilter: action.unreadFilter,
            isActive: isUnreadFilterActive,
            userToggled: userToggledFilter,
        });
        if (filterOverride === 'enable') {
            isUnreadFilterActive = true;
            unreadFilterBtn?.classList.add('active');
            localStorage.setItem('chat-unread-filter', 'active');
            applyUnreadFilter();
        } else if (filterOverride === 'disable') {
            isUnreadFilterActive = false;
            unreadFilterBtn?.classList.remove('active');
            localStorage.removeItem('chat-unread-filter');
            removeUnreadFilter();
        }

        // Wymus widocznosc listy pokoi TYLKO na ten widok — bez kasowania zapisanej
        // preferencji "hide list" (uzytkownik mogl ja swiadomie ustawic; przy nastepnym
        // bezposrednim wejsciu na /chat/ ma sie zachowac jak zapamietano).
        if (action.forceListVisible) {
            const chatRoomsEl = document.querySelector('.chat-rooms');
            chatRoomsEl?.classList.remove('room-list-hidden');
            if (action.mobileShowList) {
                chatRoomsEl?.classList.add('room-list-showing');
            }
        }

        if (action.showPlaceholder) showRoomPlaceholder();

        // ?view=rooms / ?view=unread — bez auto-joina, koniec
        if (action.joinAction === 'none') return;

        let room_id = 0;
        if (window.location.hash) {
            const obj = parseParms(window.location.hash.slice(1));
            if (obj.room_id) room_id = parseInt(obj.room_id);
            if (obj.message_id) ScrollToMessageId = obj.message_id;
        }

        // Build set of room IDs the user actually has access to (rendered in DOM by server)
        const roomLinks = $$('.room-link[data-room-id]');
        const allowedRoomIds = new Set([...roomLinks].map(el => parseInt(el.dataset.roomId)));

        // Get locally stored last room ID, but only if it's in the allowed list
        if (!room_id && localStorage.lastUsedRoomID) {
            const storedId = parseInt(localStorage.lastUsedRoomID);
            if (allowedRoomIds.has(storedId)) room_id = storedId;
            else delete localStorage.lastUsedRoomID;
        }

        // Find the first public room if no room_id is set
        if (!room_id) {
            const publicRooms = $$('.room-link[data-room-id][data-room-type="public"]');
            room_id = publicRooms.length > 0 ? parseInt(publicRooms[0].dataset.roomId) : [...allowedRoomIds][0] ?? 0;
        }

        if (room_id) onRoomTryJoin(room_id);
    };
});

export async function onSocketMessage(data) {
    if (data.join || data.leave) console.warn("deprecated");
    else if (data.replace_messages) onReplaceMessages(data.messages, data.room_id);
    else if (data.messages) onReceiveMessages(data.messages);
    else if (data.unsee_room) onRoomUnsee(data.unsee_room);
    else if (data.room_seen) onRoomSeen(data.room_seen);
    else if (data.notification) onReceiveNotification(data.notification);
    else if (data.update_votes) onReceiveVotes(data.update_votes);
    else if (data.edit_message) onReceiveEdit(data.edit_message);
    else if (data.online_data) onReceiveOnlineUpdates(data.online_data);
    else if (data.update_reactions) onReceiveReactions(data.update_reactions);
    else if (data.messages_read) onReceiveReadBy(data.messages_read);
    // unread_count is consumed by the home page WS listener — ignore here
    else console.log("Cannot handle message!");
}

export async function onReceiveNotification(notification) {
    makeNotification(notification);
}

/**
 * Expands the nav-cat-content (and archive section if needed) for the given room link.
 * @param {HTMLElement} roomLink - The room link element
 */
function expandCategoryForRoom(roomLink) {
    // Expand the nav-cat-content that wraps this room
    const navCatContent = roomLink.closest('.nav-cat-content');
    if (navCatContent) {
        if (!navCatContent.classList.contains('open')) {
            navCatContent.classList.add('open');
            const catId = navCatContent.id;
            const catBtn = catId ? document.querySelector(`[data-cat-content="${catId}"]`) : null;
            if (catBtn) catBtn.setAttribute('aria-expanded', 'true');
            if (catId) localStorage.setItem(`chat-cat-${catId}`, 'expanded');
        }
    }

    // If it's inside an archive section, reveal all archived rooms via the global toggle
    if (roomLink.closest('.archive-section')) {
        document.querySelectorAll('.archive-section').forEach(s => s.classList.add('visible'));
        document.getElementById('archive-toggle-global-btn')?.classList.add('active');
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
    const navCatContent = link.closest('.nav-cat-content');
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
    const roomName = link.querySelector('.room-name')?.textContent?.trim();
    if (roomName) parts.push({ label: roomName, active: true });

    return parts;
}

export async function onRoomTryJoin(room_id) {
    room_id = parseInt(room_id);
    if (room_id === CurrentRoomId) return; // already in this room
    if (RoomLock.locked()) await RoomLock.wait();
    if (CurrentRoomId) await onRoomTryLeave(false);

    hideRoomPlaceholder();
    DOM_API.getRoomLinkDiv(room_id)?.classList.add("joined");
    if (CurrentRoomId) return; // joined another room while awaiting confirmation

    RoomLock.lock();
    // WS może być jeszcze w trakcie łączenia (np. tuż po otwarciu strony albo
    // reconnect po zerwaniu połączenia) — komenda "join" zostanie zakolejkowana
    // i wyslana automatycznie po otwarciu socketu, ale to moze potrwac chwile.
    // Pokazujemy prosty spinner na linku do pokoju, zeby user wiedzial, ze cos sie dzieje.
    const joiningRoomLink = DOM_API.getRoomLinkDiv(room_id);
    const showConnectingSpinner = !WS_API.isConnected();
    if (showConnectingSpinner) joiningRoomLink?.classList.add("connecting");
    let response;
    try {
        response = await WS_API.joinRoom(room_id);
    } catch (error) {
        RoomLock.unlock();
        if (showConnectingSpinner) joiningRoomLink?.classList.remove("connecting");
        if (error === 'ROOM_INVALID' || error === 'ACCESS_DENIED') {
            delete localStorage.lastUsedRoomID;
            DOM_API.getRoomLinkDiv(room_id)?.classList.remove("joined");
            const roomLinks = $$('.room-link[data-room-id][data-room-type="public"]')[0];
            if (roomLinks && parseInt(roomLinks.dataset.roomId) != room_id) {
                onRoomTryJoin(parseInt(roomLinks.dataset.roomId));
            }
        } else alert(error);
        return;
    }
    RoomLock.unlock();
    if (showConnectingSpinner) joiningRoomLink?.classList.remove("connecting");

    localStorage.lastUsedRoomID = room_id;
    CurrentRoomId = room_id;
    // TODO: send seen confirmation to server after a little while
    DOM_API.seenChat(room_id);
    WS_API.seenRoom(room_id);
    DOM_API.setRoomNotifications(response.notifications);
    DOM_API.createRoomDiv(CurrentRoomId, response.title, response.public, response.notifications);
    resetSortState();
    bindSortToolbar();
    DOM_API.updateBreadcrumb(deriveBreadcrumb(room_id));
    DOM_API.showFoldedRoomHeader();
    // Restore draft after DOM is fully updated
    requestAnimationFrame(() => restoreDraft(room_id));

    // Auto-expand category and archive section if needed
    const roomLink = DOM_API.getRoomLinkDiv(room_id);
    if (roomLink) {
        expandCategoryForRoom(roomLink);
    }

    // Focus only on desktop — on mobile the keyboard would open immediately
    if (window.innerWidth >= 768) {
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
    DOM_API.getRoomLinkDiv(CurrentRoomId)?.classList.remove("joined");
    DOM_API.clearRoomData();
    DOM_API.hideFoldedRoomHeader();
    resetSortState();
    for (const t of pendingTimeouts.values()) clearTimeout(t);
    pendingTimeouts.clear();
    CurrentRoomId = null;
    isClearingInput = false;
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
            const pending = msgdiv?.querySelector(`.message[data-temp-id="${message.temp_id}"]`);
            if (pending) {
                DOM_API.confirmMessage(message.temp_id, message.message_id);
                const t = pendingTimeouts.get(message.temp_id);
                if (t) { clearTimeout(t); pendingTimeouts.delete(message.temp_id); }
                DOM_API.updateSidebarForMessage(message);
                return;
            }
        }

        const current_banner = formatDate(message.timestamp);
        const banners = DOM_API.getLastMessageBanner();
        const previous_banner = banners.length ? banners[banners.length - 1].textContent : null;
        if (previous_banner != current_banner) {
            msgdiv.insertAdjacentHTML('beforeend', `<div class='date-banner'>${current_banner}</div>`);
        }
        DOM_API.addMessage(
            message.room_id, message.user_id ?? null, message.avatar_url ?? null, message.citizen_color_class ?? '', message.message_id, message.username, message.message,
            message.upvotes, message.downvotes, message.your_vote, message.own, message.edited,
            message.attachments, message.timestamp, message.latest_timestamp,
            message.reply_to ?? null,
            message.reactions ?? { bulb: 0, question: 0 },
            message.your_reactions ?? [],
            message.read_by ?? []
        );
        if (message.new) DOM_API.updateSidebarForMessage(message);
        if (message.new && !message.own) WS_API?.markMessageRead(message.message_id);
        requestAnimationFrame(() => DOM_API.markOverflow(DOM_API.getMessageDiv(message.message_id)));
    } else {
        // Batch load (join room) — build all HTML at once, single DOM insertion
        let batchHtml = '';
        let lastBannerText = DOM_API.getLastMessageBanner();
        lastBannerText = lastBannerText.length ? lastBannerText[lastBannerText.length - 1].textContent : null;

        for (const message of messages) {
            const current_banner = formatDate(message.timestamp);
            if (current_banner !== lastBannerText) {
                batchHtml += `<div class='date-banner'>${current_banner}</div>`;
                lastBannerText = current_banner;
            }
            batchHtml += DOM_API.buildMessageHtml(
                message.room_id, message.user_id ?? null, message.avatar_url ?? null, message.citizen_color_class ?? '', message.message_id, message.username, message.message,
                message.upvotes, message.downvotes, message.your_vote, message.own, message.edited,
                message.attachments, message.timestamp, message.latest_timestamp,
                message.reply_to ?? null,
                message.reactions ?? { bulb: 0, question: 0 },
                message.your_reactions ?? [],
                message.read_by ?? []
            );
        }
        if (batchHtml) msgdiv.insertAdjacentHTML('beforeend', batchHtml);

        // Apply active vote states after batch insert
        for (const message of messages) {
            if (message.your_vote) {
                DOM_API.getVoteDiv(message.message_id, message.your_vote)?.classList.add('active');
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
        msgdiv.insertAdjacentHTML('beforeend', `<div class='empty-chat-message'>${_("No messages match the current filter.")}</div>`);
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
            message.read_by ?? []
        );
        if (message.your_vote) {
            DOM_API.getVoteDiv(message.message_id, message.your_vote)?.classList.add('active');
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
        if (message_div) $$('.msg-vote', message_div).forEach(btn => btn.classList.remove('active'));
        if (event.add) active_btn?.classList.add('active');
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
        const countEl = $(`.reaction-btn[data-reaction="${key}"] .reaction-count`, msgDiv);
        const btn = $(`.reaction-btn[data-reaction="${key}"]`, msgDiv);
        if (!btn) continue;
        if (count > 0) {
            if (countEl) {
                countEl.textContent = count;
            } else {
                btn.insertAdjacentHTML('beforeend', `<span class="reaction-count">${count}</span>`);
            }
        } else if (countEl) {
            countEl.remove();
        }
    }

    // Toggle active state if it was the current user
    if (event.your_reaction !== undefined && event.your_reaction !== null) {
        const btn = $(`.reaction-btn[data-reaction="${event.your_reaction}"]`, msgDiv);
        if (btn) btn.classList.toggle('reaction-btn--active', event.added ?? false);
    }
}

/**
 * Update "read by" button and dropdown for a message after someone reads it.
 */
export async function onReceiveReadBy(event) {
    const msgDiv = DOM_API.getMessageDiv(event.message_id);
    if (!msgDiv) return;

    const readBy = event.read_by || [];
    const btn = msgDiv.querySelector('.read-by-toggle');
    const dropdown = document.getElementById(`read-by-dropdown-${event.message_id}`);
    if (!btn || !dropdown) return;

    const listHtml = readBy.map(u => {
        const colorClass = u.citizen_color_class ? `citizen-color-${u.citizen_color_class}` : '';
        const avatar = u.avatar_url
            ? `<img class="avatar avatar-xl" src="${u.avatar_url}" alt="${u.username}">`
            : `<span class="avatar avatar-xl avatar-fallback ${colorClass}">${(u.username || '').slice(0, 2).toUpperCase()}</span>`;
        return `<div class="read-by-item">${avatar}<span class="read-by-username">${u.username}</span></div>`;
    }).join('');

    let countEl = btn.querySelector('.read-by-count');
    if (!countEl) {
        countEl = document.createElement('span');
        countEl.className = 'read-by-count';
        btn.appendChild(countEl);
    }
    countEl.textContent = readBy.length;
    btn.title = `${readBy.length} osób przeczytało tę wiadomość`;
    dropdown.querySelector('.read-by-list').innerHTML = listHtml;
}

export async function onReceiveEdit(edit_info) {
    DOM_API.editMessageText(edit_info.message_id, edit_info.text, edit_info.timestamp);
    if (edit_info.attachments !== undefined) {
        DOM_API.updateMessageAttachments(edit_info.message_id, edit_info.attachments);
    }
    DOM_API.showHistoryButton(edit_info.message_id);

    if (edit_info.is_last_message) {
        DOM_API.updateSidebarForMessage({
            room_id: edit_info.room_id,
            username: edit_info.username,
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
    DOM_API.getRoomLinkDiv(room_id)?.classList.add("room-not-seen");
    DOM_API.setRoomSeenIconState(room_id, false);
    updateUnreadFilter();
}

export async function onRoomSeen(room_id) {
    DOM_API.getRoomLinkDiv(room_id)?.classList.remove("room-not-seen");
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
    this.classList.toggle('active');
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

    $("#message-history-modal .modal-body").innerHTML = MessageHistory({ history });
    const modal = $("#message-history-modal"); // Bootstrap modal show
    if (modal) {
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            new bootstrap.Modal(modal).show();
        } else {
            modal.classList.add('show');
            modal.style.display = 'block';
            document.body.classList.add('modal-open');
        }
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
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
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
    if (button?.closest('.dropdown') && window.showToast) {
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
            attachments.images = (await WS_API.uploadFiles(files)).filenames;
        }
        WS_API.editMessage(editing_message_id, message, attachments, DOM_API.getRemovedAttachments(), DOM_API.getOriginalMessageText(editing_message_id));
        // Don't stop editing immediately - let onReceiveEdit handle it after server confirms
    } else {
        const files = DOM_API.getFiles();
        const messageText = (typeof message === 'string')
            ? (message.replace(/<[^>]*>/g, '').trim())
            : '';
        if (messageText.length === 0 && (!files || files.length === 0)) return;

        const sendBtn = document.querySelector('.send-message');
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
        const ownUsername = is_anonymous
            ? 'Anonymous'
            : (document.querySelector('.user-name')?.textContent?.trim() || '');
        const now = Date.now();

        DOM_API.removeNoMessagesBanner();
        const msgdiv = DOM_API.getMessagesDiv();
        const current_banner = formatDate(now);
        const banners = DOM_API.getLastMessageBanner();
        const previous_banner = banners.length ? banners[banners.length - 1].textContent : null;
        if (previous_banner !== current_banner && msgdiv) {
            msgdiv.insertAdjacentHTML('beforeend', `<div class='date-banner'>${current_banner}</div>`);
        }

        DOM_API.addMessage(
            CurrentRoomId, null, null, '', temp_id, ownUsername, message,
            0, 0, null, true, false,
            attachments, now, now,
            reply_to, { bulb: 0, question: 0 }, [], [],
            temp_id
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
                messageInput.style.height = 'auto';
                messageInput.style.height = '38px';
            }
            clearDraft(CurrentRoomId);
            messageInput.dispatchEvent(new InputEvent('input', { bubbles: true }));
        }
        if (DOM_API.isEditing()) {
            DOM_API.stopEditing();
        }
    }
}