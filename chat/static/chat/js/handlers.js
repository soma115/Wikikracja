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
    onMessageHistory,
    onRoomTryJoin,
    onSubmitMessage,
    onToggleNotifications,
    onToggleReaction,
    onToggleSeen,
    onUpdateVote,
    setReplyTarget
} from './chat.js';
import DomApi from './domapi.js';
import { $, $$, _ } from './utility.js';

/**
 * DOM API instance for UI operations
 * @type {DomApi}
 */
const DOM_API = new DomApi();

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
        row.classList.remove('counter--warn', 'counter--error');
        const composeBox = $('.compose-box');
        if (remaining <= 0) {
            row.classList.add('counter--error');
            composeBox?.classList.add('input--error');
        } else if (remaining <= 10) {
            row.classList.add('counter--error');
            composeBox?.classList.remove('input--error');
        } else if (remaining <= 50) {
            row.classList.add('counter--warn');
            composeBox?.classList.remove('input--error');
        } else {
            composeBox?.classList.remove('input--error');
        }
        const sendBtn = $('.send-message');
        if (sendBtn) sendBtn.disabled = remaining <= 0;
    }

    function showToast(message) {
        const existing = document.getElementById('chat-toast');
        if (existing) existing.remove();
        const toast = document.createElement('div');
        toast.id = 'chat-toast';
        toast.className = 'chat-toast';
        toast.textContent = message;
        document.body.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add('chat-toast--visible'));
        setTimeout(() => {
            toast.classList.remove('chat-toast--visible');
            setTimeout(() => toast.remove(), 300);
        }, 2500);
    }
    window.showToast = showToast;

    const { updateToolbarState } = initFormattingToolbar(document, () => $('#message-input'));

    // Inicjalizacja dropdownow w liscie pokoi z popper strategy:'fixed'.
    // Pozwala dropdownowi wyjsc poza overflow:hidden na .nav-cat-content (animacja collapse).
    if (typeof bootstrap !== 'undefined' && bootstrap.Dropdown) {
        document.querySelectorAll('.room-link__chevron[data-bs-toggle="dropdown"]').forEach(btn => {
            new bootstrap.Dropdown(btn, {
                popperConfig(defaultConfig) {
                    return { ...defaultConfig, strategy: 'fixed' };
                },
            });
        });
    }

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
            if (wouldOverflow) showToast('Wiadomość przycięta do ' + MSG_MAX + ' znaków');
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
                showToast('Wiadomość przycięta do ' + MSG_MAX + ' znaków');
            }
        }
    });

    function autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }

    // Tree sidebar — nav-cat-btn collapse/expand
    // Restore cat states from localStorage (before click handler, so initial state is set)
    document.querySelectorAll('.nav-cat-btn').forEach(btn => {
        const contentId = btn.dataset.catContent;
        if (!contentId) return;
        const content = document.getElementById(contentId);
        if (!content) return;
        const savedState = localStorage.getItem(`chat-cat-${contentId}`);
        if (savedState === 'expanded') {
            content.classList.add('open');
            btn.setAttribute('aria-expanded', 'true');
        } else {
            content.classList.remove('open');
            btn.setAttribute('aria-expanded', 'false');
        }
    });

    const globalArchiveBtn = document.getElementById('archive-toggle-global-btn');
    const archiveSectionIds = ['pub-rooms-archive', 'tasks-archive', 'votes-archive', 'prv-archive'];

    function setArchivesVisible(visible) {
        archiveSectionIds.forEach(targetId => {
            document.getElementById(`content-${targetId}`)?.classList.toggle('visible', visible);
        });
        globalArchiveBtn?.classList.toggle('active', visible);
        if (visible) localStorage.setItem('chat-archive-global', 'visible');
        else localStorage.removeItem('chat-archive-global');
    }

    if (localStorage.getItem('chat-archive-global') === 'visible') {
        setArchivesVisible(true);
    }

    globalArchiveBtn?.addEventListener('click', () => {
        setArchivesVisible(!globalArchiveBtn.classList.contains('active'));
    });

    const roomSearchInput = document.getElementById('room-search');
    roomSearchInput?.addEventListener('input', () => {
        const query = roomSearchInput.value.trim().toLowerCase();
        document.querySelectorAll('.room-link[data-room-id]').forEach(roomLink => {
            const name = (roomLink.querySelector('.room-name')?.textContent || '').toLowerCase();
            roomLink.classList.toggle('search-filtered-out', query !== '' && !name.includes(query));
        });
    });

    // nav-cat-btn click: toggle category open/closed
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.nav-cat-btn');
        if (!btn) return;
        const contentId = btn.dataset.catContent;
        const content = contentId ? document.getElementById(contentId) : null;
        if (!content) return;
        const isOpen = content.classList.contains('open');
        content.classList.toggle('open', !isOpen);
        btn.setAttribute('aria-expanded', String(!isOpen));
        if (contentId) {
            localStorage.setItem(`chat-cat-${contentId}`, isOpen ? 'collapsed' : 'expanded');
        }
    });

    // collapse-all-btn: toggle all categories at once
    document.getElementById('collapse-all-btn')?.addEventListener('click', () => {
        const allOpen = [...document.querySelectorAll('.nav-cat-content')].every(c => c.classList.contains('open'));
        document.querySelectorAll('.nav-cat-btn').forEach(btn => {
            const contentId = btn.dataset.catContent;
            const content = contentId ? document.getElementById(contentId) : null;
            if (!content) return;
            content.classList.toggle('open', !allOpen);
            btn.setAttribute('aria-expanded', String(!allOpen));
            if (contentId) localStorage.setItem(`chat-cat-${contentId}`, allOpen ? 'collapsed' : 'expanded');
        });
        const icon = document.querySelector('#collapse-all-btn i');
        if (icon) icon.className = allOpen ? 'fas fa-angles-down' : 'fas fa-angles-up';
    });

    document.addEventListener("click", (e) => {
        if (e.target.closest(".send-message")) {
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
            // Enter = nowa linia; wysyłanie przez Ctrl+Enter lub Shift+Enter
            if (e.key === 'Enter') {
                e.preventDefault();
                if (mod || e.shiftKey) { onSubmitMessage(DOM_API.getEnteredText(), DOM_API.getEditedMessageId()); }
                else { document.execCommand('insertLineBreak'); }
                return;
            }
            return;
        }

        if (e.key === 'Enter' && !e.shiftKey) {
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
        const btn = e.target.closest('.notif-switch');
        if (btn) {
            const newState = !(btn.dataset.enabled === "true" || btn.dataset.enabled === true);
            btn.dataset.enabled = newState;
            const icon = $("i", btn);
            icon?.classList.toggle('fa-bell', newState);
            icon?.classList.toggle('fa-bell-slash', !newState);
            const label = btn.querySelector('.notif-label');
            if (label) label.textContent = newState ? _('Mute room') : _('Unmute room');
            const meta = btn.closest('.room-link')?.querySelector('.room-link__meta');
            if (meta) {
                meta.dataset.muted = newState ? 'false' : 'true';
                let mutedIcon = meta.querySelector('.room-link__muted-icon');
                if (!newState) {
                    if (!mutedIcon) {
                        mutedIcon = document.createElement('i');
                        mutedIcon.className = 'fas fa-bell-slash room-link__muted-icon';
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
        const btn = e.target.closest('.seen-switch');
        if (btn) {
            e.preventDefault();
            e.stopPropagation();
            const isCurrentlySeen = btn.dataset.seen === "true";
            const newState = !isCurrentlySeen;
            DOM_API.getRoomLinkDiv(btn.dataset.roomId)?.classList.toggle('room-not-seen', !newState);
            DOM_API.setRoomSeenIconState(btn.dataset.roomId, newState);
            onToggleSeen(btn.dataset.roomId, newState);
            // Update unread filter if it's active
            if (typeof window.updateUnreadFilter === 'function') {
                window.updateUnreadFilter();
            }
        }
    });

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.anonymous-toggle');
        if (btn) {
            btn.classList.toggle('active');
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === "Escape" && DOM_API.isEditing()) {
            DOM_API.stopEditing();
        }
    });

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.delete-images-preview');
        if (btn) DOM_API.clearFiles(btn.dataset.roomId);
    });

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.copy-room-url');
        if (btn) {
            e.preventDefault();
            e.stopPropagation();
            copyRoomLink(btn.dataset.roomId, btn);
        }
    });

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.copy-message-url');
        if (btn) {
            e.preventDefault();
            e.stopPropagation();
            copyMessageLink(btn.dataset.roomId, btn.dataset.messageId, btn);
        }
    });

    document.addEventListener("change", (e) => {
        if (!e.target.classList.contains("file-input")) return;
        const files = e.target.files;
        const preview_container = DOM_API.getPreviewDiv();
        if (!DOM_API.isEditing() && preview_container) preview_container.innerHTML = '';
        if (files.length > 0) DOM_API.getPreviewContainer().style.display = '';
        for (let i = 0; i < files.length; ++i) {
            const file = files.item(i);
            const fr = new FileReader();
            const preview_id = `preview-new-${i}-${Date.now()}`;
            preview_container?.insertAdjacentHTML('beforeend', `<div class="image-preview-wrapper" style="position: relative; display: inline-block;">
                <img class='image-preview new-attachment' id='${preview_id}'>
                <button class="btn btn-sm btn-danger remove-new-attachment"
                    style="position: absolute; top: 2px; right: 2px; padding: 0 4px; font-size: 12px;"
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
        const btn = document.querySelector('.msg-vote[data-event-name="' + eventName + '"][data-message-id="' + messageId + '"]');
        if (btn) btn.classList.toggle('active', isAdd);
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
        const btn = e.target.closest(".remove-existing-attachment");
        if (btn) {
            e.preventDefault();
            e.stopPropagation();
            DOM_API.addRemovedAttachment(btn.dataset.filename);
            btn.closest('.image-preview-wrapper')?.remove();
            if (DOM_API.getPreviewDiv()?.children.length === 0) {
                DOM_API.getPreviewContainer().style.display = 'none';
            }
        }
    });

    document.addEventListener("click", (e) => {
        const btn = e.target.closest(".remove-new-attachment");
        if (btn) {
            e.preventDefault();
            e.stopPropagation();
            btn.closest('.image-preview-wrapper')?.remove();
            const previewDiv = DOM_API.getPreviewDiv();
            if (previewDiv && $$('.new-attachment', previewDiv).length === 0) {
                DOM_API.getFileInput().value = "";
            }
            if (previewDiv?.children.length === 0) {
                DOM_API.getPreviewContainer().style.display = 'none';
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
        () => document.querySelector('#room .messages')
    ));

    document.addEventListener('click', (e) => {
        if (e.target.closest('#reply-preview-close')) {
            clearReplyTarget(document.getElementById('reply-preview'));
            return;
        }
    });


    document.addEventListener('click', handleRoomLinkClick);

    function handleRoomLinkClick(e) {
        if (e.target.closest('.room-link__actions')) return;
        const roomLink = e.target.closest('.room-link');
        if (!roomLink) return;
        if (roomLink.classList.contains("joined")) {
            // Mobile: klik w już aktywny pokój = wróć do tego pokoju (zwiń rozwiniętą listę)
            if (window.innerWidth < 768) mobileHideRoomList();
            return;
        }
        const room_id = roomLink.getAttribute("data-room-id");
        roomLink.classList.add('room-tapping');
        setTimeout(() => roomLink.classList.remove('room-tapping'), 300);
        DOM_API.getRoomLinkDiv(room_id)?.classList.remove("room-not-seen");
        DOM_API.setRoomSeenIconState(room_id, true);
        onRoomTryJoin(room_id);
        if (typeof window.updateUnreadFilter === 'function') {
            window.updateUnreadFilter();
        }
    }

    // ── Room list show/hide ───────────────────────────────────────────────────
    const chatRoomsEl = $('.chat-rooms');
    const HIDDEN_KEY = 'chat-room-list-hidden';

    function setRoomListHidden(hidden) {
        chatRoomsEl?.classList.toggle('room-list-hidden', hidden);
        if (hidden) localStorage.setItem(HIDDEN_KEY, '1');
        else localStorage.removeItem(HIDDEN_KEY);
        updateToggleBtn();
    }

    function updateToggleBtn() {
        const hidden = chatRoomsEl?.classList.contains('room-list-hidden');
        // Button in sort toolbar (dynamic, inside #room)
        const dynBtn = document.getElementById('toggle-room-list-btn');
        if (dynBtn) {
            dynBtn.querySelector('i').className = hidden ? 'fas fa-angles-left' : 'fas fa-angles-right';
            dynBtn.title = hidden ? 'Show room list' : 'Hide room list';
        }
        // Button in room-list-controls (static, desktop only)
        const staticBtn = document.getElementById('room-list-toggle-static-btn');
        if (staticBtn) {
            staticBtn.querySelector('i').className = hidden ? 'fas fa-angles-left' : 'fas fa-angles-right';
            staticBtn.title = hidden ? 'Show room list' : 'Hide room list';
        }
    }

    // Restore saved state — desktop only; mobile always starts with list visible
    if (window.innerWidth < 768) {
        chatRoomsEl?.classList.remove('room-list-hidden');
    } else if (localStorage.getItem(HIDDEN_KEY)) {
        setRoomListHidden(true);
    }

    // Mobile: show room list (keep room joined, just switch view)
    function mobileShowRoomList() {
        chatRoomsEl?.classList.add('room-list-showing');
    }
    // Mobile: hide room list and return to chat view
    function mobileHideRoomList() {
        chatRoomsEl?.classList.remove('room-list-showing');
    }
    // #toggle-room-list-btn (inside room area): on mobile shows room list without leaving room
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('#toggle-room-list-btn');
        if (!btn) return;
        if (window.innerWidth < 768) {
            mobileShowRoomList();
        } else {
            setRoomListHidden(!chatRoomsEl?.classList.contains('room-list-hidden'));
        }
    });

    // #room-list-toggle-static-btn (obok "Nieprzeczytane"): na mobile zwija listę, na desktop toggle
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('#room-list-toggle-static-btn');
        if (!btn) return;
        if (window.innerWidth < 768) {
            mobileHideRoomList();
        } else {
            setRoomListHidden(!chatRoomsEl?.classList.contains('room-list-hidden'));
        }
    });

    // Handle window resize
    window.addEventListener('resize', () => {
        if (window.innerWidth >= 768 && !localStorage.getItem(HIDDEN_KEY)) {
            setRoomListHidden(false);
        }
    });

    // ── Rename room ───────────────────────────────────────────────────────────
    let renameRoomId = null;
    const renameModal = document.getElementById('rename-room-modal');
    const renameInput = document.getElementById('rename-room-input');
    const renameError = document.getElementById('rename-room-error');
    const renameConfirm = document.getElementById('rename-room-confirm');
    const bsRenameModal = renameModal && typeof bootstrap !== 'undefined'
        ? bootstrap.Modal.getOrCreateInstance(renameModal) : null;
    const showRenameError = (msg) => { if (renameError) { renameError.textContent = msg; renameError.style.display = ''; } };

    let renameOriginalTitle = null;

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.rename-room-btn');
        if (!btn) return;
        e.preventDefault();
        e.stopPropagation();
        renameRoomId = btn.dataset.roomId;
        renameOriginalTitle = btn.dataset.roomTitle || '';
        if (renameInput) renameInput.value = renameOriginalTitle;
        if (renameError) { renameError.style.display = 'none'; renameError.textContent = ''; }
        bsRenameModal?.show();
        setTimeout(() => renameInput?.select(), 300);
    });

    renameConfirm?.addEventListener('click', async () => {
        if (!renameRoomId) return;
        const newTitle = (renameInput?.value || '').trim();
        if (!newTitle) { showRenameError('Nazwa nie może być pusta.'); return; }
        if (newTitle === renameOriginalTitle) { bsRenameModal?.hide(); return; }
        try {
            const resp = await fetch(`/chat/api/room/${renameRoomId}/rename/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '' },
                body: JSON.stringify({ title: newTitle }),
            });
            const data = await resp.json();
            if (!resp.ok) { showRenameError(data.error || 'Błąd.'); return; }
            bsRenameModal?.hide();
            const roomLink = document.querySelector(`.room-link[data-room-id="${renameRoomId}"]`);
            if (roomLink) {
                roomLink.querySelector('.room-name')?.replaceChildren(document.createTextNode(data.title));
                const btn = roomLink.querySelector('.rename-room-btn');
                if (btn) btn.dataset.roomTitle = data.title;
            }
            showToast('Nazwa pokoju zmieniona.');
        } catch {
            showRenameError('Błąd połączenia.');
        }
    });

    renameInput?.addEventListener('keydown', (e) => { if (e.key === 'Enter') renameConfirm?.click(); });
});

