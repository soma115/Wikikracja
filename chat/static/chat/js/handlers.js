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

window.wkOnReady(function() {
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
        textarea.style.setProperty('--textarea-height', 'auto');
        textarea.style.setProperty('--textarea-height', Math.min(textarea.scrollHeight, 120) + 'px');
    }

    // Tree sidebar — nav-cat-btn collapse/expand
    // Default state is derived from unread rooms: the first category with an
    // .tw-room-link.tw-room-link--not-seen is expanded; others are collapsed.
    // Explicit user preference (expanded/collapsed in localStorage) takes precedence.
    function categoryHasUnreadRoom(content) {
        return !!content.querySelector('.tw-room-link.tw-room-link--not-seen');
    }

    function applyInitialCategoryState(btn, content) {
        const contentId = btn.dataset.catContent;
        if (!contentId || !content) return;

        const savedState = localStorage.getItem(`chat-cat-${contentId}`);
        let isOpen;
        if (savedState === 'expanded') {
            isOpen = true;
        } else if (savedState === 'collapsed') {
            isOpen = false;
        } else {
            isOpen = categoryHasUnreadRoom(content);
        }

        if (isOpen) closeOtherCategories(content);
        content.classList.toggle('tw-open', isOpen);
        btn.setAttribute('aria-expanded', String(isOpen));

        // When no explicit preference exists and the category is open because of
        // unread rooms, also reveal archive sections that contain unread rooms.
        if (!savedState && isOpen) {
            content.querySelectorAll('.tw-archive-section').forEach(archive => {
                if (archive.querySelector('.tw-room-link.tw-room-link--not-seen')) {
                    archive.classList.add('tw-visible');
                }
            });
        }
    }

    function closeOtherCategories(content, persist = false) {
        document.querySelectorAll('.tw-chat-cat-content').forEach(otherContent => {
            if (otherContent === content) return;
            otherContent.classList.remove('tw-open');
            const otherBtn = document.querySelector(`[data-cat-content="${otherContent.id}"]`);
            otherBtn?.setAttribute('aria-expanded', 'false');
            if (persist && otherContent.id) {
                localStorage.setItem(`chat-cat-${otherContent.id}`, 'collapsed');
            }
        });
    }

    document.querySelectorAll('.tw-chat-cat-btn').forEach(btn => {
        const contentId = btn.dataset.catContent;
        const content = contentId ? document.getElementById(contentId) : null;
        if (!content) return;
        applyInitialCategoryState(btn, content);
    });

    const globalArchiveBtn = document.getElementById('archive-toggle-global-btn');
    const archiveSectionIds = ['pub-rooms-archive', 'tasks-archive', 'votes-archive', 'documents-archive', 'surveys-archive', 'prv-archive'];
    const activeSectionIds = ['pub-rooms-active', 'tasks-active', 'votes-active', 'documents-active', 'surveys-active', 'prv-active'];

    function expandCategoriesWithArchivedRooms() {
        document.querySelectorAll('.tw-chat-cat-content').forEach(content => {
            if (!content.querySelector('.tw-archive-section .tw-room-link')) return;
            content.classList.add('tw-open');
            const catBtn = document.querySelector(`[data-cat-content="${content.id}"]`);
            catBtn?.setAttribute('aria-expanded', 'true');
        });
    }

    function setArchivesVisible(visible) {
        archiveSectionIds.forEach(targetId => {
            document.getElementById(`content-${targetId}`)?.classList.toggle('tw-visible', visible);
        });
        activeSectionIds.forEach(targetId => {
            document.getElementById(`content-${targetId}`)?.classList.toggle('tw-d-none', visible);
        });
        if (visible) expandCategoriesWithArchivedRooms();
        document.getElementById('room-list')?.classList.toggle('tw-archive-mode', visible);
        document.dispatchEvent(new CustomEvent('chat-archive-visibility-changed', { detail: { visible } }));
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

    function toggleCategory(btn, content) {
        const isOpen = content.classList.contains('tw-open');
        if (!isOpen && !globalArchiveBtn?.classList.contains('tw-active')) {
            closeOtherCategories(content, true);
        }
        content.classList.toggle('tw-open', !isOpen);
        btn.setAttribute('aria-expanded', String(!isOpen));
        const contentId = btn.dataset.catContent;
        if (contentId) {
            localStorage.setItem(`chat-cat-${contentId}`, isOpen ? 'collapsed' : 'expanded');
        }
    }

    const roomSearchInput = document.getElementById('room-search');
    roomSearchInput?.addEventListener('input', () => {
        const query = roomSearchInput.value.trim().toLowerCase();
        document.querySelectorAll('.tw-room-link[data-room-id]').forEach(roomLink => {
            const name = (roomLink.querySelector('.tw-room-name')?.textContent || '').toLowerCase();
            roomLink.classList.toggle('tw-room-link--search-filtered-out', query !== '' && !name.includes(query));
        });
        updateSearchEmptyState(query);
    });

    // New-room modal: search all public rooms as the name is typed. The server
    // intentionally includes archived rooms so old discussions can be reused.
    const addRoomForm = document.getElementById('add-room-form');
    const addRoomInput = document.getElementById('add-room-input');
    const addRoomResults = document.getElementById('add-room-results');
    const addRoomError = document.getElementById('add-room-error');
    let addRoomSearchTimer;
    let addRoomSearchController;

    function renderAddRoomResults(rooms) {
        if (!addRoomResults) return;
        addRoomResults.replaceChildren();
        if (!rooms.length) return;

        const heading = document.createElement('p');
        heading.className = 'tw-text-muted tw-mb-2';
        heading.textContent = _('Existing rooms matching this name:');
        addRoomResults.appendChild(heading);

        const list = document.createElement('div');
        list.className = 'tw-list-group';
        rooms.forEach(room => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'tw-list-group-item tw-flex tw-items-center tw-justify-between tw-gap-2 tw-text-start';
            item.dataset.roomId = room.id;

            const name = document.createElement('span');
            name.className = 'tw-flex-1';
            name.textContent = room.title;
            item.appendChild(name);

            if (room.archived) {
                const badge = document.createElement('span');
                badge.className = 'tw-badge tw-badge-secondary tw-flex-shrink-0';
                badge.textContent = _('Archived');
                item.appendChild(badge);
            }
            list.appendChild(item);
        });
        addRoomResults.appendChild(list);
    }

    addRoomInput?.addEventListener('input', () => {
        const query = addRoomInput.value.trim();
        clearTimeout(addRoomSearchTimer);
        addRoomSearchController?.abort();
        renderAddRoomResults([]);
        if (!query) return;

        addRoomSearchTimer = setTimeout(async () => {
            addRoomSearchController = new AbortController();
            try {
                const url = new URL(addRoomInput.dataset.searchUrl, window.location.origin);
                url.searchParams.set('q', query);
                const response = await window.apiFetch(url.pathname + url.search, {
                    fetchOptions: { signal: addRoomSearchController.signal },
                });
                if (response.ok) renderAddRoomResults((await response.json()).rooms || []);
            } catch (error) {
                if (error.name !== 'AbortError') renderAddRoomResults([]);
            }
        }, 200);
    });

    addRoomResults?.addEventListener('click', (event) => {
        const room = event.target.closest('[data-room-id]');
        if (!room) return;
        if (typeof TwModal !== 'undefined') TwModal.hide(document.getElementById('add-room-modal'));
        navigateToRoom(room.dataset.roomId);
    });

    addRoomForm?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const title = addRoomInput?.value.trim() || '';
        if (!title) return;
        addRoomError?.classList.add('tw-d-none');
        try {
            const response = await window.apiFetch(addRoomForm.action, {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                body: new URLSearchParams({ title }),
            });
            const data = await response.json();
            if (!response.ok) {
                if (addRoomError) {
                    addRoomError.textContent = data.error || _('Could not create the room.');
                    addRoomError.classList.remove('tw-d-none');
                }
                return;
            }
            if (typeof TwModal !== 'undefined') TwModal.hide(document.getElementById('add-room-modal'));
            navigateToRoom(data.room_id);
        } catch {
            if (addRoomError) {
                addRoomError.textContent = _('Connection error.');
                addRoomError.classList.remove('tw-d-none');
            }
        }
    });

    document.getElementById('add-room-modal')?.addEventListener('shown.tw.modal', () => {
        addRoomInput?.focus();
    });
    document.getElementById('add-room-modal')?.addEventListener('hidden.tw.modal', () => {
        if (addRoomInput) addRoomInput.value = '';
        addRoomError?.classList.add('tw-d-none');
        renderAddRoomResults([]);
    });

    // nav-cat-btn click: toggle category open/closed
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.tw-chat-cat-btn');
        if (!btn) return;
        const contentId = btn.dataset.catContent;
        const content = contentId ? document.getElementById(contentId) : null;
        if (!content) return;
        toggleCategory(btn, content);
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

    // ── Breadcrumb aria-expanded mirror ───────────────────────────────────────
    const chatRoomsEl = $('.tw-chat-rooms');

    // Chat-only swipe: right-to-left opens the room list. Keep the Android
    // system back-gesture area free by ignoring touches that start at the edge.
    (function initRoomListSwipe() {
        if (!chatRoomsEl) return;

        const MIN_DX = 60;
        const LEFT_EDGE_GUARD_RATIO = 0.25;
        const RIGHT_EDGE_GUARD = 32;
        let startX = 0;
        let startY = 0;
        let tracking = false;
        let canOpenRoomList = false;
        let suppressClickUntil = 0;

        document.addEventListener('touchstart', (e) => {
            if (!mobileMedia.matches || e.touches.length !== 1) return;
            if (!e.target.closest('.tw-chat-root-messages')) return;
            if (e.target.closest('input, textarea, select, [contenteditable]')) return;

            const touch = e.touches[0];
            tracking = true;
            canOpenRoomList = !document.getElementById('sidebar')?.classList.contains('tw-sidebar-open')
                && !chatRoomsEl.classList.contains('tw-room-list-showing')
                && touch.clientX > window.innerWidth * LEFT_EDGE_GUARD_RATIO
                && touch.clientX < window.innerWidth - RIGHT_EDGE_GUARD;
            startX = touch.clientX;
            startY = touch.clientY;
        }, { passive: true });

        const stopTracking = () => {
            tracking = false;
        };

        document.addEventListener('touchcancel', stopTracking, { passive: true });
        document.addEventListener('touchend', (e) => {
            if (!tracking) return;
            tracking = false;
            const touch = e.changedTouches[0];
            if (!touch) return;

            const dx = touch.clientX - startX;
            const dy = touch.clientY - startY;
            if (Math.abs(dy) > Math.abs(dx)) return;
            if (Math.abs(dx) >= MIN_DX) suppressClickUntil = Date.now() + 500;
            if (canOpenRoomList && dx <= -MIN_DX) navigateToRoomList();
        }, { passive: true });

        document.addEventListener('click', (e) => {
            if (Date.now() >= suppressClickUntil) return;
            e.preventDefault();
            e.stopPropagation();
            suppressClickUntil = 0;
        }, true);
    })();

    function updateBreadcrumbAria() {
        const listShowing = chatRoomsEl?.classList.contains('tw-room-list-showing');
        const bc = document.getElementById('chat-breadcrumb');
        if (bc) {
            bc.setAttribute('aria-expanded', String(!!listShowing));
        }
    }

    // Desktop room-list collapse is no longer supported — always show the list.
    // Clean up any stale state from previous sessions.
    chatRoomsEl?.classList.remove('tw-room-list-hidden');
    localStorage.removeItem('chat-desktop-room-list-hidden');
    localStorage.removeItem('chat-room-list-hidden');

    if (chatRoomsEl) {
        new MutationObserver(updateBreadcrumbAria).observe(chatRoomsEl, {
            attributes: true,
            attributeFilter: ['class'],
        });
    }
    updateBreadcrumbAria();

    function closestBreadcrumb(target) {
        // Clicking directly on text inside a segment gives a TEXT_NODE target,
        // which has no .closest(); use its parent element instead.
        const el = target.nodeType === Node.TEXT_NODE ? target.parentElement : target;
        return el?.closest('#chat-breadcrumb') || null;
    }

    // #chat-breadcrumb: on mobile acts as a back button to the room list.
    document.addEventListener('click', (e) => {
        if (e.button !== 0) return;
        const bc = closestBreadcrumb(e.target);
        if (!bc) return;
        if (mobileMedia.matches) navigateToRoomList();
    });

    // Tap-to-close: przy rozwiniętej liście (szuflada 80% od prawej) klik
    // w odsłonięty pasek pokoju po lewej zamyka listę. Capture — przechwytuje
    // klik zanim zadziałają linki/przyciski/podgląd obrazków pod spodem.
    document.addEventListener('click', (e) => {
        if (e.button !== 0) return;
        if (!mobileMedia.matches) return;
        if (!chatRoomsEl?.classList.contains('tw-room-list-showing')) return;
        if (!e.target.closest('.tw-chat-root-messages')) return;
        e.preventDefault();
        e.stopPropagation();
        const roomId = getCurrentRoomId();
        if (roomId != null) navigateToRoom(roomId);
    }, true);
    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        const bc = closestBreadcrumb(e.target);
        if (!bc) return;
        e.preventDefault();
        if (mobileMedia.matches) navigateToRoomList();
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

