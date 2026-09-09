/**
 * @file chat-embedded.js
 * Embedded chat widget — reużywa Message template i CSS z głównego czatu.
 *
 * Użycie w template:
 *   <div class="tw-embedded-chat" data-room-id="42" data-csrf="{{ csrf_token }}"></div>
 *   <script type="module" src="{% static 'chat/js/chat-embedded.js' %}"></script>
 */

import { clearReplyTarget, createEditHandler, createImageClickHandler, createQuoteJumpHandler, createReactionHandler, createReplyHandler, createVoteHandler, formatMessage, getInputHtml, handleEnterKey, initFormattingToolbar, initGlobalPasteImageHandler, insertPlainTextAtCaret, setReplyTarget, updateCounter, uploadFiles, voteButtonTitle } from './chat-core.js';
import { Message } from './templates.js';
import { _, dateBannerHtml, formatDate, formatTime } from './utility.js';
import { getSharedWebSocket } from './websocket-manager.js';

/**
 * Inicjalizuje embedded chat dla podanego elementu DOM.
 * @param {HTMLElement} container  - div.embedded-chat z data-room-id i data-csrf
 */
async function initEmbeddedChat(container) {
    const roomId = parseInt(container.dataset.roomId, 10);
    if (!roomId) return;

    const EC_MAX = window.SITE_SETTINGS?.messageMaxLength ?? 500;

    // ── 1. Zbuduj HTML widgetu ────────────────────────────────────────────────
    container.innerHTML = `
        <div class="tw-ec-wrapper">
            <div class="tw-ec-messages tw-chat-messages" id="ec-messages-${roomId}">
                <div class="tw-ec-loading">Ładowanie…</div>
            </div>
            <div class="tw-ec-input-area">
                <div class="tw-reply-preview tw-d-none" id="ec-reply-preview-${roomId}">
                    <span class="tw-reply-preview-label">↩ </span>
                    <span class="tw-reply-preview-text" id="ec-reply-preview-text-${roomId}"></span>
                    <button class="tw-reply-preview-close tw-ec-reply-cancel" type="button" title="Anuluj odpowiedź">✕</button>
                </div>
                <div class="tw-image-preview-container tw-ec-image-preview-container tw-d-none" id="ec-image-preview-${roomId}">
                    <div class="tw-preview-images tw-ec-preview-images" id="ec-preview-images-${roomId}"></div>
                    <div class="tw-delete-images-preview tw-ec-delete-images-preview" id="ec-delete-images-${roomId}">
                        <i class="fas fa-times"></i>
                    </div>
                </div>
                <div class="tw-compose-box tw-ec-form-row" id="ec-form-row-${roomId}">
                    <div id="ec-input-${roomId}" class="tw-message-input-rich" role="textbox"
                         contenteditable="true" aria-multiline="true"
                         data-placeholder="${_('Reply to the appropriate message...')}"
                         data-hint="${_('Enter send · Shift/Ctrl+Enter new line · Ctrl+B bold · Ctrl+I italic')}"></div>
                    <div class="tw-compose-bar">
                        <div class="tw-compose-bar-left">
                            <input type="file" id="ec-file-input-${roomId}" class="tw-file-input tw-ec-file-input tw-d-none" multiple="multiple"/>
                            <label class="tw-fmt-btn" for="ec-file-input-${roomId}" title="${_('Attach image')}">
                                <i class="fas fa-image"></i>
                            </label>
                            <div class="tw-compose-separator"></div>
                            <div class="tw-fmt-toolbar">
                                <button class="tw-fmt-btn" data-cmd="bold"      type="button" title="Ctrl+B"><b>B</b></button>
                                <button class="tw-fmt-btn" data-cmd="italic"    type="button" title="Ctrl+I"><i>I</i></button>
                                <button class="tw-fmt-btn" data-cmd="underline" type="button" title="Ctrl+U"><u>U</u></button>
                            </div>
                            <div class="tw-compose-separator"></div>
                            <button class="tw-fmt-btn tw-anonymous-toggle tw-ec-anonymous-toggle" id="ec-anonymous-${roomId}" type="button" title="${_('Anonymous')}">
                                <i class="fas fa-user-secret"></i>
                            </button>
                        </div>
                        <div class="tw-compose-bar-right">
                            <div class="tw-msg-counter" id="ec-counter-${roomId}">
                                <span id="ec-counter-val-${roomId}">${EC_MAX}</span> / ${EC_MAX}
                            </div>
                            <button class="tw-send-message tw-btn tw-btn-primary tw-compose-send tw-ec-send-btn" id="ec-send-${roomId}" type="button">
                                <i class="fas fa-paper-plane"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    const messagesEl = container.querySelector(`#ec-messages-${roomId}`);
    const inputEl = container.querySelector(`#ec-input-${roomId}`);
    const sendBtn = container.querySelector(`#ec-send-${roomId}`);
    const counterEl = container.querySelector(`#ec-counter-${roomId}`);
    const counterVal = container.querySelector(`#ec-counter-val-${roomId}`);
    const replyPreview = container.querySelector(`#ec-reply-preview-${roomId}`);
    const replyPreviewText = container.querySelector(`#ec-reply-preview-text-${roomId}`);
    const fileInput = container.querySelector(`#ec-file-input-${roomId}`);
    const previewContainer = container.querySelector(`#ec-image-preview-${roomId}`);
    const previewImagesDiv = container.querySelector(`#ec-preview-images-${roomId}`);
    const deleteImagesBtn = container.querySelector(`#ec-delete-images-${roomId}`);

    let currentReplyId = null;
    let lastDateBanner = null;
    let isAnonymous = false;
    let selectedFiles = [];
    const canPost = container.dataset.canPost !== 'false';

    if (!canPost) {
        const inputArea = container.querySelector('.tw-ec-input-area');
        if (inputArea) {
            inputArea.innerHTML = `<div class="tw-ec-readonly-notice"><i class="fas fa-lock"></i> ${_("Only approved helpers can write here.")}</div>`;
        }
    }

    // ── 2. Local helpers ─────────────────────────────────────────────────────

    function appendMessage(msg) {
        messagesEl.querySelector('.tw-ec-empty, .tw-ec-loading')?.remove();
        const dateStr = formatDate(msg.timestamp);
        if (dateStr !== lastDateBanner) {
            lastDateBanner = dateStr;
            messagesEl.insertAdjacentHTML('beforeend', dateBannerHtml(dateStr));
        }

        const html = Message({
            room_id: roomId,
            user_id: msg.user_id ?? null,
            avatar_url: msg.avatar_url ?? null,
            citizen_color_class: msg.citizen_color_class ?? '',
            message_id: msg.message_id,
            username: msg.username,
            display_name: msg.display_name ?? null,
            initials: msg.initials ?? null,
            message: formatMessage(msg.message),
            raw_message: msg.message,
            upvotes: msg.upvotes ?? 0,
            downvotes: msg.downvotes ?? 0,
            vote: msg.your_vote ?? null,
            own: msg.own ?? false,
            edited: msg.edited ?? false,
            attachments: msg.attachments ?? {},
            original_ts: msg.timestamp,
            latest_ts: formatTime(msg.latest_timestamp ?? msg.timestamp),
            type: "public",
            reply_to: msg.reply_to ?? null,
            reactions: msg.reactions ?? { bulb: 0, question: 0 },
            your_reactions: msg.your_reactions ?? [],
            read_by: msg.read_by ?? [],
            upvoters: msg.upvoters ?? null,
            downvoters: msg.downvoters ?? null,
        });
        messagesEl.insertAdjacentHTML('beforeend', html);
        if (msg.your_vote) {
            const msgDiv = messagesEl.querySelector(`.tw-chat-message[data-message-id="${msg.message_id}"]`);
            msgDiv?.querySelector(`.tw-msg-vote[data-event-name="${msg.your_vote}"]`)?.classList.add('tw-active');
        }
        if (msg.own) unlockSendBtn();
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function updateMessage({ message_id, message, latest_timestamp }) {
        const msgDiv = messagesEl.querySelector(`.tw-chat-message[data-message-id="${message_id}"]`);
        if (!msgDiv) return;
        const textEl = msgDiv.querySelector('.tw-msg-text');
        const timeEl = msgDiv.querySelector('.tw-message-timestamp');
        if (textEl) {
            // data-raw musi nadążać za innerHTML — następna edycja czyta dataset.raw jako "oryginalny tekst do edytowania".
            textEl.dataset.raw = message;
            textEl.innerHTML = formatMessage(message);
        }
        if (timeEl) timeEl.textContent = formatTime(latest_timestamp);
    }

    let ecSendLockTimeout = null;

    function lockSendBtn() {
        sendBtn.disabled = true;
        ecSendLockTimeout = setTimeout(() => { sendBtn.disabled = false; }, 5000);
    }

    function unlockSendBtn() {
        sendBtn.disabled = false;
        clearTimeout(ecSendLockTimeout);
    }

    function sendMessage() {
        const html = getInputHtml(inputEl);
        const text = (inputEl.textContent || '').trim();
        if (!text && selectedFiles.length === 0) return;
        if (!joined) return;
        if (text.length > EC_MAX) return;

        lockSendBtn();

        // Upload files if any selected
        if (selectedFiles.length > 0) {
            uploadFiles(selectedFiles).then((uploadResp) => {
                ws.sendJson({
                    command: 'send',
                    room_id: roomId,
                    message: html,
                    is_anonymous: isAnonymous,
                    attachments: { images: uploadResp.filenames || [] },
                    ...(currentReplyId ? { reply_to_id: currentReplyId } : {}),
                });
                inputEl.innerHTML = '';
                currentReplyId = clearReplyTarget(replyPreview);
                selectedFiles = [];
                fileInput.value = '';
                if (previewContainer) previewContainer.classList.add('tw-d-none');
                if (previewImagesDiv) previewImagesDiv.innerHTML = '';
                updateCounter(inputEl, counterEl, counterVal, sendBtn, EC_MAX);
            }).catch((err) => {
                console.error('Upload error:', err);
                unlockSendBtn();
            });
        } else {
            ws.sendJson({
                command: 'send',
                room_id: roomId,
                message: html,
                is_anonymous: isAnonymous,
                attachments: {},
                ...(currentReplyId ? { reply_to_id: currentReplyId } : {}),
            });
            inputEl.innerHTML = '';
            currentReplyId = clearReplyTarget(replyPreview);
            updateCounter(inputEl, counterEl, counterVal, sendBtn, EC_MAX);
        }
    }

    // ── 3. WebSocket ──────────────────────────────────────────────────────────
    const ws = getSharedWebSocket();
    let joined = false;
    let pendingMessages = [];
    let joinDone = false;

    let joinInFlight = false;

    function joinRoom() {
        if (joined || joinInFlight) return;
        joinInFlight = true;
        ws.sendJsonAsync({ command: 'join', room_id: roomId })
            .then(() => {
                joinInFlight = false;
                joined = true;
                setTimeout(() => {
                    joinDone = true;
                    messagesEl.innerHTML = '';
                    lastDateBanner = null;
                    for (const msg of pendingMessages) appendMessage(msg);
                    pendingMessages = [];
                    if (messagesEl.children.length === 0) {
                        messagesEl.innerHTML = '<div class="tw-ec-empty tw-empty-chat-message">' + window.escapeHtml(_('No messages. Write the first one!')) + '</div>';
                    }
                }, 0);
            })
            .catch(err => {
                joinInFlight = false;
                if (err === 'REQUEST_TIMEOUT') {
                    // Błąd przejściowy — spróbuj ponownie, nie pokazuj "brak dostępu".
                    console.warn('embedded chat join timeout, retrying:', err);
                    setTimeout(() => { if (!joined && ws.isOpen()) joinRoom(); }, 5000);
                    return;
                }
                messagesEl.innerHTML = '<div class="tw-ec-loading">' + window.escapeHtml(_('No access to this chat.')) + '</div>';
                container.querySelector('.tw-ec-input-area')?.classList.add('tw-d-none');
                console.error('embedded chat join error:', err);
            });
    }

    function onMessage(data) {
        if (data.messages) {
            for (const msg of data.messages) {
                if (msg.room_id && msg.room_id !== roomId) continue;
                if (!joinDone) pendingMessages.push(msg);
                else appendMessage(msg);
            }
        }
        if (data.edit_message) {
            updateMessage(data.edit_message);
        }
        if (data.update_reactions) {
            const ev = data.update_reactions;
            const msgDiv = messagesEl.querySelector(`.tw-chat-message[data-message-id="${ev.message_id}"]`);
            if (!msgDiv) return;
            for (const [key, count] of Object.entries(ev.counts || {})) {
                const btn = msgDiv.querySelector(`.tw-reaction-btn[data-reaction="${key}"]`);
                if (!btn) continue;
                const countEl = btn.querySelector('.tw-reaction-count');
                if (count > 0) {
                    if (countEl) countEl.textContent = count;
                    else btn.insertAdjacentHTML('beforeend', `<span class="tw-reaction-count">${count}</span>`);
                } else if (countEl) countEl.remove();
            }
            if (ev.your_reaction != null) {
                const btn = msgDiv.querySelector(`.tw-reaction-btn[data-reaction="${ev.your_reaction}"]`);
                if (btn) btn.classList.toggle('tw-reaction-btn--active', ev.added ?? false);
            }
        }
        if (data.update_votes) {
            const ev = data.update_votes;
            const msgDiv = messagesEl.querySelector(`.tw-chat-message[data-message-id="${ev.message_id}"]`);
            if (!msgDiv) return;
            const upEl = msgDiv.querySelector('.tw-msg-upvotes');
            const dnEl = msgDiv.querySelector('.tw-msg-downvotes');
            if (upEl) upEl.textContent = ev.upvotes;
            if (dnEl) dnEl.textContent = ev.downvotes;
            if (ev.your_vote) {
                msgDiv.querySelectorAll('.tw-msg-vote').forEach(b => b.classList.remove('tw-active'));
                if (ev.add) msgDiv.querySelector(`.tw-msg-vote[data-event-name="${ev.your_vote}"]`)?.classList.add('tw-active');
            }
            // Pokoje zadań: serwer dosyła nicki głosujących — odśwież tooltipsy łapek.
            if (ev.upvoters !== undefined) {
                const upBtn = msgDiv.querySelector('.tw-msg-vote[data-event-name="upvote"]');
                const dnBtn = msgDiv.querySelector('.tw-msg-vote[data-event-name="downvote"]');
                if (upBtn) upBtn.title = voteButtonTitle(_('Upvote'), ev.upvoters);
                if (dnBtn) dnBtn.title = voteButtonTitle(_('Downvote'), ev.downvoters);
            }
        }
    }

    const unsubscribeMessages = ws.subscribeMessages(onMessage);

    // Lifecycle przez subskrypcję — obejmuje pierwszy open (także gdy socket
    // już jest otwarty) oraz reconnect: po zerwaniu serwer gubi członkostwo
    // w pokoju, więc resetujemy lokalny stan i dołączamy ponownie.
    const unsubscribeConnection = ws.subscribeConnection({
        onOpen: () => {
            joined = false;
            joinDone = false;
            pendingMessages = [];
            joinRoom();
        },
        onClose: () => {
            joined = false;
            joinDone = false;
        },
    });

    // ── 4. Eventy UI ──────────────────────────────────────────────────────────

    // File input handler
    fileInput?.addEventListener('change', (e) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;

        selectedFiles = Array.from(files);
        if (previewContainer) previewContainer.classList.remove('tw-d-none');
        if (previewImagesDiv) previewImagesDiv.innerHTML = '';

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const fr = new FileReader();
            const previewId = `ec-preview-${i}-${Date.now()}`;

            if (previewImagesDiv) {
                previewImagesDiv.insertAdjacentHTML('beforeend', `
                    <div class="tw-image-preview-wrapper tw-ec-image-preview-wrapper">
                        <img class="tw-image-preview tw-new-attachment" id="${previewId}">
                        <button class="tw-btn tw-btn-sm tw-btn-danger tw-ec-remove-preview tw-image-preview-remove" data-preview-id="${previewId}" type="button">×</button>
                    </div>
                `);
            }

            fr.onload = (event) => {
                const img = document.getElementById(previewId);
                if (img) img.src = event.target.result;
            };
            fr.readAsDataURL(file);
        }
    });

    // Delete images preview
    deleteImagesBtn?.addEventListener('click', () => {
        selectedFiles = [];
        fileInput.value = '';
        if (previewContainer) previewContainer.classList.add('tw-d-none');
        if (previewImagesDiv) previewImagesDiv.innerHTML = '';
    });

    // Remove single preview
    container.addEventListener('click', (e) => {
        const removeBtn = e.target.closest('.tw-ec-remove-preview');
        if (removeBtn) {
            const previewId = removeBtn.dataset.previewId;
            removeBtn.closest('.tw-image-preview-wrapper')?.remove();
            // Update selectedFiles by reading from input again
            if (previewImagesDiv && previewImagesDiv.children.length === 0) {
                selectedFiles = [];
                fileInput.value = '';
                if (previewContainer) previewContainer.classList.add('tw-d-none');
            }
        }
    });

    // Toggle anonymous
    const anonBtn = container.querySelector(`#ec-anonymous-${roomId}`);
    if (anonBtn) {
        anonBtn.addEventListener('click', () => {
            isAnonymous = !isAnonymous;
            anonBtn.classList.toggle('tw-active', isAnonymous);
        });
    }

    inputEl.addEventListener('input', () => updateCounter(inputEl, counterEl, counterVal, sendBtn, EC_MAX));

    // insertPlainTextAtCaret turns \n into explicit <br> nodes (not browser-wrapped
    // <div> blocks) and fires 'input', so the counter listener handles updates.
    inputEl.addEventListener('paste', (e) => {
        e.preventDefault();
        const pasted = (e.clipboardData || window.clipboardData).getData('text');
        insertPlainTextAtCaret(inputEl, pasted, EC_MAX);
    });

    const { updateToolbarState } = initFormattingToolbar(container, inputEl);

    inputEl.addEventListener('keydown', (e) => {
        const mod = e.ctrlKey || e.metaKey;
        if (mod && e.key === 'b') { e.preventDefault(); document.execCommand('bold'); updateToolbarState(); return; }
        if (mod && e.key === 'i') { e.preventDefault(); document.execCommand('italic'); updateToolbarState(); return; }
        if (mod && e.key === 'u') { e.preventDefault(); document.execCommand('underline'); updateToolbarState(); return; }
        // Enter = wyślij, Shift/Ctrl+Enter = nowa linia
        if (handleEnterKey(e, submitInput)) return;
    });

    // Anuluj odpowiedź
    container.querySelector('.tw-ec-reply-cancel')?.addEventListener('click', () => {
        currentReplyId = clearReplyTarget(replyPreview);
    });

    // ── Shared handlers from chat-core.js ────────────────────────────────────
    const voteHandler = createVoteHandler((eventName, messageId, isAdd) => {
        // Toggle active state on button
        const btn = messagesEl.querySelector(`.tw-msg-vote[data-event-name="${eventName}"][data-message-id="${messageId}"]`);
        if (btn) btn.classList.toggle('tw-active', isAdd);
        if (!joined) return;
        ws.sendJson({
            command: isAdd ? 'message-add-vote' : 'message-remove-vote',
            vote: eventName,
            message_id: messageId,
        });
    });

    const reactionHandler = createReactionHandler((reaction, messageId) => {
        if (!joined) return;
        ws.sendJson({ command: 'message-react', reaction, message_id: messageId });
    });

    function startEdit(messageId, inputElRef) {
        const msgDiv = messagesEl.querySelector(`.tw-chat-message[data-message-id="${messageId}"]`);
        const msgText = msgDiv?.querySelector('.tw-msg-text')?.innerHTML ?? '';
        inputElRef.dataset.editMessage = messageId;
        inputElRef.innerHTML = msgText;
        inputElRef.classList.add('tw-editing');
        inputElRef.focus();
        updateCounter(inputElRef, counterEl, counterVal, sendBtn, EC_MAX);
    }

    const editHandler = createEditHandler(startEdit, inputEl);

    const replyHandler = createReplyHandler(
        (msgId, username, snippet, preview, previewText) => {
            currentReplyId = setReplyTarget(msgId, username, snippet, preview, previewText);
        },
        replyPreview,
        replyPreviewText,
        inputEl
    );

    const quoteJumpHandler = createQuoteJumpHandler(messagesEl);

    // Attach shared handlers
    messagesEl.addEventListener('click', voteHandler);
    messagesEl.addEventListener('click', reactionHandler);
    messagesEl.addEventListener('click', replyHandler);
    messagesEl.addEventListener('click', editHandler);
    messagesEl.addEventListener('click', quoteJumpHandler);
    messagesEl.addEventListener('click', createImageClickHandler());

    function submitInput() {
        if (inputEl.dataset.editMessage) {
            ws.sendJson({ command: 'edit-message', message_id: parseInt(inputEl.dataset.editMessage), new_message: getInputHtml(inputEl) });
            delete inputEl.dataset.editMessage;
            inputEl.innerHTML = '';
            inputEl.classList.remove('tw-editing');
            updateCounter(inputEl, counterEl, counterVal, sendBtn, EC_MAX);
        } else {
            sendMessage();
        }
    }

    sendBtn.addEventListener('click', submitInput);

    inputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && inputEl.dataset.editMessage) {
            delete inputEl.dataset.editMessage;
            inputEl.innerHTML = '';
            inputEl.classList.remove('tw-editing');
            updateCounter(inputEl, counterEl, counterVal, sendBtn, EC_MAX);
        }
    });

    // ── 5. Cleanup ────────────────────────────────────────────────────────────
    window.addEventListener('beforeunload', () => {
        unsubscribeMessages();
        unsubscribeConnection();
        if (joined) ws.sendJson({ command: 'leave', room_id: roomId });
    });
}

// ── Initialization ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initGlobalPasteImageHandler();
    for (const el of document.querySelectorAll('.tw-embedded-chat[data-room-id]')) {
        initEmbeddedChat(el);
    }
});