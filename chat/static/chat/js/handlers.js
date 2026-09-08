/**
 * @file
 * Event handlers module for chat UI interactions.
 */

import {
    clearReplyTarget,
    createEditHandler,
    createHistoryHandler,
    createImageClickHandler,
    createQuoteJumpHandler,
    createReactionHandler,
    createReplyHandler,
    createVoteHandler,
    initFormattingToolbar,
    initGlobalPasteImageHandler,
    insertPlainTextAtCaret,
} from './chat-core.js';
import {
    copyMessageLink,
    copyRoomLink,
    getCurrentRoomId,
    navigateToRoom,
    navigateToRoomList,
    onMessageHistory,
    onSubmitMessage,
    onToggleNotifications,
    onToggleReaction,
    onToggleSeen,
    onUpdateVote,
    setReplyTarget
} from './chat.js';
import DomApi from './domapi.js';
import { $, $$, _, mobileMedia } from './utility.js';

/**
 * DOM API instance for UI operations
 * @type {DomApi}
 */
const DOM_API = new DomApi();

/**
 * Jawny stan "brak wyników wyszukiwania" — pusta lista bez komunikatu to
 * pusty ekran. Notka ląduje w #room-list obok .room-list-groups; gdy jest
 * widoczna, CSS (:has) chowa drzewo kategorii i płaską listę.
 * Tekst przez textContent (defense-in-depth).
 */
function updateSearchEmptyState(query) {
    const list = document.getElementById('room-list');
    if (!list) return;
    const anyMatch = [...document.querySelectorAll('.tw-room-link[data-room-id]')]
        .some(link => !link.classList.contains('tw-room-link--search-filtered-out'));
    const show = query !== '' && !anyMatch;
    let note = document.getElementById('chat-no-search-results');
    if (show && !note) {
        note = document.createElement('div');
        note.id = 'chat-no-search-results';
        note.className = 'tw-chat-no-search-results';
        const icon = document.createElement('i');
        icon.className = 'fas fa-magnifying-glass tw-chat-no-room-icon';
        icon.setAttribute('aria-hidden', 'true');
        const text = document.createElement('p');
        text.className = 'tw-chat-no-room-text';
        text.textContent = _('No rooms match the search.');
        note.append(icon, text);
        list.appendChild(note);
    } else if (!show) {
        note?.remove();
    }
}

document.addEventListener('DOMContentLoaded', function() {
    initGlobalPasteImageHandler();
    const MSG_MAX = window.SITE_SETTINGS?.messageMaxLength ?? 500;

    function updateCounter(text) {
        const remaining = MSG_MAX - text.length;
        const counterVal = $('#msg-counter-val');
        if (!counterVal) return;
        counterVal.textContent = remaining;
        const row = $('#msg-counter');
        if (!row) return;
        window.applyCounterState(row, remaining);
        $('.tw-compose-box')?.classList.toggle('tw-compose-box--error', remaining <= 0);
        const sendBtn = $('.tw-send-message');
        if (sendBtn) sendBtn.disabled = remaining <= 0;
    }

    const showToast = (message) => window.showToast(message);

    const { updateToolbarState } = initFormattingToolbar(document, () => $('#message-input'));

    // Tailwind dropdowns auto-inicjalizuja sie po data-tw-toggle;
    // room-link__chevron uzywa data-tw-dropdown-fixed zeby wyjsc poza overflow:hidden.

    // Update counter on input; no auto-resize needed for contenteditable
    document.addEventListener('input', (e) => {
        if (e.target.id === 'message-input') {
            const el = e.target;
            const text = el.isContentEditable ? (el.textContent || '') : el.value;
            updateCounter(text);
        }
    });

    // Paste interception: strip HTML and truncate if over limit.
    // For contenteditable, insertPlainTextAtCaret turns \n into explicit <br> nodes
    // (bypassing browser auto-wrap that produced ghost empty lines on render)
    // and dispatches 'input', so the counter listener handles updates.
    document.addEventListener('paste', (e) => {
        if (e.target.id !== 'message-input') return;
        const el = e.target;
        const pastedText = (e.clipboardData || window.clipboardData).getData('text');
        if (el.isContentEditable) {
            e.preventDefault();
            const currentLength = (el.textContent || '').length;
            const sel = window.getSelection();
            const selectedLength = sel?.toString().length ?? 0;
            const wouldOverflow = currentLength - selectedLength + pastedText.length > MSG_MAX;
            insertPlainTextAtCaret(el, pastedText, MSG_MAX);
            if (wouldOverflow) showToast(_('Message trimmed to {max} characters').replace('{max}', MSG_MAX));
        } else {
            const val = el.value;
            const start = el.selectionStart;
            const end = el.selectionEnd;
            const newVal = val.slice(0, start) + pastedText + val.slice(end);
            if (newVal.length > MSG_MAX) {
                e.preventDefault();
                const truncated = newVal.slice(0, MSG_MAX);
                el.value = truncated;
                el.selectionStart = el.selectionEnd = Math.min(start + pastedText.length, MSG_MAX);
                autoResizeTextarea(el);
                updateCounter(truncated);
                showToast(_('Message trimmed to {max} characters').replace('{max}', MSG_MAX));
            }
        }
    });

    function autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }

    // Tree sidebar — nav-cat-btn collapse/expand
    // Restore cat states from localStorage (before click handler, so initial state is set)
    document.querySelectorAll('.tw-chat-cat-btn').forEach(btn => {
        const contentId = btn.dataset.catContent;
        if (!contentId) return;
        const content = document.getElementById(contentId);
        if (!content) return;
        const savedState = localStorage.getItem(`chat-cat-${contentId}`);
        if (savedState === 'expanded') {
            content.classList.add('tw-open');
            btn.setAttribute('aria-expanded', 'true');
        } else {
            content.classList.remove('tw-open');
            btn.setAttribute('aria-expanded', 'false');
        }
    });

    const globalArchiveBtn = document.getElementById('archive-toggle-global-btn');
    const archiveSectionIds = ['pub-rooms-archive', 'tasks-archive', 'votes-archive', 'documents-archive', 'prv-archive'];

    function setArchivesVisible(visible) {
        archiveSectionIds.forEach(targetId => {
            document.getElementById(`content-${targetId}`)?.classList.toggle('tw-visible', visible);
        });
        globalArchiveBtn?.classList.toggle('tw-active', visible);
        if (visible) localStorage.setItem('chat-archive-global', 'visible');
        else localStorage.removeItem('chat-archive-global');
    }

    if (localStorage.getItem('chat-archive-global') === 'visible') {
        setArchivesVisible(true);
    }

    globalArchiveBtn?.addEventListener('click', () => {
        setArchivesVisible(!globalArchiveBtn.classList.contains('tw-active'));
    });

    const roomSearchInput = document.getElementById('room-search');
    roomSearchInput?.addEventListener('input', () => {
        const query = roomSearchInput.value.trim().toLowerCase();
        document.querySelectorAll('.tw-room-link[data-room-id]').forEach(roomLink => {
            const name = (roomLink.querySelector('.tw-room-name')?.textContent || '').toLowerCase();
            roomLink.classList.toggle('tw-room-link--search-filtered-out', query !== '' && !name.includes(query));
        });
        updateSearchEmptyState(query);
    });

    // nav-cat-btn click: toggle category open/closed
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.tw-chat-cat-btn');
        if (!btn) return;
        const contentId = btn.dataset.catContent;
        const content = contentId ? document.getElementById(contentId) : null;
        if (!content) return;
        const isOpen = content.classList.contains('tw-open');
        content.classList.toggle('tw-open', !isOpen);
        btn.setAttribute('aria-expanded', String(!isOpen));
        if (contentId) {
            localStorage.setItem(`chat-cat-${contentId}`, isOpen ? 'collapsed' : 'expanded');
        }
    });

    // collapse-all-btn: toggle all categories at once
    document.getElementById('collapse-all-btn')?.addEventListener('click', () => {
        const allOpen = [...document.querySelectorAll('.tw-chat-cat-content')].every(c => c.classList.contains('tw-open'));
        document.querySelectorAll('.tw-chat-cat-btn').forEach(btn => {
            const contentId = btn.dataset.catContent;
            const content = contentId ? document.getElementById(contentId) : null;
            if (!content) return;
            content.classList.toggle('tw-open', !allOpen);
            btn.setAttribute('aria-expanded', String(!allOpen));
            if (contentId) localStorage.setItem(`chat-cat-${contentId}`, allOpen ? 'collapsed' : 'expanded');
        });
        const icon = document.querySelector('#collapse-all-btn i');
        if (icon) icon.className = allOpen ? 'fas fa-angles-down' : 'fas fa-angles-up';
    });

    document.addEventListener("click", (e) => {
        if (e.target.closest(".tw-send-message")) {
            onSubmitMessage(DOM_API.getEnteredText(), DOM_API.getEditedMessageId());
        }
    });

    document.addEventListener("keydown", (e) => {
        if (e.target.id !== "message-input") return;
        const el = e.target;
        const mod = e.ctrlKey || e.metaKey;

        // Rich text shortcuts
        if (el.isContentEditable) {
            if (mod && e.key === 'b') { e.preventDefault(); document.execCommand('bold'); updateToolbarState(); return; }
            if (mod && e.key === 'i') { e.preventDefault(); document.execCommand('italic'); updateToolbarState(); return; }
            if (mod && e.key === 'u') { e.preventDefault(); document.execCommand('underline'); updateToolbarState(); return; }
            // Enter = wyślij; nowa linia przez Ctrl+Enter lub Shift+Enter
            if (e.key === 'Enter') {
                e.preventDefault();
                if (mod || e.shiftKey) { document.execCommand('insertLineBreak'); }
                else { onSubmitMessage(DOM_API.getEnteredText(), DOM_API.getEditedMessageId()); }
                return;
            }
            return;
        }

        if (e.key === 'Enter' && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
            e.preventDefault();
            onSubmitMessage(DOM_API.getEnteredText(), DOM_API.getEditedMessageId());
        }
        if (e.key === "ArrowUp") {
            e.preventDefault();
            const message = DOM_API.getLatestOwnMessage();
            if (!DOM_API.isEditing()) {
                DOM_API.setEditing(message?.dataset.messageId);
            }
        }
    });

    document.addEventListener('click', createImageClickHandler());

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.tw-notif-switch');
        if (btn) {
            const newState = !(btn.dataset.enabled === "true" || btn.dataset.enabled === true);
            btn.dataset.enabled = newState;
            const icon = $("i", btn);
            icon?.classList.toggle('fa-bell', newState);
            icon?.classList.toggle('fa-bell-slash', !newState);
            const label = btn.querySelector('.tw-notif-label');
            if (label) label.textContent = newState ? _('Mute room') : _('Unmute room');
            const meta = btn.closest('.tw-room-link')?.querySelector('.tw-room-link-meta');
            if (meta) {
                meta.dataset.muted = newState ? 'false' : 'true';
                let mutedIcon = meta.querySelector('.tw-room-link-muted-icon');
                if (!newState) {
                    if (!mutedIcon) {
                        mutedIcon = document.createElement('i');
                        mutedIcon.className = 'fas fa-bell-slash tw-room-link-muted-icon';
                        mutedIcon.title = _('Muted');
                        meta.appendChild(mutedIcon);
                    }
                } else {
                    mutedIcon?.remove();
                }
            }
            onToggleNotifications(btn.dataset.roomId, newState);
        }
    });

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.tw-seen-switch');
        if (btn) {
            e.preventDefault();
            e.stopPropagation();
            const isCurrentlySeen = btn.dataset.seen === "true";
            const newState = !isCurrentlySeen;
            DOM_API.getRoomLinkDiv(btn.dataset.roomId)?.classList.toggle('tw-room-link--not-seen', !newState);
            DOM_API.setRoomSeenIconState(btn.dataset.roomId, newState);
            onToggleSeen(btn.dataset.roomId, newState);
            // Update unread filter if it's active
            if (typeof window.updateUnreadFilter === 'function') {
                window.updateUnreadFilter();
            }
        }
    });

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.tw-anonymous-toggle');
        if (btn) {
            btn.classList.toggle('tw-active');
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === "Escape" && DOM_API.isEditing()) {
            DOM_API.stopEditing();
        }
    });

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.tw-delete-images-preview');
        if (btn) DOM_API.clearFiles(btn.dataset.roomId);
    });

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.tw-copy-room-url');
        if (btn) {
            e.preventDefault();
            e.stopPropagation();
            copyRoomLink(btn.dataset.roomId, btn);
        }
    });

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.tw-copy-message-url');
        if (btn) {
            e.preventDefault();
            e.stopPropagation();
            copyMessageLink(btn.dataset.roomId, btn.dataset.messageId, btn);
        }
    });

    document.addEventListener("change", (e) => {
        if (!e.target.classList.contains("tw-file-input")) return;
        const files = e.target.files;
        const preview_container = DOM_API.getPreviewDiv();
        if (!DOM_API.isEditing() && preview_container) preview_container.innerHTML = '';
        if (files.length > 0) DOM_API.getPreviewContainer().classList.remove('tw-d-none');
        for (let i = 0; i < files.length; ++i) {
            const file = files.item(i);
            const fr = new FileReader();
            const preview_id = `preview-new-${i}-${Date.now()}`;
            preview_container?.insertAdjacentHTML('beforeend', `<div class="tw-image-preview-wrapper">
                <img class='tw-image-preview tw-new-attachment' id='${preview_id}'>
                <button class="tw-btn tw-btn-sm tw-btn-danger tw-remove-new-attachment tw-image-preview-remove"
                    data-preview-id="${preview_id}" type="button">×</button>
            </div>`);
            fr.onload = (e) => {
                document.getElementById(preview_id).src = e.target.result;
            };
            fr.readAsDataURL(file);
        }
    });

    // ── Shared handlers from chat-core.js ────────────────────────────────────

    document.addEventListener('click', createVoteHandler(function(eventName, messageId, isAdd) {
        const btn = document.querySelector('.tw-msg-vote[data-event-name="' + eventName + '"][data-message-id="' + messageId + '"]');
        if (btn) btn.classList.toggle('tw-active', isAdd);
        onUpdateVote.call(btn, eventName, messageId, isAdd);
    }));

    document.addEventListener('click', createReactionHandler(function(reaction, messageId) {
        onToggleReaction(reaction, messageId);
    }));

    document.addEventListener('click', createHistoryHandler(function(messageId) {
        onMessageHistory(messageId);
    }));

    document.addEventListener('click', createEditHandler(function(messageId, inputEl) {
        DOM_API.setEditing(messageId);
    }, $('#message-input')));

    document.addEventListener("click", (e) => {
        const btn = e.target.closest(".tw-remove-existing-attachment");
        if (btn) {
            e.preventDefault();
            e.stopPropagation();
            DOM_API.addRemovedAttachment(btn.dataset.filename);
            btn.closest('.tw-image-preview-wrapper')?.remove();
            if (DOM_API.getPreviewDiv()?.children.length === 0) {
                DOM_API.getPreviewContainer().classList.add('tw-d-none');
            }
        }
    });

    document.addEventListener("click", (e) => {
        const btn = e.target.closest(".tw-remove-new-attachment");
        if (btn) {
            e.preventDefault();
            e.stopPropagation();
            btn.closest('.tw-image-preview-wrapper')?.remove();
            const previewDiv = DOM_API.getPreviewDiv();
            if (previewDiv && $$('.tw-new-attachment', previewDiv).length === 0) {
                DOM_API.getFileInput().value = "";
            }
            if (previewDiv?.children.length === 0) {
                DOM_API.getPreviewContainer().classList.add('tw-d-none');
            }
        }
    });

    // Quote/Reply
    document.addEventListener('click', createReplyHandler(
        function(msgId, username, snippet, preview, previewText) {
            setReplyTarget(msgId, username, snippet, preview, previewText);
            const inputEl = $('#message-input');
            if (inputEl) inputEl.focus();
        },
        document.getElementById('reply-preview'),
        document.getElementById('reply-preview-text'),
        $('#message-input')
    ));

    document.addEventListener('click', createQuoteJumpHandler(
        () => document.querySelector('#room .tw-chat-messages')
    ));

    document.addEventListener('click', (e) => {
        if (e.target.closest('#reply-preview-close')) {
            clearReplyTarget(document.getElementById('reply-preview'));
            return;
        }
    });


    document.addEventListener('click', handleRoomLinkClick);

    function handleRoomLinkClick(e) {
        if (e.target.closest('.tw-room-link-actions')) return;
        const roomLink = e.target.closest('.tw-room-link');
        if (!roomLink) return;
        if (roomLink.classList.contains("tw-room-link--joined")) {
            // Mobile: klik w już aktywny pokój = wróć do niego (lista nakłada się
            // na pokój). Nawigacja przez URL — router sam zauważy identyczną trasę.
            if (mobileMedia.matches) navigateToRoom(parseInt(roomLink.dataset.roomId));
            return;
        }
        const room_id = roomLink.getAttribute("data-room-id");
        roomLink.classList.add('tw-room-link--tapping');
        setTimeout(() => roomLink.classList.remove('tw-room-link--tapping'), 300);
        DOM_API.getRoomLinkDiv(room_id)?.classList.remove("tw-room-link--not-seen");
        DOM_API.setRoomSeenIconState(room_id, true);
        navigateToRoom(parseInt(room_id));
        if (typeof window.updateUnreadFilter === 'function') {
            window.updateUnreadFilter();
        }
    }

    // ── Room list show/hide ───────────────────────────────────────────────────
    const chatRoomsEl = $('.tw-chat-rooms');
    // Preferencja zwinięcia dotyczy wyłącznie desktopu — na mobile panel listy
    // wynika z nawigacji (room-list-showing), nie z zapisanego stanu.
    const HIDDEN_KEY = 'chat-desktop-room-list-hidden';
    const LEGACY_HIDDEN_KEY = 'chat-room-list-hidden';

    // Jednorazowa migracja starego klucza — bez cichej utraty preferencji.
    const legacyHidden = localStorage.getItem(LEGACY_HIDDEN_KEY);
    if (legacyHidden !== null) {
        if (localStorage.getItem(HIDDEN_KEY) === null) {
            localStorage.setItem(HIDDEN_KEY, legacyHidden);
        }
        localStorage.removeItem(LEGACY_HIDDEN_KEY);
    }

    function setRoomListHidden(hidden) {
        chatRoomsEl?.classList.toggle('tw-room-list-hidden', hidden);
        if (hidden) localStorage.setItem(HIDDEN_KEY, '1');
        else localStorage.removeItem(HIDDEN_KEY);
        updateToggleBtn();
    }

    function updateToggleBtn() {
        const hidden = chatRoomsEl?.classList.contains('tw-room-list-hidden');
        const listShowing = chatRoomsEl?.classList.contains('tw-room-list-showing');
        // Button in sort toolbar (dynamic, inside #room)
        const dynBtn = document.getElementById('toggle-room-list-btn');
        if (dynBtn) {
            dynBtn.querySelector('i').className = hidden ? 'fas fa-angles-left' : 'fas fa-angles-right';
            dynBtn.title = hidden ? 'Show room list' : 'Hide room list';
            // Na mobile ten przycisk pokazuje listę nad pokojem.
            dynBtn.setAttribute('aria-expanded', String(mobileMedia.matches ? !!listShowing : !hidden));
        }
        // Button in room-list-controls (static, desktop only)
        const staticBtn = document.getElementById('room-list-toggle-static-btn');
        if (staticBtn) {
            staticBtn.querySelector('i').className = hidden ? 'fas fa-angles-left' : 'fas fa-angles-right';
            staticBtn.title = hidden ? 'Show room list' : 'Hide room list';
            staticBtn.setAttribute('aria-expanded', String(!hidden));
        }
    }

    // Restore saved state — desktop only; mobile never restores the collapse.
    if (mobileMedia.matches) {
        chatRoomsEl?.classList.remove('tw-room-list-hidden');
    } else if (localStorage.getItem(HIDDEN_KEY)) {
        setRoomListHidden(true);
    }

    // Klasy widoku na .chat-rooms zmienia router (chat.js) i desktopowa
    // preferencja — obserwujemy je, żeby ikony i aria-expanded przycisków
    // zawsze odzwierciedlały rzeczywisty stan.
    if (chatRoomsEl) {
        new MutationObserver(updateToggleBtn).observe(chatRoomsEl, {
            attributes: true,
            attributeFilter: ['class'],
        });
    }
    updateToggleBtn();

    // #toggle-room-list-btn (inside room area): na mobile prowadzi do listy
    // przez URL (Wstecz wraca do pokoju); na desktopie przełącza zwinięcie.
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('#toggle-room-list-btn');
        if (!btn) return;
        if (mobileMedia.matches) {
            navigateToRoomList();
        } else {
            setRoomListHidden(!chatRoomsEl?.classList.contains('tw-room-list-hidden'));
        }
    });

    // #room-list-toggle-static-btn: na mobile wraca do dołączonego pokoju,
    // na desktopie przełącza zwinięcie listy.
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('#room-list-toggle-static-btn');
        if (!btn) return;
        if (mobileMedia.matches) {
            const joined = getCurrentRoomId();
            if (joined) navigateToRoom(joined);
        } else {
            setRoomListHidden(!chatRoomsEl?.classList.contains('tw-room-list-hidden'));
        }
    });

    // Przejście przez breakpoint — preferencja desktopowa jest prezentowana
    // tylko na desktopie; po stronie mobile klasa jest usuwana bez kasowania
    // zapisanej preferencji.
    mobileMedia.addEventListener('change', (e) => {
        if (e.matches) {
            chatRoomsEl?.classList.remove('tw-room-list-hidden');
            updateToggleBtn();
        } else {
            setRoomListHidden(!!localStorage.getItem(HIDDEN_KEY));
        }
    });

    // ── Rename room ───────────────────────────────────────────────────────────
    let renameRoomId = null;
    const renameModal = document.getElementById('rename-room-modal');
    const renameInput = document.getElementById('rename-room-input');
    const renameError = document.getElementById('rename-room-error');
    const renameConfirm = document.getElementById('rename-room-confirm');
    const showRenameError = (msg) => { if (renameError) { renameError.textContent = msg; renameError.classList.remove('tw-d-none'); } };

    let renameOriginalTitle = null;

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.tw-rename-room-btn');
        if (!btn) return;
        e.preventDefault();
        e.stopPropagation();
        renameRoomId = btn.dataset.roomId;
        renameOriginalTitle = btn.dataset.roomTitle || '';
        if (renameInput) renameInput.value = renameOriginalTitle;
        if (renameError) { renameError.classList.add('tw-d-none'); renameError.textContent = ''; }
        if (renameModal && typeof TwModal !== 'undefined') TwModal.show(renameModal);
        setTimeout(() => renameInput?.select(), 300);
    });

    renameConfirm?.addEventListener('click', async () => {
        if (!renameRoomId) return;
        const newTitle = (renameInput?.value || '').trim();
        if (!newTitle) { showRenameError(_('The name cannot be empty.')); return; }
        if (newTitle === renameOriginalTitle) {
            if (renameModal && typeof TwModal !== 'undefined') TwModal.hide(renameModal);
            return;
        }
        try {
            const resp = await window.apiFetch(`/chat/api/room/${renameRoomId}/rename/`, {
                method: 'POST',
                body: { title: newTitle },
            });
            const data = await resp.json();
            if (!resp.ok) { showRenameError(data.error || _('Error.')); return; }
            if (renameModal && typeof TwModal !== 'undefined') TwModal.hide(renameModal);
            const roomLink = document.querySelector(`.tw-room-link[data-room-id="${renameRoomId}"]`);
            if (roomLink) {
                roomLink.querySelector('.tw-room-name')?.replaceChildren(document.createTextNode(data.title));
                const btn = roomLink.querySelector('.tw-rename-room-btn');
                if (btn) btn.dataset.roomTitle = data.title;
            }
            showToast(_('Room name changed.'));
        } catch {
            showRenameError(_('Connection error.'));
        }
    });

    renameInput?.addEventListener('keydown', (e) => { if (e.key === 'Enter') renameConfirm?.click(); });

    // ── Read by dropdown toggle ─────────────────────────────────────────────────
    let openReadByDropdown = null;

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.tw-read-by-toggle');
        if (btn) {
            e.preventDefault();
            e.stopPropagation();
            const messageId = btn.dataset.messageId;
            const dropdown = document.getElementById(`read-by-dropdown-${messageId}`);
            if (!dropdown) return;

            // Close previously open dropdown
            if (openReadByDropdown && openReadByDropdown !== dropdown) {
                openReadByDropdown.classList.add('tw-d-none');
            }

            // Toggle current dropdown
            const isHidden = dropdown.classList.contains('tw-d-none');
            dropdown.classList.toggle('tw-d-none', !isHidden);
            openReadByDropdown = isHidden ? dropdown : null;
        } else if (openReadByDropdown && !e.target.closest('.tw-read-by-dropdown')) {
            // Close dropdown when clicking outside
            openReadByDropdown.classList.add('tw-d-none');
            openReadByDropdown = null;
        }
    });
});

